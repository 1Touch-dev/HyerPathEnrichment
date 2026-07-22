import os
from typing import cast

from rq import Queue, SimpleWorker, Worker
from rq.timeouts import BaseDeathPenalty, UnixSignalDeathPenalty
from rq.worker import BaseWorker

from app.core.config import get_settings, validate_tier1_settings
from app.core.logging import configure_logging
from app.observability.error_tracking import init_error_tracking
from app.workers.queue import QUEUE_NAME, get_redis_connection


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
    connection = get_redis_connection()
    queue = Queue(QUEUE_NAME, connection=connection)
    # RQ's default Worker forks (no os.fork on Windows) and uses SIGALRM
    # for job timeouts (also unavailable on Windows). SimpleWorker + no-op
    # death penalty keeps local dev working; Linux production keeps defaults.
    worker: BaseWorker
    if hasattr(os, "fork"):
        worker = Worker([queue], connection=connection)
    else:
        worker = SimpleWorker([queue], connection=connection)
        # RQ's stubs type death_penalty_class as type[UnixSignalDeathPenalty];
        # cast satisfies both older mypy (which flags the assignment) and newer
        # mypy 2.3+ (which flags unused type: ignore comments).
        worker.death_penalty_class = cast(type[UnixSignalDeathPenalty], _NoOpDeathPenalty)
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
