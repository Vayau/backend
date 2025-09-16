"""
Comprehensive tests for JWT middleware functionality.
"""
import pytest
import json
from unittest.mock import patch, MagicMock
from utils.auth_middleware import jwt_required, jwt_optional
from utils.jwt_utils import verify_jwt_token


class TestJWTRequiredMiddleware:
    """Test cases for @jwt_required decorator."""
    
    def test_jwt_required_with_valid_token(self, sample_user, valid_token):
        """Test @jwt_required with a valid JWT token."""
        from flask import Flask, request
        
        app = Flask(__name__)
        app.config['JWT_SECRET_KEY'] = 'f270e33cbbb66099ed613db6f96b9720e2494f3e82de7bda90ee9dc0308f227c'
        
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
        """Test @jwt_required without Authorization header."""
        from flask import Flask
        
        app = Flask(__name__)
        app.config['JWT_SECRET_KEY'] = 'f270e33cbbb66099ed613db6f96b9720e2494f3e82de7bda90ee9dc0308f227c'
        
        @app.route('/protected')
        @jwt_required
        def protected_route():
            return {"message": "Access granted"}
        
        with app.test_client() as client:
            response = client.get('/protected')
            
            assert response.status_code == 401
            data = json.loads(response.data)
            assert data['error'] == 'Authorization header is missing'
    
    def test_jwt_required_with_invalid_header_format(self):
        """Test @jwt_required with invalid Authorization header format."""
        from flask import Flask
        
        app = Flask(__name__)
        app.config['JWT_SECRET_KEY'] = 'f270e33cbbb66099ed613db6f96b9720e2494f3e82de7bda90ee9dc0308f227c'
        
        @app.route('/protected')
        @jwt_required
        def protected_route():
            return {"message": "Access granted"}
        
        with app.test_client() as client:
            response = client.get('/protected', headers={
                'Authorization': 'InvalidFormat token123'
            })
            
            assert response.status_code == 401
            data = json.loads(response.data)
            assert 'Invalid authorization header format' in data['error']
    
    def test_jwt_required_with_invalid_token(self, invalid_token):
        """Test @jwt_required with invalid JWT token."""
        from flask import Flask
        
        app = Flask(__name__)
        app.config['JWT_SECRET_KEY'] = 'f270e33cbbb66099ed613db6f96b9720e2494f3e82de7bda90ee9dc0308f227c'
        
        @app.route('/protected')
        @jwt_required
        def protected_route():
            return {"message": "Access granted"}
        
        with app.test_client() as client:
            response = client.get('/protected', headers={
                'Authorization': f'Bearer {invalid_token}'
            })
            
            assert response.status_code == 401
            data = json.loads(response.data)
            assert data['error'] == 'Invalid or expired token'
    
    def test_jwt_required_with_expired_token(self, expired_token):
        """Test @jwt_required with expired JWT token."""
        from flask import Flask
        
        app = Flask(__name__)
        app.config['JWT_SECRET_KEY'] = 'f270e33cbbb66099ed613db6f96b9720e2494f3e82de7bda90ee9dc0308f227c'
        
        @app.route('/protected')
        @jwt_required
        def protected_route():
            return {"message": "Access granted"}
        
        with app.test_client() as client:
            response = client.get('/protected', headers={
                'Authorization': f'Bearer {expired_token}'
            })
            
            assert response.status_code == 401
            data = json.loads(response.data)
            assert data['error'] == 'Invalid or expired token'
    
    def test_jwt_required_sets_current_user(self, sample_user, valid_token):
        """Test that @jwt_required sets request.current_user correctly."""
        from flask import Flask, request
        
        app = Flask(__name__)
        app.config['JWT_SECRET_KEY'] = 'f270e33cbbb66099ed613db6f96b9720e2494f3e82de7bda90ee9dc0308f227c'
        
        @app.route('/protected')
        @jwt_required
        def protected_route():
            return {
                "user_id": request.current_user['user_id'],
                "email": request.current_user['email'],
                "name": request.current_user['name'],
                "role": request.current_user['role']
            }
        
        with app.test_client() as client:
            response = client.get('/protected', headers={
                'Authorization': f'Bearer {valid_token}'
            })
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['user_id'] == sample_user['id']
            assert data['email'] == sample_user['email']
            assert data['name'] == sample_user['name']
            assert data['role'] == sample_user['role']


