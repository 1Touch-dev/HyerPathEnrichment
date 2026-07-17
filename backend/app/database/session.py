import logging
from collections.abc import AsyncIterator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()
# pool_pre_ping recycles stale connections (e.g. after a Postgres restart).
engine = create_async_engine(settings.database_url, future=True, pool_pre_ping=True)
logger.info("database engine created (dialect=%s)", engine.dialect.name)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

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


def _to_sync_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    if url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return url


def legacy_pre_alembic(connection) -> bool:
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


async def init_db() -> None:
    """Apply Alembic migrations. Auto-stamps legacy unversioned databases."""
    # Import all ORM modules so Base.metadata is complete before migrate/reflect.
    from app.compliance import models as _compliance_models  # noqa: F401
    from app.modules.enrichment import models as _enrichment_models  # noqa: F401
    from app.modules.signals import models as _signals_models  # noqa: F401
    from app.storage import models as _storage_models  # noqa: F401

    run_migrations(settings.database_url, stamp_if_legacy=True)
    logger.info("database schema migrated to alembic head (dialect=%s)", engine.dialect.name)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
