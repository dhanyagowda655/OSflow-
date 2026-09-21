import os
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from flask import Flask, redirect, url_for, render_template
from flask_login import current_user
from config import Config
from extensions import db, login_manager, csrf
from blueprints.auth.routes import auth_bp, get_role_dashboard_url
from blueprints.employee.routes import employee_bp
from blueprints.manager.routes import manager_bp
from blueprints.hr.routes import hr_bp
from blueprints.it.routes import it_bp
from blueprints.finance.routes import finance_bp
from blueprints.procurement.routes import procurement_bp
from blueprints.admin.routes import admin_bp
from blueprints.workflow.routes import workflow_bp
from blueprints.api.routes import api_bp

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize Extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Configure Logging
    if not os.path.exists('logs'):
        os.makedirs('logs', exist_ok=True)
    file_handler = RotatingFileHandler('logs/flowos.log', maxBytes=1024 * 1024 * 5, backupCount=5)
    file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('FlowOS system startup')

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(employee_bp)
    app.register_blueprint(manager_bp)
    app.register_blueprint(hr_bp)
    app.register_blueprint(it_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(procurement_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(workflow_bp)
    app.register_blueprint(api_bp)

    # Root landing page route
    @app.route('/')
    def index():
        return render_template('landing.html')

    # Global Error Handlers
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        app.logger.error(f"Internal 500 error: {e}")
        return render_template('errors/500.html'), 500

    # Auto-seed database if empty
    with app.app_context():
        db.create_all()
        try:
            from models import User, Department
            if User.query.count() == 0:
                try:
                    from seed import seed_database
                    seed_database(app)
                except ImportError:
                    # Built-in fallback seeder if seed.py is excluded
                    _bootstrap_demo_data(app)
        except Exception as e:
            app.logger.warning(f"Auto-seed check note: {e}")

    return app

def _bootstrap_demo_data(app):
    """Complete built-in seeder ensuring all departments, 7 demo accounts, hardware assets,
    workflow templates with embeddings, and historical telemetry are populated automatically."""
    import json
    from datetime import datetime, timezone, timedelta
    from models import (
        Department, User, Employee, LeaveBalance, Asset,
        WorkflowTemplate, Request, AILog
    )
    from ai.embeddings import get_embedding

    with app.app_context():
        db.create_all()

        # 1. Seed Departments
        depts = ['Engineering', 'Human Resources', 'Finance & Operations', 'IT Infrastructure']
        dept_map = {}
        for d in depts:
            dept = Department.query.filter_by(name=d).first()
            if not dept:
                dept = Department(name=d)
                db.session.add(dept)
                db.session.flush()
            dept_map[d] = dept

        # 2. Seed All 7 Roles
        demo_users = [
            {'email': 'employee@flowos.demo', 'name': 'Alex Rivera', 'role': 'employee', 'dept': 'Engineering', 'desig': 'Software Engineer'},
            {'email': 'manager@flowos.demo', 'name': 'Sarah Connor', 'role': 'manager', 'dept': 'Engineering', 'desig': 'Engineering Director'},
            {'email': 'hr@flowos.demo', 'name': 'Emma Watson', 'role': 'hr', 'dept': 'Human Resources', 'desig': 'HR Specialist'},
            {'email': 'it@flowos.demo', 'name': 'David Miller', 'role': 'it', 'dept': 'IT Infrastructure', 'desig': 'Lead Systems Engineer'},
            {'email': 'finance@flowos.demo', 'name': 'Michael Chang', 'role': 'finance', 'dept': 'Finance & Operations', 'desig': 'Chief Financial Controller'},
            {'email': 'procurement@flowos.demo', 'name': 'Rachel Green', 'role': 'procurement', 'dept': 'Finance & Operations', 'desig': 'Procurement Officer'},
            {'email': 'admin@flowos.demo', 'name': 'Admin Superuser', 'role': 'admin', 'dept': 'IT Infrastructure', 'desig': 'Enterprise Systems Admin'},
        ]

        emp_map = {}
        for acc in demo_users:
            u = User.query.filter_by(email=acc['email']).first()
            if not u:
                u = User(
                    email=acc['email'],
                    name=acc['name'],
                    role=acc['role'],
                    department_id=dept_map[acc['dept']].id,
                    is_active=True
                )
                u.set_password('Demo@123')
                db.session.add(u)
                db.session.flush()

            emp = Employee.query.filter_by(user_id=u.id).first()
            if not emp:
                emp = Employee(
                    user_id=u.id,
                    designation=acc['desig'],
                    join_date=datetime.now(timezone.utc).date() - timedelta(days=120)
                )
                db.session.add(emp)
                db.session.flush()

                for l_type, days in [('Annual', 20.0), ('Casual', 10.0), ('Sick', 12.0)]:
                    lb = LeaveBalance(employee_id=emp.id, leave_type=l_type, total_days=days, used_days=2.0)
                    db.session.add(lb)

            emp_map[acc['role']] = emp

        # Link Alex Rivera's manager to Sarah Connor
        if 'employee' in emp_map and 'manager' in emp_map:
            emp_map['employee'].manager_id = emp_map['manager'].id

        # 3. Seed Assets
        if Asset.query.count() == 0:
            sample_assets = [
                Asset(type='Laptop', model_name='MacBook Pro 14" M3', serial_number='SN-MBP-98321', status='in_stock'),
                Asset(type='Laptop', model_name='Dell XPS 15 Enterprise', serial_number='SN-XPS-44129', status='in_stock'),
                Asset(type='Laptop', model_name='ThinkPad X1 Carbon', serial_number='SN-TP-11029', status='in_stock'),
                Asset(type='Monitor', model_name='Dell UltraSharp 27" 4K', serial_number='SN-MON-99120', status='in_stock'),
                Asset(type='Laptop', model_name='MacBook Air M2', serial_number='SN-MBA-77312', status='assigned', assigned_to=emp_map['employee'].id if 'employee' in emp_map else None)
            ]
            db.session.add_all(sample_assets)

        # 4. Seed Workflow Templates with precomputed embeddings
        if WorkflowTemplate.query.count() == 0:
            templates = [
                {
                    'name': 'Employee Onboarding DAG',
                    'category': 'onboarding',
                    'desc': 'Standard hiring workflow: HR verify documents, IT email setup, laptop assignment, GitHub access, orientation, manager notification, payroll sync.',
                    'dag': {
                        "workflow_name": "Standard Employee Onboarding",
                        "tasks": [
                            {"id": "t1", "name": "Verify Employee Documents", "agent_type": "hr", "depends_on": []},
                            {"id": "t2", "name": "Create Corporate Email Account", "agent_type": "it", "depends_on": ["t1"]},
                            {"id": "t3", "name": "Assign Workstation & Laptop", "agent_type": "it", "depends_on": ["t1"]},
                            {"id": "t4", "name": "Provision GitHub & Cloud Access", "agent_type": "it", "depends_on": ["t2"]},
                            {"id": "t5", "name": "Schedule Orientation & Induction", "agent_type": "hr", "depends_on": ["t1"]},
                            {"id": "t6", "name": "Notify Reporting Manager", "agent_type": "notification", "depends_on": ["t3", "t4", "t5"]},
                            {"id": "t7", "name": "Enroll in Payroll & Benefits", "agent_type": "finance", "depends_on": ["t6"]}
                        ]
                    }
                },
                {
                    'name': 'Laptop & Hardware Procurement DAG',
                    'category': 'laptop',
                    'desc': 'Hardware request chain: Manager review, Finance budget approval, Procurement purchase order, IT OS provisioning, employee notification.',
                    'dag': {
                        "workflow_name": "Hardware & Laptop Procurement",
                        "tasks": [
                            {"id": "t1", "name": "Manager Review & Approval", "agent_type": "manager", "depends_on": []},
                            {"id": "t2", "name": "Finance Budget & Policy Check", "agent_type": "finance", "depends_on": ["t1"]},
                            {"id": "t3", "name": "Procurement Purchase Order Fulfillment", "agent_type": "procurement", "depends_on": ["t2"]},
                            {"id": "t4", "name": "IT Hardware Configuration & OS Imaging", "agent_type": "it", "depends_on": ["t3"]},
                            {"id": "t5", "name": "Dispatch Notification & Asset Confirmation", "agent_type": "notification", "depends_on": ["t4"]}
                        ]
                    }
                },
                {
                    'name': 'Leave Application Approval DAG',
                    'category': 'leave',
                    'desc': 'Time off request: HR validate leave balance, Manager review, HR update records, Finance payroll check, notification.',
                    'dag': {
                        "workflow_name": "Employee Leave Approval",
                        "tasks": [
                            {"id": "t1", "name": "Validate Leave Balance", "agent_type": "hr", "depends_on": []},
                            {"id": "t2", "name": "Manager Approval Review", "agent_type": "manager", "depends_on": ["t1"]},
                            {"id": "t3", "name": "Update HR Leave Records", "agent_type": "hr", "depends_on": ["t2"]},
                            {"id": "t4", "name": "Payroll Adjustment Check", "agent_type": "finance", "depends_on": ["t3"]},
                            {"id": "t5", "name": "Send Confirmation Notification", "agent_type": "notification", "depends_on": ["t4"]}
                        ]
                    }
                },
                {
                    'name': 'Expense Reimbursement DAG',
                    'category': 'expense',
                    'desc': 'Expense claim flow: OCR receipt verification, Manager authorization, Finance policy audit, Payment disbursement.',
                    'dag': {
                        "workflow_name": "Expense Reimbursement",
                        "tasks": [
                            {"id": "t1", "name": "OCR Receipt Verification & Duplicate Check", "agent_type": "finance", "depends_on": []},
                            {"id": "t2", "name": "Manager Authorization", "agent_type": "manager", "depends_on": ["t1"]},
                            {"id": "t3", "name": "Finance Audit & Policy Compliance", "agent_type": "finance", "depends_on": ["t2"]},
                            {"id": "t4", "name": "Disburse Payment & Notify Employee", "agent_type": "notification", "depends_on": ["t3"]}
                        ]
                    }
                },
                {
                    'name': 'IT Support Resolution DAG',
                    'category': 'it_ticket',
                    'desc': 'IT ticket resolution: AI ticket categorization, Engineer investigation, User confirmation notification.',
                    'dag': {
                        "workflow_name": "IT Support Resolution",
                        "tasks": [
                            {"id": "t1", "name": "AI Ticket Categorization & Priority Routing", "agent_type": "it", "depends_on": []},
                            {"id": "t2", "name": "IT Engineer Investigation & Fix", "agent_type": "it", "depends_on": ["t1"]},
                            {"id": "t3", "name": "Resolution Confirmation & User Notification", "agent_type": "notification", "depends_on": ["t2"]}
                        ]
                    }
                }
            ]

            for tmpl_data in templates:
                vec = get_embedding(f"{tmpl_data['name']} {tmpl_data['desc']}")
                wt = WorkflowTemplate(
                    name=tmpl_data['name'],
                    description=tmpl_data['desc'],
                    category=tmpl_data['category'],
                    embedding_json=json.dumps(vec),
                    dag_json=json.dumps(tmpl_data['dag'])
                )
                db.session.add(wt)

        # 5. Seed Historical Completed Requests & Logs for Instant Analytics
        if Request.query.count() == 0 and 'employee' in emp_map:
            hist_items = [
                {'type': 'leave', 'title': 'Annual Vacation Leave (3 Days)', 'status': 'completed', 'days_ago': 10},
                {'type': 'laptop', 'title': 'Hardware Request - MacBook Pro 14"', 'status': 'completed', 'days_ago': 8},
                {'type': 'it_ticket', 'title': 'IT Ticket: VPN disconnect issue on Windows', 'status': 'completed', 'days_ago': 5},
                {'type': 'expense', 'title': 'Expense Claim - Delta Airlines ($420.00)', 'status': 'completed', 'days_ago': 3},
                {'type': 'onboarding', 'title': 'Employee Onboarding - Alex Rivera', 'status': 'completed', 'days_ago': 14},
            ]
            for h in hist_items:
                ts = datetime.now(timezone.utc) - timedelta(days=h['days_ago'])
                req = Request(
                    employee_id=emp_map['employee'].id,
                    type=h['type'],
                    title=h['title'],
                    description=f"Historical seed request for {h['type']}",
                    status=h['status'],
                    created_at=ts
                )
                db.session.add(req)

            sample_logs = [
                AILog(agent_type='system', action='generate_workflow', prompt='Onboarding request', response='{"workflow_name":"Onboarding"}', model_used='gemini', latency_ms=420.5),
                AILog(agent_type='it', action='classify_ticket', prompt='VPN disconnect', response='network', model_used='mistral', latency_ms=210.0),
                AILog(agent_type='finance', action='ocr_extract', prompt='Receipt image scan', response='Vendor: Delta, Total: 420.00', model_used='rule_engine', latency_ms=85.0)
            ]
            db.session.add_all(sample_logs)

        db.session.commit()

# Expose app for WSGI servers like Gunicorn
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)


