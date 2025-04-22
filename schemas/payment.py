from app import ma
from models.payment import Payment, PaymentStatus, PaymentType, Currency
from marshmallow import fields, validate, validates, ValidationError
from marshmallow_enum import EnumField
import datetime

class PaymentSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Payment
        load_instance = True
        include_fk = True
    
    status = EnumField(PaymentStatus, by_value=True)
    type = EnumField(PaymentType, by_value=True)
    currency = EnumField(Currency, by_value=True)
    
    # Provide validation for fields
    amount = fields.Decimal(required=True, places=2)
    project_id = fields.Integer(required=True)
    client_id = fields.Integer(required=True)
    date = fields.Date(required=True)
    
    @validates('amount')
    def validate_amount(self, value):
        if value <= 0:
            raise ValidationError('Amount must be greater than zero')
        return value
    
    @validates('paid_date')
    def validate_paid_date(self, value):
        if value and value > datetime.date.today():
            raise ValidationError('Paid date cannot be in the future')
        return value

class PaymentListSchema(ma.Schema):
    id = fields.Integer()
    project_id = fields.Integer()
    client_id = fields.Integer()
    amount = fields.Decimal(places=2)
    currency = EnumField(Currency, by_value=True)
    date = fields.Date()
    paid_date = fields.Date(allow_none=True)
    status = EnumField(PaymentStatus, by_value=True)
    type = EnumField(PaymentType, by_value=True)

class PaymentStatusUpdateSchema(ma.Schema):
    status = EnumField(PaymentStatus, by_value=True, required=True)
    paid_date = fields.Date(required=True)
    invoice_number = fields.String(allow_none=True)
