"""API routes for practice sessions."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.sessions.schemas import (
    AttemptCreate,
    AttemptResponse,
    SessionComplete,
    SessionCreate,
    SessionList,
    SessionProgressUpdate,
    SessionResponse,
)
from app.services import session_manager

router = APIRouter(tags=["sessions"], route_class=EnvelopeAPIRoute)


@router.post("/sessions", response_model=SessionResponse, status_code=201)
async def create_session(
    request: SessionCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> SessionResponse:
    """
    Start a new practice session.

    Requires authentication. Only one active session allowed per user.
    """
    try:
        session = await session_manager.start_session(db, current_user.id, request.session_type)
        return SessionResponse.model_validate(session)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> SessionResponse:
    """Get session details by ID."""
    from uuid import UUID

    try:
        session_uuid = UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session ID")

    session = await session_manager.get_session(db, session_uuid)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # Verify ownership
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this session",
        )

    return SessionResponse.model_validate(session)


@router.patch("/sessions/{session_id}/progress", response_model=SessionResponse)
async def update_progress(
    session_id: str,
    request: SessionProgressUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> SessionResponse:
    """Update session progress."""
    from uuid import UUID

    try:
        session_uuid = UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session ID")

    # Verify ownership
    session = await session_manager.get_session(db, session_uuid)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this session",
        )

    try:
        updated_session = await session_manager.update_session_progress(
            db, session_uuid, request.questions_attempted, request.score
        )
        return SessionResponse.model_validate(updated_session)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/sessions/{session_id}/complete", response_model=SessionResponse)
async def complete_session(
    session_id: str,
    request: SessionComplete,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> SessionResponse:
    """Mark session as completed."""
    from uuid import UUID

    try:
        session_uuid = UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session ID")

    # Verify ownership
    session = await session_manager.get_session(db, session_uuid)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this session",
        )

    try:
        completed = await session_manager.complete_session(db, session_uuid, request.overall_score)
        return SessionResponse.model_validate(completed)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/sessions/{session_id}/abandon", response_model=SessionResponse)
async def abandon_session(
    session_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> SessionResponse:
    """Abandon an active session."""
    from uuid import UUID

    try:
        session_uuid = UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session ID")

    # Verify ownership
    session = await session_manager.get_session(db, session_uuid)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this session",
        )

    try:
        abandoned = await session_manager.abandon_session(db, session_uuid)
        return SessionResponse.model_validate(abandoned)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/sessions", response_model=SessionList)
async def list_sessions(
    current_user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> SessionList:
    """List user's practice sessions with pagination."""
    sessions, total = await session_manager.list_user_sessions(db, current_user.id, limit, offset)
    return SessionList(
        sessions=[SessionResponse.model_validate(s) for s in sessions],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/sessions/{session_id}/attempts",
    response_model=AttemptResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_attempt(
    session_id: str,
    attempt_data: AttemptCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> AttemptResponse:
    """Submit a new question attempt for a practice session.

    Creates the attempt record and enqueues a background job for AI feedback generation.

    Args:
        session_id: UUID of the practice session
        attempt_data: Question and answer data
        db: Database session
        current_user: Authenticated user

    Returns:
        Created attempt with initial data (feedback will be added asynchronously)

    Raises:
        404: Session not found or not owned by user
        500: Failed to enqueue feedback job
    """
    from uuid import UUID

    from sqlalchemy import select

    from app.modules.sessions.models import PracticeSession, QuestionAttempt
    from app.workers.queue import enqueue_feedback
    import logging

    logger = logging.getLogger(__name__)

    try:
        session_uuid = UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session ID")

    # Verify session exists and belongs to user
    stmt = select(PracticeSession).where(
        PracticeSession.id == session_uuid,
        PracticeSession.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or access denied",
        )

    # Create attempt
    attempt = QuestionAttempt(
        session_id=session_uuid,
        user_id=current_user.id,
        response_type="text",
        text_response=attempt_data.text_response,
        time_taken_seconds=attempt_data.time_taken_seconds,
        attempt_metadata={"question_text": attempt_data.question_text},
    )

    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)

    logger.info(
        f"Created attempt {attempt.id} for session {session_id}",
        extra={
            "attempt_id": str(attempt.id),
            "session_id": str(session_id),
            "user_id": str(current_user.id),
        },
    )

    # Enqueue feedback generation job
    try:
        enqueue_feedback(str(attempt.id))
    except Exception as e:
        logger.error(
            f"Failed to enqueue feedback for attempt {attempt.id}",
            extra={"error": str(e)},
            exc_info=True,
        )
        # Don't fail the request - attempt is created, feedback will just be missing

    # Update session counters
    session.questions_attempted += 1
    await db.commit()

    return AttemptResponse.from_orm_with_metadata(attempt)


@router.get(
    "/sessions/{session_id}/attempts/{attempt_id}",
    response_model=AttemptResponse,
)
async def get_attempt(
    session_id: str,
    attempt_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> AttemptResponse:
    """Get a question attempt with feedback.

    Feedback may be null if generation is still in progress or failed.

    Args:
        session_id: UUID of the practice session
        attempt_id: UUID of the question attempt
        db: Database session
        current_user: Authenticated user

    Returns:
        Question attempt with feedback (if available)

    Raises:
        404: Attempt not found or not owned by user
    """
    from uuid import UUID

    from sqlalchemy import select

    from app.modules.sessions.models import QuestionAttempt

    try:
        session_uuid = UUID(session_id)
        attempt_uuid = UUID(attempt_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID")

    stmt = select(QuestionAttempt).where(
        QuestionAttempt.id == attempt_uuid,
        QuestionAttempt.session_id == session_uuid,
        QuestionAttempt.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    attempt = result.scalar_one_or_none()

    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attempt not found or access denied",
        )

    return AttemptResponse.from_orm_with_metadata(attempt)


@router.get(
    "/sessions/{session_id}/attempts",
    response_model=list[AttemptResponse],
)
async def list_attempts(
    session_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> list[AttemptResponse]:
    """List all attempts for a practice session.

    Args:
        session_id: UUID of the practice session
        db: Database session
        current_user: Authenticated user

    Returns:
        List of question attempts with feedback

    Raises:
        404: Session not found or not owned by user
    """
    from uuid import UUID

    from sqlalchemy import select

    from app.modules.sessions.models import PracticeSession, QuestionAttempt

    try:
        session_uuid = UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session ID")

    # Verify session exists and belongs to user
    stmt = select(PracticeSession).where(
        PracticeSession.id == session_uuid,
        PracticeSession.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or access denied",
        )

    # Get all attempts for this session
    stmt = (
        select(QuestionAttempt)
        .where(QuestionAttempt.session_id == session_uuid)
        .order_by(QuestionAttempt.attempted_at)
    )
    result = await db.execute(stmt)
    attempts = result.scalars().all()

    return [AttemptResponse.from_orm_with_metadata(attempt) for attempt in attempts]
