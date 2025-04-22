from app import ma
from models.income import Income, Currency
from marshmallow import fields, validate, validates, ValidationError
from marshmallow_enum import EnumField
import datetime

class IncomeSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Income
        load_instance = True
    
    currency = EnumField(Currency, by_value=True)
    
    # Fields for file upload, not part of model
    receipt = fields.Raw(metadata={'type': 'file'}, load_only=True)
    
    # Provide validation for fields
    description = fields.String(required=True, validate=validate.Length(min=1, max=255))
    amount = fields.Decimal(required=True, places=2)
    date = fields.Date(required=True)
    type = fields.String(required=True)
    payment_method = fields.String(required=True)
    
    @validates('amount')
    def validate_amount(self, value):
        if value <= 0:
            raise ValidationError('Amount must be greater than zero')
        return value
    
    @validates('date')
    def validate_date(self, value):
        if value > datetime.date.today():
            raise ValidationError('Income date cannot be in the future')
        return value

class IncomeListSchema(ma.Schema):
    id = fields.Integer()
    description = fields.String()
    date = fields.Date()
    amount = fields.Decimal(places=2)
    currency = EnumField(Currency, by_value=True)
    type = fields.String()
    client = fields.String(allow_none=True)
    payment_method = fields.String()
