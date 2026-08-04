import logging

from redis import Redis
from rq import Queue

from app.core.config import get_settings
from app.domain.enums import RequestedTier

# Phase 1 queues (existing)
QUEUE_NAME = "enrichment"
QUEUE_EMAIL = "email"
QUEUE_CLEANUP = "cleanup"

# Foundation Week 1 queues (document processing pipeline)
QUEUE_DOCUMENT = "document_processing"
QUEUE_EMBEDDING = "embedding_generation"
QUEUE_CV_EXTRACTION = "cv_extraction"

# Queue priorities (higher = processed first)
QUEUE_PRIORITIES = {
    QUEUE_EMAIL: 10,  # Highest (user-facing)
    QUEUE_CV_EXTRACTION: 8,  # High (user-facing)
    QUEUE_DOCUMENT: 5,  # Medium (async)
    QUEUE_EMBEDDING: 3,  # Low (batch)
    QUEUE_NAME: 2,  # Low (existing enrichment)
    QUEUE_CLEANUP: 1,  # Lowest (maintenance)
}

logger = logging.getLogger(__name__)


def get_redis_connection() -> Redis:
    """Synchronous Redis connection for RQ with proper timeouts to handle Redis under load."""
    return Redis.from_url(
        get_settings().redis_url,
        socket_connect_timeout=5,
        socket_timeout=10,
        socket_keepalive=True,
        socket_keepalive_options={},
        health_check_interval=30,
    )


def get_queue_name_for_tiers(requested_tiers: list[RequestedTier]) -> str:
    """Determine which queue to use based on requested tiers."""
    settings = get_settings()

    if settings.worker_queue_mode == "single":
        return "enrichment"

    # Per-tier routing: tier1 jobs go to tier1 queue, everything else to tier234
    if RequestedTier.tier1 in requested_tiers:
        return "tier1"
    return "tier234"


def should_split_into_children(requested_tiers: list[RequestedTier]) -> bool:
    """Check if job should be split into tier1 + tier234 children."""
    settings = get_settings()
    if settings.worker_queue_mode != "per_tier":
        return False

    has_tier1 = RequestedTier.tier1 in requested_tiers
    has_tier234 = any(
        t in {RequestedTier.tier2, RequestedTier.tier3, RequestedTier.tier4}
        for t in requested_tiers
    )

    return has_tier1 and has_tier234


def get_queue() -> Queue:
    return Queue(QUEUE_NAME, connection=get_redis_connection())


def get_worker_queue() -> Queue:
    """Get the queue this worker should listen to."""
    settings = get_settings()

    if settings.worker_queue_mode == "single":
        queue_name = "enrichment"
    else:
        # In per_tier mode, worker must specify which queue to listen to
        if not settings.worker_target_queue:
            raise ValueError("WORKER_TARGET_QUEUE required when WORKER_QUEUE_MODE=per_tier")
        queue_name = settings.worker_target_queue

    return Queue(queue_name, connection=get_redis_connection())


def enqueue_enrichment(
    job_id: str,
    requested_tiers: list[RequestedTier] | None = None,
    *,
    is_child_job: bool = False,
) -> None:
    """Enqueue an enrichment job to the appropriate tier-based queue(s).

    In per_tier mode with multiple tier groups:
    - If is_child_job=True: enqueue directly to assigned queue (child jobs)
    - If is_child_job=False: parent job, don't enqueue (children are enqueued separately)

    This enables parallel execution across different tier groups.

    Raises: Exception on enqueue failure (connection errors, Redis errors, etc.)
    """
    from app.workers.jobs import run_enrichment_job

    # Default to all tiers if none specified (backward compatibility)
    tiers = requested_tiers if requested_tiers is not None else list(RequestedTier)
    settings = get_settings()
    connection = get_redis_connection()
    timeout_seconds = settings.rq_job_timeout_seconds

    try:
        if settings.worker_queue_mode == "single":
            # Single queue mode: all tiers go to one queue
            queue = Queue("enrichment", connection=connection)
            queue.enqueue(run_enrichment_job, job_id, job_timeout=timeout_seconds)
            logger.info(f"Enqueued job {job_id} to queue: enrichment")
        else:
            # Per-tier mode
            if is_child_job:
                # Child job: enqueue to its assigned tier queue
                queue_name = get_queue_name_for_tiers(tiers)
                queue = Queue(queue_name, connection=connection)
                queue.enqueue(run_enrichment_job, job_id, job_timeout=timeout_seconds)
                logger.info(f"Enqueued child job {job_id} to queue: {queue_name}")
            else:
                # Parent job or simple job
                # If this would be split into children, don't enqueue here
                # (children are enqueued separately in service layer)
                if not should_split_into_children(tiers):
                    # Simple job with single tier group - enqueue normally
                    queue_name = get_queue_name_for_tiers(tiers)
                    queue = Queue(queue_name, connection=connection)
                    queue.enqueue(run_enrichment_job, job_id, job_timeout=timeout_seconds)
                    logger.info(f"Enqueued job {job_id} to queue: {queue_name}")
    except Exception as e:
        logger.error(
            f"Failed to enqueue job {job_id}",
            extra={
                "job_id": job_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "is_child_job": is_child_job,
                "tiers": [t.value if isinstance(t, RequestedTier) else t for t in tiers],
            },
            exc_info=True,
        )
        raise
