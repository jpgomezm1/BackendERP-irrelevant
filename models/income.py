import datetime
import enum
from app import db

class Currency(enum.Enum):
    COP = 'COP'
    USD = 'USD'

class Income(db.Model):
    __tablename__ = 'incomes'
    
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(255), nullable=False)
    date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.Enum(Currency), nullable=False)
    type = db.Column(db.String(100), nullable=False)  # 'Cliente', 'Aporte de socio', etc.
    client = db.Column(db.String(120))
    payment_method = db.Column(db.String(100), nullable=False)
    receipt_path = db.Column(db.String(255))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow,
                          onupdate=datetime.datetime.utcnow)
    
    def __repr__(self):
        return f'<Income {self.id} - {self.amount} {self.currency.value} - {self.description}>'
