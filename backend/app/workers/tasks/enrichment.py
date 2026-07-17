"""Background enrichment task — adapter only; execution lives in Pipeline."""

from __future__ import annotations

import asyncio
import logging

from app.database.session import SessionLocal, engine
from app.enrichers.pipeline import Pipeline
from app.infrastructure.redis import close_redis

logger = logging.getLogger(__name__)


def run_enrichment_job(job_id: str) -> None:
    """RQ entrypoint (sync). Bridges into the async pipeline.

    RQ workers are synchronous, so each job gets its own event loop via
    asyncio.run and its own DB session. Never reuse a global loop here.
    """
    asyncio.run(_run_enrichment_job(job_id))


async def _run_enrichment_job(job_id: str) -> None:
    try:
        async with SessionLocal() as session:
            pipeline = Pipeline(session)
            await pipeline.execute_job(job_id)
    finally:
        # Each job runs under asyncio.run with a fresh event loop, but the
        # Redis client and DB engine pool are module-global. Connections
        # created here are bound to this loop and break the next job with
        # "Event loop is closed" — drop them before the loop shuts down.
        await close_redis()
        await engine.dispose()
