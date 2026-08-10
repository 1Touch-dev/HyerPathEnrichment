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

# Foundation Week 2 queues (interview practice features)
QUEUE_FEEDBACK = "feedback"
QUEUE_AUDIO_CLEANUP = "audio_cleanup"

# Module 1: AI Job Matching & Notifications
QUEUE_JOB_MATCHING = "job_matching"

# Queue priorities (higher = processed first)
QUEUE_PRIORITIES = {
    QUEUE_EMAIL: 10,  # Highest (user-facing)
    QUEUE_CV_EXTRACTION: 8,  # High (user-facing)
    QUEUE_FEEDBACK: 7,  # High (user-facing feedback)
    QUEUE_JOB_MATCHING: 6,  # Between feedback (7) and document (5) — user-facing but async
    QUEUE_DOCUMENT: 5,  # Medium (async)
    QUEUE_EMBEDDING: 3,  # Low (batch)
    QUEUE_NAME: 2,  # Low (existing enrichment)
    QUEUE_CLEANUP: 1,  # Lowest (maintenance)
    QUEUE_AUDIO_CLEANUP: 1,  # Lowest (maintenance)
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
        retry_on_timeout=True,
        retry_on_error=[ConnectionError, TimeoutError],
        max_connections=50,
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


def enqueue_feedback(attempt_id: str) -> None:
    """Enqueue a feedback generation job.

    Args:
        attempt_id: UUID string of the QuestionAttempt

    Raises:
        Exception: On enqueue failure
    """
    from app.workers.tasks.feedback import generate_feedback_job

    connection = get_redis_connection()
    timeout_seconds = 60  # Feedback generation should be fast

    try:
        queue = Queue(QUEUE_FEEDBACK, connection=connection)
        queue.enqueue(generate_feedback_job, attempt_id, job_timeout=timeout_seconds)
        logger.info(f"Enqueued feedback job for attempt: {attempt_id}")
    except Exception as e:
        logger.error(
            f"Failed to enqueue feedback job for attempt {attempt_id}",
            extra={
                "attempt_id": attempt_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        raise


def enqueue_job_matching_scan(user_id: str) -> None:
    """Enqueue a job-matching scan for a single candidate.

    Args:
        user_id: UUID string of the candidate to scan

    Raises:
        Exception: On enqueue failure
    """
    from app.workers.tasks.job_matching import scan_jobs_for_candidate

    connection = get_redis_connection()
    try:
        queue = Queue(QUEUE_JOB_MATCHING, connection=connection)
        queue.enqueue(scan_jobs_for_candidate, user_id, job_timeout=120)
        logger.info(f"Enqueued job-matching scan for user: {user_id[:8]}")
    except Exception as e:
        logger.error(
            f"Failed to enqueue job-matching scan for user {user_id[:8]}",
            extra={"error": str(e), "error_type": type(e).__name__},
            exc_info=True,
        )
        raise


def enqueue_email(
    template: str, recipient: str, context: dict[str, object], subject: str | None = None
) -> None:
    """Enqueue a templated email send. Thin wrapper matching enqueue_feedback()'s shape."""
    from app.workers.tasks.email_tasks import send_email_task

    connection = get_redis_connection()
    try:
        queue = Queue(QUEUE_EMAIL, connection=connection)
        queue.enqueue(send_email_task, template, recipient, context, subject, job_timeout=30)
        logger.info(f"Enqueued email: {template} to {recipient[:3]}***")
    except Exception as e:
        logger.error(f"Failed to enqueue email: {template}", extra={"error": str(e)}, exc_info=True)
        raise


def register_scheduled_jobs() -> None:
    """Register scheduled cron jobs with RQ Scheduler.

    Note:
        This should be called once on scheduler startup.
        Requires RQ Scheduler to be running separately.
    """
    try:
        from rq_scheduler import Scheduler

        from app.workers.tasks.audio_cleanup import cleanup_expired_audio

        connection = get_redis_connection()
        scheduler = Scheduler(connection=connection)

        # Schedule audio cleanup daily at 2 AM UTC
        scheduler.cron(
            "0 2 * * *",  # Cron expression: minute hour day month weekday
            func=cleanup_expired_audio,
            queue_name=QUEUE_AUDIO_CLEANUP,
            id="audio_cleanup_daily",
            timeout=3600,  # 1 hour timeout for large batches
        )

        from app.workers.tasks.job_matching import fan_out_daily_scans

        scheduler.cron(
            "0 6 * * *",  # 06:00 UTC daily — before audio_cleanup's 02:00 slot to avoid contention
            func=fan_out_daily_scans,
            queue_name=QUEUE_JOB_MATCHING,
            id="job_matching_fan_out_daily",
            timeout=600,  # 10 minutes to page through and enqueue all candidates
        )

        logger.info(
            "Registered scheduled jobs",
            extra={"jobs": ["audio_cleanup_daily", "job_matching_fan_out_daily"]},
        )

    except ImportError:
        logger.warning(
            "rq-scheduler not installed, scheduled jobs will not run. "
            "Install with: pip install rq-scheduler"
        )
    except Exception as exc:
        logger.error(
            "Failed to register scheduled jobs",
            exc_info=True,
            extra={"error": str(exc)},
        )
