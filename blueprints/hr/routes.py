from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import db, roles_required
from models import User, Department, Employee, LeaveBalance, Request, Workflow, WorkflowStep
from blueprints.hr.forms import OnboardEmployeeForm
from ai.workflow_generator import workflow_generator_service
from agents.orchestrator import orchestrator

hr_bp = Blueprint('hr', __name__, url_prefix='/hr')

@hr_bp.route('/dashboard')
@login_required
@roles_required('hr', 'admin')
def dashboard():
    total_employees = Employee.query.count()
    active_onboardings = Request.query.filter_by(type='onboarding', status='in_progress').count()
    pending_leaves = Request.query.filter_by(type='leave', status='in_progress').count()
    
    recent_employees = Employee.query.order_by(Employee.join_date.desc()).limit(8).all()
    onboarding_requests = Request.query.filter_by(type='onboarding').order_by(Request.created_at.desc()).limit(5).all()

    return render_template(
        'hr/dashboard.html',
        total_employees=total_employees,
        active_onboardings=active_onboardings,
        pending_leaves=pending_leaves,
        recent_employees=recent_employees,
        onboarding_requests=onboarding_requests
    )

@hr_bp.route('/employees')
@login_required
@roles_required('hr', 'admin')
def employees_list():
    dept_id = request.args.get('department_id', type=int)
    query = Employee.query
    if dept_id:
        query = query.join(Employee.user).filter(User.department_id == dept_id)
        
    employees = query.all()
    departments = Department.query.all()
    return render_template('hr/employees.html', employees=employees, departments=departments, selected_dept=dept_id)

@hr_bp.route('/onboard', methods=['GET', 'POST'])
@login_required
@roles_required('hr', 'admin')
def onboard_employee():
    form = OnboardEmployeeForm()
    
    # Populate dropdowns
    departments = Department.query.order_by(Department.name).all()
    managers = Employee.query.join(Employee.user).filter(User.role.in_(['manager', 'admin', 'hr'])).all()
    
    form.department_id.choices = [(d.id, d.name) for d in departments]
    form.manager_id.choices = [(m.id, f"{m.user.name} ({m.designation})") for m in managers] if managers else [(1, 'Default Manager')]

    if form.validate_on_submit():
        # Check duplicate email
        existing_user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if existing_user:
            flash('A user with this email address already exists.', 'danger')
            return render_template('hr/onboard.html', form=form)

        # 1. Create User
        new_user = User(
            name=form.name.data.strip(),
            email=form.email.data.strip().lower(),
            role='employee',
            department_id=form.department_id.data,
            is_active=True
        )
        new_user.set_password('Demo@123') # Default starter password
        db.session.add(new_user)
        db.session.flush()

        # 2. Create Employee Profile
        new_emp = Employee(
            user_id=new_user.id,
            designation=form.designation.data.strip(),
            manager_id=form.manager_id.data if form.manager_id.data else None,
            join_date=datetime.now(timezone.utc).date()
        )
        db.session.add(new_emp)
        db.session.flush()

        # 3. Create default leave balances
        for l_type, days in [('Annual', 20.0), ('Casual', 10.0), ('Sick', 12.0)]:
            lb = LeaveBalance(employee_id=new_emp.id, leave_type=l_type, total_days=days, used_days=0.0)
            db.session.add(lb)

        # 4. Create Onboarding Request
        onboard_req = Request(
            employee_id=new_emp.id,
            type='onboarding',
            title=f"Employee Onboarding - {new_user.name}",
            description=f"Job Title: {new_emp.designation}. Department: {new_user.department.name if new_user.department else 'Engineering'}. Notes: {form.notes.data}",
            priority='high',
            status='pending'
        )
        db.session.add(onboard_req)
        db.session.flush()

        # 5. Generate and execute full Onboarding Workflow DAG
        instruction = (
            f"When a new employee {new_user.name} joins: verify documents, create corporate email account, "
            f"assign laptop, create GitHub account, schedule induction training, notify reporting manager, and update payroll."
        )
        workflow, tier, meta = workflow_generator_service.create_workflow_from_text(instruction, user_id=current_user.id)
        onboard_req.workflow_id = workflow.id
        db.session.commit()

        # Run multi-agent orchestrator
        orchestrator.run_workflow(workflow.id, onboard_req.id)

        flash(f"Onboarding workflow for {new_user.name} generated via {tier} and dispatched to multi-agent orchestrator!", 'success')
        return redirect(url_for('employee.request_detail', id=onboard_req.id))

    return render_template('hr/onboard.html', form=form)

@hr_bp.route('/leaves')
@login_required
@roles_required('hr', 'admin')
def leaves_overview():
    leave_requests = Request.query.filter_by(type='leave').order_by(Request.created_at.desc()).all()
    employees = Employee.query.all()
    return render_template('hr/leaves.html', leave_requests=leave_requests, employees=employees)
