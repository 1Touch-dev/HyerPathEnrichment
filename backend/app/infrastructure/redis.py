import time
from collections.abc import AsyncIterator

from redis.asyncio import Redis

from app.core.config import get_settings

_redis: Redis | None = None

# Cloudflare-style weighted sliding-window rate limit, run atomically via Lua so
# the estimate-then-increment sequence can't race under concurrent callers.
#
# KEYS[1] = current window counter key
# KEYS[2] = previous window counter key
# ARGV[1] = limit
# ARGV[2] = weight applied to the previous window's count (0..1)
# ARGV[3] = window_seconds, used to size the TTL so the key survives to serve
#           as "previous" for the next window
_RATE_LIMIT_SCRIPT = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
local previous = tonumber(redis.call('GET', KEYS[2]) or '0')
local limit = tonumber(ARGV[1])
local weight = tonumber(ARGV[2])
local window_seconds = tonumber(ARGV[3])

local estimated = current + previous * weight
if estimated >= limit then
    return 0
end

redis.call('INCR', KEYS[1])
redis.call('EXPIRE', KEYS[1], window_seconds * 2)
return 1
"""


def sliding_window_params(now: float, window_seconds: int) -> tuple[int, float]:
    """Compute the current window id and the weight for the previous window's count.

    ``weight`` decays linearly from ~1 (just entered the current window, so the
    previous window is almost fully counted) to ~0 (about to leave the current
    window, so the previous window barely matters anymore).
    """
    window_id = int(now // window_seconds)
    elapsed = now - (window_id * window_seconds)
    weight = 1 - (elapsed / window_seconds)
    return window_id, weight


def get_redis_client() -> Redis:
    """Return the shared async Redis client, creating it on first use.

    Connections are established lazily by redis-py on the first command,
    so importing or calling this does not require a live Redis server.
    """
    global _redis
    if _redis is None:
        settings = get_settings()
        # Increased timeouts to handle Redis under disk I/O pressure
        # socket_keepalive enables TCP keepalive to detect dead connections
        _redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=10,
            socket_keepalive=True,
            socket_keepalive_options={},  # Use system defaults
            health_check_interval=30,  # Check connection health every 30s
        )
    return _redis


async def get_redis() -> AsyncIterator[Redis]:
    """FastAPI dependency yielding the shared Redis client."""
    yield get_redis_client()


async def check_rate_limit(client: Redis, scope: str, limit: int, window_seconds: int = 60) -> bool:
    """Weighted sliding-window counter. Returns True if the request is within the limit.

    Fixes the boundary-burst flaw of a plain fixed-window counter (where a
    client could send ``limit`` requests in the last instant of one window and
    another ``limit`` in the first instant of the next, doubling the
    effective rate at the boundary) by blending in a weighted estimate of the
    previous window's count. The whole check-then-increment happens as one
    atomic Lua script server-side, so concurrent callers can't race between
    the read and the write. Callers decide fail-open vs fail-closed on
    RedisError; rate limiting fails open (protection, not correctness).
    """
    window_id, weight = sliding_window_params(time.time(), window_seconds)
    current_key = f"ratelimit:{scope}:{window_id}"
    previous_key = f"ratelimit:{scope}:{window_id - 1}"
    allowed = await client.eval(
        _RATE_LIMIT_SCRIPT,
        2,
        current_key,
        previous_key,
        str(limit),
        str(weight),
        str(window_seconds),
    )
    return bool(int(allowed))


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