class TestJWTOptionalMiddleware:
    """Test cases for @jwt_optional decorator."""
    
    def test_jwt_optional_with_valid_token(self, sample_user, valid_token):
        """Test @jwt_optional with a valid JWT token."""
        from flask import Flask, request
        
        app = Flask(__name__)
        app.config['JWT_SECRET_KEY'] = 'f270e33cbbb66099ed613db6f96b9720e2494f3e82de7bda90ee9dc0308f227c'
        
        @app.route('/optional')
        @jwt_optional
        def optional_route():
            if hasattr(request, 'current_user'):
                return {
                    "message": f"Hello {request.current_user['name']}!",
                    "authenticated": True,
                    "user": request.current_user
                }
            return {"message": "Hello anonymous!", "authenticated": False}
        
        with app.test_client() as client:
            response = client.get('/optional', headers={
                'Authorization': f'Bearer {valid_token}'
            })
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['authenticated'] is True
            assert data['user']['user_id'] == sample_user['id']
    
    def test_jwt_optional_without_token(self):
        """Test @jwt_optional without Authorization header."""
        from flask import Flask, request
        
        app = Flask(__name__)
        app.config['JWT_SECRET_KEY'] = 'f270e33cbbb66099ed613db6f96b9720e2494f3e82de7bda90ee9dc0308f227c'
        
        @app.route('/optional')
        @jwt_optional
        def optional_route():
            if hasattr(request, 'current_user'):
                return {"message": "Authenticated", "authenticated": True}
            return {"message": "Anonymous", "authenticated": False}
        
        with app.test_client() as client:
            response = client.get('/optional')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['authenticated'] is False
            assert data['message'] == 'Anonymous'
    
    def test_jwt_optional_with_invalid_token(self, invalid_token):
        """Test @jwt_optional with invalid JWT token (should still work)."""
        from flask import Flask, request
        
        app = Flask(__name__)
        app.config['JWT_SECRET_KEY'] = 'f270e33cbbb66099ed613db6f96b9720e2494f3e82de7bda90ee9dc0308f227c'
        
        @app.route('/optional')
        @jwt_optional
        def optional_route():
            if hasattr(request, 'current_user'):
                return {"message": "Authenticated", "authenticated": True}
            return {"message": "Anonymous", "authenticated": False}
        
        with app.test_client() as client:
            response = client.get('/optional', headers={
                'Authorization': f'Bearer {invalid_token}'
            })
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['authenticated'] is False
            assert data['message'] == 'Anonymous'
    
    def test_jwt_optional_with_malformed_header(self):
        """Test @jwt_optional with malformed Authorization header (should still work)."""
        from flask import Flask, request
        
        app = Flask(__name__)
        app.config['JWT_SECRET_KEY'] = 'f270e33cbbb66099ed613db6f96b9720e2494f3e82de7bda90ee9dc0308f227c'
        
        @app.route('/optional')
        @jwt_optional
        def optional_route():
            if hasattr(request, 'current_user'):
                return {"message": "Authenticated", "authenticated": True}
            return {"message": "Anonymous", "authenticated": False}
        
        with app.test_client() as client:
            response = client.get('/optional', headers={
                'Authorization': 'InvalidFormat token123'
            })
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['authenticated'] is False
            assert data['message'] == 'Anonymous'
    
    def test_jwt_optional_sets_current_user_when_valid(self, sample_user, valid_token):
        """Test that @jwt_optional sets request.current_user when token is valid."""
        from flask import Flask, request
        
        app = Flask(__name__)
        app.config['JWT_SECRET_KEY'] = 'f270e33cbbb66099ed613db6f96b9720e2494f3e82de7bda90ee9dc0308f227c'
        
        @app.route('/optional')
        @jwt_optional
        def optional_route():
            if hasattr(request, 'current_user'):
                return {
                    "authenticated": True,
                    "user_id": request.current_user['user_id'],
                    "email": request.current_user['email']
                }
            return {"authenticated": False}
        
        with app.test_client() as client:
            response = client.get('/optional', headers={
                'Authorization': f'Bearer {valid_token}'
            })
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['authenticated'] is True
            assert data['user_id'] == sample_user['id']
            assert data['email'] == sample_user['email']


