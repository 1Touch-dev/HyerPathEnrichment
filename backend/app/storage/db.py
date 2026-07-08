import logging
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models import Base

logger = logging.getLogger(__name__)

settings = get_settings()
# pool_pre_ping recycles stale connections (e.g. after a Postgres restart).
engine = create_async_engine(settings.database_url, future=True, pool_pre_ping=True)
logger.info("database engine created (dialect=%s)", engine.dialect.name)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
