import datetime
import enum
from app import db

class Currency(enum.Enum):
    COP = 'COP'
    USD = 'USD'

class PaymentStatus(enum.Enum):
    PAGADO = 'Pagado'
    PENDIENTE = 'Pendiente'
    VENCIDO = 'Vencido'

class PaymentType(enum.Enum):
    IMPLEMENTACION = 'Implementación'
    RECURRENTE = 'Recurrente'

class Payment(db.Model):
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.Enum(Currency), nullable=False)
    date = db.Column(db.Date, nullable=False)  # Fecha programada
    paid_date = db.Column(db.Date)  # Fecha real de pago
    status = db.Column(db.Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDIENTE)
    invoice_number = db.Column(db.String(100))
    invoice_url = db.Column(db.String(255))
    type = db.Column(db.Enum(PaymentType), nullable=False)
    installment_number = db.Column(db.Integer)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow,
                          onupdate=datetime.datetime.utcnow)
    
    # Relationships
    project = db.relationship('Project', back_populates='payments')
    client = db.relationship('Client')
    
    def __repr__(self):
        return f'<Payment {self.id} - {self.amount} {self.currency.value} - {self.status.value}>'
