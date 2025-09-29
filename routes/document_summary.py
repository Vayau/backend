from flask import Blueprint, request, jsonify, current_app
import io
from utils.supabase import supabase
from flask_mail import Message
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter

summary_bp = Blueprint("summary", __name__)

@summary_bp.route("/summaries", methods=["POST"])
def get_summaries():
    data = request.json
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    try:
        # Get user email
        user_res = supabase.table("users").select("email").eq("id", user_id).execute()
        if not user_res.data:
            return jsonify({"error": "User not found"}), 404
        recipient_email = user_res.data[0]["email"]

        # Get user departments
        dept_res = supabase.table("user_departments").select("department_id").eq("user_id", user_id).execute()
        if not dept_res.data:
            return jsonify({"summaries": []}), 200
        department_ids = [row["department_id"] for row in dept_res.data]

        summaries = []
        for dept_id in department_ids:
            
            sum_res = supabase.table("document_summaries") \
                .select("id, summary_text, document_id, documents(title, file_url)") \
                .eq("department_id", dept_id) \
                .execute()

            if sum_res.data:
                for row in sum_res.data:
                    doc_info = row.get("documents") or {}
                    summaries.append({
                        "document_id": row["document_id"],
                        "title": doc_info.get("title"),
                        "file_url": doc_info.get("file_url"),
                        "summary_text": row["summary_text"],
                        "department_id": dept_id
                    })

        # Remove duplicates keeping longest summary per document
        unique_summaries = {}
        for s in summaries:
            doc_id = s["document_id"]
            if doc_id not in unique_summaries or len(s["summary_text"]) > len(unique_summaries[doc_id]["summary_text"]):
                unique_summaries[doc_id] = s
        summaries = list(unique_summaries.values())

        # Generate PDF
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = [Paragraph("Document Summaries", styles['Title']), Spacer(1, 18)]
        for s in summaries:
            story.append(Paragraph(f"<b>Title:</b> {s['title']}", styles['Heading3']))
            story.append(Spacer(1, 8))
            story.append(Paragraph(s['summary_text'], styles['BodyText']))
            story.append(Spacer(1, 18))
        doc.build(story)
        pdf_buffer.seek(0)

        # Send email
        msg = Message(
            subject="Your Document Summaries",
            recipients=[recipient_email],
            body="Hello, please find attached your document summaries."
        )
        msg.attach("summaries.pdf", "application/pdf", pdf_buffer.read())
        current_app.extensions['mail'].send(msg)

        # Return summaries with file_url included
        return jsonify({
            "message": "Summaries fetched and emailed successfully",
            "summaries": summaries
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error fetching summaries: {e}")
        return jsonify({"error": str(e)}), 500
