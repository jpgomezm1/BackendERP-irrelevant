from flask import request, jsonify
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
)
from werkzeug.security import generate_password_hash
from models.user import User
from schemas.user import UserSchema
from app import db, jwt
import logging

# ------------------------------------------------------------------------------
# API namespace setup
# ------------------------------------------------------------------------------
api = Namespace("auth", description="Authentication operations")

# ------------------------------------------------------------------------------
# Swagger models
# ------------------------------------------------------------------------------
login_model = api.model(
    "Login",
    {
        "username": fields.String(required=True, description="Username"),
        "password": fields.String(required=True, description="Password"),
    },
)

register_model = api.model(
    "Register",
    {
        "username": fields.String(required=True, description="Username"),
        "email": fields.String(required=True, description="Email"),
        "password": fields.String(required=True, description="Password"),
        "role": fields.String(required=False, description="Role (admin or user)"),
    },
)

token_model = api.model(
    "Token",
    {
        "access_token": fields.String(description="JWT access token"),
        "refresh_token": fields.String(description="JWT refresh token"),
        "user": fields.Raw(description="User data"),
    },
)

# ------------------------------------------------------------------------------
# Schemas & helpers
# ------------------------------------------------------------------------------
user_schema = UserSchema()

# In-memory blacklist (replace with DB/Redis in production)
blacklisted_tokens: set[str] = set()


@jwt.token_in_blocklist_loader
def check_if_token_in_blacklist(jwt_header, jwt_payload):
    """Tell Flask-JWT-Extended if a token has been revoked/blacklisted."""
    return jwt_payload["jti"] in blacklisted_tokens


# ------------------------------------------------------------------------------
# /auth/login
# ------------------------------------------------------------------------------
@api.route("/login")
class Login(Resource):
    @api.expect(login_model)
    @api.response(200, "Login successful", token_model)
    @api.response(401, "Invalid credentials")
    def post(self):
        """Authenticate user and issue access/refresh tokens."""
        data = request.json or {}
        username = data.get("username")
        password = data.get("password")

        # Look up the user
        user = User.query.filter_by(username=username).first()

        # Validate credentials
        if user and user.check_password(password):
            # ------------------------------------------------------------------
            # IMPORTANT CHANGE: identity must be *string* so that PyJWT accepts
            # the 'sub' claim during validation.
            # ------------------------------------------------------------------
            user_id_str = str(user.id)

            access_token = create_access_token(
                identity=user_id_str, additional_claims={"role": user.role}
            )
            refresh_token = create_refresh_token(identity=user_id_str)

            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user": user_schema.dump(user),
            }, 200

        return {"error": "Invalid credentials"}, 401


# ------------------------------------------------------------------------------
# /auth/refresh
# ------------------------------------------------------------------------------
@api.route("/refresh")
class TokenRefresh(Resource):
    @jwt_required(refresh=True)
    @api.response(200, "Token refreshed successfully")
    @api.response(401, "Invalid token")
    def post(self):
        """Issue a new access token using a valid refresh token."""
        # get_jwt_identity() now returns a string → convert to int for DB lookups
        current_user_id = int(get_jwt_identity())
        user = User.query.get(current_user_id)

        if not user:
            return {"error": "User not found"}, 404

        new_access_token = create_access_token(
            identity=str(current_user_id),  # keep string
            additional_claims={"role": user.role},
        )

        return {"access_token": new_access_token}, 200


# ------------------------------------------------------------------------------
# /auth/logout
# ------------------------------------------------------------------------------
@api.route("/logout")
class Logout(Resource):
    @jwt_required()
    @api.response(200, "Logout successful")
    def post(self):
        """Revoke current access token (add to blacklist)."""
        jti = get_jwt()["jti"]
        blacklisted_tokens.add(jti)
        return {"message": "Logout successful"}, 200


# ------------------------------------------------------------------------------
# /auth/register
# ------------------------------------------------------------------------------
@api.route("/register")
class Register(Resource):
    @api.expect(register_model)
    @api.response(201, "User registered successfully")
    @api.response(400, "Validation error")
    def post(self):
        """Create a new user account."""
        try:
            user_data = request.json or {}
            new_user = user_schema.load(user_data)  # marshmallow validation

            db.session.add(new_user)
            db.session.commit()

            return user_schema.dump(new_user), 201

        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating user: {e}")
            return {"error": str(e)}, 400


# ------------------------------------------------------------------------------
# For documentation generators that list all resources
# ------------------------------------------------------------------------------
routes = [Login, TokenRefresh, Logout, Register]
