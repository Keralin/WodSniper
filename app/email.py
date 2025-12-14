"""Email notification service for WodSniper using Resend."""

import logging
from typing import List, Dict, Any
from datetime import datetime

from flask import current_app, render_template_string
import resend

logger = logging.getLogger(__name__)


def _get_email_config():
    """Get email configuration and check if Resend is configured."""
    api_key = current_app.config.get('RESEND_API_KEY')
    from_email = current_app.config.get('RESEND_FROM_EMAIL', 'WodSniper <onboarding@resend.dev>')
    return api_key, from_email


def _send_with_resend(to_email: str, subject: str, html_body: str) -> bool:
    """Send email using Resend API."""
    api_key, from_email = _get_email_config()

    if not api_key:
        logger.error('RESEND_API_KEY not configured')
        return False

    try:
        resend.api_key = api_key

        logger.info(f'Sending email via Resend to {to_email}')
        logger.debug(f'From: {from_email}, Subject: {subject}')

        params = {
            "from": from_email,
            "to": [to_email],
            "subject": subject,
            "html": html_body
        }

        response = resend.Emails.send(params)
        logger.info(f'Email sent successfully via Resend. ID: {response.get("id", "unknown")}')
        return True

    except resend.exceptions.ResendError as e:
        logger.error(f'Resend API error: {e}')
        return False
    except Exception as e:
        logger.exception(f'Unexpected error sending email via Resend: {e}')
        return False


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

    api_key, _ = _get_email_config()
    if not api_key:
        logger.warning('Email not configured (RESEND_API_KEY not set)')
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
    elif success_count > 0:
        subject = f'WodSniper: {success_count}/{total} classes booked'
    else:
        subject = f'WodSniper: Booking issues - action needed'

    # Render email body
    html_body = render_booking_email(user, successful, failed, waiting)

    # Send via Resend
    success = _send_with_resend(user.email, subject, html_body)

    if success:
        logger.info(f'Booking summary email sent successfully to {user.email}')
    else:
        logger.error(f'Failed to send booking summary email to {user.email}')

    return success


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
    """Send a test email to verify Resend configuration."""
    logger.info(f'Test email requested for {user.email}')

    api_key, from_email = _get_email_config()

    if not api_key:
        logger.warning('RESEND_API_KEY not configured')
        return False, 'Email not configured (RESEND_API_KEY not set)'

    logger.info(f'Using Resend with from_email: {from_email}')

    html_body = f"""
    <h2>Test Email from WodSniper</h2>
    <p>If you received this email, your notifications are working correctly!</p>
    <p>Sent at: {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
    <p><small>Sent via Resend</small></p>
    """

    success = _send_with_resend(user.email, 'WodSniper: Test Email', html_body)

    if success:
        return True, 'Test email sent successfully via Resend'
    else:
        return False, 'Failed to send email via Resend. Check logs for details.'
