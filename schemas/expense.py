from app import ma
from models.expense import (Expense, RecurringExpense, AccruedExpense, 
                            Currency, FrequencyType, RecurringExpenseStatus, AccruedExpenseStatus)
from marshmallow import fields, validate, validates, ValidationError
from marshmallow_enum import EnumField
import datetime

class ExpenseSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Expense
        load_instance = True
    
    currency = EnumField(Currency, by_value=True)
    
    # Fields for file upload, not part of model
    receipt = fields.Raw(metadata={'type': 'file'}, load_only=True)
    
    # Provide validation for fields
    description = fields.String(required=True, validate=validate.Length(min=1, max=255))
    amount = fields.Decimal(required=True, places=2)
    date = fields.Date(required=True)
    category = fields.String(required=True)
    payment_method = fields.String(required=True)
    
    @validates('amount')
    def validate_amount(self, value):
        if value <= 0:
            raise ValidationError('Amount must be greater than zero')
        return value

class ExpenseListSchema(ma.Schema):
    id = fields.Integer()
    description = fields.String()
    date = fields.Date()
    amount = fields.Decimal(places=2)
    currency = EnumField(Currency, by_value=True)
    category = fields.String()
    payment_method = fields.String()

class RecurringExpenseSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = RecurringExpense
        load_instance = True
    
    currency = EnumField(Currency, by_value=True)
    frequency = EnumField(FrequencyType, by_value=True)
    status = EnumField(RecurringExpenseStatus, by_value=True)
    
    # Provide validation for fields
    description = fields.String(required=True, validate=validate.Length(min=1, max=255))
    amount = fields.Decimal(required=True, places=2)
    start_date = fields.Date(required=True)
    category = fields.String(required=True)
    payment_method = fields.String(required=True)
    
    @validates('amount')
    def validate_amount(self, value):
        if value <= 0:
            raise ValidationError('Amount must be greater than zero')
        return value
    
    @validates('start_date')
    def validate_start_date(self, value):
        if value < datetime.date.today():
            raise ValidationError('Start date cannot be in the past')
        return value

class RecurringExpenseListSchema(ma.Schema):
    id = fields.Integer()
    description = fields.String()
    frequency = EnumField(FrequencyType, by_value=True)
    start_date = fields.Date()
    amount = fields.Decimal(places=2)
    currency = EnumField(Currency, by_value=True)
    category = fields.String()
    status = EnumField(RecurringExpenseStatus, by_value=True)
    next_payment = fields.Date(allow_none=True)

class AccruedExpenseSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = AccruedExpense
        load_instance = True
        include_fk = True
    
    currency = EnumField(Currency, by_value=True)
    status = EnumField(AccruedExpenseStatus, by_value=True)
    
    # Fields for file upload, not part of model
    receipt = fields.Raw(metadata={'type': 'file'}, load_only=True)
    
    # Provide validation for fields
    description = fields.String(required=True, validate=validate.Length(min=1, max=255))
    amount = fields.Decimal(required=True, places=2)
    due_date = fields.Date(required=True)
    category = fields.String(required=True)
    payment_method = fields.String(required=True)
    
    @validates('amount')
    def validate_amount(self, value):
        if value <= 0:
            raise ValidationError('Amount must be greater than zero')
        return value

class AccruedExpenseListSchema(ma.Schema):
    id = fields.Integer()
    description = fields.String()
    due_date = fields.Date()
    amount = fields.Decimal(places=2)
    currency = EnumField(Currency, by_value=True)
    category = fields.String()
    status = EnumField(AccruedExpenseStatus, by_value=True)
    is_recurring = fields.Boolean()
