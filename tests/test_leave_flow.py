import pytest
from app import create_app
from extensions import db
from models import Request, Approval, LeaveBalance, Employee, User
from seed import seed_database

@pytest.fixture
def app():
    app = create_app()
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False
    })
    with app.app_context():
        db.create_all()
        seed_database(app)
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def test_leave_flow_approval_path(client, app):
    # 1. Login as Employee and submit Leave Request
    client.post('/auth/login', data={'email': 'employee@flowos.demo', 'password': 'Demo@123'}, follow_redirects=True)
    res = client.post('/employee/request/leave', data={
        'leave_type': 'Annual',
        'days': 2,
        'reason': 'Family vacation holiday'
    }, follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        req = Request.query.filter_by(type='leave').order_by(Request.id.desc()).first()
        assert req is not None
        assert req.status in ('in_progress', 'pending')
        
        # Verify pending Approval created for manager
        approval = Approval.query.filter_by(request_id=req.id).first()
        assert approval is not None
        assert approval.decision == 'pending'
        app_id = approval.id

    client.get('/auth/logout', follow_redirects=True)

    # 2. Login as Manager and Approve
    client.post('/auth/login', data={'email': 'manager@flowos.demo', 'password': 'Demo@123'}, follow_redirects=True)
    res_app = client.post(f'/manager/approve/{app_id}', data={'comment': 'Approved! Have fun'}, follow_redirects=True)
    assert res_app.status_code == 200

    # Verify Request is completed and Leave balance updated
    with app.app_context():
        req = db.session.get(Request, req.id)
        assert req.status == 'completed'
        approval = db.session.get(Approval, app_id)
        assert approval.decision == 'approved'

def test_leave_flow_rejection_path(client, app):
    # 1. Submit Leave Request
    client.post('/auth/login', data={'email': 'employee@flowos.demo', 'password': 'Demo@123'}, follow_redirects=True)
    client.post('/employee/request/leave', data={
        'leave_type': 'Casual',
        'days': 1,
        'reason': 'Personal errand'
    }, follow_redirects=True)

    with app.app_context():
        req = Request.query.filter_by(type='leave').order_by(Request.id.desc()).first()
        approval = Approval.query.filter_by(request_id=req.id).first()
        app_id = approval.id

    client.get('/auth/logout', follow_redirects=True)

    # 2. Manager Rejects
    client.post('/auth/login', data={'email': 'manager@flowos.demo', 'password': 'Demo@123'}, follow_redirects=True)
    res_rej = client.post(f'/manager/reject/{app_id}', data={'comment': 'Critical sprint deadline'}, follow_redirects=True)
    assert res_rej.status_code == 200

    with app.app_context():
        req = db.session.get(Request, req.id)
        assert req.status == 'rejected'
        approval = db.session.get(Approval, app_id)
        assert approval.decision == 'rejected'
