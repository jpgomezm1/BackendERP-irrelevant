from flask import request, jsonify
from flask_restx import Namespace, Resource, fields, reqparse
from flask_jwt_extended import jwt_required
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from models.payment import Payment, PaymentStatus, Currency as PaymentCurrency
from models.client import Client
from models.project import Project, ProjectStatus
from models.income import Income, Currency as IncomeCurrency
from models.expense import Expense, AccruedExpense, Currency as ExpenseCurrency, AccruedExpenseStatus
from app import db
from utils.currency import convert_currency
from sqlalchemy import func, and_, extract, case
import calendar
import logging

# Setting up API namespace
api = Namespace('reports', description='Financial reports and analytics')

# Define parameter parsers
cash_flow_parser = reqparse.RequestParser()
cash_flow_parser.add_argument('period', type=str, default='month', help='Period for analysis (month, quarter, year)')
cash_flow_parser.add_argument('currency', type=str, default='COP', help='Currency for calculations (COP, USD)')
cash_flow_parser.add_argument('months', type=int, default=12, help='Number of months to include')

client_parser = reqparse.RequestParser()
client_parser.add_argument('client_id', type=int, help='Filter by client ID')
client_parser.add_argument('currency', type=str, default='COP', help='Currency for calculations (COP, USD)')
client_parser.add_argument('year', type=int, help='Filter by year')

profitability_parser = reqparse.RequestParser()
profitability_parser.add_argument('period', type=str, default='month', help='Period for analysis (month, quarter, year)')
profitability_parser.add_argument('currency', type=str, default='COP', help='Currency for calculations (COP, USD)')
profitability_parser.add_argument('year', type=int, help='Filter by year')

projection_parser = reqparse.RequestParser()
projection_parser.add_argument('months', type=int, default=12, help='Number of months to project')
projection_parser.add_argument('currency', type=str, default='COP', help='Currency for calculations (COP, USD)')

