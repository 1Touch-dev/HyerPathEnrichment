"""Comprehensive tests for session tracking system."""

from datetime import UTC, datetime
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationAppError
from app.modules.sessions.models import PracticeSession, QuestionAttempt
from app.modules.sessions.schemas import (
    QuestionAttemptRequest,
    SessionCreateRequest,
    SessionUpdateRequest,
)
from app.services.session_manager import SessionManager


@pytest.fixture
async def session_manager(db: AsyncSession) -> SessionManager:
    """Create a session manager instance."""
    return SessionManager(db)


@pytest.fixture
async def test_user_id() -> UUID:
    """Generate a test user ID."""
    return uuid4()


@pytest.fixture
async def sample_session(db: AsyncSession, test_user_id: UUID) -> PracticeSession:
    """Create a sample practice session."""
    session = PracticeSession(
        id=uuid4(),
        user_id=test_user_id,
        session_type="behavioral",
        status="pending",
        started_at=datetime.now(UTC),
        session_metadata={"difficulty": "medium"},
    )
    db.add(session)
    await db.flush()  # Flush to make data visible within the transaction
    return session


class TestSessionCreation:
    """Tests for session creation."""

    async def test_create_session_success(
        self, session_manager: SessionManager, test_user_id: UUID
    ):
        """Test successful session creation."""
        request = SessionCreateRequest(
            session_type="technical",
            session_metadata={"topic": "algorithms"},
        )
        response = await session_manager.create_session(request, test_user_id)

        assert response.session_type == "technical"
        assert response.status == "pending"
        assert response.user_id == test_user_id
        assert response.questions_attempted == 0
        assert response.questions_completed == 0
        assert response.session_metadata == {"topic": "algorithms"}

    async def test_create_session_with_empty_metadata(
        self, session_manager: SessionManager, test_user_id: UUID
    ):
        """Test session creation with default empty metadata."""
        request = SessionCreateRequest(session_type="behavioral")
        response = await session_manager.create_session(request, test_user_id)

        assert response.session_metadata == {}


class TestSessionRetrieval:
    """Tests for session retrieval."""

    async def test_get_session_success(
        self, session_manager: SessionManager, sample_session: PracticeSession, test_user_id: UUID
    ):
        """Test retrieving an existing session."""
        response = await session_manager.get_session(sample_session.id, test_user_id)

        assert response.id == sample_session.id
        assert response.session_type == "behavioral"
        assert response.status == "pending"

    async def test_get_session_not_found(self, session_manager: SessionManager, test_user_id: UUID):
        """Test retrieving a non-existent session."""
        fake_id = uuid4()
        with pytest.raises(NotFoundError):
            await session_manager.get_session(fake_id, test_user_id)

    async def test_get_session_wrong_user(
        self, session_manager: SessionManager, sample_session: PracticeSession
    ):
        """Test retrieving session with wrong user ID."""
        wrong_user_id = uuid4()
        with pytest.raises(NotFoundError):
            await session_manager.get_session(sample_session.id, wrong_user_id)


class TestSessionListing:
    """Tests for listing sessions."""

    async def test_list_sessions_empty(self, session_manager: SessionManager, test_user_id: UUID):
        """Test listing sessions when none exist."""
        response = await session_manager.list_sessions(test_user_id)

        assert response.total == 0
        assert len(response.sessions) == 0

    async def test_list_sessions_with_data(
        self, session_manager: SessionManager, sample_session: PracticeSession, test_user_id: UUID
    ):
        """Test listing sessions with existing data."""
        response = await session_manager.list_sessions(test_user_id)

        assert response.total == 1
        assert len(response.sessions) == 1
        assert response.sessions[0].id == sample_session.id

    async def test_list_sessions_pagination(
        self, session_manager: SessionManager, db: AsyncSession, test_user_id: UUID
    ):
        """Test session listing pagination."""
        # Create 5 sessions
        for i in range(5):
            session = PracticeSession(
                id=uuid4(),
                user_id=test_user_id,
                session_type=f"type_{i}",
                status="pending",
                started_at=datetime.now(UTC),
            )
            db.add(session)
        await db.commit()

        # Test first page
        page1 = await session_manager.list_sessions(test_user_id, limit=2, offset=0)
        assert page1.total == 5
        assert len(page1.sessions) == 2

        # Test second page
        page2 = await session_manager.list_sessions(test_user_id, limit=2, offset=2)
        assert page2.total == 5
        assert len(page2.sessions) == 2


