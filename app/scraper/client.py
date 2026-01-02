"""WodBuster client using cloudscraper to bypass Cloudflare."""

import os
import re
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin, urlparse

import requests
import cloudscraper
from bs4 import BeautifulSoup

from app.scraper.exceptions import (
    LoginError,
    SessionExpiredError,
    ClassNotFoundError,
    ClassFullError,
    BookingError,
    RateLimitError
)

logger = logging.getLogger(__name__)


class FlareSolverrClient:
    """Client for FlareSolverr proxy to bypass Cloudflare."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.timeout = 60000  # 60 seconds max for Cloudflare solving

    def solve(self, url: str, method: str = 'GET', post_data: str = None,
              cookies: List[Dict] = None) -> Dict[str, Any]:
        """
        Send request through FlareSolverr.

        Returns dict with 'cookies', 'response' (HTML), 'status', 'url'
        """
        payload = {
            'cmd': f'request.{method.lower()}',
            'url': url,
            'maxTimeout': self.timeout,
        }

        if post_data:
            payload['postData'] = post_data

        if cookies:
            payload['cookies'] = cookies

        try:
            logger.info(f'FlareSolverr: {method} {url}')
            resp = requests.post(
                self.base_url,
                json=payload,
                timeout=65  # slightly more than maxTimeout
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get('status') == 'ok':
                solution = data.get('solution', {})
                return {
                    'success': True,
                    'cookies': solution.get('cookies', []),
                    'response': solution.get('response', ''),
                    'status': solution.get('status', 0),
                    'url': solution.get('url', url),
                }
            else:
                error_msg = data.get('message', 'Unknown FlareSolverr error')
                logger.error(f'FlareSolverr error: {error_msg}')
                return {'success': False, 'error': error_msg}

        except Exception as e:
            logger.error(f'FlareSolverr request failed: {e}')
            return {'success': False, 'error': str(e)}


class WodBusterClient:
    """Client for interacting with WodBuster."""

    BASE_URL = 'https://wodbuster.com'
    USER_AGENT = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/119.0.0.0 Safari/537.36'
    )

    def __init__(self, box_url: str, timeout: int = 15, flaresolverr_url: str = None):
        """
        Initialize WodBuster client.

        Args:
            box_url: The box's WodBuster URL (e.g., https://teknix.wodbuster.com)
            timeout: Request timeout in seconds
            flaresolverr_url: FlareSolverr URL for Cloudflare bypass (optional)
        """
        self.box_url = box_url.rstrip('/')
        self.box_name = self._extract_box_name(box_url)
        self.timeout = timeout
        self.session = self._create_session()
        self._logged_in = False

        # FlareSolverr for Cloudflare bypass
        self.flaresolverr_url = flaresolverr_url or os.environ.get('FLARESOLVERR_URL')
        self.flaresolverr = FlareSolverrClient(self.flaresolverr_url) if self.flaresolverr_url else None

    def _extract_box_name(self, url: str) -> str:
        """Extract box name from URL."""
        parsed = urlparse(url)
        hostname = parsed.netloc
        if hostname.endswith('.wodbuster.com'):
            return hostname.replace('.wodbuster.com', '')
        return hostname

    def _create_session(self) -> cloudscraper.CloudScraper:
        """Create a cloudscraper session to bypass Cloudflare."""
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        scraper.headers.update({
            'User-Agent': self.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        # Don't set Accept-Encoding - let requests handle it automatically
        return scraper

    def _get_login_url(self) -> str:
        """Get the centralized login URL with box callback."""
        return f'{self.BASE_URL}/account/login.aspx?cb={self.box_name}'

    def _extract_form_tokens(self, html: str) -> Dict[str, str]:
        """Extract ASP.NET form tokens from HTML."""
        tokens = {}

        # Try lxml first, fallback to html.parser
        try:
            soup = BeautifulSoup(html, 'lxml')
        except Exception:
            soup = BeautifulSoup(html, 'html.parser')

        # Get all hidden inputs
        for inp in soup.find_all('input', attrs={'type': 'hidden'}):
            name = inp.get('name')
            if name:
                tokens[name] = inp.get('value', '')

        # If no tokens found, try regex as fallback
        if not tokens:
            logger.debug('BeautifulSoup found no tokens, trying regex fallback')
            import re
            # Extract common ASP.NET tokens
            patterns = [
                (r'name="(__VIEWSTATE[C]?)" value="([^"]*)"', '__VIEWSTATEC'),
                (r'name="(__VIEWSTATE)" value="([^"]*)"', '__VIEWSTATE'),
                (r'name="(__EVENTVALIDATION)" value="([^"]*)"', '__EVENTVALIDATION'),
                (r'name="(CSRFToken)" value="([^"]*)"', 'CSRFToken'),
                (r'name="(__EVENTTARGET)" value="([^"]*)"', '__EVENTTARGET'),
                (r'name="(__EVENTARGUMENT)" value="([^"]*)"', '__EVENTARGUMENT'),
            ]
            for pattern, _ in patterns:
                matches = re.findall(pattern, html)
                for match in matches:
                    tokens[match[0]] = match[1]

            # Also extract ctl00 fields
            ctl_pattern = r'name="(ctl00\$[^"]+)" value="([^"]*)"'
            for match in re.findall(ctl_pattern, html):
                tokens[match[0]] = match[1]

        logger.debug(f'Extracted {len(tokens)} tokens')
        return tokens

    def _apply_flaresolverr_cookies(self, cookies: List[Dict]) -> None:
        """Apply cookies from FlareSolverr to the session."""
        for cookie in cookies:
            self.session.cookies.set(
                cookie.get('name'),
                cookie.get('value'),
                domain=cookie.get('domain', ''),
                path=cookie.get('path', '/')
            )

    def _login_with_flaresolverr(self, email: str, password: str) -> bool:
        """Login using FlareSolverr for Cloudflare bypass."""
        logger.info(f'Using FlareSolverr for login to {self.box_name}')
        login_url = self._get_login_url()

        # Phase 1: Get login page through FlareSolverr
        result = self.flaresolverr.solve(login_url)
        if not result.get('success'):
            raise LoginError(f'FlareSolverr failed: {result.get("error")}')

        html = result.get('response', '')
        self._apply_flaresolverr_cookies(result.get('cookies', []))

        tokens = self._extract_form_tokens(html)
        if not tokens.get('__VIEWSTATEC') and not tokens.get('__VIEWSTATE'):
            raise LoginError('Could not extract form tokens from login page')

        # Phase 2: Submit credentials through FlareSolverr
        login_data = self._build_login_data(tokens, email, password)

        # Convert dict to URL-encoded string for FlareSolverr POST
        from urllib.parse import urlencode
        post_data = urlencode(login_data)

        # Pass existing cookies to FlareSolverr
        existing_cookies = [
            {'name': c.name, 'value': c.value, 'domain': c.domain, 'path': c.path}
            for c in self.session.cookies
        ]

        result = self.flaresolverr.solve(
            login_url,
            method='POST',
            post_data=post_data,
            cookies=existing_cookies
        )

        if not result.get('success'):
            raise LoginError(f'FlareSolverr login failed: {result.get("error")}')

        html = result.get('response', '')
        self._apply_flaresolverr_cookies(result.get('cookies', []))

        # Check for login errors
        if self._has_login_error(html):
            raise LoginError('Invalid email or password')

        # Phase 3: Handle device confirmation if needed
        if self._needs_device_confirmation(html):
            logger.info('Device confirmation required (FlareSolverr)')
            tokens = self._extract_form_tokens(html)
            confirm_data = self._build_device_confirm_data(tokens, html)
            post_data = urlencode(confirm_data)

            existing_cookies = [
                {'name': c.name, 'value': c.value, 'domain': c.domain, 'path': c.path}
                for c in self.session.cookies
            ]

            result = self.flaresolverr.solve(
                result.get('url', login_url),
                method='POST',
                post_data=post_data,
                cookies=existing_cookies
            )
            if result.get('success'):
                self._apply_flaresolverr_cookies(result.get('cookies', []))

        # Verify login
        if self._verify_login():
            self._logged_in = True
            logger.info(f'Login successful via FlareSolverr')
            return True

        raise LoginError('FlareSolverr login failed - could not establish session')

    def _build_device_confirm_data(self, tokens: Dict[str, str], html: str) -> Dict[str, str]:
        """Build device confirmation form data."""
        soup = BeautifulSoup(html, 'lxml')

        confirm_data = {
            '__VIEWSTATE': tokens.get('__VIEWSTATE', ''),
            '__VIEWSTATEC': tokens.get('__VIEWSTATEC', ''),
            '__EVENTVALIDATION': tokens.get('__EVENTVALIDATION', ''),
            '__EVENTTARGET': '',
            '__EVENTARGUMENT': '',
            'CSRFToken': tokens.get('CSRFToken', ''),
        }

        # Look for the secure device button
        secure_btn = soup.find('input', {'id': re.compile(r'CtlSeguro', re.I)})
        if secure_btn:
            btn_name = secure_btn.get('name', '')
            if btn_name:
                confirm_data[btn_name] = secure_btn.get('value', 'Aceptar')

        # Add ctl00 tokens
        for key, value in tokens.items():
            if key.startswith('ctl00$') and key not in confirm_data:
                confirm_data[key] = value

        return confirm_data

    def login(self, email: str, password: str) -> bool:
        """
        Login to WodBuster using the 3-phase authentication.

        Phase 1: Get login page and extract tokens
        Phase 2: Submit credentials
        Phase 3: Handle device confirmation if needed

        Uses FlareSolverr if available for Cloudflare bypass.
        """
        logger.info(f'Attempting login for {email} to box {self.box_name}')

        # Try FlareSolverr first if available
        if self.flaresolverr:
            try:
                return self._login_with_flaresolverr(email, password)
            except Exception as e:
                logger.warning(f'FlareSolverr login failed, falling back to cloudscraper: {e}')

        # Fallback to regular cloudscraper
        try:
            # Phase 1: Get login page
            login_url = self._get_login_url()
            logger.debug(f'Getting login page: {login_url}')

            resp = self.session.get(login_url, timeout=self.timeout)
            resp.raise_for_status()

            # Debug: log response info
            logger.debug(f'Response status: {resp.status_code}')
            logger.debug(f'Response length: {len(resp.text)} chars')
            logger.debug(f'Response first 500 chars: {resp.text[:500]}')

            tokens = self._extract_form_tokens(resp.text)
            logger.debug(f'Tokens extracted: {list(tokens.keys())}')

            if not tokens.get('__VIEWSTATEC') and not tokens.get('__VIEWSTATE'):
                raise LoginError('Could not extract form tokens from login page')

            # Phase 2: Submit credentials
            login_data = self._build_login_data(tokens, email, password)

            logger.debug('Submitting login form...')
            resp = self.session.post(
                login_url,
                data=login_data,
                timeout=self.timeout,
                allow_redirects=True
            )
            resp.raise_for_status()

            logger.debug(f'Post-login URL: {resp.url}')
            logger.debug(f'Cookies: {list(self.session.cookies.keys())}')

            # Check for login errors in response
            if self._has_login_error(resp.text):
                raise LoginError('Invalid email or password')

            # Phase 3: Handle device confirmation ("Recordar este dispositivo")
            if self._needs_device_confirmation(resp.text):
                logger.info('Device confirmation required')
                resp = self._confirm_device(resp)

            # After successful login, we should be redirected to the box
            # or have valid session cookies
            if self._verify_login():
                self._logged_in = True
                logger.info(f'Login successful for {email}')
                return True

            # If verification fails, try accessing the box directly
            # Sometimes the redirect doesn't happen automatically
            logger.debug('Direct verification failed, trying box access...')
            resp = self.session.get(
                f'{self.box_url}/athlete/default.aspx',
                timeout=self.timeout,
                allow_redirects=True
            )

            if self._verify_login():
                self._logged_in = True
                logger.info(f'Login successful for {email} (after box access)')
                return True

            raise LoginError('Login failed - could not establish session')

        except LoginError:
            raise
        except Exception as e:
            logger.error(f'Login error: {e}')
            raise LoginError(f'Login failed: {str(e)}')

    def _build_login_data(self, tokens: Dict[str, str], email: str, password: str) -> Dict[str, str]:
        """Build the login form data."""
        data = {
            # ASP.NET tokens
            '__VIEWSTATE': tokens.get('__VIEWSTATE', ''),
            '__VIEWSTATEC': tokens.get('__VIEWSTATEC', ''),
            '__EVENTVALIDATION': tokens.get('__EVENTVALIDATION', ''),
            '__EVENTTARGET': '',
            '__EVENTARGUMENT': '',
            'CSRFToken': tokens.get('CSRFToken', ''),
            # Credentials - ASP.NET naming convention
            'ctl00$ctl00$body$body$CtlLogin$IoEmail': email,
            'ctl00$ctl00$body$body$CtlLogin$IoPassword': password,
            'ctl00$ctl00$body$body$CtlLogin$CtlAceptar': 'Aceptar',
        }

        # Add any additional ctl00 hidden fields
        for key, value in tokens.items():
            if key.startswith('ctl00$') and key not in data:
                data[key] = value

        return data

    def _has_login_error(self, html: str) -> bool:
        """Check if the response contains login error messages."""
        error_indicators = [
            'usuario o contraseña incorrectos',
            'email o contraseña incorrectos',
            'credenciales incorrectas',
            'invalid credentials',
            'login failed',
        ]
        html_lower = html.lower()
        return any(indicator in html_lower for indicator in error_indicators)

    def _needs_device_confirmation(self, html: str) -> bool:
        """Check if device confirmation is needed."""
        indicators = ['recordar este dispositivo', 'dispositivo de confianza', 'ctlseguro']
        html_lower = html.lower()
        return any(indicator in html_lower for indicator in indicators)

    def _confirm_device(self, response) -> Any:
        """Handle the device confirmation dialog."""
        tokens = self._extract_form_tokens(response.text)

        # Find the confirmation button/action
        soup = BeautifulSoup(response.text, 'lxml')

        confirm_data = {
            '__VIEWSTATE': tokens.get('__VIEWSTATE', ''),
            '__VIEWSTATEC': tokens.get('__VIEWSTATEC', ''),
            '__EVENTVALIDATION': tokens.get('__EVENTVALIDATION', ''),
            '__EVENTTARGET': '',
            '__EVENTARGUMENT': '',
            'CSRFToken': tokens.get('CSRFToken', ''),
        }

        # Look for the secure device button
        secure_btn = soup.find('input', {'id': re.compile(r'CtlSeguro', re.I)})
        if secure_btn:
            btn_name = secure_btn.get('name', '')
            if btn_name:
                confirm_data[btn_name] = secure_btn.get('value', 'Aceptar')

        # Add ctl00 tokens
        for key, value in tokens.items():
            if key.startswith('ctl00$') and key not in confirm_data:
                confirm_data[key] = value

        return self.session.post(
            response.url,
            data=confirm_data,
            timeout=self.timeout,
            allow_redirects=True
        )

    def _verify_login(self) -> bool:
        """Verify that we're logged in by checking session cookies and protected page."""
        # Check for authentication cookies
        cookie_names = [c.name for c in self.session.cookies]
        has_auth_cookie = any(
            'wbauth' in name.lower() or '.wbauth' in name.lower()
            for name in cookie_names
        )

        if not cookie_names:
            logger.debug('No cookies found')
            return False

        logger.debug(f'Cookies present: {cookie_names}')

        # If we have the WBAuth cookie, we're authenticated
        if has_auth_cookie:
            logger.debug('Found .WBAuth cookie - session is valid')
            return True

        # Try to access a protected page with redirects to verify
        try:
            protected_url = f'{self.box_url}/athlete/schedule.aspx'
            logger.debug(f'Verifying login by accessing: {protected_url}')
            resp = self.session.get(
                protected_url,
                timeout=self.timeout,
                allow_redirects=True  # Follow redirects
            )

            logger.debug(f'Final URL after redirects: {resp.url}')
            logger.debug(f'Protected page status: {resp.status_code}')

            # If we end up at a schedule/athlete page, we're in
            if resp.status_code == 200:
                final_url = resp.url.lower()
                # Check if we ended up at the actual page, not a login page
                if 'login' not in final_url or 'athlete' in final_url:
                    logger.debug('Verification successful')
                    return True
                # Check if the page contains athlete content
                if 'schedule' in resp.text.lower() or 'calendario' in resp.text.lower():
                    logger.debug('Verification successful: found schedule content')
                    return True

            logger.debug(f'Verification failed: ended up at {resp.url}')
            return False
        except Exception as e:
            logger.error(f'Verify login error: {e}')
            return False

    def restore_session(self, cookies: dict) -> bool:
        """Restore a previous session using stored cookies."""
        if cookies:
            self.session.cookies.update(cookies)
            if self._verify_login():
                self._logged_in = True
                logger.info('Session restored successfully')
                return True
        return False

    def get_cookies(self) -> dict:
        """Get current session cookies for storage."""
        return dict(self.session.cookies)

    def get_classes(self, date: datetime = None) -> List[Dict[str, Any]]:
        """Get available classes for a date."""
        if not self._logged_in:
            raise SessionExpiredError('Not logged in')

        if date is None:
            date = datetime.now()

        # The ticks parameter IS the date - Unix timestamp for midnight UTC
        # Convert local date to midnight UTC and get epoch seconds
        from datetime import timezone
        target_date = date.date() if hasattr(date, 'date') else date
        midnight_utc = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        epoch = int(midnight_utc.timestamp())

        try:
            # The API uses ticks as the date parameter (epoch seconds for midnight UTC)
            url = f'{self.box_url}/athlete/handlers/LoadClass.ashx'
            params = {
                'ticks': epoch
            }

            # Debug: verify the epoch conversion
            from datetime import datetime as dt
            epoch_check = dt.utcfromtimestamp(epoch)
            logger.info(f'Fetching classes for date: {target_date}')
            logger.info(f'Epoch timestamp: {epoch} (converts back to: {epoch_check})')
            logger.info(f'Full URL: {url}?ticks={epoch}')
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()

            # Debug: log raw response
            logger.debug(f'LoadClass response status: {response.status_code}')
            logger.debug(f'LoadClass response text (first 500): {response.text[:500]}')

            try:
                data = response.json()
            except Exception as json_err:
                logger.error(f'Failed to parse JSON: {json_err}')
                logger.error(f'Raw response: {response.text[:1000]}')
                return []

            logger.debug(f'LoadClass parsed data keys: {list(data.keys()) if isinstance(data, dict) else type(data)}')

            # WodBuster API can return data in different formats:
            # - Old format: {EsCorrecto: bool, Datos: [...]}
            # - New format: {Data: [{Hora: ..., Valores: [...]}], ...}

            # Check for error in old format
            if 'EsCorrecto' in data and not data.get('EsCorrecto', False):
                error_msg = data.get('ErrorMsg', 'Unknown error')
                logger.error(f'Error fetching classes: {error_msg}')
                return []

            # Check for maintenance mode
            if data.get('Mantenimiento', False):
                logger.error('WodBuster is in maintenance mode')
                return []

            classes = []

            # Try new format first (Data with nested Valores)
            if 'Data' in data:
                for time_slot in data.get('Data', []):
                    for valor_item in time_slot.get('Valores', []):
                        valor = valor_item.get('Valor', {})
                        if valor:
                            # Check if user is booked by looking at TipoEstado
                            atletas = valor.get('AtletasEntrenando', [])
                            status = valor_item.get('TipoEstado', '')

                            # TipoEstado values:
                            # - Inscribible: can book
                            # - Borrable: booked, can cancel
                            # - Cambiable: booked, can change
                            # - Avisable: waitlist or full
                            # - Finalizada: class ended
                            is_booked = status in ['Borrable', 'Cambiable']
                            can_cancel = status == 'Borrable'

                            # Get user's booking ID from atletas list
                            booking_id = None
                            if is_booked and atletas:
                                # The user's entry should be in the atletas list
                                booking_id = atletas[0].get('Id')

                            class_info = {
                                'id': valor.get('Id'),
                                'name': valor.get('Nombre', ''),
                                'time': valor.get('HoraComienzo', ''),
                                'date': data.get('Title', ''),
                                'spots_available': valor.get('Plazas', 0) - len(atletas),
                                'spots_total': valor.get('Plazas', 0),
                                'is_booked': is_booked,
                                'booking_id': booking_id,
                                'can_book': status == 'Inscribible',
                                'can_cancel': can_cancel,
                                'trainer': '',
                                'status': status,
                                'atletas_count': len(atletas),
                            }
                            classes.append(class_info)
                logger.info(f'Found {len(classes)} classes using new format')
                return classes

            # Fallback to old format (Datos)
            for item in data.get('Datos', []):
                class_info = {
                    'id': item.get('Id'),
                    'name': item.get('Nombre', ''),
                    'time': item.get('Hora', ''),
                    'date': item.get('Fecha', ''),
                    'spots_available': item.get('PlazasLibres', 0),
                    'spots_total': item.get('PlazasTotales', 0),
                    'is_booked': item.get('Apuntado', False),
                    'can_book': item.get('PuedeApuntar', False),
                    'trainer': item.get('Entrenador', ''),
                }
                classes.append(class_info)

            return classes

        except Exception as e:
            logger.error(f'Error fetching classes: {e}')
            raise

    def book_class(self, class_id: int) -> bool:
        """Book a class."""
        if not self._logged_in:
            raise SessionExpiredError('Not logged in')

        ticks = int(time.time() * 1000)

        try:
            url = f'{self.box_url}/athlete/handlers/Calendario_Inscribir.ashx'
            params = {
                'id': class_id,
                'ticks': ticks
            }

            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()

            # Debug: log raw response
            logger.debug(f'Booking response status: {response.status_code}')
            logger.debug(f'Booking response text: {response.text[:500]}')

            data = response.json()
            logger.debug(f'Booking response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}')

            # Check for success - API returns result in 'Res' object
            res = data.get('Res', {})
            if res.get('EsCorrecto', False) or data.get('EsCorrecto', False):
                logger.info(f'Successfully booked class {class_id}')
                return True

            error_msg = res.get('ErrorMsg', data.get('ErrorMsg', 'Unknown error'))

            if 'completa' in error_msg.lower() or 'llena' in error_msg.lower():
                raise ClassFullError(f'Class {class_id} is full')

            if 'penaliz' in error_msg.lower():
                wait_match = re.search(r'(\d+)\s*(minuto|segundo)', error_msg.lower())
                if wait_match:
                    wait_time = int(wait_match.group(1))
                    if 'minuto' in wait_match.group(2):
                        wait_time *= 60
                    raise RateLimitError(error_msg, retry_after=wait_time)
                raise RateLimitError(error_msg)

            raise BookingError(f'Booking failed: {error_msg}')

        except (ClassFullError, BookingError, RateLimitError):
            raise
        except Exception as e:
            logger.error(f'Error booking class: {e}')
            raise BookingError(f'Booking error: {str(e)}')

    def cancel_booking(self, class_id: int, booking_id: int) -> bool:
        """Cancel a booking."""
        if not self._logged_in:
            raise SessionExpiredError('Not logged in')

        ticks = int(time.time() * 1000)

        try:
            url = f'{self.box_url}/athlete/handlers/Calendario_Borrar.ashx'
            params = {
                'id': class_id,
                'ticks': ticks,
                'idu': booking_id
            }

            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()

            # Debug: log raw response
            logger.debug(f'Cancel response status: {response.status_code}')
            logger.debug(f'Cancel response text: {response.text[:500]}')

            data = response.json()
            logger.debug(f'Cancel response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}')

            # Check for success - API returns result in 'Res' object (same as book_class)
            res = data.get('Res', {})
            if res.get('EsCorrecto', False) or data.get('EsCorrecto', False):
                logger.info(f'Successfully cancelled booking {booking_id} for class {class_id}')
                return True

            error_msg = res.get('ErrorMsg', data.get('ErrorMsg', 'Unknown error'))
            logger.error(f'Cancel failed: {error_msg}')
            raise BookingError(f'Cancel failed: {error_msg}')

        except BookingError:
            raise
        except Exception as e:
            logger.error(f'Error cancelling booking: {e}')
            raise BookingError(f'Cancel error: {str(e)}')

    def get_my_reservations(self, days_ahead: int = 7) -> List[Dict[str, Any]]:
        """Get user's booked classes for the next N days."""
        reservations = []
        today = datetime.now()

        for i in range(days_ahead):
            target_date = today + timedelta(days=i)
            try:
                classes = self.get_classes(target_date)
                for cls in classes:
                    if cls.get('is_booked') and cls.get('can_cancel'):
                        cls['date_obj'] = target_date.strftime('%Y-%m-%d')
                        cls['day_name'] = target_date.strftime('%A')
                        reservations.append(cls)
            except Exception as e:
                logger.error(f'Error fetching classes for {target_date}: {e}')
                continue

        return reservations

    def get_account_info(self) -> Dict[str, Any]:
        """Get user account info including available classes/credits."""
        if not self._logged_in:
            raise SessionExpiredError('Not logged in')

        try:
            # Fetch any athlete page - the user info panel is in the sidebar
            # Note: WodBuster may return 404 status but still serve content
            url = f'{self.box_url}/athlete/schedule.aspx'
            response = self.session.get(url, timeout=self.timeout)

            # Don't use raise_for_status() - WodBuster returns 404 but still has content
            if not response.text or len(response.text) < 100:
                raise Exception('Empty response from WodBuster')

            soup = BeautifulSoup(response.text, 'lxml')
            logger.debug(f'Account page length: {len(response.text)} chars')

            available_classes = None
            subscription = None
            user_name = None

            # Look for the user info div (body_CtlMenu_CtlInfoUser)
            info_div = soup.find('div', id=re.compile(r'CtlInfoUser', re.I))
            if info_div:
                info_text = info_div.get_text()
                logger.debug(f'Found user info div: {info_text[:100]}')

                # Extract "Bono:X" pattern
                bono_match = re.search(r'Bono:\s*(\d+)', info_text)
                if bono_match:
                    available_classes = int(bono_match.group(1))
                    logger.debug(f'Found bono credits: {available_classes}')

                # Extract tariff info
                tarifa_match = re.search(r'Tarifa:\s*([^\n]+)', info_text)
                if tarifa_match:
                    subscription = tarifa_match.group(1).strip()

            # Fallback: search entire page for "Bono:" pattern
            if available_classes is None:
                page_text = soup.get_text()
                bono_match = re.search(r'Bono:\s*(\d+)', page_text)
                if bono_match:
                    available_classes = int(bono_match.group(1))
                    logger.debug(f'Found bono credits (fallback): {available_classes}')

            # Find user name from the info panel
            name_div = soup.find('div', id=re.compile(r'CtlInfoUser', re.I))
            if name_div:
                # Usually the first line is the user name
                first_text = name_div.get_text().split('\n')[0].strip()
                if first_text and '@' not in first_text:
                    user_name = first_text

            return {
                'available_classes': available_classes,
                'subscription': subscription,
                'user_name': user_name,
                'has_credits': available_classes is None or available_classes > 0
            }

        except Exception as e:
            logger.error(f'Error getting account info: {e}')
            return {
                'available_classes': None,
                'subscription': None,
                'user_name': None,
                'has_credits': True,  # Assume true if we can't check
                'error': str(e)
            }

    def get_booking_open_time(self, days_ahead: int = 7) -> Optional[Dict[str, Any]]:
        """
        Get when reservations open for future classes.

        Checks future dates to find one with SegundosHastaPublicacion,
        which tells us when that day's classes become bookable.

        Returns:
            Dict with 'opens_at' (datetime), 'seconds_until', 'day_of_week', 'hour', 'minute'
            or None if unable to determine.
        """
        if not self._logged_in:
            raise SessionExpiredError('Not logged in')

        today = datetime.now()

        # Check each day ahead to find one with SegundosHastaPublicacion
        for i in range(1, days_ahead + 1):
            target_date = today + timedelta(days=i)

            try:
                # Get raw response to access SegundosHastaPublicacion
                from datetime import timezone
                target_date_only = target_date.date()
                midnight_utc = datetime.combine(target_date_only, datetime.min.time()).replace(tzinfo=timezone.utc)
                epoch = int(midnight_utc.timestamp())

                url = f'{self.box_url}/athlete/handlers/LoadClass.ashx'
                params = {'ticks': epoch}

                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()

                data = response.json()

                seconds_until = data.get('SegundosHastaPublicacion')

                if seconds_until and seconds_until > 0:
                    # Calculate when reservations open
                    opens_at = datetime.now() + timedelta(seconds=seconds_until)

                    logger.info(f'Found booking open time: {opens_at} (in {seconds_until:.0f} seconds)')

                    return {
                        'opens_at': opens_at,
                        'seconds_until': seconds_until,
                        'day_of_week': opens_at.weekday(),
                        'hour': opens_at.hour,
                        'minute': opens_at.minute,
                        'target_date': target_date_only.isoformat(),
                    }

            except Exception as e:
                logger.warning(f'Error checking booking open time for {target_date}: {e}')
                continue

        return None

    def find_class(
        self,
        date: datetime,
        time_str: str,
        class_type: str
    ) -> Optional[Dict[str, Any]]:
        """Find a specific class by date, time, and type."""
        classes = self.get_classes(date)

        target_time = time_str.replace(':', '')[:4]
        logger.info(f'Searching for class: type="{class_type}", time={target_time}')
        logger.info(f'Available classes ({len(classes)}):')
        for cls in classes:
            logger.info(f'  - {cls.get("time", "?")} {cls.get("name", "?")} (can_book={cls.get("can_book")}, status={cls.get("status")})')

        for cls in classes:
            cls_time = cls.get('time', '').replace(':', '')[:4]

            if cls_time != target_time:
                continue

            cls_name = cls.get('name', '').lower()
            if class_type.lower() in cls_name:
                logger.info(f'Found matching class: {cls}')
                return cls

        logger.warning(f'No class found matching type="{class_type}" at time={target_time}')
        return None
