import json
from datetime import datetime, timezone, timedelta
from config import Config
from extensions import db
from models import (
    Department, User, Employee, LeaveBalance, Asset,
    WorkflowTemplate, Workflow, WorkflowStep, Request, Approval, AILog, ExpenseClaim
)
from ai.embeddings import get_embedding

def seed_database(app):
    """Idempotently seeds departments, demo users, templates, assets, and historical records."""
    with app.app_context():
        db.create_all()

        # 1. Seed Departments
        dept_names = ['Engineering', 'Human Resources', 'Finance & Operations', 'IT Infrastructure']
        dept_map = {}
        for name in dept_names:
            dept = Department.query.filter_by(name=name).first()
            if not dept:
                dept = Department(name=name)
                db.session.add(dept)
                db.session.flush()
            dept_map[name] = dept

        # 2. Seed All 7 Roles
        demo_accounts = [
            {'email': 'employee@flowos.demo', 'name': 'Alex Rivera', 'role': 'employee', 'dept': 'Engineering', 'desig': 'Software Engineer'},
            {'email': 'manager@flowos.demo', 'name': 'Sarah Connor', 'role': 'manager', 'dept': 'Engineering', 'desig': 'Engineering Director'},
            {'email': 'hr@flowos.demo', 'name': 'Emma Watson', 'role': 'hr', 'dept': 'Human Resources', 'desig': 'HR Specialist'},
            {'email': 'it@flowos.demo', 'name': 'David Miller', 'role': 'it', 'dept': 'IT Infrastructure', 'desig': 'Lead Systems Engineer'},
            {'email': 'finance@flowos.demo', 'name': 'Michael Chang', 'role': 'finance', 'dept': 'Finance & Operations', 'desig': 'Chief Financial Controller'},
            {'email': 'procurement@flowos.demo', 'name': 'Rachel Green', 'role': 'procurement', 'dept': 'Finance & Operations', 'desig': 'Procurement Officer'},
            {'email': 'admin@flowos.demo', 'name': 'Admin Superuser', 'role': 'admin', 'dept': 'IT Infrastructure', 'desig': 'Enterprise Systems Admin'},
        ]

        user_map = {}
        emp_map = {}

        for acc in demo_accounts:
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

            user_map[acc['role']] = u

            emp = Employee.query.filter_by(user_id=u.id).first()
            if not emp:
                emp = Employee(
                    user_id=u.id,
                    designation=acc['desig'],
                    join_date=datetime.now(timezone.utc).date() - timedelta(days=120)
                )
                db.session.add(emp)
                db.session.flush()

                # Leave balances
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
                Asset(type='Laptop', model_name='MacBook Air M2', serial_number='SN-MBA-77312', status='assigned', assigned_to=emp_map['employee'].id)
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
        if Request.query.count() == 0:
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

            # Historical AI Logs
            sample_logs = [
                AILog(agent_type='system', action='generate_workflow', prompt='Onboarding request', response='{"workflow_name":"Onboarding"}', model_used='gemini', latency_ms=420.5),
                AILog(agent_type='it', action='classify_ticket', prompt='VPN disconnect', response='network', model_used='mistral', latency_ms=210.0),
                AILog(agent_type='finance', action='ocr_extract', prompt='Receipt image scan', response='Vendor: Delta, Total: 420.00', model_used='rule_engine', latency_ms=85.0)
            ]
            db.session.add_all(sample_logs)

        db.session.commit()

        print("\n============================================================")
        print("  FlowOS Enterprise Database Seeded Successfully!")
        print("============================================================")
        print(" Demo Accounts (Password: 'Demo@123'):")
        print("   • Employee:    employee@flowos.demo")
        print("   • Manager:     manager@flowos.demo")
        print("   • HR:          hr@flowos.demo")
        print("   • IT Support:  it@flowos.demo")
        print("   • Finance:     finance@flowos.demo")
        print("   • Procurement: procurement@flowos.demo")
        print("   • Admin:       admin@flowos.demo")
        print("============================================================\n")

if __name__ == '__main__':
    from app import create_app
    app = create_app()
    seed_database(app)
