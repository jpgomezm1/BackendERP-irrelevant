from flask import request, jsonify
from flask_restx import Namespace, Resource, fields, reqparse
from flask_jwt_extended import jwt_required
from werkzeug.datastructures import FileStorage
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from models.expense import (Expense, RecurringExpense, AccruedExpense, 
                           Currency, FrequencyType, RecurringExpenseStatus, AccruedExpenseStatus)
from schemas.expense import (ExpenseSchema, ExpenseListSchema, 
                            RecurringExpenseSchema, RecurringExpenseListSchema,
                            AccruedExpenseSchema, AccruedExpenseListSchema)
from app import db
from utils.pagination import paginate
from utils.file_storage import save_file, get_file_path
from utils.currency import convert_currency
from sqlalchemy import func
import os
import logging

# Setting up API namespace
api = Namespace('expenses', description='Expense operations')

# Define models for swagger
expense_model = api.model('Expense', {
    'description': fields.String(required=True, description='Expense description'),
    'date': fields.Date(required=True, description='Expense date'),
    'amount': fields.Float(required=True, description='Expense amount'),
    'currency': fields.String(required=True, description='Currency', enum=['COP', 'USD']),
    'category': fields.String(required=True, description='Expense category'),
    'payment_method': fields.String(required=True, description='Payment method'),
    'notes': fields.String(description='Additional notes')
})

recurring_expense_model = api.model('RecurringExpense', {
    'description': fields.String(required=True, description='Expense description'),
    'frequency': fields.String(required=True, description='Frequency', 
                             enum=['Diaria', 'Semanal', 'Quincenal', 'Mensual', 'Bimensual', 'Trimestral', 'Semestral', 'Anual']),
    'start_date': fields.Date(required=True, description='Start date'),
    'amount': fields.Float(required=True, description='Expense amount'),
    'currency': fields.String(required=True, description='Currency', enum=['COP', 'USD']),
    'category': fields.String(required=True, description='Expense category'),
    'payment_method': fields.String(required=True, description='Payment method'),
    'status': fields.String(description='Status', enum=['Activo', 'Pausado']),
    'notes': fields.String(description='Additional notes')
})

accrued_expense_model = api.model('AccruedExpense', {
    'description': fields.String(required=True, description='Expense description'),
    'due_date': fields.Date(required=True, description='Due date'),
    'amount': fields.Float(required=True, description='Expense amount'),
    'currency': fields.String(required=True, description='Currency', enum=['COP', 'USD']),
    'category': fields.String(required=True, description='Expense category'),
    'payment_method': fields.String(required=True, description='Payment method'),
    'status': fields.String(description='Status', enum=['pagado', 'pendiente', 'vencido']),
    'is_recurring': fields.Boolean(description='Is from recurring expense'),
    'recurring_id': fields.Integer(description='Recurring expense ID'),
    'notes': fields.String(description='Additional notes')
})

# Set up schemas
expense_schema = ExpenseSchema()
expenses_schema = ExpenseSchema(many=True)
expense_list_schema = ExpenseListSchema(many=True)

recurring_expense_schema = RecurringExpenseSchema()
recurring_expenses_schema = RecurringExpenseSchema(many=True)
recurring_expense_list_schema = RecurringExpenseListSchema(many=True)

accrued_expense_schema = AccruedExpenseSchema()
accrued_expenses_schema = AccruedExpenseSchema(many=True)
accrued_expense_list_schema = AccruedExpenseListSchema(many=True)

# Query parameter parser
expense_parser = reqparse.RequestParser()
expense_parser.add_argument('category', type=str, help='Filter by category')
expense_parser.add_argument('date_from', type=str, help='Filter by date from (YYYY-MM-DD)')
expense_parser.add_argument('date_to', type=str, help='Filter by date to (YYYY-MM-DD)')
expense_parser.add_argument('currency', type=str, help='Currency for conversion')
expense_parser.add_argument('sort', type=str, help='Sort field')
expense_parser.add_argument('page', type=int, help='Page number')
expense_parser.add_argument('per_page', type=int, help='Items per page')

