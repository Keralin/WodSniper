import os
from flask import Flask, request, session
from flask_babel import Babel, lazy_gettext as _l
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

from app.config import config
from app.models import db, User

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = _l('Please log in to access this page.')
login_manager.login_message_category = 'info'

migrate = Migrate()
csrf = CSRFProtect()
mail = Mail()
babel = Babel()


def get_locale():
    """Select best language based on user preference or browser."""
    # Check if user has set a language preference
    if 'language' in session:
        return session['language']
    # Fall back to browser's preferred language
    return request.accept_languages.best_match(['es', 'en'], default='es')


def create_app(config_name=None):
    """Application factory."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    mail.init_app(app)
    babel.init_app(app, locale_selector=get_locale)

    # User loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from app.auth import auth_bp
    from app.booking import booking_bp
    from app.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(admin_bp)

    # Register error handlers
    register_error_handlers(app)

    # Make get_locale available in templates
    @app.context_processor
    def inject_locale():
        return {'get_locale': get_locale}

    # Create database tables and run migrations
    with app.app_context():
        db.create_all()
        _run_migrations()

    # Initialize scheduler (only once, gunicorn uses --preload)
    _init_scheduler_once(app)

    return app


def _run_migrations():
    """Run manual database migrations for SQLite."""
    from sqlalchemy import inspect, text
    from app.models import User

    inspector = inspect(db.engine)
    columns = [col['name'] for col in inspector.get_columns('users')]

    # Migration: Add email_verified column if it doesn't exist
    if 'email_verified' not in columns:
        db.session.execute(text('ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 0'))
        # Mark all existing users as verified (so they don't get locked out)
        db.session.execute(text('UPDATE users SET email_verified = 1'))
        db.session.commit()


# Global flag to prevent scheduler from being initialized multiple times
_scheduler_initialized = False


def _init_scheduler_once(app):
    """Initialize scheduler only once (important for gunicorn with multiple workers)."""
    global _scheduler_initialized
    if _scheduler_initialized:
        return

    from app.scheduler import init_scheduler
    with app.app_context():
        init_scheduler(app)
    _scheduler_initialized = True


def register_error_handlers(app):
    """Register error handlers."""
    from flask import render_template
    import traceback

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.error(f'500 Error: {error}')
        app.logger.error(traceback.format_exc())
        return render_template('errors/500.html'), 500
