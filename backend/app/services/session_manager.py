"""Session management service for practice sessions."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sessions.models import PracticeSession


async def start_session(db: AsyncSession, user_id: UUID, session_type: str) -> PracticeSession:
    """
    Start a new practice session.

    Args:
        db: Database session
        user_id: User ID
        session_type: Type of session (e.g., "interview", "technical")

    Returns:
        Created PracticeSession

    Raises:
        ValueError: If user already has an active session
    """
    # Check for existing active session
    result = await db.execute(
        select(PracticeSession).where(
            PracticeSession.user_id == user_id,
            PracticeSession.status.in_(["pending", "in_progress"]),
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise ValueError("User already has an active session")

    # Create new session
    session = PracticeSession(
        user_id=user_id,
        session_type=session_type,
        status="in_progress",
        started_at=datetime.now(UTC),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session(db: AsyncSession, session_id: UUID) -> PracticeSession | None:
    """
    Get a practice session by ID.

    Args:
        db: Database session
        session_id: Session ID

    Returns:
        PracticeSession or None if not found
    """
    result = await db.execute(select(PracticeSession).where(PracticeSession.id == session_id))
    return result.scalar_one_or_none()


async def update_session_progress(
    db: AsyncSession,
    session_id: UUID,
    questions_attempted: int,
    score: float | None = None,
) -> PracticeSession:
    """
    Update session progress.

    Args:
        db: Database session
        session_id: Session ID
        questions_attempted: Number of questions attempted
        score: Optional score (0-100 range)

    Returns:
        Updated PracticeSession

    Raises:
        ValueError: If session not found or score out of range
    """
    session = await get_session(db, session_id)
    if not session:
        raise ValueError("Session not found")

    if score is not None and (score < 0 or score > 100):
        raise ValueError("Score must be between 0 and 100")

    session.questions_attempted = questions_attempted
    if score is not None:
        session.overall_score = score

    await db.commit()
    await db.refresh(session)
    return session


async def complete_session(
    db: AsyncSession, session_id: UUID, overall_score: float
) -> PracticeSession:
    """
    Mark session as completed.

    Args:
        db: Database session
        session_id: Session ID
        overall_score: Final score (0-100 range)

    Returns:
        Updated PracticeSession

    Raises:
        ValueError: If session not found, already completed, or score out of range
    """
    session = await get_session(db, session_id)
    if not session:
        raise ValueError("Session not found")

    if session.status not in ["in_progress", "pending"]:
        raise ValueError(f"Cannot complete session with status: {session.status}")

    if overall_score < 0 or overall_score > 100:
        raise ValueError("Score must be between 0 and 100")

    session.status = "completed"
    session.overall_score = overall_score
    session.completed_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(session)
    return session


async def abandon_session(db: AsyncSession, session_id: UUID) -> PracticeSession:
    """
    Mark session as abandoned.

    Args:
        db: Database session
        session_id: Session ID

    Returns:
        Updated PracticeSession

    Raises:
        ValueError: If session not found or already completed
    """
    session = await get_session(db, session_id)
    if not session:
        raise ValueError("Session not found")

    if session.status not in ["in_progress", "pending"]:
        raise ValueError(f"Cannot abandon session with status: {session.status}")

    session.status = "abandoned"
    session.completed_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(session)
    return session


async def list_user_sessions(
    db: AsyncSession,
    user_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[PracticeSession], int]:
    """
    List user's practice sessions.

    Args:
        db: Database session
        user_id: User ID
        limit: Max results per page
        offset: Results offset

    Returns:
        Tuple of (sessions list, total count)
    """
    # Get total count
    count_result = await db.execute(
        select(PracticeSession).where(PracticeSession.user_id == user_id)
    )
    total = len(count_result.all())

    # Get paginated results
    result = await db.execute(
        select(PracticeSession)
        .where(PracticeSession.user_id == user_id)
        .order_by(PracticeSession.started_at.desc())
        .limit(limit)
        .offset(offset)
    )
    sessions = result.scalars().all()
    return list(sessions), total
