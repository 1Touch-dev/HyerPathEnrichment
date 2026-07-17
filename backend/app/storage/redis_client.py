"""Compatibility shim — prefer app.infrastructure.redis."""
from app.infrastructure.redis import (  # noqa: F401
    check_rate_limit,
    close_redis,
    get_redis,
    get_redis_client,
)

__all__ = ["check_rate_limit", "close_redis", "get_redis", "get_redis_client"]
