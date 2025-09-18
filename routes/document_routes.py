import os
import hashlib
import uuid
import re
from flask import Blueprint, request, jsonify
from utils.supabase import supabase

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

    # hash for deduplication file
    content_hash = calculate_file_hash(file)

    # check duplicate in the documents table
    existing = supabase.table("documents") \
        .select("id, file_url") \
        .eq("content_hash", content_hash) \
        .execute()

    if existing.data:
        doc_id = existing.data[0]["id"]
        # just link to departments
        link_err = link_document_to_departments(doc_id, uploaded_by)
        if link_err:
            return jsonify(link_err[0]), link_err[1]

        return jsonify({
            "message": "Document already exists, linked to department(s)",
            "document_id": doc_id,
            "file_url": existing.data[0]["file_url"]
        }), 200

    # generate storage file name
    file_ext = os.path.splitext(file.filename)[1]
    doc_uuid = str(uuid.uuid4())
    safe_title = sanitize_filename(title)[:50]  # prevent overly long names
    storage_name = f"{doc_uuid}_{safe_title}{file_ext}"

    try:
        supabase.storage.from_("documents_bucket").upload(
            storage_name, file.read(),
            {"content-type": "application/pdf"}
        )
        file.seek(0)
    except Exception as e:
        return jsonify({"error": f"Storage upload failed: {str(e)}"}), 500

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

        # link to departments
        link_err = link_document_to_departments(doc_id, uploaded_by)
        if link_err:
            return jsonify(link_err[0]), link_err[1]

        return jsonify({
            "message": "Document uploaded successfully",
            "document_id": doc_id,
            "file_url": file_url
        }), 201

    except Exception as e:
        return jsonify({"error": f"DB insert failed: {str(e)}"}), 500
