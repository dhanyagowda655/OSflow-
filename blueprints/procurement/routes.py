from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import db, roles_required
from models import Request, Asset, Notification

procurement_bp = Blueprint('procurement', __name__, url_prefix='/procurement')

@procurement_bp.route('/dashboard')
@login_required
@roles_required('procurement', 'admin')
def dashboard():
    hardware_reqs = Request.query.filter_by(type='laptop').order_by(Request.created_at.desc()).all()
    pending_orders = [r for r in hardware_reqs if r.status in ('pending', 'in_progress')]
    fulfilled_orders = [r for r in hardware_reqs if r.status == 'completed']

    return render_template(
        'procurement/dashboard.html',
        pending_orders=pending_orders,
        fulfilled_orders=fulfilled_orders,
        hardware_reqs=hardware_reqs
    )

@procurement_bp.route('/orders')
@login_required
@roles_required('procurement', 'admin')
def orders_list():
    hardware_reqs = Request.query.filter_by(type='laptop').order_by(Request.created_at.desc()).all()
    return render_template('procurement/orders.html', orders=hardware_reqs)

@procurement_bp.route('/fulfill/<int:id>', methods=['POST'])
@login_required
@roles_required('procurement', 'admin')
def fulfill_order(id):
    req = Request.query.get_or_404(id)
    carrier = request.form.get('carrier', 'Express Enterprise Courier')
    tracking = request.form.get('tracking_num', 'TRK-982341-US')

    if req.workflow:
        for s in req.workflow.steps:
            if s.agent_type == 'procurement' and s.status != 'done':
                s.status = 'done'
                s.result_text = f"Procurement Specialist: Dispatched via {carrier} (Tracking: {tracking})."
        db.session.commit()

    if req.employee and req.employee.user:
        notif = Notification(
            user_id=req.employee.user.id,
            message=f"Hardware Order #{req.id} has been DISPATCHED via {carrier} (Tracking: {tracking}).",
            link=f"/employee/requests/{req.id}"
        )
        db.session.add(notif)
        db.session.commit()

    flash(f"Hardware Order #{req.id} marked as fulfilled and in transit.", 'success')
    return redirect(url_for('procurement.orders_list'))
