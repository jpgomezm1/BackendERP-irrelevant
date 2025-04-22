from app import ma
from models.project import Project, ProjectStatus, PaymentPlan, PaymentPlanType, Currency, FrequencyType
from marshmallow import fields, validate, validates, validates_schema, ValidationError, post_load
from marshmallow_enum import EnumField
import datetime

class PaymentPlanSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = PaymentPlan
        load_instance = True
        include_fk = True
    
    type = EnumField(PaymentPlanType, by_value=True, required=True)
    implementation_fee_currency = EnumField(Currency, by_value=True, allow_none=True)
    recurring_fee_currency = EnumField(Currency, by_value=True, allow_none=True)
    recurring_fee_frequency = EnumField(FrequencyType, by_value=True, allow_none=True)
    
    # Custom validation for payment plan fields based on type
    @validates_schema
    def validate_plan_fields(self, data, **kwargs):
        plan_type = data.get('type')
        
        if plan_type in [PaymentPlanType.FEE_UNICO, PaymentPlanType.FEE_POR_CUOTAS, PaymentPlanType.MIXTO]:
            if not data.get('implementation_fee_total'):
                raise ValidationError("Implementation fee total is required for this plan type")
            if not data.get('implementation_fee_currency'):
                raise ValidationError("Implementation fee currency is required for this plan type")
        
        if plan_type in [PaymentPlanType.FEE_POR_CUOTAS, PaymentPlanType.MIXTO]:
            if not data.get('implementation_fee_installments') or data.get('implementation_fee_installments') < 1:
                raise ValidationError("Valid implementation fee installments are required for this plan type")
        
        if plan_type in [PaymentPlanType.SUSCRIPCION_PERIODICA, PaymentPlanType.MIXTO]:
            if not data.get('recurring_fee_amount'):
                raise ValidationError("Recurring fee amount is required for this plan type")
            if not data.get('recurring_fee_currency'):
                raise ValidationError("Recurring fee currency is required for this plan type")
            if not data.get('recurring_fee_frequency'):
                raise ValidationError("Recurring fee frequency is required for this plan type")
            if not data.get('recurring_fee_day_of_charge'):
                raise ValidationError("Recurring fee day of charge is required for this plan type")

class ProjectSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Project
        load_instance = True
        include_fk = True
    
    status = EnumField(ProjectStatus, by_value=True)
    payment_plan = fields.Nested(PaymentPlanSchema)
    
    # Provide validation for fields
    name = fields.String(required=True, validate=validate.Length(min=1, max=120))
    description = fields.String(required=True)
    start_date = fields.Date(required=True)
    client_id = fields.Integer(required=True)
    
    @validates('start_date')
    def validate_start_date(self, value):
        if value > datetime.date.today() + datetime.timedelta(days=365):
            raise ValidationError('Start date cannot be more than a year in the future')
        return value
    
    @validates('end_date')
    def validate_end_date(self, value):
        if value and self.context.get('start_date') and value < self.context.get('start_date'):
            raise ValidationError('End date cannot be before start date')
        return value
    
    @post_load
    def process_nested_payment_plan(self, data, **kwargs):
        # If payment_plan is in the data and we're loading a new instance,
        # detach it from the data dict to handle separately
        if 'payment_plan' in data and isinstance(data, Project):
            payment_plan_data = data.payment_plan
            data.payment_plan = None  # Detach to avoid conflicts
            return {'project': data, 'payment_plan': payment_plan_data}
        return data

class ProjectListSchema(ma.Schema):
    id = fields.Integer()
    name = fields.String()
    client_id = fields.Integer()
    start_date = fields.Date()
    end_date = fields.Date(allow_none=True)
    status = EnumField(ProjectStatus, by_value=True)
