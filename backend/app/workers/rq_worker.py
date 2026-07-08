import asyncio
import os

from rq import Queue, SimpleWorker, Worker
from rq.timeouts import BaseDeathPenalty

from app.storage.db import engine, init_db
from app.workers.queue import QUEUE_NAME, get_redis_connection


async def _init_db_once() -> None:
    # Dispose afterwards: pooled connections are bound to this startup event
    # loop and would break the per-job asyncio.run loops in jobs.py.
    try:
        await init_db()
    finally:
        await engine.dispose()


class _NoOpDeathPenalty(BaseDeathPenalty):
    """Windows-safe timeout context: RQ's signal-based penalties don't work here."""

    def setup_death_penalty(self) -> None:
        pass

    def cancel_death_penalty(self) -> None:
        pass


def main() -> None:
    # Ensure tables exist before the first job runs — the worker must not
    # depend on the API having started first (shared Postgres in Docker).
    asyncio.run(_init_db_once())
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
