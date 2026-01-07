"""Tests for booking routes."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta


class TestIndexRoute:
    """Tests for / route."""

    def test_index_renders_for_anonymous(self, client, app):
        """Should render landing page for anonymous users."""
        with app.app_context():
            response = client.get('/')
            assert response.status_code == 200

    def test_index_redirects_authenticated(self, client, app, test_user):
        """Should redirect authenticated users to dashboard."""
        with app.app_context():
            client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'testpassword123',
            })

            response = client.get('/')
            assert response.status_code == 302


class TestDashboardRoute:
    """Tests for /dashboard route."""

    def test_dashboard_requires_login(self, client, app):
        """Should require authentication."""
        with app.app_context():
            response = client.get('/dashboard')
            assert response.status_code == 302

    def test_dashboard_renders_for_authenticated(self, client, app, test_user):
        """Should render dashboard for authenticated users."""
        with app.app_context():
            client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'testpassword123',
            })

            response = client.get('/dashboard')
            assert response.status_code == 200

    def test_dashboard_shows_user_bookings(self, client, app, test_user):
        """Should display user's bookings."""
        from app.models import db, Booking

        with app.app_context():
            booking = Booking(
                user_id=test_user.id,
                day_of_week=0,
                time='07:00',
                class_type='CrossFit'
            )
            db.session.add(booking)
            db.session.commit()

            client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'testpassword123',
            })

            response = client.get('/dashboard')
            assert response.status_code == 200
            assert b'CrossFit' in response.data or b'07:00' in response.data


class TestNewBookingRoute:
    """Tests for /new route."""

    def test_new_booking_requires_login(self, client, app):
        """Should require authentication."""
        with app.app_context():
            response = client.get('/new')
            assert response.status_code == 302

    def test_new_booking_requires_wodbuster(self, client, app, test_user):
        """Should redirect if WodBuster not connected."""
        with app.app_context():
            client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'testpassword123',
            })

            response = client.get('/new', follow_redirects=True)
            assert response.status_code == 200

    def test_new_booking_page_renders(self, client, app, test_user):
        """Should render new booking page."""
        from app.models import db, User

        with app.app_context():
            # Re-query user in this context
            user = User.query.filter_by(email='test@example.com').first()
            user.box_url = 'https://test.wodbuster.com'
            user.set_wodbuster_cookies({'.WBAuth': 'test'})
            db.session.commit()

            client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'testpassword123',
            })

            response = client.get('/new')
            assert response.status_code == 200

    def test_create_booking(self, client, app, test_user):
        """Should create a new booking."""
        from app.models import db, User, Booking

        with app.app_context():
            # Re-query user in this context
            user = User.query.filter_by(email='test@example.com').first()
            user.box_url = 'https://test.wodbuster.com'
            user.set_wodbuster_cookies({'.WBAuth': 'test'})
            db.session.commit()
            user_id = user.id

            client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'testpassword123',
            })

            response = client.post('/new', data={
                'day_of_week': '0',
                'time': '07:00',
                'class_type': 'CrossFit',
            }, follow_redirects=True)

            booking = Booking.query.filter_by(user_id=user_id).first()
            assert booking is not None
            assert booking.day_of_week == 0
            assert booking.time == '07:00'

    def test_prevent_duplicate_booking(self, client, app, test_user):
        """Should prevent duplicate bookings."""
        from app.models import db, Booking

        with app.app_context():
            test_user.box_url = 'https://test.wodbuster.com'

            # Create existing booking
            booking = Booking(
                user_id=test_user.id,
                day_of_week=0,
                time='07:00',
                class_type='CrossFit'
            )
            db.session.add(booking)
            db.session.commit()

            client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'testpassword123',
            })

            response = client.post('/new', data={
                'day_of_week': '0',
                'time': '07:00',
                'class_type': 'CrossFit',
            })

            # Should show error, not create duplicate
            count = Booking.query.filter_by(
                user_id=test_user.id,
                day_of_week=0,
                time='07:00',
                class_type='CrossFit'
            ).count()
            assert count == 1


class TestToggleBookingRoute:
    """Tests for /toggle/<id> route."""

    def test_toggle_requires_login(self, client, app):
        """Should require authentication."""
        with app.app_context():
            response = client.post('/toggle/1')
            assert response.status_code == 302

    def test_toggle_booking_status(self, client, app, test_user):
        """Should toggle booking active status."""
        from app.models import db, Booking

        with app.app_context():
            booking = Booking(
                user_id=test_user.id,
                day_of_week=0,
                time='07:00',
                class_type='CrossFit',
                is_active=True
            )
            db.session.add(booking)
            db.session.commit()
            booking_id = booking.id

            client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'testpassword123',
            })

            response = client.post(f'/toggle/{booking_id}', follow_redirects=True)

            booking = Booking.query.get(booking_id)
            assert booking.is_active is False

    def test_toggle_reactivates_booking(self, client, app, test_user):
        """Should reactivate inactive booking."""
        from app.models import db, Booking

        with app.app_context():
            booking = Booking(
                user_id=test_user.id,
                day_of_week=0,
                time='07:00',
                class_type='CrossFit',
                is_active=False
            )
            db.session.add(booking)
            db.session.commit()
            booking_id = booking.id

            client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'testpassword123',
            })

            response = client.post(f'/toggle/{booking_id}', follow_redirects=True)

            booking = Booking.query.get(booking_id)
            assert booking.is_active is True

    def test_toggle_other_user_booking_404(self, client, app, test_user):
        """Should return 404 for other user's booking."""
        from app.models import db, User, Booking

        with app.app_context():
            other_user = User(email='other@example.com')
            other_user.set_password('password')
            other_user.email_verified = True
            db.session.add(other_user)
            db.session.flush()

            booking = Booking(
                user_id=other_user.id,
                day_of_week=0,
                time='07:00',
                class_type='CrossFit'
            )
            db.session.add(booking)
            db.session.commit()
            booking_id = booking.id

            client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'testpassword123',
            })

            response = client.post(f'/toggle/{booking_id}')
            assert response.status_code == 404


