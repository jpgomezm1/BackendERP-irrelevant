from flask import Blueprint

# Create blueprint objects for each API section
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')
clients_bp = Blueprint('clients', __name__, url_prefix='/api/clients')
projects_bp = Blueprint('projects', __name__, url_prefix='/api/projects')
payments_bp = Blueprint('payments', __name__, url_prefix='/api/payments')
documents_bp = Blueprint('documents', __name__, url_prefix='/api/documents')
incomes_bp = Blueprint('incomes', __name__, url_prefix='/api/incomes')
expenses_bp = Blueprint('expenses', __name__, url_prefix='/api/expenses')
reports_bp = Blueprint('reports', __name__, url_prefix='/api/reports')