recurring_expense_parser = reqparse.RequestParser()
recurring_expense_parser.add_argument('status', type=str, help='Filter by status')
recurring_expense_parser.add_argument('category', type=str, help='Filter by category')
recurring_expense_parser.add_argument('frequency', type=str, help='Filter by frequency')
recurring_expense_parser.add_argument('page', type=int, help='Page number')
recurring_expense_parser.add_argument('per_page', type=int, help='Items per page')

accrued_expense_parser = reqparse.RequestParser()
accrued_expense_parser.add_argument('status', type=str, help='Filter by status')
accrued_expense_parser.add_argument('category', type=str, help='Filter by category')
accrued_expense_parser.add_argument('date_from', type=str, help='Filter by due date from (YYYY-MM-DD)')
accrued_expense_parser.add_argument('date_to', type=str, help='Filter by due date to (YYYY-MM-DD)')
accrued_expense_parser.add_argument('is_recurring', type=bool, help='Filter by recurring flag')
accrued_expense_parser.add_argument('page', type=int, help='Page number')
accrued_expense_parser.add_argument('per_page', type=int, help='Items per page')

# Setup file upload parser
expense_upload_parser = reqparse.RequestParser()
expense_upload_parser.add_argument('description', type=str, required=True, help='Expense description')
expense_upload_parser.add_argument('date', type=str, required=True, help='Expense date (YYYY-MM-DD)')
expense_upload_parser.add_argument('amount', type=float, required=True, help='Expense amount')
expense_upload_parser.add_argument('currency', type=str, required=True, help='Currency (COP or USD)')
expense_upload_parser.add_argument('category', type=str, required=True, help='Expense category')
expense_upload_parser.add_argument('payment_method', type=str, required=True, help='Payment method')
expense_upload_parser.add_argument('notes', type=str, help='Additional notes')
expense_upload_parser.add_argument('receipt', type=FileStorage, location='files', help='Receipt file')

@api.route('')
class ExpenseList(Resource):
    @jwt_required()
    @api.expect(expense_parser)
    @api.response(200, 'Success')
    def get(self):
        """Get all expenses with optional filtering and pagination"""
        args = expense_parser.parse_args()
        
        # Base query
        query = Expense.query
        
        # Apply filters
        if args.get('category'):
            query = query.filter(Expense.category == args['category'])
            
        if args.get('date_from'):
            try:
                date_from = datetime.strptime(args['date_from'], '%Y-%m-%d').date()
                query = query.filter(Expense.date >= date_from)
            except ValueError:
                return {'error': 'Invalid date_from format. Use YYYY-MM-DD'}, 400
                
        if args.get('date_to'):
            try:
                date_to = datetime.strptime(args['date_to'], '%Y-%m-%d').date()
                query = query.filter(Expense.date <= date_to)
            except ValueError:
                return {'error': 'Invalid date_to format. Use YYYY-MM-DD'}, 400
        
        # Apply sorting
        if args.get('sort'):
            sort_field = args['sort']
            if hasattr(Expense, sort_field):
                query = query.order_by(getattr(Expense, sort_field))
        else:
            # Default sort by date desc
            query = query.order_by(Expense.date.desc())
        
        # Calculate total before pagination
        total_cop = sum(float(e.amount) for e in query.all() if e.currency == Currency.COP)
        total_usd = sum(float(e.amount) for e in query.all() if e.currency == Currency.USD)
        
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
        result = paginate(query, args.get('page', 1), args.get('per_page', 10), expense_list_schema)
        
        # Add total to result
        result['total'] = total
        
        return result, 200
    
    @jwt_required()
    @api.expect(expense_upload_parser)
    @api.response(201, 'Expense created successfully')
    @api.response(400, 'Validation error')
    def post(self):
        """Create a new expense"""
        try:
            args = expense_upload_parser.parse_args()
            
            # Process file if uploaded
            receipt_path = None
            if args.get('receipt'):
                receipt_path = save_file(args['receipt'])
            
            # Process date
            try:
                date_obj = datetime.strptime(args['date'], '%Y-%m-%d').date()
            except ValueError:
                return {'error': 'Invalid date format. Use YYYY-MM-DD'}, 400
            
            # Create expense object
            expense_data = {
                'description': args['description'],
                'date': date_obj,
                'amount': args['amount'],
                'currency': args['currency'],
                'category': args['category'],
                'payment_method': args['payment_method'],
                'notes': args.get('notes'),
                'receipt_path': receipt_path
            }
            
            # Validate and deserialize input
            expense = expense_schema.load(expense_data)
            
            # Add to database
            db.session.add(expense)
            db.session.commit()
            
            return {'data': expense_schema.dump(expense)}, 201
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating expense: {str(e)}")
            return {'error': str(e)}, 400

