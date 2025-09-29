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
from functions import convert_to_pdf, HandwrittenOCR, PDFTranslator, DocumentClassifier

from Model_rag.query import summarizer

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

def classify_and_summarize_document(pdf_path_or_url, title, is_existing=False):
    """Helper function to classify a document, extract text, and generate summary"""
    classification_results = None
    extracted_text = None
    summary = None
    metadata = None
    predicted_departments = None
    temp_pdf_path = None
    
    try:
        # Handle both file paths and URLs
        if is_existing and pdf_path_or_url.startswith('http'):
            # Download existing document from URL
            response = requests.get(pdf_path_or_url)
            response.raise_for_status()
            
            # Save to a temporary file for processing
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(response.content)
                temp_pdf_path = tmp.name
            actual_pdf_path = temp_pdf_path
        else:
            # Use the provided file path directly
            actual_pdf_path = pdf_path_or_url
        
        # Initialize classifier and process
        classifier = DocumentClassifier()
        metadata, predicted_departments = classifier.process_pdf(actual_pdf_path)
        extracted_text = classifier.extract_text_from_pdf(actual_pdf_path)
        
        # Generate summary using the extracted text
        doc_type = "existing document" if is_existing else "document"
        if extracted_text and len(extracted_text.strip()) > 0:
            try:
                summary = summarizer(extracted_text)
                if summary and len(summary.strip()) > 0:
                    print(f"Summary generated for {doc_type} {title}")
                else:
                    summary = "Summary generation returned empty result"
                    print(f"Summary generation returned empty result for {doc_type} {title}")
            except Exception as summary_error:
                print(f"Summary generation failed for {doc_type} {title}: {str(summary_error)}")
                summary = f"Summary generation failed: {str(summary_error)}"
        else:
            summary = "No text content available for summarization"
            print(f"No text content available for summarization for {doc_type} {title}")
        
        # Log classification results
        doc_type = "existing document" if is_existing else "document"
        print(f"Document classification completed for {doc_type} {title}")
        print(f"Metadata: {metadata}")
        print(f"Predicted departments: {predicted_departments}")
        print(f"Extracted text length: {len(extracted_text) if extracted_text else 0} characters")
        print(f"Summary length: {len(summary) if summary else 0} characters")
        
        # Ensure summary is never None
        if summary is None:
            summary = "Summary generation failed - no summary available"
        
        classification_results = {
            "metadata": metadata,
            "predicted_departments": predicted_departments,
            "extracted_text_length": len(extracted_text) if extracted_text else 0,
            "summary": summary
        }
        
    except Exception as e:
        doc_type = "existing document" if is_existing else "document"
        print(f"Document processing failed for {doc_type} {title}: {str(e)}")
        # Continue even if processing fails
        # Ensure summary is never None even in error case
        error_summary = f"Processing failed: {str(e)}"
        if error_summary is None:
            error_summary = "Processing failed - no summary available"
            
        classification_results = {
            "error": f"Processing failed: {str(e)}",
            "metadata": None,
            "predicted_departments": None,
            "extracted_text_length": 0,
            "summary": error_summary
        }
    finally:
        # Clean up temporary file if we created one
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            os.unlink(temp_pdf_path)
    
    return classification_results, extracted_text, summary

