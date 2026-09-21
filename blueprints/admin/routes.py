import json
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from extensions import db, roles_required
from models import User, Department, Employee, Workflow, WorkflowStep, WorkflowTemplate, AILog, Request
from ai.ai_client import ping_services, get_recommendation
from ai.delay_predictor import delay_predictor

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
@login_required
@roles_required('admin')
def dashboard():
    total_users = User.query.count()
    total_requests = Request.query.count()
    total_workflows = Workflow.query.count()
    total_logs = AILog.query.count()

    recent_workflows = Workflow.query.order_by(Workflow.created_at.desc()).limit(5).all()
    recent_logs = AILog.query.order_by(AILog.created_at.desc()).limit(8).all()
    health = ping_services()

    return render_template(
        'admin/dashboard.html',
        total_users=total_users,
        total_requests=total_requests,
        total_workflows=total_workflows,
        total_logs=total_logs,
        recent_workflows=recent_workflows,
        recent_logs=recent_logs,
        health=health
    )

@admin_bp.route('/users', methods=['GET', 'POST'])
@login_required
@roles_required('admin')
def users_list():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email', '').strip().lower()
        role = request.form.get('role', 'employee')
        dept_id = request.form.get('department_id', type=int)
        password = request.form.get('password', 'Demo@123')

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash('A user with this email already exists.', 'danger')
        else:
            u = User(name=name, email=email, role=role, department_id=dept_id, is_active=True)
            u.set_password(password)
            db.session.add(u)
            db.session.flush()
            emp = Employee(user_id=u.id, designation='Team Member')
            db.session.add(emp)
            db.session.commit()
            flash(f"User '{name}' ({role}) created successfully.", 'success')
        return redirect(url_for('admin.users_list'))

    users = User.query.order_by(User.id).all()
    departments = Department.query.order_by(Department.name).all()
    return render_template('admin/users.html', users=users, departments=departments)

@admin_bp.route('/users/<int:id>/toggle-status', methods=['POST'])
@login_required
@roles_required('admin')
def toggle_user_status(id):
    u = User.query.get_or_404(id)
    if u.id == current_user.id:
        flash('You cannot deactivate your own administrative account.', 'warning')
    else:
        u.is_active = not u.is_active
        db.session.commit()
        flash(f"User '{u.name}' is now {'active' if u.is_active else 'deactivated'}.", 'info')
    return redirect(url_for('admin.users_list'))

@admin_bp.route('/departments', methods=['GET', 'POST'])
@login_required
@roles_required('admin')
def departments_list():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if name:
            existing = Department.query.filter_by(name=name).first()
            if existing:
                flash('Department already exists.', 'danger')
            else:
                d = Department(name=name)
                db.session.add(d)
                db.session.commit()
                flash(f"Department '{name}' created.", 'success')
        return redirect(url_for('admin.departments_list'))

    depts = Department.query.all()
    return render_template('admin/departments.html', departments=depts)

@admin_bp.route('/templates')
@login_required
@roles_required('admin')
def templates_list():
    tmpls = WorkflowTemplate.query.all()
    return render_template('admin/templates.html', templates=tmpls)

@admin_bp.route('/audit')
@login_required
@roles_required('admin')
def audit_logs():
    logs = AILog.query.order_by(AILog.created_at.desc()).limit(100).all()
    return render_template('admin/audit.html', logs=logs)

@admin_bp.route('/analytics')
@login_required
@roles_required('admin', 'hr', 'manager')
def analytics():
    # Analytics data generation for Chart.js
    total_reqs = Request.query.count()
    completed_reqs = Request.query.filter_by(status='completed').count()
    in_prog_reqs = Request.query.filter_by(status='in_progress').count()
    failed_reqs = Request.query.filter_by(status='failed').count()

    # Breakdown by request type
    type_counts = {}
    for r_type in ['leave', 'laptop', 'it_ticket', 'expense', 'onboarding', 'custom']:
        type_counts[r_type] = Request.query.filter_by(type=r_type).count()

    # Department loads
    dept_loads = {}
    for d in Department.query.all():
        dept_loads[d.name] = Request.query.join(Request.employee).join(Employee.user).filter(User.department_id == d.id).count()

    # AI Model execution count in logs
    model_stats = {}
    for log in AILog.query.all():
        m = log.model_used or 'rule_engine'
        model_stats[m] = model_stats.get(m, 0) + 1

    summary_metric = {
        'total_requests': total_reqs,
        'completed': completed_reqs,
        'failed_steps': failed_reqs,
        'slowest_request_type': 'laptop',
        'avg_completion_hours': 14.5
    }
    ai_recommendation = get_recommendation(summary_metric)

    return render_template(
        'admin/analytics.html',
        total_reqs=total_reqs,
        completed_reqs=completed_reqs,
        in_prog_reqs=in_prog_reqs,
        failed_reqs=failed_reqs,
        type_counts=type_counts,
        dept_loads=dept_loads,
        model_stats=model_stats,
        ai_recommendation=ai_recommendation
    )

@admin_bp.route('/ping-ai', methods=['POST'])
@login_required
@roles_required('admin')
def ping_ai():
    health = ping_services()
    return jsonify(health)
