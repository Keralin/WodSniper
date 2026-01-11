#!/usr/bin/env python3
"""WodSniper - Entry point."""

import os
import sys
import logging
from app import create_app
from app.scheduler import shutdown_scheduler


class StdoutFilter(logging.Filter):
    """Filter to only allow logs below ERROR level."""
    def filter(self, record):
        return record.levelno < logging.ERROR


def configure_logging():
    """Configure logging with stdout for info and stderr for errors.

    This setup is container-friendly:
    - stdout: DEBUG, INFO, WARNING (normal operation)
    - stderr: ERROR, CRITICAL (errors and failures)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    formatter = logging.Formatter(log_format)

    # Handler for stdout (DEBUG, INFO, WARNING)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.addFilter(StdoutFilter())
    stdout_handler.setFormatter(formatter)

    # Handler for stderr (ERROR, CRITICAL)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.ERROR)
    stderr_handler.setFormatter(formatter)

    root_logger.addHandler(stdout_handler)
    root_logger.addHandler(stderr_handler)

    # Reduce noise from external libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('cloudscraper').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.INFO)
    logging.getLogger('apscheduler').setLevel(logging.WARNING)


configure_logging()

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
