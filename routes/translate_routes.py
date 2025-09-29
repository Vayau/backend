import os
import tempfile
import uuid
import hashlib
import re
from flask import Blueprint, request, jsonify
from utils.supabase import supabase
from functions import PDFTranslator
from deep_translator import GoogleTranslator

translate_bp = Blueprint("translate", __name__)

def calculate_file_hash(file):
    sha256 = hashlib.sha256()
    for chunk in iter(lambda: file.read(4096), b""):
        sha256.update(chunk)
    file.seek(0)
    return sha256.hexdigest()

def sanitize_filename(filename):
    # Keep only safe chars for storage 
    return re.sub(r'[^a-zA-Z0-9_\-\.]', '_', filename)

def is_pdf_file(file):
    """Check if the file is already a PDF"""
    import mimetypes
    mime_type, _ = mimetypes.guess_type(file.filename)
    return mime_type == 'application/pdf'

@translate_bp.route("/translate-document", methods=["POST"])
def translate_document():
    """Translate a PDF document using PDFTranslator"""
    try:
        # Check if file is provided
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files["file"]
        direction = request.form.get("direction", "en2ml")  # Default to en2ml if not provided
        uploaded_by = request.form.get("uploaded_by")
        title = request.form.get("title", "Translated Document")
        
        if direction not in ["ml2en", "en2ml"]:
            return jsonify({"error": "Invalid direction. Use 'ml2en' or 'en2ml'"}), 400
            
        if not uploaded_by:
            return jsonify({"error": "uploaded_by is required"}), 400
        
        # Check if file is a PDF
        if not is_pdf_file(file):
            return jsonify({"error": "Only PDF files are supported for translation"}), 400
        
        # Create temporary files
        temp_input = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        
        # Save uploaded file to temp location
        file.save(temp_input.name)
        file.seek(0)  # Reset file pointer
        
        # Translate the document
        translator = PDFTranslator()
        translated_text = translator.translate_pdf(temp_input.name, temp_output.name, direction)
        
        # Generate new filename and upload to storage
        direction_suffix = "en" if direction == "ml2en" else "ml"
        translated_title = f"{title}_translated_{direction_suffix}"
        doc_uuid = str(uuid.uuid4())
        safe_title = sanitize_filename(translated_title)[:50]
        storage_name = f"{doc_uuid}_{safe_title}.pdf"
        
        # Upload translated PDF to storage
        with open(temp_output.name, 'rb') as f:
            supabase.storage.from_("documents_bucket").upload(
                storage_name, f.read(),
                {"content-type": "application/pdf"}
            )
        
        translated_file_url = supabase.storage.from_("documents_bucket").get_public_url(storage_name)
        
        # Calculate content hash
        with open(temp_output.name, 'rb') as f:
            content_hash = calculate_file_hash(f)
        
        # Insert translated document into database
        res = supabase.table("documents").insert({
            "title": translated_title,
            "file_url": translated_file_url,
            "language": "english" if direction == "ml2en" else "malayalam",
            "type": "translated",
            "source": "translation",
            "uploaded_by": uploaded_by,
            "content_hash": content_hash
        }).execute()
        
        if not res.data:
            return jsonify({"error": "Failed to save translated document to database"}), 500
        
        translated_doc_id = res.data[0]["id"]
        
        # Clean up temporary files
        os.unlink(temp_input.name)
        os.unlink(temp_output.name)
        
        return jsonify({
            "message": "Document translated successfully",
            "translated_document_id": translated_doc_id,
            "translated_file_url": translated_file_url,
            "direction": direction,
            "translated_text_preview": translated_text[:500] + "..." if len(translated_text) > 500 else translated_text
        }), 200
        
    except Exception as e:
        # Clean up temporary files in case of error
        try:
            if 'temp_input' in locals() and os.path.exists(temp_input.name):
                os.unlink(temp_input.name)
            if 'temp_output' in locals() and os.path.exists(temp_output.name):
                os.unlink(temp_output.name)
        except:
            pass
        
        return jsonify({"error": f"Translation failed: {str(e)}"}), 500

@translate_bp.route("/translate-summary", methods=["POST"])
def translate_summary():
    """Translate English text to Malayalam using Google Translate with chunking support"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "Request body is required"}), 400

        text = data.get("text")
        if not text or not text.strip():
            return jsonify({"error": "Text is required and cannot be empty"}), 400

        text = text.strip()
        if len(text) < 1:
            return jsonify({"error": "Text must be at least 1 character long"}), 400

        try:
            translator = GoogleTranslator(source="en", target="ml")

            if len(text) > 5000:
                chunks = [text[i:i+4500] for i in range(0, len(text), 4500)]
                translated_chunks = []
                for chunk in chunks:
                    translated_chunk = translator.translate(chunk)
                    if not translated_chunk:
                        return jsonify({"error": "Translation failed for one of the chunks"}), 500
                    translated_chunks.append(translated_chunk)
                translated_text = " ".join(translated_chunks)
            else:
                translated_text = translator.translate(text)

            if not translated_text:
                return jsonify({"error": "Translation failed - no result returned"}), 500

            return jsonify({
                "message": "Text translated successfully",
                "original_text": text,
                "translated_text": translated_text,
                "source_language": "en",
                "target_language": "ml"
            }), 200

        except Exception as translate_error:
            print(f"Translation error: {str(translate_error)}")
            return jsonify({"error": f"Translation failed: {str(translate_error)}"}), 500

    except Exception as e:
        print(f"Error in translate_summary: {str(e)}")
        return jsonify({"error": f"Failed to process translation request: {str(e)}"}), 500
