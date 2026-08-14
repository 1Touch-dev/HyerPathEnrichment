"""Background worker tasks for interview feedback generation.

Processes feedback generation jobs asynchronously using RQ workers.
Integrates with cost tracking and error handling.
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import SyncSessionLocal
from app.models import InterviewQuestion
from app.modules.sessions.models import QuestionAttempt
from app.observability.cost_tracking import track_llm_cost, track_llm_failure
from app.services.feedback_generator import generate_interview_feedback

logger = logging.getLogger(__name__)


def _generate_feedback_sync(attempt_id: str, db: Session) -> None:
    """Internal sync logic for feedback generation in RQ worker.

    Args:
        attempt_id: UUID string of the QuestionAttempt
        db: Sync database session

    Raises:
        ValueError: If attempt not found or invalid
    """
    settings = get_settings()
    attempt_uuid = UUID(attempt_id)

    # Fetch QuestionAttempt
    stmt = select(QuestionAttempt).where(QuestionAttempt.id == attempt_uuid)
    attempt = db.scalar(stmt)

    if not attempt:
        logger.error(f"QuestionAttempt not found: {attempt_id}")
        raise ValueError(f"Attempt not found: {attempt_id}")

    # Validate required fields
    if not attempt.text_response:
        logger.warning(f"No text response for attempt {attempt_id}, skipping feedback")
        return

    # Look up question text via the real FK (question_attempts.question_id ->
    # interview_questions.id). If question_id is null, pass None to enable
    # general evaluation mode.
    question_text: str | None = None
    if attempt.question_id is not None:
        question_stmt = select(InterviewQuestion.question_text).where(
            InterviewQuestion.id == attempt.question_id
        )
        question_text = db.scalar(question_stmt)

    # Generate feedback (run async function in event loop)
    logger.info(f"Calling feedback service for attempt {attempt_id}")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        feedback, token_usage = loop.run_until_complete(
            generate_interview_feedback(
                question=question_text,
                answer=attempt.text_response,
                settings=settings,
            )
        )
    finally:
        loop.close()

    # Update attempt with feedback
    attempt.ai_score = float(feedback["overall_score"])
    attempt.score_breakdown = feedback["dimension_scores"]
    attempt.ai_feedback = feedback["detailed_feedback"]

    # Add strengths and improvements to attempt_metadata.
    # Reassign (not in-place mutate) so SQLAlchemy's change tracking detects
    # the update on the JSON column and includes it in the commit.
    updated_metadata = dict(attempt.attempt_metadata or {})
    updated_metadata["strengths"] = feedback["strengths"]
    updated_metadata["improvements"] = feedback["improvements"]
    attempt.attempt_metadata = updated_metadata

    db.commit()

    logger.info(
        f"Feedback generated successfully for attempt {attempt_id}",
        extra={
            "attempt_id": attempt_id,
            "overall_score": feedback["overall_score"],
            "input_tokens": token_usage["input_tokens"],
            "output_tokens": token_usage["output_tokens"],
        },
    )

    # Track LLM cost (run async function in new loop)
    loop2 = asyncio.new_event_loop()
    asyncio.set_event_loop(loop2)
    try:
        loop2.run_until_complete(
            track_llm_cost(
                model="gpt-4o-mini",
                input_tokens=token_usage["input_tokens"],
                output_tokens=token_usage["output_tokens"],
                operation="feedback",
                user_id=str(attempt.user_id),
            )
        )
    finally:
        loop2.close()


def generate_feedback_job(attempt_id: str) -> None:
    """Generate AI feedback for a question attempt.

    This is the main worker task enqueued to the 'feedback' queue.
    Fetches the attempt, generates feedback, updates the database, and tracks costs.

    Args:
        attempt_id: UUID string of the QuestionAttempt

    Note:
        This is a synchronous function that wraps async logic for RQ compatibility.
        Errors are logged but not re-raised to prevent automatic retries.
    """
    logger.info(f"Starting feedback generation for attempt {attempt_id}")

    db: Session | None = None
    try:
        # Parse UUID - will raise ValueError if invalid
        UUID(attempt_id)

        # Get database session
        db = SyncSessionLocal()

        # Run sync logic
        _generate_feedback_sync(attempt_id, db)

    except Exception as e:
        logger.error(
            f"Feedback generation failed for attempt {attempt_id}",
            extra={
                "attempt_id": attempt_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )

        # Track failure
        track_llm_failure(model="gpt-4o-mini", operation="feedback")

        # Try to mark attempt with error
        if db:
            try:
                stmt = select(QuestionAttempt).where(QuestionAttempt.id == UUID(attempt_id))
                attempt = db.scalar(stmt)
                if attempt:
                    updated_metadata = dict(attempt.attempt_metadata or {})
                    updated_metadata["feedback_error"] = str(e)
                    attempt.attempt_metadata = updated_metadata
                    db.commit()
            except Exception as update_error:
                logger.error(
                    "Failed to update attempt with error status",
                    extra={"error": str(update_error)},
                )
                db.rollback()

        # Don't re-raise - we don't want the worker to retry automatically
        # The error is logged and stored in metadata

    finally:
        if db:
            db.close()
