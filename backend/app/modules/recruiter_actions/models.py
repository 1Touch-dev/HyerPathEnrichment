"""Recruiter-initiated apply/suggest actions on behalf of a candidate, gated by
users.recruiter_action_mode. See this module's parent directory's
09-recruiter-initiated-apply-and-suggest.md for the full autonomous-vs-
approval_required design."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class PendingRecruiterAction(Base):
    """A recruiter-initiated "apply for candidate" action awaiting the candidate's
    approval (only created when the candidate's recruiter_action_mode ==
    "approval_required" at the time the recruiter acted — approval_required is
    re-checked at approve-time too, see service.py, in case the candidate changed
    their preference in between)."""

    __tablename__ = "pending_recruiter_actions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recruiter_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "apply"
    # Exactly one of job_match_id/manual_job_entry_id, mirroring JobMatch's own
    # ck_job_matches_exactly_one_source convention — a pending apply action always
    # references an existing JobMatch row (created by the normal matching
    # pipeline or a manual entry), it does not fabricate a new job reference.
    job_match_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_matches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False, index=True
    )  # "pending" | "approved" | "rejected" | "cancelled"
    recruiter_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class RoleSuggestion(Base):
    """A recruiter's manual role suggestion to a candidate, for the candidate to
    review. Independent of recruiter_action_mode — always requires candidate
    review, see Goal section."""

    __tablename__ = "role_suggestions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recruiter_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_match_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_matches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recruiter_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False, index=True
    )  # "pending" | "accepted" | "dismissed"
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
