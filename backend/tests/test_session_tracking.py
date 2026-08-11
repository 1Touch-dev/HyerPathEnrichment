"""Comprehensive tests for session tracking system."""

from datetime import UTC, datetime
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
