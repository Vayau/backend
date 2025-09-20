from flask import Blueprint, request, jsonify
from utils.auth_middleware import jwt_optional
from Model_rag.query import ask_question, summarizer
from Model_rag.index import index_document
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

@rag_bp.route("/index", methods=["POST"])
@jwt_optional
def index_document_for_rag():
    """
    Index a document for RAG retrieval.
    Authentication is optional.
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        document_content = data.get("content")
        document_id = data.get("document_id")
        title = data.get("title", "Untitled Document")
        
        if not document_content or not document_content.strip():
            return jsonify({"error": "Document content is required and cannot be empty"}), 400
        
        # Generate document ID if not provided
        if not document_id:
            document_id = str(uuid.uuid4())
        
        # Clean and validate the content
        document_content = document_content.strip()
        if len(document_content) < 10:
            return jsonify({"error": "Document content must be at least 10 characters long"}), 400
        
        # Index the document
        index_document(document_id, document_content)
        
        response_data = {
            "message": "Document indexed successfully",
            "document_id": document_id,
            "title": title,
            "content_length": len(document_content)
        }
        
        # Add user_id if authenticated
        if hasattr(request, 'current_user') and request.current_user:
            response_data["user_id"] = request.current_user['user_id']
        
        return jsonify(response_data), 200
        
    except Exception as e:
        print(f"Error in index_document_for_rag: {str(e)}")
        return jsonify({"error": f"Failed to index document: {str(e)}"}), 500

@rag_bp.route("/summarize", methods=["POST"])
@jwt_optional
def summarize_document():
    """
    Generate a summary of document content.
    Authentication is optional.
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        content = data.get("content")
        title = data.get("title", "Untitled Document")
        
        if not content or not content.strip():
            return jsonify({"error": "Document content is required and cannot be empty"}), 400
        
        # Clean and validate the content
        content = content.strip()
        if len(content) < 10:
            return jsonify({"error": "Document content must be at least 10 characters long"}), 400
        
        if len(content) > 50000:
            return jsonify({"error": "Document content must be less than 50,000 characters"}), 400
        
        # Generate summary
        summary = summarizer(content)
        
        if not summary:
            return jsonify({"error": "Failed to generate summary"}), 500
        
        response_data = {
            "message": "Document summarized successfully",
            "title": title,
            "original_length": len(content),
            "summary": summary,
            "summary_length": len(summary)
        }
        
        # Add user_id if authenticated
        if hasattr(request, 'current_user') and request.current_user:
            response_data["user_id"] = request.current_user['user_id']
        
        return jsonify(response_data), 200
        
    except Exception as e:
        print(f"Error in summarize_document: {str(e)}")
        return jsonify({"error": f"Failed to summarize document: {str(e)}"}), 500

@rag_bp.route("/health", methods=["GET"])
def rag_health_check():
    """
    Health check endpoint for RAG system.
    No authentication required.
    """
    try:
        # Test if the RAG system is working by asking a simple question
        test_question = "What is the system status?"
        answer = ask_question(test_question)
        
        return jsonify({
            "status": "healthy",
            "message": "RAG system is operational",
            "test_question": test_question,
            "test_answer": answer[:100] + "..." if len(answer) > 100 else answer
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "message": "RAG system is not operational",
            "error": str(e)
        }), 500

@rag_bp.route("/batch-index", methods=["POST"])
@jwt_optional
def batch_index_documents():
    """
    Index multiple documents at once for RAG retrieval.
    Authentication is optional.
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        documents = data.get("documents", [])
        
        if not documents or not isinstance(documents, list):
            return jsonify({"error": "Documents array is required"}), 400
        
        if len(documents) == 0:
            return jsonify({"error": "At least one document is required"}), 400
        
        if len(documents) > 10:
            return jsonify({"error": "Maximum 10 documents can be indexed at once"}), 400
        
        results = []
        errors = []
        
        for i, doc in enumerate(documents):
            try:
                document_content = doc.get("content")
                document_id = doc.get("document_id")
                title = doc.get("title", f"Document {i+1}")
                
                if not document_content or not document_content.strip():
                    errors.append(f"Document {i+1}: Content is required and cannot be empty")
                    continue
                
                # Generate document ID if not provided
                if not document_id:
                    document_id = str(uuid.uuid4())
                
                # Clean and validate the content
                document_content = document_content.strip()
                if len(document_content) < 10:
                    errors.append(f"Document {i+1}: Content must be at least 10 characters long")
                    continue
                
                # Index the document
                index_document(document_id, document_content)
                
                results.append({
                    "document_id": document_id,
                    "title": title,
                    "content_length": len(document_content),
                    "status": "success"
                })
                
            except Exception as doc_error:
                errors.append(f"Document {i+1}: {str(doc_error)}")
                results.append({
                    "document_id": doc.get("document_id", f"doc_{i+1}"),
                    "title": doc.get("title", f"Document {i+1}"),
                    "status": "error",
                    "error": str(doc_error)
                })
        
        response_data = {
            "message": f"Batch indexing completed. {len(results)} documents processed.",
            "successful": len([r for r in results if r["status"] == "success"]),
            "failed": len([r for r in results if r["status"] == "error"]),
            "results": results,
            "errors": errors
        }
        
        # Add user_id if authenticated
        if hasattr(request, 'current_user') and request.current_user:
            response_data["user_id"] = request.current_user['user_id']
        
        return jsonify(response_data), 200
        
    except Exception as e:
        print(f"Error in batch_index_documents: {str(e)}")
        return jsonify({"error": f"Failed to batch index documents: {str(e)}"}), 500
