"""Shared pytest fixtures for backend API tests."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

# Check if running in Docker container with real infrastructure
# If DATABASE_URL is already set to PostgreSQL, use it (real infrastructure testing)
# Otherwise, use SQLite for isolated unit tests
_EXISTING_DB_URL = os.environ.get("DATABASE_URL", "")
_USE_REAL_INFRA = "postgresql" in _EXISTING_DB_URL.lower()

if not _USE_REAL_INFRA:
    # Use SQLite for local/CI testing (isolated environment)
    _TEST_DB = Path(__file__).resolve().parent / "_pytest_hyrepath.db"
    if _TEST_DB.exists():
        _TEST_DB.unlink()
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB.as_posix()}"
    print(f"[TEST CONFIG] Using SQLite: {_TEST_DB}")
else:
    # Use existing PostgreSQL (real infrastructure testing)
    print(f"[TEST CONFIG] Using real PostgreSQL: {_EXISTING_DB_URL[:50]}...")

os.environ["API_TOKEN"] = "change-me"

import asyncio

import pytest
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.compliance import suppression
from app.core.config import get_settings
from app.database.session import get_db_session
from app.modules.enrichment import job_events
from app.storage import photo_cache
from tests.migration_helpers import upgrade_head


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the entire test session.

    This ensures all async fixtures and tests use the same event loop,
    preventing 'attached to a different loop' errors.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_test_database():
    """Initialize database engine for tests and dispose after all tests complete.

    For PostgreSQL: Disposes and recreates the engine to ensure it binds to the test event loop.
    For SQLite: Just ensures proper cleanup.
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.database import session as db_session_module

    # Check if using PostgreSQL (which has the event loop issue)
    db_url = get_settings().database_url
    if "postgresql" in db_url.lower():
        # Dispose the module-level engine that was created with the wrong event loop
        await db_session_module.engine.dispose()

        # Recreate engine in the correct event loop with NullPool to avoid connection reuse issues
        from sqlalchemy.pool import NullPool

        db_session_module.engine = create_async_engine(
            db_url,
            future=True,
            pool_pre_ping=True,
            poolclass=NullPool,  # Disable pooling for tests to avoid cross-loop issues
        )

        # Recreate SessionLocal with new engine
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        db_session_module.SessionLocal = async_sessionmaker(
            db_session_module.engine, expire_on_commit=False, class_=AsyncSession
        )

    yield

    # Dispose of the engine after all tests complete
    await db_session_module.engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def ensure_db_schema() -> None:
    """Migrate database so tests have tables.

    For SQLite: Creates fresh test database
    For PostgreSQL: Assumes migrations already ran (via docker-compose migrate service)

    ``verify_tier234_live`` runs ``test_pipeline_shape`` with ``TestClient(app)``
    without a context manager, so FastAPI lifespan / ``init_db`` never runs.
    """
    db_url = get_settings().database_url

    # Only run migrations for SQLite (PostgreSQL already migrated by docker-compose)
    if "sqlite" in db_url.lower():
        upgrade_head(db_url)
        print("[TEST CONFIG] SQLite schema migrated")
    else:
        print("[TEST CONFIG] Using existing PostgreSQL schema (migrations assumed complete)")


