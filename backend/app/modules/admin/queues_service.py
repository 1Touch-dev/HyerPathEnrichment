"""Authorized, redacted RQ inspection with queue mutations disabled."""

from __future__ import annotations

from datetime import UTC, datetime

from rq import Queue, Worker
from rq.registry import FailedJobRegistry

from app.core.errors import AppError, NotFoundError
from app.modules.admin.schemas import FailedJobResponse, QueueSnapshotResponse
from app.observability.security_metrics import record_queue_event
from app.workers.queue import QUEUE_PRIORITIES, get_redis_connection

REDACTED_FAILURE_DETAIL = "Failure details redacted"


def _require_allowed_queue(queue_name: str) -> None:
    if queue_name not in QUEUE_PRIORITIES:
        raise NotFoundError("Queue not found")


def get_queues_overview() -> list[QueueSnapshotResponse]:
    record_queue_event("overview", "inspected")
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
    """Return failed-job metadata without exception payloads, arguments, or PII."""
    _require_allowed_queue(queue_name)
    record_queue_event("failed_jobs", "inspected")
    connection = get_redis_connection()
    queue = Queue(queue_name, connection=connection)
    registry = FailedJobRegistry(queue=queue)
    job_ids = registry.get_job_ids()[:limit]

    results = []
    for job_id in job_ids:
        job = queue.fetch_job(job_id)
        if job is None:
            continue
        record_queue_event("failed_jobs", "redacted")
        results.append(
            FailedJobResponse(
                job_id=job.id,
                queue_name=queue_name,
                func_name=job.func_name,
                enqueued_at=job.enqueued_at,
                failed_at=job.ended_at,
                exc_info=REDACTED_FAILURE_DETAIL,
            )
        )
    return results


def deny_retry(queue_name: str, job_id: str) -> None:
    """Fail closed before any Redis lookup or mutation.

    Retry stays unavailable until an explicit retry-safe function catalog and
    an approved durable cross-store contract exist.
    """
    del queue_name, job_id
    record_queue_event("retry", "denied")
    raise AppError(
        "QUEUE_ADMIN_READ_ONLY",
        "Queue administration is read-only; retry is unavailable",
        405,
    )
