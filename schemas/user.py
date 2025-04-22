from app import ma
from models.user import User
from marshmallow import fields, validate, validates, ValidationError

class UserSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = User
        load_instance = True
        exclude = ('password_hash',)
    
    # Add password field for input but don't return it in serialized data
    password = fields.String(
        required=True, 
        load_only=True,
        validate=validate.Length(min=8, error="Password must be at least 8 characters long")
    )
    
    email = fields.Email(required=True)
    username = fields.String(required=True, validate=validate.Length(min=3, max=64))
    role = fields.String(validate=validate.OneOf(['admin', 'user']))
    
    @validates('username')
    def validate_username(self, value):
        if User.query.filter_by(username=value).first():
            raise ValidationError('Username already exists')
        return value
    
    @validates('email')
    def validate_email(self, value):
        if User.query.filter_by(email=value).first():
            raise ValidationError('Email already exists')
        return value
