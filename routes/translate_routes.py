import os
import tempfile
import uuid
import hashlib
import re
from flask import Blueprint, request, jsonify
from utils.supabase import supabase
from functions import PDFTranslator

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
        direction = request.form.get("direction")
        uploaded_by = request.form.get("uploaded_by")
        title = request.form.get("title", "Translated Document")
        
        if not direction:
            return jsonify({"error": "Direction is required (ml2en or en2ml)"}), 400
        
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
        
        # Save translated text to a text file for easy checking
        text_filename = f"{doc_uuid}_{safe_title}.txt"
        with open(text_filename, 'w', encoding='utf-8') as text_file:
            text_file.write(translated_text)
        
        # Upload the text file to storage as well
        with open(text_filename, 'rb') as f:
            supabase.storage.from_("documents_bucket").upload(
                text_filename, f.read(),
                {"content-type": "text/plain; charset=utf-8"}
            )
        
        text_file_url = supabase.storage.from_("documents_bucket").get_public_url(text_filename)
        
        # Clean up temporary files
        os.unlink(temp_input.name)
        os.unlink(temp_output.name)
        os.unlink(text_filename)  # Clean up local text file
        
        return jsonify({
            "message": "Document translated successfully",
            "translated_document_id": translated_doc_id,
            "translated_file_url": translated_file_url,
            "translated_text_url": text_file_url,
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
            if 'text_filename' in locals() and os.path.exists(text_filename):
                os.unlink(text_filename)
        except:
            pass
        
        return jsonify({"error": f"Translation failed: {str(e)}"}), 500
