"""Orchestrates question selection (existing question_selector.py) with
on-demand, résumé-personalized generation (existing question_generator.py)
when the shared bank has too few matching rows.

Layer: modules/ (API-facing use case). Calls services/ only - does not touch
enrichers/pipeline.py, workers/, or compliance/, per RULE.md layer ownership.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ValidationAppError
from app.models import InterviewQuestion
from app.modules.documents.models import DOCUMENT_READY_STATUSES, CandidateDocument
from app.modules.questions.schemas import (
    QuestionCategory,
    QuestionDifficulty,
    QuestionItem,
    QuestionListResponse,
    QuestionRequest,
)
from app.observability.cost_tracking import track_llm_cost, track_llm_failure
from app.services.question_generator import CandidateContext, QuestionData, generate_questions
from app.services.question_selector import select_questions

logger = logging.getLogger(__name__)

MIN_BANK_RESULTS_BEFORE_GENERATING = 3


async def _personalized_generation_count_today(db: AsyncSession, user_id: UUID) -> int:
    """Count this user's personalized questions generated in the last 24h.

    Cost-control guard for QUESTION_GENERATION_DAILY_LIMIT_PER_USER (mirrors
    DAILY_COST_THRESHOLD_USD's intent, scoped to this one feature — see
    .env.example). A rolling 24h window (not calendar-day) since InterviewQuestion
    has no per-user request log, only the rows it already persists.
    """
    since = datetime.now(UTC) - timedelta(days=1)
    stmt = select(func.count()).where(
        InterviewQuestion.personalized_for_user_id == user_id,
        InterviewQuestion.created_at >= since,
    )
    return (await db.execute(stmt)).scalar_one()


def _context_from_document(document: CandidateDocument) -> CandidateContext | None:
    if not document.extracted_data:
        return None
    data = document.extracted_data
    return CandidateContext(
        skills=data.get("technical_skills", [])[:15],
        target_role=(data.get("desired_roles") or [None])[0],
        years_experience=data.get("years_experience"),
        recent_job_titles=[
            exp.get("title") for exp in (data.get("experience") or [])[:3] if exp.get("title")
        ],
    )


async def _load_candidate_context(
    db: AsyncSession,
    user_id: UUID,
    document_id: UUID | None = None,
) -> CandidateContext | None:
    """Read a processed CandidateDocument's extracted_data (§3 Decision 1).

    When ``document_id`` is set, that row must be owned by ``user_id`` and ready
    (``DOCUMENT_READY_STATUSES``); otherwise raises ``ValidationAppError``.
    When unset, returns the most recent ready document, or None if none exist —
    callers must treat missing docs as "personalize silently degrades", never as
    an error, unless an explicit id was requested.
    """
    if document_id is not None:
        stmt = select(CandidateDocument).where(
            CandidateDocument.id == document_id,
            CandidateDocument.user_id == user_id,
        )
        result = await db.execute(stmt)
        document = result.scalar_one_or_none()
        if document is None:
            raise ValidationAppError("Document not found")
        if document.processing_status not in DOCUMENT_READY_STATUSES:
            raise ValidationAppError("Document is not ready for personalization")
        return _context_from_document(document)

    stmt = (
        select(CandidateDocument)
        .where(
            CandidateDocument.user_id == user_id,
            CandidateDocument.processing_status.in_(DOCUMENT_READY_STATUSES),
        )
        .order_by(CandidateDocument.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    document = result.scalar_one_or_none()
    if document is None:
        return None
    return _context_from_document(document)


async def get_questions(
    db: AsyncSession,
    user_id: UUID,
    request: QuestionRequest,
    settings: Settings,
) -> QuestionListResponse:
    """Return `request.count` questions, personalized if requested and possible."""
    candidate_context: CandidateContext | None = None
    if request.personalize:
        candidate_context = await _load_candidate_context(
            db, user_id, document_id=request.document_id
        )

    bank_results = await select_questions(
        session=db,
        user_id=user_id,
        job_role=request.job_role,
        difficulty=request.difficulty,
        category=request.category,
        count=request.count,
    )

    items = [
        QuestionItem(
            id=UUID(cast(str, q["id"])),
            question_text=cast(str, q["question_text"]),
            category=cast(QuestionCategory, q["category"]),
            difficulty=cast(QuestionDifficulty, q["difficulty"]),
            job_roles=cast("list[str]", q["job_roles"]),
            technologies=cast("list[str]", q["technologies"]),
            is_personalized=False,
        )
        for q in bank_results
    ]

    shortfall = request.count - len(items)
    if shortfall <= 0:
        return QuestionListResponse(questions=items, source="question_bank")

    if not settings.openai_api_key.strip():
        logger.warning(
            "Question bank shortfall but no OPENAI_API_KEY configured; returning bank results only",
            extra={"user_id": str(user_id)[:8], "shortfall": shortfall},
        )
        return QuestionListResponse(questions=items, source="question_bank")

    if candidate_context is not None:
        generated_today = await _personalized_generation_count_today(db, user_id)
        if generated_today >= settings.question_generation_daily_limit_per_user:
            logger.info(
                "Personalized question generation daily limit reached; "
                "generating from the shared (non-personalized) pool instead",
                extra={
                    "user_id": str(user_id)[:8],
                    "generated_today": generated_today,
                    "limit": settings.question_generation_daily_limit_per_user,
                },
            )
            candidate_context = None

    # generate_questions accepts up to 15 per call (matches QuestionRequest.le).
    # Still batch defensively if a future caller asks for more than one LLM round-trip.
    had_bank = bool(bank_results)
    while len(items) < request.count:
        shortfall = request.count - len(items)
        batch_context = candidate_context
        if batch_context is not None:
            generated_today = await _personalized_generation_count_today(db, user_id)
            if generated_today >= settings.question_generation_daily_limit_per_user:
                batch_context = None
        try:
            generated, token_usage = await generate_questions(
                job_role=request.job_role,
                category=request.category or "technical",
                difficulty=request.difficulty or "medium",
                settings=settings,
                count=min(shortfall, 15),
                candidate_context=batch_context,
            )
        except Exception:
            logger.error(
                "On-demand question generation failed; returning results so far",
                exc_info=True,
                extra={"user_id": str(user_id)[:8]},
            )
            track_llm_failure(model="gpt-4o-mini", operation="question_generation")
            break
        if not generated:
            break
        persisted = await _persist_generated_questions(
            db, generated, personalized_for_user_id=user_id if batch_context else None
        )
        await track_llm_cost(
            model="gpt-4o-mini",
            input_tokens=token_usage["input_tokens"],
            output_tokens=token_usage["output_tokens"],
            operation="question_generation",
            user_id=str(user_id),
        )
        items.extend(
            QuestionItem(
                id=q.id,
                question_text=q.question_text,
                category=cast(QuestionCategory, q.question_category),
                difficulty=cast(QuestionDifficulty, q.difficulty),
                job_roles=q.job_roles,
                technologies=q.technologies,
                is_personalized=q.personalized_for_user_id is not None,
            )
            for q in persisted
        )

    if not had_bank and len(items) > 0:
        source: Literal["question_bank", "generated", "mixed"] = "generated"
    elif len(items) > len(bank_results):
        source = "mixed"
    else:
        source = "question_bank"
    return QuestionListResponse(questions=items[: request.count], source=source)


async def _persist_generated_questions(
    db: AsyncSession,
    generated: list[QuestionData],
    personalized_for_user_id: UUID | None,
) -> list[InterviewQuestion]:
    """Write freshly-generated questions into interview_questions so they are
    reusable and rotation-tracked exactly like hand-seeded ones (no parallel
    "generated questions" table — one bank, one selection path, per §4.6's
    "one source of truth" principle applied consistently).
    """
    rows = [
        InterviewQuestion(
            question_text=item["question_text"],
            question_category=item["category"],
            difficulty=item["difficulty"],
            job_roles=item["job_roles"],
            technologies=item["technologies"],
            sample_answer=item["sample_answer"],
            scoring_rubric=item["scoring_rubric"],
            source="ai_generated_personalized" if personalized_for_user_id else "ai_generated",
            personalized_for_user_id=personalized_for_user_id,
        )
        for item in generated
    ]
    db.add_all(rows)
    await db.commit()
    for row in rows:
        await db.refresh(row)
    return rows
