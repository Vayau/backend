from flask import Blueprint, request, jsonify
from utils.supabase import supabase

summary_bp = Blueprint("summary", __name__)

@summary_bp.route("/summaries", methods=["POST"])
def get_summaries():
    data = request.json
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    try:
        dept_res = supabase.table("user_departments").select("department_id").eq("user_id", user_id).execute()

        if not dept_res.data:
            return jsonify({"summaries": []}), 200

        department_ids = [row["department_id"] for row in dept_res.data]

        # We'll join documents + document_summaries to get title + summary_text
        summaries = []
        for dept_id in department_ids:
            sum_res = (
                supabase.table("document_summaries")
                .select("summary_text, document_id, documents(title)")
                .eq("department_id", dept_id)
                .execute()
            )

            if sum_res.data:
                for row in sum_res.data:
                    summaries.append({
                        "document_id": row["document_id"],
                        "title": row["documents"]["title"] if "documents" in row else None,
                        "summary_text": row["summary_text"],
                        "department_id": dept_id
                    })

        return jsonify({"summaries": summaries}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
