import pytest
import json
from datetime import date, timedelta
import io

def test_get_clients_unauthorized(client):
    """Test that clients endpoint requires authentication"""
    response = client.get('/api/clients')
    assert response.status_code == 401

def test_get_clients(client, auth_headers):
    """Test getting all clients"""
    response = client.get('/api/clients', headers=auth_headers)
    
    # Check status code
    assert response.status_code == 200
    
    # Check response structure
    data = json.loads(response.data)
    assert 'data' in data
    assert 'pagination' in data
    assert isinstance(data['data'], list)
    
    # Check at least one client exists
    assert len(data['data']) > 0
    
    # Check client data
    client_data = data['data'][0]
    assert 'id' in client_data
    assert 'name' in client_data
    assert client_data['name'] == 'Test Client'
    assert 'status' in client_data
    assert client_data['status'] == 'Activo'

def test_get_client_detail(client, auth_headers):
    """Test getting a single client by ID"""
    # First, get all clients to get an ID
    response = client.get('/api/clients', headers=auth_headers)
    data = json.loads(response.data)
    client_id = data['data'][0]['id']
    
    # Now get the specific client
    response = client.get(f'/api/clients/{client_id}', headers=auth_headers)
    
    # Check status code
    assert response.status_code == 200
    
    # Check response structure
    data = json.loads(response.data)
    assert 'data' in data
    
    # Check client data is complete
    client_data = data['data']
    assert client_data['id'] == client_id
    assert client_data['name'] == 'Test Client'
    assert client_data['contact_name'] == 'Test Contact'
    assert client_data['email'] == 'client@example.com'
    assert client_data['phone'] == '123-456-7890'
    assert client_data['status'] == 'Activo'
    assert 'projects' in client_data

def test_get_nonexistent_client(client, auth_headers):
    """Test getting a client that doesn't exist"""
    response = client.get('/api/clients/999', headers=auth_headers)
    
    # Check status code
    assert response.status_code == 404

def test_create_client(client, auth_headers):
    """Test creating a new client"""
    # Create a new client
    new_client = {
        'name': 'New Test Client',
        'contact_name': 'New Contact',
        'email': 'new.client@example.com',
        'phone': '987-654-3210',
        'address': '456 New Street',
        'tax_id': '987654321',
        'start_date': date.today().isoformat(),
        'status': 'Activo',
        'notes': 'New client notes'
    }
    
    response = client.post('/api/clients', json=new_client, headers=auth_headers)
    
    # Check status code
    assert response.status_code == 201
    
    # Check response data
    data = json.loads(response.data)
    assert 'data' in data
    
    # Verify client was created with correct data
    client_data = data['data']
    assert client_data['name'] == new_client['name']
    assert client_data['email'] == new_client['email']
    assert client_data['status'] == new_client['status']
    assert 'id' in client_data
    
    # Get client to verify it exists in database
    client_id = client_data['id']
    response = client.get(f'/api/clients/{client_id}', headers=auth_headers)
    assert response.status_code == 200

def test_create_client_validation(client, auth_headers):
    """Test client creation validation"""
    # Try to create a client without required fields
    invalid_client = {
        'contact_name': 'Invalid Contact',
        'email': 'invalid@example.com'
        # Missing required name and start_date
    }
    
    response = client.post('/api/clients', json=invalid_client, headers=auth_headers)
    
    # Check status code
    assert response.status_code == 400
    
    # Try with future start date
    future_date = (date.today() + timedelta(days=30)).isoformat()
    invalid_client = {
        'name': 'Future Client',
        'start_date': future_date,
        'status': 'Activo'
    }
    
    response = client.post('/api/clients', json=invalid_client, headers=auth_headers)
    
    # Check status code - should also fail validation
    assert response.status_code == 400

def test_update_client(client, auth_headers):
    """Test updating a client"""
    # First, get all clients to get an ID
    response = client.get('/api/clients', headers=auth_headers)
    data = json.loads(response.data)
    client_id = data['data'][0]['id']
    
    # Update the client
    updated_data = {
        'name': 'Updated Client Name',
        'contact_name': 'Updated Contact',
        'status': 'Pausado'
    }
    
    response = client.put(f'/api/clients/{client_id}', json=updated_data, headers=auth_headers)
    
    # Check status code
    assert response.status_code == 200
    
    # Check client was updated
    data = json.loads(response.data)
    assert 'data' in data
    client_data = data['data']
    assert client_data['name'] == updated_data['name']
    assert client_data['contact_name'] == updated_data['contact_name']
    assert client_data['status'] == updated_data['status']
    
    # Get client to verify changes are persisted
    response = client.get(f'/api/clients/{client_id}', headers=auth_headers)
    data = json.loads(response.data)
    client_data = data['data']
    assert client_data['name'] == updated_data['name']
    assert client_data['status'] == updated_data['status']

def test_delete_client(client, auth_headers):
    """Test deleting a client"""
    # Create a client to delete
    new_client = {
        'name': 'Client To Delete',
        'start_date': date.today().isoformat(),
        'status': 'Activo'
    }
    
    response = client.post('/api/clients', json=new_client, headers=auth_headers)
    data = json.loads(response.data)
    client_id = data['data']['id']
    
    # Now delete the client
    response = client.delete(f'/api/clients/{client_id}', headers=auth_headers)
    
    # Check status code
    assert response.status_code == 200
    
    # Check message
    data = json.loads(response.data)
    assert 'message' in data
    assert data['message'] == 'Client deleted'
    
    # Try to get the deleted client
    response = client.get(f'/api/clients/{client_id}', headers=auth_headers)
    assert response.status_code == 404

def test_client_document_upload(client, auth_headers):
    """Test uploading a document for a client"""
    # First, get all clients to get an ID
    response = client.get('/api/clients', headers=auth_headers)
    data = json.loads(response.data)
    client_id = data['data'][0]['id']
    
    # Create a test file
    test_file = io.BytesIO(b'This is a test document file')
    
    # Upload document
    response = client.post(
        f'/api/clients/{client_id}/documents',
        data={
            'name': 'Test Document',
            'type': 'RUT',
            'file': (test_file, 'test.txt')
        },
        headers=auth_headers,
        content_type='multipart/form-data'
    )
    
    # Check status code
    assert response.status_code == 201
    
    # Check response data
    data = json.loads(response.data)
    assert 'data' in data
    assert data['data']['name'] == 'Test Document'
    assert data['data']['type'] == 'RUT'
    assert data['data']['entity_type'] == 'client'
    assert data['data']['entity_id'] == client_id
    
    # Get client documents to verify
    response = client.get(f'/api/clients/{client_id}/documents', headers=auth_headers)
    assert response.status_code == 200
    
    data = json.loads(response.data)
    assert 'data' in data
    assert isinstance(data['data'], list)
    assert len(data['data']) > 0
    
    # Verify the uploaded document is in the list
    document = next((d for d in data['data'] if d['name'] == 'Test Document'), None)
    assert document is not None
    assert document['type'] == 'RUT'
