"""Redis-cached aggregate helper. See Decision 3 — applied first to the existing
cost endpoints, then reused for job-match analytics (§3's correction)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TypeVar

from pydantic import BaseModel

from app.core.config import get_settings
from app.infrastructure.redis import get_redis_client

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


async def cached_aggregate(
    key: str,
    model_cls: type[T],
    compute_fn: Callable[[], Awaitable[T]],
    *,
    refresh: bool = False,
    ttl_seconds: int | None = None,
) -> tuple[T, bool]:
    """Returns (result, cache_hit). On any Redis error, fails open by calling
    compute_fn() directly — caching is a performance optimization, never a
    correctness dependency, matching this repo's existing rate-limit fail-open
    convention in app/infrastructure/redis.py::check_rate_limit."""
    settings = get_settings()
    ttl = ttl_seconds if ttl_seconds is not None else settings.admin_aggregate_cache_ttl_seconds
    cache_key = f"admin:cache:{key}"

    if not refresh:
        try:
            client = get_redis_client()
            cached = await client.get(cache_key)
            if cached:
                return model_cls.model_validate_json(cached), True
        except Exception:
            logger.warning("Admin aggregate cache read failed for key=%s", key, exc_info=True)

    result = await compute_fn()

    try:
        client = get_redis_client()
        await client.set(cache_key, result.model_dump_json(), ex=ttl)
    except Exception:
        logger.warning("Admin aggregate cache write failed for key=%s", key, exc_info=True)

    return result, False


def utcnow() -> datetime:
    return datetime.now(UTC)
