"""Tests for database models."""

import pytest
from datetime import datetime, date
from unittest.mock import patch, MagicMock


class TestUserModel:
    """Tests for User model."""

    def test_create_user(self, app):
        """Should create a user with email."""
        from app.models import db, User

        with app.app_context():
            user = User(email='newuser@example.com')
            user.set_password('password123')
            db.session.add(user)
            db.session.commit()

            assert user.id is not None
            assert user.email == 'newuser@example.com'
            assert user.password_hash is not None

    def test_password_hashing(self, app):
        """Should hash password and verify correctly."""
        from app.models import User

        with app.app_context():
            user = User(email='test@example.com')
            user.set_password('mysecretpassword')

            assert user.check_password('mysecretpassword') is True
            assert user.check_password('wrongpassword') is False

    def test_password_hash_is_not_plaintext(self, app):
        """Should not store password in plaintext."""
        from app.models import User

        with app.app_context():
            user = User(email='test@example.com')
            user.set_password('mysecretpassword')

            assert user.password_hash != 'mysecretpassword'
            assert 'mysecretpassword' not in user.password_hash

    def test_user_repr(self, app):
        """Should have readable string representation."""
        from app.models import User

        with app.app_context():
            user = User(email='test@example.com')
            assert repr(user) == '<User test@example.com>'

    def test_unique_email_constraint(self, app):
        """Should enforce unique email constraint."""
        from app.models import db, User
        from sqlalchemy.exc import IntegrityError

        with app.app_context():
            user1 = User(email='duplicate@example.com')
            user1.set_password('password1')
            db.session.add(user1)
            db.session.commit()

            user2 = User(email='duplicate@example.com')
            user2.set_password('password2')
            db.session.add(user2)

            with pytest.raises(IntegrityError):
                db.session.commit()

    def test_box_name_from_box_model(self, app):
        """Should get box name from Box relationship."""
        from app.models import db, User, Box

        with app.app_context():
            box = Box(name='testbox', url='https://testbox.wodbuster.com')
            db.session.add(box)
            db.session.flush()

            user = User(email='test@example.com', box_id=box.id)
            user.set_password('password')
            db.session.add(user)
            db.session.commit()

            assert user.box_name == 'testbox'

    def test_box_name_from_legacy_url(self, app):
        """Should extract box name from legacy box_url."""
        from app.models import User

        with app.app_context():
            user = User(
                email='test@example.com',
                box_url='https://legacybox.wodbuster.com'
            )
            user.set_password('password')

            assert user.box_name == 'legacybox'

    def test_effective_box_url_from_box(self, app):
        """Should get URL from Box model."""
        from app.models import db, User, Box

        with app.app_context():
            box = Box(name='testbox', url='https://testbox.wodbuster.com')
            db.session.add(box)
            db.session.flush()

            user = User(email='test@example.com', box_id=box.id)
            user.set_password('password')
            db.session.add(user)
            db.session.commit()

            assert user.effective_box_url == 'https://testbox.wodbuster.com'

    def test_wodbuster_cookies_storage(self, app):
        """Should store and retrieve WodBuster cookies."""
        from app.models import db, User

        with app.app_context():
            user = User(email='test@example.com')
            user.set_password('password')

            cookies = {'.WBAuth': 'auth_token', 'cf_clearance': 'cf_token'}
            user.set_wodbuster_cookies(cookies)

            db.session.add(user)
            db.session.commit()

            retrieved = user.get_wodbuster_cookies()
            assert retrieved == cookies

    def test_get_wodbuster_cookies_when_none(self, app):
        """Should return None when no cookies stored."""
        from app.models import User

        with app.app_context():
            user = User(email='test@example.com')
            user.set_password('password')

            assert user.get_wodbuster_cookies() is None

    def test_email_verified_default(self, app):
        """Should default to unverified email."""
        from app.models import db, User

        with app.app_context():
            user = User(email='verified_test@example.com')
            user.set_password('password')
            db.session.add(user)
            db.session.commit()

            # Defaults are applied after commit
            assert user.email_verified is False

    def test_is_admin_default(self, app):
        """Should default to non-admin."""
        from app.models import db, User

        with app.app_context():
            user = User(email='admin_test@example.com')
            user.set_password('password')
            db.session.add(user)
            db.session.commit()

            # Defaults are applied after commit
            assert user.is_admin is False

    def test_reset_token_generation(self, app):
        """Should generate a reset token."""
        from app.models import db, User

        with app.app_context():
            user = User(email='test@example.com')
            user.set_password('password')
            db.session.add(user)
            db.session.commit()

            token = user.get_reset_token()
            assert token is not None
            assert len(token) > 0

    def test_reset_token_verification(self, app):
        """Should verify a valid reset token."""
        from app.models import db, User

        with app.app_context():
            user = User(email='test@example.com')
            user.set_password('password')
            db.session.add(user)
            db.session.commit()

            token = user.get_reset_token()
            verified_user = User.verify_reset_token(token)

            assert verified_user is not None
            assert verified_user.id == user.id

    def test_invalid_reset_token(self, app):
        """Should return None for invalid reset token."""
        from app.models import User

        with app.app_context():
            result = User.verify_reset_token('invalid-token')
            assert result is None

    def test_verification_token_generation(self, app):
        """Should generate an email verification token."""
        from app.models import db, User

        with app.app_context():
            user = User(email='test@example.com')
            user.set_password('password')
            db.session.add(user)
            db.session.commit()

            token = user.get_verification_token()
            assert token is not None
            assert len(token) > 0

    def test_verification_token_verification(self, app):
        """Should verify a valid email verification token."""
        from app.models import db, User

        with app.app_context():
            user = User(email='test@example.com')
            user.set_password('password')
            db.session.add(user)
            db.session.commit()

            token = user.get_verification_token()
            verified_user = User.verify_email_token(token)

            assert verified_user is not None
            assert verified_user.id == user.id


