"""Data-access layer for billing. Plain async functions, not a class -- matches
app/modules/staff_invites/repository.py's style. `get_subscription_for_user`,
`event_already_processed`, and `mark_event_processed` are named exactly this way
per task-orchestration/post-tenancy-features/01-billing-stripe-integration.md --
the (not-yet-built) webhook_router.py/service.py call them by these exact names."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.models import StripeWebhookEvent, UserSubscription


async def get_subscription_for_user(db: AsyncSession, user_id: UUID) -> UserSubscription | None:
    """The at-most-one UserSubscription row for this candidate, if any. Absence
    means free tier -- see models.py's UserSubscription docstring."""
    result = await db.execute(select(UserSubscription).where(UserSubscription.user_id == user_id))
    return result.scalar_one_or_none()


async def get_subscription_by_stripe_customer_id(
    db: AsyncSession, stripe_customer_id: str
) -> UserSubscription | None:
    result = await db.execute(
        select(UserSubscription).where(UserSubscription.stripe_customer_id == stripe_customer_id)
    )
    return result.scalar_one_or_none()


async def create_subscription(
    db: AsyncSession,
    *,
    user_id: UUID,
    stripe_customer_id: str,
    stripe_subscription_id: str | None = None,
    plan_tier: str = "free",
    status: str = "active",
    current_period_end: datetime | None = None,
) -> UserSubscription:
    subscription = UserSubscription(
        id=uuid4(),
        user_id=user_id,
        stripe_customer_id=stripe_customer_id,
        stripe_subscription_id=stripe_subscription_id,
        plan_tier=plan_tier,
        status=status,
        current_period_end=current_period_end,
    )
    db.add(subscription)
    await db.commit()
    await db.refresh(subscription)
    return subscription


async def update_subscription(
    db: AsyncSession,
    subscription: UserSubscription,
    *,
    stripe_subscription_id: str | None = None,
    plan_tier: str | None = None,
    status: str | None = None,
    current_period_end: datetime | None = None,
) -> UserSubscription:
    """Partial update -- only explicitly-passed (non-None) fields are changed.
    Used by the (deferred) webhook handlers syncing Stripe's own subscription
    state onto this read-side cache."""
    if stripe_subscription_id is not None:
        subscription.stripe_subscription_id = stripe_subscription_id
    if plan_tier is not None:
        subscription.plan_tier = plan_tier
    if status is not None:
        subscription.status = status
    if current_period_end is not None:
        subscription.current_period_end = current_period_end
    subscription.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(subscription)
    return subscription


async def event_already_processed(db: AsyncSession, stripe_event_id: str) -> bool:
    """Idempotency check -- Stripe explicitly documents at-least-once delivery, so
    the same event.id may be delivered more than once. See models.py's
    StripeWebhookEvent docstring."""
    result = await db.execute(
        select(StripeWebhookEvent).where(StripeWebhookEvent.stripe_event_id == stripe_event_id)
    )
    return result.scalar_one_or_none() is not None


async def mark_event_processed(
    db: AsyncSession, stripe_event_id: str, event_type: str
) -> StripeWebhookEvent:
    event = StripeWebhookEvent(stripe_event_id=stripe_event_id, event_type=event_type)
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event
