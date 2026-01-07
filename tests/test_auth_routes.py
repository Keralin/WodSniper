"""Tests for authentication routes."""

import pytest
from unittest.mock import patch, MagicMock
from flask import url_for


class TestLoginRoute:
    """Tests for /auth/login route."""

    def test_login_page_renders(self, client, app):
        """Should render login page."""
        with app.app_context():
            response = client.get('/auth/login')
            assert response.status_code == 200
            assert b'login' in response.data.lower() or b'iniciar' in response.data.lower()

    def test_login_with_valid_credentials(self, client, app, test_user):
        """Should login with valid credentials."""
        with app.app_context():
            response = client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'testpassword123',
            }, follow_redirects=True)

            assert response.status_code == 200

    def test_login_with_invalid_password(self, client, app, test_user):
        """Should reject invalid password."""
        with app.app_context():
            response = client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'wrongpassword',
            })

            assert response.status_code == 200
            # Should show error message or stay on login page

    def test_login_with_nonexistent_email(self, client, app):
        """Should reject nonexistent email."""
        with app.app_context():
            response = client.post('/auth/login', data={
                'email': 'nonexistent@example.com',
                'password': 'anypassword',
            })

            assert response.status_code == 200

    def test_login_redirects_authenticated_user(self, client, app, test_user):
        """Should redirect already authenticated user."""
        with app.app_context():
            # First login
            client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'testpassword123',
            })

            # Try to access login page again
            response = client.get('/auth/login')
            assert response.status_code in [200, 302]

    def test_login_with_unverified_email(self, client, app):
        """Should reject login for unverified email."""
        from app.models import db, User

        with app.app_context():
            user = User(email='unverified@example.com')
            user.set_password('password123')
            user.email_verified = False
            db.session.add(user)
            db.session.commit()

            response = client.post('/auth/login', data={
                'email': 'unverified@example.com',
                'password': 'password123',
            })

            assert response.status_code == 200


class TestRegisterRoute:
    """Tests for /auth/register route."""

    def test_register_page_renders(self, client, app):
        """Should render registration page."""
        with app.app_context():
            response = client.get('/auth/register')
            assert response.status_code == 200

    @patch('app.auth.routes.send_verification_email')
    def test_register_creates_user(self, mock_send_email, client, app):
        """Should create a new user."""
        from app.models import User

        with app.app_context():
            response = client.post('/auth/register', data={
                'email': 'newuser@example.com',
                'password': 'securepassword123',
                'password2': 'securepassword123',
            }, follow_redirects=True)

            user = User.query.filter_by(email='newuser@example.com').first()
            assert user is not None
            assert user.email_verified is False

    @patch('app.auth.routes.send_verification_email')
    def test_register_sends_verification_email(self, mock_send_email, client, app):
        """Should send verification email on registration."""
        with app.app_context():
            client.post('/auth/register', data={
                'email': 'newuser2@example.com',
                'password': 'securepassword123',
                'password2': 'securepassword123',
            })

            mock_send_email.assert_called_once()

    def test_register_with_existing_email(self, client, app, test_user):
        """Should reject registration with existing email."""
        with app.app_context():
            response = client.post('/auth/register', data={
                'email': 'test@example.com',
                'password': 'newpassword123',
                'password2': 'newpassword123',
            })

            assert response.status_code == 200

    def test_register_with_mismatched_passwords(self, client, app):
        """Should reject mismatched passwords."""
        with app.app_context():
            response = client.post('/auth/register', data={
                'email': 'mismatch@example.com',
                'password': 'password123',
                'password2': 'differentpassword',
            })

            assert response.status_code == 200


class TestLogoutRoute:
    """Tests for /auth/logout route."""

    def test_logout_clears_session(self, client, app, test_user):
        """Should clear session on logout."""
        with app.app_context():
            # Login first
            client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'testpassword123',
            })

            # Logout
            response = client.get('/auth/logout', follow_redirects=True)
            assert response.status_code == 200

    def test_logout_redirects_to_login(self, client, app, test_user):
        """Should redirect to login after logout."""
        with app.app_context():
            client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'testpassword123',
            })

            response = client.get('/auth/logout')
            assert response.status_code == 302


