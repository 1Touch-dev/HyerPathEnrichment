"""Human-in-the-loop LinkedIn send task queue, plus an opt-in automated-batch mode
with a human trigger. See this file's parent directory's 06-linkedin-outreach-send.md
for the legal-risk rationale for why this is a task queue for a human operator by
default, and why the batch mode still requires a human to explicitly start it and
caps sends with a hard per-day ceiling rather than running unattended and unbounded.

Neither this file nor any other file in this module imports from or extends
app.integrations.linkedin.client or app.integrations.multilogin.profile_pool — the
actual mechanism that would perform an automated click on linkedin.com is explicitly
out of scope here (see the plan's "Track 06 — updated scope" section)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class LinkedInSendBatch(Base):
    """An operator-triggered batch of LinkedInSendTask rows to be worked through by
    the (out-of-scope, not-yet-designed) automated mechanism, subject to a hard
    per-day send ceiling per Multilogin profile. Creating a batch does not start it —
    a separate human action (`POST .../start`) is required, and the worker halts at
    `max_sends_per_day` rather than treating it as a soft target."""

    __tablename__ = "linkedin_send_batches"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    triggered_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Identifies which Multilogin browser profile this batch's sends-today ceiling
    # is tracked against. Stored as a plain string identifier only — this module
    # never looks up, authenticates, or drives that profile itself.
    multilogin_profile_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False, index=True
    )  # "pending" | "running" | "completed" | "cancelled" | "failed"
    # Required, not optional: no unlimited option. A hard technical ceiling, not a
    # suggestion — enforced by the worker job, not just documented here.
    max_sends_per_day: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class LinkedInSendTask(Base):
    __tablename__ = "linkedin_send_tasks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    outreach_message_id: Mapped[UUID] = mapped_column(
        ForeignKey("outreach_messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # NULL = existing manual-mode behavior (a human operator claims/completes/skips
    # this task themselves, unaffected by batch mode). Set only when this task was
    # attached to a LinkedInSendBatch via the batch endpoints.
    batch_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("linkedin_send_batches.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # The recipient's LinkedIn profile URL the operator should navigate to. Required —
    # unlike email, there is no other recipient identifier for this task type.
    linkedin_profile_url: Mapped[str] = mapped_column(String(512), nullable=False)
    action_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "connection_request" | "inmail" | "direct_message"
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False, index=True
    )  # "pending" | "claimed" | "completed" | "skipped"
    claimed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Operator's own note on outcome, e.g. "sent", "profile no longer exists", "already connected".
    outcome_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
