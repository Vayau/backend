import os
import hashlib
import uuid
import re
import tempfile
import mimetypes
import requests
import shutil
from flask import Blueprint, request, jsonify
from utils.supabase import supabase
from functions import convert_to_pdf, HandwrittenOCR, PDFTranslator

docs_bp = Blueprint("documents", __name__)

def calculate_file_hash(file):
    sha256 = hashlib.sha256()
    for chunk in iter(lambda: file.read(4096), b""):
        sha256.update(chunk)
    file.seek(0)
    return sha256.hexdigest()

def sanitize_filename(filename):
    # Keep only safe chars for storage 
    return re.sub(r'[^a-zA-Z0-9_\-\.]', '_', filename)

def is_handwritten_file(file):
    """Check if the uploaded file is a handwritten document based on file type and user input"""
    # Check if user explicitly marked it as handwritten
    is_handwritten = request.form.get("is_handwritten", "false").lower() == "true"
    
    if is_handwritten:
        # Verify it's an image file
        mime_type, _ = mimetypes.guess_type(file.filename)
        return mime_type and mime_type.startswith('image/')
    
    return False

def is_pdf_file(file):
    """Check if the file is already a PDF"""
    mime_type, _ = mimetypes.guess_type(file.filename)
    return mime_type == 'application/pdf'

def process_uploaded_file(file, is_handwritten=False):
    """Process the uploaded file based on its type"""
    try:
        # Create temporary files
        temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1])
        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        
        # Save uploaded file to temp location
        file.save(temp_input.name)
        file.seek(0)  # Reset file pointer
        
        if is_handwritten:
            ocr = HandwrittenOCR()
            text = ocr.process_image(temp_input.name)
            ocr.save_to_pdf(text, temp_output.name)
            return temp_output.name, "handwritten_ocr"
        else:
            if not is_pdf_file(file):
                convert_to_pdf(temp_input.name, temp_output.name)
                return temp_output.name, "converted_to_pdf"
            else:
                import shutil
                shutil.copy2(temp_input.name, temp_output.name)
                return temp_output.name, "pdf_original"
                
    except Exception as e:
        try:
            os.unlink(temp_input.name)
            os.unlink(temp_output.name)
        except:
            pass
        raise e

def link_document_to_departments(document_id, user_id):
    try:
        # find departments for this user
        user_depts = supabase.table("user_departments") \
            .select("department_id") \
            .eq("user_id", user_id) \
            .execute()

        if not user_depts.data:
            return {"warning": "User not mapped to any department"}, 200

        # create mappings in document_departments
        dept_links = [
            {"document_id": document_id, "department_id": d["department_id"]}
            for d in user_depts.data
        ]

        supabase.table("document_departments").insert(dept_links).execute()
        return None
    except Exception as e:
        return {"error": f"Failed linking document to departments: {str(e)}"}, 500


