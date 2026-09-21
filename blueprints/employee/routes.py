import os
import uuid
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from extensions import db, roles_required
from models import Request, Workflow, WorkflowStep, Employee, LeaveBalance, ExpenseClaim, Notification
from blueprints.employee.forms import (
    LeaveRequestForm,
    LaptopRequestForm,
    ITTicketForm,
    ExpenseClaimForm,
    CustomNLRequestForm
)
from ai.workflow_generator import workflow_generator_service
from ai.ocr import extract_text_from_file, parse_receipt_data
from ai.delay_predictor import delay_predictor
from agents.orchestrator import orchestrator

employee_bp = Blueprint('employee', __name__, url_prefix='/employee')

def get_or_create_employee(user):
    emp = Employee.query.filter_by(user_id=user.id).first()
    if not emp:
        emp = Employee(user_id=user.id, designation='Enterprise Member')
        db.session.add(emp)
        db.session.flush()
        # default leave
        lb = LeaveBalance(employee_id=emp.id, leave_type='Annual', total_days=20.0, used_days=0.0)
        db.session.add(lb)
        db.session.commit()
    return emp

@employee_bp.route('/dashboard')
@login_required
def dashboard():
    emp = get_or_create_employee(current_user)
    recent_requests = Request.query.filter_by(employee_id=emp.id).order_by(Request.created_at.desc()).limit(5).all()
    leave_balances = LeaveBalance.query.filter_by(employee_id=emp.id).all()
    
    total_reqs = Request.query.filter_by(employee_id=emp.id).count()
    completed_reqs = Request.query.filter_by(employee_id=emp.id, status='completed').count()
    pending_reqs = Request.query.filter_by(employee_id=emp.id, status='in_progress').count()

    custom_form = CustomNLRequestForm()

    return render_template(
        'employee/dashboard.html',
        recent_requests=recent_requests,
        leave_balances=leave_balances,
        total_reqs=total_reqs,
        completed_reqs=completed_reqs,
        pending_reqs=pending_reqs,
        custom_form=custom_form
    )

@employee_bp.route('/requests')
@login_required
def requests_list():
    emp = get_or_create_employee(current_user)
    req_type = request.args.get('type')
    status = request.args.get('status')
    
    query = Request.query.filter_by(employee_id=emp.id)
    if req_type:
        query = query.filter_by(type=req_type)
    if status:
        query = query.filter_by(status=status)
        
    requests = query.order_by(Request.created_at.desc()).all()
    return render_template('employee/requests.html', requests=requests)

@employee_bp.route('/requests/<int:id>')
@login_required
def request_detail(id):
    emp = get_or_create_employee(current_user)
    req = Request.query.get_or_404(id)
    
    # Authorize: Requester, Manager, or Department Role / Admin
    if req.employee_id != emp.id and current_user.role not in ('manager', 'hr', 'it', 'finance', 'procurement', 'admin'):
        flash('Access restricted to the owner of this request.', 'danger')
        return redirect(url_for('employee.requests_list'))

    steps = []
    if req.workflow:
        steps = req.workflow.steps

    prediction = delay_predictor.predict_delay(req.type, req.priority, len(steps), 3)

    return render_template('employee/request_detail.html', request=req, steps=steps, prediction=prediction)

@employee_bp.route('/request/leave', methods=['GET', 'POST'])
@login_required
def request_leave():
    emp = get_or_create_employee(current_user)
    form = LeaveRequestForm()
    
    if form.validate_on_submit():
        desc = f"Leave Request: {form.days.data} day(s) of {form.leave_type.data} leave. Reason: {form.reason.data}"
        title = f"{form.leave_type.data} Leave ({form.days.data} Days)"
        
        req = Request(
            employee_id=emp.id,
            type='leave',
            title=title,
            description=desc,
            priority='medium',
            status='pending'
        )
        db.session.add(req)
        db.session.flush()

        # Generate Leave Workflow
        workflow, tier, _ = workflow_generator_service.create_workflow_from_text(
            f"Employee requesting {form.days.data} days of leave: validate balance, manager approval, update HR records, finance check, notification",
            user_id=current_user.id
        )
        req.workflow_id = workflow.id
        db.session.commit()

        # Orchestrate execution
        orchestrator.run_workflow(workflow.id, req.id)
        
        flash(f'Leave request submitted! Workflow orchestrated via {tier}.', 'success')
        return redirect(url_for('employee.request_detail', id=req.id))

    return render_template('employee/request_leave.html', form=form)

@employee_bp.route('/request/laptop', methods=['GET', 'POST'])
@login_required
def request_laptop():
    emp = get_or_create_employee(current_user)
    form = LaptopRequestForm()
    
    if form.validate_on_submit():
        desc = f"Hardware Provisioning Request: {form.model_preference.data}. Justification: {form.business_justification.data}"
        title = f"Hardware Request - {form.model_preference.data}"
        
        req = Request(
            employee_id=emp.id,
            type='laptop',
            title=title,
            description=desc,
            priority=form.priority.data,
            status='pending'
        )
        db.session.add(req)
        db.session.flush()

        # Generate Laptop Workflow (Employee -> Manager -> Finance -> Procurement -> IT -> Notification)
        workflow, tier, _ = workflow_generator_service.create_workflow_from_text(
            f"Hardware laptop provisioning request for {form.model_preference.data}: manager approval, finance budget check, procurement order, IT laptop provisioning, notify employee",
            user_id=current_user.id
        )
        req.workflow_id = workflow.id
        db.session.commit()

        # Orchestrate execution
        orchestrator.run_workflow(workflow.id, req.id)

        flash(f'Hardware request submitted! Multi-agent pipeline initiated via {tier}.', 'success')
        return redirect(url_for('employee.request_detail', id=req.id))

    return render_template('employee/request_laptop.html', form=form)

