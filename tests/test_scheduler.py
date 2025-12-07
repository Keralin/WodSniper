"""Tests for booking scheduler and retry logic."""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timedelta
import time


class TestRetryLogic:
    """Tests for booking retry logic."""

    @patch('app.scheduler.time.sleep')
    @patch('app.scraper.WodBusterClient')
    def test_successful_booking_on_first_attempt(self, mock_client_class, mock_sleep):
        """Should succeed on first attempt without retries."""
        from app.scheduler import _process_single_booking, MAX_RETRY_ATTEMPTS

        # Setup mocks
        mock_client = MagicMock()
        mock_client.restore_session.return_value = True
        mock_client.find_class.return_value = {'id': 123, 'name': 'CrossFit'}
        mock_client.book_class.return_value = True
        mock_client_class.return_value = mock_client

        mock_booking = Mock()
        mock_booking.id = 1
        mock_booking.day_of_week = 0
        mock_booking.time = '07:00'
        mock_booking.class_type = 'crossfit'
        mock_booking.day_name = 'Monday'
        mock_booking.success_count = 0
        mock_booking.fail_count = 0
        mock_booking.user = Mock()
        mock_booking.user.id = 1
        mock_booking.user.email = 'test@test.com'
        mock_booking.user.box_url = 'https://test.wodbuster.com'
        mock_booking.user.get_wodbuster_cookies.return_value = {'.WBAuth': 'cookie'}
        mock_booking.user.get_wodbuster_password.return_value = 'password'

        mock_app = MagicMock()

        with patch('app.models.db') as mock_db, \
             patch('app.models.BookingLog'):
            result = _process_single_booking(mock_booking, mock_app)

        assert mock_booking.status == 'success'
        assert mock_booking.success_count == 1
        # Should not have called sleep for retries
        assert mock_sleep.call_count == 0

    @patch('app.scheduler.RETRY_DELAY', 0.01)  # Fast retries for testing
    @patch('app.scheduler.time.sleep')
    @patch('app.scraper.WodBusterClient')
    def test_retries_on_booking_error(self, mock_client_class, mock_sleep):
        """Should retry on BookingError."""
        from app.scheduler import _process_single_booking, MAX_RETRY_ATTEMPTS
        from app.scraper.exceptions import BookingError

        # Setup mocks - fail twice, succeed on third
        mock_client = MagicMock()
        mock_client.restore_session.return_value = True
        mock_client.find_class.return_value = {'id': 123, 'name': 'CrossFit'}
        mock_client.book_class.side_effect = [
            BookingError('Network error'),
            BookingError('Network error'),
            True  # Success on third attempt
        ]
        mock_client_class.return_value = mock_client

        mock_booking = Mock()
        mock_booking.id = 1
        mock_booking.day_of_week = 0
        mock_booking.time = '07:00'
        mock_booking.class_type = 'crossfit'
        mock_booking.day_name = 'Monday'
        mock_booking.success_count = 0
        mock_booking.fail_count = 0
        mock_booking.user = Mock()
        mock_booking.user.id = 1
        mock_booking.user.email = 'test@test.com'
        mock_booking.user.box_url = 'https://test.wodbuster.com'
        mock_booking.user.get_wodbuster_cookies.return_value = {'.WBAuth': 'cookie'}

        mock_app = MagicMock()

        with patch('app.models.db') as mock_db, \
             patch('app.models.BookingLog'):
            result = _process_single_booking(mock_booking, mock_app)

        assert mock_booking.status == 'success'
        assert mock_client.book_class.call_count == 3
        # Should have slept twice between retries
        assert mock_sleep.call_count == 2

    @patch('app.scheduler.RETRY_DELAY', 0.01)
    @patch('app.scheduler.time.sleep')
    @patch('app.scraper.WodBusterClient')
    def test_no_retry_on_class_full(self, mock_client_class, mock_sleep):
        """Should NOT retry when class is full."""
        from app.scheduler import _process_single_booking
        from app.scraper.exceptions import ClassFullError

        mock_client = MagicMock()
        mock_client.restore_session.return_value = True
        mock_client.find_class.return_value = {'id': 123, 'name': 'CrossFit'}
        mock_client.book_class.side_effect = ClassFullError('Class is full')
        mock_client_class.return_value = mock_client

        mock_booking = Mock()
        mock_booking.id = 1
        mock_booking.day_of_week = 0
        mock_booking.time = '07:00'
        mock_booking.class_type = 'crossfit'
        mock_booking.day_name = 'Monday'
        mock_booking.user = Mock()
        mock_booking.user.id = 1
        mock_booking.user.email = 'test@test.com'
        mock_booking.user.box_url = 'https://test.wodbuster.com'
        mock_booking.user.get_wodbuster_cookies.return_value = {'.WBAuth': 'cookie'}

        mock_app = MagicMock()

        with patch('app.models.db') as mock_db, \
             patch('app.models.BookingLog'):
            result = _process_single_booking(mock_booking, mock_app)

        assert mock_booking.status == 'waiting'
        # Should only try once - no retries for full class
        assert mock_client.book_class.call_count == 1
        assert mock_sleep.call_count == 0

    @patch('app.scheduler.RETRY_DELAY', 0.01)
    @patch('app.scheduler.MAX_RETRY_ATTEMPTS', 3)
    @patch('app.scheduler.time.sleep')
    @patch('app.scraper.WodBusterClient')
    def test_fails_after_max_retries(self, mock_client_class, mock_sleep):
        """Should mark as failed after max retries."""
        from app.scheduler import _process_single_booking
        from app.scraper.exceptions import BookingError

        mock_client = MagicMock()
        mock_client.restore_session.return_value = True
        mock_client.find_class.return_value = {'id': 123, 'name': 'CrossFit'}
        mock_client.book_class.side_effect = BookingError('Persistent error')
        mock_client_class.return_value = mock_client

        mock_booking = Mock()
        mock_booking.id = 1
        mock_booking.day_of_week = 0
        mock_booking.time = '07:00'
        mock_booking.class_type = 'crossfit'
        mock_booking.day_name = 'Monday'
        mock_booking.fail_count = 0
        mock_booking.user = Mock()
        mock_booking.user.id = 1
        mock_booking.user.email = 'test@test.com'
        mock_booking.user.box_url = 'https://test.wodbuster.com'
        mock_booking.user.get_wodbuster_cookies.return_value = {'.WBAuth': 'cookie'}

        mock_app = MagicMock()

        with patch('app.models.db') as mock_db, \
             patch('app.models.BookingLog'):
            result = _process_single_booking(mock_booking, mock_app)

        assert mock_booking.status == 'failed'
        assert mock_booking.fail_count == 1
        assert mock_client.book_class.call_count == 3
        assert mock_booking.last_error == 'Persistent error'


