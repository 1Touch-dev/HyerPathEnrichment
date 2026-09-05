"""Service-layer tests for JD-tailored interview practice (Module 4, Module E).

Mirrors the pattern in test_application_tracker_repository.py: `test_user`/
`second_test_user` fixtures are defined locally, and committed rows persist
across tests in the same DB (no per-test transaction rollback), so assertions
scope explicitly to the fixture's own user/postings rather than assuming an
empty table.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.password import hash_password
from app.core.config import get_settings
from app.core.errors import NotFoundError, RateLimitError, ValidationAppError
from app.models import InterviewQuestion
from app.modules.jd_practice.schemas import JdPracticeRequest
from app.modules.jd_practice.service import get_jd_tailored_questions
from app.modules.job_matching.models import JobMatch, JobPosting
from app.modules.manual_jobs.schemas import CreateManualJobEntryRequest
from app.modules.manual_jobs.service import create_manual_entry
from app.modules.sessions.models import PracticeSession

SAMPLE_GENERATED_QUESTION = {
    "question_text": "Describe how you would design the payments retry logic mentioned in this posting.",
    "category": "technical",
    "difficulty": "medium",
    "job_roles": ["software_engineer"],
    "technologies": ["python"],
    "sample_answer": "A strong answer would cover idempotency keys...",
    "scoring_rubric": {"depth": "Covers idempotency and backoff"},
}


@pytest.fixture
async def test_user(db: AsyncSession) -> User:
    user = User(
        email=f"jd-practice-primary-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Primary",
        last_name="Candidate",
        hashed_password=hash_password("password123"),
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def second_test_user(db: AsyncSession) -> User:
    user = User(
        email=f"jd-practice-secondary-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Secondary",
        last_name="Candidate",
        hashed_password=hash_password("password123"),
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _make_posting(db: AsyncSession, **overrides) -> JobPosting:
    fields = {
        "dedup_key": uuid.uuid4().hex,
        "title": "Backend Engineer",
        "company": "Acme",
        "location": "Remote",
        "remote": True,
        "source": "linkedin",
        "sources_seen": ["linkedin"],
        "is_active": True,
        "description_raw": "We are looking for a Backend Engineer to own our payments retry logic.",
    }
    fields.update(overrides)
    posting = JobPosting(**fields)
    db.add(posting)
    await db.commit()
    await db.refresh(posting)
    return posting


async def _make_match(
    db: AsyncSession, user_id: uuid.UUID, posting: JobPosting, **overrides
) -> JobMatch:
    fields = {
        "user_id": user_id,
        "job_posting_id": posting.id,
        "similarity_score": 0.5,
        "rule_score": 0.5,
        "overall_score": 50.0,
        "score_breakdown": {},
    }
    fields.update(overrides)
    match = JobMatch(**fields)
    db.add(match)
    await db.commit()
    await db.refresh(match)
    return match


def _mock_settings(monkeypatch: pytest.MonkeyPatch):
    # get_settings() is @lru_cache'd (app/core/config.py) -- mutating the
    # singleton instance via monkeypatch (auto-reverted at test teardown, per
    # test_questions_router.py's established pattern) is visible to the
    # `Depends(get_settings)` used by the route and to this module's direct
    # calls alike, without leaking state into other tests.
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "test-key-for-jd-practice")
    return settings


class TestBankNeverQueried:
    @pytest.mark.asyncio
    async def test_jd_tailored_generation_never_calls_bank_selection(
        self, db: AsyncSession, test_user: User, monkeypatch: pytest.MonkeyPatch
    ):
        """§9.2/§9.7 regression guard: JD-tailored practice must bypass the
        shared bank entirely — accidentally falling back to it would silently
        reintroduce generic questions for a JD-tailored request.
        """
        posting = await _make_posting(db)
        match = await _make_match(db, test_user.id, posting)
        settings = _mock_settings(monkeypatch)

        with (
            patch(
                "app.modules.jd_practice.service.generate_jd_tailored_questions",
                new_callable=AsyncMock,
            ) as mock_generate,
            patch(
                "app.services.question_selector.select_questions", new_callable=AsyncMock
            ) as mock_select,
        ):
            mock_generate.return_value = (
                [SAMPLE_GENERATED_QUESTION],
                {"input_tokens": 10, "output_tokens": 20},
            )
            request = JdPracticeRequest(job_match_id=str(match.id), count=5)
            response = await get_jd_tailored_questions(db, test_user.id, request, settings)

            assert len(response.questions) == 5
            mock_select.assert_not_called()


class TestDailyLimitIsSeparateCounter:
    @pytest.mark.asyncio
    async def test_hitting_jd_limit_does_not_block_non_jd_generation(
        self, db: AsyncSession, test_user: User, monkeypatch: pytest.MonkeyPatch
    ):
        posting = await _make_posting(db)
        match = await _make_match(db, test_user.id, posting)
        settings = _mock_settings(monkeypatch)
        monkeypatch.setattr(settings, "jd_question_generation_daily_limit_per_user", 1)

        with patch(
            "app.modules.jd_practice.service.generate_jd_tailored_questions",
            new_callable=AsyncMock,
        ) as mock_generate:
            mock_generate.return_value = (
                [SAMPLE_GENERATED_QUESTION],
                {"input_tokens": 10, "output_tokens": 20},
            )
            request = JdPracticeRequest(job_match_id=str(match.id), count=5)
            await get_jd_tailored_questions(db, test_user.id, request, settings)

            # JD limit (1) now reached for this user -> second JD call rejected.
            with pytest.raises(RateLimitError):
                await get_jd_tailored_questions(db, test_user.id, request, settings)

        # The (separate) non-JD personalized-generation limit is untouched by
        # the JD-tailored counter above -- questions/service.py's own limit
        # guard reads InterviewQuestion.personalized_for_user_id, never
        # PracticeSession rows, so it must still report 0 generated today.
        from app.modules.questions.service import _personalized_generation_count_today

        count = await _personalized_generation_count_today(db, test_user.id)
        assert count == 0

    @pytest.mark.asyncio
    async def test_hitting_non_jd_limit_does_not_block_jd_generation(
        self, db: AsyncSession, test_user: User, monkeypatch: pytest.MonkeyPatch
    ):
        posting = await _make_posting(db)
        match = await _make_match(db, test_user.id, posting)
        settings = _mock_settings(monkeypatch)

        # Simulate Module 3's non-JD personalized-generation daily limit
        # already being exhausted for this user (a real InterviewQuestion row
        # with personalized_for_user_id set, created "today").
        db.add(
            InterviewQuestion(
                question_text="Some other personalized bank question",
                question_category="technical",
                difficulty="medium",
                job_roles=["software_engineer"],
                technologies=["python"],
                personalized_for_user_id=test_user.id,
                source="ai_generated_personalized",
            )
        )
        await db.commit()

        with patch(
            "app.modules.jd_practice.service.generate_jd_tailored_questions",
            new_callable=AsyncMock,
        ) as mock_generate:
            mock_generate.return_value = (
                [SAMPLE_GENERATED_QUESTION],
                {"input_tokens": 10, "output_tokens": 20},
            )
            request = JdPracticeRequest(job_match_id=str(match.id), count=5)
            # Must succeed -- the JD-tailored counter is entirely separate
            # from the InterviewQuestion-based non-JD counter above.
            response = await get_jd_tailored_questions(db, test_user.id, request, settings)
            assert len(response.questions) == 5


class TestOwnershipAndValidation:
    @pytest.mark.asyncio
    async def test_404_when_job_match_not_owned_by_caller(
        self,
        db: AsyncSession,
        test_user: User,
        second_test_user: User,
        monkeypatch: pytest.MonkeyPatch,
    ):
        posting = await _make_posting(db)
        match = await _make_match(db, test_user.id, posting)
        settings = _mock_settings(monkeypatch)

        request = JdPracticeRequest(job_match_id=str(match.id), count=5)
        with pytest.raises(NotFoundError):
            await get_jd_tailored_questions(db, second_test_user.id, request, settings)

    @pytest.mark.asyncio
    async def test_404_when_job_match_id_does_not_exist(
        self, db: AsyncSession, test_user: User, monkeypatch: pytest.MonkeyPatch
    ):
        settings = _mock_settings(monkeypatch)
        request = JdPracticeRequest(job_match_id=str(uuid.uuid4()), count=5)
        with pytest.raises(NotFoundError):
            await get_jd_tailored_questions(db, test_user.id, request, settings)

    @pytest.mark.asyncio
    async def test_validation_error_when_posting_missing_description_raw(
        self, db: AsyncSession, test_user: User, monkeypatch: pytest.MonkeyPatch
    ):
        posting = await _make_posting(db, description_raw=None)
        match = await _make_match(db, test_user.id, posting)
        settings = _mock_settings(monkeypatch)

        request = JdPracticeRequest(job_match_id=str(match.id), count=5)
        with pytest.raises(ValidationAppError) as exc_info:
            await get_jd_tailored_questions(db, test_user.id, request, settings)
        assert "no description to practice against" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validation_error_when_posting_row_is_dangling(
        self, db: AsyncSession, test_user: User, monkeypatch: pytest.MonkeyPatch
    ):
        """A `JobMatch` whose `job_posting_id` is set but whose `JobPosting` row
        no longer resolves (e.g. deleted out from under it) is a data-integrity
        edge case, distinct from a genuine Module F manual entry (whose
        `job_posting_id` is NULL by design, never set-then-orphaned). Must hit
        the SAME "missing description" message as a real posting with no
        `description_raw` -- not the manual-entry-specific message below, since
        `match.job_posting_id` is still non-NULL here.
        """
        posting = await _make_posting(db)
        match = await _make_match(db, test_user.id, posting)
        await db.delete(posting)
        await db.commit()
        settings = _mock_settings(monkeypatch)

        request = JdPracticeRequest(job_match_id=str(match.id), count=5)
        with pytest.raises(ValidationAppError) as exc_info:
            await get_jd_tailored_questions(db, test_user.id, request, settings)
        assert "no description to practice against" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validation_error_for_manual_entry_job_match(
        self, db: AsyncSession, test_user: User, monkeypatch: pytest.MonkeyPatch
    ):
        """A real Module F manual entry (`job_posting_id IS NULL`,
        `manual_job_entry_id` set) must be rejected with its own specific
        message -- distinct from the "missing description_raw" message used
        for a genuine (but incomplete) `JobPosting` above.
        """
        await create_manual_entry(
            db,
            test_user.id,
            CreateManualJobEntryRequest(title="Staff Engineer", company="Acme Networking Co"),
        )

        from sqlalchemy import select

        result = await db.execute(
            select(JobMatch).where(
                JobMatch.user_id == test_user.id, JobMatch.manual_job_entry_id.is_not(None)
            )
        )
        match = result.scalar_one()
        settings = _mock_settings(monkeypatch)

        request = JdPracticeRequest(job_match_id=str(match.id), count=5)
        with pytest.raises(ValidationAppError) as exc_info:
            await get_jd_tailored_questions(db, test_user.id, request, settings)
        assert "Manual job entries have no job description" in str(exc_info.value)


class TestQuestionsNeverPersistedToBank:
    @pytest.mark.asyncio
    async def test_generated_questions_are_not_written_to_interview_questions(
        self, db: AsyncSession, test_user: User, monkeypatch: pytest.MonkeyPatch
    ):
        posting = await _make_posting(db)
        match = await _make_match(db, test_user.id, posting)
        settings = _mock_settings(monkeypatch)

        unique_text = f"Unique JD-tailored question {uuid.uuid4()}"
        with patch(
            "app.modules.jd_practice.service.generate_jd_tailored_questions",
            new_callable=AsyncMock,
        ) as mock_generate:
            mock_generate.return_value = (
                [{**SAMPLE_GENERATED_QUESTION, "question_text": unique_text}],
                {"input_tokens": 10, "output_tokens": 20},
            )
            request = JdPracticeRequest(job_match_id=str(match.id), count=5)
            response = await get_jd_tailored_questions(db, test_user.id, request, settings)

        assert response.questions[0].question_text == unique_text

        from sqlalchemy import select

        result = await db.execute(
            select(InterviewQuestion).where(InterviewQuestion.question_text == unique_text)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_creates_practice_session_with_jd_tailored_type(
        self, db: AsyncSession, test_user: User, monkeypatch: pytest.MonkeyPatch
    ):
        posting = await _make_posting(db)
        match = await _make_match(db, test_user.id, posting)
        settings = _mock_settings(monkeypatch)

        with patch(
            "app.modules.jd_practice.service.generate_jd_tailored_questions",
            new_callable=AsyncMock,
        ) as mock_generate:
            mock_generate.return_value = (
                [SAMPLE_GENERATED_QUESTION],
                {"input_tokens": 10, "output_tokens": 20},
            )
            request = JdPracticeRequest(job_match_id=str(match.id), count=5)
            response = await get_jd_tailored_questions(db, test_user.id, request, settings)

        from sqlalchemy import select

        result = await db.execute(
            select(PracticeSession).where(PracticeSession.id == response.practice_session_id)
        )
        session = result.scalar_one()
        assert session.session_type == "jd_tailored"
        assert session.session_metadata["job_match_id"] == str(match.id)