def get_department_id_by_name(department_name):
    """Get department ID by department name with proper mapping"""
    try:
        # Map classifier department names to actual database department names
        department_mapping = {
            "Finance": "Finance",
            "Engineering": "Engineering", 
            "HR": "Human Resources",
            "Procurement": "Procurement",
            "Legal": "Legal",
            "Regulatory": "Regulatory",
            "Safety": "Safety",
            "Operations": "Operations"
        }
        
        # Get the actual department name from mapping
        actual_dept_name = department_mapping.get(department_name, department_name)
        
        result = supabase.table("departments") \
            .select("id, name") \
            .eq("name", actual_dept_name) \
            .execute()
        
        if result.data and len(result.data) > 0:
            dept_id = result.data[0]["id"]
            print(f"✓ Mapped '{department_name}' -> '{actual_dept_name}' -> {dept_id}")
            return dept_id
        else:
            print(f"⚠ Department '{department_name}' (mapped to '{actual_dept_name}') not found in database")
            return None
    except Exception as e:
        print(f"Error getting department ID for {department_name}: {str(e)}")
        return None

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

    # Calculate content hash for reference (but don't check for duplicates)
    with open(processed_file_path, 'rb') as f:
        content_hash = calculate_file_hash(f)
    
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
    
    # Process document with DocumentClassifier and generate summary using the already processed file
    classification_results, extracted_text, summary = classify_and_summarize_document(processed_file_path, title, is_existing=False)

    # Now clean up the temp file and get public URL
    os.unlink(processed_file_path)
    # get public url
    file_url = supabase.storage.from_("documents_bucket").get_public_url(storage_name)

    # insert into DB
    try:
        print(f"Inserting document into database: {title}")
        res = supabase.table("documents").insert({
            "title": title,
            "file_url": file_url,
            "language": language,
            "type": doc_type,
            "source": source,
            "uploaded_by": uploaded_by,
            "content_hash": content_hash
        }).execute()

        if not res.data:
            print(f"Database insert failed: {res}")
            return jsonify({"error": f"Database insert failed: {res}"}), 500

        doc_id = res.data[0]["id"]
        print(f"Document inserted with ID: {doc_id}")
        
    except Exception as db_insert_error:
        # Check if it's a duplicate content_hash error
        if "duplicate key value violates unique constraint" in str(db_insert_error) and "content_hash" in str(db_insert_error):
            print(f"Duplicate content detected, generating new content hash for duplicate upload")
            # Generate a new content hash with timestamp to make it unique
            import time
            unique_content_hash = f"{content_hash}_{int(time.time())}"
            
            try:
                res = supabase.table("documents").insert({
                    "title": title,
                    "file_url": file_url,
                    "language": language,
                    "type": doc_type,
                    "source": source,
                    "uploaded_by": uploaded_by,
                    "content_hash": unique_content_hash
                }).execute()

                if not res.data:
                    print(f"Retry database insert failed: {res}")
                    return jsonify({"error": f"Retry database insert failed: {res}"}), 500

                doc_id = res.data[0]["id"]
                print(f"Document inserted with unique hash ID: {doc_id}")
            except Exception as retry_error:
                print(f"Retry database insert failed: {str(retry_error)}")
                return jsonify({"error": f"Database insert failed after retry: {str(retry_error)}"}), 500
        else:
            print(f"Database insert failed: {str(db_insert_error)}")
            return jsonify({"error": f"Database insert failed: {str(db_insert_error)}"}), 500

    # Store summary in document_summaries table
    try:
        # Get the first predicted department as the primary department
        primary_department_id = None
        if classification_results.get("predicted_departments") and len(classification_results["predicted_departments"]) > 0:
            # Handle both tuple and string formats
            if isinstance(classification_results["predicted_departments"][0], tuple):
                primary_department_name = classification_results["predicted_departments"][0][0]  # Get department name from tuple
            else:
                primary_department_name = classification_results["predicted_departments"][0]  # Get department name directly
            primary_department_id = get_department_id_by_name(primary_department_name)
            
            if not primary_department_id:
                print(f"Department '{primary_department_name}' not found in database, saving without department_id")
        
        # Insert summary into document_summaries table
        summary_data = {
            "document_id": doc_id,
            "summary_text": summary,
            "department_id": primary_department_id
        }
        
        # Insert into database
        summary_result = supabase.table("document_summaries").insert(summary_data).execute()
        
        if summary_result.data:
            print(f"Summary saved to document_summaries table for document {doc_id}")
            print(f"  - Summary ID: {summary_result.data[0]['id']}")
            print(f"  - Department ID: {primary_department_id}")
            print(f"  - Summary length: {len(summary)} characters")
        else:
            print(f"⚠ Failed to save summary to database: {summary_result}")
        
    except Exception as db_error:
        print(f"Failed to save summary to database: {str(db_error)}")
        # Log the summary data for debugging
        print(f"Summary data that failed to save: {summary_data}")

    # Link document to departments
    try:
        print(f"Linking document {doc_id} to departments for user {uploaded_by}")
        link_err = link_document_to_departments(doc_id, uploaded_by)
        if link_err:
            print(f"⚠ Department linking failed: {link_err}")
            return jsonify(link_err[0]), link_err[1]
        print(f"Document linked to departments successfully")
    except Exception as link_error:
        print(f"Error linking document to departments: {str(link_error)}")
        # Continue even if linking fails

    try:
        # Ensure all response data is JSON serializable
        safe_classification_results = classification_results if classification_results else {}
        safe_extracted_text_preview = extracted_text[:500] if extracted_text else None
        safe_summary = summary if summary else "No summary available"
        
        response_data = {
            "message": "Document uploaded and processed successfully",
            "document_id": doc_id,
            "file_url": file_url,
             "processing_type": processing_type,
            "classification_results": safe_classification_results,
            "extracted_text_preview": safe_extracted_text_preview,
            "summary": safe_summary
        }
        print(f"Preparing response for document {doc_id}")
        print(f"  - Classification results type: {type(safe_classification_results)}")
        print(f"  - Summary length: {len(safe_summary)}")
        return jsonify(response_data), 201
    
    except Exception as response_error:
        print(f"Error preparing response: {str(response_error)}")
        return jsonify({"error": f"Response preparation failed: {str(response_error)}"}), 500
    

 