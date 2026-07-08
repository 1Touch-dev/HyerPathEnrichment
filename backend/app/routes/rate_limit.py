import hashlib
import logging

from fastapi import Depends, Header, HTTPException, status
from redis.exceptions import RedisError

from app.config import Settings, get_settings
from app.storage.redis_client import check_rate_limit, get_redis_client

logger = logging.getLogger(__name__)


def _client_id(authorization: str | None) -> str:
    """Stable per-caller id without logging the raw token."""
    token = (authorization or "anonymous").removeprefix("Bearer ").strip()
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


async def _enforce(scope: str, limit: int) -> None:
    try:
        allowed = await check_rate_limit(get_redis_client(), scope, limit)
    except RedisError:
        # Fail open: rate limiting is protection, not correctness. A Redis
        # outage must not block legitimate enrichment traffic.
        logger.warning("redis unavailable during rate limit check; allowing request")
        return
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate limit exceeded",
        )


async def enforce_sync_rate_limit(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    await _enforce(f"sync:{_client_id(authorization)}", settings.max_sync_requests_per_minute)


async def enforce_async_rate_limit(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    await _enforce(f"async:{_client_id(authorization)}", settings.max_async_requests_per_minute)