class TestTargetDateCalculation:
    """Tests for target date calculation."""

    def test_calculates_next_monday_from_sunday(self):
        """Should calculate next Monday when today is Sunday."""
        # Sunday = 6, Monday = 0
        with patch('app.scheduler.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 12, 8)  # Sunday
            mock_datetime.utcnow.return_value = datetime(2024, 12, 8)

            # day_of_week = 0 (Monday)
            today = datetime(2024, 12, 8)  # Sunday
            days_ahead = 0 - today.weekday()  # 0 - 6 = -6
            if days_ahead <= 0:
                days_ahead += 7  # -6 + 7 = 1

            target = today + timedelta(days=days_ahead)

            assert target.weekday() == 0  # Monday
            assert target == datetime(2024, 12, 9)

    def test_calculates_next_friday_from_sunday(self):
        """Should calculate next Friday when today is Sunday."""
        today = datetime(2024, 12, 8)  # Sunday
        day_of_week = 4  # Friday

        days_ahead = day_of_week - today.weekday()  # 4 - 6 = -2
        if days_ahead <= 0:
            days_ahead += 7  # -2 + 7 = 5

        target = today + timedelta(days=days_ahead)

        assert target.weekday() == 4  # Friday
        assert target == datetime(2024, 12, 13)


class TestSchedulerConfig:
    """Tests for scheduler configuration."""

    def test_retry_constants_exist(self):
        """Should have retry configuration constants."""
        from app.scheduler import MAX_RETRY_ATTEMPTS, RETRY_DELAY

        assert MAX_RETRY_ATTEMPTS == 3
        assert RETRY_DELAY == 2

    def test_booking_interval_exists(self):
        """Should have booking interval constant."""
        from app.scheduler import BOOKING_INTERVAL

        assert BOOKING_INTERVAL == 0.5


class TestSessionRefresh:
    """Tests for pre-booking session refresh."""

    @patch('app.scraper.WodBusterClient')
    def test_refreshes_sessions_for_users_with_bookings(self, mock_client_class):
        """Should refresh sessions for users with active bookings."""
        from app.scheduler import refresh_all_sessions

        mock_client = MagicMock()
        mock_client.login.return_value = True
        mock_client.get_cookies.return_value = {'.WBAuth': 'new_cookie'}
        mock_client_class.return_value = mock_client

        mock_user = Mock()
        mock_user.email = 'test@test.com'
        mock_user.box_url = 'https://test.wodbuster.com'
        mock_user.wodbuster_email = 'test@wodbuster.com'
        mock_user.get_wodbuster_password.return_value = 'password'

        mock_app = MagicMock()

        with patch('app.models.db') as mock_db, \
             patch('app.models.User') as mock_user_model, \
             patch('app.models.Booking') as mock_booking_model, \
             patch('app.scheduler.time.sleep'):

            # Setup query to return our mock user
            mock_query = MagicMock()
            mock_query.filter.return_value.distinct.return_value.all.return_value = [mock_user]
            mock_db.session.query.return_value.join.return_value = mock_query

            refresh_all_sessions(mock_app)

        mock_client.login.assert_called_once_with('test@wodbuster.com', 'password')
        mock_user.set_wodbuster_cookies.assert_called_once()
