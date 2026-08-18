"""ORM model for swipe actions. JobMatch/JobPosting are OWNED by Module 1's job_matching module —
imported here read-only, never redefined (Decision 6, RULE.md 'do not duplicate merge/matching logic')."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class JobSwipeAction(Base):
    """One candidate's swipe decision on one Module-1 JobMatch."""

    __tablename__ = "job_swipe_actions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_match_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_matches.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # "right"|"left"|"up"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
