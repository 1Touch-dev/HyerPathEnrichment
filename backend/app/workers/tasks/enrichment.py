"""Background enrichment task — adapter only; execution lives in Pipeline."""

from __future__ import annotations

import asyncio
import logging

# Import ORM registry FIRST to register all models with SQLAlchemy
import app.database.orm_registry  # noqa: F401

from app.core.logging import set_job_id
from app.database.session import SessionLocal, engine
from app.domain.enums import JobStatus
from app.enrichers.pipeline import Pipeline
from app.infrastructure.redis import close_redis
from app.modules.enrichment.job_events import close_events_redis, publish_job_status
from app.modules.enrichment.repository import JobRepository
from app.observability.error_tracking import capture_exception, set_job_context

logger = logging.getLogger(__name__)


def run_enrichment_job(job_id: str) -> None:
    """RQ entrypoint (sync). Bridges into the async pipeline.

    RQ workers are synchronous, so each job gets its own event loop via
    asyncio.run and its own DB session. Never reuse a global loop here.
    """
    asyncio.run(_run_enrichment_job(job_id))


async def _run_enrichment_job(job_id: str) -> None:
    set_job_context(job_id)
    set_job_id(job_id)
    session = None
    try:
        async with SessionLocal() as session:
            pipeline = Pipeline(session)
            await pipeline.execute_job(job_id)

            # Send job completion email
            try:
                jobs_repo = JobRepository(session)
                job = await jobs_repo.get(job_id)
                if job and job.status == JobStatus.completed.value:
                    # Extract business name from request payload
                    business_name = "N/A"
                    if job.request_payload:
                        business_name = (
                            job.request_payload.get("business_name")
                            or job.request_payload.get("full_name")
                            or job.request_payload.get("username")
                            or "Unknown"
                        )

                    # TODO: Extract user email from job metadata when user system is implemented
                    # For now, skip email sending in production until we have user emails
                    # enqueue_email(
                    #     template=EmailTemplate.JOB_COMPLETION,
                    #     recipient="user@example.com",  # Replace with actual user email
                    #     context={
                    #         "job_id": job_id,
                    #         "business_name": business_name,
                    #         "enriched_fields": job.dossier_payload or {},
                    #     },
                    # )
                    logger.info(
                        "Job completed successfully (email notification skipped - no user system yet)",
                        extra={"job_id": job_id, "business_name": business_name},
                    )
            except Exception as email_exc:
                # Don't fail the job if email sending fails
                logger.warning(
                    "Failed to send job completion email",
                    exc_info=True,
                    extra={"job_id": job_id, "error": str(email_exc)},
                )

    except Exception as exc:
        # Catch all exceptions including RQ JobTimeoutException
        logger.error(
            "enrichment job failed",
            exc_info=True,
            extra={"job_id": job_id, "exception_type": type(exc).__name__},
        )

        # Ensure job is marked as failed in database
        # This is critical for timeout exceptions that may bypass pipeline error handling
        try:
            if session is not None:
                await session.rollback()

            # Create new session to mark job as failed
            async with SessionLocal() as recovery_session:
                jobs_repo = JobRepository(recovery_session)
                failed_job = await jobs_repo.get(job_id)
                if failed_job is not None and failed_job.status == "running":
                    await jobs_repo.mark_status(failed_job, JobStatus.failed)
                    await publish_job_status(job_id, JobStatus.failed)
                    logger.info(
                        "marked timed-out job as failed",
                        extra={"job_id": job_id},
                    )

                    # Send job failure email
                    try:
                        business_name = "N/A"
                        if failed_job.request_payload:
                            business_name = (
                                failed_job.request_payload.get("business_name")
                                or failed_job.request_payload.get("full_name")
                                or failed_job.request_payload.get("username")
                                or "Unknown"
                            )

                        # TODO: Extract user email from job metadata when user system is implemented
                        # enqueue_email(
                        #     template=EmailTemplate.JOB_FAILED,
                        #     recipient="user@example.com",  # Replace with actual user email
                        #     context={
                        #         "job_id": job_id,
                        #         "business_name": business_name,
                        #         "error": str(exc),
                        #     },
                        # )
                        logger.info(
                            "Job failed (failure email notification skipped - no user system yet)",
                            extra={"job_id": job_id, "error": str(exc)},
                        )
                    except Exception as email_exc:
                        logger.warning(
                            "Failed to send job failure email",
                            exc_info=True,
                            extra={"job_id": job_id, "error": str(email_exc)},
                        )
        except Exception:
            logger.error(
                "failed to mark job as failed during error recovery",
                exc_info=True,
                extra={"job_id": job_id},
            )

        capture_exception(exc, tags={"job_id": job_id})
        raise
    finally:
        set_job_id(None)
        # Each job runs under asyncio.run with a fresh event loop, but the
        # Redis clients (both the shared request-path client and job_events'
        # dedicated pub/sub client) and the DB engine pool are module-global.
        # Connections created here are bound to this loop and break the next
        # job with "Event loop is closed" — drop them before the loop shuts
        # down. Missing close_events_redis() here previously left a stale
        # pub/sub client alive across jobs, which crashed the *next* job's
        # publish_job_status call once this loop closed (seen live during
        # the Tier 1 canary: job 2 in a worker process failed with
        # `AttributeError: 'NoneType' object has no attribute 'send'` /
        # `RuntimeError: Event loop is closed`).
        await close_redis()
        await close_events_redis()
        await engine.dispose()
