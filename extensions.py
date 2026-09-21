from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'

def roles_required(*roles):
    """
    Decorator for route functions to enforce role-based access control.
    Pass allowed role names (case-insensitive) as strings, e.g. @roles_required('admin', 'hr')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            
            user_role = (current_user.role or '').strip().lower()
            normalized_roles = [r.strip().lower() for r in roles]
            
            # Admin role can access anything
            if 'admin' in normalized_roles and user_role == 'admin':
                return f(*args, **kwargs)
                
            if user_role not in normalized_roles and user_role != 'admin':
                flash('Access denied. You do not have the required permissions for this portal.', 'danger')
                abort(403)
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator
