from flask import request, jsonify
from flask_restx import Namespace, Resource, fields, reqparse
from flask_jwt_extended import jwt_required
from werkzeug.datastructures import FileStorage
from datetime import datetime, timedelta
from sqlalchemy import func, extract
from models.income import Income, Currency
from schemas.income import IncomeSchema, IncomeListSchema
from app import db
from utils.pagination import paginate
from utils.file_storage import save_file, get_file_path
from utils.currency import convert_currency
import os
import logging

# Setting up API namespace
api = Namespace('incomes', description='Income operations')

# Define models for swagger
income_model = api.model('Income', {
    'description': fields.String(required=True, description='Income description'),
    'date': fields.Date(required=True, description='Income date'),
    'amount': fields.Float(required=True, description='Income amount'),
    'currency': fields.String(required=True, description='Currency', enum=['COP', 'USD']),
    'type': fields.String(required=True, description='Income type'),
    'client': fields.String(description='Client name'),
    'payment_method': fields.String(required=True, description='Payment method'),
    'notes': fields.String(description='Additional notes')
})

# Set up schemas
income_schema = IncomeSchema()
incomes_schema = IncomeSchema(many=True)
income_list_schema = IncomeListSchema(many=True)

# Query parameter parser
income_parser = reqparse.RequestParser()
income_parser.add_argument('type', type=str, help='Filter by income type')
income_parser.add_argument('date_from', type=str, help='Filter by date from (YYYY-MM-DD)')
income_parser.add_argument('date_to', type=str, help='Filter by date to (YYYY-MM-DD)')
income_parser.add_argument('currency', type=str, help='Currency for conversion')
income_parser.add_argument('sort', type=str, help='Sort field')
income_parser.add_argument('page', type=int, help='Page number')
income_parser.add_argument('per_page', type=int, help='Items per page')

# Setup file upload parser
income_upload_parser = reqparse.RequestParser()
income_upload_parser.add_argument('description', type=str, required=True, help='Income description')
income_upload_parser.add_argument('date', type=str, required=True, help='Income date (YYYY-MM-DD)')
income_upload_parser.add_argument('amount', type=float, required=True, help='Income amount')
income_upload_parser.add_argument('currency', type=str, required=True, help='Currency (COP or USD)')
income_upload_parser.add_argument('type', type=str, required=True, help='Income type')
income_upload_parser.add_argument('client', type=str, help='Client name')
income_upload_parser.add_argument('payment_method', type=str, required=True, help='Payment method')
income_upload_parser.add_argument('notes', type=str, help='Additional notes')
income_upload_parser.add_argument('receipt', type=FileStorage, location='files', help='Receipt file')

# Analysis parameter parser
analysis_parser = reqparse.RequestParser()
analysis_parser.add_argument('period', type=str, default='month', help='Analysis period (month, quarter, year)')
analysis_parser.add_argument('currency', type=str, help='Currency for conversion')

@api.route('')
class IncomeList(Resource):
    @jwt_required()
    @api.expect(income_parser)
    @api.response(200, 'Success')
    def get(self):
        """Get all incomes with optional filtering and pagination"""
        args = income_parser.parse_args()
        
        # Base query
        query = Income.query
        
        # Apply filters
        if args.get('type'):
            query = query.filter(Income.type == args['type'])
            
        if args.get('date_from'):
            try:
                date_from = datetime.strptime(args['date_from'], '%Y-%m-%d').date()
                query = query.filter(Income.date >= date_from)
            except ValueError:
                return {'error': 'Invalid date_from format. Use YYYY-MM-DD'}, 400
                
        if args.get('date_to'):
            try:
                date_to = datetime.strptime(args['date_to'], '%Y-%m-%d').date()
                query = query.filter(Income.date <= date_to)
            except ValueError:
                return {'error': 'Invalid date_to format. Use YYYY-MM-DD'}, 400
        
        # Apply sorting
        if args.get('sort'):
            sort_field = args['sort']
            if hasattr(Income, sort_field):
                query = query.order_by(getattr(Income, sort_field))
        else:
            # Default sort by date desc
            query = query.order_by(Income.date.desc())
        
        # Calculate total before pagination
        total_cop = sum(float(i.amount) for i in query.all() if i.currency == Currency.COP)
        total_usd = sum(float(i.amount) for i in query.all() if i.currency == Currency.USD)
        
        # Convert totals if necessary
        target_currency = args.get('currency')
        total = None
        
        if target_currency == 'COP':
            total = total_cop + convert_currency(total_usd, 'USD', 'COP')
        elif target_currency == 'USD':
            total = total_usd + convert_currency(total_cop, 'COP', 'USD')
        else:
            total = {'COP': total_cop, 'USD': total_usd}
        
        # Apply pagination
        result = paginate(query, args.get('page', 1), args.get('per_page', 10), income_list_schema)
        
        # Add total to result
        result['total'] = total
        
        return result, 200
    
    @jwt_required()
    @api.expect(income_upload_parser)
    @api.response(201, 'Income created successfully')
    @api.response(400, 'Validation error')
    def post(self):
        """Create a new income"""
        try:
            args = income_upload_parser.parse_args()
            
            # Process file if uploaded
            receipt_path = None
            if args.get('receipt'):
                receipt_path = save_file(args['receipt'])
            
            # Process date
            try:
                date_obj = datetime.strptime(args['date'], '%Y-%m-%d').date()
            except ValueError:
                return {'error': 'Invalid date format. Use YYYY-MM-DD'}, 400
            
            # Create income object
            income_data = {
                'description': args['description'],
                'date': date_obj,
                'amount': args['amount'],
                'currency': args['currency'],
                'type': args['type'],
                'client': args.get('client'),
                'payment_method': args['payment_method'],
                'notes': args.get('notes'),
                'receipt_path': receipt_path
            }
            
            # Validate and deserialize input
            income = income_schema.load(income_data)
            
            # Add to database
            db.session.add(income)
            db.session.commit()
            
            return {'data': income_schema.dump(income)}, 201
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating income: {str(e)}")
            return {'error': str(e)}, 400

