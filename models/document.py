import datetime
import enum
from app import db

class EntityType(enum.Enum):
    CLIENT = 'client'
    PROJECT = 'project'

class DocumentType(enum.Enum):
    RUT = 'RUT'
    CAMARA_COMERCIO = 'Cámara de Comercio'
    NDA = 'NDA'
    CONTRATO = 'Contrato'
    FACTURA = 'Factura'
    OTRO = 'Otro'

class Document(db.Model):
    __tablename__ = 'documents'
    
    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.Enum(EntityType), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.Enum(DocumentType), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow,
                          onupdate=datetime.datetime.utcnow)
    
    def __repr__(self):
        return f'<Document {self.name} - {self.type.value} - {self.entity_type.value} {self.entity_id}>'