@docs_bp.route("/upload", methods=["POST"])
def upload_document():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    title = request.form.get("title")
    language = request.form.get("language", "english")
    doc_type = request.form.get("type")
    uploaded_by = request.form.get("uploaded_by")
    source = request.form.get("source")

    if not uploaded_by or not title:
        return jsonify({"error": "uploaded_by and title are required"}), 400

    is_handwritten = is_handwritten_file(file)
    
    try:
        processed_file_path, processing_type = process_uploaded_file(file, is_handwritten)
    except Exception as e:
        return jsonify({"error": f"File processing failed: {str(e)}"}), 500

    with open(processed_file_path, 'rb') as f:
        content_hash = calculate_file_hash(f)

    existing = supabase.table("documents") \
        .select("id, file_url") \
        .eq("content_hash", content_hash) \
        .execute()

    if existing.data:
        # Clean up temp file
        os.unlink(processed_file_path)
        
        doc_id = existing.data[0]["id"]
        # just link to departments
        link_err = link_document_to_departments(doc_id, uploaded_by)
        if link_err:
            return jsonify(link_err[0]), link_err[1]

        return jsonify({
            "message": "Document already exists, linked to department(s)",
            "document_id": doc_id,
            "file_url": existing.data[0]["file_url"],
            "processing_type": processing_type
        }), 200

    doc_uuid = str(uuid.uuid4())
    safe_title = sanitize_filename(title)[:50]  
    storage_name = f"{doc_uuid}_{safe_title}.pdf"

    try:
        with open(processed_file_path, 'rb') as f:
            supabase.storage.from_("documents_bucket").upload(
                storage_name, f.read(),
                {"content-type": "application/pdf"}
            )
    except Exception as e:
        os.unlink(processed_file_path)
        return jsonify({"error": f"Storage upload failed: {str(e)}"}), 500

    os.unlink(processed_file_path)
    # get public url
    file_url = supabase.storage.from_("documents_bucket").get_public_url(storage_name)

    # insert into DB
    try:
        res = supabase.table("documents").insert({
            "title": title,
            "file_url": file_url,
            "language": language,
            "type": doc_type,
            "source": source,
            "uploaded_by": uploaded_by,
            "content_hash": content_hash
        }).execute()

        doc_id = res.data[0]["id"]

        link_err = link_document_to_departments(doc_id, uploaded_by)
        if link_err:
            return jsonify(link_err[0]), link_err[1]

        return jsonify({
            "message": "Document uploaded and processed successfully",
            "document_id": doc_id,
            "file_url": file_url,
            "processing_type": processing_type
        }), 201

    except Exception as e:
        return jsonify({"error": f"DB insert failed: {str(e)}"}), 500


@docs_bp.route("/translate", methods=["POST"])
def translate_document():
    """Translate a PDF document using PDFTranslator"""
    try:
        data = request.get_json()
        
        required_fields = ["document_id", "direction"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        document_id = data["document_id"]
        direction = data["direction"]  
        
        if direction not in ["ml2en", "en2ml"]:
            return jsonify({"error": "Invalid direction. Use 'ml2en' or 'en2ml'"}), 400
        
        doc_result = supabase.table("documents").select("file_url, title").eq("id", document_id).execute()
        
        if not doc_result.data:
            return jsonify({"error": "Document not found"}), 404
        
        document = doc_result.data[0]
        file_url = document["file_url"]
        title = document["title"]
        
        import requests
        response = requests.get(file_url)
        if response.status_code != 200:
            return jsonify({"error": "Failed to download document"}), 500
        
        temp_input = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        
        temp_input.write(response.content)
        temp_input.close()
        
        translator = PDFTranslator()
        translated_text = translator.translate_pdf(temp_input.name, temp_output.name, direction)
        
        direction_suffix = "en" if direction == "ml2en" else "ml"
        translated_title = f"{title}_translated_{direction_suffix}"
        doc_uuid = str(uuid.uuid4())
        safe_title = sanitize_filename(translated_title)[:50]
        storage_name = f"{doc_uuid}_{safe_title}.pdf"
        
        with open(temp_output.name, 'rb') as f:
            supabase.storage.from_("documents_bucket").upload(
                storage_name, f.read(),
                {"content-type": "application/pdf"}
            )
        
        translated_file_url = supabase.storage.from_("documents_bucket").get_public_url(storage_name)
        
        with open(temp_output.name, 'rb') as f:
            content_hash = calculate_file_hash(f)
        
        res = supabase.table("documents").insert({
            "title": translated_title,
            "file_url": translated_file_url,
            "language": "english" if direction == "ml2en" else "malayalam",
            "type": "translated",
            "source": "translation",
            "uploaded_by": data.get("uploaded_by", "system"),
            "content_hash": content_hash
        }).execute()
        
        translated_doc_id = res.data[0]["id"]
        
        os.unlink(temp_input.name)
        os.unlink(temp_output.name)
        
        return jsonify({
            "message": "Document translated successfully",
            "original_document_id": document_id,
            "translated_document_id": translated_doc_id,
            "translated_file_url": translated_file_url,
            "direction": direction,
            "translated_text_preview": translated_text[:500] + "..." if len(translated_text) > 500 else translated_text
        }), 200
        
    except Exception as e:
        try:
            if 'temp_input' in locals():
                os.unlink(temp_input.name)
            if 'temp_output' in locals():
                os.unlink(temp_output.name)
        except:
            pass
        
        return jsonify({"error": f"Translation failed: {str(e)}"}), 500