class TestMiddlewareIntegration:
    """Integration tests for middleware with Flask app."""
    
    def test_middleware_with_flask_app(self, client, valid_token, invalid_token):
        """Test middleware integration with the actual Flask app."""
        response = client.get('/test', headers={
            'Authorization': f'Bearer {valid_token}'
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['authenticated'] is True
        assert 'user' in data
        
        # Test /test route without token
        response = client.get('/test')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['authenticated'] is False
        
        # Test /test route with invalid token
        response = client.get('/test', headers={
            'Authorization': f'Bearer {invalid_token}'
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['authenticated'] is False
    
    def test_middleware_error_handling(self, client):
        """Test middleware error handling with various edge cases."""
        response = client.get('/test', headers={'Authorization': ''})
        assert response.status_code == 200  
        
        response = client.get('/test', headers={'Authorization': 'Bearer'})
        assert response.status_code == 200  
        
        long_invalid_token = "invalid." * 100
        response = client.get('/test', headers={
            'Authorization': f'Bearer {long_invalid_token}'
        })
        assert response.status_code == 200 


class TestMiddlewareDecoratorBehavior:
    """Test the decorator behavior and function wrapping."""
    
    def test_jwt_required_preserves_function_metadata(self):
        """Test that @jwt_required preserves original function metadata."""
        from flask import Flask
        
        app = Flask(__name__)
        app.config['JWT_SECRET_KEY'] = 'f270e33cbbb66099ed613db6f96b9720e2494f3e82de7bda90ee9dc0308f227c'
        
        @app.route('/test')
        @jwt_required
        def test_function():
            """This is a test function."""
            return {"message": "test"}
        
        assert test_function.__name__ == 'test_function'
        assert test_function.__doc__ == 'This is a test function.'
    
    def test_jwt_optional_preserves_function_metadata(self):
        """Test that @jwt_optional preserves original function metadata."""
        from flask import Flask
        
        app = Flask(__name__)
        app.config['JWT_SECRET_KEY'] = 'f270e33cbbb66099ed613db6f96b9720e2494f3e82de7bda90ee9dc0308f227c'
        
        @app.route('/test')
        @jwt_optional
        def test_function():
            """This is a test function."""
            return {"message": "test"}
        
        assert test_function.__name__ == 'test_function'
        assert test_function.__doc__ == 'This is a test function.'
    
    def test_decorator_chaining(self, valid_token):
        """Test that decorators can be chained properly."""
        from flask import Flask, request
        
        app = Flask(__name__)
        app.config['JWT_SECRET_KEY'] = 'f270e33cbbb66099ed613db6f96b9720e2494f3e82de7bda90ee9dc0308f227c'
        
        def custom_decorator(f):
            def decorated_function(*args, **kwargs):
                return f(*args, **kwargs)
            return decorated_function
        
        @app.route('/test')
        @custom_decorator
        @jwt_optional
        def test_function():
            return {"message": "test"}
        
        with app.test_client() as client:
            response = client.get('/test', headers={
                'Authorization': f'Bearer {valid_token}'
            })
            assert response.status_code == 200
