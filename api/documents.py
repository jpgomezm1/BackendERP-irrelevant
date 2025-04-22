from flask import request, jsonify, send_file
from flask_restx import Namespace, Resource, fields, reqparse
from flask_jwt_extended import jwt_required
from werkzeug.datastructures import FileStorage
from models.document import Document, EntityType, DocumentType
from schemas.document import DocumentSchema, DocumentListSchema
from app import db
from utils.pagination import paginate
from utils.file_storage import save_file, get_file_path
import os
import logging

# Setting up API namespace
api = Namespace('documents', description='Document operations')

# Define models for swagger
document_model = api.model('Document', {
    'entity_type': fields.String(required=True, description='Entity type', enum=['client', 'project']),
    'entity_id': fields.Integer(required=True, description='Entity ID'),
    'name': fields.String(required=True, description='Document name'),
    'type': fields.String(required=True, description='Document type', 
                        enum=['RUT', 'Cámara de Comercio', 'NDA', 'Contrato', 'Factura', 'Otro'])
})

# Set up schemas
document_schema = DocumentSchema()
documents_schema = DocumentListSchema(many=True)

# Query parameter parser
document_parser = reqparse.RequestParser()
document_parser.add_argument('entity_type', type=str, help='Filter by entity type')
document_parser.add_argument('entity_id', type=int, help='Filter by entity ID')
document_parser.add_argument('type', type=str, help='Filter by document type')
document_parser.add_argument('page', type=int, help='Page number')
document_parser.add_argument('per_page', type=int, help='Items per page')

# Setup file upload parser
document_upload_parser = reqparse.RequestParser()
document_upload_parser.add_argument('entity_type', type=str, required=True, 
                                   help='Entity type (client or project)')
document_upload_parser.add_argument('entity_id', type=int, required=True, help='Entity ID')
document_upload_parser.add_argument('name', type=str, required=True, help='Document name')
document_upload_parser.add_argument('type', type=str, required=True, help='Document type')
document_upload_parser.add_argument('file', type=FileStorage, location='files', required=True, help='Document file')

@api.route('')
class DocumentList(Resource):
    @jwt_required()
    @api.expect(document_parser)
    @api.response(200, 'Success')
    def get(self):
        """Get all documents with optional filtering and pagination"""
        args = document_parser.parse_args()
        
        # Base query
        query = Document.query
        
        # Apply filters
        if args.get('entity_type'):
            query = query.filter(Document.entity_type == args['entity_type'])
            
        if args.get('entity_id'):
            query = query.filter(Document.entity_id == args['entity_id'])
            
        if args.get('type'):
            query = query.filter(Document.type == args['type'])
        
        # Apply pagination
        result = paginate(query, args.get('page', 1), args.get('per_page', 10), documents_schema)
        
        return result, 200
    
    @jwt_required()
    @api.expect(document_upload_parser)
    @api.response(201, 'Document uploaded successfully')
    @api.response(400, 'Invalid input')
    def post(self):
        """Upload a new document"""
        args = document_upload_parser.parse_args()
        
        try:
            # Save the file
            file = args['file']
            filename = save_file(file)
            
            # Create document record
            document = Document(
                entity_type=args['entity_type'],
                entity_id=args['entity_id'],
                name=args['name'],
                type=args['type'],
                file_path=filename
            )
            
            db.session.add(document)
            db.session.commit()
            
            return {'data': document_schema.dump(document)}, 201
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error uploading document: {str(e)}")
            return {'error': str(e)}, 400

@api.route('/<int:id>')
class DocumentDetail(Resource):
    @jwt_required()
    @api.response(200, 'Success')
    @api.response(404, 'Document not found')
    def get(self, id):
        """Get a document by ID"""
        document = Document.query.get_or_404(id)
        return {'data': document_schema.dump(document)}, 200
    
    @jwt_required()
    @api.response(200, 'Document deleted successfully')
    @api.response(404, 'Document not found')
    @api.response(400, 'Error deleting document')
    def delete(self, id):
        """Delete a document"""
        document = Document.query.get_or_404(id)
        
        try:
            # Delete file from storage
            file_path = get_file_path(document.file_path)
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # Delete record from database
            db.session.delete(document)
            db.session.commit()
            
            return {'message': 'Document deleted successfully'}, 200
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error deleting document: {str(e)}")
            return {'error': str(e)}, 400

@api.route('/<int:id>/download')
class DocumentDownload(Resource):
    @jwt_required()
    @api.response(200, 'Success')
    @api.response(404, 'Document not found')
    @api.response(400, 'Error downloading document')
    def get(self, id):
        """Download a document"""
        document = Document.query.get_or_404(id)
        
        try:
            file_path = get_file_path(document.file_path)
            if not os.path.exists(file_path):
                return {'error': 'Document file not found'}, 404
                
            return send_file(file_path, download_name=document.name, as_attachment=True)
            
        except Exception as e:
            logging.error(f"Error downloading document: {str(e)}")
            return {'error': str(e)}, 400

# Routes for the blueprint
routes = [
    DocumentList,
    DocumentDetail,
    DocumentDownload
]
