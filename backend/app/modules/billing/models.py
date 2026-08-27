"""ORM models for candidate-level freemium billing (Stripe). See
task-orchestration/post-tenancy-features/01-billing-stripe-integration.md's
"Model shift: OrganizationSubscription -> UserSubscription" section: billing in
this product is per-candidate, never per-Brand -- Brand is a presentation-only
storefront (docs/adr/0019-tenancy-model.md) and is never an FK target here."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class UserSubscription(Base):
    """Candidate-level freemium subscription. One row per paying-or-formerly-paying
    User; free/never-subscribed candidates simply have no row here (absence of a
    row means "free tier," not an error state — see service.py's get_effective_tier)."""

    __tablename__ = "user_subscriptions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    stripe_customer_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True
    )
    plan_tier: Mapped[str] = mapped_column(
        String(32), default="free", nullable=False
    )  # "free"|"premium"
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    # Mirrors Stripe's own subscription.status values ("active", "past_due", "canceled",
    # "incomplete", "trialing") rather than inventing a bespoke vocabulary — this table is a
    # read-side cache of Stripe's state, not a system of record competing with Stripe's own.
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class StripeWebhookEvent(Base):
    """Processed-event ledger for webhook idempotency — Stripe explicitly documents
    that the same event may be delivered more than once; this table is the dedup key,
    not an audit log (though it doubles as one). Unchanged in shape from the prior
    org-billing design — idempotency is a property of the webhook transport, not of
    what the event's payload happens to be about."""

    __tablename__ = "stripe_webhook_events"

    stripe_event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