@api.route('/<int:id>')
class IncomeDetail(Resource):
    @jwt_required()
    @api.response(200, 'Success')
    @api.response(404, 'Income not found')
    def get(self, id):
        """Get an income by ID"""
        income = Income.query.get_or_404(id)
        return {'data': income_schema.dump(income)}, 200
    
    @jwt_required()
    @api.expect(income_model)
    @api.response(200, 'Income updated successfully')
    @api.response(404, 'Income not found')
    @api.response(400, 'Validation error')
    def put(self, id):
        """Update an income"""
        try:
            income = Income.query.get_or_404(id)
            income_data = request.json
            
            # Update income with new data
            for key, value in income_data.items():
                if hasattr(income, key):
                    setattr(income, key, value)
            
            db.session.commit()
            
            return {'data': income_schema.dump(income)}, 200
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating income: {str(e)}")
            return {'error': str(e)}, 400
    
    @jwt_required()
    @api.response(200, 'Income deleted successfully')
    @api.response(404, 'Income not found')
    @api.response(400, 'Error deleting income')
    def delete(self, id):
        """Delete an income"""
        income = Income.query.get_or_404(id)
        
        try:
            # Delete receipt file if exists
            if income.receipt_path:
                file_path = get_file_path(income.receipt_path)
                if os.path.exists(file_path):
                    os.remove(file_path)
            
            # Delete from database
            db.session.delete(income)
            db.session.commit()
            
            return {'message': 'Income deleted'}, 200
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error deleting income: {str(e)}")
            return {'error': str(e)}, 400

