"""Shared pytest fixtures for backend API tests."""

from __future__ import annotations

import pytest

from app.routes import rate_limit
from app.storage import photo_cache
from app.workers import runner


class FakeRedis:
    def __init__(self) -> None:
        self._sets: dict[str, set[str]] = {}
        self._counters: dict[str, int] = {}
        self._kv: dict[str, str] = {}

    async def sadd(self, key: str, *values: str) -> int:
        members = self._sets.setdefault(key, set())
        added = len([value for value in values if value not in members])
        members.update(values)
        return added

    async def sismember(self, key: str, value: str) -> bool:
        return value in self._sets.get(key, set())

    async def incr(self, key: str) -> int:
        self._counters[key] = self._counters.get(key, 0) + 1
        return self._counters[key]

    async def expire(self, key: str, seconds: int) -> bool:
        return key in self._counters

    async def get(self, key: str) -> str | None:
        return self._kv.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self._kv[key] = value
        return True

    async def delete(self, key: str) -> int:
        return 1 if self._kv.pop(key, None) is not None else 0


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> FakeRedis:
    """No live Redis in CI — in-memory stand-in for suppression, rate limits, photo cache."""
    fake = FakeRedis()
    monkeypatch.setattr(runner, "get_redis_client", lambda: fake)
    monkeypatch.setattr(rate_limit, "get_redis_client", lambda: fake)
    monkeypatch.setattr(photo_cache, "get_redis_client", lambda: fake)
    return fake
