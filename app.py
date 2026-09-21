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
    """Fallback seeder to ensure all 7 roles work on cloud deployment."""
    from models import Department, User, Employee, LeaveBalance
    with app.app_context():
        depts = ['Engineering', 'Human Resources', 'Finance & Operations', 'IT Infrastructure']
        dept_map = {}
        for d in depts:
            dept = Department.query.filter_by(name=d).first()
            if not dept:
                dept = Department(name=d)
                db.session.add(dept)
                db.session.flush()
            dept_map[d] = dept

        demo_users = [
            {'email': 'employee@flowos.demo', 'name': 'Alex Rivera', 'role': 'employee', 'dept': 'Engineering', 'desig': 'Software Engineer'},
            {'email': 'manager@flowos.demo', 'name': 'Sarah Connor', 'role': 'manager', 'dept': 'Engineering', 'desig': 'Engineering Director'},
            {'email': 'hr@flowos.demo', 'name': 'Emma Watson', 'role': 'hr', 'dept': 'Human Resources', 'desig': 'HR Specialist'},
            {'email': 'it@flowos.demo', 'name': 'David Miller', 'role': 'it', 'dept': 'IT Infrastructure', 'desig': 'Lead Systems Engineer'},
            {'email': 'finance@flowos.demo', 'name': 'Michael Chang', 'role': 'finance', 'dept': 'Finance & Operations', 'desig': 'Chief Financial Controller'},
            {'email': 'procurement@flowos.demo', 'name': 'Rachel Green', 'role': 'procurement', 'dept': 'Finance & Operations', 'desig': 'Procurement Officer'},
            {'email': 'admin@flowos.demo', 'name': 'Admin Superuser', 'role': 'admin', 'dept': 'IT Infrastructure', 'desig': 'Enterprise Systems Admin'},
        ]

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

                emp = Employee(
                    user_id=u.id,
                    designation=acc['desig'],
                    joining_date=datetime.now(timezone.utc).date() if 'datetime' in globals() else None
                )
                db.session.add(emp)
                db.session.flush()
                db.session.add(LeaveBalance(employee_id=emp.id, annual_leave=20, sick_leave=10, casual_leave=7))

        db.session.commit()

# Expose app for WSGI servers like Gunicorn
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

