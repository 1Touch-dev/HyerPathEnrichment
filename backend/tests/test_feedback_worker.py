"""Tests for feedback generation worker tasks.

Updated to match the current sync implementation (`_generate_feedback_sync` /
`SyncSessionLocal`, introduced by commit 155a3e10 "Fix sync/async mismatch in
feedback worker - use sync session"). The previous version of this file tested
a `_generate_feedback_async` function and patched a `SessionLocal` name that no
longer exist in `app.workers.tasks.feedback`, so it failed to even import.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database.base import Base
from app.models import InterviewQuestion  # noqa: F401 — register on Base.metadata
from app.modules.sessions.models import QuestionAttempt
from app.workers.tasks.feedback import _generate_feedback_sync, generate_feedback_job


@pytest.fixture
def in_memory_db():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


@pytest.fixture
def sample_attempt(in_memory_db):
    """Create a sample QuestionAttempt for testing.

    `QuestionAttempt` has no real `attempt_metadata` column (see
    `app.modules.sessions.models`); `feedback.py` treats it as a transient,
    duck-typed dict attribute via `hasattr`/`getattr`, so it must be set as a
    plain instance attribute after construction rather than a constructor
    kwarg (which the declarative constructor would reject as unknown).
    """
    attempt = QuestionAttempt(
        id=uuid4(),
        session_id=uuid4(),
        user_id=uuid4(),
        response_type="text",
        text_response="REST is an architectural style for building web services...",
    )
    attempt.attempt_metadata = {"question_text": "Explain REST APIs"}
    in_memory_db.add(attempt)
    in_memory_db.commit()
    in_memory_db.refresh(attempt)
    return attempt


@pytest.fixture
def mock_feedback():
    """Sample feedback response."""
    return (
        {
            "overall_score": 85.0,
            "dimension_scores": {
                "clarity": 22.0,
                "technical_accuracy": 21.0,
                "completeness": 21.0,
                "communication_skills": 21.0,
            },
            "strengths": ["Clear explanation", "Good structure"],
            "improvements": ["Add more examples", "Discuss trade-offs"],
            "detailed_feedback": "Strong answer with clear structure and good understanding.",
        },
        {"input_tokens": 150, "output_tokens": 200},
    )


def test_generate_feedback_sync_success(in_memory_db, sample_attempt, mock_feedback):
    """Feedback generation updates attempt with scores and feedback."""
    with patch(
        "app.workers.tasks.feedback.generate_interview_feedback",
        new_callable=AsyncMock,
    ) as mock_generate:
        mock_generate.return_value = mock_feedback

        with patch("app.workers.tasks.feedback.track_llm_cost", new_callable=AsyncMock):
            _generate_feedback_sync(str(sample_attempt.id), in_memory_db)

            # Refresh from DB
            in_memory_db.refresh(sample_attempt)

            # Verify feedback was stored
            assert sample_attempt.ai_score == Decimal("85.0")
            assert sample_attempt.score_breakdown == mock_feedback[0]["dimension_scores"]
            assert sample_attempt.ai_feedback == mock_feedback[0]["detailed_feedback"]

            # Verify attempt_metadata was updated
            assert "strengths" in sample_attempt.attempt_metadata
            assert sample_attempt.attempt_metadata["strengths"] == mock_feedback[0]["strengths"]
            assert "improvements" in sample_attempt.attempt_metadata
            assert (
                sample_attempt.attempt_metadata["improvements"] == mock_feedback[0]["improvements"]
            )


def test_generate_feedback_sync_no_text_response(in_memory_db, sample_attempt):
    """Empty text response skips feedback generation."""
    sample_attempt.text_response = None
    in_memory_db.commit()

    with patch(
        "app.workers.tasks.feedback.generate_interview_feedback",
        new_callable=AsyncMock,
    ) as mock_generate:
        _generate_feedback_sync(str(sample_attempt.id), in_memory_db)

        # Should not call feedback service
        mock_generate.assert_not_called()


def test_generate_feedback_sync_invalid_uuid(in_memory_db):
    """Invalid UUID raises ValueError."""
    with pytest.raises(ValueError, match="Attempt not found"):
        _generate_feedback_sync(str(uuid4()), in_memory_db)


def test_generate_feedback_sync_tracks_cost(in_memory_db, sample_attempt, mock_feedback):
    """Cost tracking is called with correct parameters."""
    with patch(
        "app.workers.tasks.feedback.generate_interview_feedback",
        new_callable=AsyncMock,
    ) as mock_generate:
        mock_generate.return_value = mock_feedback

        with patch(
            "app.workers.tasks.feedback.track_llm_cost", new_callable=AsyncMock
        ) as mock_track:
            _generate_feedback_sync(str(sample_attempt.id), in_memory_db)

            # Verify cost tracking was called
            mock_track.assert_called_once_with(
                model="gpt-4o-mini",
                input_tokens=150,
                output_tokens=200,
                operation="feedback",
                user_id=str(sample_attempt.user_id),
            )


def test_generate_feedback_job_sync_wrapper(sample_attempt, mock_feedback):
    """Sync wrapper runs feedback generation successfully."""
    with patch("app.workers.tasks.feedback.SyncSessionLocal") as mock_session_local:
        mock_db = MagicMock(spec=Session)
        mock_session_local.return_value = mock_db

        # Mock the attempt
        mock_db.scalar.return_value = sample_attempt

        with patch(
            "app.workers.tasks.feedback.generate_interview_feedback",
            new_callable=AsyncMock,
        ) as mock_generate:
            mock_generate.return_value = mock_feedback

            with patch("app.workers.tasks.feedback.track_llm_cost", new_callable=AsyncMock):
                # Should not raise
                generate_feedback_job(str(sample_attempt.id))

                # Verify DB session was created and closed
                mock_session_local.assert_called_once()
                mock_db.close.assert_called_once()


def test_generate_feedback_job_invalid_uuid():
    """Invalid UUID format is handled gracefully without ever opening a DB session.

    `generate_feedback_job` parses the UUID before calling `SyncSessionLocal()`,
    so an invalid UUID raises and is caught without a session ever being created.
    """
    with patch("app.workers.tasks.feedback.SyncSessionLocal") as mock_session_local:
        # Should not raise - error is logged
        generate_feedback_job("not-a-uuid")

        # No DB session should have been created for this early failure
        mock_session_local.assert_not_called()


def test_generate_feedback_job_attempt_not_found():
    """Non-existent attempt is handled gracefully."""
    with patch("app.workers.tasks.feedback.SyncSessionLocal") as mock_session_local:
        mock_db = MagicMock(spec=Session)
        mock_session_local.return_value = mock_db

        # Mock no attempt found
        mock_db.scalar.return_value = None

        # Should not raise - error is logged
        generate_feedback_job(str(uuid4()))

        # DB session should still be closed
        mock_db.close.assert_called_once()


def test_generate_feedback_job_api_failure_stores_error(sample_attempt):
    """API failure is stored in attempt metadata."""
    with patch("app.workers.tasks.feedback.SyncSessionLocal") as mock_session_local:
        mock_db = MagicMock(spec=Session)
        mock_session_local.return_value = mock_db

        # Mock finding the attempt twice (fetch + error update)
        mock_db.scalar.side_effect = [sample_attempt, sample_attempt]

        with patch(
            "app.workers.tasks.feedback.generate_interview_feedback",
            new_callable=AsyncMock,
        ) as mock_generate:
            mock_generate.side_effect = Exception("API Error")

            with patch("app.workers.tasks.feedback.track_llm_failure"):
                # Should not raise - error is logged
                generate_feedback_job(str(sample_attempt.id))

                # Verify attempt_metadata was updated with error
                assert "feedback_error" in sample_attempt.attempt_metadata
                assert "API Error" in sample_attempt.attempt_metadata["feedback_error"]

                # DB should commit error and close
                mock_db.commit.assert_called()
                mock_db.close.assert_called_once()


def test_generate_feedback_job_tracks_failure():
    """Failed jobs track failure metric."""
    with patch("app.workers.tasks.feedback.SyncSessionLocal") as mock_session_local:
        mock_db = MagicMock(spec=Session)
        mock_session_local.return_value = mock_db

        # Mock exception during processing
        mock_db.scalar.side_effect = Exception("DB Error")

        with patch("app.workers.tasks.feedback.track_llm_failure") as mock_track_failure:
            # Should not raise
            generate_feedback_job(str(uuid4()))

            # Verify failure was tracked
            mock_track_failure.assert_called_once_with(model="gpt-4o-mini", operation="feedback")


def test_generate_feedback_uses_question_from_fk(in_memory_db):
    """Question text is looked up via question_id → InterviewQuestion, not metadata."""
    question = InterviewQuestion(
        id=uuid4(),
        question_text="Custom question from bank",
        question_category="technical",
        difficulty="medium",
        job_roles=["software_engineer"],
        technologies=["python"],
    )
    in_memory_db.add(question)
    attempt = QuestionAttempt(
        id=uuid4(),
        session_id=uuid4(),
        user_id=uuid4(),
        question_id=question.id,
        response_type="text",
        text_response="My answer here",
    )
    # Stale metadata must not win over the FK lookup.
    attempt.attempt_metadata = {"question_text": "Stale metadata question"}
    in_memory_db.add(attempt)
    in_memory_db.commit()

    mock_feedback = (
        {
            "overall_score": 75.0,
            "dimension_scores": {
                "clarity": 18.0,
                "technical_accuracy": 19.0,
                "completeness": 19.0,
                "communication_skills": 19.0,
            },
            "strengths": ["Good"],
            "improvements": ["Better"],
            "detailed_feedback": "Feedback",
        },
        {"input_tokens": 100, "output_tokens": 100},
    )

    with patch(
        "app.workers.tasks.feedback.generate_interview_feedback",
        new_callable=AsyncMock,
    ) as mock_generate:
        mock_generate.return_value = mock_feedback

        with patch("app.workers.tasks.feedback.track_llm_cost", new_callable=AsyncMock):
            _generate_feedback_sync(str(attempt.id), in_memory_db)

            call_kwargs = mock_generate.call_args.kwargs
            assert call_kwargs["question"] == "Custom question from bank"
            assert call_kwargs["answer"] == "My answer here"
