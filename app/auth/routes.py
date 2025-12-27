from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, current_app, abort
from flask_login import login_user, logout_user, login_required, current_user

from app.auth import auth_bp
from app.auth.forms import LoginForm, RegisterForm, WodBusterConnectForm
from app.models import db, User
from app.scraper import WodBusterClient, LoginError


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page."""
    if current_user.is_authenticated:
        return redirect(url_for('booking.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()

        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            user.last_login = datetime.utcnow()
            db.session.commit()

            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('booking.dashboard'))

        flash('Invalid email or password', 'error')

    return render_template('auth/login.html', form=form)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page."""
    if current_user.is_authenticated:
        return redirect(url_for('booking.dashboard'))

    form = RegisterForm()
    if form.validate_on_submit():
        user = User(email=form.email.data.lower())
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        flash('Account created successfully. Now connect your WodBuster account.', 'success')
        login_user(user)
        return redirect(url_for('auth.connect_wodbuster'))

    return render_template('auth/register.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    """Logout user."""
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/connect', methods=['GET', 'POST'])
@login_required
def connect_wodbuster():
    """Connect WodBuster account."""
    form = WodBusterConnectForm()

    # Pre-fill with existing data
    if request.method == 'GET' and current_user.box_url:
        form.box_url.data = current_user.box_url
        form.wodbuster_email.data = current_user.wodbuster_email

    if form.validate_on_submit():
        box_url = form.box_url.data.strip()
        email = form.wodbuster_email.data
        password = form.wodbuster_password.data

        try:
            # Test connection to WodBuster
            client = WodBusterClient(box_url)
            client.login(email, password)

            # Save credentials and session
            current_user.box_url = box_url
            current_user.wodbuster_email = email
            current_user.set_wodbuster_password(password)  # Save encrypted password for auto re-login
            current_user.set_wodbuster_cookies(client.get_cookies())

            db.session.commit()

            flash('Successfully connected to WodBuster', 'success')
            return redirect(url_for('booking.dashboard'))

        except LoginError as e:
            flash(f'Connection error: {str(e)}', 'error')
        except Exception as e:
            flash(f'Unexpected error: {str(e)}', 'error')

    return render_template('auth/connect.html', form=form)


@auth_bp.route('/test-connection')
@login_required
def test_connection():
    """Test WodBuster connection."""
    if not current_user.box_url:
        flash('Please connect your WodBuster account first', 'warning')
        return redirect(url_for('auth.connect_wodbuster'))

    try:
        client = WodBusterClient(current_user.box_url)
        cookies = current_user.get_wodbuster_cookies()

        if cookies and client.restore_session(cookies):
            flash('Connection verified successfully', 'success')
        else:
            flash('Session expired. Please reconnect your account.', 'warning')
            return redirect(url_for('auth.connect_wodbuster'))

    except Exception as e:
        flash(f'Connection error: {str(e)}', 'error')

    return redirect(url_for('booking.dashboard'))


@auth_bp.route('/explore-endpoints')
@login_required
def explore_endpoints():
    """Explore available WodBuster endpoints to find user stats. Only works in debug mode."""
    if not current_app.debug:
        abort(404)

    import json
    import time

    if not current_user.box_url:
        return {'error': 'Not connected to WodBuster'}, 400

    try:
        client = WodBusterClient(current_user.box_url)
        cookies = current_user.get_wodbuster_cookies()

        if not cookies or not client.restore_session(cookies):
            return {'error': 'Session expired'}, 401

        results = {}
        ticks = int(time.time() * 1000)

        # Try various handlers
        handlers = [
            '/athlete/handlers/LoadUserData.ashx',
            '/athlete/handlers/GetUserInfo.ashx',
            '/athlete/handlers/Dashboard.ashx',
            '/athlete/handlers/GetProfile.ashx',
            '/athlete/handlers/GetMembership.ashx',
            '/athlete/handlers/Perfil.ashx',
            '/athlete/handlers/GetBonos.ashx',
            '/athlete/handlers/LoadBonos.ashx',
            '/athlete/handlers/GetReservas.ashx',
            '/handlers/GetUserData.ashx',
        ]

        for handler in handlers:
            try:
                url = f'{client.box_url}{handler}'
                resp = client.session.get(url, params={'ticks': ticks}, timeout=10)

                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        results[handler] = {
                            'status': resp.status_code,
                            'data': data
                        }
                    except:
                        results[handler] = {
                            'status': resp.status_code,
                            'content_type': resp.headers.get('Content-Type', 'unknown'),
                            'preview': resp.text[:500] if resp.text else 'empty'
                        }
                else:
                    results[handler] = {'status': resp.status_code}
            except Exception as e:
                results[handler] = {'error': str(e)}

        return {'endpoints': results}

    except Exception as e:
        return {'error': str(e)}, 500