@api.route('/cash-flow')
class CashFlowReport(Resource):
    @jwt_required()
    @api.expect(cash_flow_parser)
    @api.response(200, 'Success')
    def get(self):
        """Generate cash flow report"""
        args = cash_flow_parser.parse_args()
        period = args.get('period', 'month')
        currency = args.get('currency', 'COP')
        months = args.get('months', 12)
        
        today = datetime.today()
        start_date = today - relativedelta(months=months)
        
        try:
            # Define date truncation based on period
            if period == 'month':
                date_trunc = func.date_trunc('month', Income.date)
                expense_date_trunc = func.date_trunc('month', Expense.date)
                format_str = '%Y-%m'
            elif period == 'quarter':
                date_trunc = func.date_trunc('quarter', Income.date)
                expense_date_trunc = func.date_trunc('quarter', Expense.date)
                format_str = '%Y-Q%q'  # Will need post-processing
            elif period == 'year':
                date_trunc = func.date_trunc('year', Income.date)
                expense_date_trunc = func.date_trunc('year', Expense.date)
                format_str = '%Y'
            else:
                return {'error': 'Invalid period. Use month, quarter, or year'}, 400
            
            # Query income data
            income_data = db.session.query(
                date_trunc.label('period'),
                func.sum(Income.amount).label('amount'),
                Income.currency
            ).filter(
                Income.date >= start_date.date()
            ).group_by(
                'period',
                Income.currency
            ).all()
            
            # Query expense data
            expense_data = db.session.query(
                expense_date_trunc.label('period'),
                func.sum(Expense.amount).label('amount'),
                Expense.currency
            ).filter(
                Expense.date >= start_date.date()
            ).group_by(
                'period',
                Expense.currency
            ).all()
            
            # Process data
            periods = {}
            
            # Process income data
            for item in income_data:
                period_date = item[0]
                amount = float(item[1])
                item_currency = item[2].value
                
                # Format period label
                if period == 'quarter':
                    quarter = (period_date.month - 1) // 3 + 1
                    label = f"{period_date.year}-Q{quarter}"
                else:
                    label = period_date.strftime(format_str)
                
                if label not in periods:
                    periods[label] = {
                        'income': {'COP': 0, 'USD': 0},
                        'expenses': {'COP': 0, 'USD': 0},
                        'net': {'COP': 0, 'USD': 0}
                    }
                
                # Add income
                periods[label]['income'][item_currency] += amount
                
                # Update net
                periods[label]['net'][item_currency] += amount
            
            # Process expense data
            for item in expense_data:
                period_date = item[0]
                amount = float(item[1])
                item_currency = item[2].value
                
                # Format period label
                if period == 'quarter':
                    quarter = (period_date.month - 1) // 3 + 1
                    label = f"{period_date.year}-Q{quarter}"
                else:
                    label = period_date.strftime(format_str)
                
                if label not in periods:
                    periods[label] = {
                        'income': {'COP': 0, 'USD': 0},
                        'expenses': {'COP': 0, 'USD': 0},
                        'net': {'COP': 0, 'USD': 0}
                    }
                
                # Add expenses
                periods[label]['expenses'][item_currency] += amount
                
                # Update net (subtract expenses)
                periods[label]['net'][item_currency] -= amount
            
            # Convert to target currency if specified
            if currency in ['COP', 'USD']:
                for label in periods:
                    # Convert income
                    source_currency = 'USD' if currency == 'COP' else 'COP'
                    periods[label]['income'][currency] += convert_currency(
                        periods[label]['income'][source_currency], source_currency, currency
                    )
                    periods[label]['income'] = {currency: periods[label]['income'][currency]}
                    
                    # Convert expenses
                    periods[label]['expenses'][currency] += convert_currency(
                        periods[label]['expenses'][source_currency], source_currency, currency
                    )
                    periods[label]['expenses'] = {currency: periods[label]['expenses'][currency]}
                    
                    # Convert net
                    periods[label]['net'][currency] += convert_currency(
                        periods[label]['net'][source_currency], source_currency, currency
                    )
                    periods[label]['net'] = {currency: periods[label]['net'][currency]}
            
            # Format for response
            cash_flow_data = []
            for label, data in sorted(periods.items()):
                entry = {'period': label}
                entry.update(data)
                cash_flow_data.append(entry)
            
            # Calculate summary
            total_income = {'COP': 0, 'USD': 0}
            total_expenses = {'COP': 0, 'USD': 0}
            total_net = {'COP': 0, 'USD': 0}
            
            for period_data in cash_flow_data:
                for curr in ['COP', 'USD']:
                    if curr in period_data['income']:
                        total_income[curr] += period_data['income'][curr]
                    if curr in period_data['expenses']:
                        total_expenses[curr] += period_data['expenses'][curr]
                    if curr in period_data['net']:
                        total_net[curr] += period_data['net'][curr]
            
            # Convert summary to target currency if specified
            if currency in ['COP', 'USD']:
                source_currency = 'USD' if currency == 'COP' else 'COP'
                total_income = {currency: total_income[currency] + convert_currency(total_income[source_currency], source_currency, currency)}
                total_expenses = {currency: total_expenses[currency] + convert_currency(total_expenses[source_currency], source_currency, currency)}
                total_net = {currency: total_net[currency] + convert_currency(total_net[source_currency], source_currency, currency)}
            
            return {
                'data': cash_flow_data,
                'summary': {
                    'total_income': total_income,
                    'total_expenses': total_expenses,
                    'total_net': total_net
                }
            }, 200
            
        except Exception as e:
            logging.error(f"Error generating cash flow report: {str(e)}")
            return {'error': str(e)}, 500

