# WodSniper 🎯

Automated class booking system for CrossFit boxes using WodBuster platform.

## Features

- **Automatic Booking**: Schedule your weekly classes once, WodSniper books them automatically when the booking window opens (Sundays at 13:00)
- **Smart Scheduling**: Dynamic class selection based on real-time availability from WodBuster
- **Email Notifications**: Receive summaries after automatic bookings with success/failure details
- **Credit Monitoring**: Track your available class credits with low-balance warnings
- **Manual Booking**: Book classes instantly with one click
- **Reservation Management**: View and cancel your upcoming reservations

## Tech Stack

- **Backend**: Flask (Python 3.11+)
- **Database**: SQLAlchemy (SQLite/PostgreSQL)
- **Scheduler**: APScheduler for cron-like background tasks
- **Web Scraping**: Cloudscraper (Cloudflare bypass)
- **Auth**: Flask-Login with secure session management
- **Email**: Flask-Mail with SMTP support

## Architecture

```
WodSniper/
├── app/
│   ├── auth/           # Authentication blueprint
│   ├── booking/        # Booking management blueprint
│   ├── scraper/        # WodBuster API client
│   ├── scheduler/      # Background job scheduling
│   ├── templates/      # Jinja2 templates
│   └── static/         # CSS, JS assets
├── run.py              # Application entry point
└── requirements.txt
```

## Key Technical Challenges Solved

1. **Cloudflare Bypass**: WodBuster uses Cloudflare protection. Solved using cloudscraper with browser emulation.

2. **ASP.NET Form Handling**: WodBuster uses complex ASP.NET forms with ViewState, EventValidation, and CSRF tokens. Implemented robust token extraction and session management.

3. **Precise Timing**: Bookings open at exactly 13:00. Implemented precise waiting with busy-wait for sub-second accuracy.

4. **Session Persistence**: WodBuster sessions expire. Implemented cookie serialization and automatic session restoration.

## Screenshots

*Dashboard with scheduled bookings and credit monitoring*

## Local Development

```bash
# Clone and setup
git clone https://github.com/yourusername/wodsniper.git
cd wodsniper
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your settings

# Run
python run.py
```

## Deployment

Ready for deployment on Railway, Render, or Fly.io. See deployment docs for details.

## Disclaimer

This project is for educational and personal use only. Users are responsible for ensuring their use complies with WodBuster's Terms of Service. The authors assume no liability for any consequences arising from the use of this software.

## License

MIT License with Commons Clause - See [LICENSE](LICENSE) for details.
