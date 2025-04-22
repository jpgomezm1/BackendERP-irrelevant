from flask import request, jsonify
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import (create_access_token, create_refresh_token, 
                               jwt_required, get_jwt_identity, get_jwt)
from werkzeug.security import generate_password_hash
from models.user import User
from schemas.user import UserSchema
from app import db, jwt
import logging

# Setting up API namespace
api = Namespace('auth', description='Authentication operations')

# Define request and response models
login_model = api.model('Login', {
    'username': fields.String(required=True, description='Username'),
    'password': fields.String(required=True, description='Password')
})

register_model = api.model('Register', {
    'username': fields.String(required=True, description='Username'),
    'email': fields.String(required=True, description='Email'),
    'password': fields.String(required=True, description='Password'),
    'role': fields.String(required=False, description='Role (admin or user)')
})

token_model = api.model('Token', {
    'access_token': fields.String(description='JWT access token'),
    'refresh_token': fields.String(description='JWT refresh token'),
    'user': fields.Raw(description='User data')
})

# Set up schemas
user_schema = UserSchema()

# Blacklisted tokens storage (in-memory for simplicity)
# In production, this should be a database or Redis store
blacklisted_tokens = set()

@jwt.token_in_blocklist_loader
def check_if_token_in_blacklist(jwt_header, jwt_payload):
    jti = jwt_payload["jti"]
    return jti in blacklisted_tokens

@api.route('/login')
class Login(Resource):
    @api.expect(login_model)
    @api.response(200, 'Login successful', token_model)
    @api.response(401, 'Invalid credentials')
    def post(self):
        """User login endpoint"""
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        # Find user in database
        user = User.query.filter_by(username=username).first()
        
        # Verify user and password
        if user and user.check_password(password):
            # Create tokens
            access_token = create_access_token(identity=user.id, additional_claims={'role': user.role})
            refresh_token = create_refresh_token(identity=user.id)
            
            # Return tokens and user data
            return {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'user': user_schema.dump(user)
            }, 200
        
        return {'error': 'Invalid credentials'}, 401

@api.route('/refresh')
class TokenRefresh(Resource):
    @jwt_required(refresh=True)
    @api.response(200, 'Token refreshed successfully')
    @api.response(401, 'Invalid token')
    def post(self):
        """Refresh access token"""
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return {'error': 'User not found'}, 404
            
        # Create new access token with role claim
        new_access_token = create_access_token(identity=current_user_id, additional_claims={'role': user.role})
        
        return {'access_token': new_access_token}, 200

@api.route('/logout')
class Logout(Resource):
    @jwt_required()
    @api.response(200, 'Logout successful')
    def post(self):
        """Logout endpoint - blacklist current token"""
        jti = get_jwt()["jti"]
        blacklisted_tokens.add(jti)
        return {'message': 'Logout successful'}, 200

@api.route('/register')
class Register(Resource):
    @api.expect(register_model)
    @api.response(201, 'User registered successfully')
    @api.response(400, 'Validation error')
    def post(self):
        """Register a new user (admin access may be restricted in production)"""
        try:
            user_data = request.json
            # Parse with schema for validation
            new_user = user_schema.load(user_data)
            
            # Add to database
            db.session.add(new_user)
            db.session.commit()
            
            return user_schema.dump(new_user), 201
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating user: {str(e)}")
            return {'error': str(e)}, 400

# Routes for the blueprint
routes = [
    Login,
    TokenRefresh,
    Logout,
    Register
]