class TestDeleteBookingRoute:
    """Tests for /delete/<id> route."""

    def test_delete_requires_login(self, client, app):
        """Should require authentication."""
        with app.app_context():
            response = client.post('/delete/1')
            assert response.status_code == 302

    def test_delete_booking(self, client, app, test_user):
        """Should delete user's booking."""
        from app.models import db, Booking

        with app.app_context():
            booking = Booking(
                user_id=test_user.id,
                day_of_week=0,
                time='07:00',
                class_type='CrossFit'
            )
            db.session.add(booking)
            db.session.commit()
            booking_id = booking.id

            client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'testpassword123',
            })

            response = client.post(f'/delete/{booking_id}', follow_redirects=True)

            booking = Booking.query.get(booking_id)
            assert booking is None

    def test_delete_other_user_booking_404(self, client, app, test_user):
        """Should return 404 for other user's booking."""
        from app.models import db, User, Booking

        with app.app_context():
            other_user = User(email='other@example.com')
            other_user.set_password('password')
            other_user.email_verified = True
            db.session.add(other_user)
            db.session.flush()

            booking = Booking(
                user_id=other_user.id,
                day_of_week=0,
                time='07:00',
                class_type='CrossFit'
            )
            db.session.add(booking)
            db.session.commit()
            booking_id = booking.id

            client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'testpassword123',
            })

            response = client.post(f'/delete/{booking_id}')
            assert response.status_code == 404


class TestBookingLogsRoute:
    """Tests for /logs/<id> route."""

    def test_logs_requires_login(self, client, app):
        """Should require authentication."""
        with app.app_context():
            response = client.get('/logs/1')
            assert response.status_code == 302

    def test_logs_shows_booking_history(self, client, app, test_user):
        """Should show booking attempt history."""
        from app.models import db, Booking, BookingLog

        with app.app_context():
            booking = Booking(
                user_id=test_user.id,
                day_of_week=0,
                time='07:00',
                class_type='CrossFit'
            )
            db.session.add(booking)
            db.session.flush()

            log = BookingLog(
                booking_id=booking.id,
                status='success',
                message='Booked successfully'
            )
            db.session.add(log)
            db.session.commit()
            booking_id = booking.id

            client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'testpassword123',
            })

            response = client.get(f'/logs/{booking_id}')
            assert response.status_code == 200


class TestClassesAPIRoute:
    """Tests for /classes API route."""

    def test_classes_requires_login(self, client, app):
        """Should require authentication."""
        with app.app_context():
            response = client.get('/classes')
            assert response.status_code == 302

    def test_classes_requires_wodbuster(self, client, app, test_user):
        """Should return error if WodBuster not connected."""
        with app.app_context():
            client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'testpassword123',
            })

            response = client.get('/classes')
            assert response.status_code == 400


class TestHealthCheckRoute:
    """Tests for /health route."""

    def test_health_check_returns_status(self, client, app):
        """Should return health status."""
        with app.app_context():
            response = client.get('/health')
            data = response.get_json()

            assert 'status' in data
            assert 'checks' in data
            assert 'database' in data['checks']


class TestSetLanguageRoute:
    """Tests for /set-language/<language> route."""

    def test_set_language_spanish(self, client, app):
        """Should set language to Spanish."""
        with app.app_context():
            response = client.get('/set-language/es', follow_redirects=False)
            assert response.status_code == 302

    def test_set_language_english(self, client, app):
        """Should set language to English."""
        with app.app_context():
            response = client.get('/set-language/en', follow_redirects=False)
            assert response.status_code == 302

    def test_set_invalid_language(self, client, app):
        """Should ignore invalid language."""
        with app.app_context():
            response = client.get('/set-language/invalid', follow_redirects=False)
            assert response.status_code == 302


class TestBookNowRoute:
    """Tests for /book-now/<id> route."""

    def test_book_now_requires_login(self, client, app):
        """Should require authentication."""
        with app.app_context():
            response = client.post('/book-now/1')
            assert response.status_code == 302

    @patch('app.booking.routes.WodBusterClient')
    def test_book_now_triggers_booking(self, mock_client_class, client, app, test_user):
        """Should attempt to book class immediately."""
        from app.models import db, User, Booking

        with app.app_context():
            # Re-query user in this context
            user = User.query.filter_by(email='test@example.com').first()
            user.box_url = 'https://test.wodbuster.com'
            user.set_wodbuster_cookies({'.WBAuth': 'token'})

            booking = Booking(
                user_id=user.id,
                day_of_week=0,
                time='07:00',
                class_type='CrossFit'
            )
            db.session.add(booking)
            db.session.commit()
            booking_id = booking.id

            mock_client = MagicMock()
            mock_client.restore_session.return_value = True
            mock_client.find_class.return_value = {'id': 123, 'name': 'CrossFit'}
            mock_client.book_class.return_value = True
            # Mock get_account_info to return proper dict for dashboard template
            mock_client.get_account_info.return_value = {'available_classes': 10}
            mock_client_class.return_value = mock_client

            client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'testpassword123',
            })

            # Don't follow redirects to dashboard which needs account_info
            response = client.post(f'/book-now/{booking_id}', follow_redirects=False)

            mock_client.book_class.assert_called_once()
            assert response.status_code == 302  # Redirect to dashboard
