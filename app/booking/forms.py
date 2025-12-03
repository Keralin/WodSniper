from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TimeField
from wtforms.validators import DataRequired, InputRequired


class BookingForm(FlaskForm):
    """Form to create a new scheduled booking."""
    day_of_week = SelectField('Day of Week', choices=[
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ], coerce=int, validators=[InputRequired()])

    time = StringField('Time (HH:MM)', validators=[
        DataRequired(message='Time is required')
    ], render_kw={'placeholder': '07:00'})

    class_type = StringField('Class Type', validators=[
        DataRequired(message='Class type is required')
    ], render_kw={'placeholder': 'CrossFit, Hyrox, Open Box...'})

    submit = SubmitField('Schedule Booking')

    def validate_time(self, time):
        """Validate time format."""
        import re
        if not re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', time.data):
            from wtforms.validators import ValidationError
            raise ValidationError('Invalid time format. Use HH:MM')
