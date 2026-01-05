from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer
from flask import current_app
import pickle

db = SQLAlchemy()


class Box(db.Model):
    """CrossFit/Gym box configuration."""
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
    """User model for WodSniper authentication."""
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

    # Email verification
    email_verified = db.Column(db.Boolean, default=False)

    # Admin
    is_admin = db.Column(db.Boolean, default=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    # Relationships
    bookings = db.relationship('Booking', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def set_wodbuster_cookies(self, cookies):
        """Store WodBuster session cookies."""
        self.wodbuster_cookie = pickle.dumps(cookies)

    def get_wodbuster_cookies(self):
        """Retrieve WodBuster session cookies."""
        if self.wodbuster_cookie:
            return pickle.loads(self.wodbuster_cookie)
        return None

    def set_wodbuster_password(self, password):
        """Store WodBuster password (encrypted)."""
        from app.crypto import encrypt_credential
        self.wodbuster_password_encrypted = encrypt_credential(password)

    def get_wodbuster_password(self):
        """Retrieve WodBuster password (decrypted)."""
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

    def get_reset_token(self):
        """Generate a password reset token valid for 1 hour."""
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return s.dumps(self.email, salt='password-reset')

    @staticmethod
    def verify_reset_token(token, max_age=3600):
        """Verify a password reset token. Returns user if valid, None otherwise."""
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            email = s.loads(token, salt='password-reset', max_age=max_age)
        except Exception:
            return None
        return User.query.filter_by(email=email).first()

    def get_verification_token(self):
        """Generate an email verification token valid for 24 hours."""
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return s.dumps(self.email, salt='email-verification')

    @staticmethod
    def verify_email_token(token, max_age=86400):
        """Verify an email verification token. Returns user if valid, None otherwise."""
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            email = s.loads(token, salt='email-verification', max_age=max_age)
        except Exception:
            return None
        return User.query.filter_by(email=email).first()

    def __repr__(self):
        return f'<User {self.email}>'


class Booking(db.Model):
    """Scheduled booking model."""
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
    """Log of booking attempts."""
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
