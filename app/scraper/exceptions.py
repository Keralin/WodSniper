"""Custom exceptions for WodBuster scraping."""


class WodBusterError(Exception):
    """Base exception for WodBuster errors."""
    pass


class LoginError(WodBusterError):
    """Failed to login to WodBuster."""
    pass


class SessionExpiredError(WodBusterError):
    """Session cookies have expired."""
    pass


class ClassNotFoundError(WodBusterError):
    """Requested class not found in schedule."""
    pass


class ClassFullError(WodBusterError):
    """Class is full, no spots available."""
    pass


class BookingError(WodBusterError):
    """Generic booking error."""
    pass


class RateLimitError(WodBusterError):
    """Rate limited by WodBuster or Cloudflare."""

    def __init__(self, message, retry_after=60):
        super().__init__(message)
        self.retry_after = retry_after
