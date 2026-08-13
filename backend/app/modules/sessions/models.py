"""Database models for practice session tracking."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, JsonDoc

if TYPE_CHECKING:
    from app.auth.models import User


class PracticeSession(Base):
    """Tracks practice session lifecycle and aggregated metrics."""

    __tablename__ = "practice_sessions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_type: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_progress")
    questions_attempted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    questions_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overall_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    session_metadata: Mapped[dict[str, Any]] = mapped_column(
        JsonDoc,
        nullable=False,
        default=dict,
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="practice_sessions")
    attempts: Mapped[list[QuestionAttempt]] = relationship(
        "QuestionAttempt", back_populates="session", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'failed', 'abandoned')",
            name="check_session_status",
        ),
        CheckConstraint(
            "questions_attempted >= questions_completed",
            name="check_questions_count",
        ),
        CheckConstraint(
            "overall_score IS NULL OR (overall_score >= 0 AND overall_score <= 100)",
            name="check_overall_score_range",
        ),
        Index("idx_sessions_user_status", "user_id", "status"),
        Index("idx_sessions_started", "started_at"),
    )


class QuestionAttempt(Base):
    """Records a single question attempt within a practice session."""

    __tablename__ = "question_attempts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("practice_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    response_type: Mapped[str] = mapped_column(String(20), nullable=False)
    text_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_recording_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    ai_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    score_breakdown: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc, nullable=True)
    ai_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    time_taken_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempt_metadata: Mapped[dict[str, Any]] = mapped_column(
        JsonDoc,
        nullable=False,
        default=dict,
    )
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="question_attempts")
    session: Mapped[PracticeSession] = relationship("PracticeSession", back_populates="attempts")

    __table_args__ = (
        CheckConstraint(
            "response_type IN ('text', 'audio')",
            name="check_response_type",
        ),
        Index("idx_attempts_session", "session_id"),
        Index("idx_attempts_user", "user_id"),
    )