@api.route('/<int:id>')
class ExpenseDetail(Resource):
    @jwt_required()
    @api.response(200, 'Success')
    @api.response(404, 'Expense not found')
    def get(self, id):
        """Get an expense by ID"""
        expense = Expense.query.get_or_404(id)
        return {'data': expense_schema.dump(expense)}, 200
    
    @jwt_required()
    @api.expect(expense_model)
    @api.response(200, 'Expense updated successfully')
    @api.response(404, 'Expense not found')
    @api.response(400, 'Validation error')
    def put(self, id):
        """Update an expense"""
        try:
            expense = Expense.query.get_or_404(id)
            expense_data = request.json
            
            # Update expense with new data
            for key, value in expense_data.items():
                if hasattr(expense, key):
                    setattr(expense, key, value)
            
            db.session.commit()
            
            return {'data': expense_schema.dump(expense)}, 200
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating expense: {str(e)}")
            return {'error': str(e)}, 400
    
    @jwt_required()
    @api.response(200, 'Expense deleted successfully')
    @api.response(404, 'Expense not found')
    @api.response(400, 'Error deleting expense')
    def delete(self, id):
        """Delete an expense"""
        expense = Expense.query.get_or_404(id)
        
        try:
            # Delete receipt file if exists
            if expense.receipt_path:
                file_path = get_file_path(expense.receipt_path)
                if os.path.exists(file_path):
                    os.remove(file_path)
            
            # Delete from database
            db.session.delete(expense)
            db.session.commit()
            
            return {'message': 'Expense deleted'}, 200
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error deleting expense: {str(e)}")
            return {'error': str(e)}, 400

@api.route('/recurring')
class RecurringExpenseList(Resource):
    @jwt_required()
    @api.expect(recurring_expense_parser)
    @api.response(200, 'Success')
    def get(self):
        """Get all recurring expenses with optional filtering and pagination"""
        args = recurring_expense_parser.parse_args()
        
        # Base query
        query = RecurringExpense.query
        
        # Apply filters
        if args.get('status'):
            query = query.filter(RecurringExpense.status == args['status'])
            
        if args.get('category'):
            query = query.filter(RecurringExpense.category == args['category'])
            
        if args.get('frequency'):
            query = query.filter(RecurringExpense.frequency == args['frequency'])
        
        # Default sort by next_payment
        query = query.order_by(RecurringExpense.next_payment)
        
        # Apply pagination
        result = paginate(query, args.get('page', 1), args.get('per_page', 10), recurring_expense_list_schema)
        
        return result, 200
    
    @jwt_required()
    @api.expect(recurring_expense_model)
    @api.response(201, 'Recurring expense created successfully')
    @api.response(400, 'Validation error')
    def post(self):
        """Create a new recurring expense"""
        try:
            recurring_expense_data = request.json
            
            # Ensure next_payment is set to start_date initially
            if 'start_date' in recurring_expense_data:
                recurring_expense_data['next_payment'] = recurring_expense_data['start_date']
            
            # Validate and deserialize input
            recurring_expense = recurring_expense_schema.load(recurring_expense_data)
            
            # Add to database
            db.session.add(recurring_expense)
            db.session.commit()
            
            return {'data': recurring_expense_schema.dump(recurring_expense)}, 201
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating recurring expense: {str(e)}")
            return {'error': str(e)}, 400

