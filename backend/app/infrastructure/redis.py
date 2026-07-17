from collections.abc import AsyncIterator

from redis.asyncio import Redis

from app.core.config import get_settings

_redis: Redis | None = None


def get_redis_client() -> Redis:
    """Return the shared async Redis client, creating it on first use.

    Connections are established lazily by redis-py on the first command,
    so importing or calling this does not require a live Redis server.
    """
    global _redis
    if _redis is None:
        settings = get_settings()
        # Short timeouts so an unreachable Redis degrades fast instead of
        # stalling request paths that fall back to SQL.
        _redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _redis


async def get_redis() -> AsyncIterator[Redis]:
    """FastAPI dependency yielding the shared Redis client."""
    yield get_redis_client()


async def check_rate_limit(client: Redis, scope: str, limit: int, window_seconds: int = 60) -> bool:
    """Fixed-window counter. Returns True if the request is within the limit.

    Increments the per-scope counter and sets the window TTL on the first hit,
    so the key auto-resets when the window ends. Callers decide fail-open vs
    fail-closed on RedisError; rate limiting fails open (protection, not
    correctness).
    """
    key = f"ratelimit:{scope}"
    count = await client.incr(key)
    if count == 1:
        await client.expire(key, window_seconds)
    return count <= limit


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
