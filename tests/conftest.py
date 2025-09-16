"""
Pytest configuration and fixtures for testing.
"""
import pytest
import os
import sys
from unittest.mock import patch, MagicMock
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load test environment variables
load_dotenv('.env.test')

from app import app
from utils.jwt_utils import generate_jwt_token

@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    # Set a test-specific JWT secret for testing
    original_secret = app.config.get('JWT_SECRET_KEY')
    test_secret = os.getenv('JWT_SECRET_KEY', 'test-secret-key-for-testing-only')
    app.config['JWT_SECRET_KEY'] = test_secret
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        yield client
    
    # Restore original secret after test
    app.config['JWT_SECRET_KEY'] = original_secret

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
    
    # Use test secret key from environment
    test_secret_key = os.getenv('JWT_SECRET_KEY', 'test-secret-key-for-testing-only')
    
    payload = {
        'user_id': sample_user['id'],
        'email': sample_user['email'],
        'name': sample_user['name'],
        'role': sample_user['role'],
        'exp': datetime.utcnow() + timedelta(hours=24),
        'iat': datetime.utcnow()
    }
    
    return jwt.encode(payload, test_secret_key, algorithm='HS256')

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
