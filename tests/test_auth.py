import pytest
import json
from flask_jwt_extended import decode_token

def test_login_success(client):
    """Test successful login"""
    # Make a POST request to the login endpoint
    response = client.post('/api/auth/login', json={
        'username': 'testuser',
        'password': 'testpassword'
    })
    
    # Check status code
    assert response.status_code == 200
    
    # Check response data
    data = json.loads(response.data)
    assert 'access_token' in data
    assert 'refresh_token' in data
    assert 'user' in data
    assert data['user']['username'] == 'testuser'
    assert data['user']['email'] == 'test@example.com'
    assert 'password_hash' not in data['user']
    
    # Check tokens are valid
    access_token = data['access_token']
    refresh_token = data['refresh_token']
    assert access_token is not None
    assert refresh_token is not None

def test_login_invalid_credentials(client):
    """Test login with invalid credentials"""
    # Make a POST request with wrong password
    response = client.post('/api/auth/login', json={
        'username': 'testuser',
        'password': 'wrongpassword'
    })
    
    # Check status code
    assert response.status_code == 401
    
    # Check error message
    data = json.loads(response.data)
    assert 'error' in data
    assert data['error'] == 'Invalid credentials'
    
    # Try with non-existent user
    response = client.post('/api/auth/login', json={
        'username': 'nonexistentuser',
        'password': 'testpassword'
    })
    
    # Check status code
    assert response.status_code == 401

def test_refresh_token(client):
    """Test refreshing access token"""
    # First, login to get tokens
    response = client.post('/api/auth/login', json={
        'username': 'testuser',
        'password': 'testpassword'
    })
    
    data = json.loads(response.data)
    refresh_token = data['refresh_token']
    
    # Use refresh token to get new access token
    response = client.post('/api/auth/refresh', headers={
        'Authorization': f'Bearer {refresh_token}'
    })
    
    # Check status code
    assert response.status_code == 200
    
    # Check new access token is returned
    data = json.loads(response.data)
    assert 'access_token' in data
    assert data['access_token'] is not None

def test_logout(client, auth_headers):
    """Test logout functionality"""
    # Log out with valid token
    response = client.post('/api/auth/logout', headers=auth_headers)
    
    # Check status code
    assert response.status_code == 200
    
    # Check message
    data = json.loads(response.data)
    assert 'message' in data
    assert data['message'] == 'Logout successful'
    
    # Try to use the same token for a protected route
    response = client.get('/api/clients', headers=auth_headers)
    
    # Token should be blacklisted, so expect 401
    assert response.status_code == 401

def test_register_user(client, auth_headers):
    """Test user registration"""
    # Register a new user
    response = client.post('/api/auth/register', json={
        'username': 'newuser',
        'email': 'new@example.com',
        'password': 'newpassword',
        'role': 'user'
    }, headers=auth_headers)  # Need admin to register users
    
    # Check status code
    assert response.status_code == 201
    
    # Check response data
    data = json.loads(response.data)
    assert 'id' in data
    assert data['username'] == 'newuser'
    assert data['email'] == 'new@example.com'
    assert data['role'] == 'user'
    assert 'password_hash' not in data
    
    # Try to login with the new user
    response = client.post('/api/auth/login', json={
        'username': 'newuser',
        'password': 'newpassword'
    })
    
    # Check successful login
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'access_token' in data

def test_register_duplicate_username(client, auth_headers):
    """Test registration with duplicate username"""
    # Try to register with existing username
    response = client.post('/api/auth/register', json={
        'username': 'testuser',  # Existing username
        'email': 'unique@example.com',
        'password': 'password123',
        'role': 'user'
    }, headers=auth_headers)
    
    # Check status code
    assert response.status_code == 400

def test_token_claims(client):
    """Test JWT token contains correct claims"""
    # Login to get token
    response = client.post('/api/auth/login', json={
        'username': 'testuser',
        'password': 'testpassword'
    })
    
    data = json.loads(response.data)
    access_token = data['access_token']
    
    # Decode token without verification to inspect claims
    with client.application.app_context():
        decoded = decode_token(access_token)
        
        # Check identity and role claims
        assert decoded['sub'] == 1  # User ID
        assert decoded['role'] == 'admin'
