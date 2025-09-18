import bcrypt
from flask import Blueprint, request, jsonify, current_app, make_response
from utils.supabase import supabase
from utils.jwt_utils import generate_jwt_token, verify_jwt_token

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = request.json
    email = data.get("email")
    name = data.get("name")
    password = data.get("password")
    role = data.get("role", "staff")

    if not email or not password or not name:
        return jsonify({"error": "Email, name, and password are required"}), 400

    hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    try:
        res = supabase.table("users").insert({
            "name": name,
            "email": email,
            "password": hashed_pw,
            "role": role
        }).execute()

        if res.data:
            return jsonify({"message": "User created", "user_id": res.data[0]["id"]}), 201
        else:
            return jsonify({"error": "Failed to insert user"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    res = supabase.table("users").select("*").eq("email", email).execute()

    if not res.data:
        return jsonify({"error": "Invalid email or password"}), 401

    user = res.data[0]
    stored_password = user["password"]

    if stored_password.startswith("$2b$"):
        if bcrypt.checkpw(password.encode("utf-8"), stored_password.encode("utf-8")):
            password_valid = True
        else:
            password_valid = False
    else:
        password_valid = (password == stored_password)

    if password_valid:
        token = generate_jwt_token(user)
        
        response_data = {
            "message": "Login successful",
            "user": {
                "id": user["id"],
                "email": user["email"],
                "name": user["name"],
                "role": user["role"]
            }
        }
        
        response = make_response(jsonify(response_data), 200)
        
        response.set_cookie(
            'auth_token',
            token,
            max_age=86400,
            httponly=True,
            secure=True,
            samesite='Lax'
        )
        
        return response
    else:
        return jsonify({"error": "Invalid email or password"}), 401

@auth_bp.route("/logout", methods=["POST"])
def logout():
    response = make_response(jsonify({"message": "Logout successful"}), 200)
    
    response.set_cookie(
        'auth_token',
        '',
        max_age=0,
        httponly=True,
        secure=True,
        samesite='Lax'
    )
    
    return response



