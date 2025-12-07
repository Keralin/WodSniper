# WodSniper 🎯

Automated class booking system for CrossFit boxes using WodBuster platform.

## Features

- **Automatic Booking**: Schedule your weekly classes once, WodSniper books them automatically when the booking window opens (Sundays at 13:00)
- **Smart Scheduling**: Dynamic class selection based on real-time availability from WodBuster
- **Email Notifications**: Receive summaries after automatic bookings with success/failure details
- **Credit Monitoring**: Track your available class credits with low-balance warnings
- **Manual Booking**: Book classes instantly with one click
- **Reservation Management**: View and cancel your upcoming reservations
- **Multi-language**: Spanish and English with automatic browser detection

## Tech Stack

- **Backend**: Flask (Python 3.11+)
- **Database**: SQLAlchemy (SQLite/PostgreSQL)
- **Scheduler**: APScheduler for cron-like background tasks
- **Web Scraping**: Cloudscraper + FlareSolverr (Cloudflare bypass)
- **Auth**: Flask-Login with secure session management
- **Email**: Flask-Mail with SMTP support
- **i18n**: Flask-Babel

## Architecture

```
WodSniper/
├── app/
│   ├── auth/           # Authentication blueprint
│   ├── booking/        # Booking management blueprint
│   ├── scraper/        # WodBuster API client
│   ├── scheduler/      # Background job scheduling
│   ├── templates/      # Jinja2 templates
│   ├── translations/   # i18n (es, en)
│   └── static/         # CSS, JS, images
├── Dockerfile
├── docker-compose.yml
├── run.py              # Application entry point
└── requirements.txt
```

## Key Technical Challenges Solved

1. **Cloudflare Bypass**: WodBuster uses Cloudflare protection. Solved using cloudscraper with FlareSolverr as fallback.

2. **ASP.NET Form Handling**: WodBuster uses complex ASP.NET forms with ViewState, EventValidation, and CSRF tokens. Implemented robust token extraction and session management.

3. **Precise Timing**: Bookings open at exactly 13:00. Implemented precise waiting with busy-wait for sub-second accuracy.

4. **Session Persistence**: WodBuster sessions expire. Implemented cookie serialization, automatic session restoration, and encrypted credential storage for auto re-login.

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
4. Set environment variables:
   - `SECRET_KEY` - Secure random string
   - `FLARESOLVERR_URL` - If using FlareSolverr
   - `MAIL_*` - For email notifications
5. Set health check path: `/health`

## Environment Variables

See `.env.example` for all available options.

## Disclaimer

This project is for educational and personal use only. Users are responsible for ensuring their use complies with WodBuster's Terms of Service. The authors assume no liability for any consequences arising from the use of this software.

## License

MIT License with Commons Clause - See [LICENSE](LICENSE) for details.