@employee_bp.route('/request/it-ticket', methods=['GET', 'POST'])
@login_required
def request_it_ticket():
    emp = get_or_create_employee(current_user)
    form = ITTicketForm()
    
    if form.validate_on_submit():
        req = Request(
            employee_id=emp.id,
            type='it_ticket',
            title=f"IT Ticket: {form.subject.data}",
            description=form.description.data,
            priority=form.priority.data,
            status='pending'
        )
        db.session.add(req)
        db.session.flush()

        # Generate IT Support Workflow
        workflow, tier, _ = workflow_generator_service.create_workflow_from_text(
            f"IT Support ticket issue '{form.subject.data}': AI categorization, IT engineer resolution, user notification",
            user_id=current_user.id
        )
        req.workflow_id = workflow.id
        db.session.commit()

        # Run orchestrator
        orchestrator.run_workflow(workflow.id, req.id)

        flash(f'IT Support ticket registered and categorized via {tier}!', 'success')
        return redirect(url_for('employee.request_detail', id=req.id))

    return render_template('employee/request_it_ticket.html', form=form)

@employee_bp.route('/request/expense', methods=['GET', 'POST'])
@login_required
def request_expense():
    emp = get_or_create_employee(current_user)
    form = ExpenseClaimForm()
    
    if form.validate_on_submit():
        receipt_filename = None
        extracted_data = {}
        
        # Save file upload if provided
        if form.receipt.data:
            f = form.receipt.data
            safe_name = secure_filename(f.filename)
            receipt_filename = f"receipt_{uuid.uuid4().hex[:8]}_{safe_name}"
            upload_dir = current_app.config.get('UPLOAD_FOLDER', os.path.join(os.getcwd(), 'uploads'))
            os.makedirs(upload_dir, exist_ok=True)
            saved_path = os.path.join(upload_dir, receipt_filename)
            f.save(saved_path)

            # Extract text via OCR
            raw_text = extract_text_from_file(saved_path)
            extracted_data = parse_receipt_data(raw_text, fallback_vendor=form.vendor.data, fallback_amount=float(form.amount.data))

        amount_val = float(form.amount.data)
        vendor_val = form.vendor.data.strip()

        req = Request(
            employee_id=emp.id,
            type='expense',
            title=f"Expense Claim - {vendor_val} (${amount_val:.2f})",
            description=f"Category: {form.category.data}. Purpose: {form.description.data}",
            priority='medium',
            status='pending'
        )
        db.session.add(req)
        db.session.flush()

        claim = ExpenseClaim(
            request_id=req.id,
            amount=amount_val,
            vendor=vendor_val,
            category=form.category.data,
            receipt_path=receipt_filename,
            extracted_json=str(extracted_data)
        )
        db.session.add(claim)

        # Generate Expense Reimbursement Workflow
        workflow, tier, _ = workflow_generator_service.create_workflow_from_text(
            f"Expense reimbursement claim for ${amount_val:.2f} at {vendor_val}: OCR receipt verification, manager approval, finance policy audit, payment disbursement",
            user_id=current_user.id
        )
        req.workflow_id = workflow.id
        db.session.commit()

        # Orchestrate execution
        orchestrator.run_workflow(workflow.id, req.id)

        flash(f'Expense claim processed with OCR verification and dispatched via {tier}!', 'success')
        return redirect(url_for('employee.request_detail', id=req.id))

    return render_template('employee/request_expense.html', form=form)

@employee_bp.route('/request/custom', methods=['POST'])
@login_required
def request_custom():
    emp = get_or_create_employee(current_user)
    form = CustomNLRequestForm()
    
    if form.validate_on_submit():
        prompt_text = form.prompt.data.strip()
        
        req = Request(
            employee_id=emp.id,
            type='custom',
            title=f"AI Request: {prompt_text[:50]}...",
            description=prompt_text,
            priority='medium',
            status='pending'
        )
        db.session.add(req)
        db.session.flush()

        try:
            workflow, tier, meta = workflow_generator_service.create_workflow_from_text(
                prompt_text,
                user_id=current_user.id
            )
            req.workflow_id = workflow.id
            db.session.commit()

            # Execute workflow
            orchestrator.run_workflow(workflow.id, req.id)
            flash(f"AI Workflow '{workflow.name}' dynamically constructed ({tier}) and launched!", 'success')
            return redirect(url_for('employee.request_detail', id=req.id))
        except Exception as e:
            db.session.rollback()
            flash(f"Could not generate workflow: {str(e)}", 'danger')
            return redirect(url_for('employee.dashboard'))

    flash('Please enter a valid request description.', 'warning')
    return redirect(url_for('employee.dashboard'))
