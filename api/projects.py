from flask import request, jsonify
from flask_restx import Namespace, Resource, fields, reqparse
from flask_jwt_extended import jwt_required, get_jwt
from werkzeug.datastructures import FileStorage
from models.project import Project, PaymentPlan, ProjectStatus
from models.client import Client
from models.document import Document, EntityType, DocumentType
from schemas.project import ProjectSchema, ProjectListSchema, PaymentPlanSchema
from schemas.document import DocumentSchema, DocumentListSchema
from app import db
from utils.pagination import paginate
from utils.file_storage import save_file
import os
import logging

# Setting up API namespace
api = Namespace('projects', description='Project operations')

# Define models for swagger
payment_plan_model = api.model('PaymentPlan', {
    'type': fields.String(required=True, description='Plan type', 
                        enum=['Fee único', 'Fee por cuotas', 'Suscripción periódica', 'Mixto']),
    'implementation_fee_total': fields.Float(description='Implementation fee total'),
    'implementation_fee_currency': fields.String(description='Implementation fee currency', enum=['COP', 'USD']),
    'implementation_fee_installments': fields.Integer(description='Implementation fee installments', default=1),
    'recurring_fee_amount': fields.Float(description='Recurring fee amount'),
    'recurring_fee_currency': fields.String(description='Recurring fee currency', enum=['COP', 'USD']),
    'recurring_fee_frequency': fields.String(description='Recurring fee frequency', 
                                           enum=['Semanal', 'Quincenal', 'Mensual', 'Bimensual', 'Trimestral', 'Semestral', 'Anual']),
    'recurring_fee_day_of_charge': fields.Integer(description='Recurring fee day of charge'),
    'recurring_fee_grace_periods': fields.Integer(description='Recurring fee grace periods', default=0),
    'recurring_fee_discount_periods': fields.Integer(description='Recurring fee discount periods', default=0),
    'recurring_fee_discount_percentage': fields.Float(description='Recurring fee discount percentage', default=0)
})

project_model = api.model('Project', {
    'client_id': fields.Integer(required=True, description='Client ID'),
    'name': fields.String(required=True, description='Project name'),
    'description': fields.String(required=True, description='Project description'),
    'start_date': fields.Date(required=True, description='Project start date'),
    'end_date': fields.Date(description='Project end date'),
    'status': fields.String(description='Project status', enum=['Activo', 'Pausado', 'Finalizado', 'Cancelado']),
    'notes': fields.String(description='Additional notes'),
    'payment_plan': fields.Nested(payment_plan_model, description='Payment plan')
})

# Set up schemas
project_schema = ProjectSchema()
projects_schema = ProjectSchema(many=True)
project_list_schema = ProjectListSchema(many=True)
payment_plan_schema = PaymentPlanSchema()
document_schema = DocumentSchema()
documents_schema = DocumentListSchema(many=True)

# Query parameter parser
project_parser = reqparse.RequestParser()
project_parser.add_argument('client_id', type=int, help='Filter by client ID')
project_parser.add_argument('status', type=str, help='Filter by status')
project_parser.add_argument('sort', type=str, help='Sort field')
project_parser.add_argument('page', type=int, help='Page number')
project_parser.add_argument('per_page', type=int, help='Items per page')

# Setup file upload parser
document_upload_parser = reqparse.RequestParser()
document_upload_parser.add_argument('name', type=str, required=True, help='Document name')
document_upload_parser.add_argument('type', type=str, required=True, help='Document type')
document_upload_parser.add_argument('file', type=FileStorage, location='files', required=True, help='Document file')

