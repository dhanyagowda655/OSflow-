from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import db, roles_required
from models import Approval, Request, Workflow, WorkflowStep, Employee, User, Notification
from agents.orchestrator import orchestrator

manager_bp = Blueprint('manager', __name__, url_prefix='/manager')

@manager_bp.route('/dashboard')
@login_required
@roles_required('manager', 'admin')
def dashboard():
    # Direct reports
    manager_emp = Employee.query.filter_by(user_id=current_user.id).first()
    direct_reports = manager_emp.direct_reports if manager_emp else []
    report_ids = [e.id for e in direct_reports]

    pending_approvals = Approval.query.filter_by(approver_id=current_user.id, decision='pending').all()
    # If no pending specifically assigned, also show pending for direct reports
    if not pending_approvals and report_ids:
        pending_approvals = Approval.query.join(Approval.request).filter(
            Request.employee_id.in_(report_ids),
            Approval.decision == 'pending'
        ).all()

    team_requests = []
    if report_ids:
        team_requests = Request.query.filter(Request.employee_id.in_(report_ids)).order_by(Request.created_at.desc()).limit(10).all()
    else:
        # Fallback to all recent requests for demo simplicity if no direct reports assigned
        team_requests = Request.query.order_by(Request.created_at.desc()).limit(10).all()

    return render_template(
        'manager/dashboard.html',
        pending_approvals=pending_approvals,
        direct_reports=direct_reports,
        team_requests=team_requests
    )

@manager_bp.route('/approvals')
@login_required
@roles_required('manager', 'admin')
def approvals_list():
    manager_emp = Employee.query.filter_by(user_id=current_user.id).first()
    report_ids = [e.id for e in manager_emp.direct_reports] if manager_emp else []

    query = Approval.query.filter(
        (Approval.approver_id == current_user.id) |
        (Approval.request.has(Request.employee_id.in_(report_ids))) |
        (Approval.decision == 'pending')
    )
    approvals = query.order_by(Approval.created_at.desc()).all()
    return render_template('manager/approvals.html', approvals=approvals)

@manager_bp.route('/approve/<int:id>', methods=['POST'])
@login_required
@roles_required('manager', 'admin')
def approve_request(id):
    approval = Approval.query.get_or_404(id)
    comment = request.form.get('comment', 'Approved by Manager')

    approval.decision = 'approved'
    approval.comment = comment
    approval.decided_at = datetime.now(timezone.utc)
    db.session.commit()

    # Resume the workflow execution
    if approval.request and approval.request.workflow_id:
        orchestrator.run_workflow(approval.request.workflow_id, approval.request.id)

    # Notify Requester
    if approval.request and approval.request.employee and approval.request.employee.user:
        notif = Notification(
            user_id=approval.request.employee.user.id,
            message=f"Request #{approval.request.id} ({approval.request.title}) APPROVED by Manager {current_user.name}.",
            link=f"/employee/requests/{approval.request.id}"
        )
        db.session.add(notif)
        db.session.commit()

    flash(f"Request #{approval.request_id} has been approved! Workflow pipeline resumed.", 'success')
    return redirect(request.referrer or url_for('manager.approvals_list'))

@manager_bp.route('/reject/<int:id>', methods=['POST'])
@login_required
@roles_required('manager', 'admin')
def reject_request(id):
    approval = Approval.query.get_or_404(id)
    comment = request.form.get('comment', 'Rejected by Manager')

    approval.decision = 'rejected'
    approval.comment = comment
    approval.decided_at = datetime.now(timezone.utc)

    if approval.request:
        approval.request.status = 'rejected'
        if approval.step_id:
            step = db.session.get(WorkflowStep, approval.step_id)
            if step:
                step.status = 'failed'
                step.result_text = f"Manager Rejected: {comment}"
        if approval.request.workflow:
            approval.request.workflow.status = 'failed'

    # Notify Requester
    if approval.request and approval.request.employee and approval.request.employee.user:
        notif = Notification(
            user_id=approval.request.employee.user.id,
            message=f"Request #{approval.request.id} ({approval.request.title}) was REJECTED by Manager {current_user.name}: '{comment}'.",
            link=f"/employee/requests/{approval.request.id}"
        )
        db.session.add(notif)

    db.session.commit()
    flash(f"Request #{approval.request_id} was rejected.", 'warning')
    return redirect(request.referrer or url_for('manager.approvals_list'))
