"""Regression test for phase2_module3.md §4.4: the feedback worker previously
read a nonexistent `attempt_metadata` attribute via `hasattr()` (always False
on the real, already-mapped `QuestionAttempt` class) and so `question_text`
was always `None`. The real, current implementation
(`backend/app/workers/tasks/feedback.py::_generate_feedback_sync`) instead
looks the question text up via the `QuestionAttempt.question_id` ->
`InterviewQuestion.id` FK, and writes `strengths`/`improvements` onto the now
real, mapped `QuestionAttempt.attempt_metadata` JSON column (dimension scores
go to `score_breakdown`, which is a separate column).

This test uses `SyncSessionLocal` (the real sync session factory
`_generate_feedback_sync` is designed to receive, per its
`db: Session` parameter) against the shared test SQLite database, following
the same real, working pattern already established in
`tests/test_job_matching_worker.py` for testing sync RQ worker entrypoints
that internally spin their own event loop (rather than inventing a new
`sync_db_session` fixture/session type, since none of that fictional name
exists anywhere in this repo).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

from app.database.session import SyncSessionLocal
from app.models import InterviewQuestion
from app.modules.sessions.models import PracticeSession, QuestionAttempt
from app.workers.tasks.feedback import _generate_feedback_sync


def _create_question(**overrides) -> InterviewQuestion:
    with SyncSessionLocal() as session:
        fields = {
            "question_text": "Describe the CAP theorem.",
            "question_category": "technical",
            "difficulty": "hard",
            "job_roles": ["software_engineer"],
            "technologies": ["distributed-systems"],
        }
        fields.update(overrides)
        question = InterviewQuestion(**fields)
        session.add(question)
        session.commit()
        session.refresh(question)
        return question


def _create_practice_session(user_id, **overrides) -> PracticeSession:
    with SyncSessionLocal() as session:
        fields = {
            "user_id": user_id,
            "session_type": "text",
        }
        fields.update(overrides)
        practice_session = PracticeSession(**fields)
        session.add(practice_session)
        session.commit()
        session.refresh(practice_session)
        return practice_session


def _create_attempt(session_id, user_id, question_id, **overrides) -> QuestionAttempt:
    with SyncSessionLocal() as session:
        fields = {
            "session_id": session_id,
            "user_id": user_id,
            "question_id": question_id,
            "response_type": "text",
            "text_response": "CAP theorem states you can only have two of "
            "consistency, availability, and partition tolerance.",
        }
        fields.update(overrides)
        attempt = QuestionAttempt(**fields)
        session.add(attempt)
        session.commit()
        session.refresh(attempt)
        return attempt


def test_question_text_is_looked_up_via_fk_not_metadata():
    """`_generate_feedback_sync` resolves `question_text` from the FK-joined
    `InterviewQuestion` row (not a nonexistent `attempt_metadata` attribute),
    and persists `strengths`/`improvements` onto the real
    `QuestionAttempt.attempt_metadata` JSON column."""
    user_id = uuid.uuid4()
    question = _create_question()
    practice_session = _create_practice_session(user_id)
    attempt = _create_attempt(practice_session.id, user_id, question.id)

    canned_feedback = (
        {
            "overall_score": 80.0,
            "dimension_scores": {
                "clarity": 20.0,
                "technical_accuracy": 20.0,
                "completeness": 20.0,
                "communication_skills": 20.0,
            },
            "strengths": ["Clear"],
            "improvements": ["More depth"],
            "detailed_feedback": "Good answer.",
        },
        {"input_tokens": 100, "output_tokens": 50},
    )

    # `feedback.py` does `from app.services.feedback_generator import
    # generate_interview_feedback`, binding the function directly into its
    # own module namespace — patching `app.services.feedback_generator.
    # generate_interview_feedback` (the plan's literal snippet) would NOT
    # intercept the call, since feedback.py already holds its own reference
    # to the original function object. The call site must be patched instead.
    with patch(
        "app.workers.tasks.feedback.generate_interview_feedback",
        new_callable=AsyncMock,
    ) as mock_generate:
        mock_generate.return_value = canned_feedback

        with SyncSessionLocal() as db:
            _generate_feedback_sync(str(attempt.id), db)

        call_kwargs = mock_generate.call_args.kwargs
        assert call_kwargs["question"] == "Describe the CAP theorem."

    with SyncSessionLocal() as verify_session:
        refreshed = verify_session.get(QuestionAttempt, attempt.id)
        assert refreshed.attempt_metadata["strengths"] == ["Clear"]
        assert refreshed.attempt_metadata["improvements"] == ["More depth"]
        assert refreshed.ai_score == 80.0
        assert refreshed.score_breakdown["clarity"] == 20.0


def test_question_text_is_none_when_question_id_is_null():
    """When `question_id` is null, `question_text` stays `None` and
    `generate_interview_feedback` runs its general-evaluation branch, rather
    than raising or silently misreading a nonexistent attribute."""
    user_id = uuid.uuid4()
    practice_session = _create_practice_session(user_id)
    attempt = _create_attempt(practice_session.id, user_id, question_id=None)

    canned_feedback = (
        {
            "overall_score": 60.0,
            "dimension_scores": {
                "clarity": 15.0,
                "technical_accuracy": 15.0,
                "completeness": 15.0,
                "communication_skills": 15.0,
            },
            "strengths": ["Fine"],
            "improvements": ["Be more specific"],
            "detailed_feedback": "General feedback.",
        },
        {"input_tokens": 80, "output_tokens": 40},
    )

    with patch(
        "app.workers.tasks.feedback.generate_interview_feedback",
        new_callable=AsyncMock,
    ) as mock_generate:
        mock_generate.return_value = canned_feedback

        with SyncSessionLocal() as db:
            _generate_feedback_sync(str(attempt.id), db)

        call_kwargs = mock_generate.call_args.kwargs
        assert call_kwargs["question"] is None
