from flask import request, jsonify
from flask_restx import Namespace, Resource, fields, reqparse
from flask_jwt_extended import jwt_required
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from models.payment import Payment, PaymentStatus, PaymentType, Currency
from models.project import Project, PaymentPlan, PaymentPlanType, FrequencyType
from models.client import Client
from schemas.payment import PaymentSchema, PaymentListSchema, PaymentStatusUpdateSchema
from app import db
from utils.pagination import paginate
from utils.currency import convert_currency
from sqlalchemy import func, and_, or_
import logging

# Setting up API namespace
api = Namespace('payments', description='Payment operations')

# Define models for swagger
payment_model = api.model('Payment', {
    'project_id': fields.Integer(required=True, description='Project ID'),
    'client_id': fields.Integer(required=True, description='Client ID'),
    'amount': fields.Float(required=True, description='Payment amount'),
    'currency': fields.String(required=True, description='Currency', enum=['COP', 'USD']),
    'date': fields.Date(required=True, description='Scheduled payment date'),
    'paid_date': fields.Date(description='Actual payment date'),
    'status': fields.String(description='Payment status', enum=['Pagado', 'Pendiente', 'Vencido']),
    'invoice_number': fields.String(description='Invoice number'),
    'invoice_url': fields.String(description='Invoice URL'),
    'type': fields.String(required=True, description='Payment type', enum=['Implementación', 'Recurrente']),
    'installment_number': fields.Integer(description='Installment number for implementation payments'),
    'notes': fields.String(description='Additional notes')
})

payment_status_model = api.model('PaymentStatusUpdate', {
    'status': fields.String(required=True, description='New payment status', enum=['Pagado', 'Pendiente', 'Vencido']),
    'paid_date': fields.Date(required=True, description='Actual payment date'),
    'invoice_number': fields.String(description='Invoice number')
})

generate_payments_model = api.model('GeneratePayments', {
    'project_id': fields.Integer(required=True, description='Project ID'),
    'months': fields.Integer(description='Number of months to generate payments for', default=12)
})

# Set up schemas
payment_schema = PaymentSchema()
payments_schema = PaymentSchema(many=True)
payment_list_schema = PaymentListSchema(many=True)
payment_status_schema = PaymentStatusUpdateSchema()

# Query parameter parser
payment_parser = reqparse.RequestParser()
payment_parser.add_argument('project_id', type=int, help='Filter by project ID')
payment_parser.add_argument('client_id', type=int, help='Filter by client ID')
payment_parser.add_argument('status', type=str, help='Filter by status')
payment_parser.add_argument('date_from', type=str, help='Filter by date from (YYYY-MM-DD)')
payment_parser.add_argument('date_to', type=str, help='Filter by date to (YYYY-MM-DD)')
payment_parser.add_argument('currency', type=str, help='Currency for conversion')
payment_parser.add_argument('sort', type=str, help='Sort field', default='date')
payment_parser.add_argument('page', type=int, help='Page number')
payment_parser.add_argument('per_page', type=int, help='Items per page')

