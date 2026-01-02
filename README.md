# WodSniper

Automatic class booking system for CrossFit boxes using the WodBuster platform.

## Features

- **Automatic Booking**: Set up your weekly classes once, WodSniper books them automatically when the reservation window opens
- **Auto-detect Schedule**: Automatically detects when your box opens reservations (using WodBuster's `SegundosHastaPublicacion`)
- **Per-Box Configuration**: Each box has its own opening schedule, shared between users of the same box
- **Email Notifications**: Receive summaries after automatic bookings
- **Credit Monitoring**: Track your available classes with low balance warnings
- **Manual Booking**: Book classes instantly with one click
- **Reservation Management**: View and cancel your upcoming reservations
- **Special Day Detection**: Detects reduced schedules (holidays) and shows the typical schedule as reference
- **Multi-language**: Spanish and English with automatic browser detection
- **Modern UI**: Dark theme with glassmorphism effects

## Tech Stack

- **Backend**: Flask (Python 3.11+)
- **Database**: SQLAlchemy (SQLite/PostgreSQL)
- **Scheduler**: APScheduler for background tasks
- **Web Scraping**: Cloudscraper + FlareSolverr (Cloudflare bypass)
- **Auth**: Flask-Login with secure session management
- **Email**: Resend API
- **i18n**: Flask-Babel

## Architecture

```
WodSniper/
├── app/
│   ├── auth/           # Authentication blueprint
│   ├── booking/        # Booking management blueprint
│   ├── scraper/        # WodBuster API client
│   ├── scheduler/      # Background task scheduling
│   ├── templates/      # Jinja2 templates
│   ├── translations/   # i18n (es, en)
│   ├── static/         # CSS, JS, images
│   └── models.py       # Models: User, Box, Booking, BookingLog
├── Dockerfile
├── docker-compose.yml
├── run.py              # Entry point
└── requirements.txt
```

## Data Models

- **Box**: Box configuration (URL, reservation opening schedule)
- **User**: WodSniper user, linked to a Box
- **Booking**: Scheduled booking (day, time, class type)
- **BookingLog**: Booking attempt history

## How the Scheduler Works

1. Every minute, the scheduler checks which boxes have their reservation window opening in 5 minutes
2. 10 minutes before: refreshes user sessions for the box
3. 5 minutes before: waits until the exact time
4. At the exact time: processes all active bookings for the box
5. Sends email notifications with results

## Local Development

```bash
# Clone and setup
git clone https://github.com/Keralin/WodSniper.git
cd WodSniper
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your settings

# Run
python run.py
```

## Docker

```bash
# Start app + PostgreSQL
docker compose up -d

# With FlareSolverr (Cloudflare bypass)
docker compose --profile full up -d

# View logs
docker compose logs -f wodsniper

# Stop
docker compose down
```

Services:
- `wodsniper` - Flask app (port 5000)
- `postgres` - PostgreSQL 16
- `flaresolverr` - Cloudflare bypass (optional, use `--profile full`)

## Deployment (Railway)

1. Create project from GitHub repo
2. Add PostgreSQL database
3. (Optional) Add FlareSolverr service
4. Configure environment variables:
   - `SECRET_KEY` - Secure random string
   - `FLARESOLVERR_URL` - If using FlareSolverr
   - `RESEND_API_KEY` - For email notifications
   - `CREDENTIAL_KEY` - Key for encrypting WodBuster credentials
5. Configure health check: `/health`

## Environment Variables

See `.env.example` for all available options.

## Disclaimer

This project is for educational and personal use only. Users are responsible for ensuring their use complies with WodBuster's Terms of Service. The authors assume no responsibility for consequences arising from the use of this software.

## License

MIT License with Commons Clause - See [LICENSE](LICENSE) for details.
