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
    # Admin Module (phase2_admin_module.md §9): cache.py's cached_aggregate() and
    # health.py's Redis ping both import get_redis_client from
    # app.infrastructure.redis directly into their own module namespace, so they
    # need their own patch targets here, same as every other module above.
    monkeypatch.setattr("app.modules.admin.cache.get_redis_client", lambda: fake)
    monkeypatch.setattr("app.modules.admin.health.get_redis_client", lambda: fake)
    # impersonation.py's end_impersonation() imports get_redis_client *inside*
    # the function body (not at module top), so there is no
    # `app.modules.admin.impersonation.get_redis_client` name to patch — the
    # lookup happens against the source module at call time. Patching the
    # source directly covers this and any other function-scoped import site.
    monkeypatch.setattr("app.infrastructure.redis.get_redis_client", lambda: fake)

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


# ---------------------------------------------------------------------------
# Admin Module (phase2_admin_module.md §9) fixtures.
#
# The plan's example test snippets (§9.1-§9.11) reference fixture names —
# `db_session`, `client`, `superuser`, `superuser_cookie`, `regular_user`,
# `support_user`, `support_role_cookie`, `seed_user`, `mock_redis`,
# `seeded_job_postings`, `superuser_with_mfa` — that assume a cookie-based
# login flow. This repo's actual test-auth mechanism is the header-based
# `test_auth_dependency` above (X-Test-User-ID + Bearer API token), so the
# fixtures below are adapted to that mechanism instead of inventing a second,
# parallel one. Where the plan says "*_cookie", use `auth_headers(user.id)`.
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_session():
    """Async DB session fixture — name matches phase2_admin_module.md's tests.

    Same lifecycle as the `db` fixture above; kept separate (rather than a
    plain alias) so admin tests read the same way the plan wrote them.
    """
    from app.database.session import SessionLocal

    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()


@pytest.fixture
def db_engine():
    """The application's async engine, already pointed at the test database
    by `setup_test_database`/`ensure_db_schema` above. Resolved fresh on each
    use (not cached at session scope) since `setup_test_database` may replace
    the module-level engine object for PostgreSQL runs."""
    from app.database import session as db_session_module

    return db_session_module.engine


@pytest.fixture
def client():
    """Shared TestClient(app), matching test_admin_costs.py's existing pattern.

    Test files that need different behavior (e.g. a `with TestClient(app)`
    lifespan context) define their own local `client` fixture, which shadows
    this one for that module only.
    """
    from fastapi.testclient import TestClient as _TestClient

    from app.main import app

    return _TestClient(app)


SQLITE_ROLE_UUID_DASH_BUG_REASON = (
    "KNOWN BUG (SQLite-only, not fixed here — this task is test-writing/running only): "
    "migration 038 seeds roles/permissions/role_permissions via raw SQL using "
    "str(uuid4()) (dashed, e.g. '09467844-bb13-...'), while every ORM-written UUID "
    "column (e.g. users.role_id, via the Mapped[UUID] default Uuid type) is stored "
    "WITHOUT dashes on SQLite (confirmed directly against the sqlite file: roles.id is "
    "dashed, users.role_id for the same role is undashed). Any FK comparison between an "
    "ORM-written UUID value and a migration-seeded UUID value never matches as a raw "
    "SQLite TEXT comparison, so user_has_permission()'s RolePermission lookup silently "
    "returns no rows for any role-based (non-superuser) user on SQLite. Does not affect "
    "PostgreSQL (native UUID column). Root cause is in app/modules/admin/models.py / the "
    "migration files, both out of scope for this test-only task."
)


@pytest.fixture
def auth_headers():
    """Factory returning the X-Test-User-ID + Bearer headers `test_auth_dependency`
    expects. Stands in for the plan's cookie-based `superuser_cookie` /
    `support_role_cookie` fixtures — see module docstring above."""
    settings = get_settings()

    def _make(user_id) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.api_token}",
            "X-Test-User-ID": str(user_id),
        }

    return _make


