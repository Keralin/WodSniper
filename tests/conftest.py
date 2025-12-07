"""Pytest fixtures for WodSniper tests."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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