@api.route('')
class ProjectList(Resource):
    @jwt_required()
    @api.expect(project_parser)
    @api.response(200, 'Success')
    def get(self):
        """Get all projects with optional filtering and pagination"""
        args = project_parser.parse_args()
        
        # Base query
        query = Project.query
        
        # Apply filters
        if args.get('client_id'):
            query = query.filter(Project.client_id == args['client_id'])
            
        if args.get('status'):
            query = query.filter(Project.status == args['status'])
        
        # Apply sorting
        if args.get('sort'):
            sort_field = args['sort']
            if hasattr(Project, sort_field):
                query = query.order_by(getattr(Project, sort_field))
        else:
            # Default sort by start_date desc
            query = query.order_by(Project.start_date.desc())
        
        # Apply pagination
        result = paginate(query, args.get('page', 1), args.get('per_page', 10), project_list_schema)
        
        return result, 200
    
    @jwt_required()
    @api.expect(project_model)
    @api.response(201, 'Project created successfully')
    @api.response(400, 'Validation error')
    @api.response(404, 'Client not found')
    def post(self):
        """Create a new project with payment plan"""
        try:
            project_data = request.json
            
            # Check if client exists
            client_id = project_data.get('client_id')
            if not Client.query.get(client_id):
                return {'error': f'Client with ID {client_id} not found'}, 404
            
            # Extract payment plan data
            payment_plan_data = project_data.pop('payment_plan', None)
            
            # Validate and deserialize project input
            project = project_schema.load(project_data)
            
            # Add to database
            db.session.add(project)
            db.session.flush()  # Flush to get project ID
            
            # Create payment plan if provided
            if payment_plan_data:
                payment_plan_data['project_id'] = project.id
                payment_plan = payment_plan_schema.load(payment_plan_data)
                db.session.add(payment_plan)
            
            db.session.commit()
            
            # Return project with payment plan
            result = project_schema.dump(project)
            
            return {'data': result}, 201
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating project: {str(e)}")
            return {'error': str(e)}, 400

@api.route('/<int:id>')
class ProjectDetail(Resource):
    @jwt_required()
    @api.response(200, 'Success')
    @api.response(404, 'Project not found')
    def get(self, id):
        """Get a project by ID"""
        project = Project.query.get_or_404(id)
        return {'data': project_schema.dump(project)}, 200
    
    @jwt_required()
    @api.expect(project_model)
    @api.response(200, 'Project updated successfully')
    @api.response(404, 'Project not found')
    @api.response(400, 'Validation error')
    def put(self, id):
        """Update a project"""
        try:
            project = Project.query.get_or_404(id)
            project_data = request.json
            
            # Extract payment plan data
            payment_plan_data = project_data.pop('payment_plan', None)
            
            # Update project with new data
            for key, value in project_data.items():
                if hasattr(project, key):
                    setattr(project, key, value)
            
            # Update payment plan if provided
            if payment_plan_data and project.payment_plan:
                for key, value in payment_plan_data.items():
                    if hasattr(project.payment_plan, key):
                        setattr(project.payment_plan, key, value)
            elif payment_plan_data:
                # Create new payment plan
                payment_plan_data['project_id'] = project.id
                payment_plan = payment_plan_schema.load(payment_plan_data)
                db.session.add(payment_plan)
            
            db.session.commit()
            
            return {'data': project_schema.dump(project)}, 200
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating project: {str(e)}")
            return {'error': str(e)}, 400

@api.route('/<int:id>/documents')
class ProjectDocuments(Resource):
    @jwt_required()
    @api.response(200, 'Success')
    @api.response(404, 'Project not found')
    def get(self, id):
        """Get all documents for a project"""
        # Verify project exists
        Project.query.get_or_404(id)
        
        # Get documents
        documents = Document.query.filter_by(
            entity_type=EntityType.PROJECT,
            entity_id=id
        ).all()
        
        return {'data': documents_schema.dump(documents)}, 200
    
    @jwt_required()
    @api.expect(document_upload_parser)
    @api.response(201, 'Document uploaded successfully')
    @api.response(400, 'Invalid input')
    @api.response(404, 'Project not found')
    def post(self, id):
        """Upload a document for a project"""
        # Verify project exists
        Project.query.get_or_404(id)
        
        args = document_upload_parser.parse_args()
        
        try:
            # Save the file
            file = args['file']
            filename = save_file(file)
            
            # Create document record
            document = Document(
                entity_type=EntityType.PROJECT,
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
    ProjectList,
    ProjectDetail,
    ProjectDocuments
]
