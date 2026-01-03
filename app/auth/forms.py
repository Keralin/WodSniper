from flask_wtf import FlaskForm
from flask_babel import lazy_gettext as _l
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, URL, ValidationError

from app.models import User


class LoginForm(FlaskForm):
    """Login form for WodSniper."""
    email = StringField(_l('Email'), validators=[
        DataRequired(message=_l('Email is required')),
        Email(message=_l('Invalid email'))
    ])
    password = PasswordField(_l('Password'), validators=[
        DataRequired(message=_l('Password is required'))
    ])
    remember_me = BooleanField(_l('Remember me'))
    submit = SubmitField(_l('Sign In'))


class RegisterForm(FlaskForm):
    """Registration form for WodSniper."""
    email = StringField(_l('Email'), validators=[
        DataRequired(message=_l('Email is required')),
        Email(message=_l('Invalid email'))
    ])
    password = PasswordField(_l('Password'), validators=[
        DataRequired(message=_l('Password is required')),
        Length(min=6, message=_l('Password must be at least 6 characters'))
    ])
    password2 = PasswordField(_l('Confirm Password'), validators=[
        DataRequired(message=_l('Please confirm your password')),
        EqualTo('password', message=_l('Passwords do not match'))
    ])
    submit = SubmitField(_l('Sign Up'))

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data.lower()).first()
        if user:
            raise ValidationError(_l('This email is already registered'))


class WodBusterConnectForm(FlaskForm):
    """Form to connect WodBuster account."""
    wodbuster_email = StringField(_l('WodBuster Email'), validators=[
        DataRequired(message=_l('Email is required')),
        Email(message=_l('Invalid email'))
    ])
    wodbuster_password = PasswordField(_l('WodBuster Password'), validators=[
        DataRequired(message=_l('Password is required'))
    ])
    submit = SubmitField(_l('Connect'))


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
