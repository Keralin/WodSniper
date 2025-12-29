from flask_wtf import FlaskForm
from flask_babel import lazy_gettext as _l
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, URL, ValidationError

from app.models import User


class LoginForm(FlaskForm):
    """Login form for WodSniper."""
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Invalid email')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required')
    ])
    remember_me = BooleanField('Remember me')
    submit = SubmitField('Sign In')


class RegisterForm(FlaskForm):
    """Registration form for WodSniper."""
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Invalid email')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required'),
        Length(min=6, message='Password must be at least 6 characters')
    ])
    password2 = PasswordField('Confirm Password', validators=[
        DataRequired(message='Please confirm your password'),
        EqualTo('password', message='Passwords do not match')
    ])
    submit = SubmitField('Sign Up')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data.lower()).first()
        if user:
            raise ValidationError('This email is already registered')


class WodBusterConnectForm(FlaskForm):
    """Form to connect WodBuster account."""
    box_url = StringField('Box URL', validators=[
        DataRequired(message='Box URL is required'),
    ], render_kw={'placeholder': 'https://yourbox.wodbuster.com'})
    wodbuster_email = StringField('WodBuster Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Invalid email')
    ])
    wodbuster_password = PasswordField('WodBuster Password', validators=[
        DataRequired(message='Password is required')
    ])
    submit = SubmitField('Connect')

    def validate_box_url(self, box_url):
        url = box_url.data.lower().strip()
        if not url.startswith('https://'):
            url = 'https://' + url
        if 'wodbuster.com' not in url:
            raise ValidationError('URL must be a WodBuster URL (e.g., https://yourbox.wodbuster.com)')
        box_url.data = url


class ForgotPasswordForm(FlaskForm):
    """Form to request password reset."""
    email = StringField(_l('Email'), validators=[
        DataRequired(message=_l('Email is required')),
        Email(message=_l('Invalid email'))
    ])
    submit = SubmitField(_l('Send Reset Link'))


class ResetPasswordForm(FlaskForm):
    """Form to reset password with token."""
    password = PasswordField(_l('New Password'), validators=[
        DataRequired(message=_l('Password is required')),
        Length(min=6, message=_l('Password must be at least 6 characters'))
    ])
    password2 = PasswordField(_l('Confirm Password'), validators=[
        DataRequired(message=_l('Please confirm your password')),
        EqualTo('password', message=_l('Passwords do not match'))
    ])
    submit = SubmitField(_l('Reset Password'))
