import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry

from alembic import command
from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()
# pool_pre_ping recycles stale connections (e.g. after a Postgres restart).
_engine_kwargs: dict[str, Any] = {"future": True, "pool_pre_ping": True}
if settings.database_url.startswith("sqlite"):
    # SQLite's default rollback-journal mode takes an exclusive lock on writes,
    # so the API and worker processes sharing one file can race and raise
    # "database is locked" even for short INSERT/UPDATE statements (seen live
    # during the Tier 1 canary: photo_cache writes from the worker collided
    # with API reads). WAL allows concurrent readers during a writer, and
    # busy_timeout makes SQLite retry instead of failing immediately.
    _engine_kwargs["connect_args"] = {"timeout": 30}
engine = create_async_engine(settings.database_url, **_engine_kwargs)
if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection: Any, _connection_record: ConnectionPoolEntry) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()


logger.info("database engine created (dialect=%s)", engine.dialect.name)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _to_sync_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    if url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return url


# Sync session factory for RQ workers (sync context)
sync_engine = create_engine(_to_sync_url(settings.database_url), **_engine_kwargs)

SyncSessionLocal = sessionmaker(sync_engine, expire_on_commit=False, class_=Session)

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
BASELINE_REVISION = "001_baseline_schema"
# Stable lock key so API + worker do not run DDL concurrently.
_MIGRATION_LOCK_KEY = 0x4879_5245_4D49_4752  # "HYREMIGR"


def alembic_config(database_url: str | None = None) -> Config:
    """Build Alembic Config with package-relative paths (Docker + local safe)."""
    cfg = Config(str(_BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url or settings.database_url)
    return cfg


def legacy_pre_alembic(connection: Connection) -> bool:
    """True when ORM tables exist but Alembic has never stamped this database."""
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    return "jobs" in tables and "alembic_version" not in tables


def _stamp_and_upgrade(database_url: str, *, stamp_if_legacy: bool) -> None:
    cfg = alembic_config(database_url)
    if stamp_if_legacy:
        sync_engine = create_engine(_to_sync_url(database_url))
        try:
            with sync_engine.connect() as conn:
                needs_stamp = legacy_pre_alembic(conn)
        finally:
            sync_engine.dispose()
        if needs_stamp:
            logger.info("pre-Alembic schema detected; stamping %s", BASELINE_REVISION)
            command.stamp(cfg, BASELINE_REVISION)
    command.upgrade(cfg, "head")


def run_migrations(database_url: str, *, stamp_if_legacy: bool = True) -> None:
    """Stamp legacy bootstrap DBs at baseline (optional), then upgrade to head."""
    sync_url = _to_sync_url(database_url)
    if sync_url.startswith("postgresql"):
        lock_engine = create_engine(sync_url)
        try:
            with lock_engine.connect() as lock_conn:
                lock_conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": _MIGRATION_LOCK_KEY})
                lock_conn.commit()
                try:
                    _stamp_and_upgrade(database_url, stamp_if_legacy=stamp_if_legacy)
                finally:
                    lock_conn.execute(
                        text("SELECT pg_advisory_unlock(:k)"), {"k": _MIGRATION_LOCK_KEY}
                    )
                    lock_conn.commit()
        finally:
            lock_engine.dispose()
        return

    _stamp_and_upgrade(database_url, stamp_if_legacy=stamp_if_legacy)


def expected_schema_revision(database_url: str | None = None) -> str:
    """Return the Alembic head revision id for the configured database."""
    script = ScriptDirectory.from_config(alembic_config(database_url))
    head = script.get_current_head()
    if head is None:
        raise RuntimeError("no alembic head revision configured")
    return head


async def database_schema_at_head(session: AsyncSession) -> bool:
    """True when alembic_version matches the repository head revision."""
    head = expected_schema_revision()
    try:
        result = await session.execute(text("SELECT version_num FROM alembic_version"))
        current = result.scalar_one_or_none()
    except Exception:
        return False
    return current == head


async def init_db() -> None:
    """Apply Alembic migrations. Auto-stamps legacy unversioned databases."""
    # Import all ORM modules so Base.metadata is complete before migrate/reflect.

    run_migrations(settings.database_url, stamp_if_legacy=True)
    logger.info("database schema migrated to alembic head (dialect=%s)", engine.dialect.name)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


@asynccontextmanager
async def get_db_session_context() -> AsyncIterator[AsyncSession]:
    """Async context-manager wrapper around the same session factory
    `get_db_session()` uses — for callers outside FastAPI's `Depends()`
    injection (e.g. ASGI middleware), which cannot receive
    `db: AsyncSession = Depends(get_db_session)` the way routes do."""
    async with SessionLocal() as session:
        yield session
