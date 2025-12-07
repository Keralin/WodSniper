#!/usr/bin/env python3
"""WodSniper - Entry point."""

import os
import sys
import logging
from app import create_app
from app.scheduler import shutdown_scheduler

# Configure logging to stdout (Railway treats stderr as errors)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
# Reduce noise from external libraries only
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('cloudscraper').setLevel(logging.WARNING)
logging.getLogger('werkzeug').setLevel(logging.INFO)
logging.getLogger('apscheduler').setLevel(logging.DEBUG)

app = create_app()

# Note: scheduler is initialized in create_app() via _init_scheduler_once()
# This prevents duplicate initialization in both dev (run.py) and prod (gunicorn)


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
