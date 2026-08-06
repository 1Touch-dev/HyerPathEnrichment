"""Comprehensive tests for session tracking functionality."""

import pytest
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.modules.sessions.models import PracticeSession
from app.services import session_manager


@pytest.fixture
async def test_user(db: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        email=f"test-{uuid4()}@example.com",
        first_name="Test",
        last_name="User",
        is_verified=True,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.mark.asyncio
async def test_session_creation(db: AsyncSession, test_user: User):
    """Test creating a new practice session."""
    session = await session_manager.start_session(db, test_user.id, "interview_practice")

    assert session.id is not None
    assert session.user_id == test_user.id
    assert session.session_type == "interview_practice"
    assert session.status == "in_progress"
    assert session.questions_attempted == 0
    assert session.questions_completed == 0
    assert session.overall_score is None
    assert session.started_at is not None
    assert session.completed_at is None


@pytest.mark.asyncio
async def test_duplicate_session_prevention(db: AsyncSession, test_user: User):
    """Test that user cannot start multiple active sessions."""
    # Start first session
    await session_manager.start_session(db, test_user.id, "interview_practice")

    # Try to start second session - should fail
    with pytest.raises(ValueError, match="User already has an active session"):
        await session_manager.start_session(db, test_user.id, "technical_interview")


@pytest.mark.asyncio
async def test_session_state_transitions(db: AsyncSession, test_user: User):
    """Test valid state transitions for sessions."""
    # Start session (in_progress)
    session = await session_manager.start_session(db, test_user.id, "interview_practice")
    assert session.status == "in_progress"

    # Update progress
    updated = await session_manager.update_session_progress(
        db, session.id, questions_attempted=5, score=75.5
    )
    assert updated.questions_attempted == 5
    assert float(updated.overall_score) == 75.5

    # Complete session
    completed = await session_manager.complete_session(db, session.id, 85.0)
    assert completed.status == "completed"
    assert float(completed.overall_score) == 85.0
    assert completed.completed_at is not None

    # Try to complete again - should fail
    with pytest.raises(ValueError, match="Cannot complete session"):
        await session_manager.complete_session(db, session.id, 90.0)


@pytest.mark.asyncio
async def test_session_abandon(db: AsyncSession, test_user: User):
    """Test abandoning a session."""
    session = await session_manager.start_session(db, test_user.id, "interview_practice")

    abandoned = await session_manager.abandon_session(db, session.id)
    assert abandoned.status == "abandoned"
    assert abandoned.completed_at is not None

    # Try to abandon again - should fail
    with pytest.raises(ValueError, match="Cannot abandon session"):
        await session_manager.abandon_session(db, session.id)


@pytest.mark.asyncio
async def test_progress_updates(db: AsyncSession, test_user: User):
    """Test updating session progress."""
    session = await session_manager.start_session(db, test_user.id, "interview_practice")

    # Update with valid score
    updated = await session_manager.update_session_progress(
        db, session.id, questions_attempted=3, score=80.0
    )
    assert updated.questions_attempted == 3
    assert float(updated.overall_score) == 80.0

    # Update without score
    updated = await session_manager.update_session_progress(db, session.id, questions_attempted=5)
    assert updated.questions_attempted == 5
    assert float(updated.overall_score) == 80.0  # Score unchanged

    # Invalid score - too low
    with pytest.raises(ValueError, match="Score must be between 0 and 100"):
        await session_manager.update_session_progress(
            db, session.id, questions_attempted=5, score=-1
        )

    # Invalid score - too high
    with pytest.raises(ValueError, match="Score must be between 0 and 100"):
        await session_manager.update_session_progress(
            db, session.id, questions_attempted=5, score=101
        )


@pytest.mark.asyncio
async def test_session_queries(db: AsyncSession, test_user: User):
    """Test querying sessions."""
    # Create multiple sessions
    session1 = await session_manager.start_session(db, test_user.id, "interview_practice")
    await session_manager.complete_session(db, session1.id, 85.0)

    session2 = await session_manager.start_session(db, test_user.id, "technical_interview")

    # Get specific session
    retrieved = await session_manager.get_session(db, session1.id)
    assert retrieved is not None
    assert retrieved.id == session1.id
    assert retrieved.status == "completed"

    # List user sessions
    sessions, total = await session_manager.list_user_sessions(db, test_user.id, limit=10, offset=0)
    assert len(sessions) == 2
    assert total == 2
    # Most recent first
    assert sessions[0].id == session2.id
    assert sessions[1].id == session1.id


@pytest.mark.asyncio
async def test_session_pagination(db: AsyncSession, test_user: User):
    """Test session list pagination."""
    # Create 5 sessions
    for i in range(5):
        session = await session_manager.start_session(db, test_user.id, f"session_{i}")
        await session_manager.complete_session(db, session.id, 80.0)

    # Get first page
    sessions, total = await session_manager.list_user_sessions(db, test_user.id, limit=2, offset=0)
    assert len(sessions) == 2
    assert total == 5

    # Get second page
    sessions, total = await session_manager.list_user_sessions(db, test_user.id, limit=2, offset=2)
    assert len(sessions) == 2
    assert total == 5

    # Get last page
    sessions, total = await session_manager.list_user_sessions(db, test_user.id, limit=2, offset=4)
    assert len(sessions) == 1
    assert total == 5


@pytest.mark.asyncio
async def test_cascade_deletion(db: AsyncSession, test_user: User):
    """Test that sessions are deleted when user is deleted."""
    # Create session
    session = await session_manager.start_session(db, test_user.id, "interview_practice")

    # Delete user
    await db.delete(test_user)
    await db.commit()

    # Session should be deleted
    result = await db.execute(select(PracticeSession).where(PracticeSession.id == session.id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_session_score_validation(db: AsyncSession, test_user: User):
    """Test score validation in complete_session."""
    session = await session_manager.start_session(db, test_user.id, "interview_practice")

    # Valid scores
    await session_manager.update_session_progress(db, session.id, 1, score=0.0)
    await session_manager.update_session_progress(db, session.id, 2, score=100.0)
    await session_manager.update_session_progress(db, session.id, 3, score=50.5)

    # Complete with valid score
    completed = await session_manager.complete_session(db, session.id, 75.0)
    assert float(completed.overall_score) == 75.0

    # Start new session for invalid score tests
    session2 = await session_manager.start_session(db, test_user.id, "technical_interview")

    # Invalid completion score
    with pytest.raises(ValueError, match="Score must be between 0 and 100"):
        await session_manager.complete_session(db, session2.id, -5.0)

    with pytest.raises(ValueError, match="Score must be between 0 and 100"):
        await session_manager.complete_session(db, session2.id, 150.0)


@pytest.mark.asyncio
async def test_get_nonexistent_session(db: AsyncSession):
    """Test getting a session that doesn't exist."""
    nonexistent_id = uuid4()
    session = await session_manager.get_session(db, nonexistent_id)
    assert session is None


@pytest.mark.asyncio
async def test_update_nonexistent_session(db: AsyncSession):
    """Test updating a session that doesn't exist."""
    nonexistent_id = uuid4()
    with pytest.raises(ValueError, match="Session not found"):
        await session_manager.update_session_progress(db, nonexistent_id, questions_attempted=5)