@api.route('/recurring/<int:id>')
class RecurringExpenseDetail(Resource):
    @jwt_required()
    @api.response(200, 'Success')
    @api.response(404, 'Recurring expense not found')
    def get(self, id):
        """Get a recurring expense by ID"""
        recurring_expense = RecurringExpense.query.get_or_404(id)
        return {'data': recurring_expense_schema.dump(recurring_expense)}, 200
    
    @jwt_required()
    @api.expect(recurring_expense_model)
    @api.response(200, 'Recurring expense updated successfully')
    @api.response(404, 'Recurring expense not found')
    @api.response(400, 'Validation error')
    def put(self, id):
        """Update a recurring expense"""
        try:
            recurring_expense = RecurringExpense.query.get_or_404(id)
            recurring_expense_data = request.json
            
            # Update recurring expense with new data
            for key, value in recurring_expense_data.items():
                if hasattr(recurring_expense, key):
                    setattr(recurring_expense, key, value)
            
            db.session.commit()
            
            return {'data': recurring_expense_schema.dump(recurring_expense)}, 200
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating recurring expense: {str(e)}")
            return {'error': str(e)}, 400
    
    @jwt_required()
    @api.response(200, 'Recurring expense deleted successfully')
    @api.response(404, 'Recurring expense not found')
    @api.response(409, 'Cannot delete recurring expense with associated accrued expenses')
    def delete(self, id):
        """Delete a recurring expense"""
        recurring_expense = RecurringExpense.query.get_or_404(id)
        
        # Check if it has associated accrued expenses
        if recurring_expense.accrued_expenses:
            return {'error': 'Cannot delete recurring expense with associated accrued expenses'}, 409
        
        try:
            db.session.delete(recurring_expense)
            db.session.commit()
            
            return {'message': 'Recurring expense deleted'}, 200
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error deleting recurring expense: {str(e)}")
            return {'error': str(e)}, 400

@api.route('/recurring/<int:id>/generate')
class GenerateAccruedExpenses(Resource):
    @jwt_required()
    @api.expect(reqparse.RequestParser().add_argument('months', type=int, default=3, help='Number of months to generate'))
    @api.response(201, 'Accrued expenses generated successfully')
    @api.response(404, 'Recurring expense not found')
    @api.response(400, 'Error generating accrued expenses')
    def post(self, id):
        """Generate accrued expenses for a recurring expense"""
        try:
            recurring_expense = RecurringExpense.query.get_or_404(id)
            
            # Check if recurring expense is active
            if recurring_expense.status != RecurringExpenseStatus.ACTIVO:
                return {'error': 'Cannot generate accrued expenses for inactive recurring expense'}, 400
                
            args = reqparse.RequestParser().add_argument('months', type=int, default=3).parse_args()
            months = args.get('months', 3)
            
            # Define frequency in days/months
            frequency_map = {
                FrequencyType.DIARIA: {'days': 1},
                FrequencyType.SEMANAL: {'days': 7},
                FrequencyType.QUINCENAL: {'days': 15},
                FrequencyType.MENSUAL: {'months': 1},
                FrequencyType.BIMENSUAL: {'months': 2},
                FrequencyType.TRIMESTRAL: {'months': 3},
                FrequencyType.SEMESTRAL: {'months': 6},
                FrequencyType.ANUAL: {'months': 12}
            }
            
            freq = frequency_map.get(recurring_expense.frequency, {'months': 1})
            
            # Start from next payment date
            current_date = recurring_expense.next_payment
            today = date.today()
            
            # Generate accrued expenses
            generated_expenses = []
            next_payment_date = None
            
            for i in range(months):
                # Skip if current date is in the past
                if current_date < today:
                    if 'days' in freq:
                        current_date = current_date + timedelta(days=freq['days'])
                    else:
                        current_date = current_date + relativedelta(months=freq['months'])
                    continue
                
                # Create accrued expense
                accrued_expense = AccruedExpense(
                    description=recurring_expense.description,
                    due_date=current_date,
                    amount=recurring_expense.amount,
                    currency=recurring_expense.currency,
                    category=recurring_expense.category,
                    payment_method=recurring_expense.payment_method,
                    status=AccruedExpenseStatus.PENDIENTE,
                    is_recurring=True,
                    recurring_id=recurring_expense.id,
                    notes=recurring_expense.notes
                )
                
                db.session.add(accrued_expense)
                generated_expenses.append(accrued_expense)
                
                # Save the next payment date
                if i == 0:
                    next_payment_date = current_date
                
                # Move to next period
                if 'days' in freq:
                    current_date = current_date + timedelta(days=freq['days'])
                else:
                    current_date = current_date + relativedelta(months=freq['months'])
            
            # Update next payment date of recurring expense
            if next_payment_date:
                recurring_expense.next_payment = next_payment_date
            
            db.session.commit()
            
            return {
                'data': accrued_expense_list_schema.dump(generated_expenses),
                'message': f'{len(generated_expenses)} accrued expenses generated'
            }, 201
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error generating accrued expenses: {str(e)}")
            return {'error': str(e)}, 400

