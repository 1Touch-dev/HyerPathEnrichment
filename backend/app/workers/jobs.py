import asyncio
import logging

from app.services import get_orchestrator
from app.storage.db import SessionLocal, engine
from app.storage.redis_client import close_redis

logger = logging.getLogger(__name__)


def run_enrichment_job(job_id: str) -> None:
    """RQ entrypoint (sync). Bridges into the async orchestrator.

    RQ workers are synchronous, so each job gets its own event loop via
    asyncio.run and its own DB session. Never reuse a global loop here.
    """
    asyncio.run(_run_enrichment_job(job_id))


async def _run_enrichment_job(job_id: str) -> None:
    try:
        async with SessionLocal() as session:
            orchestrator = get_orchestrator(session)
            await orchestrator.execute_job(job_id)
    finally:
        # Each job runs under asyncio.run with a fresh event loop, but the
        # Redis client and DB engine pool are module-global. Connections
        # created here are bound to this loop and break the next job with
        # "Event loop is closed" — drop them before the loop shuts down.
        await close_redis()
        await engine.dispose()
