"""Background worker tasks for personalized question pre-generation.

Pre-generates personalized interview questions for a candidate ahead of need,
so a practice session doesn't have to block on LLM generation. Mirrors the
sync/async bridging pattern used in app/workers/tasks/feedback.py.
"""

from __future__ import annotations

import asyncio
import logging
from typing import cast
from uuid import UUID

from app.core.config import get_settings
from app.database.session import get_async_session_for_sync_context
from app.observability.cost_tracking import track_llm_failure

logger = logging.getLogger(__name__)


def generate_personalized_questions_job(user_id: str, job_role: str, count: int = 5) -> None:
    """Pre-generate personalized interview questions for a candidate.

    This is the main worker task enqueued to the 'question_generation' queue.

    Args:
        user_id: UUID string of the candidate to generate questions for
        job_role: Target job role to generate questions for
        count: Number of questions to pre-generate

    Note:
        This is a synchronous function that wraps async logic for RQ compatibility.
        Errors are logged but not re-raised to prevent automatic retries.
    """
    logger.info(f"Starting personalized question pre-generation for user {user_id[:8]}")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        from app.modules.questions.schemas import JobRole, QuestionRequest
        from app.modules.questions.service import get_questions

        async def _run() -> None:
            settings = get_settings()
            async with get_async_session_for_sync_context() as db:
                request = QuestionRequest(
                    job_role=cast(JobRole, job_role), count=count, personalize=True
                )
                await get_questions(db, UUID(user_id), request, settings)

        loop.run_until_complete(_run())
    except Exception as e:
        logger.error(
            "Personalized question pre-generation failed",
            extra={
                "user_id": user_id[:8],
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )

        # Track failure
        track_llm_failure(model="gpt-4o-mini", operation="question_generation")

        # Don't re-raise - we don't want the worker to retry automatically
    finally:
        loop.close()
