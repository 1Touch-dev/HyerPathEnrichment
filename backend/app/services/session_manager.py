"""Service layer for session management with state machine."""

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFoundError, ValidationAppError
from app.models import InterviewQuestion
from app.modules.sessions.models import PracticeAudioRecording, PracticeSession, QuestionAttempt
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


def _coerce_uuid(user_id: UUID) -> UUID:
    """Coerce ``user_id`` to a real ``uuid.UUID`` instance.

    ``user_id`` is typed as ``UUID`` throughout this module, but is coerced
    defensively at every entry point: the ORM columns bound against it
    (``practice_sessions.user_id``, ``question_attempts.user_id``) are
    ``postgresql.UUID(as_uuid=True)``, which requires a real ``uuid.UUID``
    instance — binding a ``str`` raises
    ``StatementError: 'str' object has no attribute 'hex'``.
    See phase2_module2.md §2.1 Bug 2.
    """
    return user_id if isinstance(user_id, UUID) else UUID(str(user_id))


async def _fetch_question_texts(db: AsyncSession, question_ids: set[UUID]) -> dict[UUID, str]:
    """Batch-fetch `question_text` for a set of question ids in one query.

    `QuestionAttempt` intentionally has no relationship to `InterviewQuestion`
    (different module, see app/models.py's module docstring) — the FK
    (migration 033) exists only for referential integrity, not ORM traversal.
    """
    if not question_ids:
        return {}
    stmt = select(InterviewQuestion.id, InterviewQuestion.question_text).where(
        InterviewQuestion.id.in_(question_ids)
    )
    result = await db.execute(stmt)
    return {row[0]: row[1] for row in result.all()}


async def _serialize_session(db: AsyncSession, session: PracticeSession) -> SessionResponse:
    """Serialize a session, filling in two things `model_validate` can't get
    straight off the ORM instance:

    - `question_text` per attempt, via `_fetch_question_texts` (see its
      docstring — `QuestionAttempt` has no relationship to `InterviewQuestion`).
    - `overall_score`, defaulted to the average of scored attempts when the
      column itself is still NULL. It's a plain nullable column, only ever
      written by an explicit `PATCH .../sessions/{id}` with `overall_score` in
      the body (see `update_session` below). Nothing in this module's automatic
      flow (feedback generation finishing in the background) ever calls that,
      and the frontend has no "finish session" action either — so real practice
      sessions left the report page showing "Pending..." forever even after
      every attempt had a real AI score. Falling back only when the column is
      still NULL keeps existing explicit-PATCH callers (e.g.
      test_session_integration.py) working unchanged, while giving the common
      case (never explicitly PATCHed) a real number as soon as at least one
      attempt has been scored — no session-completion side effects needed.
    """
    question_ids = {a.question_id for a in session.attempts if a.question_id is not None}
    texts = await _fetch_question_texts(db, question_ids)

    response = SessionResponse.model_validate(session)
    for attempt_response in response.attempts:
        if attempt_response.question_id is not None:
            attempt_response.question_text = texts.get(attempt_response.question_id)

    if response.overall_score is None:
        scored = [a.ai_score for a in session.attempts if a.ai_score is not None]
        if scored:
            response.overall_score = round(sum(scored) / len(scored), 2)
    return response


async def _resolve_audio_transcription(
    db: AsyncSession, user_id: UUID, audio_recording_id: UUID
) -> str | None:
    """Look up the completed transcription for an audio attempt, so it can be
    stored as `QuestionAttempt.text_response` and drive feedback generation.

    `POST /api/practice/audio` (practice_audio/service.py's
    `upload_and_process_audio`) transcribes synchronously — by the time the
    frontend gets `audioRecordingId` back and calls `add_attempt`, the
    recording's `transcription_status` is already "completed" or "failed",
    never "processing". Without this lookup, audio attempts never got a
    `text_response`, so `add_attempt`'s "enqueue feedback if text_response"
    check below was always false for them — every audio answer's score/
    feedback stayed "Pending..." forever, silently, with no error anywhere.
    Returns None (rather than raising) for a missing/failed/still-pending
    recording — callers treat that exactly like "no answer text yet".
    """
    stmt = select(
        PracticeAudioRecording.transcription_status, PracticeAudioRecording.transcription
    ).where(
        PracticeAudioRecording.id == audio_recording_id,
        PracticeAudioRecording.user_id == user_id,
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        logger.warning(
            "Audio recording not found for transcription backfill",
            extra={"audio_recording_id": str(audio_recording_id), "user_id": str(user_id)},
        )
        return None
    status, transcription = row
    resolved = transcription if status == "completed" and transcription else None
    # `transcription_status` is safe at INFO; the transcription text itself
    # (candidate's spoken answer) is DEBUG-only.
    logger.info(
        "Resolved audio transcription for attempt",
        extra={
            "audio_recording_id": str(audio_recording_id),
            "transcription_status": status,
            "has_text_response": resolved is not None,
        },
    )
    logger.debug(
        "Resolved audio transcription text",
        extra={"audio_recording_id": str(audio_recording_id), "transcription_text": transcription},
    )
    return resolved


class SessionManager:
    """Manages practice session lifecycle and state transitions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(self, request: SessionCreateRequest, user_id: UUID) -> SessionResponse:
        """Create a new practice session."""
        user_id = _coerce_uuid(user_id)
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
        user_id = _coerce_uuid(user_id)
        stmt = (
            select(PracticeSession)
            .where(PracticeSession.id == session_id, PracticeSession.user_id == user_id)
            .options(selectinload(PracticeSession.attempts))
        )
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            raise NotFoundError(f"Session {session_id} not found")

        return await _serialize_session(self.db, session)

    async def list_sessions(
        self, user_id: UUID, limit: int = 20, offset: int = 0
    ) -> SessionListResponse:
        """List sessions for a user."""
        user_id = _coerce_uuid(user_id)
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
            sessions=[await _serialize_session(self.db, s) for s in sessions],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def update_session(
        self, session_id: UUID, request: SessionUpdateRequest, user_id: UUID
    ) -> SessionResponse:
        """Update session with state machine validation."""
        user_id = _coerce_uuid(user_id)
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
        user_id = _coerce_uuid(user_id)
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
        user_id = _coerce_uuid(user_id)
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

        # Audio attempts arrive with only `audio_recording_id` (see
        # `_resolve_audio_transcription`'s docstring) — backfill `text_response`
        # from the already-transcribed recording so scoring/feedback can run on
        # it exactly like a typed answer.
        text_response = request.text_response
        if request.response_type == "audio" and request.audio_recording_id is not None:
            text_response = await _resolve_audio_transcription(
                self.db, user_id, request.audio_recording_id
            )

        # Create attempt
        attempt = QuestionAttempt(
            id=uuid4(),
            session_id=session_id,
            user_id=user_id,
            question_id=request.question_id,
            response_type=request.response_type,
            text_response=text_response,
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

        response = QuestionAttemptResponse.model_validate(attempt)
        if attempt.question_id is not None:
            texts = await _fetch_question_texts(self.db, {attempt.question_id})
            response.question_text = texts.get(attempt.question_id)
        return response

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