@api.route('')
class PaymentList(Resource):
    @jwt_required()
    @api.expect(payment_parser)
    @api.response(200, 'Success')
    def get(self):
        """Get all payments with optional filtering and pagination"""
        args = payment_parser.parse_args()
        
        # Base query
        query = Payment.query
        
        # Apply filters
        if args.get('project_id'):
            query = query.filter(Payment.project_id == args['project_id'])
            
        if args.get('client_id'):
            query = query.filter(Payment.client_id == args['client_id'])
            
        if args.get('status'):
            query = query.filter(Payment.status == args['status'])
            
        if args.get('date_from'):
            try:
                date_from = datetime.strptime(args['date_from'], '%Y-%m-%d').date()
                query = query.filter(Payment.date >= date_from)
            except ValueError:
                return {'error': 'Invalid date_from format. Use YYYY-MM-DD'}, 400
                
        if args.get('date_to'):
            try:
                date_to = datetime.strptime(args['date_to'], '%Y-%m-%d').date()
                query = query.filter(Payment.date <= date_to)
            except ValueError:
                return {'error': 'Invalid date_to format. Use YYYY-MM-DD'}, 400
        
        # Apply sorting
        if args.get('sort'):
            sort_field = args['sort']
            if hasattr(Payment, sort_field):
                query = query.order_by(getattr(Payment, sort_field))
        else:
            # Default sort by date
            query = query.order_by(Payment.date)
        
        # Calculate totals before pagination
        # Get a copy of the query for aggregation
        totals_query = query.with_entities(
            Payment.status,
            func.sum(Payment.amount).label('total_amount'),
            Payment.currency
        ).group_by(Payment.status, Payment.currency)
        
        totals = {
            'Pagado': {'COP': 0, 'USD': 0},
            'Pendiente': {'COP': 0, 'USD': 0},
            'Vencido': {'COP': 0, 'USD': 0}
        }
        
        for item in totals_query.all():
            status = item[0].value
            amount = float(item[1])
            currency = item[2].value
            totals[status][currency] = amount
        
        # Convert totals if currency parameter provided
        if args.get('currency'):
            target_currency = args.get('currency')
            for status in totals:
                for source_currency in totals[status]:
                    if source_currency != target_currency:
                        totals[status][target_currency] = totals[status].get(target_currency, 0) + \
                                                          convert_currency(totals[status][source_currency], 
                                                                          source_currency, 
                                                                          target_currency)
        
        # Apply pagination
        result = paginate(query, args.get('page', 1), args.get('per_page', 10), payment_list_schema)
        
        # Add totals to result
        result['totals'] = totals
        
        return result, 200
    
    @jwt_required()
    @api.expect(payment_model)
    @api.response(201, 'Payment created successfully')
    @api.response(400, 'Validation error')
    @api.response(404, 'Project or client not found')
    def post(self):
        """Create a new payment"""
        try:
            payment_data = request.json
            
            # Check if project and client exist
            project_id = payment_data.get('project_id')
            client_id = payment_data.get('client_id')
            
            if not Project.query.get(project_id):
                return {'error': f'Project with ID {project_id} not found'}, 404
                
            if not Client.query.get(client_id):
                return {'error': f'Client with ID {client_id} not found'}, 404
            
            # Validate and deserialize input
            payment = payment_schema.load(payment_data)
            
            # Add to database
            db.session.add(payment)
            db.session.commit()
            
            return {'data': payment_schema.dump(payment)}, 201
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating payment: {str(e)}")
            return {'error': str(e)}, 400

@api.route('/<int:id>')
class PaymentDetail(Resource):
    @jwt_required()
    @api.response(200, 'Success')
    @api.response(404, 'Payment not found')
    def get(self, id):
        """Get a payment by ID"""
        payment = Payment.query.get_or_404(id)
        return {'data': payment_schema.dump(payment)}, 200
    
    @jwt_required()
    @api.expect(payment_model)
    @api.response(200, 'Payment updated successfully')
    @api.response(404, 'Payment not found')
    @api.response(400, 'Validation error')
    def put(self, id):
        """Update a payment"""
        try:
            payment = Payment.query.get_or_404(id)
            payment_data = request.json
            
            # Update payment with new data
            for key, value in payment_data.items():
                if hasattr(payment, key):
                    setattr(payment, key, value)
            
            db.session.commit()
            
            return {'data': payment_schema.dump(payment)}, 200
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating payment: {str(e)}")
            return {'error': str(e)}, 400