class TestSessionUpdate:
    """Tests for session updates and state transitions."""

    async def test_update_session_status(
        self, session_manager: SessionManager, sample_session: PracticeSession, test_user_id: UUID
    ):
        """Test updating session status."""
        request = SessionUpdateRequest(status="in_progress")
        response = await session_manager.update_session(sample_session.id, request, test_user_id)

        assert response.status == "in_progress"

    async def test_update_session_metrics(
        self, session_manager: SessionManager, sample_session: PracticeSession, test_user_id: UUID
    ):
        """Test updating session metrics."""
        request = SessionUpdateRequest(
            questions_attempted=5,
            questions_completed=3,
            overall_score=85.5,
        )
        response = await session_manager.update_session(sample_session.id, request, test_user_id)

        assert response.questions_attempted == 5
        assert response.questions_completed == 3
        assert response.overall_score == 85.5

    async def test_update_session_metadata(
        self, session_manager: SessionManager, sample_session: PracticeSession, test_user_id: UUID
    ):
        """Test updating session metadata."""
        request = SessionUpdateRequest(session_metadata={"new_key": "new_value"})
        response = await session_manager.update_session(sample_session.id, request, test_user_id)

        assert response.session_metadata == {"new_key": "new_value"}

    async def test_state_transition_to_completed(
        self, session_manager: SessionManager, db: AsyncSession, test_user_id: UUID
    ):
        """Test transition to completed sets completed_at."""
        session = PracticeSession(
            id=uuid4(),
            user_id=test_user_id,
            session_type="test",
            status="in_progress",
            started_at=datetime.now(UTC),
        )
        db.add(session)
        await db.commit()

        request = SessionUpdateRequest(status="completed")
        response = await session_manager.update_session(session.id, request, test_user_id)

        assert response.status == "completed"
        assert response.completed_at is not None

    async def test_invalid_state_transition(
        self, session_manager: SessionManager, db: AsyncSession, test_user_id: UUID
    ):
        """Test invalid state transition raises error."""
        session = PracticeSession(
            id=uuid4(),
            user_id=test_user_id,
            session_type="test",
            status="completed",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        db.add(session)
        await db.commit()

        request = SessionUpdateRequest(status="in_progress")
        with pytest.raises(ValidationAppError, match="Invalid transition"):
            await session_manager.update_session(session.id, request, test_user_id)

    async def test_valid_state_transitions(
        self, session_manager: SessionManager, db: AsyncSession, test_user_id: UUID
    ):
        """Test all valid state transitions."""
        # pending -> in_progress
        session = PracticeSession(
            id=uuid4(),
            user_id=test_user_id,
            session_type="test",
            status="pending",
            started_at=datetime.now(UTC),
        )
        db.add(session)
        await db.commit()

        request = SessionUpdateRequest(status="in_progress")
        response = await session_manager.update_session(session.id, request, test_user_id)
        assert response.status == "in_progress"

        # in_progress -> completed
        request = SessionUpdateRequest(status="completed")
        response = await session_manager.update_session(session.id, request, test_user_id)
        assert response.status == "completed"


class TestSessionDeletion:
    """Tests for session deletion."""

    async def test_delete_session_success(
        self, session_manager: SessionManager, sample_session: PracticeSession, test_user_id: UUID
    ):
        """Test successful session deletion."""
        await session_manager.delete_session(sample_session.id, test_user_id)

        with pytest.raises(NotFoundError):
            await session_manager.get_session(sample_session.id, test_user_id)

    async def test_delete_session_not_found(
        self, session_manager: SessionManager, test_user_id: UUID
    ):
        """Test deleting non-existent session."""
        fake_id = uuid4()
        with pytest.raises(NotFoundError):
            await session_manager.delete_session(fake_id, test_user_id)

    async def test_delete_session_cascades_to_attempts(
        self, session_manager: SessionManager, db: AsyncSession, test_user_id: UUID
    ):
        """Test deleting session cascades to attempts."""
        session = PracticeSession(
            id=uuid4(),
            user_id=test_user_id,
            session_type="test",
            status="in_progress",
            started_at=datetime.now(UTC),
        )
        db.add(session)
        await db.commit()

        # Add attempt
        attempt = QuestionAttempt(
            id=uuid4(),
            session_id=session.id,
            user_id=test_user_id,
            response_type="text",
            text_response="Test answer",
            attempted_at=datetime.now(UTC),
        )
        db.add(attempt)
        await db.commit()

        # Delete session
        await session_manager.delete_session(session.id, test_user_id)

        # Verify attempt is also deleted
        stmt = select(QuestionAttempt).where(QuestionAttempt.id == attempt.id)
        result = await db.execute(stmt)
        assert result.scalar_one_or_none() is None


class TestQuestionAttempts:
    """Tests for question attempts."""

    async def test_add_text_attempt(
        self, session_manager: SessionManager, sample_session: PracticeSession, test_user_id: UUID
    ):
        """Test adding a text response attempt."""
        request = QuestionAttemptRequest(
            question_id=uuid4(),
            response_type="text",
            text_response="My answer to the question",
            ai_score=75.0,
            ai_feedback="Good answer, but could be more detailed",
            time_taken_seconds=120,
        )
        response = await session_manager.add_attempt(sample_session.id, request, test_user_id)

        assert response.response_type == "text"
        assert response.text_response == "My answer to the question"
        assert response.ai_score == 75.0
        assert response.time_taken_seconds == 120

    async def test_add_audio_attempt(
        self, session_manager: SessionManager, sample_session: PracticeSession, test_user_id: UUID
    ):
        """Test adding an audio response attempt."""
        audio_id = str(uuid4())
        request = QuestionAttemptRequest(
            question_id=uuid4(),
            response_type="audio",
            audio_recording_id=audio_id,
            ai_score=88.5,
            time_taken_seconds=180,
        )
        response = await session_manager.add_attempt(sample_session.id, request, test_user_id)

        assert response.response_type == "audio"
        assert str(response.audio_recording_id) == audio_id  # Compare as strings
        assert response.ai_score == 88.5

    async def test_add_audio_attempt_backfills_text_response_from_transcription(
        self,
        session_manager: SessionManager,
        sample_session: PracticeSession,
        test_user_id: UUID,
        db: AsyncSession,
    ):
        """Regression test: `POST /api/practice/audio` transcribes
        synchronously and returns before `add_attempt` is ever called, so the
        recording is already "completed" by then. Without backfilling
        `text_response` here, every audio attempt's `text_response` stayed
        `None` forever, so `add_attempt`'s "enqueue feedback if text_response"
        check never fired for audio answers — real users saw every audio
        question's score/feedback stuck at "Pending..." with no error."""
        from app.modules.sessions.models import PracticeAudioRecording

        recording = PracticeAudioRecording(
            id=uuid4(),
            user_id=test_user_id,
            practice_session_id=sample_session.id,
            storage_path="practice-audio/u/s/r.webm",
            file_size_bytes=1234,
            audio_format="audio/webm",
            transcription="This is my spoken answer.",
            transcription_status="completed",
        )
        db.add(recording)
        await db.flush()

        request = QuestionAttemptRequest(
            response_type="audio",
            audio_recording_id=recording.id,
        )
        with patch("app.services.session_manager.enqueue_feedback") as mock_enqueue:
            response = await session_manager.add_attempt(sample_session.id, request, test_user_id)

        assert response.text_response == "This is my spoken answer."
        mock_enqueue.assert_called_once_with(str(response.id))

    async def test_add_audio_attempt_with_pending_transcription_has_no_text_response(
        self,
        session_manager: SessionManager,
        sample_session: PracticeSession,
        test_user_id: UUID,
        db: AsyncSession,
    ):
        """A recording that hasn't finished transcribing (or failed) yields no
        `text_response` — no feedback job should be enqueued yet, since there's
        nothing to score."""
        from app.modules.sessions.models import PracticeAudioRecording

        recording = PracticeAudioRecording(
            id=uuid4(),
            user_id=test_user_id,
            practice_session_id=sample_session.id,
            storage_path="practice-audio/u/s/r2.webm",
            file_size_bytes=1234,
            audio_format="audio/webm",
            transcription_status="failed",
        )
        db.add(recording)
        await db.flush()

        request = QuestionAttemptRequest(
            response_type="audio",
            audio_recording_id=recording.id,
        )
        with patch("app.services.session_manager.enqueue_feedback") as mock_enqueue:
            response = await session_manager.add_attempt(sample_session.id, request, test_user_id)

        assert response.text_response is None
        mock_enqueue.assert_not_called()

    async def test_add_attempt_updates_session_metrics(
        self, session_manager: SessionManager, sample_session: PracticeSession, test_user_id: UUID
    ):
        """Test adding attempt updates session metrics."""
        request = QuestionAttemptRequest(
            response_type="text",
            text_response="Answer",
            ai_score=90.0,
        )
        await session_manager.add_attempt(sample_session.id, request, test_user_id)

        # Verify session was updated
        session = await session_manager.get_session(sample_session.id, test_user_id)
        assert session.questions_attempted == 1
        assert session.questions_completed == 1

    async def test_add_attempt_transitions_to_in_progress(
        self, session_manager: SessionManager, sample_session: PracticeSession, test_user_id: UUID
    ):
        """Test first attempt transitions pending session to in_progress."""
        assert sample_session.status == "pending"

        request = QuestionAttemptRequest(response_type="text", text_response="Answer")
        await session_manager.add_attempt(sample_session.id, request, test_user_id)

        session = await session_manager.get_session(sample_session.id, test_user_id)
        assert session.status == "in_progress"

    async def test_add_attempt_to_completed_session_fails(
        self, session_manager: SessionManager, db: AsyncSession, test_user_id: UUID
    ):
        """Test cannot add attempt to completed session."""
        session = PracticeSession(
            id=uuid4(),
            user_id=test_user_id,
            session_type="test",
            status="completed",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        db.add(session)
        await db.commit()

        request = QuestionAttemptRequest(response_type="text", text_response="Answer")
        with pytest.raises(ValidationAppError, match="Cannot add attempts"):
            await session_manager.add_attempt(session.id, request, test_user_id)

    async def test_add_attempt_without_score_does_not_increment_completed(
        self, session_manager: SessionManager, sample_session: PracticeSession, test_user_id: UUID
    ):
        """Test adding attempt without score only increments attempted count."""
        request = QuestionAttemptRequest(response_type="text", text_response="Answer")
        await session_manager.add_attempt(sample_session.id, request, test_user_id)

        session = await session_manager.get_session(sample_session.id, test_user_id)
        assert session.questions_attempted == 1
        assert session.questions_completed == 0


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    async def test_session_with_score_breakdown(
        self, session_manager: SessionManager, sample_session: PracticeSession, test_user_id: UUID
    ):
        """Test attempt with detailed score breakdown."""
        request = QuestionAttemptRequest(
            response_type="text",
            text_response="Detailed answer",
            ai_score=85.0,
            score_breakdown={
                "clarity": 90,
                "completeness": 80,
                "accuracy": 85,
            },
        )
        response = await session_manager.add_attempt(sample_session.id, request, test_user_id)

        assert response.score_breakdown == {
            "clarity": 90,
            "completeness": 80,
            "accuracy": 85,
        }

    async def test_multiple_attempts_per_session(
        self, session_manager: SessionManager, sample_session: PracticeSession, test_user_id: UUID
    ):
        """Test adding multiple attempts to a session."""
        for i in range(3):
            request = QuestionAttemptRequest(
                response_type="text",
                text_response=f"Answer {i}",
                ai_score=80.0 + i,
            )
            await session_manager.add_attempt(sample_session.id, request, test_user_id)

        session = await session_manager.get_session(sample_session.id, test_user_id)
        assert session.questions_attempted == 3
        assert session.questions_completed == 3
        assert len(session.attempts) == 3

    async def test_overall_score_defaults_to_average_of_scored_attempts(
        self, session_manager: SessionManager, sample_session: PracticeSession, test_user_id: UUID
    ):
        """`overall_score` is never set explicitly (no PATCH call, no
        session-completion flow) for a real practice session — it must fall
        back to the average of scored attempts instead of staying `None`
        forever (frontend showed "Overall score: Pending..." indefinitely)."""
        for score in (10.0, 80.0, 60.0):
            request = QuestionAttemptRequest(
                response_type="text", text_response="answer", ai_score=score
            )
            await session_manager.add_attempt(sample_session.id, request, test_user_id)

        session = await session_manager.get_session(sample_session.id, test_user_id)
        assert session.overall_score == 50.0  # (10 + 80 + 60) / 3

    async def test_overall_score_stays_none_with_no_scored_attempts(
        self, session_manager: SessionManager, sample_session: PracticeSession, test_user_id: UUID
    ):
        """No attempts scored yet (feedback job still pending) means "Pending"
        is still the correct UI state — must not default to 0."""
        request = QuestionAttemptRequest(response_type="text", text_response="answer")
        await session_manager.add_attempt(sample_session.id, request, test_user_id)

        session = await session_manager.get_session(sample_session.id, test_user_id)
        assert session.overall_score is None

    async def test_explicit_overall_score_is_not_overridden_by_average(
        self, session_manager: SessionManager, sample_session: PracticeSession, test_user_id: UUID
    ):
        """An explicit PATCH-set `overall_score` (e.g. a future "finish
        session" flow) always wins over the computed average."""
        request = QuestionAttemptRequest(
            response_type="text", text_response="answer", ai_score=10.0
        )
        await session_manager.add_attempt(sample_session.id, request, test_user_id)

        update = SessionUpdateRequest(overall_score=99.0)
        await session_manager.update_session(sample_session.id, update, test_user_id)

        session = await session_manager.get_session(sample_session.id, test_user_id)
        assert session.overall_score == 99.0

    async def test_attempt_question_text_is_populated_from_question_bank(
        self,
        session_manager: SessionManager,
        sample_session: PracticeSession,
        test_user_id: UUID,
        db: AsyncSession,
    ):
        """The report page needs the actual question wording next to a
        candidate's answer, not just `question_id` — both `add_attempt`'s
        return value and `get_session`'s attempts must carry `question_text`
        looked up from `interview_questions` (see session_manager.py's
        `_fetch_question_texts`)."""
        from app.models import InterviewQuestion

        question = InterviewQuestion(
            id=uuid4(),
            question_text="Tell me about a time you disagreed with a teammate.",
            question_category="behavioral",
            difficulty="medium",
            job_roles=["software_engineer"],
            technologies=[],
        )
        db.add(question)
        await db.flush()

        try:
            request = QuestionAttemptRequest(
                question_id=question.id, response_type="text", text_response="answer"
            )
            added = await session_manager.add_attempt(sample_session.id, request, test_user_id)
            assert added.question_text == "Tell me about a time you disagreed with a teammate."

            session = await session_manager.get_session(sample_session.id, test_user_id)
            assert len(session.attempts) == 1
            assert (
                session.attempts[0].question_text
                == "Tell me about a time you disagreed with a teammate."
            )
        finally:
            # `add_attempt` above commits (not just flushes), so this row survives
            # the `db` fixture's end-of-test rollback and leaks into the shared
            # SQLite test database used by other test modules (e.g.
            # test_question_bank.py's unscoped `job_role="software_engineer"`
            # queries) unless explicitly deleted here.
            await db.delete(question)
            await db.commit()

    async def test_attempt_question_text_is_none_without_question_id(
        self, session_manager: SessionManager, sample_session: PracticeSession, test_user_id: UUID
    ):
        """No `question_id` on the attempt (e.g. free-form practice) means no
        lookup happens and `question_text` stays `None` rather than erroring."""
        request = QuestionAttemptRequest(response_type="text", text_response="answer")
        added = await session_manager.add_attempt(sample_session.id, request, test_user_id)
        assert added.question_text is None

        session = await session_manager.get_session(sample_session.id, test_user_id)
        assert session.attempts[0].question_text is None


class TestUserIdUuidCoercion:
    """Regression tests for phase2_module2.md §2.1 Bug 2: user_id must be coerced to
    uuid.UUID before binding to the ORM column, or Postgres raises StatementError
    ('str' object has no attribute 'hex')."""

    async def test_create_session_accepts_uuid_user_id(
        self, session_manager: SessionManager, test_user_id: UUID
    ):
        """Passing a real uuid.UUID instance works and round-trips correctly."""
        request = SessionCreateRequest(session_type="technical")
        response = await session_manager.create_session(request, test_user_id)

        assert isinstance(response.user_id, UUID)
        assert response.user_id == test_user_id

    async def test_create_session_accepts_str_user_id(
        self, session_manager: SessionManager, test_user_id: UUID
    ):
        """Passing a str user_id (as an API boundary caller might) is coerced to
        uuid.UUID before it reaches the PracticeSession constructor, instead of
        raising StatementError."""
        request = SessionCreateRequest(session_type="technical")
        response = await session_manager.create_session(request, str(test_user_id))

        assert isinstance(response.user_id, UUID)
        assert response.user_id == test_user_id

    async def test_add_attempt_accepts_str_user_id(
        self, session_manager: SessionManager, sample_session: PracticeSession, test_user_id: UUID
    ):
        """add_attempt's user_id is coerced the same way as create_session's."""
        request = QuestionAttemptRequest(response_type="text", text_response="Answer")
        response = await session_manager.add_attempt(sample_session.id, request, str(test_user_id))

        assert isinstance(response.user_id, UUID)
        assert response.user_id == test_user_id
