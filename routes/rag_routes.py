from flask import Blueprint, request, jsonify
from utils.auth_middleware import jwt_optional
from Model_rag.query import ask_question, summarizer
import uuid

rag_bp = Blueprint("rag", __name__)

@rag_bp.route("/ask", methods=["POST"])
@jwt_optional
def ask_rag_question():
    """
    Ask a question using the RAG system.
    Authentication is optional.
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        question = data.get("question")
        if not question or not question.strip():
            return jsonify({"error": "Question is required and cannot be empty"}), 400
        
        # Clean and validate the question
        question = question.strip()
        if len(question) < 3:
            return jsonify({"error": "Question must be at least 3 characters long"}), 400
        
        if len(question) > 1000:
            return jsonify({"error": "Question must be less than 1000 characters"}), 400
        
        # Get the answer from RAG system
        answer = ask_question(question)
        
        if not answer:
            return jsonify({"error": "Failed to generate answer"}), 500
        
        response_data = {
            "message": "Question answered successfully",
            "question": question,
            "answer": answer
        }
        
        # Add user_id if authenticated
        if hasattr(request, 'current_user') and request.current_user:
            response_data["user_id"] = request.current_user['user_id']
        
        return jsonify(response_data), 200
        
    except Exception as e:
        print(f"Error in ask_rag_question: {str(e)}")
        return jsonify({"error": f"Failed to process question: {str(e)}"}), 500


