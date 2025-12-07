"""Tests for WodBuster scraper client."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from app.scraper.client import WodBusterClient
from app.scraper.exceptions import (
    LoginError, ClassNotFoundError, ClassFullError, BookingError
)


class TestWodBusterClientInit:
    """Tests for WodBusterClient initialization."""

    def test_extracts_box_name_from_url(self):
        """Should extract box name from WodBuster URL."""
        client = WodBusterClient('https://mybox.wodbuster.com')
        assert client.box_name == 'mybox'

    def test_extracts_box_name_with_trailing_slash(self):
        """Should handle trailing slash in URL."""
        client = WodBusterClient('https://mybox.wodbuster.com/')
        assert client.box_name == 'mybox'
        assert client.box_url == 'https://mybox.wodbuster.com'

    def test_login_url_includes_box_callback(self):
        """Should build login URL with box callback."""
        client = WodBusterClient('https://mybox.wodbuster.com')
        assert client._get_login_url() == 'https://wodbuster.com/account/login.aspx?cb=mybox'


class TestTokenExtraction:
    """Tests for ASP.NET token extraction."""

    def test_extracts_viewstate_token(self, sample_login_html):
        """Should extract __VIEWSTATE token."""
        client = WodBusterClient('https://test.wodbuster.com')
        tokens = client._extract_form_tokens(sample_login_html)
        assert tokens.get('__VIEWSTATE') == 'viewstate_value'

    def test_extracts_viewstatec_token(self, sample_login_html):
        """Should extract __VIEWSTATEC token."""
        client = WodBusterClient('https://test.wodbuster.com')
        tokens = client._extract_form_tokens(sample_login_html)
        assert tokens.get('__VIEWSTATEC') == 'viewstatec_value'

    def test_extracts_csrf_token(self, sample_login_html):
        """Should extract CSRFToken."""
        client = WodBusterClient('https://test.wodbuster.com')
        tokens = client._extract_form_tokens(sample_login_html)
        assert tokens.get('CSRFToken') == 'csrf_token_value'

    def test_returns_empty_dict_for_empty_html(self):
        """Should return empty dict for empty HTML."""
        client = WodBusterClient('https://test.wodbuster.com')
        tokens = client._extract_form_tokens('')
        assert tokens == {}


class TestLoginErrorDetection:
    """Tests for login error detection."""

    def test_detects_spanish_error(self):
        """Should detect Spanish error message."""
        client = WodBusterClient('https://test.wodbuster.com')
        html = '<div class="error">Usuario o contraseña incorrectos</div>'
        assert client._has_login_error(html) is True

    def test_detects_english_error(self):
        """Should detect English error message."""
        client = WodBusterClient('https://test.wodbuster.com')
        html = '<div class="error">Invalid credentials</div>'
        assert client._has_login_error(html) is True

    def test_no_error_in_clean_html(self):
        """Should return False for HTML without errors."""
        client = WodBusterClient('https://test.wodbuster.com')
        html = '<div>Welcome to WodBuster</div>'
        assert client._has_login_error(html) is False


class TestDeviceConfirmation:
    """Tests for device confirmation detection."""

    def test_detects_device_confirmation_spanish(self):
        """Should detect device confirmation in Spanish."""
        client = WodBusterClient('https://test.wodbuster.com')
        html = '<button>Recordar este dispositivo</button>'
        assert client._needs_device_confirmation(html) is True

    def test_detects_secure_device_button(self):
        """Should detect CtlSeguro button."""
        client = WodBusterClient('https://test.wodbuster.com')
        html = '<input id="CtlSeguro" type="submit" />'
        assert client._needs_device_confirmation(html) is True

    def test_no_confirmation_needed(self):
        """Should return False when no confirmation needed."""
        client = WodBusterClient('https://test.wodbuster.com')
        html = '<div>Dashboard</div>'
        assert client._needs_device_confirmation(html) is False


class TestClassParsing:
    """Tests for class data parsing."""

    @patch.object(WodBusterClient, '_create_session')
    def test_parses_classes_from_new_format(self, mock_create, sample_classes_response):
        """Should parse classes from new API format."""
        import json
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.json.return_value = sample_classes_response
        mock_response.text = json.dumps(sample_classes_response)
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response
        mock_create.return_value = mock_session

        client = WodBusterClient('https://test.wodbuster.com')
        client._logged_in = True

        classes = client.get_classes(datetime(2024, 12, 15))

        assert len(classes) == 2
        assert classes[0]['name'] == 'CrossFit'
        assert classes[0]['time'] == '07:00'
        assert classes[1]['name'] == 'Hyrox'

    @patch.object(WodBusterClient, '_create_session')
    def test_find_class_by_time_and_type(self, mock_create, sample_classes_response):
        """Should find class by time and type."""
        import json
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.json.return_value = sample_classes_response
        mock_response.text = json.dumps(sample_classes_response)
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response
        mock_create.return_value = mock_session

        client = WodBusterClient('https://test.wodbuster.com')
        client._logged_in = True

        cls = client.find_class(datetime(2024, 12, 15), '07:00', 'crossfit')

        assert cls is not None
        assert cls['id'] == 123
        assert cls['name'] == 'CrossFit'

    @patch.object(WodBusterClient, '_create_session')
    def test_find_class_returns_none_when_not_found(self, mock_create, sample_classes_response):
        """Should return None when class not found."""
        import json
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.json.return_value = sample_classes_response
        mock_response.text = json.dumps(sample_classes_response)
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response
        mock_create.return_value = mock_session

        client = WodBusterClient('https://test.wodbuster.com')
        client._logged_in = True

        cls = client.find_class(datetime(2024, 12, 15), '09:00', 'yoga')

        assert cls is None


class TestBooking:
    """Tests for booking functionality."""

    @patch.object(WodBusterClient, '_create_session')
    def test_book_class_success(self, mock_create, sample_booking_success):
        """Should return True on successful booking."""
        import json
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.json.return_value = sample_booking_success
        mock_response.text = json.dumps(sample_booking_success)
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response
        mock_create.return_value = mock_session

        client = WodBusterClient('https://test.wodbuster.com')
        client._logged_in = True

        result = client.book_class(123)

        assert result is True

    @patch.object(WodBusterClient, '_create_session')
    def test_book_class_raises_class_full(self, mock_create, sample_booking_full):
        """Should raise ClassFullError when class is full."""
        import json
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.json.return_value = sample_booking_full
        mock_response.text = json.dumps(sample_booking_full)
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response
        mock_create.return_value = mock_session

        client = WodBusterClient('https://test.wodbuster.com')
        client._logged_in = True

        with pytest.raises(ClassFullError):
            client.book_class(123)


class TestSessionManagement:
    """Tests for session management."""

    @patch.object(WodBusterClient, '_create_session')
    @patch.object(WodBusterClient, '_verify_login')
    def test_restore_session_with_valid_cookies(self, mock_verify, mock_create):
        """Should restore session with valid cookies."""
        mock_create.return_value = MagicMock()
        mock_verify.return_value = True

        client = WodBusterClient('https://test.wodbuster.com')
        cookies = {'.WBAuth': 'valid_cookie'}

        result = client.restore_session(cookies)

        assert result is True
        assert client._logged_in is True

    @patch.object(WodBusterClient, '_create_session')
    @patch.object(WodBusterClient, '_verify_login')
    def test_restore_session_with_invalid_cookies(self, mock_verify, mock_create):
        """Should fail to restore session with invalid cookies."""
        mock_create.return_value = MagicMock()
        mock_verify.return_value = False

        client = WodBusterClient('https://test.wodbuster.com')
        cookies = {'.WBAuth': 'invalid_cookie'}

        result = client.restore_session(cookies)

        assert result is False

    @patch.object(WodBusterClient, '_create_session')
    def test_get_cookies_returns_dict(self, mock_create):
        """Should return cookies as dict."""
        mock_session = MagicMock()
        mock_session.cookies = {'.WBAuth': 'test', 'cf_clearance': 'cf_test'}
        mock_create.return_value = mock_session

        client = WodBusterClient('https://test.wodbuster.com')
        cookies = client.get_cookies()

        assert isinstance(cookies, dict)
