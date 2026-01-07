"""
Custom exceptions for WodBuster scraping.

This module defines a hierarchy of exceptions for handling various
error conditions when interacting with the WodBuster platform.

Exception Hierarchy:
    WodBusterError (base)
    ├── LoginError - Authentication failures
    ├── SessionExpiredError - Expired session cookies
    ├── ClassNotFoundError - Class not in schedule
    ├── NoClassesAvailableError - No classes for day (holiday/closed)
    ├── ClassFullError - No spots available
    ├── BookingError - Generic booking failures
    └── RateLimitError - Rate limiting (with retry_after)
"""

from typing import Optional


class WodBusterError(Exception):
    """
    Base exception for all WodBuster-related errors.

    All specific WodBuster exceptions inherit from this class,
    allowing for broad exception handling when needed.

    Example:
        try:
            client.book_class(123)
        except WodBusterError as e:
            logger.error(f"WodBuster operation failed: {e}")
    """
    pass


class LoginError(WodBusterError):
    """
    Failed to authenticate with WodBuster.

    Raised when:
    - Invalid email or password
    - Cannot extract form tokens from login page
    - Device confirmation fails
    - User has access to multiple boxes (unsupported)

    Example:
        try:
            client.login(email, password)
        except LoginError as e:
            flash("Invalid credentials", "error")
    """
    pass


class SessionExpiredError(WodBusterError):
    """
    Session cookies have expired and need to be refreshed.

    This typically occurs when:
    - Stored cookies are too old
    - WodBuster has invalidated the session
    - User logged in from another device

    The application should attempt to re-login when this occurs.

    Example:
        try:
            classes = client.get_classes(date)
        except SessionExpiredError:
            client.login(email, password)
            classes = client.get_classes(date)
    """
    pass


class ClassNotFoundError(WodBusterError):
    """
    The requested class was not found in the schedule.

    Raised when find_class() cannot locate a class matching
    the specified time and class type.

    This differs from NoClassesAvailableError in that classes
    exist for the day, but none match the search criteria.

    Attributes:
        The exception message contains the search criteria.
    """
    pass


class NoClassesAvailableError(WodBusterError):
    """
    No classes are available for the requested day.

    This typically occurs on:
    - Holidays (Christmas, New Year, etc.)
    - Box closure days
    - Days outside the published schedule

    The scheduler should not retry when this exception is raised,
    as the situation won't change.

    Example:
        try:
            cls = client.find_class(date, time, class_type)
        except NoClassesAvailableError:
            booking.status = 'failed'
            booking.last_error = 'Holiday or closed day'
    """
    pass


class ClassFullError(WodBusterError):
    """
    The class has no available spots.

    Raised when attempting to book a class that is already full.
    The user may be added to a waitlist depending on box settings.

    The scheduler should not retry immediately when this occurs,
    as spots are unlikely to become available.

    Example:
        try:
            client.book_class(class_id)
        except ClassFullError:
            booking.status = 'waiting'
    """
    pass


class BookingError(WodBusterError):
    """
    Generic error during the booking process.

    Raised for various booking failures that don't fit
    specific categories like ClassFullError.

    Common causes:
    - Network issues
    - Invalid class ID
    - User not authorized for class type
    - Booking restrictions (e.g., too early/late)
    """
    pass


class RateLimitError(WodBusterError):
    """
    Rate limited by WodBuster or Cloudflare.

    Raised when too many requests are made in a short period.
    Includes a retry_after attribute indicating when to retry.

    Attributes:
        retry_after: Seconds to wait before retrying (default: 60)

    Example:
        try:
            client.book_class(class_id)
        except RateLimitError as e:
            time.sleep(e.retry_after)
            client.book_class(class_id)
    """

    def __init__(self, message: str, retry_after: Optional[int] = 60):
        """
        Initialize RateLimitError with retry information.

        Args:
            message: Error description
            retry_after: Seconds to wait before retrying
        """
        super().__init__(message)
        self.retry_after = retry_after
