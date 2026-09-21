from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db
from models import User, Department, Employee, LeaveBalance
from blueprints.auth.forms import LoginForm, RegisterForm

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

def get_role_dashboard_url(role: str) -> str:
    """Returns corresponding dashboard route for a given user role."""
    role = (role or 'employee').lower()
    mapping = {
        'employee': 'employee.dashboard',
        'manager': 'manager.dashboard',
        'hr': 'hr.dashboard',
        'it': 'it.dashboard',
        'finance': 'finance.dashboard',
        'procurement': 'procurement.dashboard',
        'admin': 'admin.dashboard'
    }
    return mapping.get(role, 'employee.dashboard')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(get_role_dashboard_url(current_user.role)))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('Your account has been deactivated. Please contact an administrator.', 'danger')
                return render_template('auth/login.html', form=form)
            
            login_user(user)
            flash(f'Welcome back, {user.name} ({user.role.title()})!', 'success')
            next_page = request.args.get('next')
            if next_page and not next_page.startswith('//') and not next_page.startswith('http'):
                return redirect(next_page)
            return redirect(url_for(get_role_dashboard_url(user.role)))
        else:
            flash('Invalid email address or password. Please try again.', 'danger')

    return render_template('auth/login.html', form=form)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for(get_role_dashboard_url(current_user.role)))

    form = RegisterForm()
    departments = Department.query.order_by(Department.name).all()
    form.department_id.choices = [(d.id, d.name) for d in departments]

    if form.validate_on_submit():
        existing = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if existing:
            flash('An account with this email address already exists.', 'danger')
            return render_template('auth/register.html', form=form)

        user = User(
            name=form.name.data.strip(),
            email=form.email.data.strip().lower(),
            role=form.role.data,
            department_id=form.department_id.data,
            is_active=True
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()

        # Create Employee profile
        emp = Employee(
            user_id=user.id,
            designation=form.designation.data.strip() or 'Associate'
        )
        db.session.add(emp)
        db.session.flush()

        # Seed initial leave balances
        for l_type, days in [('Annual', 20.0), ('Casual', 10.0), ('Sick', 12.0)]:
            lb = LeaveBalance(employee_id=emp.id, leave_type=l_type, total_days=days, used_days=0.0)
            db.session.add(lb)

        db.session.commit()
        flash('Account registered successfully! You can now log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been securely signed out.', 'info')
    return redirect(url_for('auth.login'))
