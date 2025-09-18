from flask import Flask, request
from flask_cors import CORS
from routes.auth_routes import auth_bp
from utils.auth_middleware import jwt_required, jwt_optional
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'secret-key')

CORS(app, supports_credentials=True)


app.register_blueprint(auth_bp, url_prefix="/auth")

@app.route("/test")
@jwt_optional
def test():
    """Public test route with optional authentication"""
    if hasattr(request, 'current_user'):
        return {
            "message": "Backend is up and running!",
            "user": {
                "id": request.current_user['user_id'],
                "email": request.current_user['email'],
                "name": request.current_user['name'],
                "role": request.current_user['role']
            },
            "authenticated": True
        }, 200
    return {
        "message": "Backend is up and running!",
        "authenticated": False
    }, 200

@app.route("/protected")
@jwt_required
def protected():
    """Protected test route that requires authentication"""
    return {
        "message": "Access granted! This is a protected route.",
        "user": {
            "id": request.current_user['user_id'],
            "email": request.current_user['email'],
            "name": request.current_user['name'],
            "role": request.current_user['role']
        },
        "timestamp": request.current_user.get('iat'),
        "authenticated": True
    }, 200


if __name__ == "__main__":
    app.run(debug=True, port=5001)