class FakeRedis:
    def __init__(self) -> None:
        self._sets: dict[str, set[str]] = {}
        self._counters: dict[str, int] = {}
        self._kv: dict[str, str] = {}
        self._lists: dict[str, list[str]] = {}

    # Async methods for Redis async client (wrapping sync methods)
    async def delete_async(self, key: str) -> int:
        """Delete key (async version)."""
        return 1 if self._kv.pop(key, None) is not None else 0

    async def sismember(self, key: str, value: str) -> bool:
        return value in self._sets.get(key, set())

    async def incr(self, key: str) -> int:
        self._counters[key] = self._counters.get(key, 0) + 1
        return self._counters[key]

    async def expire(self, key: str, seconds: int) -> bool:
        return key in self._counters

    async def eval(self, script: str, numkeys: int, *keys_and_args: str) -> int:
        """Reproduce the weighted sliding-window Lua script's semantics.

        Not a general Lua interpreter -- this mirrors the exact algorithm in
        ``app.infrastructure.redis._RATE_LIMIT_SCRIPT`` (same weighted-estimate
        formula, same reject-without-incrementing-on-limit behavior) against
        this fake's own ``_counters`` dict, which is the same store ``incr``/
        ``expire`` above already use. The current/previous window keys and the
        weight are computed by the real (unmocked) ``check_rate_limit`` before
        it calls ``client.eval(...)``, so there is nothing left for this fake
        to recompute independently -- it just has to apply the same estimate
        check and increment step against its own state.
        """
        current_key, previous_key = keys_and_args[:numkeys]
        limit_str, weight_str = keys_and_args[numkeys], keys_and_args[numkeys + 1]
        limit = int(limit_str)
        weight = float(weight_str)

        current = self._counters.get(current_key, 0)
        previous = self._counters.get(previous_key, 0)
        estimated = current + previous * weight
        if estimated >= limit:
            return 0

        self._counters[current_key] = current + 1
        return 1

    async def get(self, key: str) -> str | None:
        return self._kv.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self._kv[key] = value
        return True

    async def publish(self, channel: str, message: str) -> int:
        return 0

    async def ping(self) -> bool:
        return True

    # RQ compatibility methods (sync)
    def lpush(self, key: str, *values: str) -> int:
        """Push values to list (for RQ queue compatibility)."""
        lst = self._lists.setdefault(key, [])
        lst.extend(values)
        return len(lst)

    def rpop(self, key: str) -> str | None:
        """Pop value from list (for RQ queue compatibility)."""
        lst = self._lists.get(key, [])
        return lst.pop() if lst else None

    async def exists(self, key: str) -> int:
        """Check if key exists (matches redis.asyncio.Redis.exists)."""
        return 1 if key in self._kv or key in self._lists or key in self._sets else 0

    def _exists_sync(self, key: str) -> int:
        """Sync helper for internal RQ-compatibility methods."""
        return 1 if key in self._kv or key in self._lists or key in self._sets else 0

    def hset(self, name: str, key: str, value: str) -> int:
        """Set hash field (for RQ compatibility)."""
        hash_key = f"{name}:{key}"
        self._kv[hash_key] = value
        return 1

    def hgetall(self, name: str) -> dict[str, str]:
        """Get all hash fields (for RQ compatibility)."""
        prefix = f"{name}:"
        return {k.removeprefix(prefix): v for k, v in self._kv.items() if k.startswith(prefix)}

    async def setex(self, key: str, time: int, value: str) -> bool:
        """Set with expiry (matches redis.asyncio.Redis.setex)."""
        self._kv[key] = value
        return True

    async def sadd(self, key: str, *values: str) -> int:
        """Add members to set (async, matches redis.asyncio.Redis.sadd)."""
        members = self._sets.setdefault(key, set())
        added = len([value for value in values if value not in members])
        members.update(values)
        return added

    def smembers(self, key: str) -> set:
        """Get all set members (for RQ)."""
        return self._sets.get(key, set())

    def srem(self, key: str, *values: str) -> int:
        """Remove members from set (for RQ)."""
        if key not in self._sets:
            return 0
        removed = 0
        for value in values:
            if value in self._sets[key]:
                self._sets[key].remove(value)
                removed += 1
        return removed

    def delete(self, *keys: str) -> int:
        """Delete keys (for RQ)."""
        count = 0
        for key in keys:
            if self._kv.pop(key, None) is not None:
                count += 1
            if self._lists.pop(key, None) is not None:
                count += 1
            if self._sets.pop(key, None) is not None:
                count += 1
        return count

    def ttl(self, key: str) -> int:
        """Time to live (for RQ - always return -1 for no expiry)."""
        return -1 if self._exists_sync(key) else -2

    def zadd(self, name: str, mapping: dict) -> int:
        """Add to sorted set (stub for RQ)."""
        return len(mapping)

    def zrem(self, name: str, *values: str) -> int:
        """Remove from sorted set (stub for RQ)."""
        return len(values)

    def zcard(self, name: str) -> int:
        """Get sorted set cardinality (stub for RQ)."""
        return 0

    def zrange(self, name: str, start: int, end: int) -> list:
        """Get sorted set range (stub for RQ)."""
        return []

    def pipeline(self):
        """Return self as a fake pipeline (for RQ)."""
        return self

    def execute(self):
        """Execute pipeline (no-op for fake)."""
        return []

    def watch(self, *keys: str):
        """Watch keys (no-op for fake)."""

    def multi(self):
        """Start transaction (no-op for fake)."""


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> FakeRedis:
    """Mock Redis for tests.

    - For SQLite tests: Uses FakeRedis (isolated testing)
    - For PostgreSQL tests: Uses real Redis (integration testing with real workers)
    """
    # Re-check at runtime (environment might have been set after module import)
    db_url = os.environ.get("DATABASE_URL", "")
    redis_url = os.environ.get("REDIS_URL", "")
    use_real_infra = "postgresql" in db_url.lower()
    use_real_redis = "redis:" in redis_url.lower() and use_real_infra

    if use_real_redis:
        # Real infrastructure testing - use actual Redis, don't mock anything
        print(f"[TEST CONFIG] Using real Redis: {redis_url}")
        print("[TEST CONFIG] NOT mocking Redis or RQ - using real infrastructure")
        # Return a dummy object since tests expect this fixture to return something
        return FakeRedis()

    # Isolated testing - use FakeRedis
    print("[TEST CONFIG] Using FakeRedis (mocked)")
    fake = FakeRedis()
    monkeypatch.setattr(suppression, "get_redis_client", lambda: fake)
    monkeypatch.setattr("app.dependencies.rate_limit.get_redis_client", lambda: fake)
    monkeypatch.setattr(photo_cache, "get_redis_client", lambda: fake)
    monkeypatch.setattr(job_events, "_get_events_redis_client", lambda: fake)
    # Patch workers.queue.get_redis_connection for document service
    monkeypatch.setattr("app.workers.queue.get_redis_connection", lambda: fake)
    # Patch auth router's Redis usage (token blacklisting on logout/delete)
    monkeypatch.setattr("app.auth.router.get_redis_client", lambda: fake)
    monkeypatch.setattr("app.auth.dependencies.get_redis_client", lambda: fake)

    # Mock RQ Queue for document processing tests
    class FakeRQJob:
        """Fake RQ job object."""

        def __init__(self, job_id: str, status: str = "queued"):
            self.id = job_id
            self.status = status
            self.result = None

    class FakeQueue:
        """Fake RQ Queue that processes jobs synchronously for testing."""

        def __init__(self, name: str, connection=None):
            self.name = name
            self.connection = connection
            self._jobs = {}

        def enqueue(self, func, *args, job_timeout=None, **kwargs):
            """Enqueue and immediately process job synchronously."""
            import importlib
            import uuid

            job_id = str(uuid.uuid4())
            job = FakeRQJob(job_id)
            self._jobs[job_id] = job

            # Try to actually process the job synchronously if it's a string path
            if isinstance(func, str):
                try:
                    # Verify the target function is importable before marking queued
                    module_path, func_name = func.rsplit(".", 1)
                    module = importlib.import_module(module_path)
                    getattr(module, func_name)
                    # Call it in the background (don't block)
                    # For now, just mark as queued - the test will need to handle this
                    job.status = "queued"
                except Exception as e:
                    print(f"[FakeQueue] Failed to process job {job_id}: {e}")
                    job.status = "failed"

            return job

    # Patch RQ Queue class - patch where it's used, not where it's defined
    import rq

    monkeypatch.setattr("app.modules.documents.service.Queue", FakeQueue)
    monkeypatch.setattr(rq, "Queue", FakeQueue)  # Keep this for other potential uses

    return fake