@api.route('/analysis')
class IncomeAnalysis(Resource):
    @jwt_required()
    @api.expect(analysis_parser)
    @api.response(200, 'Success')
    def get(self):
        """Get income analysis data"""
        args = analysis_parser.parse_args()
        period = args.get('period', 'month')
        target_currency = args.get('currency')
        
        today = datetime.today()
        
        # Define the time range based on period
        if period == 'month':
            # Last 12 months
            start_date = today - timedelta(days=365)
            group_by = func.date_trunc('month', Income.date)
            label_format = '%Y-%m'
        elif period == 'quarter':
            # Last 8 quarters
            start_date = today - timedelta(days=730)  # 2 years
            group_by = func.date_trunc('quarter', Income.date)
            label_format = '%Y-Q%m'  # Will need post-processing
        elif period == 'year':
            # Last 5 years
            start_date = today - timedelta(days=1825)  # 5 years
            group_by = func.date_trunc('year', Income.date)
            label_format = '%Y'
        else:
            return {'error': 'Invalid period. Use month, quarter, or year'}, 400
            
        # Monthly/quarterly/yearly aggregated data
        period_data_query = db.session.query(
            group_by.label('period'),
            func.sum(Income.amount).label('amount'),
            Income.currency
        ).filter(
            Income.date >= start_date.date()
        ).group_by(
            group_by,
            Income.currency
        ).order_by(
            group_by
        ).all()
        
        # Process period data
        period_data = {}
        
        for item in period_data_query:
            period_date = item[0]
            amount = float(item[1])
            currency = item[2].value
            
            # Format the period label
            if period == 'quarter':
                quarter = (period_date.month - 1) // 3 + 1
                label = f"{period_date.year}-Q{quarter}"
            else:
                label = period_date.strftime(label_format)
            
            if label not in period_data:
                period_data[label] = {'COP': 0, 'USD': 0}
                
            period_data[label][currency] = amount
        
        # Convert to target currency if specified
        if target_currency in ['COP', 'USD']:
            for label in period_data:
                source_currency = 'USD' if target_currency == 'COP' else 'COP'
                converted_amount = convert_currency(period_data[label][source_currency], source_currency, target_currency)
                period_data[label][target_currency] += converted_amount
                period_data[label].pop(source_currency)
        
        # Format for response (sorted by period)
        monthly_data = [{'period': k, **v} for k, v in sorted(period_data.items())]
        
        # Client income data
        client_data_query = db.session.query(
            Income.client,
            func.sum(Income.amount).label('amount'),
            Income.currency
        ).filter(
            Income.client.isnot(None),
            Income.date >= start_date.date()
        ).group_by(
            Income.client,
            Income.currency
        ).order_by(
            func.sum(Income.amount).desc()
        ).limit(10).all()
        
        # Process client data
        client_data = {}
        
        for item in client_data_query:
            client = item[0] or "Other"
            amount = float(item[1])
            currency = item[2].value
            
            if client not in client_data:
                client_data[client] = {'COP': 0, 'USD': 0}
                
            client_data[client][currency] = amount
        
        # Convert to target currency if specified
        if target_currency in ['COP', 'USD']:
            for client in client_data:
                source_currency = 'USD' if target_currency == 'COP' else 'COP'
                converted_amount = convert_currency(client_data[client][source_currency], source_currency, target_currency)
                client_data[client][target_currency] += converted_amount
                client_data[client].pop(source_currency)
        
        # Format for response
        client_income_data = [{'client': k, **v} for k, v in client_data.items()]
        
        # Calculate total for current month
        current_month_start = today.replace(day=1)
        total_month_query = db.session.query(
            func.sum(Income.amount).label('amount'),
            Income.currency
        ).filter(
            Income.date >= current_month_start.date(),
            Income.date <= today.date()
        ).group_by(
            Income.currency
        ).all()
        
        total_month = {'COP': 0, 'USD': 0}
        
        for item in total_month_query:
            amount = float(item[0]) if item[0] else 0
            currency = item[1].value
            total_month[currency] = amount
        
        # Convert to target currency if specified
        if target_currency in ['COP', 'USD']:
            source_currency = 'USD' if target_currency == 'COP' else 'COP'
            converted_amount = convert_currency(total_month[source_currency], source_currency, target_currency)
            total_month[target_currency] += converted_amount
            total_month.pop(source_currency)
        
        # Calculate average monthly income for the last 12 months
        one_year_ago = today - timedelta(days=365)
        avg_month_query = db.session.query(
            func.avg(db.session.query(
                func.sum(Income.amount)
            ).filter(
                Income.date >= one_year_ago.date(),
                Income.currency == currency
            ).group_by(
                func.date_trunc('month', Income.date)
            )).label('avg_amount'),
            Income.currency
        ).group_by(
            Income.currency
        ).all()
        
        avg_month = {'COP': 0, 'USD': 0}
        
        for item in avg_month_query:
            amount = float(item[0]) if item[0] else 0
            currency = item[1].value
            avg_month[currency] = amount
        
        # Convert to target currency if specified
        if target_currency in ['COP', 'USD']:
            source_currency = 'USD' if target_currency == 'COP' else 'COP'
            converted_amount = convert_currency(avg_month[source_currency], source_currency, target_currency)
            avg_month[target_currency] += converted_amount
            avg_month.pop(source_currency)
        
        # Calculate percent of income from clients
        client_income_query = db.session.query(
            func.sum(Income.amount).label('amount'),
            Income.currency
        ).filter(
            Income.client.isnot(None),
            Income.date >= one_year_ago.date()
        ).group_by(
            Income.currency
        ).all()
        
        client_income = {'COP': 0, 'USD': 0}
        
        for item in client_income_query:
            amount = float(item[0]) if item[0] else 0
            currency = item[1].value
            client_income[currency] = amount
        
        # Calculate total income for the same period
        total_income_query = db.session.query(
            func.sum(Income.amount).label('amount'),
            Income.currency
        ).filter(
            Income.date >= one_year_ago.date()
        ).group_by(
            Income.currency
        ).all()
        
        total_income = {'COP': 0, 'USD': 0}
        
        for item in total_income_query:
            amount = float(item[0]) if item[0] else 0
            currency = item[1].value
            total_income[currency] = amount
        
        # Calculate percentages
        client_income_percent = {}
        
        if target_currency in ['COP', 'USD']:
            # Convert all to target currency
            client_income_converted = client_income.get(target_currency, 0)
            if target_currency == 'COP':
                client_income_converted += convert_currency(client_income.get('USD', 0), 'USD', 'COP')
            else:
                client_income_converted += convert_currency(client_income.get('COP', 0), 'COP', 'USD')
                
            total_income_converted = total_income.get(target_currency, 0)
            if target_currency == 'COP':
                total_income_converted += convert_currency(total_income.get('USD', 0), 'USD', 'COP')
            else:
                total_income_converted += convert_currency(total_income.get('COP', 0), 'COP', 'USD')
                
            client_income_percent[target_currency] = (client_income_converted / total_income_converted * 100) if total_income_converted > 0 else 0
        else:
            # Calculate for both currencies
            for curr in ['COP', 'USD']:
                client_income_percent[curr] = (client_income.get(curr, 0) / total_income.get(curr, 1) * 100) if total_income.get(curr, 0) > 0 else 0
        
        return {
            'monthly_data': monthly_data,
            'client_data': client_income_data,
            'total_month': total_month,
            'avg_month': avg_month,
            'client_income_percent': client_income_percent
        }, 200

# Routes for the blueprint
routes = [
    IncomeList,
    IncomeDetail,
    IncomeAnalysis
]
