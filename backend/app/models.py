"""SQLAlchemy models for the interview question bank.

Defines database models for:
- InterviewQuestion: Question bank with filtering and rotation
- InterviewAttempt: User attempts for recency tracking
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, JsonDoc

# PostgreSQL: native TEXT[] array (see migration 016). SQLite: JSON-encoded TEXT,
# transparently (de)serialized to/from a Python list by SQLAlchemy's JSON type.
StringArray = postgresql.ARRAY(String).with_variant(JSON(), "sqlite")


class InterviewQuestion(Base):
    """Interview question with metadata for smart selection."""

    __tablename__ = "interview_questions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_category: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # behavioral, technical, system_design
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)  # easy, medium, hard

    job_roles: Mapped[list[str]] = mapped_column(StringArray, nullable=False)
    technologies: Mapped[list[str]] = mapped_column(StringArray, nullable=False)

    sample_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    scoring_rubric: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc, nullable=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    # Personalization (migration 033, phase2_module3.md Decision 1). NULL means
    # this question is shared across the general rotation pool; set means it
    # was generated for one candidate's résumé and must be excluded from
    # everyone else's selection (see question_selector.py's leak guard).
    personalized_for_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    generation_context: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<InterviewQuestion(id={self.id}, category={self.question_category}, "
            f"difficulty={self.difficulty})>"
        )


class InterviewAttempt(Base):
    """Tracks user attempts to avoid repeating recent questions."""

    __tablename__ = "interview_attempts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(nullable=False)  # Foreign key not enforced for now
    question_id: Mapped[UUID] = mapped_column(ForeignKey("interview_questions.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    def __repr__(self) -> str:
        return (
            f"<InterviewAttempt(id={self.id}, user_id={self.user_id}, "
            f"question_id={self.question_id})>"
        )
