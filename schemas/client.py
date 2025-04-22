from app import ma
from models.client import Client, ClientStatus
from marshmallow import fields, validate, validates, ValidationError
from marshmallow_enum import EnumField
import datetime

class ClientSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Client
        load_instance = True
        include_fk = True
    
    status = EnumField(ClientStatus, by_value=True)
    
    # Provide validation for fields
    name = fields.String(required=True, validate=validate.Length(min=1, max=120))
    email = fields.Email(allow_none=True)
    phone = fields.String(allow_none=True, validate=validate.Length(max=50))
    start_date = fields.Date(required=True)
    
    @validates('start_date')
    def validate_start_date(self, value):
        if value > datetime.date.today():
            raise ValidationError('Start date cannot be in the future')
        return value

class ClientListSchema(ma.Schema):
    id = fields.Integer()
    name = fields.String()
    contact_name = fields.String(allow_none=True)
    email = fields.String(allow_none=True)
    phone = fields.String(allow_none=True)
    status = EnumField(ClientStatus, by_value=True)
    start_date = fields.Date()