@api.route('/client-analytics')
class ClientAnalyticsReport(Resource):
    @jwt_required()
    @api.expect(client_parser)
    @api.response(200, 'Success')
    def get(self):
        """Generate client analytics report"""
        args = client_parser.parse_args()
        client_id = args.get('client_id')
        currency = args.get('currency', 'COP')
        year = args.get('year', datetime.today().year)
        
        try:
            # Get all active clients if no client_id specified
            if client_id:
                clients = [Client.query.get_or_404(client_id)]
            else:
                clients = Client.query.filter_by(status='Activo').all()
                
            client_data = []
            
            for client in clients:
                # Get projects for client
                projects = Project.query.filter_by(client_id=client.id).all()
                project_ids = [p.id for p in projects]
                
                if not project_ids:
                    continue
                
                # Get payments for all projects
                year_start = datetime(year, 1, 1).date()
                year_end = datetime(year, 12, 31).date()
                
                payments = Payment.query.filter(
                    Payment.project_id.in_(project_ids),
                    Payment.date >= year_start,
                    Payment.date <= year_end
                ).all()
                
                # Calculate totals
                total_billed = {'COP': 0, 'USD': 0}
                total_paid = {'COP': 0, 'USD': 0}
                total_pending = {'COP': 0, 'USD': 0}
                total_overdue = {'COP': 0, 'USD': 0}
                
                for payment in payments:
                    payment_currency = payment.currency.value
                    amount = float(payment.amount)
                    
                    # Add to total billed
                    total_billed[payment_currency] += amount
                    
                    # Add to appropriate category based on status
                    if payment.status == PaymentStatus.PAGADO:
                        total_paid[payment_currency] += amount
                    elif payment.status == PaymentStatus.PENDIENTE:
                        if payment.date <= date.today():
                            total_overdue[payment_currency] += amount
                        else:
                            total_pending[payment_currency] += amount
                    elif payment.status == PaymentStatus.VENCIDO:
                        total_overdue[payment_currency] += amount
                
                # Convert to target currency if specified
                if currency in ['COP', 'USD']:
                    source_currency = 'USD' if currency == 'COP' else 'COP'
                    
                    total_billed[currency] += convert_currency(total_billed[source_currency], source_currency, currency)
                    total_billed = {currency: total_billed[currency]}
                    
                    total_paid[currency] += convert_currency(total_paid[source_currency], source_currency, currency)
                    total_paid = {currency: total_paid[currency]}
                    
                    total_pending[currency] += convert_currency(total_pending[source_currency], source_currency, currency)
                    total_pending = {currency: total_pending[currency]}
                    
                    total_overdue[currency] += convert_currency(total_overdue[source_currency], source_currency, currency)
                    total_overdue = {currency: total_overdue[currency]}
                
                # Get monthly distribution
                monthly_data = {}
                for month in range(1, 13):
                    month_start = datetime(year, month, 1).date()
                    month_end = datetime(year, month, calendar.monthrange(year, month)[1]).date()
                    
                    month_payments = [p for p in payments if month_start <= p.date <= month_end]
                    
                    month_total = {'COP': 0, 'USD': 0}
                    for payment in month_payments:
                        month_total[payment.currency.value] += float(payment.amount)
                    
                    # Convert to target currency if specified
                    if currency in ['COP', 'USD']:
                        source_currency = 'USD' if currency == 'COP' else 'COP'
                        month_total[currency] += convert_currency(month_total[source_currency], source_currency, currency)
                        month_total = {currency: month_total[currency]}
                    
                    monthly_data[f"{year}-{month:02d}"] = month_total
                
                client_data.append({
                    'client_id': client.id,
                    'client_name': client.name,
                    'total_billed': total_billed,
                    'total_paid': total_paid,
                    'total_pending': total_pending,
                    'total_overdue': total_overdue,
                    'monthly_distribution': monthly_data,
                    'project_count': len(projects),
                    'active_project_count': len([p for p in projects if p.status == ProjectStatus.ACTIVO])
                })
            
            return {'data': client_data}, 200
            
        except Exception as e:
            logging.error(f"Error generating client analytics report: {str(e)}")
            return {'error': str(e)}, 500

