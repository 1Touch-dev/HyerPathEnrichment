from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.auth.logged_out_tokens import LoggedOutTokenService
from app.core.logging import configure_logging
from app.database.session import get_db_session
from app.infrastructure.redis import close_redis, get_redis_client
from app.modules.enrichment.job_events import close_events_redis
from app.observability.error_tracking import init_error_tracking


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Logging before Sentry so LoggingIntegration can attach to the root logger.
    configure_logging()
    init_error_tracking()
    redis_client = get_redis_client()

    # Sync logged-out tokens from PostgreSQL to Redis on startup
    try:
        async for db in get_db_session():
            blacklist_service = LoggedOutTokenService(redis_client)
            await blacklist_service.sync_blacklist_to_redis(db)
            break  # Only need one session for startup sync
    except Exception as e:
        # Log error but don't prevent startup
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Failed to sync logged-out tokens on startup: {e}")

    yield
    await close_redis()
    await close_events_redis()
