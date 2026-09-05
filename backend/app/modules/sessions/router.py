"""API router for session tracking endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.sessions.schemas import (
    QuestionAttemptRequest,
    QuestionAttemptResponse,
    SessionCreateRequest,
    SessionListResponse,
    SessionResponse,
    SessionUpdateRequest,
)
from app.services.session_manager import get_session_manager

router = APIRouter(prefix="/sessions", tags=["sessions"], route_class=EnvelopeAPIRoute)


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    request: SessionCreateRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> SessionResponse:
    """Create a new practice session."""
    manager = get_session_manager(db)
    return await manager.create_session(request, user_id=current_user.id)


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    current_user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> SessionListResponse:
    """List all sessions for the current user."""
    manager = get_session_manager(db)
    return await manager.list_sessions(user_id=current_user.id, limit=limit, offset=offset)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> SessionResponse:
    """Get a specific session with all attempts."""
    manager = get_session_manager(db)
    return await manager.get_session(session_id, user_id=current_user.id)


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: UUID,
    request: SessionUpdateRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> SessionResponse:
    """Update session status or metrics."""
    manager = get_session_manager(db)
    return await manager.update_session(session_id, request, user_id=current_user.id)


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a session and all its attempts."""
    manager = get_session_manager(db)
    await manager.delete_session(session_id, user_id=current_user.id)


@router.post("/{session_id}/attempts", response_model=QuestionAttemptResponse, status_code=201)
async def add_attempt(
    session_id: UUID,
    request: QuestionAttemptRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> QuestionAttemptResponse:
    """Add a question attempt to a session."""
    manager = get_session_manager(db)
    return await manager.add_attempt(session_id, request, user_id=current_user.id)
