"""Human-in-the-loop LinkedIn sourcing/scouting lead log. See this file's parent
directory's 12-linkedin-sourcing-intern-multilogin.md for why this is a manual
data-entry form filled out by a human who read a LinkedIn profile themselves, and
NEVER a scraper — that file's legal-risk section is the most important thing to
read before touching this module."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class SourcedCandidateLead(Base):
    __tablename__ = "sourced_candidate_leads"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # The intern who manually observed and typed in this lead. Never NULL — every
    # row must be attributable to a specific human who actually looked at the
    # profile, both for accountability and because "who sourced this" is itself
    # useful recruiting-ops data.
    sourced_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    headline: Mapped[str | None] = mapped_column(String(500), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linkedin_profile_url: Mapped[str] = mapped_column(String(512), nullable=False)
    target_role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="new", nullable=False, index=True
    )  # "new" | "reviewed" | "contacted" | "dismissed"
    reviewed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
