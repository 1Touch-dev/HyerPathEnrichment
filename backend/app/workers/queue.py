from redis import Redis
from rq import Queue

from app.core.config import get_settings
from app.domain.enums import RequestedTier

QUEUE_NAME = "enrichment"


def get_redis_connection() -> Redis:
    """Synchronous Redis connection for RQ (the async client is not compatible)."""
    return Redis.from_url(get_settings().redis_url)


def get_queue_name_for_tiers(requested_tiers: list[RequestedTier]) -> str:
    """Determine which queue to use based on requested tiers."""
    settings = get_settings()

    if settings.worker_queue_mode == "single":
        return "enrichment"

    # Per-tier routing: tier1 jobs go to tier1 queue, everything else to tier234
    if RequestedTier.tier1 in requested_tiers:
        return "tier1"
    return "tier234"


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


def enqueue_enrichment(job_id: str, requested_tiers: list[RequestedTier] | None = None) -> None:
    """Enqueue an enrichment job to the appropriate tier-based queue(s).

    In per_tier mode, this will enqueue to multiple queues if multiple tier groups are requested:
    - tier1 queue: for Tier 1 (browser-based enrichment)
    - tier234 queue: for Tiers 2, 3, 4 (API-based enrichment)

    This enables parallel execution across different tier groups.
    """
    from app.workers.jobs import run_enrichment_job

    # Default to all tiers if none specified (backward compatibility)
    tiers = requested_tiers if requested_tiers is not None else list(RequestedTier)
    settings = get_settings()
    connection = get_redis_connection()
    timeout_seconds = settings.rq_job_timeout_seconds

    if settings.worker_queue_mode == "single":
        # Single queue mode: all tiers go to one queue
        queue = Queue("enrichment", connection=connection)
        queue.enqueue(run_enrichment_job, job_id, job_timeout=timeout_seconds)
    else:
        # Per-tier mode: enqueue to multiple queues for parallel execution
        # Enqueue to tier1 queue if tier1 is requested
        if RequestedTier.tier1 in tiers:
            tier1_queue = Queue("tier1", connection=connection)
            tier1_queue.enqueue(run_enrichment_job, job_id, job_timeout=timeout_seconds)

        # Enqueue to tier234 queue if any of tier2/3/4 are requested
        tier234_tiers = {RequestedTier.tier2, RequestedTier.tier3, RequestedTier.tier4}
        if any(tier in tier234_tiers for tier in tiers):
            tier234_queue = Queue("tier234", connection=connection)
            tier234_queue.enqueue(run_enrichment_job, job_id, job_timeout=timeout_seconds)
