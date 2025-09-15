import bcrypt
from flask import Blueprint, request, jsonify
from utils.supabase import supabase  # this is supabase object defined in /utils directory

auth_bp = Blueprint("auth", __name__)

# signup route
@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = request.json
    email = data.get("email")
    name = data.get("name")
    password = data.get("password")
    role = data.get("role", "staff")  # default role if not provided

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



# login route hai
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
    stored_hash = user["password"].encode("utf-8")

    if bcrypt.checkpw(password.encode("utf-8"), stored_hash):
        return jsonify({"message": "Login successful", "user_id": user["id"]}), 200
    else:
        return jsonify({"error": "Invalid email or password"}), 401
