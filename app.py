import os
import logging
from datetime import timedelta
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy.orm import DeclarativeBase
from flask_jwt_extended import JWTManager
from flask_marshmallow import Marshmallow
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_restx import Api

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Database setup
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
migrate = Migrate()
ma = Marshmallow()
jwt = JWTManager()

def create_app(config_object='config.DevelopmentConfig'):
    # Create and configure the app
    app = Flask(__name__)
    app.config.from_object(config_object)
    
    # Set secret key from environment or default
    app.secret_key = os.environ.get("SESSION_SECRET") or os.environ.get("JWT_SECRET_KEY", "development_secret_key")
    
    # Fix proxy issues
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    ma.init_app(app)
    jwt.init_app(app)
    CORS(app)
    
    # Setup JWT configurations
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', app.secret_key)
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=30)
    
    # Register namespaces directly instead of using blueprints
    
    # API documentation setup
    authorizations = {
        'jwt': {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Authorization',
            'description': "Type in the *'Value'* input box below: **'Bearer &lt;JWT&gt;'**, where JWT is the token"
        }
    }
    
    api = Api(
        app, 
        version='1.0', 
        title='Control Fresco API',
        description='Financial management application API',
        doc='/api/docs',
        authorizations=authorizations,
        security='jwt'
    )
    
    # Register namespaces
    from api.auth import api as auth_ns
    from api.clients import api as clients_ns
    from api.projects import api as projects_ns
    from api.payments import api as payments_ns
    from api.documents import api as documents_ns
    from api.incomes import api as incomes_ns
    from api.expenses import api as expenses_ns
    from api.reports import api as reports_ns
    
    api.add_namespace(auth_ns)
    api.add_namespace(clients_ns)
    api.add_namespace(projects_ns)
    api.add_namespace(payments_ns)
    api.add_namespace(documents_ns)
    api.add_namespace(incomes_ns)
    api.add_namespace(expenses_ns)
    api.add_namespace(reports_ns)
    
    # Register error handlers
    @app.errorhandler(404)
    def not_found(error):
        return {'error': 'Not found'}, 404
    
    @app.errorhandler(500)
    def server_error(error):
        logger.error(f"Server error: {error}")
        return {'error': 'Internal server error'}, 500
        
    # Create database tables within app context
    with app.app_context():
        db.create_all()
        
    return app

app = create_app()
