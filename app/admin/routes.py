"""Admin panel routes."""

from functools import wraps
from datetime import datetime, timedelta

from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.admin import admin_bp
from app.models import db, User, Booking, BookingLog


def admin_required(f):
    """Decorator to require admin access."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            abort(404)  # Hide admin routes from non-admins
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/')
@admin_required
def dashboard():
    """Admin dashboard with stats."""
    # User stats
    total_users = User.query.count()
    users_with_wodbuster = User.query.filter(User.box_url.isnot(None)).count()

    # Booking stats
    total_bookings = Booking.query.count()
    active_bookings = Booking.query.filter_by(is_active=True).count()

    # Success rate from logs (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_logs = BookingLog.query.filter(BookingLog.created_at >= thirty_days_ago).all()

    success_count = sum(1 for log in recent_logs if log.status == 'success')
    failed_count = sum(1 for log in recent_logs if log.status == 'failed')
    total_attempts = success_count + failed_count
    success_rate = (success_count / total_attempts * 100) if total_attempts > 0 else 0

    # Recent activity
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    recent_booking_logs = BookingLog.query.order_by(BookingLog.created_at.desc()).limit(10).all()

    return render_template('admin/dashboard.html',
                           total_users=total_users,
                           users_with_wodbuster=users_with_wodbuster,
                           total_bookings=total_bookings,
                           active_bookings=active_bookings,
                           success_count=success_count,
                           failed_count=failed_count,
                           success_rate=success_rate,
                           recent_users=recent_users,
                           recent_booking_logs=recent_booking_logs)


@admin_bp.route('/users')
@admin_required
def users():
    """List all users."""
    page = request.args.get('page', 1, type=int)
    users = User.query.order_by(User.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('admin/users.html', users=users)


@admin_bp.route('/users/<int:user_id>')
@admin_required
def user_detail(user_id):
    """View user details."""
    user = User.query.get_or_404(user_id)
    bookings = user.bookings.order_by(Booking.day_of_week).all()

    # Get recent logs for this user's bookings
    booking_ids = [b.id for b in bookings]
    recent_logs = BookingLog.query.filter(
        BookingLog.booking_id.in_(booking_ids)
    ).order_by(BookingLog.created_at.desc()).limit(20).all() if booking_ids else []

    return render_template('admin/user_detail.html',
                           user=user,
                           bookings=bookings,
                           recent_logs=recent_logs)


@admin_bp.route('/users/<int:user_id>/verify-email', methods=['POST'])
@admin_required
def verify_user_email(user_id):
    """Manually verify a user's email."""
    user = User.query.get_or_404(user_id)

    if user.email_verified:
        flash(f'{user.email} is already verified', 'info')
    else:
        user.email_verified = True
        db.session.commit()
        flash(f'{user.email} has been verified', 'success')

    return redirect(url_for('admin.user_detail', user_id=user_id))


@admin_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def reset_user_password(user_id):
    """Send password reset email to user."""
    from app.email import send_password_reset_email

    user = User.query.get_or_404(user_id)
    send_password_reset_email(user)
    flash(f'Password reset email sent to {user.email}', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))


@admin_bp.route('/users/<int:user_id>/toggle-admin', methods=['POST'])
@admin_required
def toggle_admin(user_id):
    """Toggle admin status for user."""
    user = User.query.get_or_404(user_id)

    # Prevent removing own admin status
    if user.id == current_user.id:
        flash('Cannot change your own admin status', 'error')
        return redirect(url_for('admin.user_detail', user_id=user_id))

    user.is_admin = not user.is_admin
    db.session.commit()

    status = 'admin' if user.is_admin else 'regular user'
    flash(f'{user.email} is now a {status}', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Delete a user."""
    user = User.query.get_or_404(user_id)

    # Prevent self-deletion
    if user.id == current_user.id:
        flash('Cannot delete your own account', 'error')
        return redirect(url_for('admin.user_detail', user_id=user_id))

    email = user.email
    db.session.delete(user)
    db.session.commit()

    flash(f'User {email} deleted', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/bookings')
@admin_required
def bookings():
    """List all bookings."""
    page = request.args.get('page', 1, type=int)
    bookings = Booking.query.join(User).order_by(Booking.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('admin/bookings.html', bookings=bookings)


@admin_bp.route('/logs')
@admin_required
def logs():
    """View booking logs."""
    page = request.args.get('page', 1, type=int)
    logs = BookingLog.query.join(Booking).join(User).order_by(
        BookingLog.created_at.desc()
    ).paginate(page=page, per_page=50)
    return render_template('admin/logs.html', logs=logs)
