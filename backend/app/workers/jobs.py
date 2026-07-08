import asyncio
import logging

from app.services import get_orchestrator
from app.storage.db import SessionLocal

logger = logging.getLogger(__name__)


def run_enrichment_job(job_id: str) -> None:
    """RQ entrypoint (sync). Bridges into the async orchestrator.

    RQ workers are synchronous, so each job gets its own event loop via
    asyncio.run and its own DB session. Never reuse a global loop here.
    """
    asyncio.run(_run_enrichment_job(job_id))


async def _run_enrichment_job(job_id: str) -> None:
    async with SessionLocal() as session:
        orchestrator = get_orchestrator(session)
        await orchestrator.execute_job(job_id)