@api.route('/accrued')
class AccruedExpenseList(Resource):
    @jwt_required()
    @api.expect(accrued_expense_parser)
    @api.response(200, 'Success')
    def get(self):
        """Get all accrued expenses with optional filtering and pagination"""
        args = accrued_expense_parser.parse_args()
        
        # Base query
        query = AccruedExpense.query
        
        # Apply filters
        if args.get('status'):
            query = query.filter(AccruedExpense.status == args['status'])
            
        if args.get('category'):
            query = query.filter(AccruedExpense.category == args['category'])
            
        if args.get('is_recurring') is not None:
            query = query.filter(AccruedExpense.is_recurring == args['is_recurring'])
            
        if args.get('date_from'):
            try:
                date_from = datetime.strptime(args['date_from'], '%Y-%m-%d').date()
                query = query.filter(AccruedExpense.due_date >= date_from)
            except ValueError:
                return {'error': 'Invalid date_from format. Use YYYY-MM-DD'}, 400
                
        if args.get('date_to'):
            try:
                date_to = datetime.strptime(args['date_to'], '%Y-%m-%d').date()
                query = query.filter(AccruedExpense.due_date <= date_to)
            except ValueError:
                return {'error': 'Invalid date_to format. Use YYYY-MM-DD'}, 400
        
        # Default sort by due_date
        query = query.order_by(AccruedExpense.due_date)
        
        # Apply pagination
        result = paginate(query, args.get('page', 1), args.get('per_page', 10), accrued_expense_list_schema)
        
        return result, 200
    
    @jwt_required()
    @api.expect(accrued_expense_model)
    @api.response(201, 'Accrued expense created successfully')
    @api.response(400, 'Validation error')
    def post(self):
        """Create a new accrued expense"""
        try:
            accrued_expense_data = request.json
            
            # Validate and deserialize input
            accrued_expense = accrued_expense_schema.load(accrued_expense_data)
            
            # Add to database
            db.session.add(accrued_expense)
            db.session.commit()
            
            return {'data': accrued_expense_schema.dump(accrued_expense)}, 201
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating accrued expense: {str(e)}")
            return {'error': str(e)}, 400

@api.route('/accrued/<int:id>')
class AccruedExpenseDetail(Resource):
    @jwt_required()
    @api.response(200, 'Success')
    @api.response(404, 'Accrued expense not found')
    def get(self, id):
        """Get an accrued expense by ID"""
        accrued_expense = AccruedExpense.query.get_or_404(id)
        return {'data': accrued_expense_schema.dump(accrued_expense)}, 200
    
    @jwt_required()
    @api.expect(accrued_expense_model)
    @api.response(200, 'Accrued expense updated successfully')
    @api.response(404, 'Accrued expense not found')
    @api.response(400, 'Validation error')
    def put(self, id):
        """Update an accrued expense"""
        try:
            accrued_expense = AccruedExpense.query.get_or_404(id)
            accrued_expense_data = request.json
            
            # Update accrued expense with new data
            for key, value in accrued_expense_data.items():
                if hasattr(accrued_expense, key):
                    setattr(accrued_expense, key, value)
            
            db.session.commit()
            
            return {'data': accrued_expense_schema.dump(accrued_expense)}, 200
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating accrued expense: {str(e)}")
            return {'error': str(e)}, 400
    
    @jwt_required()
    @api.response(200, 'Accrued expense deleted successfully')
    @api.response(404, 'Accrued expense not found')
    def delete(self, id):
        """Delete an accrued expense"""
        accrued_expense = AccruedExpense.query.get_or_404(id)
        
        try:
            # Delete receipt file if exists
            if accrued_expense.receipt_path:
                file_path = get_file_path(accrued_expense.receipt_path)
                if os.path.exists(file_path):
                    os.remove(file_path)
            
            db.session.delete(accrued_expense)
            db.session.commit()
            
            return {'message': 'Accrued expense deleted'}, 200
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error deleting accrued expense: {str(e)}")
            return {'error': str(e)}, 400