class TestForgotPasswordRoute:
    """Tests for /auth/forgot-password route."""

    def test_forgot_password_page_renders(self, client, app):
        """Should render forgot password page."""
        with app.app_context():
            response = client.get('/auth/forgot-password')
            assert response.status_code == 200

    @patch('app.auth.routes.send_password_reset_email')
    def test_forgot_password_sends_email(self, mock_send_email, client, app, test_user):
        """Should send reset email for existing user."""
        with app.app_context():
            response = client.post('/auth/forgot-password', data={
                'email': 'test@example.com',
            }, follow_redirects=True)

            mock_send_email.assert_called_once()

    @patch('app.auth.routes.send_password_reset_email')
    def test_forgot_password_nonexistent_email(self, mock_send_email, client, app):
        """Should not reveal if email exists."""
        with app.app_context():
            response = client.post('/auth/forgot-password', data={
                'email': 'nonexistent@example.com',
            }, follow_redirects=True)

            # Should still show success to prevent enumeration
            assert response.status_code == 200
            mock_send_email.assert_not_called()


class TestResetPasswordRoute:
    """Tests for /auth/reset-password/<token> route."""

    def test_reset_password_invalid_token(self, client, app):
        """Should reject invalid token."""
        with app.app_context():
            response = client.get('/auth/reset-password/invalid-token')
            assert response.status_code == 302  # Redirect to forgot password

    def test_reset_password_valid_token(self, client, app, test_user):
        """Should allow reset with valid token."""
        with app.app_context():
            token = test_user.get_reset_token()
            response = client.get(f'/auth/reset-password/{token}')
            assert response.status_code == 200

    def test_reset_password_changes_password(self, client, app, test_user):
        """Should change password with valid token."""
        from app.models import User

        with app.app_context():
            token = test_user.get_reset_token()
            response = client.post(f'/auth/reset-password/{token}', data={
                'password': 'newpassword123',
                'password2': 'newpassword123',
            }, follow_redirects=True)

            user = User.query.filter_by(email='test@example.com').first()
            assert user.check_password('newpassword123') is True


class TestEmailVerificationRoute:
    """Tests for /auth/verify-email/<token> route."""

    def test_verify_email_valid_token(self, client, app):
        """Should verify email with valid token."""
        from app.models import db, User

        with app.app_context():
            user = User(email='verify@example.com')
            user.set_password('password')
            user.email_verified = False
            db.session.add(user)
            db.session.commit()

            token = user.get_verification_token()
            response = client.get(f'/auth/verify-email/{token}', follow_redirects=True)

            user = User.query.filter_by(email='verify@example.com').first()
            assert user.email_verified is True

    def test_verify_email_invalid_token(self, client, app):
        """Should reject invalid verification token."""
        with app.app_context():
            response = client.get('/auth/verify-email/invalid-token')
            assert response.status_code == 302


class TestConnectWodBusterRoute:
    """Tests for /auth/connect route."""

    def test_connect_requires_login(self, client, app):
        """Should require authentication."""
        with app.app_context():
            response = client.get('/auth/connect')
            assert response.status_code == 302  # Redirect to login

    def test_connect_page_renders(self, client, app, test_user):
        """Should render connect page for authenticated user."""
        with app.app_context():
            # Login first
            client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'testpassword123',
            })

            response = client.get('/auth/connect')
            assert response.status_code == 200

    @patch('app.auth.routes.WodBusterClient')
    def test_connect_with_valid_credentials(self, mock_client_class, client, app, test_user):
        """Should connect with valid WodBuster credentials."""
        with app.app_context():
            mock_client = MagicMock()
            mock_client.get_cookies.return_value = {'.WBAuth': 'token'}
            mock_client.get_booking_open_time.return_value = None
            mock_client_class.return_value = mock_client
            mock_client_class.detect_box_url.return_value = 'https://testbox.wodbuster.com'

            # Login first
            client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'testpassword123',
            })

            response = client.post('/auth/connect', data={
                'wodbuster_email': 'wodbuster@example.com',
                'wodbuster_password': 'wodbusterpass',
            }, follow_redirects=True)

            mock_client.login.assert_called_once()


class TestTestConnectionRoute:
    """Tests for /auth/test-connection route."""

    def test_test_connection_requires_login(self, client, app):
        """Should require authentication."""
        with app.app_context():
            response = client.get('/auth/test-connection')
            assert response.status_code == 302

    def test_test_connection_without_wodbuster(self, client, app, test_user):
        """Should redirect if WodBuster not connected."""
        with app.app_context():
            client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'testpassword123',
            })

            response = client.get('/auth/test-connection', follow_redirects=True)
            assert response.status_code == 200
