from datetime import datetime, timedelta
from flask import render_template, redirect, url_for, flash, jsonify, request, session
from flask_login import login_required, current_user

from app.booking import booking_bp
from app.booking.forms import BookingForm
from app.models import db, Booking, BookingLog
from app.scraper import WodBusterClient, SessionExpiredError


def _group_classes_by_time(classes):
    """Group classes by time slot, collecting unique class names per slot."""
    time_slots = {}
    for cls in classes:
        time = cls.get('time', '')[:5]  # HH:MM format
        name = cls.get('name', '')

        if time not in time_slots:
            time_slots[time] = []

        if name and name not in time_slots[time]:
            time_slots[time].append(name)

    return time_slots


@booking_bp.route('/')
def index():
    """Landing page."""
    if current_user.is_authenticated:
        return redirect(url_for('booking.dashboard'))
    return render_template('index.html')


@booking_bp.route('/health')
def health_check():
    """Health check endpoint for monitoring and Railway."""
    from app.scheduler import scheduler

    health = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'checks': {}
    }

    # Check database
    try:
        db.session.execute(db.text('SELECT 1'))
        health['checks']['database'] = 'ok'
    except Exception as e:
        health['checks']['database'] = f'error: {str(e)}'
        health['status'] = 'unhealthy'

    # Check scheduler
    try:
        if scheduler.running:
            jobs = scheduler.get_jobs()
            health['checks']['scheduler'] = f'ok ({len(jobs)} jobs)'
        else:
            health['checks']['scheduler'] = 'not running'
            health['status'] = 'unhealthy'
    except Exception as e:
        health['checks']['scheduler'] = f'error: {str(e)}'
        health['status'] = 'unhealthy'

    status_code = 200 if health['status'] == 'healthy' else 503
    return jsonify(health), status_code


@booking_bp.route('/dashboard')
@login_required
def dashboard():
    """User dashboard."""
    bookings = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.day_of_week).all()

    # Check if WodBuster is connected
    wodbuster_connected = bool(current_user.box_url and current_user.wodbuster_cookie)

    # Get account info (available credits)
    account_info = None
    if wodbuster_connected:
        try:
            client = WodBusterClient(current_user.box_url)
            cookies = current_user.get_wodbuster_cookies()
            if cookies and client.restore_session(cookies):
                account_info = client.get_account_info()
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f'Error getting account info: {e}')

    return render_template(
        'booking/dashboard.html',
        bookings=bookings,
        wodbuster_connected=wodbuster_connected,
        account_info=account_info
    )


@booking_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_booking():
    """Create a new scheduled booking."""
    if not current_user.box_url:
        flash('Please connect your WodBuster account first', 'warning')
        return redirect(url_for('auth.connect_wodbuster'))

    form = BookingForm()

    if form.validate_on_submit():
        # Check for duplicate
        existing = Booking.query.filter_by(
            user_id=current_user.id,
            day_of_week=form.day_of_week.data,
            time=form.time.data,
            class_type=form.class_type.data
        ).first()

        if existing:
            flash('You already have a booking scheduled for this day/time/class', 'error')
            return render_template('booking/new.html', form=form)

        booking = Booking(
            user_id=current_user.id,
            day_of_week=form.day_of_week.data,
            time=form.time.data,
            class_type=form.class_type.data
        )

        db.session.add(booking)
        db.session.commit()

        flash(f'Booking scheduled: {booking.day_name} {booking.time} - {booking.class_type}', 'success')
        return redirect(url_for('booking.dashboard'))

    return render_template('booking/new.html', form=form)


@booking_bp.route('/toggle/<int:booking_id>', methods=['POST'])
@login_required
def toggle_booking(booking_id):
    """Toggle booking active status."""
    booking = Booking.query.filter_by(id=booking_id, user_id=current_user.id).first_or_404()
    booking.is_active = not booking.is_active
    db.session.commit()

    status = 'activated' if booking.is_active else 'deactivated'
    flash(f'Booking {status}', 'success')
    return redirect(url_for('booking.dashboard'))


