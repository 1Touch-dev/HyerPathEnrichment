"""RQ queue introspection + retry. Read/retry access to the EXISTING queues in
QUEUE_PRIORITIES only — never registers a new queue (Decision 9)."""

from __future__ import annotations

from datetime import UTC, datetime

from rq import Queue, Worker
from rq.registry import FailedJobRegistry

from app.modules.admin.schemas import FailedJobResponse, QueueSnapshotResponse
from app.workers.queue import QUEUE_PRIORITIES, get_redis_connection


def get_queues_overview() -> list[QueueSnapshotResponse]:
    connection = get_redis_connection()
    workers = Worker.all(connection=connection)
    snapshots = []

    for name, priority in QUEUE_PRIORITIES.items():
        queue = Queue(name, connection=connection)
        failed_registry = FailedJobRegistry(queue=queue)
        oldest_age = None
        job_ids = queue.job_ids
        if job_ids:
            oldest_job = queue.fetch_job(job_ids[0])
            if oldest_job and oldest_job.enqueued_at:
                oldest_age = (datetime.now(UTC) - oldest_job.enqueued_at).total_seconds()

        listening = sum(1 for w in workers if name in [q.name for q in w.queues])

        snapshots.append(
            QueueSnapshotResponse(
                name=name,
                priority=priority,
                queued_count=len(queue),
                failed_count=len(failed_registry),
                oldest_queued_age_seconds=oldest_age,
                workers_listening=listening,
            )
        )
    return snapshots


def list_failed_jobs(queue_name: str, limit: int = 50) -> list[FailedJobResponse]:
    connection = get_redis_connection()
    queue = Queue(queue_name, connection=connection)
    registry = FailedJobRegistry(queue=queue)
    job_ids = registry.get_job_ids()[:limit]

    results = []
    for job_id in job_ids:
        job = queue.fetch_job(job_id)
        if job is None:
            continue
        results.append(
            FailedJobResponse(
                job_id=job.id,
                queue_name=queue_name,
                func_name=job.func_name,
                enqueued_at=job.enqueued_at,
                failed_at=job.ended_at,
                exc_info=job.exc_info,
            )
        )
    return results


def retry_failed_job(queue_name: str, job_id: str) -> bool:
    connection = get_redis_connection()
    queue = Queue(queue_name, connection=connection)
    registry = FailedJobRegistry(queue=queue)
    if job_id not in registry.get_job_ids():
        return False
    registry.requeue(job_id)
    return True
