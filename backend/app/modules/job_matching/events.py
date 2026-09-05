"""Redis pub/sub for unread-match-count push — feeds the `/api/job-matching/events` SSE route.

Separate from `infrastructure/redis.py`'s shared client: that client uses a short
`socket_timeout` tuned for fast-failing request paths, which would tear down a
long-lived pub/sub subscription. SSE gets its own connection here instead.

Also separate from `enrichment/job_events.py`'s own dedicated client — each
module owns its own connection rather than sharing a global (per that module's
docstring on separation of concerns).
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

HEARTBEAT_SECONDS = 15.0
MAX_STREAM_SECONDS = 300.0

_events_redis: Redis | None = None


def _channel(user_id: str) -> str:
    return f"job_matching:user:{user_id}"


def _format_event(unread_count: int) -> str:
    payload = json.dumps({"unread_count": unread_count})
    return f"data: {payload}\n\n"


def _get_events_redis_client() -> Redis:
    """Dedicated Redis client for pub/sub — no short read timeout."""
    global _events_redis
    if _events_redis is None:
        settings = get_settings()
        _events_redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
        )
    return _events_redis


async def publish_unread_count(user_id: str, unread_count: int) -> None:
    """Publish a fresh unread-match count. Fail-soft: never raises on Redis errors."""
    payload = json.dumps({"unread_count": unread_count})
    try:
        client = _get_events_redis_client()
        await client.publish(_channel(user_id), payload)
    except RedisError:
        logger.warning("job_matching events publish failed for user_id=%s", user_id, exc_info=True)


async def stream_unread_match_events(
    user_id: str,
    initial_count: int,
    *,
    heartbeat_seconds: float = HEARTBEAT_SECONDS,
    max_seconds: float = MAX_STREAM_SECONDS,
) -> AsyncIterator[str]:
    """Yield SSE `data:` lines with the unread-match count until timeout or disconnect.

    Yields ``initial_count`` first — this is the "re-check DB on connect" behavior;
    the caller passes in a freshly-queried count so a client that (re)connects after
    missing a pub/sub message self-heals to the true count immediately. After that,
    subscribes to the pub/sub channel and yields subsequent published counts. Unlike
    `job_events.stream_job_status_events`, there is no terminal-status concept here:
    the stream simply runs until ``max_seconds`` elapses or the client disconnects.
    """
    yield _format_event(initial_count)

    client = _get_events_redis_client()
    pubsub = client.pubsub()
    channel = _channel(user_id)
    elapsed = 0.0
    try:
        await pubsub.subscribe(channel)
        while elapsed < max_seconds:
            try:
                message = await pubsub.get_message(
                    timeout=heartbeat_seconds, ignore_subscribe_messages=True
                )
            except RedisError:
                logger.warning(
                    "job_matching events subscribe failed for user_id=%s", user_id, exc_info=True
                )
                return
            elapsed += heartbeat_seconds
            if message is None:
                yield ": ping\n\n"
                continue

            raw = message.get("data")
            if not raw:
                continue
            try:
                data = json.loads(raw)
                unread_count = int(data["unread_count"])
            except (ValueError, KeyError, TypeError):
                logger.warning(
                    "job_matching events received malformed payload for user_id=%s", user_id
                )
                continue

            yield _format_event(unread_count)
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()  # type: ignore[no-untyped-call]
        except RedisError:
            logger.warning(
                "job_matching events unsubscribe failed for user_id=%s", user_id, exc_info=True
            )


async def close_job_matching_events_redis() -> None:
    global _events_redis
    if _events_redis is not None:
        await _events_redis.aclose()
        _events_redis = None