@api.route('/profitability')
class ProfitabilityReport(Resource):
    @jwt_required()
    @api.expect(profitability_parser)
    @api.response(200, 'Success')
    def get(self):
        """Generate profitability report"""
        args = profitability_parser.parse_args()
        period = args.get('period', 'month')
        currency = args.get('currency', 'COP')
        year = args.get('year', datetime.today().year)
        
        try:
            # Define date range
            year_start = datetime(year, 1, 1).date()
            year_end = datetime(year, 12, 31).date()
            
            # Define date truncation based on period
            if period == 'month':
                income_date_trunc = func.date_trunc('month', Income.date)
                expense_date_trunc = func.date_trunc('month', Expense.date)
                format_str = '%Y-%m'
            elif period == 'quarter':
                income_date_trunc = func.date_trunc('quarter', Income.date)
                expense_date_trunc = func.date_trunc('quarter', Expense.date)
                format_str = '%Y-Q%q'  # Will need post-processing
            elif period == 'year':
                income_date_trunc = func.date_trunc('year', Income.date)
                expense_date_trunc = func.date_trunc('year', Expense.date)
                format_str = '%Y'
            else:
                return {'error': 'Invalid period. Use month, quarter, or year'}, 400
            
            # Query income data
            income_data = db.session.query(
                income_date_trunc.label('period'),
                func.sum(Income.amount).label('amount'),
                Income.currency
            ).filter(
                Income.date >= year_start,
                Income.date <= year_end
            ).group_by(
                'period',
                Income.currency
            ).all()
            
            # Query expense data
            expense_data = db.session.query(
                expense_date_trunc.label('period'),
                func.sum(Expense.amount).label('amount'),
                Expense.currency
            ).filter(
                Expense.date >= year_start,
                Expense.date <= year_end
            ).group_by(
                'period',
                Expense.currency
            ).all()
            
            # Query client income data
            client_income_data = db.session.query(
                income_date_trunc.label('period'),
                func.sum(Income.amount).label('amount'),
                Income.currency
            ).filter(
                Income.date >= year_start,
                Income.date <= year_end,
                Income.client.isnot(None)
            ).group_by(
                'period',
                Income.currency
            ).all()
            
            # Process data
            periods = {}
            
            # Process income data
            for item in income_data:
                period_date = item[0]
                amount = float(item[1])
                item_currency = item[2].value
                
                # Format period label
                if period == 'quarter':
                    quarter = (period_date.month - 1) // 3 + 1
                    label = f"{period_date.year}-Q{quarter}"
                else:
                    label = period_date.strftime(format_str)
                
                if label not in periods:
                    periods[label] = {
                        'total_income': {'COP': 0, 'USD': 0},
                        'client_income': {'COP': 0, 'USD': 0},
                        'expenses': {'COP': 0, 'USD': 0},
                        'profit': {'COP': 0, 'USD': 0},
                        'margin': 0
                    }
                
                # Add income
                periods[label]['total_income'][item_currency] += amount
            
            # Process client income data
            for item in client_income_data:
                period_date = item[0]
                amount = float(item[1])
                item_currency = item[2].value
                
                # Format period label
                if period == 'quarter':
                    quarter = (period_date.month - 1) // 3 + 1
                    label = f"{period_date.year}-Q{quarter}"
                else:
                    label = period_date.strftime(format_str)
                
                if label not in periods:
                    periods[label] = {
                        'total_income': {'COP': 0, 'USD': 0},
                        'client_income': {'COP': 0, 'USD': 0},
                        'expenses': {'COP': 0, 'USD': 0},
                        'profit': {'COP': 0, 'USD': 0},
                        'margin': 0
                    }
                
                # Add client income
                periods[label]['client_income'][item_currency] += amount
            
            # Process expense data
            for item in expense_data:
                period_date = item[0]
                amount = float(item[1])
                item_currency = item[2].value
                
                # Format period label
                if period == 'quarter':
                    quarter = (period_date.month - 1) // 3 + 1
                    label = f"{period_date.year}-Q{quarter}"
                else:
                    label = period_date.strftime(format_str)
                
                if label not in periods:
                    periods[label] = {
                        'total_income': {'COP': 0, 'USD': 0},
                        'client_income': {'COP': 0, 'USD': 0},
                        'expenses': {'COP': 0, 'USD': 0},
                        'profit': {'COP': 0, 'USD': 0},
                        'margin': 0
                    }
                
                # Add expenses
                periods[label]['expenses'][item_currency] += amount
            
            # Calculate profit and margin
            for label in periods:
                for curr in ['COP', 'USD']:
                    # Calculate profit
                    periods[label]['profit'][curr] = periods[label]['total_income'][curr] - periods[label]['expenses'][curr]
                
                # Convert to target currency if specified
                if currency in ['COP', 'USD']:
                    source_currency = 'USD' if currency == 'COP' else 'COP'
                    
                    # Convert total income
                    periods[label]['total_income'][currency] += convert_currency(
                        periods[label]['total_income'][source_currency], source_currency, currency
                    )
                    periods[label]['total_income'] = {currency: periods[label]['total_income'][currency]}
                    
                    # Convert client income
                    periods[label]['client_income'][currency] += convert_currency(
                        periods[label]['client_income'][source_currency], source_currency, currency
                    )
                    periods[label]['client_income'] = {currency: periods[label]['client_income'][currency]}
                    
                    # Convert expenses
                    periods[label]['expenses'][currency] += convert_currency(
                        periods[label]['expenses'][source_currency], source_currency, currency
                    )
                    periods[label]['expenses'] = {currency: periods[label]['expenses'][currency]}
                    
                    # Convert profit
                    periods[label]['profit'][currency] += convert_currency(
                        periods[label]['profit'][source_currency], source_currency, currency
                    )
                    periods[label]['profit'] = {currency: periods[label]['profit'][currency]}
                    
                    # Calculate margin
                    total_income = periods[label]['total_income'][currency]
                    periods[label]['margin'] = ((total_income - periods[label]['expenses'][currency]) / total_income * 100) if total_income > 0 else 0
                else:
                    # Calculate margin using COP
                    total_income_cop = periods[label]['total_income']['COP']
                    if total_income_cop > 0:
                        periods[label]['margin'] = ((total_income_cop - periods[label]['expenses']['COP']) / total_income_cop * 100)
                    else:
                        total_income_usd = periods[label]['total_income']['USD']
                        if total_income_usd > 0:
                            # Convert to COP for calculation
                            total_income_cop = convert_currency(total_income_usd, 'USD', 'COP')
                            expenses_cop = periods[label]['expenses']['COP'] + convert_currency(periods[label]['expenses']['USD'], 'USD', 'COP')
                            periods[label]['margin'] = ((total_income_cop - expenses_cop) / total_income_cop * 100)
                        else:
                            periods[label]['margin'] = 0
            
            # Format for response
            profitability_data = []
            for label, data in sorted(periods.items()):
                entry = {'period': label}
                entry.update(data)
                profitability_data.append(entry)
            
            # Calculate yearly summary
            yearly_total_income = {'COP': 0, 'USD': 0}
            yearly_client_income = {'COP': 0, 'USD': 0}
            yearly_expenses = {'COP': 0, 'USD': 0}
            yearly_profit = {'COP': 0, 'USD': 0}
            
            for period_data in profitability_data:
                if currency in ['COP', 'USD']:
                    yearly_total_income[currency] += period_data['total_income'][currency]
                    yearly_client_income[currency] += period_data['client_income'][currency]
                    yearly_expenses[currency] += period_data['expenses'][currency]
                    yearly_profit[currency] += period_data['profit'][currency]
                else:
                    for curr in ['COP', 'USD']:
                        yearly_total_income[curr] += period_data['total_income'][curr]
                        yearly_client_income[curr] += period_data['client_income'][curr]
                        yearly_expenses[curr] += period_data['expenses'][curr]
                        yearly_profit[curr] += period_data['profit'][curr]
            
            # Calculate yearly margin
            yearly_margin = 0
            if currency in ['COP', 'USD']:
                if yearly_total_income[currency] > 0:
                    yearly_margin = (yearly_profit[currency] / yearly_total_income[currency]) * 100
            else:
                # Use COP for calculation
                if yearly_total_income['COP'] > 0:
                    yearly_margin = (yearly_profit['COP'] / yearly_total_income['COP']) * 100
                else:
                    # Convert USD to COP for calculation
                    total_income_cop = convert_currency(yearly_total_income['USD'], 'USD', 'COP')
                    if total_income_cop > 0:
                        profit_cop = convert_currency(yearly_profit['USD'], 'USD', 'COP')
                        yearly_margin = (profit_cop / total_income_cop) * 100
            
            # Calculate client income percentage
            client_income_pct = 0
            if currency in ['COP', 'USD']:
                if yearly_total_income[currency] > 0:
                    client_income_pct = (yearly_client_income[currency] / yearly_total_income[currency]) * 100
            else:
                # Use COP for calculation
                if yearly_total_income['COP'] > 0:
                    client_income_pct = (yearly_client_income['COP'] / yearly_total_income['COP']) * 100
                else:
                    # Convert USD to COP for calculation
                    total_income_cop = convert_currency(yearly_total_income['USD'], 'USD', 'COP')
                    if total_income_cop > 0:
                        client_income_cop = convert_currency(yearly_client_income['USD'], 'USD', 'COP')
                        client_income_pct = (client_income_cop / total_income_cop) * 100
            
            return {
                'data': profitability_data,
                'summary': {
                    'total_income': yearly_total_income,
                    'client_income': yearly_client_income,
                    'expenses': yearly_expenses,
                    'profit': yearly_profit,
                    'margin': yearly_margin,
                    'client_income_percentage': client_income_pct
                }
            }, 200
            
        except Exception as e:
            logging.error(f"Error generating profitability report: {str(e)}")
            return {'error': str(e)}, 500

