"""
Simplified tests for JWT middleware functionality focusing on cookie-based authentication.
"""
import pytest
import json
import os
from unittest.mock import patch, MagicMock
from utils.auth_middleware import jwt_required, jwt_optional
from utils.jwt_utils import verify_jwt_token


class TestBackwardCompatibility:
    """Test cases for backward compatibility with Authorization headers."""
    
    def test_jwt_required_with_valid_header(self, sample_user, valid_token):
        """Test @jwt_required with valid Authorization header (backward compatibility)."""
        from flask import Flask, request
        
        app = Flask(__name__)
        app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'test-secret-key-for-testing-only')
        
        @app.route('/protected')
        @jwt_required
        def protected_route():
            return {
                "message": "Access granted",
                "user": request.current_user
            }
        
        with app.test_client() as client:
            response = client.get('/protected', headers={
                'Authorization': f'Bearer {valid_token}'
            })
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['message'] == 'Access granted'
            assert 'user' in data
            assert data['user']['user_id'] == sample_user['id']
    
    def test_jwt_required_without_token(self):
        """Test @jwt_required without any authentication."""
        from flask import Flask
        
        app = Flask(__name__)
        app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'test-secret-key-for-testing-only')
        
        @app.route('/protected')
        @jwt_required
        def protected_route():
            return {"message": "Access granted"}
        
        with app.test_client() as client:
            response = client.get('/protected')
            
            assert response.status_code == 401
            data = json.loads(response.data)
            assert data['error'] == 'Authentication token is missing'


class TestMiddlewareIntegration:
    """Test middleware integration with the actual Flask app."""
    
    def test_middleware_with_flask_app(self, client, valid_token, invalid_token):
        """Test middleware integration with the actual Flask app."""
        response = client.get('/test')
        assert response.status_code == 200
        data = response.get_json()
        assert data['authenticated'] == False
        
        response = client.get('/test', headers={
            'Authorization': f'Bearer {valid_token}'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['authenticated'] == True
        
        response = client.get('/test', headers={
            'Authorization': f'Bearer {invalid_token}'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['authenticated'] == False

    def test_middleware_error_handling(self, client):
        """Test middleware error handling with various edge cases."""
        response = client.get('/test', headers={'Authorization': 'Bearer'})
        assert response.status_code == 200
        
        response = client.get('/test', headers={'Authorization': 'InvalidFormat'})
        assert response.status_code == 200


class TestCookieAuthenticationIntegration:
    """Test cookie-based authentication with actual Flask app."""
    
    def test_login_sets_cookie(self, client):
        """Test that login endpoint sets auth_token cookie"""
        user_data = {
            "email": "test@example.com",
            "name": "Test User",
            "password": "testpassword123",
            "role": "staff"
        }
        
        client.post('/auth/signup', json=user_data)
        
        login_data = {
            "email": "test@example.com",
            "password": "testpassword123"
        }
        
        response = client.post('/auth/login', json=login_data)
        
        assert response.status_code == 200
        assert 'auth_token' in response.headers.get('Set-Cookie', '')
        assert 'HttpOnly' in response.headers.get('Set-Cookie', '')

    def test_authentication_with_cookie(self, client):
        """Test that authentication works with cookie instead of header"""
        user_data = {
            "email": "cookietest@example.com",
            "name": "Cookie Test User",
            "password": "testpassword123",
            "role": "staff"
        }
        
        client.post('/auth/signup', json=user_data)
        
        login_data = {
            "email": "cookietest@example.com",
            "password": "testpassword123"
        }
        
        login_response = client.post('/auth/login', json=login_data)
        assert login_response.status_code == 200
        
        cookie_header = login_response.headers.get('Set-Cookie', '')
        auth_token = None
        for cookie in cookie_header.split(';'):
            if cookie.strip().startswith('auth_token='):
                auth_token = cookie.strip().split('=')[1]
                break
        
        assert auth_token is not None
        
        response = client.get('/test', headers={'Cookie': f'auth_token={auth_token}'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['authenticated'] == True
        assert data['user']['email'] == 'cookietest@example.com'

    def test_logout_clears_cookie(self, client):
        """Test that logout clears the auth_token cookie"""
        user_data = {
            "email": "logouttest@example.com",
            "name": "Logout Test User",
            "password": "testpassword123",
            "role": "staff"
        }
        
        client.post('/auth/signup', json=user_data)
        
        login_data = {
            "email": "logouttest@example.com",
            "password": "testpassword123"
        }
        
        login_response = client.post('/auth/login', json=login_data)
        assert login_response.status_code == 200
        
        logout_response = client.post('/auth/logout')
        assert logout_response.status_code == 200
        
        cookie_header = logout_response.headers.get('Set-Cookie', '')
        assert 'auth_token=;' in cookie_header or 'auth_token="";' in cookie_header
