from app import ma
from models.user import User
from marshmallow import fields, validate, validates, ValidationError, post_load

class UserSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = User
        load_instance = False
        exclude = ("password_hash",)

    # ---------- Campos ----------
    username = fields.String(required=True, validate=validate.Length(min=3, max=64))
    email = fields.Email(required=True)
    password = fields.String(
        required=True,
        load_only=True,
        validate=validate.Length(min=8, error="Password must be at least 8 characters long"),
    )
    role = fields.String(validate=validate.OneOf(["admin", "user"]))

    # ---------- Validadores ----------
    @validates("username")
    def validate_username(self, value, **kwargs):   #  ←  AÑADE **kwargs
        if User.query.filter_by(username=value).first():
            raise ValidationError("Username already exists")
        return value

    @validates("email")
    def validate_email(self, value, **kwargs):      #  ←  AÑADE **kwargs
        if User.query.filter_by(email=value).first():
            raise ValidationError("Email already exists")
        return value

    # ---------- post_load ----------
    @post_load
    def make_user(self, data, **kwargs):
        return User(**data)