@api.route('/accrued/overdue')
class OverdueAccruedExpenses(Resource):
    @jwt_required()
    @api.expect(reqparse.RequestParser().add_argument('currency', type=str, help='Currency for conversion'))
    @api.response(200, 'Success')
    def get(self):
        """Get overdue accrued expenses"""
        args = reqparse.RequestParser().add_argument('currency', type=str).parse_args()
        
        today = date.today()
        
        # Get all overdue accrued expenses
        overdue_expenses = AccruedExpense.query.filter(
            AccruedExpense.due_date < today,
            AccruedExpense.status == AccruedExpenseStatus.PENDIENTE
        ).order_by(AccruedExpense.due_date).all()
        
        # Update status to 'vencido'
        for expense in overdue_expenses:
            expense.status = AccruedExpenseStatus.VENCIDO
        
        db.session.commit()
        
        # Calculate total
        total_cop = sum(float(e.amount) for e in overdue_expenses if e.currency == Currency.COP)
        total_usd = sum(float(e.amount) for e in overdue_expenses if e.currency == Currency.USD)
        
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
            'data': accrued_expense_list_schema.dump(overdue_expenses),
            'total': total
        }, 200

@api.route('/accrued/upcoming')
class UpcomingAccruedExpenses(Resource):
    @jwt_required()
    @api.expect(reqparse.RequestParser()
                .add_argument('days', type=int, default=30, help='Number of days to look ahead')
                .add_argument('currency', type=str, help='Currency for conversion'))
    @api.response(200, 'Success')
    def get(self):
        """Get upcoming accrued expenses within specified days"""
        parser = reqparse.RequestParser()
        parser.add_argument('days', type=int, default=30)
        parser.add_argument('currency', type=str)
        args = parser.parse_args()
        
        days = args.get('days', 30)
        today = date.today()
        end_date = today + timedelta(days=days)
        
        # Get all upcoming accrued expenses
        upcoming_expenses = AccruedExpense.query.filter(
            AccruedExpense.due_date >= today,
            AccruedExpense.due_date <= end_date,
            AccruedExpense.status == AccruedExpenseStatus.PENDIENTE
        ).order_by(AccruedExpense.due_date).all()
        
        # Calculate total
        total_cop = sum(float(e.amount) for e in upcoming_expenses if e.currency == Currency.COP)
        total_usd = sum(float(e.amount) for e in upcoming_expenses if e.currency == Currency.USD)
        
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
            'data': accrued_expense_list_schema.dump(upcoming_expenses),
            'total': total
        }, 200

@api.route('/categories')
class ExpenseCategories(Resource):
    @jwt_required()
    @api.response(200, 'Success')
    def get(self):
        """Get all expense categories with their totals"""
        # Get distinct categories from expenses
        categories_query = db.session.query(
            Expense.category,
            func.sum(Expense.amount).label('amount'),
            Expense.currency
        ).group_by(
            Expense.category,
            Expense.currency
        ).all()
        
        # Process categories
        categories = {}
        
        for item in categories_query:
            category = item[0]
            amount = float(item[1])
            currency = item[2].value
            
            if category not in categories:
                categories[category] = {'COP': 0, 'USD': 0}
                
            categories[category][currency] = amount
        
        # Format for response
        categories_data = [{'category': k, **v} for k, v in categories.items()]
        
        return {'data': categories_data}, 200

# Routes for the blueprint
routes = [
    ExpenseList,
    ExpenseDetail,
    RecurringExpenseList,
    RecurringExpenseDetail,
    GenerateAccruedExpenses,
    AccruedExpenseList,
    AccruedExpenseDetail,
    OverdueAccruedExpenses,
    UpcomingAccruedExpenses,
    ExpenseCategories
]
