from flask import request, jsonify
from flask_restx import Namespace, Resource, fields, reqparse
from flask_jwt_extended import jwt_required, get_jwt
from werkzeug.datastructures import FileStorage
from models.client import Client
from models.document import Document, EntityType, DocumentType
from schemas.client import ClientSchema, ClientListSchema
from schemas.document import DocumentSchema, DocumentListSchema
from app import db
from utils.pagination import paginate
from utils.file_storage import save_file
import os
import logging

# Setting up API namespace
api = Namespace('clients', description='Client operations')

# Define models for swagger
client_model = api.model('Client', {
    'name': fields.String(required=True, description='Client name'),
    'contact_name': fields.String(description='Contact person name'),
    'email': fields.String(description='Client email'),
    'phone': fields.String(description='Client phone number'),
    'address': fields.String(description='Client address'),
    'tax_id': fields.String(description='Tax ID (NIT)'),
    'start_date': fields.Date(required=True, description='Client start date'),
    'status': fields.String(required=True, description='Client status', enum=['Activo', 'Pausado', 'Terminado']),
    'notes': fields.String(description='Additional notes')
})

# Set up schemas
client_schema = ClientSchema()
clients_schema = ClientSchema(many=True)
client_list_schema = ClientListSchema(many=True)
document_schema = DocumentSchema()
documents_schema = DocumentListSchema(many=True)

# Query parameter parser
client_parser = reqparse.RequestParser()
client_parser.add_argument('status', type=str, help='Filter by status')
client_parser.add_argument('sort', type=str, help='Sort field')
client_parser.add_argument('page', type=int, help='Page number')
client_parser.add_argument('per_page', type=int, help='Items per page')

# Setup file upload parser
document_upload_parser = reqparse.RequestParser()
document_upload_parser.add_argument('name', type=str, required=True, help='Document name')
document_upload_parser.add_argument('type', type=str, required=True, help='Document type')
document_upload_parser.add_argument('file', type=FileStorage, location='files', required=True, help='Document file')

@api.route('')
class ClientList(Resource):
    @jwt_required()
    @api.expect(client_parser)
    @api.response(200, 'Success')
    def get(self):
        """Get all clients with optional filtering and pagination"""
        args = client_parser.parse_args()
        
        # Base query
        query = Client.query
        
        # Apply filters
        if args.get('status'):
            query = query.filter(Client.status == args['status'])
        
        # Apply sorting
        if args.get('sort'):
            sort_field = args['sort']
            if hasattr(Client, sort_field):
                query = query.order_by(getattr(Client, sort_field))
        else:
            # Default sort by name
            query = query.order_by(Client.name)
        
        # Apply pagination
        result = paginate(query, args.get('page', 1), args.get('per_page', 10), client_list_schema)
        
        return result, 200
    
    @jwt_required()
    @api.expect(client_model)
    @api.response(201, 'Client created successfully')
    @api.response(400, 'Validation error')
    def post(self):
        """Create a new client"""
        try:
            client_data = request.json
            
            # Validate and deserialize input
            client = client_schema.load(client_data)
            
            # Add to database
            db.session.add(client)
            db.session.commit()
            
            return {'data': client_schema.dump(client)}, 201
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating client: {str(e)}")
            return {'error': str(e)}, 400

@api.route('/<int:id>')
class ClientDetail(Resource):
    @jwt_required()
    @api.response(200, 'Success')
    @api.response(404, 'Client not found')
    def get(self, id):
        """Get a client by ID"""
        client = Client.query.get_or_404(id)
        return {'data': client_schema.dump(client)}, 200
    
    @jwt_required()
    @api.expect(client_model)
    @api.response(200, 'Client updated successfully')
    @api.response(404, 'Client not found')
    @api.response(400, 'Validation error')
    def put(self, id):
        """Update a client"""
        try:
            client = Client.query.get_or_404(id)
            client_data = request.json
            
            # Update client with new data
            for key, value in client_data.items():
                if hasattr(client, key):
                    setattr(client, key, value)
            
            db.session.commit()
            
            return {'data': client_schema.dump(client)}, 200
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating client: {str(e)}")
            return {'error': str(e)}, 400
    
    @jwt_required()
    @api.response(200, 'Client deleted successfully')
    @api.response(404, 'Client not found')
    @api.response(409, 'Client has projects and cannot be deleted')
    def delete(self, id):
        """Delete a client"""
        client = Client.query.get_or_404(id)
        
        # Check if client has associated projects
        if client.projects:
            return {'error': 'Client has projects and cannot be deleted'}, 409
            
        try:
            db.session.delete(client)
            db.session.commit()
            return {'message': 'Client deleted'}, 200
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error deleting client: {str(e)}")
            return {'error': str(e)}, 400

@api.route('/<int:id>/documents')
class ClientDocuments(Resource):
    @jwt_required()
    @api.response(200, 'Success')
    @api.response(404, 'Client not found')
    def get(self, id):
        """Get all documents for a client"""
        # Verify client exists
        Client.query.get_or_404(id)
        
        # Get documents
        documents = Document.query.filter_by(
            entity_type=EntityType.CLIENT,
            entity_id=id
        ).all()
        
        return {'data': documents_schema.dump(documents)}, 200
    
    @jwt_required()
    @api.expect(document_upload_parser)
    @api.response(201, 'Document uploaded successfully')
    @api.response(400, 'Invalid input')
    @api.response(404, 'Client not found')
    def post(self, id):
        """Upload a document for a client"""
        # Verify client exists
        Client.query.get_or_404(id)
        
        args = document_upload_parser.parse_args()
        
        try:
            # Save the file
            file = args['file']
            filename = save_file(file)
            
            # Create document record
            document = Document(
                entity_type=EntityType.CLIENT,
                entity_id=id,
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

# Routes for the blueprint
routes = [
    ClientList,
    ClientDetail,
    ClientDocuments
]
