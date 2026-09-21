import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

class Config:
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'flowos-default-secret-key-384918237')
    _raw_db_url = os.getenv('DATABASE_URL', f"sqlite:///{BASE_DIR / 'flowos.db'}")
    # Render PostgreSQL URLs start with postgres://, which SQLAlchemy 2.0 requires as postgresql://
    if _raw_db_url.startswith('postgres://'):
        _raw_db_url = _raw_db_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = _raw_db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload settings
    UPLOAD_FOLDER = BASE_DIR / 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max limit
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'txt', 'csv'}
    
    # AI API Keys
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '').strip()
    MISTRAL_API_KEY = os.getenv('MISTRAL_API_KEY', '').strip()
    
    # Mail settings
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', '')
    MAIL_APP_PASSWORD = os.getenv('MAIL_APP_PASSWORD', '')
    MAIL_ENABLED = os.getenv('MAIL_ENABLED', 'false').lower() in ('true', '1', 't', 'yes')

    # Security & Sessions
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    WTF_CSRF_TIME_LIMIT = 3600