@api.route('/<int:id>/status')
class PaymentStatusUpdate(Resource):
    @jwt_required()
    @api.expect(payment_status_model)
    @api.response(200, 'Payment status updated successfully')
    @api.response(404, 'Payment not found')
    @api.response(400, 'Validation error')
    def patch(self, id):
        """Update payment status"""
        try:
            payment = Payment.query.get_or_404(id)
            status_data = request.json
            
            # Validate input
            validated_data = payment_status_schema.load(status_data)
            
            # Update payment status
            payment.status = validated_data['status']
            payment.paid_date = validated_data['paid_date']
            
            if 'invoice_number' in validated_data:
                payment.invoice_number = validated_data['invoice_number']
            
            db.session.commit()
            
            return {'data': payment_schema.dump(payment)}, 200
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating payment status: {str(e)}")
            return {'error': str(e)}, 400

@api.route('/overdue')
class OverduePayments(Resource):
    @jwt_required()
    @api.expect(reqparse.RequestParser().add_argument('currency', type=str, help='Currency for conversion'))
    @api.response(200, 'Success')
    def get(self):
        """Get overdue payments"""
        args = reqparse.RequestParser().add_argument('currency', type=str, help='Currency for conversion').parse_args()
        
        today = date.today()
        
        # Get all overdue payments
        overdue_payments = Payment.query.filter(
            and_(
                Payment.date < today,
                Payment.status != PaymentStatus.PAGADO
            )
        ).order_by(Payment.date).all()
        
        # Calculate total
        total_cop = sum(float(p.amount) for p in overdue_payments if p.currency == Currency.COP)
        total_usd = sum(float(p.amount) for p in overdue_payments if p.currency == Currency.USD)
        
        # Convert totals if necessary
        target_currency = args.get('currency')
        total = None
        
        if target_currency == 'COP':
            total = total_cop + convert_currency(total_usd, 'USD', 'COP')
        elif target_currency == 'USD':
            total = total_usd + convert_currency(total_cop, 'COP', 'USD')
        else:
            total = {'COP': total_cop, 'USD': total_usd}
        
        return {
            'data': payment_list_schema.dump(overdue_payments),
            'total': total
        }, 200

@api.route('/upcoming')
class UpcomingPayments(Resource):
    @jwt_required()
    @api.expect(reqparse.RequestParser()
                .add_argument('days', type=int, default=30, help='Number of days to look ahead')
                .add_argument('currency', type=str, help='Currency for conversion'))
    @api.response(200, 'Success')
    def get(self):
        """Get upcoming payments within specified days"""
        parser = reqparse.RequestParser()
        parser.add_argument('days', type=int, default=30, help='Number of days to look ahead')
        parser.add_argument('currency', type=str, help='Currency for conversion')
        args = parser.parse_args()
        
        days = args.get('days', 30)
        today = date.today()
        end_date = today + timedelta(days=days)
        
        # Get all upcoming payments
        upcoming_payments = Payment.query.filter(
            and_(
                Payment.date >= today,
                Payment.date <= end_date,
                Payment.status != PaymentStatus.PAGADO
            )
        ).order_by(Payment.date).all()
        
        # Calculate total
        total_cop = sum(float(p.amount) for p in upcoming_payments if p.currency == Currency.COP)
        total_usd = sum(float(p.amount) for p in upcoming_payments if p.currency == Currency.USD)
        
        # Convert totals if necessary
        target_currency = args.get('currency')
        total = None
        
        if target_currency == 'COP':
            total = total_cop + convert_currency(total_usd, 'USD', 'COP')
        elif target_currency == 'USD':
            total = total_usd + convert_currency(total_cop, 'COP', 'USD')
        else:
            total = {'COP': total_cop, 'USD': total_usd}
        
        return {
            'data': payment_list_schema.dump(upcoming_payments),
            'total': total
        }, 200

@api.route('/generate')
class GeneratePayments(Resource):
    @jwt_required()
    @api.expect(generate_payments_model)
    @api.response(201, 'Payments generated successfully')
    @api.response(400, 'Invalid input')
    @api.response(404, 'Project not found')
    def post(self):
        """Generate payments for a project based on its payment plan"""
        try:
            data = request.json
            project_id = data.get('project_id')
            months = data.get('months', 12)
            
            # Get project and payment plan
            project = Project.query.get_or_404(project_id)
            
            if not project.payment_plan:
                return {'error': 'Project does not have a payment plan'}, 400
            
            plan = project.payment_plan
            generated_payments = []
            
            # Generate implementation fee payments if applicable
            if plan.type in [PaymentPlanType.FEE_UNICO, PaymentPlanType.FEE_POR_CUOTAS, PaymentPlanType.MIXTO]:
                if plan.implementation_fee_total:
                    # Calculate amount per installment
                    installments = max(1, plan.implementation_fee_installments or 1)
                    amount_per_installment = float(plan.implementation_fee_total) / installments
                    
                    # Generate implementation payments
                    for i in range(installments):
                        payment_date = project.start_date + relativedelta(months=i)
                        
                        payment = Payment(
                            project_id=project.id,
                            client_id=project.client_id,
                            amount=round(amount_per_installment, 2),
                            currency=plan.implementation_fee_currency,
                            date=payment_date,
                            status=PaymentStatus.PENDIENTE,
                            type=PaymentType.IMPLEMENTACION,
                            installment_number=i+1
                        )
                        
                        db.session.add(payment)
                        generated_payments.append(payment)
            
            # Generate recurring fee payments if applicable
            if plan.type in [PaymentPlanType.SUSCRIPCION_PERIODICA, PaymentPlanType.MIXTO]:
                if plan.recurring_fee_amount and plan.recurring_fee_frequency:
                    # Define the frequency in months
                    frequency_months = {
                        FrequencyType.SEMANAL: 0.25,  # Approximation
                        FrequencyType.QUINCENAL: 0.5,  # Approximation
                        FrequencyType.MENSUAL: 1,
                        FrequencyType.BIMENSUAL: 2,
                        FrequencyType.TRIMESTRAL: 3,
                        FrequencyType.SEMESTRAL: 6,
                        FrequencyType.ANUAL: 12
                    }
                    
                    interval = frequency_months.get(plan.recurring_fee_frequency, 1)
                    
                    # Determine start date for recurring payments
                    start_date = project.start_date
                    
                    # Apply grace period if any
                    if plan.recurring_fee_grace_periods:
                        start_date = start_date + relativedelta(months=int(plan.recurring_fee_grace_periods * interval))
                    
                    # Set the day of charge
                    if plan.recurring_fee_day_of_charge:
                        # Make sure day is valid for the month
                        day = min(plan.recurring_fee_day_of_charge, 28)  # Safe value for all months
                        start_date = start_date.replace(day=day)
                    
                    # Generate recurring payments
                    num_payments = int(months / interval)
                    
                    for i in range(num_payments):
                        payment_date = start_date + relativedelta(months=int(i * interval))
                        
                        # Calculate amount with discount if applicable
                        amount = float(plan.recurring_fee_amount)
                        if plan.recurring_fee_discount_periods and i < plan.recurring_fee_discount_periods:
                            discount_rate = float(plan.recurring_fee_discount_percentage or 0) / 100
                            amount = amount * (1 - discount_rate)
                        
                        payment = Payment(
                            project_id=project.id,
                            client_id=project.client_id,
                            amount=round(amount, 2),
                            currency=plan.recurring_fee_currency,
                            date=payment_date,
                            status=PaymentStatus.PENDIENTE,
                            type=PaymentType.RECURRENTE,
                            installment_number=i+1
                        )
                        
                        db.session.add(payment)
                        generated_payments.append(payment)
            
            db.session.commit()
            
            return {
                'data': payment_list_schema.dump(generated_payments),
                'message': f'{len(generated_payments)} payments generated'
            }, 201
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error generating payments: {str(e)}")
            return {'error': str(e)}, 400

# Routes for the blueprint
routes = [
    PaymentList,
    PaymentDetail,
    PaymentStatusUpdate,
    OverduePayments,
    UpcomingPayments,
    GeneratePayments
]
