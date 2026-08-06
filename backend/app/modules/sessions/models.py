"""SQLAlchemy models for practice sessions and question attempts."""

from __future__ import annotations

from datetime import datetime, UTC
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, JsonDoc

if TYPE_CHECKING:
    from app.auth.models import User


class PracticeSession(Base):
    """Practice session for interview practice or job matching workflows."""

    __tablename__ = "practice_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_type: Mapped[str] = mapped_column(nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(
        nullable=False,
        default="in_progress",
    )
    questions_attempted: Mapped[int] = mapped_column(nullable=False, default=0)
    questions_completed: Mapped[int] = mapped_column(nullable=False, default=0)
    overall_score: Mapped[Decimal | None] = mapped_column(nullable=True)
    session_metadata: Mapped[dict] = mapped_column(
        JsonDoc,
        nullable=False,
        default=dict,
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="practice_sessions")
    attempts: Mapped[list["QuestionAttempt"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )

    # Constraints
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
    """Individual question attempt within a practice session."""

    __tablename__ = "question_attempts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("practice_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: Mapped[UUID | None] = mapped_column(nullable=True)
    response_type: Mapped[str] = mapped_column(nullable=False)
    text_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_recording_id: Mapped[UUID | None] = mapped_column(nullable=True)
    ai_score: Mapped[Decimal | None] = mapped_column(nullable=True)
    score_breakdown: Mapped[dict | None] = mapped_column(
        JsonDoc,
        nullable=True,
    )
    ai_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    time_taken_seconds: Mapped[int | None] = mapped_column(nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    attempt_metadata: Mapped[dict | None] = mapped_column(
        JsonDoc,
        nullable=True,
    )

    # Relationships
    session: Mapped["PracticeSession"] = relationship(back_populates="attempts")
    user: Mapped["User"] = relationship(back_populates="question_attempts")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "response_type IN ('text', 'audio')",
            name="check_response_type",
        ),
        Index("idx_attempts_session", "session_id"),
        Index("idx_attempts_user", "user_id"),
    )
