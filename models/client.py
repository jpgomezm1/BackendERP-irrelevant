import datetime
import enum
from app import db
from sqlalchemy.orm import foreign

class ClientStatus(enum.Enum):
    ACTIVO = 'Activo'
    PAUSADO = 'Pausado'
    TERMINADO = 'Terminado'

class Client(db.Model):
    __tablename__ = 'clients'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    contact_name = db.Column(db.String(120))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(50))
    address = db.Column(db.String(200))
    tax_id = db.Column(db.String(50))  # NIT/ID tributario
    start_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.Enum(ClientStatus), nullable=False, default=ClientStatus.ACTIVO)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow,
                          onupdate=datetime.datetime.utcnow)
    
    # Relationships
    projects = db.relationship('Project', back_populates='client', cascade='all, delete-orphan')
    documents = db.relationship('Document', 
                               primaryjoin="and_(Document.entity_type=='client', "
                                          "foreign(Document.entity_id)==Client.id)",
                               cascade='all, delete-orphan',
                               viewonly=True)
    
    def __repr__(self):
        return f'<Client {self.name}>'