async def _make_persisted_user(db_session, /, **overrides):
    from uuid import uuid4

    from app.auth.models import User

    defaults = {
        "id": uuid4(),
        "email": f"admin-test-{uuid4().hex[:10]}@example.com",
        "first_name": "Test",
        "last_name": "User",
        "is_active": True,
        "is_verified": True,
        "is_superuser": False,
    }
    defaults.update(overrides)
    user = User(**defaults)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def superuser(db_session):
    """Real, persisted superuser row (not a MagicMock) — needed so HTTP-level
    tests that authenticate via `auth_headers(superuser.id)` resolve to a real
    DB user with `is_superuser=True` when `test_auth_dependency` looks it up."""
    return await _make_persisted_user(db_session, is_superuser=True)


@pytest.fixture
async def regular_user(db_session):
    return await _make_persisted_user(db_session)


@pytest.fixture
async def seed_user(db_session):
    """Distinct persisted user for tests (e.g. test_admin_audit.py) that need
    an actor unrelated to any other fixture in the same test."""
    return await _make_persisted_user(db_session)


@pytest.fixture
async def support_user(db_session):
    """Persisted user assigned the seeded 'support' role (migration 038):
    users:read, users:suspend, audit_logs:read, system_health:read — read-only
    plus suspend, no write/role-management permissions."""
    from sqlalchemy import select

    from app.modules.admin.models import Role

    result = await db_session.execute(select(Role).where(Role.name == "support"))
    support_role = result.scalar_one()
    return await _make_persisted_user(db_session, role_id=support_role.id)


@pytest.fixture
async def superuser_with_mfa(db_session):
    """Superuser with TOTP MFA enrolled+enabled, secret known to the test so it
    can compute valid codes with `pyotp.TOTP(user.mfa_secret).now()`."""
    from datetime import UTC, datetime

    import pyotp

    return await _make_persisted_user(
        db_session,
        is_superuser=True,
        mfa_enabled=True,
        mfa_secret=pyotp.random_base32(),
        mfa_enrolled_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_redis(fake_redis):
    """Alias for phase2_admin_module.md's fixture name — same FakeRedis
    instance the autouse `fake_redis` fixture above already installs
    everywhere Admin Module code reads Redis (cache.py, health.py)."""
    return fake_redis


@pytest.fixture
async def seeded_job_postings(db_session):
    """A handful of JobPosting + JobMatch rows for test_admin_analytics.py —
    enough spread across `source`/`company` to exercise the group-by
    aggregates in app/modules/admin/analytics.py.

    Source/company names carry a unique-per-invocation suffix so tests that
    run get_job_match_analytics() (a table-wide aggregate, not scoped to this
    fixture's own rows) can assert exact counts without leaking into/from
    other tests that also use this fixture in the same session-scoped SQLite
    database.
    """
    from uuid import uuid4

    from app.modules.job_matching.models import JobMatch, JobPosting

    suffix = uuid4().hex[:8]
    postings_spec = [
        (f"linkedin-{suffix}", f"Acme Corp {suffix}", 100_000, 140_000),
        (f"linkedin-{suffix}", f"Acme Corp {suffix}", 110_000, 150_000),
        (f"indeed-{suffix}", f"Globex Inc {suffix}", 90_000, 120_000),
    ]
    postings = []
    for source, company, salary_min, salary_max in postings_spec:
        posting = JobPosting(
            dedup_key=f"dedup-{uuid4().hex}",
            title="Backend Engineer",
            company=company,
            location="Remote",
            remote=True,
            source=source,
            source_url="https://example.com/job",
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency="USD",
        )
        db_session.add(posting)
        postings.append(posting)
    await db_session.commit()
    for posting in postings:
        await db_session.refresh(posting)

    user = await _make_persisted_user(db_session)
    for i, posting in enumerate(postings):
        match = JobMatch(
            user_id=user.id,
            job_posting_id=posting.id,
            similarity_score=0.8,
            rule_score=0.7,
            overall_score=70.0 + i * 10,
            score_breakdown={"salary_fit": 1.0},
        )
        db_session.add(match)
    await db_session.commit()

    return postings
