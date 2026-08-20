import logging
import os
import time
from typing import cast

from rq import SimpleWorker, Worker
from rq.timeouts import BaseDeathPenalty, UnixSignalDeathPenalty
from rq.worker import BaseWorker

# Import ORM registry FIRST to register all models with SQLAlchemy
import app.database.orm_registry  # noqa: F401
from app.core.config import get_settings, validate_tier1_settings
from app.core.logging import configure_logging
from app.observability.error_tracking import init_error_tracking
from app.workers.queue import get_redis_connection

logger = logging.getLogger(__name__)


class _NoOpDeathPenalty(BaseDeathPenalty):
    """Windows-safe timeout context: RQ's signal-based penalties don't work here."""

    def setup_death_penalty(self) -> None:
        pass

    def cancel_death_penalty(self) -> None:
        pass


def main() -> None:
    # Fail closed when Tier 1 is enabled without Multilogin/bot (and prod R2).
    validate_tier1_settings(get_settings())
    # Logging before Sentry so LoggingIntegration can attach to the root logger.
    configure_logging()
    init_error_tracking()

    settings = get_settings()

    # Startup retry logic with exponential backoff
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        try:
            connection = get_redis_connection()
            # Test connection
            connection.ping()

            from rq import Queue

            if settings.worker_queue_mode == "per_tier":
                # Tier-specific worker: must listen to exactly one assigned queue.
                if not settings.worker_target_queue:
                    raise ValueError("WORKER_TARGET_QUEUE required when WORKER_QUEUE_MODE=per_tier")
                queues = [Queue(settings.worker_target_queue, connection=connection)]
                logger.info(f"Worker configured for tier queue: {settings.worker_target_queue}")
            else:
                # General-purpose worker: listen to feedback, document processing, and default queues
                from app.workers.queue import (
                    QUEUE_CV_EXTRACTION,
                    QUEUE_DOCUMENT,
                    QUEUE_EMBEDDING,
                    QUEUE_FEEDBACK,
                    QUEUE_INTERVIEW_REMINDERS,  # NEW
                    QUEUE_NAME,
                    QUEUE_OUTREACH,  # NEW
                    QUEUE_QUESTION_GENERATION,
                )

                queues = [
                    Queue(QUEUE_FEEDBACK, connection=connection),  # Week 2: Interview feedback
                    Queue(
                        QUEUE_QUESTION_GENERATION, connection=connection
                    ),  # Week 2 Module 3: question pre-gen
                    Queue(QUEUE_OUTREACH, connection=connection),  # NEW — Module 2
                    Queue(QUEUE_INTERVIEW_REMINDERS, connection=connection),  # NEW — Module D
                    Queue(QUEUE_DOCUMENT, connection=connection),  # Week 1: Document processing
                    Queue(QUEUE_EMBEDDING, connection=connection),  # Week 1: Embeddings
                    Queue(QUEUE_CV_EXTRACTION, connection=connection),  # Week 1: CV extraction
                    Queue(QUEUE_NAME, connection=connection),  # Original enrichment queue
                ]
                logger.info(f"Worker configured for multiple queues: {[q.name for q in queues]}")

            logger.info("Successfully connected to Redis")
            break
        except Exception as exc:
            if attempt == max_attempts:
                logger.error(
                    f"Failed to connect to Redis after {max_attempts} attempts",
                    exc_info=True,
                )
                raise

            backoff_seconds = 2**attempt  # Exponential backoff: 2, 4, 8, 16 seconds
            logger.warning(
                f"Failed to connect to Redis (attempt {attempt}/{max_attempts}), "
                f"retrying in {backoff_seconds}s: {exc}"
            )
            time.sleep(backoff_seconds)

    logger.info(f"Worker starting, listening to queues: {[q.name for q in queues]}")

    # RQ's default Worker forks (no os.fork on Windows) and uses SIGALRM
    # for job timeouts (also unavailable on Windows). SimpleWorker + no-op
    # death penalty keeps local dev working; Linux production keeps defaults.
    worker: BaseWorker
    if hasattr(os, "fork"):
        worker = Worker(queues, connection=connection)
    else:
        worker = SimpleWorker(queues, connection=connection)
        # RQ's stubs type death_penalty_class as type[UnixSignalDeathPenalty];
        # cast satisfies both older mypy (which flags the assignment) and newer
        # mypy 2.3+ (which flags unused type: ignore comments).
        worker.death_penalty_class = cast(type[UnixSignalDeathPenalty], _NoOpDeathPenalty)
    # RQ's scheduler runs as a forked subprocess (rq.scheduler.RQScheduler._process).
    # On Windows, multiprocessing has no fork and falls back to spawn, which pickles
    # the target object graph — including this worker's Redis connection, which holds
    # an unpicklable `_thread.lock` — causing `TypeError: cannot pickle '_thread.lock'
    # object` and crashing the whole worker. Same os.fork() check as the Worker/
    # SimpleWorker split above.
    if not hasattr(os, "fork"):
        logger.warning(
            "RQ scheduler disabled on Windows (multiprocessing spawn can't pickle the "
            "Redis connection) — scheduled jobs won't auto-fire; queue processing still works"
        )
    worker.work(with_scheduler=hasattr(os, "fork"))


if __name__ == "__main__":
    main()
