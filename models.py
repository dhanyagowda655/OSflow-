import json
from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db, login_manager

class Department(db.Model):
    __tablename__ = 'departments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    users = db.relationship('User', backref='department', lazy=True)

    def to_dict(self):
        return {'id': self.id, 'name': self.name}


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='employee') # employee, manager, hr, it, finance, procurement, admin
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    employee_profile = db.relationship('Employee', backref='user', uselist=False, lazy=True, cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user', lazy=True, order_by='desc(Notification.created_at)', cascade='all, delete-orphan')
    created_workflows = db.relationship('Workflow', backref='creator', lazy=True)
    approvals = db.relationship('Approval', backref='approver', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'role': self.role,
            'department': self.department.name if self.department else None,
            'is_active': self.is_active
        }

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Employee(db.Model):
    __tablename__ = 'employees'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    designation = db.Column(db.String(120), nullable=False, default='Associate')
    join_date = db.Column(db.Date, default=lambda: datetime.now(timezone.utc).date())
    manager_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)

    # Self-referential relationship for Manager -> Direct Reports
    direct_reports = db.relationship('Employee', backref=db.backref('manager', remote_side=[id]), lazy=True)
    requests = db.relationship('Request', backref='employee', lazy=True, order_by='desc(Request.created_at)', cascade='all, delete-orphan')
    leave_balances = db.relationship('LeaveBalance', backref='employee', lazy=True, cascade='all, delete-orphan')
    assigned_assets = db.relationship('Asset', backref='assigned_employee', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.user.name if self.user else None,
            'email': self.user.email if self.user else None,
            'designation': self.designation,
            'join_date': str(self.join_date) if self.join_date else None,
            'manager_name': self.manager.user.name if (self.manager and self.manager.user) else None
        }


class Workflow(db.Model):
    __tablename__ = 'workflows'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    dag_json = db.Column(db.Text, nullable=False) # JSON representation of full DAG
    source_text = db.Column(db.Text, nullable=True) # Original natural language input
    status = db.Column(db.String(50), default='pending') # pending, in_progress, completed, failed, partially_failed
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    steps = db.relationship('WorkflowStep', backref='workflow', lazy=True, order_by='WorkflowStep.id', cascade='all, delete-orphan')
    requests = db.relationship('Request', backref='workflow', lazy=True)
    ai_logs = db.relationship('AILog', backref='workflow', lazy=True)

    def get_dag(self):
        try:
            return json.loads(self.dag_json) if self.dag_json else {}
        except Exception:
            return {}

    def set_dag(self, data):
        self.dag_json = json.dumps(data)


class WorkflowStep(db.Model):
    __tablename__ = 'workflow_steps'
    
    id = db.Column(db.Integer, primary_key=True)
    workflow_id = db.Column(db.Integer, db.ForeignKey('workflows.id'), nullable=False)
    step_key = db.Column(db.String(50), nullable=True) # e.g. 't1', 't2'
    name = db.Column(db.String(255), nullable=False)
    agent_type = db.Column(db.String(50), nullable=False) # hr, manager, finance, procurement, it, notification
    depends_on_json = db.Column(db.Text, default='[]') # JSON list of step keys or ids
    status = db.Column(db.String(50), default='pending') # pending, in_progress, done, failed, skipped, waiting_approval
    retry_count = db.Column(db.Integer, default=0)
    result_text = db.Column(db.Text, nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    @property
    def depends_on(self):
        try:
            return json.loads(self.depends_on_json) if self.depends_on_json else []
        except Exception:
            return []

    @depends_on.setter
    def depends_on(self, value):
        self.depends_on_json = json.dumps(value if isinstance(value, list) else [])

    def to_dict(self):
        return {
            'id': self.id,
            'step_key': self.step_key,
            'name': self.name,
            'agent_type': self.agent_type,
            'depends_on': self.depends_on,
            'status': self.status,
            'retry_count': self.retry_count,
            'result_text': self.result_text,
            'started_at': self.started_at.strftime('%H:%M:%S') if self.started_at else None,
            'completed_at': self.completed_at.strftime('%H:%M:%S') if self.completed_at else None
        }


class Request(db.Model):
    __tablename__ = 'requests'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False) # leave, laptop, it_ticket, expense, onboarding, custom
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default='pending') # pending, in_progress, approved, rejected, completed, failed
    priority = db.Column(db.String(20), default='medium') # low, medium, high, urgent
    workflow_id = db.Column(db.Integer, db.ForeignKey('workflows.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    approvals = db.relationship('Approval', backref='request', lazy=True, cascade='all, delete-orphan')
    expense_claim = db.relationship('ExpenseClaim', backref='request', uselist=False, lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'priority': self.priority,
            'employee_name': self.employee.user.name if (self.employee and self.employee.user) else None,
            'workflow_id': self.workflow_id,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None
        }


class Approval(db.Model):
    __tablename__ = 'approvals'
    
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('requests.id'), nullable=False)
    approver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    step_id = db.Column(db.Integer, db.ForeignKey('workflow_steps.id'), nullable=True)
    decision = db.Column(db.String(50), default='pending') # pending, approved, rejected
    comment = db.Column(db.Text, nullable=True)
    decided_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(255), nullable=True)
    read_flag = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'message': self.message,
            'link': self.link,
            'read_flag': self.read_flag,
            'created_at': self.created_at.strftime('%b %d, %H:%M') if self.created_at else ''
        }


class Asset(db.Model):
    __tablename__ = 'assets'
    
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(100), nullable=False) # Laptop, Monitor, Headset, Phone, Access Card
    model_name = db.Column(db.String(150), nullable=True)
    serial_number = db.Column(db.String(100), unique=True, nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    status = db.Column(db.String(50), default='in_stock') # in_stock, assigned, retired, in_repair
    allocated_at = db.Column(db.DateTime, nullable=True)


class AILog(db.Model):
    __tablename__ = 'ai_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    workflow_id = db.Column(db.Integer, db.ForeignKey('workflows.id'), nullable=True)
    agent_type = db.Column(db.String(50), nullable=False)
    action = db.Column(db.String(200), nullable=False)
    prompt = db.Column(db.Text, nullable=True)
    response = db.Column(db.Text, nullable=True)
    model_used = db.Column(db.String(50), nullable=True) # gemini, mistral, rule_engine, local_bert
    latency_ms = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class LeaveBalance(db.Model):
    __tablename__ = 'leave_balances'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    leave_type = db.Column(db.String(50), nullable=False) # Casual, Sick, Annual, Paid
    total_days = db.Column(db.Float, default=20.0)
    used_days = db.Column(db.Float, default=0.0)

    @property
    def remaining_days(self):
        return max(0.0, (self.total_days or 0.0) - (self.used_days or 0.0))


class ExpenseClaim(db.Model):
    __tablename__ = 'expense_claims'
    
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('requests.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    vendor = db.Column(db.String(150), nullable=True)
    expense_date = db.Column(db.Date, nullable=True)
    category = db.Column(db.String(100), nullable=False, default='Travel') # Travel, Meals, Hardware, Software, Misc
    receipt_path = db.Column(db.String(255), nullable=True)
    extracted_json = db.Column(db.Text, nullable=True)
    duplicate_flag = db.Column(db.Boolean, default=False)
    policy_compliant = db.Column(db.Boolean, default=True)


class WorkflowTemplate(db.Model):
    __tablename__ = 'workflow_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    embedding_json = db.Column(db.Text, nullable=True) # Stored vector as JSON float list
    dag_json = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default='general')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def get_dag(self):
        try:
            return json.loads(self.dag_json) if self.dag_json else {}
        except Exception:
            return {}
