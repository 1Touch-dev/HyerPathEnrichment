"""Orchestrates JD-tailored interview question generation (Module 4, Module E).

Always bypasses the shared question bank (see phase2_module4 plan §9.2) — every
call generates fresh via `generate_jd_tailored_questions`, since bank questions
are role/category/difficulty-keyed and never JD-specific; sharing them across
users of different companies/JDs would be actively wrong.

Layer: modules/ (API-facing use case). Calls services/ only - does not touch
enrichers/pipeline.py, workers/, or compliance/, per RULE.md layer ownership.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import NotFoundError, RateLimitError, ValidationAppError
from app.modules.job_matching import repository as job_matching_repository
from app.modules.jd_practice.schemas import (
    JdPracticeQuestionItem,
    JdPracticeRequest,
    JdPracticeResponse,
)
from app.modules.questions.service import _load_candidate_context
from app.modules.sessions.models import PracticeSession
from app.observability.cost_tracking import track_llm_cost
from app.observability.jd_practice_metrics import (
    jd_practice_daily_limit_hit_total,
    jd_practice_questions_generated_total,
)
from app.services.question_generator import JobContext, QuestionData, generate_jd_tailored_questions


async def _jd_generation_count_today(db: AsyncSession, user_id: UUID) -> int:
    """Count this user's JD-tailored practice sessions created in the last 24h.

    Mirrors questions/service.py's `_personalized_generation_count_today` shape,
    but counts `PracticeSession` rows with `session_type="jd_tailored"` created
    in the last 24h, since JD-tailored questions aren't persisted to
    `interview_questions` with a `personalized_for_user_id` flag the way Module
    3's bank-reuse-eligible generated questions are — JD questions are NOT
    written back to the shared bank at all (they're inherently non-reusable
    across users/JDs); they live only in `session_metadata` / are returned
    directly to the caller, never persisted as `InterviewQuestion` rows. This
    is a SEPARATE counter from `_personalized_generation_count_today` — hitting
    one daily limit must never block the other.
    """
    since = datetime.now(UTC) - timedelta(days=1)
    stmt = select(func.count()).where(
        PracticeSession.user_id == user_id,
        PracticeSession.session_type == "jd_tailored",
        PracticeSession.started_at >= since,
    )
    return (await db.execute(stmt)).scalar_one()


async def get_jd_tailored_questions(
    db: AsyncSession,
    user_id: UUID,
    request: JdPracticeRequest,
    settings: Settings,
) -> JdPracticeResponse:
    """Always bypasses the shared bank (§9.2) — every call generates fresh via
    generate_jd_tailored_questions. Daily-limit-guarded the same way
    questions/service.py guards personalized (résumé-only) generation, but
    against the SEPARATE jd_question_generation_daily_limit_per_user budget
    (§4), since this path is strictly more expensive per request (always
    generates, never serves from the bank) and deserves its own
    independently-tunable cap rather than competing with Module 3's
    résumé-personalization budget for the same limit.

    JD source is either a tracked ``job_match_id`` or a pasted ``job_description``
    (ADR 0018) — schema enforces XOR.
    """
    job_context: JobContext
    session_metadata: dict[str, str]
    response_match_id: str | None

    if request.job_match_id:
        match_row = await job_matching_repository.get_owned_match(
            db, UUID(request.job_match_id), user_id
        )
        if match_row is None:
            raise NotFoundError("Tracked job not found")
        match, posting = match_row
        if match.job_posting_id is None:
            # Module F: a manual job entry (job_posting_id is NULL, manual_job_entry_id
            # set instead — see JobMatch's ck_job_matches_exactly_one_source) has no
            # scraped description at all — there is nothing to tailor a question
            # against, so this is a distinct, expected case (by design), not a data
            # error. Rejected explicitly here, before ever touching `posting`, so it
            # never falls through to the `description_raw` check below (which would
            # be an AttributeError on `None.description_raw`) or silently falls back
            # to generic (non-JD-tailored) questions the candidate didn't ask for.
            raise ValidationAppError(
                "Manual job entries have no job description to practice against — "
                "this feature requires a scanned posting"
            )
        if posting is None or not posting.description_raw:
            raise ValidationAppError("This job posting has no description to practice against")

        job_context = JobContext(
            job_description=posting.description_raw,
            job_title=posting.title,
            company=posting.company,
        )
        session_metadata = {
            "job_match_id": str(match.id),
            "job_title": posting.title,
            "company": posting.company,
        }
        response_match_id = request.job_match_id
    else:
        assert request.job_description is not None  # schema XOR
        job_context = JobContext(
            job_description=request.job_description.strip(),
            job_title=request.job_title or "Role",
            company=request.company or "Company",
        )
        session_metadata = {
            "source": "pasted_jd",
            "job_title": job_context.job_title,
            "company": job_context.company,
        }
        response_match_id = None

    generated_today = await _jd_generation_count_today(db, user_id)
    if generated_today >= settings.jd_question_generation_daily_limit_per_user:
        jd_practice_daily_limit_hit_total.inc()
        raise RateLimitError("Daily JD-tailored practice question limit reached")

    candidate_context = await _load_candidate_context(db, user_id, document_id=request.document_id)

    generated: list[QuestionData] = []
    token_usage = {"input_tokens": 0, "output_tokens": 0}
    remaining = request.count
    while remaining > 0:
        batch, usage = await generate_jd_tailored_questions(
            job_context,
            request.category or "technical",
            request.difficulty or "medium",
            settings,
            count=min(remaining, 15),
            candidate_context=candidate_context,
        )
        if not batch:
            break
        generated.extend(batch)
        token_usage["input_tokens"] += usage["input_tokens"]
        token_usage["output_tokens"] += usage["output_tokens"]
        remaining -= len(batch)
    await track_llm_cost(
        model="gpt-4o-mini",
        input_tokens=token_usage["input_tokens"],
        output_tokens=token_usage["output_tokens"],
        operation="jd_question_generation",
        user_id=str(user_id),
    )
    jd_practice_questions_generated_total.inc(len(generated))

    session = PracticeSession(
        user_id=user_id,
        session_type="jd_tailored",
        status="in_progress",
        session_metadata=session_metadata,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    # Design decision (§9.4): JD-tailored questions get a fresh random uuid4()
    # for their id and are NEVER written to interview_questions — writing them
    # to the shared bank would pollute the shared pool with a question that's
    # only meaningful for one specific job posting at one specific company.
    return JdPracticeResponse(
        questions=[
            JdPracticeQuestionItem(
                id=uuid4(),
                question_text=q["question_text"],
                category=q["category"],
                difficulty=q["difficulty"],
                sample_answer=q["sample_answer"],
            )
            for q in generated
        ],
        job_match_id=response_match_id,
        practice_session_id=session.id,
    )
