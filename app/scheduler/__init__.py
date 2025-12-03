"""Background scheduler for automated bookings."""

import logging
from datetime import datetime, timedelta
import threading
import time

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
_booking_lock = threading.Lock()
_last_booking_time = None
BOOKING_INTERVAL = 0.5  # Minimum seconds between bookings


def init_scheduler(app):
    """Initialize the scheduler with the Flask app context."""

    # Run booking check every Sunday at 12:55 (5 mins before 13:00 opening)
    scheduler.add_job(
        func=lambda: run_scheduled_bookings(app),
        trigger=CronTrigger(day_of_week='sun', hour=12, minute=55),
        id='weekly_booking_check',
        name='Weekly Booking Check',
        replace_existing=True
    )

    # Debug scheduler - disabled by default, change minutes=60 to lower value for testing
    if app.debug:
        scheduler.add_job(
            func=lambda: check_pending_bookings(app),
            trigger='interval',
            minutes=60,  # Set to 1 for testing, 60 to effectively disable
            id='debug_booking_check',
            name='Debug Booking Check',
            replace_existing=True
        )

    scheduler.start()
    logger.info('Scheduler initialized')


def run_scheduled_bookings(app):
    """Execute all scheduled bookings when booking window opens."""
    from app.models import db, User, Booking, BookingLog
    from app.scraper import WodBusterClient
    from collections import defaultdict

    logger.info('Starting scheduled booking run')

    with app.app_context():
        # Get all active bookings for today's day of week
        today = datetime.now()
        target_day = today.weekday()

        # For Sunday booking window, we book for the coming week
        bookings = Booking.query.filter_by(
            is_active=True
        ).join(User).filter(
            User.box_url.isnot(None),
            User.wodbuster_cookie.isnot(None)
        ).all()

        if not bookings:
            logger.info('No active bookings found')
            return

        logger.info(f'Found {len(bookings)} active bookings')

        # Wait until exactly 13:00
        now = datetime.now()
        target_time = now.replace(hour=13, minute=0, second=0, microsecond=0)

        if now < target_time:
            wait_seconds = (target_time - now).total_seconds()
            logger.info(f'Waiting {wait_seconds:.1f} seconds until 13:00')
            time.sleep(max(0, wait_seconds - 1))  # Wake up 1 second early

            # Precise wait for the last second
            while datetime.now() < target_time:
                time.sleep(0.01)

        # Collect results by user for email notifications
        results_by_user = defaultdict(list)

        # Process bookings with rate limiting
        for booking in bookings:
            try:
                result = _process_single_booking(booking, app)
                if result:
                    results_by_user[booking.user_id].append(result)
            except Exception as e:
                logger.error(f'Error processing booking {booking.id}: {e}')
                # Add error result
                results_by_user[booking.user_id].append({
                    'status': 'failed',
                    'day_name': booking.day_name,
                    'time': booking.time,
                    'class_type': booking.class_type,
                    'message': str(e),
                    'target_date': None
                })

            # Rate limiting between bookings
            _wait_for_rate_limit()

        # Send email notifications to each user
        _send_booking_notifications(app, results_by_user)


