"""Service layer for session management with state machine."""

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFoundError, ValidationAppError
from app.modules.sessions.models import PracticeSession, QuestionAttempt
from app.modules.sessions.schemas import (
    QuestionAttemptRequest,
    QuestionAttemptResponse,
    SessionCreateRequest,
    SessionListResponse,
    SessionResponse,
    SessionUpdateRequest,
)
from app.workers.queue import enqueue_feedback

logger = logging.getLogger(__name__)

# Valid state transitions for session status
VALID_TRANSITIONS = {
    "pending": {"in_progress", "abandoned"},
    "in_progress": {"completed", "failed", "abandoned"},
    "completed": set(),  # Terminal state
    "failed": set(),  # Terminal state
    "abandoned": set(),  # Terminal state
}


class SessionManager:
    """Manages practice session lifecycle and state transitions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(self, request: SessionCreateRequest, user_id: UUID) -> SessionResponse:
        """Create a new practice session."""
        session = PracticeSession(
            id=uuid4(),
            user_id=user_id,
            session_type=request.session_type,
            status="pending",
            started_at=datetime.now(UTC),
            session_metadata=request.session_metadata,
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session, ["attempts"])

        logger.info(
            "Created session",
            extra={
                "session_id": str(session.id),
                "user_id": str(user_id),
                "session_type": request.session_type,
            },
        )

        return SessionResponse.model_validate(session)

    async def get_session(self, session_id: UUID, user_id: UUID) -> SessionResponse:
        """Get a session by ID with all attempts."""
        stmt = (
            select(PracticeSession)
            .where(PracticeSession.id == session_id, PracticeSession.user_id == user_id)
            .options(selectinload(PracticeSession.attempts))
        )
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            raise NotFoundError(f"Session {session_id} not found")

        return SessionResponse.model_validate(session)

    async def list_sessions(
        self, user_id: UUID, limit: int = 20, offset: int = 0
    ) -> SessionListResponse:
        """List sessions for a user."""
        # Get total count
        count_stmt = select(func.count(PracticeSession.id)).where(
            PracticeSession.user_id == user_id
        )
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar_one()

        # Get sessions
        stmt = (
            select(PracticeSession)
            .where(PracticeSession.user_id == user_id)
            .order_by(PracticeSession.started_at.desc())
            .limit(limit)
            .offset(offset)
            .options(selectinload(PracticeSession.attempts))
        )
        result = await self.db.execute(stmt)
        sessions = result.scalars().all()

        return SessionListResponse(
            sessions=[SessionResponse.model_validate(s) for s in sessions],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def update_session(
        self, session_id: UUID, request: SessionUpdateRequest, user_id: UUID
    ) -> SessionResponse:
        """Update session with state machine validation."""
        stmt = select(PracticeSession).where(
            PracticeSession.id == session_id, PracticeSession.user_id == user_id
        )
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            raise NotFoundError(f"Session {session_id} not found")

        # Validate state transition
        if request.status and request.status != session.status:
            self._validate_transition(session.status, request.status)
            session.status = request.status

            # Set completed_at for terminal states
            if request.status in {"completed", "failed", "abandoned"}:
                session.completed_at = datetime.now(UTC)

        # Update metrics
        if request.questions_attempted is not None:
            session.questions_attempted = request.questions_attempted
        if request.questions_completed is not None:
            session.questions_completed = request.questions_completed
        if request.overall_score is not None:
            session.overall_score = request.overall_score
        if request.session_metadata is not None:
            session.session_metadata = request.session_metadata

        await self.db.commit()
        await self.db.refresh(session, ["attempts"])

        logger.info(
            "Updated session",
            extra={
                "session_id": str(session_id),
                "status": session.status,
                "questions_attempted": session.questions_attempted,
            },
        )

        return SessionResponse.model_validate(session)

    async def delete_session(self, session_id: UUID, user_id: UUID) -> None:
        """Delete a session and all its attempts."""
        stmt = select(PracticeSession).where(
            PracticeSession.id == session_id, PracticeSession.user_id == user_id
        )
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            raise NotFoundError(f"Session {session_id} not found")

        await self.db.delete(session)
        await self.db.commit()

        logger.info("Deleted session", extra={"session_id": str(session_id)})

    async def add_attempt(
        self, session_id: UUID, request: QuestionAttemptRequest, user_id: UUID
    ) -> QuestionAttemptResponse:
        """Add a question attempt to a session."""
        # Verify session exists and belongs to user
        stmt = select(PracticeSession).where(
            PracticeSession.id == session_id, PracticeSession.user_id == user_id
        )
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            raise NotFoundError(f"Session {session_id} not found")

        if session.status not in {"pending", "in_progress"}:
            raise ValidationAppError(f"Cannot add attempts to {session.status} session")

        # Create attempt
        attempt = QuestionAttempt(
            id=uuid4(),
            session_id=session_id,
            user_id=user_id,
            question_id=request.question_id,
            response_type=request.response_type,
            text_response=request.text_response,
            audio_recording_id=request.audio_recording_id,
            ai_score=request.ai_score,
            score_breakdown=request.score_breakdown,
            ai_feedback=request.ai_feedback,
            time_taken_seconds=request.time_taken_seconds,
            attempted_at=datetime.now(UTC),
        )
        self.db.add(attempt)

        # Update session metrics
        session.questions_attempted += 1
        if request.ai_score is not None:
            session.questions_completed += 1

        # Auto-transition to in_progress if still pending
        if session.status == "pending":
            session.status = "in_progress"

        await self.db.commit()
        await self.db.refresh(attempt)

        logger.info(
            "Added attempt",
            extra={
                "session_id": str(session_id),
                "attempt_id": str(attempt.id),
                "response_type": request.response_type,
            },
        )

        # Enqueue feedback generation job if text response exists
        if attempt.text_response:
            try:
                enqueue_feedback(str(attempt.id))
                logger.info(
                    "Enqueued feedback generation job",
                    extra={"attempt_id": str(attempt.id)},
                )
            except Exception as e:
                logger.error(
                    "Failed to enqueue feedback job",
                    extra={
                        "attempt_id": str(attempt.id),
                        "error": str(e),
                    },
                    exc_info=True,
                )

        return QuestionAttemptResponse.model_validate(attempt)

    def _validate_transition(self, from_status: str, to_status: str) -> None:
        """Validate state transition according to state machine."""
        allowed = VALID_TRANSITIONS.get(from_status, set())
        if to_status not in allowed:
            raise ValidationAppError(
                f"Invalid transition from {from_status} to {to_status}. "
                f"Allowed: {allowed or 'none (terminal state)'}"
            )


def get_session_manager(db: AsyncSession) -> SessionManager:
    """Dependency injection for SessionManager."""
    return SessionManager(db)