class TestBoxModel:
    """Tests for Box model."""

    def test_create_box(self, app):
        """Should create a box with name and URL."""
        from app.models import db, Box

        with app.app_context():
            box = Box(name='mybox', url='https://mybox.wodbuster.com')
            db.session.add(box)
            db.session.commit()

            assert box.id is not None
            assert box.name == 'mybox'
            assert box.url == 'https://mybox.wodbuster.com'

    def test_box_default_schedule(self, app):
        """Should have default booking schedule (Sunday 13:00)."""
        from app.models import db, Box

        with app.app_context():
            box = Box(name='defaultbox', url='https://defaultbox.wodbuster.com')
            db.session.add(box)
            db.session.commit()

            # Defaults are applied after commit
            assert box.booking_open_day == 6  # Sunday
            assert box.booking_open_hour == 13
            assert box.booking_open_minute == 0

    def test_box_repr(self, app):
        """Should have readable string representation."""
        from app.models import Box

        with app.app_context():
            box = Box(name='mybox', url='https://mybox.wodbuster.com')
            assert repr(box) == '<Box mybox>'

    def test_unique_url_constraint(self, app):
        """Should enforce unique URL constraint."""
        from app.models import db, Box
        from sqlalchemy.exc import IntegrityError

        with app.app_context():
            box1 = Box(name='box1', url='https://same.wodbuster.com')
            db.session.add(box1)
            db.session.commit()

            box2 = Box(name='box2', url='https://same.wodbuster.com')
            db.session.add(box2)

            with pytest.raises(IntegrityError):
                db.session.commit()


class TestBookingModel:
    """Tests for Booking model."""

    def test_create_booking(self, app, test_user):
        """Should create a booking for a user."""
        from app.models import db, Booking

        with app.app_context():
            booking = Booking(
                user_id=test_user.id,
                day_of_week=0,  # Monday
                time='07:00',
                class_type='CrossFit'
            )
            db.session.add(booking)
            db.session.commit()

            assert booking.id is not None
            assert booking.user_id == test_user.id
            assert booking.is_active is True
            assert booking.status == 'pending'

    def test_booking_day_name(self, app, test_user):
        """Should return correct day name."""
        from app.models import Booking

        with app.app_context():
            days = [
                (0, 'Monday'),
                (1, 'Tuesday'),
                (2, 'Wednesday'),
                (3, 'Thursday'),
                (4, 'Friday'),
                (5, 'Saturday'),
                (6, 'Sunday'),
            ]

            for day_num, day_name in days:
                booking = Booking(
                    user_id=test_user.id,
                    day_of_week=day_num,
                    time='07:00',
                    class_type='CrossFit'
                )
                assert booking.day_name == day_name

    def test_booking_default_stats(self, app, test_user):
        """Should have zero counts by default."""
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

            # Defaults are applied after commit
            assert booking.success_count == 0
            assert booking.fail_count == 0
            assert booking.last_error is None

    def test_booking_repr(self, app, test_user):
        """Should have readable string representation."""
        from app.models import Booking

        with app.app_context():
            booking = Booking(
                user_id=test_user.id,
                day_of_week=0,
                time='07:00',
                class_type='CrossFit'
            )

            assert repr(booking) == '<Booking Monday 07:00 - CrossFit>'

    def test_unique_booking_constraint(self, app, test_user):
        """Should enforce unique constraint per user/day/time/class."""
        from app.models import db, Booking
        from sqlalchemy.exc import IntegrityError

        with app.app_context():
            booking1 = Booking(
                user_id=test_user.id,
                day_of_week=0,
                time='07:00',
                class_type='CrossFit'
            )
            db.session.add(booking1)
            db.session.commit()

            booking2 = Booking(
                user_id=test_user.id,
                day_of_week=0,
                time='07:00',
                class_type='CrossFit'
            )
            db.session.add(booking2)

            with pytest.raises(IntegrityError):
                db.session.commit()

    def test_different_class_same_time_allowed(self, app, test_user):
        """Should allow different class types at same time."""
        from app.models import db, Booking

        with app.app_context():
            booking1 = Booking(
                user_id=test_user.id,
                day_of_week=0,
                time='07:00',
                class_type='CrossFit'
            )
            booking2 = Booking(
                user_id=test_user.id,
                day_of_week=0,
                time='07:00',
                class_type='Hyrox'
            )

            db.session.add(booking1)
            db.session.add(booking2)
            db.session.commit()

            assert booking1.id is not None
            assert booking2.id is not None


class TestBookingLogModel:
    """Tests for BookingLog model."""

    def test_create_booking_log(self, app, test_user):
        """Should create a booking log."""
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
                message='Booked successfully',
                target_date=date.today()
            )
            db.session.add(log)
            db.session.commit()

            assert log.id is not None
            assert log.booking_id == booking.id
            assert log.status == 'success'

    def test_booking_log_relationship(self, app, test_user):
        """Should link log to booking."""
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
                status='failed',
                message='Class full'
            )
            db.session.add(log)
            db.session.commit()

            assert log.booking == booking
            assert log in booking.logs.all()

    def test_booking_log_repr(self, app, test_user):
        """Should have readable string representation."""
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
                status='success'
            )

            assert f'<BookingLog {booking.id} - success>' == repr(log)

    def test_booking_log_created_at(self, app, test_user):
        """Should have created_at timestamp."""
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
                status='success'
            )
            db.session.add(log)
            db.session.commit()

            assert log.created_at is not None
            assert isinstance(log.created_at, datetime)