@api.route('/financial-projection')
class FinancialProjectionReport(Resource):
    @jwt_required()
    @api.expect(projection_parser)
    @api.response(200, 'Success')
    def get(self):
        """Generate financial projection report"""
        args = projection_parser.parse_args()
        months = args.get('months', 12)
        currency = args.get('currency', 'COP')
        
        try:
            today = date.today()
            end_date = today + relativedelta(months=months)
            
            # Get upcoming payments
            payments = Payment.query.filter(
                Payment.date >= today,
                Payment.date <= end_date,
                Payment.status == PaymentStatus.PENDIENTE
            ).order_by(Payment.date).all()
            
            # Get upcoming accrued expenses
            expenses = AccruedExpense.query.filter(
                AccruedExpense.due_date >= today,
                AccruedExpense.due_date <= end_date,
                AccruedExpense.status == AccruedExpenseStatus.PENDIENTE
            ).order_by(AccruedExpense.due_date).all()
            
            # Process by month
            projection = {}
            
            for i in range(months):
                month_date = today + relativedelta(months=i)
                month_start = date(month_date.year, month_date.month, 1)
                month_end = date(month_date.year, month_date.month, 
                               calendar.monthrange(month_date.year, month_date.month)[1])
                
                month_label = month_start.strftime('%Y-%m')
                
                # Initialize month data
                projection[month_label] = {
                    'income': {'COP': 0, 'USD': 0},
                    'expenses': {'COP': 0, 'USD': 0},
                    'net': {'COP': 0, 'USD': 0},
                    'details': {
                        'payments': [],
                        'expenses': []
                    }
                }
                
                # Add payments for the month
                month_payments = [p for p in payments if month_start <= p.date <= month_end]
                for payment in month_payments:
                    payment_currency = payment.currency.value
                    amount = float(payment.amount)
                    
                    projection[month_label]['income'][payment_currency] += amount
                    projection[month_label]['net'][payment_currency] += amount
                    
                    # Add to details
                    projection[month_label]['details']['payments'].append({
                        'id': payment.id,
                        'client_id': payment.client_id,
                        'project_id': payment.project_id,
                        'date': payment.date.isoformat(),
                        'amount': amount,
                        'currency': payment_currency,
                        'type': payment.type.value,
                        'invoice_number': payment.invoice_number
                    })
                
                # Add expenses for the month
                month_expenses = [e for e in expenses if month_start <= e.due_date <= month_end]
                for expense in month_expenses:
                    expense_currency = expense.currency.value
                    amount = float(expense.amount)
                    
                    projection[month_label]['expenses'][expense_currency] += amount
                    projection[month_label]['net'][expense_currency] -= amount
                    
                    # Add to details
                    projection[month_label]['details']['expenses'].append({
                        'id': expense.id,
                        'description': expense.description,
                        'due_date': expense.due_date.isoformat(),
                        'amount': amount,
                        'currency': expense_currency,
                        'category': expense.category,
                        'is_recurring': expense.is_recurring
                    })
                
                # Convert to target currency if specified
                if currency in ['COP', 'USD']:
                    source_currency = 'USD' if currency == 'COP' else 'COP'
                    
                    # Convert income
                    projection[month_label]['income'][currency] += convert_currency(
                        projection[month_label]['income'][source_currency], source_currency, currency
                    )
                    projection[month_label]['income'] = {currency: projection[month_label]['income'][currency]}
                    
                    # Convert expenses
                    projection[month_label]['expenses'][currency] += convert_currency(
                        projection[month_label]['expenses'][source_currency], source_currency, currency
                    )
                    projection[month_label]['expenses'] = {currency: projection[month_label]['expenses'][currency]}
                    
                    # Convert net
                    projection[month_label]['net'][currency] += convert_currency(
                        projection[month_label]['net'][source_currency], source_currency, currency
                    )
                    projection[month_label]['net'] = {currency: projection[month_label]['net'][currency]}
            
            # Format for response
            projection_data = []
            running_balance = {'COP': 0, 'USD': 0}
            
            for month_label in sorted(projection.keys()):
                month_data = projection[month_label]
                
                # Update running balance
                if currency in ['COP', 'USD']:
                    running_balance[currency] += month_data['net'][currency]
                    month_data['running_balance'] = {currency: running_balance[currency]}
                else:
                    for curr in ['COP', 'USD']:
                        running_balance[curr] += month_data['net'][curr]
                    month_data['running_balance'] = running_balance.copy()
                
                projection_data.append({
                    'month': month_label,
                    **month_data
                })
            
            # Calculate summary
            total_projected_income = {'COP': 0, 'USD': 0}
            total_projected_expenses = {'COP': 0, 'USD': 0}
            total_projected_net = {'COP': 0, 'USD': 0}
            
            for month_data in projection_data:
                if currency in ['COP', 'USD']:
                    total_projected_income[currency] += month_data['income'][currency]
                    total_projected_expenses[currency] += month_data['expenses'][currency]
                    total_projected_net[currency] += month_data['net'][currency]
                else:
                    for curr in ['COP', 'USD']:
                        total_projected_income[curr] += month_data['income'][curr]
                        total_projected_expenses[curr] += month_data['expenses'][curr]
                        total_projected_net[curr] += month_data['net'][curr]
            
            return {
                'data': projection_data,
                'summary': {
                    'total_projected_income': total_projected_income,
                    'total_projected_expenses': total_projected_expenses,
                    'total_projected_net': total_projected_net,
                    'final_balance': running_balance
                }
            }, 200
            
        except Exception as e:
            logging.error(f"Error generating financial projection: {str(e)}")
            return {'error': str(e)}, 500

