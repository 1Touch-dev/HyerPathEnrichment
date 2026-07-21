"""Redis pub/sub for job status push — feeds the `/enrich/{job_id}/events` SSE route.

Separate from `infrastructure/redis.py`'s shared client: that client uses a short
`socket_timeout` tuned for fast-failing request paths, which would tear down a
long-lived pub/sub subscription. SSE gets its own connection here instead.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.domain.enums import JobStatus

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = frozenset({JobStatus.completed, JobStatus.failed, JobStatus.suppressed})

HEARTBEAT_SECONDS = 15.0
MAX_STREAM_SECONDS = 300.0

_events_redis: Redis | None = None


def _channel(job_id: str) -> str:
    return f"enrich:job:{job_id}"


def _format_event(job_id: str, status: JobStatus) -> str:
    payload = json.dumps({"job_id": job_id, "status": status.value})
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


async def publish_job_status(job_id: str, status: JobStatus) -> None:
    """Publish a terminal job status. Fail-soft: never raises on Redis errors."""
    payload = json.dumps({"job_id": job_id, "status": status.value})
    try:
        client = _get_events_redis_client()
        await client.publish(_channel(job_id), payload)
    except RedisError:
        logger.warning("job_events publish failed for job_id=%s", job_id, exc_info=True)


async def stream_job_status_events(
    job_id: str,
    initial_status: JobStatus,
    *,
    heartbeat_seconds: float = HEARTBEAT_SECONDS,
    max_seconds: float = MAX_STREAM_SECONDS,
) -> AsyncIterator[str]:
    """Yield SSE `data:` lines for a job's status until terminal, timeout, or disconnect.

    Checks ``initial_status`` first so an already-terminal job (or one that
    finished between the caller's DB read and the subscribe call below) gets
    one event and closes immediately instead of hanging on a missed publish.
    """
    if initial_status in TERMINAL_STATUSES:
        yield _format_event(job_id, initial_status)
        return

    client = _get_events_redis_client()
    pubsub = client.pubsub()
    channel = _channel(job_id)
    elapsed = 0.0
    try:
        await pubsub.subscribe(channel)
        while elapsed < max_seconds:
            try:
                message = await pubsub.get_message(
                    timeout=heartbeat_seconds, ignore_subscribe_messages=True
                )
            except RedisError:
                logger.warning("job_events subscribe failed for job_id=%s", job_id, exc_info=True)
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
                status = JobStatus(data["status"])
            except (ValueError, KeyError, TypeError):
                logger.warning("job_events received malformed payload for job_id=%s", job_id)
                continue

            yield _format_event(job_id, status)
            if status in TERMINAL_STATUSES:
                return
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()  # type: ignore[no-untyped-call]
        except RedisError:
            logger.warning("job_events unsubscribe failed for job_id=%s", job_id, exc_info=True)


async def close_events_redis() -> None:
    global _events_redis
    if _events_redis is not None:
        await _events_redis.aclose()
        _events_redis = None
