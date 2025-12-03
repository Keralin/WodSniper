#!/usr/bin/env python3
"""WodSniper - Entry point."""

import os
import logging
from app import create_app
from app.scheduler import init_scheduler, shutdown_scheduler

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
# Reduce noise from other libraries
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('cloudscraper').setLevel(logging.WARNING)

app = create_app()

# Initialize scheduler
with app.app_context():
    init_scheduler(app)


@app.teardown_appcontext
def cleanup(exception=None):
    """Cleanup on app shutdown."""
    pass


if __name__ == '__main__':
    try:
        port = int(os.environ.get('PORT', 5000))
        debug = os.environ.get('FLASK_ENV') == 'development'

        app.run(
            host='0.0.0.0',
            port=port,
            debug=debug
        )
    finally:
        shutdown_scheduler()