@pytest.fixture
async def db():
    """Provide async database session for tests.

    Creates a new session for each test and ensures proper cleanup.
    """
    from app.database.session import SessionLocal

    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()


async def test_auth_dependency(
    authorization: str | None = Header(None),
    x_test_user_id: str | None = Header(None, alias="X-Test-User-ID"),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """Test authentication dependency that supports X-Test-User-ID header.

    This allows tests to bypass cookie-based JWT auth and directly specify a test user.

    Args:
        authorization: Bearer token (must match API_TOKEN for test mode)
        x_test_user_id: Test user ID (creates user if not exists)
        db: Database session (provided by dependency injection)

    Returns:
        Test User object

    Raises:
        HTTPException: If authorization fails
    """
    settings = get_settings()

    # Verify API token
    if not authorization or authorization != f"Bearer {settings.api_token}":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authorization",
        )

    # Get or create test user
    if not x_test_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Test-User-ID header required in test mode",
        )

    user_uuid = UUID(x_test_user_id)

    # Check if user exists
    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    # Create user if doesn't exist
    if not user:
        user = User(
            id=user_uuid,
            email=f"test_{x_test_user_id[:8]}@example.com",
            first_name="Test",
            last_name="User",
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user


@pytest.fixture(autouse=True)
async def override_auth_for_tests() -> None:
    """Override authentication dependencies to use test auth."""
    from app.auth.dependencies import get_current_user_from_cookie, require_verified_user
    from app.main import app

    # Override dependencies for test mode
    app.dependency_overrides[get_current_user_from_cookie] = test_auth_dependency
    app.dependency_overrides[require_verified_user] = test_auth_dependency

    yield

    # Clean up overrides after test
    app.dependency_overrides.clear()