@api.route('/dashboard')
class DashboardReport(Resource):
    @jwt_required()
    @api.expect(reqparse.RequestParser().add_argument('currency', type=str, default='COP'))
    @api.response(200, 'Success')
    def get(self):
        """Generate dashboard summary data"""
        args = reqparse.RequestParser().add_argument('currency', type=str, default='COP').parse_args()
        currency = args.get('currency', 'COP')
        
        try:
            today = date.today()
            month_start = date(today.year, today.month, 1)
            month_end = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
            
            # Get active clients count
            active_clients = Client.query.filter_by(status='Activo').count()
            
            # Get active projects count
            active_projects = Project.query.filter_by(status='Activo').count()
            
            # Get overdue payments
            overdue_payments = Payment.query.filter(
                Payment.date < today,
                Payment.status != PaymentStatus.PAGADO
            ).all()
            
            overdue_amount = {'COP': 0, 'USD': 0}
            for payment in overdue_payments:
                overdue_amount[payment.currency.value] += float(payment.amount)
            
            # Get upcoming payments (next 30 days)
            upcoming_date = today + timedelta(days=30)
            upcoming_payments = Payment.query.filter(
                Payment.date >= today,
                Payment.date <= upcoming_date,
                Payment.status == PaymentStatus.PENDIENTE
            ).all()
            
            upcoming_amount = {'COP': 0, 'USD': 0}
            for payment in upcoming_payments:
                upcoming_amount[payment.currency.value] += float(payment.amount)
            
            # Get current month income
            current_month_income = db.session.query(
                func.sum(Income.amount).label('amount'),
                Income.currency
            ).filter(
                Income.date >= month_start,
                Income.date <= today
            ).group_by(
                Income.currency
            ).all()
            
            month_income = {'COP': 0, 'USD': 0}
            for item in current_month_income:
                amount = float(item[0]) if item[0] else 0
                item_currency = item[1].value
                month_income[item_currency] = amount
            
            # Get current month expenses
            current_month_expenses = db.session.query(
                func.sum(Expense.amount).label('amount'),
                Expense.currency
            ).filter(
                Expense.date >= month_start,
                Expense.date <= today
            ).group_by(
                Expense.currency
            ).all()
            
            month_expenses = {'COP': 0, 'USD': 0}
            for item in current_month_expenses:
                amount = float(item[0]) if item[0] else 0
                item_currency = item[1].value
                month_expenses[item_currency] = amount
            
            # Convert to target currency if specified
            if currency in ['COP', 'USD']:
                source_currency = 'USD' if currency == 'COP' else 'COP'
                
                # Convert overdue amount
                overdue_amount[currency] += convert_currency(overdue_amount[source_currency], source_currency, currency)
                overdue_amount = {currency: overdue_amount[currency]}
                
                # Convert upcoming amount
                upcoming_amount[currency] += convert_currency(upcoming_amount[source_currency], source_currency, currency)
                upcoming_amount = {currency: upcoming_amount[currency]}
                
                # Convert month income
                month_income[currency] += convert_currency(month_income[source_currency], source_currency, currency)
                month_income = {currency: month_income[currency]}
                
                # Convert month expenses
                month_expenses[currency] += convert_currency(month_expenses[source_currency], source_currency, currency)
                month_expenses = {currency: month_expenses[currency]}
            
            # Calculate month net
            month_net = {}
            if currency in ['COP', 'USD']:
                month_net = {currency: month_income[currency] - month_expenses[currency]}
            else:
                month_net = {
                    'COP': month_income['COP'] - month_expenses['COP'],
                    'USD': month_income['USD'] - month_expenses['USD']
                }
            
            return {
                'active_clients': active_clients,
                'active_projects': active_projects,
                'overdue_payments': {
                    'count': len(overdue_payments),
                    'amount': overdue_amount
                },
                'upcoming_payments': {
                    'count': len(upcoming_payments),
                    'amount': upcoming_amount
                },
                'current_month': {
                    'income': month_income,
                    'expenses': month_expenses,
                    'net': month_net
                }
            }, 200
            
        except Exception as e:
            logging.error(f"Error generating dashboard data: {str(e)}")
            return {'error': str(e)}, 500

# Routes for the blueprint
routes = [
    CashFlowReport,
    ClientAnalyticsReport,
    ProfitabilityReport,
    FinancialProjectionReport,
    DashboardReport
]
