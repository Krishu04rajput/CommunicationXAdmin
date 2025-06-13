import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from urllib.parse import urlparse

# Configure logging with reduced verbosity for performance
logging.basicConfig(
    level=logging.WARNING,  # Reduced from INFO to WARNING
    format='%(levelname)s - %(message)s'  # Simplified format
)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Security configurations
app.config['WTF_CSRF_ENABLED'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour

# Use SQLite for reliable local development
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///communicationx.db"

app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Simplified rate limiting for better performance
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["1000 per hour"]  # Simplified single limit
)

# Initialize extensions
db.init_app(app)
socketio = SocketIO(app, 
                   cors_allowed_origins="*", 
                   async_mode='threading',
                   logger=False, 
                   engineio_logger=False,
                   ping_timeout=60,
                   ping_interval=25)

# Force database initialization with all new models
def init_database():
    """Initialize database tables with all Discord-like features"""
    with app.app_context():
        try:
            # Import all models to register them
            import models  # noqa: F401
            
            # Drop all tables and recreate to ensure new schema
            db.drop_all()
            db.create_all()
            
            # Database tables created successfully
            logging.warning("Database tables created successfully")
            
            db.session.commit()
            logging.warning("Database recreated with Discord-like features")
            
        except Exception as e:
            logging.error(f"Database initialization error: {e}")

# Initialize database immediately
init_database()
