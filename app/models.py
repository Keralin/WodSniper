"""
Database models for WodSniper.

This module defines the SQLAlchemy models for the application:
- Box: CrossFit/Gym configuration with booking schedule
- User: Application users with WodBuster connection
- Booking: Scheduled class reservations
- BookingLog: History of booking attempts

All models use SQLAlchemy ORM with Flask-SQLAlchemy integration.
"""

from datetime import datetime
from typing import Optional, Dict, Any

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer
from flask import current_app
import pickle

db = SQLAlchemy()


class Box(db.Model):
    """
    CrossFit/Gym box configuration.

    Represents a WodBuster-connected gym with its booking schedule.
    Each box can have a different day/time when reservations open
    for the upcoming week.

    Attributes:
        id: Primary key
        name: Box identifier (e.g., "teknix")
        url: Full WodBuster URL (e.g., "https://teknix.wodbuster.com")
        booking_open_day: Day of week when bookings open (0=Mon, 6=Sun)
        booking_open_hour: Hour (UTC) when bookings open (0-23)
        booking_open_minute: Minute when bookings open (0-59)
        created_at: When the box was added to the system

    Relationships:
        users: All users associated with this box

    Example:
        box = Box(
            name='teknix',
            url='https://teknix.wodbuster.com',
            booking_open_day=6,  # Sunday
            booking_open_hour=13,  # 13:00 UTC
            booking_open_minute=0
        )
    """
    __tablename__ = 'boxes'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # e.g., "teknix"
    url = db.Column(db.String(256), unique=True, nullable=False)  # e.g., "https://teknix.wodbuster.com"

    # Booking schedule configuration (when the box opens reservations)
    # Default: Sunday (6) at 13:00 UTC (14:00 Spanish time)
    booking_open_day = db.Column(db.Integer, default=6)  # 0=Monday, 6=Sunday
    booking_open_hour = db.Column(db.Integer, default=13)  # 0-23 UTC
    booking_open_minute = db.Column(db.Integer, default=0)  # 0-59

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    users = db.relationship('User', backref='box', lazy='dynamic')

    def __repr__(self):
        return f'<Box {self.name}>'


