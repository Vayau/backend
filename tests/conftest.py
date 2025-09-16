"""
Pytest configuration and fixtures for testing.
"""
import pytest
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from utils.jwt_utils import generate_jwt_token

@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

#define a sample user
@pytest.fixture
def sample_user():
    """Sample user data for testing."""
    return {
        'id': 'test-user-123',
        'email': 'test@example.com',
        'name': 'Test User',
        'role': 'staff'
    }
#define a valid token
@pytest.fixture
def valid_token(sample_user):
    """Generate a valid JWT token for testing."""
    import jwt
    from datetime import datetime, timedelta
    from app import app
    
    payload = {
        'user_id': sample_user['id'],
        'email': sample_user['email'],
        'name': sample_user['name'],
        'role': sample_user['role'],
        'exp': datetime.utcnow() + timedelta(hours=24),
        'iat': datetime.utcnow()
    }
    
    with app.app_context():
        return jwt.encode(payload, app.config['JWT_SECRET_KEY'], algorithm='HS256')

#define an invalid token
@pytest.fixture
def invalid_token():
    """Return an invalid JWT token for testing."""
    return "invalid.jwt.token"

#define an expired token
@pytest.fixture
def expired_token():
    """Return an expired JWT token for testing."""
    return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoidGVzdC11c2VyLTEyMyIsImVtYWlsIjoidGVzdEBleGFtGxlLmNvbSIsIm5hbWUiOiJUZXN0IFVzZXIiLCJyb2xlIjoic3RhZmYiLCJleHAiOjE2MDAwMDAwMDAsImlhdCI6MTYwMDAwMDAwMH0.invalid_signature"
