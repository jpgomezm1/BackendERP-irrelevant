from app import ma
from models.document import Document, EntityType, DocumentType
from marshmallow import fields, validate, validates, ValidationError
from marshmallow_enum import EnumField

class DocumentSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Document
        load_instance = True
        include_fk = True
    
    entity_type = EnumField(EntityType, by_value=True)
    type = EnumField(DocumentType, by_value=True)
    
    # Fields for file upload, not part of model
    file = fields.Raw(metadata={'type': 'file'}, load_only=True)
    
    # Provide validation for fields
    name = fields.String(required=True, validate=validate.Length(min=1, max=255))
    entity_id = fields.Integer(required=True)

class DocumentListSchema(ma.Schema):
    id = fields.Integer()
    entity_type = EnumField(EntityType, by_value=True)
    entity_id = fields.Integer()
    name = fields.String()
    type = EnumField(DocumentType, by_value=True)
    upload_date = fields.DateTime()
    file_path = fields.String()
