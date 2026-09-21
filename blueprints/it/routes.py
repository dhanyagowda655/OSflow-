import uuid
from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import db, roles_required
from models import Request, Asset, Employee, User, Notification

it_bp = Blueprint('it', __name__, url_prefix='/it')

@it_bp.route('/dashboard')
@login_required
@roles_required('it', 'admin')
def dashboard():
    open_tickets = Request.query.filter_by(type='it_ticket', status='in_progress').count()
    pending_laptops = Request.query.filter_by(type='laptop', status='in_progress').count()
    total_assets = Asset.query.count()
    in_stock_assets = Asset.query.filter_by(status='in_stock').count()

    recent_tickets = Request.query.filter_by(type='it_ticket').order_by(Request.created_at.desc()).limit(6).all()
    hardware_requests = Request.query.filter_by(type='laptop').order_by(Request.created_at.desc()).limit(6).all()

    return render_template(
        'it/dashboard.html',
        open_tickets=open_tickets,
        pending_laptops=pending_laptops,
        total_assets=total_assets,
        in_stock_assets=in_stock_assets,
        recent_tickets=recent_tickets,
        hardware_requests=hardware_requests
    )

@it_bp.route('/tickets')
@login_required
@roles_required('it', 'admin')
def tickets_list():
    status = request.args.get('status')
    query = Request.query.filter_by(type='it_ticket')
    if status:
        query = query.filter_by(status=status)
    tickets = query.order_by(Request.created_at.desc()).all()
    return render_template('it/tickets.html', tickets=tickets)

@it_bp.route('/tickets/<int:id>/resolve', methods=['POST'])
@login_required
@roles_required('it', 'admin')
def resolve_ticket(id):
    req = Request.query.get_or_404(id)
    notes = request.form.get('resolution_notes', 'Resolved by IT Engineer')
    
    req.status = 'completed'
    if req.workflow:
        for s in req.workflow.steps:
            if s.status != 'done':
                s.status = 'done'
                s.result_text = f"IT Engineer Action: {notes}"
        req.workflow.status = 'completed'

    if req.employee and req.employee.user:
        notif = Notification(
            user_id=req.employee.user.id,
            message=f"IT Ticket #{req.id} ({req.title}) has been RESOLVED by IT Specialist {current_user.name}.",
            link=f"/employee/requests/{req.id}"
        )
        db.session.add(notif)

    db.session.commit()
    flash(f"IT Ticket #{req.id} marked as resolved.", 'success')
    return redirect(url_for('it.tickets_list'))

@it_bp.route('/assets', methods=['GET', 'POST'])
@login_required
@roles_required('it', 'admin')
def assets_list():
    if request.method == 'POST':
        asset_type = request.form.get('type', 'Laptop')
        model_name = request.form.get('model_name', 'MacBook Pro 14"')
        serial = request.form.get('serial_number') or f"SN-{uuid.uuid4().hex[:8].upper()}"

        existing = Asset.query.filter_by(serial_number=serial).first()
        if existing:
            flash('An asset with this serial number already exists.', 'danger')
        else:
            new_asset = Asset(
                type=asset_type,
                model_name=model_name,
                serial_number=serial,
                status='in_stock'
            )
            db.session.add(new_asset)
            db.session.commit()
            flash(f"Asset [{model_name} (S/N: {serial})] added to inventory.", 'success')
        return redirect(url_for('it.assets_list'))

    assets = Asset.query.order_by(Asset.id.desc()).all()
    employees = Employee.query.all()
    return render_template('it/assets.html', assets=assets, employees=employees)
