"""ORM model for interview scheduling (Module 4, Module D)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class InterviewSchedule(Base):
    """One row per JobMatch, enforced by a UNIQUE constraint on job_match_id — v1
    is deliberately single-schedule-per-match ("when is *the* interview for this
    application"), not a multi-round interview tracker (phone screen -> onsite ->
    offer as separate rows). Rescheduling reuses the same row (schedule_interview
    is an upsert, see repository.upsert_schedule). Multi-round support is a real
    future need (most real interview loops have 2-4 rounds) but is explicitly out
    of scope for this plan — the UNIQUE constraint below is the honest reflection
    of that scope cut, not an oversight. Revisiting this later means dropping the
    constraint and adding a round_number/round_label column; not done now to avoid
    building UI (a whole "rounds" list view) nobody asked for yet.
    """

    __tablename__ = "interview_schedules"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_match_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_matches.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reminder_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=lambda: datetime.now(UTC)
    )
