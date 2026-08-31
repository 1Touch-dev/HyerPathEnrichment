"""ORM model for the AI-agent supervision (audit/oversight) view.

See task-orchestration/machine-2-parallel-tracks/04-rbac-admin-platform.md's
"AI-agent supervision (audit/oversight view)" section (confirmed by
leadership 2026-08-26: "ai agent supervision, of all job applications cvs
eyes"). Kept in its own module rather than `models.py`, per that doc's
explicit allowance.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AiActionAuditLog(Base):
    """Read-only audit trail of autonomous AI actions, for admin oversight (machine-2/04,
    confirmed by leadership 2026-08-26: "ai agent supervision, of all job applications
    cvs eyes"). Rows are written by the acting module itself at the point the action
    executes (see cross-references in 09/10/outreach's own files), never backfilled or
    reconstructed after the fact."""

    __tablename__ = "ai_action_audit_log"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    action_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # "autonomous_apply" | "outreach_draft" | "resume_tailoring"
    candidate_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # The recruiter whose action_mode/request triggered this (may be NULL for a
    # candidate-initiated action, e.g. the candidate's own resume-tailoring request
    # has no recruiter in the loop at all).
    triggered_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Loose FK-by-convention (no DB-level FK constraint, mirroring this module's
    # existing cross-module reference style for recruiter_actions/outreach ids) to
    # whichever row the acting module created for this event — a JobMatch.id for
    # autonomous_apply, an OutreachMessage.id for outreach_draft, or None for
    # resume_tailoring (nothing is persisted to point at, per the tension noted in
    # the source doc).
    related_id: Mapped[UUID | None] = mapped_column(nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)  # short, human-readable
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
