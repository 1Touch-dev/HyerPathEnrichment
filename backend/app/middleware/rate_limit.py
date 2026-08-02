"""Rate limiting middleware using slowapi."""

from slowapi import Limiter
from slowapi.util import get_remote_address


def get_limiter() -> Limiter:
    """
    Create and configure rate limiter.

    Returns:
        Configured Limiter instance
    """
    return Limiter(
        key_func=get_remote_address,
        default_limits=["100/minute"],  # Global default
        storage_uri="memory://",  # In-memory for now; use Redis in production
    )


# Rate limit configs for specific endpoints
AUTH_RATE_LIMIT = "5/minute"  # Login, register
VERIFY_RATE_LIMIT = "10/minute"  # Email verification
API_RATE_LIMIT = "60/minute"  # General API endpoints
