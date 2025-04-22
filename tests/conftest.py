import os
import pytest
import datetime
import tempfile
from app import create_app, db
from models import User, Client, Project, PaymentPlan
from models.client import ClientStatus
from models.project import ProjectStatus, PaymentPlanType, Currency, FrequencyType
from werkzeug.security import generate_password_hash

@pytest.fixture
def app():
    """Create and configure a Flask app for testing"""
    # Create a temporary file to isolate the database for each test
    db_fd, db_path = tempfile.mkstemp()
    
    # Use SQLite for testing
    app = create_app('config.TestingConfig')
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f"sqlite:///{db_path}",
        'UPLOAD_FOLDER': tempfile.mkdtemp(),
        'WTF_CSRF_ENABLED': False
    })
    
    # Create the database and the database tables
    with app.app_context():
        db.create_all()
        _init_test_data(db)
    
    yield app
    
    # Close and remove the temporary database
    os.close(db_fd)
    os.unlink(db_path)
    
    # Remove the temporary upload folder
    os.rmdir(app.config['UPLOAD_FOLDER'])

@pytest.fixture
def client(app):
    """A test client for the app"""
    return app.test_client()

@pytest.fixture
def runner(app):
    """A test CLI runner for the app"""
    return app.test_cli_runner()

@pytest.fixture
def auth_headers(client):
    """Get authentication headers with a valid JWT token"""
    # Login to get token
    response = client.post('/api/auth/login', json={
        'username': 'testuser',
        'password': 'testpassword'
    })
    
    # Extract token from response
    data = response.get_json()
    token = data.get('access_token')
    
    # Return headers
    return {'Authorization': f'Bearer {token}'}

def _init_test_data(db):
    """Initialize test data in the database"""
    # Create test user
    test_user = User(
        username='testuser',
        email='test@example.com',
        password_hash=generate_password_hash('testpassword'),
        role='admin'
    )
    db.session.add(test_user)
    
    # Create test client
    test_client = Client(
        name='Test Client',
        contact_name='Test Contact',
        email='client@example.com',
        phone='123-456-7890',
        address='123 Test Street',
        tax_id='123456789',
        start_date=datetime.date.today() - datetime.timedelta(days=30),
        status=ClientStatus.ACTIVO,
        notes='Test client notes'
    )
    db.session.add(test_client)
    
    # Commit to get IDs
    db.session.commit()
    
    # Create test project
    test_project = Project(
        client_id=test_client.id,
        name='Test Project',
        description='Test project description',
        start_date=datetime.date.today() - datetime.timedelta(days=15),
        end_date=datetime.date.today() + datetime.timedelta(days=180),
        status=ProjectStatus.ACTIVO,
        notes='Test project notes'
    )
    db.session.add(test_project)
    
    # Commit to get project ID
    db.session.commit()
    
    # Create test payment plan
    test_payment_plan = PaymentPlan(
        project_id=test_project.id,
        type=PaymentPlanType.MIXTO,
        implementation_fee_total=1000.00,
        implementation_fee_currency=Currency.USD,
        implementation_fee_installments=2,
        recurring_fee_amount=500.00,
        recurring_fee_currency=Currency.USD,
        recurring_fee_frequency=FrequencyType.MENSUAL,
        recurring_fee_day_of_charge=1,
        recurring_fee_grace_periods=0,
        recurring_fee_discount_periods=0,
        recurring_fee_discount_percentage=0
    )
    db.session.add(test_payment_plan)
    
    # Commit all changes
    db.session.commit()
