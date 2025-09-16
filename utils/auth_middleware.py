from functools import wraps
from flask import request, jsonify
from utils.jwt_utils import verify_jwt_token

def jwt_required(f):
    """
    Decorator that requires JWT authentication for a route.
    
    Validates JWT token from Authorization header. Returns 401 if token is missing,
    invalid, or expired. User info is available in request.current_user.
    
    Example:
        @jwt_required
        def protected_route():
            return {"user": request.current_user['name']}
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({"error": "Authorization header is missing"}), 401
        
        if not auth_header.startswith('Bearer '):
            return jsonify({"error": "Invalid authorization header format. Expected 'Bearer <token>'"}), 401
        
        token = auth_header.split(' ')[1]
        
        payload = verify_jwt_token(token)
        
        if payload is None:
            return jsonify({"error": "Invalid or expired token"}), 401
        
        request.current_user = payload
        
        return f(*args, **kwargs)
    
    return decorated_function

def jwt_optional(f):
    """
    Decorator that provides optional JWT authentication for a route.
    
    Validates JWT token if present, but doesn't block request if missing/invalid.
    User info available in request.current_user when authenticated.
    
    Example:
        @jwt_optional
        def optional_route():
            if hasattr(request, 'current_user'):
                return {"user": request.current_user['name']}
            return {"user": "anonymous"}
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            payload = verify_jwt_token(token)
            
            if payload is not None:
                request.current_user = payload
        
        return f(*args, **kwargs)
    
    return decorated_function