@booking_bp.route('/delete/<int:booking_id>', methods=['POST'])
@login_required
def delete_booking(booking_id):
    """Delete a booking."""
    booking = Booking.query.filter_by(id=booking_id, user_id=current_user.id).first_or_404()

    db.session.delete(booking)
    db.session.commit()

    flash('Booking deleted', 'success')
    return redirect(url_for('booking.dashboard'))


@booking_bp.route('/classes')
@login_required
def get_classes():
    """Get available classes from WodBuster."""
    if not current_user.box_url:
        return jsonify({'error': 'WodBuster not connected'}), 400

    date_str = request.args.get('date')
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400
    else:
        target_date = datetime.now()

    try:
        client = WodBusterClient(current_user.box_url)
        cookies = current_user.get_wodbuster_cookies()

        if not cookies or not client.restore_session(cookies):
            return jsonify({'error': 'Session expired. Please reconnect WodBuster.'}), 401

        classes = client.get_classes(target_date)
        return jsonify({'classes': classes})

    except SessionExpiredError:
        return jsonify({'error': 'Session expired. Please reconnect WodBuster.'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@booking_bp.route('/api/classes-by-day/<int:day_of_week>')
@login_required
def get_classes_by_day(day_of_week):
    """Get available classes for a specific day of the week."""
    if not current_user.box_url:
        return jsonify({'error': 'WodBuster not connected'}), 400

    if day_of_week < 0 or day_of_week > 6:
        return jsonify({'error': 'Invalid day of week'}), 400

    try:
        client = WodBusterClient(current_user.box_url)
        cookies = current_user.get_wodbuster_cookies()

        if not cookies or not client.restore_session(cookies):
            return jsonify({'error': 'Session expired. Please reconnect WodBuster.'}), 401

        # Calculate next occurrence of this day
        today = datetime.now()
        days_ahead = day_of_week - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        target_date = today + timedelta(days=days_ahead)

        classes = client.get_classes(target_date)
        is_reference = False
        is_special_day = False
        reference_slots = None
        reference_date = None

        # If no classes found (schedule not published yet), try last week's same day
        if not classes:
            past_date = today + timedelta(days=days_ahead - 7)
            classes = client.get_classes(past_date)
            is_reference = True
            target_date = past_date
        else:
            # Check if this might be a special/holiday schedule (few classes)
            # Threshold: if <= 4 unique time slots, it's likely a special day
            unique_times = set(cls.get('time', '')[:5] for cls in classes if cls.get('time'))
            if len(unique_times) <= 4:
                # Fetch last week's schedule as reference for typical day
                past_date = today + timedelta(days=days_ahead - 7)
                reference_classes = client.get_classes(past_date)
                reference_unique_times = set(cls.get('time', '')[:5] for cls in reference_classes if cls.get('time'))

                # If last week had more classes, include it as reference
                if len(reference_unique_times) > len(unique_times):
                    is_special_day = True
                    reference_date = past_date
                    reference_slots = _group_classes_by_time(reference_classes)

        # Group classes by time, then by class type
        time_slots = _group_classes_by_time(classes)

        # Sort and format response
        result = []
        for time in sorted(time_slots.keys()):
            result.append({
                'time': time,
                'classes': sorted(time_slots[time])
            })

        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        response_data = {
            'date': target_date.strftime('%Y-%m-%d'),
            'date_display': target_date.strftime('%d/%m/%Y'),
            'day_name': day_names[day_of_week],
            'is_reference': is_reference,
            'reference_note': 'Schedule based on last week (next week not published yet)' if is_reference else None,
            'slots': result
        }

        # Include typical schedule if this is a special day
        if is_special_day and reference_slots:
            reference_result = []
            for time in sorted(reference_slots.keys()):
                reference_result.append({
                    'time': time,
                    'classes': sorted(reference_slots[time])
                })
            response_data['is_special_day'] = True
            response_data['special_day_note'] = f'This day appears to have a reduced schedule ({len(result)} time slots vs {len(reference_result)} typical)'
            response_data['typical_slots'] = reference_result
            response_data['typical_date'] = reference_date.strftime('%Y-%m-%d')
            response_data['typical_date_display'] = reference_date.strftime('%d/%m/%Y')

        return jsonify(response_data)

    except SessionExpiredError:
        return jsonify({'error': 'Session expired. Please reconnect WodBuster.'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@booking_bp.route('/book-now/<int:booking_id>', methods=['POST'])
@login_required
def book_now(booking_id):
    """Manually trigger a booking attempt."""
    booking = Booking.query.filter_by(id=booking_id, user_id=current_user.id).first_or_404()

    if not current_user.box_url:
        flash('WodBuster not connected', 'error')
        return redirect(url_for('booking.dashboard'))

    try:
        client = WodBusterClient(current_user.box_url)
        cookies = current_user.get_wodbuster_cookies()

        if not cookies or not client.restore_session(cookies):
            flash('Session expired. Please reconnect your WodBuster account.', 'warning')
            return redirect(url_for('auth.connect_wodbuster'))

        # Calculate target date (next occurrence of the booking day)
        today = datetime.now()
        days_ahead = booking.day_of_week - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        target_date = today + timedelta(days=days_ahead)

        # Debug logging
        from flask import current_app
        current_app.logger.info(f'Today: {today}, day_of_week: {booking.day_of_week}, days_ahead: {days_ahead}')
        current_app.logger.info(f'Target date: {target_date.strftime("%Y-%m-%d")} ({target_date.strftime("%A")})')
        current_app.logger.info(f'Looking for: {booking.class_type} at {booking.time}')

        # Find the class
        cls = client.find_class(target_date, booking.time, booking.class_type)

        if not cls:
            booking.status = 'failed'
            booking.last_error = 'Class not found'
            booking.last_attempt = datetime.utcnow()
            booking.fail_count += 1

            log = BookingLog(
                booking_id=booking.id,
                status='failed',
                message='Class not found',
                target_date=target_date.date()
            )
            db.session.add(log)
            db.session.commit()

            flash(f'Class not found: {booking.class_type} at {booking.time}', 'error')
            return redirect(url_for('booking.dashboard'))

        # Try to book
        if client.book_class(cls['id']):
            booking.status = 'success'
            booking.last_attempt = datetime.utcnow()
            booking.success_count += 1
            booking.last_error = None

            log = BookingLog(
                booking_id=booking.id,
                status='success',
                message=f'Booked successfully: {cls["name"]}',
                target_date=target_date.date()
            )
            db.session.add(log)
            db.session.commit()

            flash(f'Booked successfully: {cls["name"]} on {target_date.strftime("%d/%m")} at {booking.time}', 'success')
        else:
            raise Exception('Booking failed')

    except Exception as e:
        booking.status = 'failed'
        booking.last_error = str(e)
        booking.last_attempt = datetime.utcnow()
        booking.fail_count += 1

        log = BookingLog(
            booking_id=booking.id,
            status='failed',
            message=str(e),
            target_date=datetime.now().date()
        )
        db.session.add(log)
        db.session.commit()

        flash(f'Booking error: {str(e)}', 'error')

    return redirect(url_for('booking.dashboard'))


@booking_bp.route('/logs/<int:booking_id>')
@login_required
def booking_logs(booking_id):
    """View booking attempt logs."""
    booking = Booking.query.filter_by(id=booking_id, user_id=current_user.id).first_or_404()
    logs = BookingLog.query.filter_by(booking_id=booking_id).order_by(BookingLog.created_at.desc()).limit(20).all()

    return render_template('booking/logs.html', booking=booking, logs=logs)


@booking_bp.route('/my-reservations')
@login_required
def my_reservations():
    """View user's upcoming reservations from WodBuster."""
    if not current_user.box_url:
        flash('WodBuster not connected', 'warning')
        return redirect(url_for('auth.connect_wodbuster'))

    reservations = []
    error = None

    try:
        client = WodBusterClient(current_user.box_url)
        cookies = current_user.get_wodbuster_cookies()

        if not cookies or not client.restore_session(cookies):
            flash('Session expired. Please reconnect your WodBuster account.', 'warning')
            return redirect(url_for('auth.connect_wodbuster'))

        reservations = client.get_my_reservations(days_ahead=7)

    except SessionExpiredError:
        flash('Session expired. Please reconnect your WodBuster account.', 'warning')
        return redirect(url_for('auth.connect_wodbuster'))
    except Exception as e:
        error = str(e)
        from flask import current_app
        current_app.logger.error(f'Error fetching reservations: {e}')

    return render_template('booking/my_reservations.html', reservations=reservations, error=error)


@booking_bp.route('/toggle-notifications', methods=['POST'])
@login_required
def toggle_notifications():
    """Toggle email notifications for the user."""
    from app.models import db

    # Checkbox sends value only when checked
    current_user.email_notifications = 'email_notifications' in request.form
    db.session.commit()

    status = 'enabled' if current_user.email_notifications else 'disabled'
    flash(f'Email notifications {status}', 'success')
    return redirect(url_for('booking.dashboard'))


@booking_bp.route('/test-email', methods=['POST'])
@login_required
def test_email():
    """Send a test email to verify email configuration."""
    from app.email import send_test_email

    success, message = send_test_email(current_user)

    if success:
        flash(f'Test email sent to {current_user.email}. Check your inbox!', 'success')
    else:
        flash(f'Failed to send test email: {message}', 'error')

    return redirect(url_for('booking.dashboard'))


@booking_bp.route('/debug-account')
@login_required
def debug_account():
    """Debug: show raw account page HTML from WodBuster."""
    if not current_user.box_url:
        return jsonify({'error': 'WodBuster not connected'}), 400

    try:
        client = WodBusterClient(current_user.box_url)
        cookies = current_user.get_wodbuster_cookies()

        if not cookies or not client.restore_session(cookies):
            return jsonify({'error': 'Session expired'}), 401

        # Fetch the athlete default page
        import cloudscraper
        url = f'{current_user.box_url}/athlete/default.aspx'
        response = client.session.get(url, timeout=15)

        # Return just the relevant section (look for credits info)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'lxml')

        # Find all spans that might contain credits info
        relevant = []
        for span in soup.find_all(['span', 'div']):
            text = span.get_text(strip=True).lower()
            if any(kw in text for kw in ['clase', 'bono', 'crédito', 'credit', 'sueltas']):
                relevant.append({
                    'tag': span.name,
                    'id': span.get('id'),
                    'class': span.get('class'),
                    'text': span.get_text(strip=True)[:200]
                })

        # Also get account info
        account_info = client.get_account_info()

        return jsonify({
            'account_info': account_info,
            'relevant_elements': relevant[:20],
            'page_length': len(response.text)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@booking_bp.route('/cancel-reservation/<int:class_id>/<int:booking_id>', methods=['POST'])
@login_required
def cancel_reservation(class_id, booking_id):
    """Cancel a reservation on WodBuster."""
    if not current_user.box_url:
        flash('WodBuster not connected', 'error')
        return redirect(url_for('booking.my_reservations'))

    try:
        client = WodBusterClient(current_user.box_url)
        cookies = current_user.get_wodbuster_cookies()

        if not cookies or not client.restore_session(cookies):
            flash('Session expired. Please reconnect your WodBuster account.', 'warning')
            return redirect(url_for('auth.connect_wodbuster'))

        if client.cancel_booking(class_id, booking_id):
            flash('Reservation cancelled successfully', 'success')
        else:
            flash('Failed to cancel reservation', 'error')

    except SessionExpiredError:
        flash('Session expired. Please reconnect your WodBuster account.', 'warning')
        return redirect(url_for('auth.connect_wodbuster'))
    except Exception as e:
        flash(f'Error cancelling reservation: {str(e)}', 'error')

    return redirect(url_for('booking.my_reservations'))


@booking_bp.route('/set-language/<language>')
def set_language(language):
    """Set user's preferred language."""
    from flask import current_app
    if language in current_app.config.get('LANGUAGES', ['es', 'en']):
        session['language'] = language
    return redirect(request.referrer or url_for('booking.index'))
