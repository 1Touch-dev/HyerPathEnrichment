import logging
import os
import time
from typing import cast

from rq import SimpleWorker, Worker
from rq.timeouts import BaseDeathPenalty, UnixSignalDeathPenalty
from rq.worker import BaseWorker

# Import ORM registry FIRST to register all models with SQLAlchemy
import app.database.orm_registry  # noqa: F401
from app.core.config import get_settings, validate_outreach_settings, validate_tier1_settings
from app.core.logging import configure_logging
from app.observability.error_tracking import init_error_tracking
from app.workers.queue import get_redis_connection, get_worker_queue_names

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
    # Fail closed when outreach is enabled without a CAN-SPAM-required physical address.
    validate_outreach_settings(get_settings())
    # Logging before Sentry so LoggingIntegration can attach to the root logger.
    configure_logging()
    init_error_tracking()

    # Startup retry logic with exponential backoff
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        try:
            connection = get_redis_connection()
            # Test connection
            connection.ping()

            from rq import Queue

            queue_names = get_worker_queue_names()
            queues = [Queue(name, connection=connection) for name in queue_names]
            logger.info(f"Worker configured for queues: {queue_names}")

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
