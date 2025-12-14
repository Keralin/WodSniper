import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///wodsniper.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # WodBuster settings
    WODBUSTER_BASE_URL = 'https://wodbuster.com'
    WODBUSTER_LOGIN_URL = f'{WODBUSTER_BASE_URL}/account/login.aspx'

    # Booking settings
    BOOKING_CHECK_INTERVAL = 30  # seconds
    MAX_BOOKING_RETRIES = 20
    REQUEST_TIMEOUT = 10  # seconds

    # FlareSolverr settings (for Cloudflare bypass)
    FLARESOLVERR_URL = os.environ.get('FLARESOLVERR_URL', None)  # e.g., http://flaresolverr:8191/v1

    # Babel settings (i18n)
    LANGUAGES = ['es', 'en']
    BABEL_DEFAULT_LOCALE = 'es'
    BABEL_DEFAULT_TIMEZONE = 'Europe/Madrid'

    # Email settings (Resend)
    RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
    RESEND_FROM_EMAIL = os.environ.get('RESEND_FROM_EMAIL', 'WodSniper <onboarding@resend.dev>')


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
