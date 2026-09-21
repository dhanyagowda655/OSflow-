import pytest
from app import create_app, _bootstrap_demo_data
from config import TestConfig
from extensions import db
from models import Request, Approval, Asset, Employee, User

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

def test_laptop_provisioning_full_chain(client, app):
    # 1. Employee submits laptop request
    client.post('/auth/login', data={'email': 'employee@flowos.demo', 'password': 'Demo@123'}, follow_redirects=True)
    res = client.post('/employee/request/laptop', data={
        'model_preference': 'MacBook Pro 14" M3 (Engineering Standard)',
        'business_justification': 'Heavy local Docker & ML development workloads',
        'priority': 'high'
    }, follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        req = Request.query.filter_by(type='laptop').order_by(Request.id.desc()).first()
        assert req is not None
        approval = Approval.query.filter_by(request_id=req.id).first()
        assert approval is not None
        app_id = approval.id

    client.get('/auth/logout', follow_redirects=True)

    # 2. Manager Approves the request -> triggers downstream multi-agent chain
    client.post('/auth/login', data={'email': 'manager@flowos.demo', 'password': 'Demo@123'}, follow_redirects=True)
    res_app = client.post(f'/manager/approve/{app_id}', data={'comment': 'Budget approved for engineering upgrade'}, follow_redirects=True)
    assert res_app.status_code == 200

    # 3. Check State changes in DB: Request completed, Asset assigned
    with app.app_context():
        req = db.session.get(Request, req.id)
        assert req.status == 'completed'
        
        # Verify workflow steps are done
        assert req.workflow is not None
        for step in req.workflow.steps:
            assert step.status == 'done'

        # Verify an asset is assigned to the employee
        assigned_asset = Asset.query.filter_by(assigned_to=req.employee_id, status='assigned').first()
        assert assigned_asset is not None
        assert 'MacBook' in assigned_asset.model_name or 'Dell' in assigned_asset.model_name or assigned_asset.type == 'Laptop'
