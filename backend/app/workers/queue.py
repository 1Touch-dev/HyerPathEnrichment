from redis import Redis
from rq import Queue

from app.config import get_settings

QUEUE_NAME = "enrichment"


def get_redis_connection() -> Redis:
    """Synchronous Redis connection for RQ (the async client is not compatible)."""
    return Redis.from_url(get_settings().redis_url)


def get_queue() -> Queue:
    return Queue(QUEUE_NAME, connection=get_redis_connection())


def enqueue_enrichment(job_id: str) -> None:
    """Enqueue an enrichment job for the worker process to execute."""
    from app.workers.jobs import run_enrichment_job

    get_queue().enqueue(run_enrichment_job, job_id)
