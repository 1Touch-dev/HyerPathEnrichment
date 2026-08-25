"""ORM model for outreach drafts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, JsonDoc


class OutreachMessage(Base):
    """A single AI-drafted (and possibly sent) outreach message."""

    __tablename__ = "outreach_messages"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_match_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("job_matches.id", ondelete="SET NULL"), nullable=True
    )
    recipient_role_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    company_context_used: Mapped[dict[str, Any]] = mapped_column(
        JsonDoc, default=dict, nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    message_type: Mapped[str] = mapped_column(
        String(20), default="email", nullable=False, index=True
    )
    strategy: Mapped[str] = mapped_column(
        String(20), default="direct_pitch", nullable=False, index=True
    )
    referral_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    role_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    seniority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    recipient_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    # CAN-SPAM: set once at send time from the identifier-hash suppression check
    # (app/compliance/suppression.py), not editable after — a message that was
    # suppression-blocked stays blocked even if suppression state later changes,
    # so a recruiter can't "retry" past a real opt-out by re-sending the same draft.
    suppression_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Machine-2/06: required at draft-creation time when message_type == "linkedin"
    # (same conditional-requirement pattern as recipient_email above). Consumed by
    # OutreachService.send_message() -> linkedin_send_service.enqueue_send_task —
    # this is the profile a human operator is shown, never used for any automated
    # action.
    recipient_linkedin_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    custom_instruction: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    # Admin Module (Phase 2 moderation, migration 040): admin can block a message
    # from being sent without deleting it. Enforced in
    # OutreachService.send_message() (service.py), which raises 403 when this
    # flag is set instead of silently allowing the send.
    admin_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class EmployerCompanyTier(Base):
    """A recruiter's manual, human-set classification of a target employer. This is
    NOT auto-computed from any enrichment/scraping signal — it reflects a recruiter's
    own judgment call (e.g. a well-known, high-paying "premium" employer vs. a
    lower-paying staffing/outsourcing shop), and is set/edited explicitly through the
    admin UI, not derived by any background job."""

    __tablename__ = "employer_company_tiers"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # Matches OutreachMessage.company_name's free-text convention — no FK to a
    # dedicated "Company" table, because none exists today (company identity here is
    # a name string, same as everywhere else in this module).
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)  # "premium" | "outsourcing"
    set_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