def _process_single_booking(booking, app):
    """
    Process a single booking.

    Returns:
        dict: Result with status, booking info, and message for email notification
    """
    from app.models import db, BookingLog
    from app.scraper import (
        WodBusterClient, SessionExpiredError, ClassNotFoundError,
        ClassFullError, BookingError, RateLimitError
    )

    user = booking.user
    logger.info(f'Processing booking {booking.id} for user {user.email}')
    target_date = None
    message = ''

    try:
        client = WodBusterClient(user.box_url)
        cookies = user.get_wodbuster_cookies()

        if not cookies or not client.restore_session(cookies):
            raise SessionExpiredError('Session expired')

        # Calculate target date
        today = datetime.now()
        days_ahead = booking.day_of_week - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        target_date = today + timedelta(days=days_ahead)

        # Find and book the class
        cls = client.find_class(target_date, booking.time, booking.class_type)

        if not cls:
            raise ClassNotFoundError(f'Class not found: {booking.class_type} at {booking.time}')

        if client.book_class(cls['id']):
            booking.status = 'success'
            booking.success_count += 1
            booking.last_error = None
            message = f'Booked: {cls["name"]} on {target_date.strftime("%d/%m")}'
            logger.info(message)
        else:
            raise BookingError('Booking returned false')

    except ClassFullError as e:
        booking.status = 'waiting'
        booking.last_error = str(e)
        message = 'Class is full - added to waitlist'
        logger.warning(f'Class full for booking {booking.id}')

    except (SessionExpiredError, ClassNotFoundError, BookingError, RateLimitError) as e:
        booking.status = 'failed'
        booking.fail_count += 1
        booking.last_error = str(e)
        message = str(e)
        logger.error(f'Booking {booking.id} failed: {e}')

    except Exception as e:
        booking.status = 'failed'
        booking.fail_count += 1
        booking.last_error = str(e)
        message = str(e)
        logger.exception(f'Unexpected error for booking {booking.id}')

    # Update booking
    booking.last_attempt = datetime.utcnow()

    # Create log entry
    log = BookingLog(
        booking_id=booking.id,
        status=booking.status,
        message=message[:500] if message else None,
        target_date=target_date.date() if target_date else None
    )

    with app.app_context():
        db.session.add(log)
        db.session.commit()

    # Return result for email notification
    return {
        'user_id': user.id,
        'status': booking.status,
        'day_name': booking.day_name,
        'time': booking.time,
        'class_type': booking.class_type,
        'message': message,
        'target_date': target_date.strftime('%d/%m/%Y') if target_date else None
    }


def _wait_for_rate_limit():
    """Enforce rate limiting between bookings."""
    global _last_booking_time

    with _booking_lock:
        now = time.time()
        if _last_booking_time:
            elapsed = now - _last_booking_time
            if elapsed < BOOKING_INTERVAL:
                time.sleep(BOOKING_INTERVAL - elapsed)
        _last_booking_time = time.time()


def check_pending_bookings(app):
    """Check for pending bookings (debug/development mode)."""
    logger.info('=== DEBUG: Running scheduled bookings check ===')
    run_bookings_now(app)


def run_bookings_now(app, send_emails=True):
    """Execute all scheduled bookings immediately (for testing)."""
    from app.models import db, User, Booking, BookingLog
    from app.scraper import WodBusterClient
    from collections import defaultdict

    logger.info('=== Starting IMMEDIATE booking run ===')

    with app.app_context():
        # Get all active bookings
        bookings = Booking.query.filter_by(
            is_active=True
        ).join(User).filter(
            User.box_url.isnot(None),
            User.wodbuster_cookie.isnot(None)
        ).all()

        if not bookings:
            logger.info('No active bookings found')
            return

        logger.info(f'Found {len(bookings)} active bookings to process')

        # Collect results by user for email notifications
        results_by_user = defaultdict(list)

        # Process bookings immediately (no waiting for 13:00)
        for booking in bookings:
            try:
                logger.info(f'Processing: {booking.day_name} {booking.time} {booking.class_type}')
                result = _process_single_booking(booking, app)
                if result:
                    results_by_user[booking.user_id].append(result)
            except Exception as e:
                logger.error(f'Error processing booking {booking.id}: {e}')
                results_by_user[booking.user_id].append({
                    'status': 'failed',
                    'day_name': booking.day_name,
                    'time': booking.time,
                    'class_type': booking.class_type,
                    'message': str(e),
                    'target_date': None
                })

            # Rate limiting between bookings
            _wait_for_rate_limit()

        # Send email notifications
        if send_emails:
            _send_booking_notifications(app, results_by_user)

    logger.info('=== Booking run complete ===')


def _send_booking_notifications(app, results_by_user):
    """Send email notifications to users about their booking results."""
    from app.models import User
    from app.email import send_booking_summary

    logger.info(f'Sending email notifications to {len(results_by_user)} users')

    with app.app_context():
        for user_id, results in results_by_user.items():
            try:
                user = User.query.get(user_id)
                if user and user.email_notifications:
                    success = send_booking_summary(user, results)
                    if success:
                        logger.info(f'Email sent to {user.email}')
                    else:
                        logger.warning(f'Failed to send email to {user.email}')
            except Exception as e:
                logger.error(f'Error sending notification to user {user_id}: {e}')


def shutdown_scheduler():
    """Shutdown the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info('Scheduler shut down')
