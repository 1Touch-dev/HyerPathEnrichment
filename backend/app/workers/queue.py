import logging
from datetime import UTC, datetime

from redis import Redis
from rq import Queue

from app.core.config import get_settings
from app.core.logging import get_request_id, scrub_identifier
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

# Phase 2, Module 3 (interview practice — personalized question pre-generation)
QUEUE_QUESTION_GENERATION = "question_generation"

# Module 1: AI Job Matching & Notifications
QUEUE_JOB_MATCHING = "job_matching"

# Module 2: Tinder-Style Job Board + CV Management (outreach drafting, §8.15)
QUEUE_OUTREACH = "outreach_generation"

# Machine-2/06: LinkedIn send batch processing (rate-limit/queue skeleton only —
# see app/workers/tasks/linkedin_send_batch.py's module docstring for the explicit
# scope cut on the actual automated-click mechanism).
QUEUE_LINKEDIN_SEND_BATCH = "linkedin_send_batch"

# Module 4, Module D: interview scheduling reminders
QUEUE_INTERVIEW_REMINDERS = "interview_reminders"

# Queue priorities (higher = processed first)
QUEUE_PRIORITIES = {
    QUEUE_EMAIL: 10,  # Highest (user-facing)
    QUEUE_CV_EXTRACTION: 8,  # High (user-facing)
    QUEUE_FEEDBACK: 7,  # High (user-facing feedback)
    QUEUE_INTERVIEW_REMINDERS: 7,  # NEW — same tier as QUEUE_FEEDBACK: user-facing, time-sensitive
    QUEUE_JOB_MATCHING: 6,  # Between feedback (7) and document (5) — user-facing but async
    QUEUE_OUTREACH: 6,  # NEW — user-facing but not time-critical; below feedback, above document/embedding
    QUEUE_DOCUMENT: 5,  # Medium (async)
    QUEUE_QUESTION_GENERATION: 4,  # Below feedback: not user-blocking, above batch embedding
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


def _request_context_meta() -> dict[str, str]:
    request_id = get_request_id()
    return {"request_id": scrub_identifier(request_id)} if request_id else {}


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
    request_meta = _request_context_meta()

    try:
        if settings.worker_queue_mode == "single":
            # Single queue mode: all tiers go to one queue
            queue = Queue("enrichment", connection=connection)
            queue.enqueue(
                run_enrichment_job,
                job_id,
                job_timeout=timeout_seconds,
                meta=request_meta,
            )
            logger.info(f"Enqueued job {job_id} to queue: enrichment")
        else:
            # Per-tier mode
            if is_child_job:
                # Child job: enqueue to its assigned tier queue
                queue_name = get_queue_name_for_tiers(tiers)
                queue = Queue(queue_name, connection=connection)
                queue.enqueue(
                    run_enrichment_job,
                    job_id,
                    job_timeout=timeout_seconds,
                    meta=request_meta,
                )
                logger.info(f"Enqueued child job {job_id} to queue: {queue_name}")
            else:
                # Parent job or simple job
                # If this would be split into children, don't enqueue here
                # (children are enqueued separately in service layer)
                if not should_split_into_children(tiers):
                    # Simple job with single tier group - enqueue normally
                    queue_name = get_queue_name_for_tiers(tiers)
                    queue = Queue(queue_name, connection=connection)
                    queue.enqueue(
                        run_enrichment_job,
                        job_id,
                        job_timeout=timeout_seconds,
                        meta=request_meta,
                    )
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


def enqueue_question_generation(user_id: str, job_role: str, count: int = 5) -> None:
    """Enqueue personalized question pre-generation. Fire-and-forget: failures are
    logged and cost-tracked inside the task itself, never raised back to a request
    path that has no reason to block on this.

    Args:
        user_id: UUID string of the candidate to generate questions for
        job_role: Target job role to generate questions for
        count: Number of questions to pre-generate

    Raises:
        Exception: On enqueue failure
    """
    from app.workers.tasks.question_generation import generate_personalized_questions_job

    connection = get_redis_connection()

    try:
        queue = Queue(QUEUE_QUESTION_GENERATION, connection=connection)
        queue.enqueue(
            generate_personalized_questions_job, user_id, job_role, count, job_timeout=120
        )
        logger.info(f"Enqueued question generation job for user: {user_id[:8]}")
    except Exception as e:
        logger.error(
            "Failed to enqueue question generation job",
            extra={
                "user_id": user_id[:8],
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


def enqueue_interview_reminder(interview_schedule_id: str, send_at: datetime) -> None:
    """Enqueue a one-off interview reminder at `send_at`, mirroring
    `fan_out_daily_scans`'s existing use of `Scheduler.enqueue_at` for staggered
    per-candidate jobs. Per §8.6: if `send_at` is already in the past (interview
    scheduled with less than `interview_reminder_hours_before` notice), the
    reminder enqueues immediately instead of being skipped — a same-day interview
    still deserves a reminder, just sent right away rather than not at all.

    The RQ job's id is deterministically derived from `interview_schedule_id` so
    `cancel_interview_reminder` below can look it up without needing to persist
    a separate RQ job id anywhere.
    """
    from rq_scheduler import Scheduler

    from app.workers.tasks.interview_reminders import send_interview_reminder_job

    connection = get_redis_connection()
    job_id = f"interview-reminder-{interview_schedule_id}"

    try:
        if send_at <= datetime.now(UTC):
            queue = Queue(QUEUE_INTERVIEW_REMINDERS, connection=connection)
            queue.enqueue(
                send_interview_reminder_job,
                interview_schedule_id,
                job_id=job_id,
                job_timeout=60,
            )
            logger.info(
                f"Enqueued interview reminder immediately for schedule: {interview_schedule_id}"
            )
            return

        scheduler = Scheduler(queue_name=QUEUE_INTERVIEW_REMINDERS, connection=connection)
        scheduler.enqueue_at(
            send_at,
            send_interview_reminder_job,
            interview_schedule_id,
            job_id=job_id,
            timeout=60,
        )
        logger.info(
            f"Enqueued interview reminder for schedule: {interview_schedule_id} at {send_at}"
        )
    except Exception as e:
        logger.error(
            f"Failed to enqueue interview reminder for schedule {interview_schedule_id}",
            extra={"error": str(e), "error_type": type(e).__name__},
            exc_info=True,
        )
        raise


def cancel_interview_reminder(schedule_id: str) -> None:
    """Best-effort cancellation of a pending interview-reminder job — wraps
    `rq_scheduler.Scheduler.cancel` and swallows `rq.exceptions.NoSuchJobError`
    (the job already fired, or never existed — both are fine, cancellation is
    best-effort, same idempotent-cancel pattern as job_matching's existing
    scan-cancellation path).
    """
    from rq.exceptions import NoSuchJobError
    from rq_scheduler import Scheduler

    connection = get_redis_connection()
    job_id = f"interview-reminder-{schedule_id}"

    try:
        scheduler = Scheduler(queue_name=QUEUE_INTERVIEW_REMINDERS, connection=connection)
        scheduler.cancel(job_id)
        logger.info(f"Cancelled interview reminder for schedule: {schedule_id}")
    except NoSuchJobError:
        logger.warning(
            "Interview reminder job already fired or never existed — nothing to cancel",
            extra={"schedule_id": schedule_id},
        )
    except Exception as e:
        logger.warning(
            f"Failed to cancel interview reminder for schedule {schedule_id}",
            extra={"error": str(e), "error_type": type(e).__name__},
        )


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
            get_settings().job_matching_scan_cron,  # default "0 6 * * *", configurable via JOB_MATCHING_SCAN_CRON
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
