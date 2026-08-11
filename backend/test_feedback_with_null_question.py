#!/usr/bin/env python3
"""Test feedback generation with null question_id.

This script:
1. Creates a test user and practice session
2. Creates a question attempt with question_id=None
3. Enqueues a feedback generation job
4. Monitors the job execution
"""

import logging
import sys
from uuid import uuid4

from redis import Redis
from rq import Queue
from sqlalchemy import select

from app.auth.models import User
from app.core.config import get_settings
from app.database.session import SyncSessionLocal
from app.modules.sessions.models import PracticeSession, QuestionAttempt

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_test_attempt() -> str:
    """Create a test attempt with null question_id.

    Returns:
        UUID string of the created attempt
    """
    db = SyncSessionLocal()
    try:
        # Find or create test user
        stmt = select(User).where(User.email == "test-feedback@example.com")
        user = db.scalar(stmt)

        if not user:
            logger.info("Creating test user...")
            user = User(
                id=uuid4(),
                email="test-feedback@example.com",
                first_name="Feedback",
                last_name="Test User",
                hashed_password="test-password-hash",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"Created user: {user.id}")
        else:
            logger.info(f"Using existing user: {user.id}")

        # Create practice session
        logger.info("Creating practice session...")
        session = PracticeSession(
            id=uuid4(),
            user_id=user.id,
            session_type="practice",
            status="active",
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        logger.info(f"Created session: {session.id}")

        # Create attempt with null question_id (the issue we're fixing)
        logger.info("Creating question attempt with null question_id...")
        attempt = QuestionAttempt(
            id=uuid4(),
            session_id=session.id,
            user_id=user.id,
            question_id=None,  # This is what was causing the 400 error
            response_type="text",
            text_response="""
I would approach this problem by first understanding the requirements thoroughly.
Then I would break down the problem into smaller, manageable components.
I believe in test-driven development, so I would write tests first to ensure
the solution meets all the requirements. Finally, I would implement the solution
iteratively, refactoring as needed to maintain code quality.
""".strip(),
            time_taken_seconds=180,
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)
        logger.info(f"Created attempt: {attempt.id}")

        return str(attempt.id)

    except Exception as e:
        logger.error(f"Failed to create test attempt: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


def enqueue_feedback_job(attempt_id: str) -> None:
    """Enqueue feedback generation job.

    Args:
        attempt_id: UUID string of the attempt
    """
    settings = get_settings()
    redis_conn = Redis.from_url(settings.redis_url)
    feedback_queue = Queue("feedback", connection=redis_conn)

    logger.info(f"Enqueuing feedback job for attempt {attempt_id}...")
    job = feedback_queue.enqueue(
        "app.workers.tasks.feedback.generate_feedback_job",
        attempt_id,
        job_timeout="5m",
        result_ttl=3600,
    )
    logger.info(f"Job enqueued: {job.id}")
    logger.info(f"Queue length: {len(feedback_queue)}")

    # Monitor job
    logger.info("\nMonitoring job status...")
    import time

    for i in range(60):  # Monitor for up to 60 seconds
        job.refresh()
        logger.info(f"[{i + 1}s] Job status: {job.get_status()}")

        if job.is_finished:
            logger.info("✅ Job completed successfully!")
            break
        elif job.is_failed:
            logger.error(f"❌ Job failed: {job.exc_info}")
            break

        time.sleep(1)

    # Check the attempt
    db = SyncSessionLocal()
    try:
        from uuid import UUID

        stmt = select(QuestionAttempt).where(QuestionAttempt.id == UUID(attempt_id))
        attempt = db.scalar(stmt)

        if attempt:
            logger.info("\n=== Attempt Results ===")
            logger.info(f"AI Score: {attempt.ai_score}")
            logger.info(f"Score Breakdown: {attempt.score_breakdown}")
            logger.info(f"AI Feedback: {attempt.ai_feedback[:200]}...")
            if attempt.attempt_metadata:
                logger.info(f"Strengths: {attempt.attempt_metadata.get('strengths')}")
                logger.info(f"Improvements: {attempt.attempt_metadata.get('improvements')}")
    finally:
        db.close()


def main():
    """Main test flow."""
    try:
        logger.info("=== Starting Feedback Test with Null Question ID ===\n")

        # Create test data
        attempt_id = create_test_attempt()

        # Enqueue job
        enqueue_feedback_job(attempt_id)

        logger.info("\n✅ Test completed!")
        logger.info(f"Attempt ID: {attempt_id}")
        logger.info("\nYou can also check the worker logs with:")
        logger.info("  docker compose --env-file ../.env.production logs worker -f")

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
