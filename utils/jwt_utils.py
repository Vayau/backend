import jwt
from datetime import datetime, timedelta
from flask import current_app

def generate_jwt_token(user_data):
    """
    Generate a JWT token with user data as payload
    
    Args:
        user_data (dict): Dictionary containing user information
        
    Returns:
        str: Encoded JWT token
    """
    expiration_time = datetime.utcnow() + timedelta(hours=24)
    
    payload = {
        'user_id': user_data['id'],
        'email': user_data['email'],
        'name': user_data['name'],
        'role': user_data['role'],
        'exp': expiration_time,
        'iat': datetime.utcnow() 
    }
    
    token = jwt.encode(
        payload, 
        current_app.config['JWT_SECRET_KEY'], 
        algorithm='HS256'
    )
    
    return token

def verify_jwt_token(token):
    """
    Verify and decode a JWT token
    
    Args:
        token (str): JWT token to verify
        
    Returns:
        dict: Decoded payload if valid, None if invalid
    """
    try:
        payload = jwt.decode(
            token, 
            current_app.config['JWT_SECRET_KEY'], 
            algorithms=['HS256']
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
