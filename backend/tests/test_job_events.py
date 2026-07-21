"""Unit tests for Redis pub/sub backing the `/enrich/{job_id}/events` SSE route."""

from __future__ import annotations

import asyncio

import pytest

from app.domain.enums import JobStatus
from app.modules.enrichment import job_events


class _FakePubSub:
    def __init__(self, redis: "_FakeEventsRedis") -> None:
        self._redis = redis
        self._channel: str | None = None

    async def subscribe(self, channel: str) -> None:
        self._channel = channel
        self._redis.channels.setdefault(channel, asyncio.Queue())

    async def get_message(
        self, *, timeout: float, ignore_subscribe_messages: bool = True
    ) -> dict[str, str] | None:
        assert self._channel is not None
        queue = self._redis.channels[self._channel]
        try:
            data = await asyncio.wait_for(queue.get(), timeout=timeout)
        except TimeoutError:
            return None
        return {"type": "message", "data": data}

    async def unsubscribe(self, channel: str) -> None:
        return None

    async def aclose(self) -> None:
        return None


class _FakeEventsRedis:
    def __init__(self) -> None:
        self.channels: dict[str, asyncio.Queue] = {}

    async def publish(self, channel: str, message: str) -> int:
        queue = self.channels.setdefault(channel, asyncio.Queue())
        await queue.put(message)
        return 1

    def pubsub(self) -> _FakePubSub:
        return _FakePubSub(self)

    async def aclose(self) -> None:
        return None


@pytest.fixture
def fake_events_redis(monkeypatch: pytest.MonkeyPatch) -> _FakeEventsRedis:
    fake = _FakeEventsRedis()
    monkeypatch.setattr(job_events, "_get_events_redis_client", lambda: fake)
    return fake


async def test_publish_then_stream_yields_terminal_event(
    fake_events_redis: _FakeEventsRedis,
) -> None:
    async def publish_later() -> None:
        await asyncio.sleep(0.05)
        await job_events.publish_job_status("job_abc", JobStatus.completed)

    asyncio.create_task(publish_later())

    events = [
        event
        async for event in job_events.stream_job_status_events(
            "job_abc", JobStatus.queued, heartbeat_seconds=0.5, max_seconds=2
        )
    ]

    assert len(events) == 1
    assert events[0].startswith("data: ")
    assert '"job_id": "job_abc"' in events[0]
    assert '"status": "completed"' in events[0]


async def test_already_terminal_status_yields_immediately_without_subscribing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _ExplodingRedis:
        def pubsub(self) -> None:
            raise AssertionError("should not subscribe when already terminal")

    monkeypatch.setattr(job_events, "_get_events_redis_client", lambda: _ExplodingRedis())

    events = [
        event async for event in job_events.stream_job_status_events("job_xyz", JobStatus.failed)
    ]

    assert len(events) == 1
    assert '"status": "failed"' in events[0]


async def test_heartbeat_emitted_while_waiting_then_stream_times_out(
    fake_events_redis: _FakeEventsRedis,
) -> None:
    events = [
        event
        async for event in job_events.stream_job_status_events(
            "job_slow", JobStatus.running, heartbeat_seconds=0.05, max_seconds=0.15
        )
    ]

    assert events
    assert all(event == ": ping\n\n" for event in events)
