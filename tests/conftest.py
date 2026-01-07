"""Pytest fixtures for WodSniper tests."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
import tempfile
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def app():
    """Create Flask application for testing."""
    from app import create_app
    from app.models import db

    # Create a temporary database file
    db_fd, db_path = tempfile.mkstemp()

    app = create_app('testing')
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
        'WTF_CSRF_ENABLED': False,
        'SECRET_KEY': 'test-secret-key',
        'SERVER_NAME': 'localhost',
    })

    with app.app_context():
        db.create_all()

    yield app

    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create test CLI runner."""
    return app.test_cli_runner()


@pytest.fixture
def db_session(app):
    """Create database session for testing."""
    from app.models import db

    with app.app_context():
        yield db.session
        db.session.rollback()


@pytest.fixture
def test_user(app):
    """Create a test user."""
    from app.models import db, User

    with app.app_context():
        user = User(email='test@example.com')
        user.set_password('testpassword123')
        user.email_verified = True
        db.session.add(user)
        db.session.commit()
        yield user


@pytest.fixture
def authenticated_client(app, client, test_user):
    """Create an authenticated test client."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(test_user.id)
        sess['_fresh'] = True
    return client


@pytest.fixture
def mock_session():
    """Mock cloudscraper session."""
    session = MagicMock()
    session.cookies = MagicMock()
    session.cookies.keys.return_value = ['.WBAuth', 'cf_clearance']
    session.cookies.__iter__ = lambda self: iter([
        Mock(name='.WBAuth', value='test', domain='.wodbuster.com', path='/'),
    ])
    return session


@pytest.fixture
def sample_login_html():
    """Sample WodBuster login page HTML."""
    return '''
    <html>
    <body>
        <form>
            <input type="hidden" name="__VIEWSTATE" value="viewstate_value" />
            <input type="hidden" name="__VIEWSTATEC" value="viewstatec_value" />
            <input type="hidden" name="__EVENTVALIDATION" value="eventval_value" />
            <input type="hidden" name="CSRFToken" value="csrf_token_value" />
            <input type="text" name="ctl00$ctl00$body$body$CtlLogin$IoEmail" />
            <input type="password" name="ctl00$ctl00$body$body$CtlLogin$IoPassword" />
        </form>
    </body>
    </html>
    '''


@pytest.fixture
def sample_classes_response():
    """Sample WodBuster classes API response."""
    return {
        'Data': [
            {
                'Hora': '07:00',
                'Valores': [
                    {
                        'TipoEstado': 'Inscribible',
                        'Valor': {
                            'Id': 123,
                            'Nombre': 'CrossFit',
                            'HoraComienzo': '07:00',
                            'Plazas': 20,
                            'AtletasEntrenando': []
                        }
                    }
                ]
            },
            {
                'Hora': '08:00',
                'Valores': [
                    {
                        'TipoEstado': 'Inscribible',
                        'Valor': {
                            'Id': 124,
                            'Nombre': 'Hyrox',
                            'HoraComienzo': '08:00',
                            'Plazas': 15,
                            'AtletasEntrenando': []
                        }
                    }
                ]
            }
        ],
        'Title': '2024-12-15'
    }


@pytest.fixture
def sample_booking_success():
    """Sample successful booking response."""
    return {
        'Res': {
            'EsCorrecto': True,
            'ErrorMsg': ''
        }
    }


@pytest.fixture
def sample_booking_full():
    """Sample class full response."""
    return {
        'Res': {
            'EsCorrecto': False,
            'ErrorMsg': 'Clase completa'
        }
    }


@pytest.fixture
def mock_booking():
    """Mock Booking model."""
    booking = Mock()
    booking.id = 1
    booking.day_of_week = 0  # Monday
    booking.time = '07:00'
    booking.class_type = 'crossfit'
    booking.day_name = 'Monday'
    booking.is_active = True
    booking.status = 'pending'
    booking.success_count = 0
    booking.fail_count = 0
    booking.last_error = None
    booking.last_attempt = None
    return booking


@pytest.fixture
def mock_user():
    """Mock User model."""
    user = Mock()
    user.id = 1
    user.email = 'test@example.com'
    user.box_url = 'https://testbox.wodbuster.com'
    user.wodbuster_email = 'test@wodbuster.com'
    user.get_wodbuster_cookies.return_value = {'.WBAuth': 'test_cookie'}
    user.get_wodbuster_password.return_value = 'test_password'
    return user
