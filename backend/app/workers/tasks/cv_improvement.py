"""RQ worker task: generate CV improvement suggestions (Decision 3).

Runs on the existing QUEUE_FEEDBACK queue (reused, not a new queue) — same
convention as app/workers/tasks/document.py's sync-entrypoint-wraps-async pattern.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy import update as sa_update

import app.database.orm_registry  # noqa: F401  (registers all ORM models with SQLAlchemy first)
from app.core.config import get_settings
from app.database.session import SessionLocal, engine
from app.infrastructure.redis import close_redis
from app.modules.documents.models import CandidateDocument, CvFeedbackReport, DocumentJob
from app.services.feedback_generator import generate_cv_improvement

logger = logging.getLogger(__name__)


def generate_cv_improvement_job(document_id: str, job_id: str, target_role: str | None) -> None:
    """RQ entrypoint (sync)."""
    asyncio.run(_generate_cv_improvement_job(document_id, job_id, target_role))


async def _generate_cv_improvement_job(document_id: str, job_id: str, target_role: str | None) -> None:
    try:
        async with SessionLocal() as session:
            result = await session.execute(select(CandidateDocument).where(CandidateDocument.id == document_id))
            document = result.scalar_one_or_none()
            if not document or not document.raw_text:
                raise ValueError(f"Document {document_id} not found or has no extracted text")

            settings = get_settings()
            improvement, token_usage = await generate_cv_improvement(document.raw_text, target_role, settings)

            report = CvFeedbackReport(
                id=uuid4(),
                document_id=document.id,
                user_id=document.user_id,
                target_role=target_role,
                ats_score=improvement["ats_score"],
                strengths=improvement["strengths"],
                improvements=improvement["improvements"],
                rewritten_bullets=improvement["rewritten_bullets"],
                accepted_bullet_indices=[],
                created_at=datetime.now(UTC),
            )
            session.add(report)

            await session.execute(
                sa_update(DocumentJob)
                .where(DocumentJob.id == job_id)
                .values(status="completed", progress=100.0, result={"report_id": str(report.id)})
            )
            await session.commit()

            logger.info(
                "CV improvement generated",
                extra={
                    "document_id": document_id,
                    "user_id": str(document.user_id)[:8],
                    "ats_score": improvement["ats_score"],
                    "input_tokens": token_usage["input_tokens"],
                },
            )

    except Exception as exc:
        logger.error("CV improvement generation failed", exc_info=True, extra={"document_id": document_id})
        try:
            async with SessionLocal() as recovery_session:
                await recovery_session.execute(
                    sa_update(DocumentJob).where(DocumentJob.id == job_id).values(status="failed", error=str(exc))
                )
                await recovery_session.commit()
        except Exception:
            logger.error("Failed to mark cv_feedback job as failed", exc_info=True)
        raise
    finally:
        await close_redis()
        await engine.dispose()
