import datetime
import enum
from app import db

class Currency(enum.Enum):
    COP = 'COP'
    USD = 'USD'

class FrequencyType(enum.Enum):
    DIARIA = 'Diaria'
    SEMANAL = 'Semanal'
    QUINCENAL = 'Quincenal'
    MENSUAL = 'Mensual'
    BIMENSUAL = 'Bimensual'
    TRIMESTRAL = 'Trimestral'
    SEMESTRAL = 'Semestral'
    ANUAL = 'Anual'

class RecurringExpenseStatus(enum.Enum):
    ACTIVO = 'Activo'
    PAUSADO = 'Pausado'

class AccruedExpenseStatus(enum.Enum):
    PAGADO = 'pagado'
    PENDIENTE = 'pendiente'
    VENCIDO = 'vencido'

class Expense(db.Model):
    __tablename__ = 'expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(255), nullable=False)
    date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.Enum(Currency), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    payment_method = db.Column(db.String(100), nullable=False)
    receipt_path = db.Column(db.String(255))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow,
                          onupdate=datetime.datetime.utcnow)
    
    def __repr__(self):
        return f'<Expense {self.id} - {self.amount} {self.currency.value} - {self.description}>'

class RecurringExpense(db.Model):
    __tablename__ = 'recurring_expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(255), nullable=False)
    frequency = db.Column(db.Enum(FrequencyType), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.Enum(Currency), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    payment_method = db.Column(db.String(100), nullable=False)
    status = db.Column(db.Enum(RecurringExpenseStatus), nullable=False, default=RecurringExpenseStatus.ACTIVO)
    next_payment = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow,
                          onupdate=datetime.datetime.utcnow)
    
    # Relationships
    accrued_expenses = db.relationship('AccruedExpense', backref='recurring_expense')
    
    def __repr__(self):
        return f'<RecurringExpense {self.id} - {self.amount} {self.currency.value} - {self.description}>'

class AccruedExpense(db.Model):
    __tablename__ = 'accrued_expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(255), nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.Enum(Currency), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    payment_method = db.Column(db.String(100), nullable=False)
    status = db.Column(db.Enum(AccruedExpenseStatus), nullable=False, default=AccruedExpenseStatus.PENDIENTE)
    receipt_path = db.Column(db.String(255))
    is_recurring = db.Column(db.Boolean, default=False)
    recurring_id = db.Column(db.Integer, db.ForeignKey('recurring_expenses.id', ondelete='SET NULL'))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow,
                          onupdate=datetime.datetime.utcnow)
    
    def __repr__(self):
        return f'<AccruedExpense {self.id} - {self.amount} {self.currency.value} - {self.description}>'
