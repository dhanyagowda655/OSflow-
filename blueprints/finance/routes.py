from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import db, roles_required
from models import Request, ExpenseClaim, Notification

finance_bp = Blueprint('finance', __name__, url_prefix='/finance')

@finance_bp.route('/dashboard')
@login_required
@roles_required('finance', 'admin')
def dashboard():
    claims = ExpenseClaim.query.all()
    total_amount = sum(c.amount for c in claims)
    pending_claims = ExpenseClaim.query.join(ExpenseClaim.request).filter(Request.status.in_(['pending', 'in_progress'])).all()
    duplicate_flags = [c for c in claims if c.duplicate_flag]

    recent_expenses = Request.query.filter_by(type='expense').order_by(Request.created_at.desc()).limit(8).all()

    return render_template(
        'finance/dashboard.html',
        total_amount=total_amount,
        pending_claims=pending_claims,
        duplicate_flags=duplicate_flags,
        recent_expenses=recent_expenses
    )

@finance_bp.route('/claims')
@login_required
@roles_required('finance', 'admin')
def claims_list():
    claims = ExpenseClaim.query.order_by(ExpenseClaim.id.desc()).all()
    return render_template('finance/claims.html', claims=claims)

@finance_bp.route('/settle/<int:id>', methods=['POST'])
@login_required
@roles_required('finance', 'admin')
def settle_claim(id):
    claim = ExpenseClaim.query.get_or_404(id)
    notes = request.form.get('notes', 'Payment disbursed via direct bank transfer.')
    
    if claim.request:
        claim.request.status = 'completed'
        if claim.request.workflow:
            for s in claim.request.workflow.steps:
                if s.status != 'done':
                    s.status = 'done'
                    s.result_text = f"Finance Officer Disbursement: {notes}"
            claim.request.workflow.status = 'completed'

        if claim.request.employee and claim.request.employee.user:
            notif = Notification(
                user_id=claim.request.employee.user.id,
                message=f"Expense Claim #{claim.id} for ${claim.amount:.2f} ({claim.vendor}) has been SETTLED and disbursed to your bank account.",
                link=f"/employee/requests/{claim.request_id}"
            )
            db.session.add(notif)

    db.session.commit()
    flash(f"Claim #{claim.id} settled. Payment disbursed.", 'success')
    return redirect(url_for('finance.claims_list'))
