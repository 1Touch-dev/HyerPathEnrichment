"""Shared pytest fixtures for backend API tests."""

from __future__ import annotations

import os
from pathlib import Path

# Bind a dedicated SQLite file before any app import creates the async engine.
# Relative ``./hyrepath.db`` (and local ``.env`` overrides) diverge between
# repo-root CI, ``cd backend``, and leftover developer DBs.
_TEST_DB = Path(__file__).resolve().parent / "_pytest_hyrepath.db"
if _TEST_DB.exists():
    _TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB.as_posix()}"

import pytest

from app.compliance import suppression
from app.core.config import get_settings
from app.dependencies import rate_limit
from app.storage import photo_cache
from tests.migration_helpers import upgrade_head


@pytest.fixture(scope="session", autouse=True)
def ensure_db_schema() -> None:
    """Migrate host SQLite so bare TestClient tests (no lifespan) have tables.

    ``verify_tier234_live`` runs ``test_pipeline_shape`` with ``TestClient(app)``
    without a context manager, so FastAPI lifespan / ``init_db`` never runs.
    """
    upgrade_head(get_settings().database_url)


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

    async def ping(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> FakeRedis:
    """No live Redis in CI — in-memory stand-in for suppression, rate limits, photo cache."""
    fake = FakeRedis()
    monkeypatch.setattr(suppression, "get_redis_client", lambda: fake)
    monkeypatch.setattr(rate_limit, "get_redis_client", lambda: fake)
    monkeypatch.setattr(photo_cache, "get_redis_client", lambda: fake)
    return fake
