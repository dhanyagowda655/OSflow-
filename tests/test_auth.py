import pytest
from app import create_app, _bootstrap_demo_data
from config import TestConfig
from extensions import db
from models import User

@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        _bootstrap_demo_data(app)
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()

def test_login_all_7_roles(client):
    roles = ['employee', 'manager', 'hr', 'it', 'finance', 'procurement', 'admin']
    for role in roles:
        email = f"{role}@flowos.demo"
        res = client.post('/auth/login', data={
            'email': email,
            'password': 'Demo@123'
        }, follow_redirects=True)
        assert res.status_code == 200
        assert b'Sign Out' in res.data or b'Portal' in res.data or b'Welcome' in res.data
        
        # Logout
        client.get('/auth/logout', follow_redirects=True)

def test_role_based_access_control(client):
    # Log in as Employee
    client.post('/auth/login', data={'email': 'employee@flowos.demo', 'password': 'Demo@123'}, follow_redirects=True)
    
    # Try accessing Admin dashboard -> should be 403 Forbidden
    res = client.get('/admin/dashboard')
    assert res.status_code == 403
    
    # Try accessing HR dashboard -> should be 403
    res_hr = client.get('/hr/dashboard')
    assert res_hr.status_code == 403

def test_landing_page(client):
    res = client.get('/')
    assert res.status_code == 200
    assert b'Intelligent Enterprise' in res.data or b'FlowOS' in res.data
    assert b'Multi-Agent DAG' in res.data

