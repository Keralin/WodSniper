"""Email notification service for WodSniper."""

import logging
from typing import List, Dict, Any
from datetime import datetime

from flask import current_app, render_template_string
from flask_mail import Message

from app import mail

logger = logging.getLogger(__name__)


def send_booking_summary(user, results: List[Dict[str, Any]]):
    """
    Send a summary email after scheduled bookings run.

    Args:
        user: User object with email
        results: List of booking results with status, booking info, and message
    """
    if not user.email_notifications:
        logger.info(f'Email notifications disabled for user {user.email}')
        return False

    if not current_app.config.get('MAIL_USERNAME'):
        logger.warning('Email not configured (MAIL_USERNAME not set)')
        return False

    if not results:
        logger.info('No results to send')
        return False

    # Categorize results
    successful = [r for r in results if r['status'] == 'success']
    failed = [r for r in results if r['status'] == 'failed']
    waiting = [r for r in results if r['status'] == 'waiting']

    # Build email subject
    total = len(results)
    success_count = len(successful)

    if success_count == total:
        subject = f'WodSniper: {success_count} classes booked successfully!'
        emoji = ''
    elif success_count > 0:
        subject = f'WodSniper: {success_count}/{total} classes booked'
        emoji = ''
    else:
        subject = f'WodSniper: Booking issues - action needed'
        emoji = ''

    # Render email body
    html_body = render_booking_email(user, successful, failed, waiting)

    try:
        msg = Message(
            subject=subject,
            recipients=[user.email],
            html=html_body
        )
        mail.send(msg)
        logger.info(f'Booking summary email sent to {user.email}')
        return True

    except Exception as e:
        logger.error(f'Failed to send email to {user.email}: {e}')
        return False


def render_booking_email(user, successful, failed, waiting):
    """Render the booking summary email HTML."""

    template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: #1d3557; color: white; padding: 20px; border-radius: 8px 8px 0 0; text-align: center; }
        .header h1 { margin: 0; font-size: 24px; }
        .content { background: #f8f9fa; padding: 20px; border-radius: 0 0 8px 8px; }
        .section { margin-bottom: 20px; }
        .section-title { font-size: 16px; font-weight: 600; margin-bottom: 10px; display: flex; align-items: center; gap: 8px; }
        .booking-card { background: white; padding: 12px; border-radius: 6px; margin-bottom: 8px; border-left: 4px solid #ccc; }
        .booking-card.success { border-left-color: #2a9d8f; }
        .booking-card.failed { border-left-color: #e63946; }
        .booking-card.waiting { border-left-color: #e9c46a; }
        .booking-info { font-weight: 500; }
        .booking-message { font-size: 14px; color: #666; margin-top: 4px; }
        .footer { text-align: center; margin-top: 20px; font-size: 12px; color: #666; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 500; }
        .badge-success { background: #d4edda; color: #155724; }
        .badge-failed { background: #f8d7da; color: #721c24; }
        .badge-waiting { background: #fff3cd; color: #856404; }
    </style>
</head>
<body>
    <div class="header">
        <h1>WodSniper Booking Summary</h1>
    </div>
    <div class="content">
        <p>Hi {{ user_name }},</p>
        <p>Here's your weekly booking summary:</p>

        {% if successful %}
        <div class="section">
            <div class="section-title">
                <span class="badge badge-success">{{ successful|length }} Booked</span>
            </div>
            {% for r in successful %}
            <div class="booking-card success">
                <div class="booking-info">{{ r.day_name }} {{ r.time }} - {{ r.class_type }}</div>
                <div class="booking-message">{{ r.message }}</div>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        {% if failed %}
        <div class="section">
            <div class="section-title">
                <span class="badge badge-failed">{{ failed|length }} Failed</span>
            </div>
            {% for r in failed %}
            <div class="booking-card failed">
                <div class="booking-info">{{ r.day_name }} {{ r.time }} - {{ r.class_type }}</div>
                <div class="booking-message">{{ r.message }}</div>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        {% if waiting %}
        <div class="section">
            <div class="section-title">
                <span class="badge badge-waiting">{{ waiting|length }} Waiting</span>
            </div>
            {% for r in waiting %}
            <div class="booking-card waiting">
                <div class="booking-info">{{ r.day_name }} {{ r.time }} - {{ r.class_type }}</div>
                <div class="booking-message">{{ r.message }}</div>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        {% if failed %}
        <p><strong>Need help?</strong> Check your WodSniper dashboard to review failed bookings and try again manually.</p>
        {% endif %}
    </div>
    <div class="footer">
        <p>Sent by WodSniper on {{ now }}</p>
        <p>You can disable email notifications in your account settings.</p>
    </div>
</body>
</html>
    """

    return render_template_string(
        template,
        user_name=user.email.split('@')[0].title(),
        successful=successful,
        failed=failed,
        waiting=waiting,
        now=datetime.now().strftime('%d/%m/%Y %H:%M')
    )


def send_test_email(user):
    """Send a test email to verify configuration."""
    if not current_app.config.get('MAIL_USERNAME'):
        return False, 'Email not configured (MAIL_USERNAME not set)'

    try:
        msg = Message(
            subject='WodSniper: Test Email',
            recipients=[user.email],
            html=f"""
            <h2>Test Email from WodSniper</h2>
            <p>If you received this email, your notifications are working correctly!</p>
            <p>Sent at: {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
            """
        )
        mail.send(msg)
        return True, 'Test email sent successfully'

    except Exception as e:
        logger.error(f'Failed to send test email: {e}')
        return False, str(e)
