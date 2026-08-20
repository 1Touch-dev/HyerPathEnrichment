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
from app.services.question_generator import JobContext, generate_jd_tailored_questions


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
    """
    match_row = await job_matching_repository.get_owned_match(
        db, UUID(request.job_match_id), user_id
    )
    if match_row is None:
        raise NotFoundError("Tracked job not found")
    match, posting = match_row
    if posting is None:
        # TODO(Module F): once Module F (manual job entries) lands, this must
        # ALSO explicitly reject manual-entry job_match_ids with a clear error
        # message distinguishing "manually-added, no JD to tailor against"
        # from other failure modes (§13.3 checklist item 3) — not implemented
        # yet because Module F doesn't exist on this branch. Do not forget
        # this the moment Module F's PR opens.
        #
        # A manual job entry (job_posting_id is NULL) has no scraped
        # description at all — there is nothing to tailor a question against,
        # so this path is explicitly rejected with a clear, actionable message
        # rather than crashing on `posting.description_raw` (which would be an
        # AttributeError on None) or silently falling back to generic
        # (non-JD-tailored) questions the candidate didn't ask for.
        raise ValidationAppError(
            "JD-tailored practice isn't available for manually-added jobs "
            "(no job description on file) — try résumé-personalized practice instead"
        )
    if not posting.description_raw:
        raise ValidationAppError("This job posting has no description to practice against")

    generated_today = await _jd_generation_count_today(db, user_id)
    if generated_today >= settings.jd_question_generation_daily_limit_per_user:
        jd_practice_daily_limit_hit_total.inc()
        raise RateLimitError("Daily JD-tailored practice question limit reached")

    candidate_context = await _load_candidate_context(db, user_id)

    job_context = JobContext(
        job_description=posting.description_raw,
        job_title=posting.title,
        company=posting.company,
    )
    generated, token_usage = await generate_jd_tailored_questions(
        job_context,
        request.category or "technical",
        request.difficulty or "medium",
        settings,
        count=request.count,
        candidate_context=candidate_context,
    )
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
        session_metadata={
            "job_match_id": str(match.id),
            "job_title": posting.title,
            "company": posting.company,
        },
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
        job_match_id=request.job_match_id,
        practice_session_id=session.id,
    )
