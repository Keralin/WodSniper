# Contributing to WodSniper

## Development Setup

### Prerequisites

- Python 3.11+
- pip
- virtualenv (recommended)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/WodSniper.git
cd WodSniper

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env
# Edit .env with your settings
```

### Running the Application

```bash
# Activate virtual environment
source venv/bin/activate

# Run the development server
python run.py

# Access at http://localhost:5000
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_models.py

# Run with coverage report
pytest --cov=app --cov-report=term-missing

# Run only fast unit tests
pytest -m "not slow"
```

### Test Structure

```
tests/
├── conftest.py           # Shared fixtures
├── test_models.py        # Model unit tests
├── test_scraper.py       # WodBuster client tests
├── test_scheduler.py     # Scheduler logic tests
├── test_auth_routes.py   # Authentication route tests
└── test_booking_routes.py # Booking route tests
```

### Writing Tests

- Use pytest fixtures from `conftest.py`
- Mock external services (WodBuster API)
- Each test should be independent
- Use descriptive test names

Example:

```python
def test_user_password_hashing(app):
    """Should hash password and verify correctly."""
    from app.models import User

    with app.app_context():
        user = User(email='test@example.com')
        user.set_password('password123')

        assert user.check_password('password123') is True
        assert user.check_password('wrong') is False
```

## Code Style

### Python Style Guide

- Follow PEP 8
- Use meaningful variable names
- Keep functions focused and small
- Add docstrings to modules, classes, and functions

### Commit Messages

Use conventional commits format:

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Examples:
```
feat(booking): add retry logic for failed reservations
fix(scraper): handle Cloudflare challenge correctly
docs(readme): update installation instructions
test(models): add User password hashing tests
```

## Pull Request Process

1. Create a feature branch from `main`
   ```bash
   git checkout -b feat/your-feature-name
   ```

2. Make your changes and commit
   ```bash
   git add .
   git commit -m "feat(scope): description"
   ```

3. Run tests to ensure nothing is broken
   ```bash
   pytest
   ```

4. Push your branch
   ```bash
   git push origin feat/your-feature-name
   ```

5. Open a Pull Request with:
   - Clear description of changes
   - Link to any related issues
   - Screenshots if UI changes

## Project Architecture

### Directory Structure

```
WodSniper/
├── app/
│   ├── __init__.py      # Application factory
│   ├── config.py        # Configuration classes
│   ├── models.py        # SQLAlchemy models
│   ├── auth/            # Authentication blueprint
│   ├── booking/         # Booking blueprint
│   ├── scraper/         # WodBuster client
│   ├── scheduler/       # Background jobs
│   ├── templates/       # Jinja2 templates
│   └── static/          # CSS, JS, images
├── tests/               # Test suite
├── run.py               # Application entry point
└── requirements.txt     # Python dependencies
```

### Key Components

| Component | Description |
|-----------|-------------|
| `app/models.py` | Database models (User, Booking, BookingLog, Box) |
| `app/scraper/client.py` | WodBuster API client with Cloudflare bypass |
| `app/scheduler/__init__.py` | APScheduler jobs for automated booking |
| `app/auth/routes.py` | Login, register, password reset routes |
| `app/booking/routes.py` | Dashboard, booking management routes |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key | dev-secret-key |
| `DATABASE_URL` | Database connection URL | sqlite:///wodsniper.db |
| `FLASK_ENV` | Environment (development/production) | development |
| `RESEND_API_KEY` | Resend.com API key for emails | - |
| `RESEND_FROM_EMAIL` | Sender email address | - |

## Debugging

### Common Issues

**Import errors**: Make sure you're in the virtual environment
```bash
source venv/bin/activate
```

**Database issues**: Reset the database
```bash
rm -f instance/wodsniper.db
python run.py  # Will recreate tables
```

**WodBuster connection issues**: Check if Cloudflare is blocking
- The scraper uses `cloudscraper` to bypass basic challenges
- If persistent, session cookies may be expired

### Logging

Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

View scheduler logs:
```python
from app.scheduler import logger
logger.setLevel(logging.DEBUG)
```

## Questions?

Open an issue on GitHub or reach out to the maintainers.