class User(UserMixin, db.Model):
    """
    WodSniper user with WodBuster integration.

    Handles authentication for both WodSniper and WodBuster platforms.
    Stores encrypted WodBuster credentials for automatic re-login
    and session cookies for faster access.

    Attributes:
        id: Primary key
        email: Unique email address (used for login)
        password_hash: Hashed WodSniper password
        box_id: Foreign key to associated Box
        box_url: Legacy box URL field (use effective_box_url property)
        wodbuster_email: Email for WodBuster login
        wodbuster_password_encrypted: Encrypted WodBuster password
        wodbuster_cookie: Pickled session cookies
        email_notifications: Whether to send booking summary emails
        email_verified: Whether email has been verified
        is_admin: Admin privileges flag
        created_at: Registration timestamp
        last_login: Last login timestamp

    Relationships:
        box: Associated Box model
        bookings: User's scheduled bookings

    Security:
        - Passwords are hashed using Werkzeug's security functions
        - WodBuster passwords are encrypted (not hashed) for retrieval
        - Tokens use itsdangerous with time-based expiration
    """
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)

    # WodBuster connection
    box_id = db.Column(db.Integer, db.ForeignKey('boxes.id'), nullable=True)
    box_url = db.Column(db.String(256), nullable=True)  # Legacy, kept for migration. Use box.url instead
    wodbuster_email = db.Column(db.String(120), nullable=True)
    wodbuster_password_encrypted = db.Column(db.String(512), nullable=True)  # Encrypted password
    wodbuster_cookie = db.Column(db.LargeBinary, nullable=True)  # Pickled session cookies

    # Notification preferences
    email_notifications = db.Column(db.Boolean, default=True)

    # Language preference (es, en)
    language = db.Column(db.String(5), default='en')

    # Email verification
    email_verified = db.Column(db.Boolean, default=False)

    # Admin
    is_admin = db.Column(db.Boolean, default=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    # Relationships
    bookings = db.relationship('Booking', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password: str) -> None:
        """
        Hash and store the user's password.

        Args:
            password: Plain text password to hash
        """
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """
        Verify a password against the stored hash.

        Args:
            password: Plain text password to verify

        Returns:
            True if password matches, False otherwise
        """
        return check_password_hash(self.password_hash, password)

    def set_wodbuster_cookies(self, cookies: Dict[str, str]) -> None:
        """
        Store WodBuster session cookies (pickled).

        Args:
            cookies: Dictionary of cookie name/value pairs
        """
        self.wodbuster_cookie = pickle.dumps(cookies)

    def get_wodbuster_cookies(self) -> Optional[Dict[str, str]]:
        """
        Retrieve WodBuster session cookies.

        Returns:
            Dictionary of cookies, or None if not set
        """
        if self.wodbuster_cookie:
            return pickle.loads(self.wodbuster_cookie)
        return None

    def set_wodbuster_password(self, password: str) -> None:
        """
        Store WodBuster password (encrypted for retrieval).

        Unlike set_password(), this uses reversible encryption
        so the password can be used for automatic re-login.

        Args:
            password: Plain text WodBuster password
        """
        from app.crypto import encrypt_credential
        self.wodbuster_password_encrypted = encrypt_credential(password)

    def get_wodbuster_password(self) -> Optional[str]:
        """
        Retrieve WodBuster password (decrypted).

        Returns:
            Decrypted password, or None if not set
        """
        from app.crypto import decrypt_credential
        return decrypt_credential(self.wodbuster_password_encrypted)

    @property
    def box_name(self):
        """Get box name from Box model or extract from legacy URL."""
        if self.box:
            return self.box.name
        elif self.box_url:
            # Legacy: https://teknix.wodbuster.com -> teknix
            return self.box_url.replace('https://', '').replace('.wodbuster.com', '').split('/')[0]
        return None

    @property
    def effective_box_url(self):
        """Get box URL from Box model or legacy field."""
        if self.box:
            return self.box.url
        return self.box_url

    def get_reset_token(self) -> str:
        """
        Generate a password reset token.

        Returns:
            URL-safe token valid for 1 hour
        """
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return s.dumps(self.email, salt='password-reset')

    @staticmethod
    def verify_reset_token(token: str, max_age: int = 3600) -> Optional['User']:
        """
        Verify a password reset token.

        Args:
            token: The token to verify
            max_age: Maximum age in seconds (default: 1 hour)

        Returns:
            User if token is valid, None otherwise
        """
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            email = s.loads(token, salt='password-reset', max_age=max_age)
        except Exception:
            return None
        return User.query.filter_by(email=email).first()

    def get_verification_token(self) -> str:
        """
        Generate an email verification token.

        Returns:
            URL-safe token valid for 24 hours
        """
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return s.dumps(self.email, salt='email-verification')

    @staticmethod
    def verify_email_token(token: str, max_age: int = 86400) -> Optional['User']:
        """
        Verify an email verification token.

        Args:
            token: The token to verify
            max_age: Maximum age in seconds (default: 24 hours)

        Returns:
            User if token is valid, None otherwise
        """
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            email = s.loads(token, salt='email-verification', max_age=max_age)
        except Exception:
            return None
        return User.query.filter_by(email=email).first()

    def __repr__(self):
        return f'<User {self.email}>'


class Booking(db.Model):
    """
    Scheduled class booking configuration.

    Represents a recurring booking that the scheduler attempts
    each week when the box's booking window opens.

    Attributes:
        id: Primary key
        user_id: Foreign key to User
        day_of_week: Target day (0=Monday, 6=Sunday)
        time: Class time in HH:MM format
        class_type: Class name to match (e.g., "CrossFit", "Hyrox")
        is_active: Whether the scheduler should process this booking
        status: Current status (pending/success/failed/waiting)
        last_attempt: Timestamp of last booking attempt
        last_error: Error message from last failed attempt
        success_count: Total successful bookings
        fail_count: Total failed attempts
        created_at: When the booking was created
        updated_at: Last modification timestamp

    Relationships:
        user: User who owns this booking
        logs: History of booking attempts

    Constraints:
        - Unique per user/day/time/class combination

    Status Values:
        - pending: Waiting for next booking window
        - success: Last attempt was successful
        - failed: Last attempt failed
        - waiting: Added to waitlist (class was full)
    """
    __tablename__ = 'bookings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Booking details
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=Monday, 6=Sunday
    time = db.Column(db.String(5), nullable=False)  # HH:MM format
    class_type = db.Column(db.String(100), nullable=False)  # e.g., "CrossFit", "Hyrox"

    # Status
    is_active = db.Column(db.Boolean, default=True)
    status = db.Column(db.String(20), default='pending')  # pending, success, failed, waiting
    last_attempt = db.Column(db.DateTime, nullable=True)
    last_error = db.Column(db.String(500), nullable=True)

    # Stats
    success_count = db.Column(db.Integer, default=0)
    fail_count = db.Column(db.Integer, default=0)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Unique constraint: one booking per user per day/time/class
    __table_args__ = (
        db.UniqueConstraint('user_id', 'day_of_week', 'time', 'class_type', name='unique_user_booking'),
    )

    DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    @property
    def day_name(self):
        return self.DAY_NAMES[self.day_of_week]

    def __repr__(self):
        return f'<Booking {self.day_name} {self.time} - {self.class_type}>'


class BookingLog(db.Model):
    """
    Historical record of booking attempts.

    Each time the scheduler processes a Booking, a log entry is created
    to track the outcome. This provides visibility into booking history
    and helps diagnose recurring issues.

    Attributes:
        id: Primary key
        booking_id: Foreign key to parent Booking
        status: Outcome (success/failed/waiting)
        message: Detailed result message
        target_date: The class date that was targeted
        created_at: When the attempt was made

    Relationships:
        booking: Parent Booking model

    Usage:
        logs = BookingLog.query.filter_by(booking_id=booking.id)\\
                                .order_by(BookingLog.created_at.desc())\\
                                .limit(10).all()
    """
    __tablename__ = 'booking_logs'

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False, index=True)

    # Relationship
    booking = db.relationship('Booking', backref=db.backref('logs', lazy='dynamic'))

    # Log details
    status = db.Column(db.String(20), nullable=False)  # success, failed, waiting
    message = db.Column(db.String(500), nullable=True)
    target_date = db.Column(db.Date, nullable=True)

    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<BookingLog {self.booking_id} - {self.status}>'
