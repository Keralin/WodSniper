"""Background scheduler for automated bookings."""

import logging
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
MAX_RETRY_ATTEMPTS = 3  # Maximum retry attempts per booking
RETRY_DELAY = 1  # Seconds between retry attempts
MAX_PARALLEL_USERS = 50  # Maximum concurrent user booking threads


def init_scheduler(app):
    """Initialize the scheduler with the Flask app context."""

    # Check every minute for boxes that have their booking window opening
    scheduler.add_job(
        func=lambda: check_booking_windows(app),
        trigger='interval',
        minutes=1,
        id='booking_window_check',
        name='Booking Window Check',
        replace_existing=True
    )

    # Pre-refresh sessions 10 minutes before each box's booking window
    # Runs every minute and checks which boxes need session refresh
    scheduler.add_job(
        func=lambda: check_session_refresh(app),
        trigger='interval',
        minutes=1,
        id='session_refresh_check',
        name='Session Refresh Check',
        replace_existing=True
    )

    scheduler.start()
    logger.info('Scheduler initialized - checking booking windows every minute')

    # Log scheduled jobs for verification
    for job in scheduler.get_jobs():
        logger.info(f'Scheduled job: {job.name} - Next run: {job.next_run_time}')


def check_booking_windows(app):
    """
    Check if any box has its booking window opening right now.
    Runs every minute to support per-box scheduling.
    """
    from app.models import db, Box, User, Booking

    with app.app_context():
        now = datetime.now()
        current_day = now.weekday()  # 0=Monday, 6=Sunday
        current_hour = now.hour
        current_minute = now.minute

        # Find boxes whose booking window opens in 5 minutes
        # We trigger 5 min early to wait precisely until the exact time
        target_minute = (current_minute + 5) % 60
        target_hour = current_hour + ((current_minute + 5) // 60)
        if target_hour >= 24:
            # Would be next day - skip for now
            return

        boxes_opening = Box.query.filter(
            Box.booking_open_day == current_day,
            Box.booking_open_hour == target_hour,
            Box.booking_open_minute == target_minute
        ).all()

        if not boxes_opening:
            return

        for box in boxes_opening:
            logger.info(f'Booking window opening for box {box.name} at {target_hour:02d}:{target_minute:02d}')
            run_scheduled_bookings_for_box(app, box)


def check_session_refresh(app):
    """
    Check if any box needs session refresh (10 min before booking window).
    """
    from app.models import db, Box

    with app.app_context():
        now = datetime.now()
        current_day = now.weekday()
        current_hour = now.hour
        current_minute = now.minute

        # Find boxes whose booking window opens in 10 minutes
        target_minute = (current_minute + 10) % 60
        target_hour = current_hour + ((current_minute + 10) // 60)
        if target_hour >= 24:
            return

        boxes_to_refresh = Box.query.filter(
            Box.booking_open_day == current_day,
            Box.booking_open_hour == target_hour,
            Box.booking_open_minute == target_minute
        ).all()

        if not boxes_to_refresh:
            return

        for box in boxes_to_refresh:
            logger.info(f'Refreshing sessions for box {box.name} (window opens in 10 min)')
            refresh_sessions_for_box(app, box)


def refresh_sessions_for_box(app, box):
    """Refresh sessions for all users of a specific box."""
    from app.models import db, User, Booking
    from app.scraper import WodBusterClient, LoginError

    logger.info(f'=== Refreshing sessions for box: {box.name} ===')

    with app.app_context():
        # Get users with active bookings for this box
        users = User.query.filter(
            User.box_id == box.id,
            User.wodbuster_email.isnot(None)
        ).join(Booking).filter(
            Booking.is_active == True
        ).distinct().all()

        if not users:
            logger.info(f'No users with active bookings for box {box.name}')
            return

        logger.info(f'Refreshing sessions for {len(users)} users')

        for user in users:
            try:
                logger.info(f'Refreshing session for {user.email}')
                client = WodBusterClient(user.effective_box_url)

                wodbuster_password = user.get_wodbuster_password()
                if wodbuster_password and user.wodbuster_email:
                    client.login(user.wodbuster_email, wodbuster_password)
                    user.set_wodbuster_cookies(client.get_cookies())
                    db.session.commit()
                    logger.info(f'Session refreshed for {user.email}')
                else:
                    logger.warning(f'No credentials for {user.email}')

            except LoginError as e:
                logger.error(f'Failed to refresh session for {user.email}: {e}')
            except Exception as e:
                logger.exception(f'Error refreshing session for {user.email}: {e}')

            time.sleep(2)  # Avoid rate limiting

    logger.info(f'=== Session refresh complete for box: {box.name} ===')


def run_scheduled_bookings_for_box(app, box):
    """Execute scheduled bookings for a specific box when its window opens."""
    from app.models import db, User, Booking, BookingLog
    from app.scraper import WodBusterClient
    from collections import defaultdict

    logger.info('=' * 60)
    logger.info(f'=== BOOKING WINDOW FOR BOX: {box.name} ===')
    logger.info(f'Current time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")}')

    with app.app_context():
        # Get active bookings for users of this box
        bookings = Booking.query.filter_by(
            is_active=True
        ).join(User).filter(
            User.box_id == box.id,
            User.wodbuster_cookie.isnot(None)
        ).all()

        if not bookings:
            logger.info(f'No active bookings for box {box.name}')
            return

        logger.info(f'Found {len(bookings)} active bookings for box {box.name}')

        # Group bookings by user for parallel processing
        bookings_by_user = defaultdict(list)
        for booking in bookings:
            bookings_by_user[booking.user_id].append({
                'id': booking.id,
                'day_of_week': booking.day_of_week,
                'day_name': booking.day_name,
                'time': booking.time,
                'class_type': booking.class_type,
            })

        user_ids = list(bookings_by_user.keys())
        logger.info(f'Processing {len(user_ids)} users in parallel')

        # Wait until exact opening time
        now = datetime.now()
        target_time = now.replace(
            hour=box.booking_open_hour,
            minute=box.booking_open_minute,
            second=0,
            microsecond=0
        )

        if now < target_time:
            wait_seconds = (target_time - now).total_seconds()
            logger.info(f'Waiting {wait_seconds:.1f} seconds until {box.booking_open_hour:02d}:{box.booking_open_minute:02d}...')
            time.sleep(max(0, wait_seconds - 1))

            # Precise wait for the last second
            while datetime.now() < target_time:
                time.sleep(0.01)

        logger.info(f'=== BOOKING START at {datetime.now().strftime("%H:%M:%S.%f")} ===')

        # Process users in parallel
        results_by_user = {}
        num_workers = min(len(user_ids), MAX_PARALLEL_USERS)

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = {
                executor.submit(
                    _process_user_bookings,
                    app,
                    user_id,
                    bookings_by_user[user_id]
                ): user_id
                for user_id in user_ids
            }

            for future in as_completed(futures):
                user_id = futures[future]
                try:
                    user_results = future.result()
                    if user_results:
                        results_by_user[user_id] = user_results
                except Exception as e:
                    logger.error(f'Error processing user {user_id}: {e}')

        total_time = (datetime.now() - target_time).total_seconds()
        logger.info(f'=== BOOKING COMPLETE FOR BOX: {box.name} in {total_time:.2f}s ===')

        _send_booking_notifications(app, results_by_user)

        logger.info('=' * 60)


def refresh_all_sessions(app):
    """
    Refresh sessions for all users with active bookings.
    Legacy function - kept for manual triggering.
    """
    from app.models import db, User, Booking
    from app.scraper import WodBusterClient, LoginError

    logger.info('=== Starting pre-booking session refresh ===')

    with app.app_context():
        # Get unique users with active bookings
        users_with_bookings = db.session.query(User).join(Booking).filter(
            Booking.is_active == True,
            User.box_url.isnot(None),
            User.wodbuster_email.isnot(None)
        ).distinct().all()

        if not users_with_bookings:
            logger.info('No users with active bookings found')
            return

        logger.info(f'Refreshing sessions for {len(users_with_bookings)} users')

        for user in users_with_bookings:
            try:
                logger.info(f'Refreshing session for {user.email}')
                client = WodBusterClient(user.effective_box_url)

                # Always do a fresh login to get new cookies
                wodbuster_password = user.get_wodbuster_password()

                if wodbuster_password and user.wodbuster_email:
                    client.login(user.wodbuster_email, wodbuster_password)
                    user.set_wodbuster_cookies(client.get_cookies())
                    db.session.commit()
                    logger.info(f'Session refreshed successfully for {user.email}')
                else:
                    logger.warning(f'No credentials stored for {user.email}, skipping refresh')

            except LoginError as e:
                logger.error(f'Failed to refresh session for {user.email}: {e}')
            except Exception as e:
                logger.exception(f'Unexpected error refreshing session for {user.email}: {e}')

            # Small delay between users to avoid rate limiting
            time.sleep(2)

    logger.info('=== Session refresh complete ===')


def run_scheduled_bookings(app):
    """Execute all scheduled bookings when booking window opens (parallel processing)."""
    from app.models import db, User, Booking, BookingLog
    from app.scraper import WodBusterClient
    from collections import defaultdict

    logger.info('=' * 60)
    logger.info('=== BOOKING WINDOW TRIGGERED ===')
    logger.info(f'Current time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")}')

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

        logger.info(f'Found {len(bookings)} active bookings')

        # Group bookings by user for parallel processing
        bookings_by_user = defaultdict(list)
        for booking in bookings:
            bookings_by_user[booking.user_id].append({
                'id': booking.id,
                'day_of_week': booking.day_of_week,
                'day_name': booking.day_name,
                'time': booking.time,
                'class_type': booking.class_type,
            })

        user_ids = list(bookings_by_user.keys())
        logger.info(f'Processing {len(user_ids)} users in parallel')

        # Wait until exactly 13:00 UTC (14:00 Spanish time)
        now = datetime.now()
        target_time = now.replace(hour=13, minute=0, second=0, microsecond=0)

        if now < target_time:
            wait_seconds = (target_time - now).total_seconds()
            logger.info(f'Waiting {wait_seconds:.1f} seconds until 13:00 UTC (14:00 Spanish)...')
            time.sleep(max(0, wait_seconds - 1))

            # Precise wait for the last second
            logger.debug('Entering precision wait loop...')
            while datetime.now() < target_time:
                time.sleep(0.01)

        logger.info(f'=== BOOKING START at {datetime.now().strftime("%H:%M:%S.%f")} ===')

        # Process users in parallel
        results_by_user = {}
        num_workers = min(len(user_ids), MAX_PARALLEL_USERS)

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = {
                executor.submit(
                    _process_user_bookings,
                    app,
                    user_id,
                    bookings_by_user[user_id]
                ): user_id
                for user_id in user_ids
            }

            for future in as_completed(futures):
                user_id = futures[future]
                try:
                    user_results = future.result()
                    if user_results:
                        results_by_user[user_id] = user_results
                except Exception as e:
                    logger.error(f'Error processing user {user_id}: {e}')

        total_time = (datetime.now() - target_time).total_seconds()
        logger.info(f'=== BOOKING RUN COMPLETE in {total_time:.2f}s ===')

        # Send email notifications to each user
        _send_booking_notifications(app, results_by_user)

        logger.info('=' * 60)


def _process_user_bookings(app, user_id, booking_data_list):
    """
    Process all bookings for a single user in a dedicated thread.

    Each user gets their own thread with a fresh DB session for thread-safety.
    This allows parallel processing of different users' bookings.

    Args:
        app: Flask application instance
        user_id: User ID to process bookings for
        booking_data_list: List of booking data dicts with id, day_of_week, time, class_type

    Returns:
        list: Results for each booking
    """
    from app.models import db, User, Booking, BookingLog
    from app.scraper import (
        WodBusterClient, SessionExpiredError, ClassNotFoundError,
        NoClassesAvailableError, ClassFullError, BookingError, RateLimitError, LoginError
    )

    results = []

    with app.app_context():
        user = User.query.get(user_id)
        if not user:
            logger.error(f'User {user_id} not found')
            return results

        logger.info(f'[Thread-{user_id}] Processing {len(booking_data_list)} bookings for {user.email}')

        # Initialize client once per user
        client = WodBusterClient(user.effective_box_url)
        session_valid = False

        # Try to restore session
        cookies = user.get_wodbuster_cookies()
        if cookies:
            session_valid = client.restore_session(cookies)

        # If session expired, try re-login
        if not session_valid:
            logger.info(f'[Thread-{user_id}] Session expired, re-logging...')
            wodbuster_password = user.get_wodbuster_password()

            if wodbuster_password and user.wodbuster_email:
                try:
                    client.login(user.wodbuster_email, wodbuster_password)
                    user.set_wodbuster_cookies(client.get_cookies())
                    db.session.commit()
                    session_valid = True
                    logger.info(f'[Thread-{user_id}] Re-login successful')
                except LoginError as e:
                    logger.error(f'[Thread-{user_id}] Re-login failed: {e}')
                    # Return failure for all bookings
                    for bd in booking_data_list:
                        results.append({
                            'user_id': user_id,
                            'status': 'failed',
                            'day_name': bd['day_name'],
                            'time': bd['time'],
                            'class_type': bd['class_type'],
                            'message': f'Session expired and re-login failed: {e}',
                            'target_date': None
                        })
                    return results
            else:
                logger.error(f'[Thread-{user_id}] No credentials for re-login')
                for bd in booking_data_list:
                    results.append({
                        'user_id': user_id,
                        'status': 'failed',
                        'day_name': bd['day_name'],
                        'time': bd['time'],
                        'class_type': bd['class_type'],
                        'message': 'Session expired and no credentials stored',
                        'target_date': None
                    })
                return results

        # Process each booking for this user
        for booking_data in booking_data_list:
            booking = Booking.query.get(booking_data['id'])
            if not booking:
                continue

            result = _process_single_booking_with_client(booking, client, app, user)
            if result:
                results.append(result)

        logger.info(f'[Thread-{user_id}] Completed all bookings for {user.email}')

    return results


def _process_single_booking_with_client(booking, client, app, user):
    """
    Process a single booking using an existing client session.

    Args:
        booking: Booking model instance
        client: Pre-authenticated WodBusterClient
        app: Flask application instance
        user: User model instance

    Returns:
        dict: Result with status, booking info, and message
    """
    from app.models import db, BookingLog
    from app.scraper import (
        ClassNotFoundError, NoClassesAvailableError, ClassFullError,
        BookingError, RateLimitError
    )

    logger.info(f'[Thread-{user.id}] Booking {booking.id}: {booking.day_name} {booking.time} {booking.class_type}')
    target_date = None
    message = ''
    last_error = None

    # Calculate target date
    today = datetime.now()
    days_ahead = booking.day_of_week - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    target_date = today + timedelta(days=days_ahead)

    # Retry loop
    for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
        try:
            logger.debug(f'[Thread-{user.id}] Attempt {attempt}/{MAX_RETRY_ATTEMPTS} for booking {booking.id}')

            # Find and book the class
            cls = client.find_class(target_date, booking.time, booking.class_type)

            if not cls:
                raise ClassNotFoundError(f'Class not found: {booking.class_type} at {booking.time}')

            if client.book_class(cls['id']):
                booking.status = 'success'
                booking.success_count += 1
                booking.last_error = None
                message = f'Booked: {cls["name"]} on {target_date.strftime("%d/%m")}'
                if attempt > 1:
                    message += f' (attempt {attempt})'
                logger.info(f'[Thread-{user.id}] {message}')
                break
            else:
                raise BookingError('Booking returned false')

        except ClassFullError as e:
            booking.status = 'waiting'
            booking.last_error = str(e)
            message = 'Class is full - added to waitlist'
            logger.warning(f'[Thread-{user.id}] Class full for booking {booking.id}')
            break

        except NoClassesAvailableError as e:
            booking.status = 'failed'
            booking.fail_count += 1
            booking.last_error = str(e)
            message = 'No classes available (holiday or closed)'
            logger.warning(f'[Thread-{user.id}] No classes for booking {booking.id}')
            break

        except (ClassNotFoundError, BookingError, RateLimitError) as e:
            last_error = str(e)
            logger.warning(f'[Thread-{user.id}] Attempt {attempt} failed: {e}')

            if attempt < MAX_RETRY_ATTEMPTS:
                time.sleep(RETRY_DELAY)
            else:
                booking.status = 'failed'
                booking.fail_count += 1
                booking.last_error = last_error
                message = f'{last_error} (after {MAX_RETRY_ATTEMPTS} attempts)'

        except Exception as e:
            last_error = str(e)
            logger.exception(f'[Thread-{user.id}] Unexpected error: {e}')

            if attempt < MAX_RETRY_ATTEMPTS:
                time.sleep(RETRY_DELAY)
            else:
                booking.status = 'failed'
                booking.fail_count += 1
                booking.last_error = last_error
                message = f'{last_error} (after {MAX_RETRY_ATTEMPTS} attempts)'

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

    return {
        'user_id': user.id,
        'status': booking.status,
        'day_name': booking.day_name,
        'time': booking.time,
        'class_type': booking.class_type,
        'message': message,
        'target_date': target_date.strftime('%d/%m/%Y') if target_date else None
    }


def _process_single_booking(booking, app):
    """
    Process a single booking with retry logic.
    Legacy function for backwards compatibility.

    Returns:
        dict: Result with status, booking info, and message for email notification
    """
    from app.models import db, BookingLog
    from app.scraper import (
        WodBusterClient, SessionExpiredError, ClassNotFoundError,
        NoClassesAvailableError, ClassFullError, BookingError, RateLimitError, LoginError
    )

    user = booking.user
    logger.info(f'Processing booking {booking.id}: {booking.day_name} {booking.time} {booking.class_type} (user: {user.email})')
    target_date = None
    message = ''
    last_error = None

    # Calculate target date
    today = datetime.now()
    days_ahead = booking.day_of_week - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    target_date = today + timedelta(days=days_ahead)

    # Retry loop
    for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
        try:
            logger.info(f'Attempt {attempt}/{MAX_RETRY_ATTEMPTS} for booking {booking.id}')

            client = WodBusterClient(user.effective_box_url)
            cookies = user.get_wodbuster_cookies()
            session_valid = False

            # Try to restore session with existing cookies
            if cookies:
                session_valid = client.restore_session(cookies)

            # If session expired, try re-login with stored credentials
            if not session_valid:
                logger.info(f'Session expired for {user.email}, attempting re-login...')
                wodbuster_password = user.get_wodbuster_password()

                if wodbuster_password and user.wodbuster_email:
                    try:
                        client.login(user.wodbuster_email, wodbuster_password)
                        # Save new cookies for future use
                        user.set_wodbuster_cookies(client.get_cookies())
                        db.session.commit()
                        logger.info(f'Re-login successful for {user.email}')
                        session_valid = True
                    except LoginError as e:
                        logger.error(f'Re-login failed for {user.email}: {e}')
                        raise SessionExpiredError(f'Session expired and re-login failed: {e}')
                else:
                    raise SessionExpiredError('Session expired and no credentials stored for re-login')

            # Find and book the class
            logger.debug(f'Searching for class: {booking.class_type} at {booking.time} on {target_date.strftime("%Y-%m-%d")}')
            cls = client.find_class(target_date, booking.time, booking.class_type)

            if not cls:
                raise ClassNotFoundError(f'Class not found: {booking.class_type} at {booking.time}')

            logger.debug(f'Found class: {cls}')

            if client.book_class(cls['id']):
                booking.status = 'success'
                booking.success_count += 1
                booking.last_error = None
                message = f'Booked: {cls["name"]} on {target_date.strftime("%d/%m")}'
                if attempt > 1:
                    message += f' (attempt {attempt})'
                logger.info(message)
                break  # Success - exit retry loop
            else:
                raise BookingError('Booking returned false')

        except ClassFullError as e:
            # Don't retry if class is full - no point
            booking.status = 'waiting'
            booking.last_error = str(e)
            message = 'Class is full - added to waitlist'
            logger.warning(f'Class full for booking {booking.id}, not retrying')
            break  # Exit retry loop

        except NoClassesAvailableError as e:
            # Don't retry if no classes for this day (holiday/closed) - no point
            booking.status = 'failed'
            booking.fail_count += 1
            booking.last_error = str(e)
            message = f'No classes available (holiday or closed)'
            logger.warning(f'No classes for booking {booking.id} on {target_date}, not retrying')
            break  # Exit retry loop

        except (SessionExpiredError, ClassNotFoundError, BookingError, RateLimitError) as e:
            last_error = str(e)
            logger.warning(f'Attempt {attempt} failed for booking {booking.id}: {e}')

            if attempt < MAX_RETRY_ATTEMPTS:
                logger.info(f'Retrying in {RETRY_DELAY} seconds...')
                time.sleep(RETRY_DELAY)
            else:
                # Final attempt failed
                booking.status = 'failed'
                booking.fail_count += 1
                booking.last_error = last_error
                message = f'{last_error} (after {MAX_RETRY_ATTEMPTS} attempts)'
                logger.error(f'Booking {booking.id} failed after {MAX_RETRY_ATTEMPTS} attempts')

        except Exception as e:
            last_error = str(e)
            logger.exception(f'Unexpected error on attempt {attempt} for booking {booking.id}')

            if attempt < MAX_RETRY_ATTEMPTS:
                logger.info(f'Retrying in {RETRY_DELAY} seconds...')
                time.sleep(RETRY_DELAY)
            else:
                booking.status = 'failed'
                booking.fail_count += 1
                booking.last_error = last_error
                message = f'{last_error} (after {MAX_RETRY_ATTEMPTS} attempts)'

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


def check_pending_bookings(app):
    """Check for pending bookings (debug/development mode)."""
    logger.info('=== DEBUG: Running scheduled bookings check ===')
    run_bookings_now(app)


def run_bookings_now(app, send_emails=True):
    """Execute all scheduled bookings immediately (for testing, parallel processing)."""
    from app.models import db, User, Booking, BookingLog
    from app.scraper import WodBusterClient
    from collections import defaultdict

    logger.info('=== Starting IMMEDIATE booking run (parallel) ===')
    start_time = datetime.now()

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

        # Group bookings by user for parallel processing
        bookings_by_user = defaultdict(list)
        for booking in bookings:
            bookings_by_user[booking.user_id].append({
                'id': booking.id,
                'day_of_week': booking.day_of_week,
                'day_name': booking.day_name,
                'time': booking.time,
                'class_type': booking.class_type,
            })

        user_ids = list(bookings_by_user.keys())
        logger.info(f'Processing {len(user_ids)} users in parallel')

        # Process users in parallel
        results_by_user = {}
        num_workers = min(len(user_ids), MAX_PARALLEL_USERS)

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = {
                executor.submit(
                    _process_user_bookings,
                    app,
                    user_id,
                    bookings_by_user[user_id]
                ): user_id
                for user_id in user_ids
            }

            for future in as_completed(futures):
                user_id = futures[future]
                try:
                    user_results = future.result()
                    if user_results:
                        results_by_user[user_id] = user_results
                except Exception as e:
                    logger.error(f'Error processing user {user_id}: {e}')

        total_time = (datetime.now() - start_time).total_seconds()
        logger.info(f'=== IMMEDIATE booking run complete in {total_time:.2f}s ===')

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
