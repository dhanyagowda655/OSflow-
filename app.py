import os
import logging
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
            from models import User
            if User.query.count() == 0:
                from seed import seed_database
                seed_database(app)
        except Exception as e:
            app.logger.warning(f"Auto-seed check note: {e}")

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='127.0.0.1', port=5000, debug=True)
