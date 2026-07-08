import os

from rq import Queue, SimpleWorker, Worker
from rq.timeouts import BaseDeathPenalty

from app.workers.queue import QUEUE_NAME, get_redis_connection


class _NoOpDeathPenalty(BaseDeathPenalty):
    """Windows-safe timeout context: RQ's signal-based penalties don't work here."""

    def setup_death_penalty(self) -> None:
        pass

    def cancel_death_penalty(self) -> None:
        pass


def main() -> None:
    connection = get_redis_connection()
    queue = Queue(QUEUE_NAME, connection=connection)
    # RQ's default Worker forks (no os.fork on Windows) and uses SIGALRM
    # for job timeouts (also unavailable on Windows). SimpleWorker + no-op
    # death penalty keeps local dev working; Linux production keeps defaults.
    if hasattr(os, "fork"):
        worker = Worker([queue], connection=connection)
    else:
        worker = SimpleWorker([queue], connection=connection)
        worker.death_penalty_class = _NoOpDeathPenalty
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
