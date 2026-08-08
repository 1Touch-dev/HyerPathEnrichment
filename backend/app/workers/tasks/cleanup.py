"""Background cleanup tasks for job maintenance."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import engine
from app.modules.enrichment.models import JobRecord

logger = logging.getLogger(__name__)


async def cleanup_orphaned_jobs(max_age_minutes: int = 15) -> int:
    """Find and fix jobs stuck in 'running' or 'queued' with no worker progress.

    A job is considered orphaned if:
    - Status is 'running' or 'queued'
    - updated_at equals created_at (never progressed)
    - Created more than max_age_minutes ago

    This handles cases where:
    - Job was created but enqueue to RQ failed silently
    - Job was enqueued but worker crashed before updating status
    - Job lost in queue due to Redis restart

    Args:
        max_age_minutes: How old a stuck job must be before cleanup (default: 15 minutes)

    Returns:
        Number of jobs fixed
    """
    async with AsyncSession(engine, expire_on_commit=False) as db:
        # Find stuck jobs
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
        stmt = select(JobRecord).where(
            JobRecord.status.in_(["running", "queued"]),
            JobRecord.updated_at == JobRecord.created_at,
            JobRecord.created_at < cutoff,
        )
        result = await db.execute(stmt)
        stuck_jobs = result.scalars().all()

        if not stuck_jobs:
            logger.debug("No orphaned jobs found")
            return 0

        logger.warning(
            f"Found {len(stuck_jobs)} orphaned jobs",
            extra={"job_ids": [j.id for j in stuck_jobs], "max_age_minutes": max_age_minutes},
        )

        # Mark them as failed
        for job in stuck_jobs:
            original_status = job.status
            job.status = "failed"
            job.updated_at = datetime.now(timezone.utc)

            # Update progress metadata with error info
            if not job.progress_metadata:
                job.progress_metadata = {}
            job.progress_metadata["error"] = (
                f"Job orphaned - stuck in '{original_status}' for >{max_age_minutes} minutes "
                "with no worker progress. Likely enqueue failure or worker crash."
            )
            job.progress_metadata["cleanup_timestamp"] = datetime.now(timezone.utc).isoformat()
            job.progress_metadata["original_status"] = original_status

            logger.info(
                f"Marked orphaned job {job.id} as failed",
                extra={
                    "job_id": job.id,
                    "original_status": original_status,
                    "age_minutes": (datetime.now(timezone.utc) - job.created_at).total_seconds()
                    / 60,
                },
            )

        await db.commit()
        logger.info(f"Cleanup completed: marked {len(stuck_jobs)} orphaned jobs as failed")
        return len(stuck_jobs)
