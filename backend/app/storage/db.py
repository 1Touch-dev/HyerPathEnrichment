import logging
from collections.abc import AsyncIterator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models import Base

logger = logging.getLogger(__name__)

settings = get_settings()
# pool_pre_ping recycles stale connections (e.g. after a Postgres restart).
engine = create_async_engine(settings.database_url, future=True, pool_pre_ping=True)
logger.info("database engine created (dialect=%s)", engine.dialect.name)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _migrate_schema(connection) -> None:
    """Add columns introduced after first deploy (no Alembic yet)."""
    inspector = inspect(connection)
    if "jobs" not in inspector.get_table_names():
        return

    job_columns = {column["name"] for column in inspector.get_columns("jobs")}
    if "identifier_hashes" not in job_columns:
        if connection.dialect.name == "postgresql":
            connection.execute(text("ALTER TABLE jobs ADD COLUMN identifier_hashes JSONB NOT NULL DEFAULT '[]'::jsonb"))
        else:
            connection.execute(text("ALTER TABLE jobs ADD COLUMN identifier_hashes JSON NOT NULL DEFAULT '[]'"))
        logger.info("migrated jobs.identifier_hashes column")


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_schema)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
