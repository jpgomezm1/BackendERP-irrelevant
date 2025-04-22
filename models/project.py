import datetime
import enum
from app import db
from sqlalchemy.orm import foreign

class ProjectStatus(enum.Enum):
    ACTIVO = 'Activo'
    PAUSADO = 'Pausado'
    FINALIZADO = 'Finalizado'
    CANCELADO = 'Cancelado'

class PaymentPlanType(enum.Enum):
    FEE_UNICO = 'Fee único'
    FEE_POR_CUOTAS = 'Fee por cuotas'
    SUSCRIPCION_PERIODICA = 'Suscripción periódica'
    MIXTO = 'Mixto'

class Currency(enum.Enum):
    COP = 'COP'
    USD = 'USD'

class FrequencyType(enum.Enum):
    SEMANAL = 'Semanal'
    QUINCENAL = 'Quincenal'
    MENSUAL = 'Mensual'
    BIMENSUAL = 'Bimensual'
    TRIMESTRAL = 'Trimestral'
    SEMESTRAL = 'Semestral'
    ANUAL = 'Anual'

class Project(db.Model):
    __tablename__ = 'projects'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date)
    status = db.Column(db.Enum(ProjectStatus), nullable=False, default=ProjectStatus.ACTIVO)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow,
                          onupdate=datetime.datetime.utcnow)
    
    # Relationships
    client = db.relationship('Client', back_populates='projects')
    payment_plan = db.relationship('PaymentPlan', backref='project', uselist=False, cascade='all, delete-orphan')
    payments = db.relationship('Payment', back_populates='project', cascade='all, delete-orphan')
    documents = db.relationship('Document', 
                               primaryjoin="and_(Document.entity_type=='project', "
                                          "foreign(Document.entity_id)==Project.id)",
                               cascade='all, delete-orphan',
                               viewonly=True)
    
    def __repr__(self):
        return f'<Project {self.name} - Client {self.client_id}>'

class PaymentPlan(db.Model):
    __tablename__ = 'payment_plans'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), unique=True, nullable=False)
    type = db.Column(db.Enum(PaymentPlanType), nullable=False)
    implementation_fee_total = db.Column(db.Numeric(12, 2))
    implementation_fee_currency = db.Column(db.Enum(Currency))
    implementation_fee_installments = db.Column(db.Integer, default=1)
    recurring_fee_amount = db.Column(db.Numeric(12, 2))
    recurring_fee_currency = db.Column(db.Enum(Currency))
    recurring_fee_frequency = db.Column(db.Enum(FrequencyType))
    recurring_fee_day_of_charge = db.Column(db.Integer)
    recurring_fee_grace_periods = db.Column(db.Integer, default=0)
    recurring_fee_discount_periods = db.Column(db.Integer, default=0)
    recurring_fee_discount_percentage = db.Column(db.Numeric(5, 2), default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow,
                          onupdate=datetime.datetime.utcnow)
    
    def __repr__(self):
        return f'<PaymentPlan for Project {self.project_id}>'
