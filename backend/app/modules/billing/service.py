"""Billing business logic: tier resolution, paywall helpers, Stripe checkout/portal, webhooks."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

import stripe
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.config import get_settings
from app.core.errors import NotFoundError, ValidationAppError
from app.integrations.stripe.client import get_stripe_client
from app.modules.billing import repository
from app.modules.billing.models import UserSubscription
from app.modules.billing.schemas import (
    CheckoutSessionResponse,
    PortalSessionResponse,
    UserSubscriptionResponse,
)
from app.modules.documents.schemas import CvFeedbackResponse

EffectiveTier = Literal["free", "premium"]

MATCH_EXPLANATION_TEASER = "Unlock to see why this role matches you"
CV_STRENGTHS_TEASER = ["Upgrade to unlock personalized CV strengths"]
CV_IMPROVEMENTS_TEASER = ["Upgrade to unlock tailored improvement suggestions"]
CV_METHODOLOGY_TEASER = "Upgrade to see the full ATS scoring methodology"


async def get_effective_tier(db: AsyncSession, user_id: UUID) -> EffectiveTier:
    """Return premium when billing is disabled, or when the user has an active/trialing sub."""
    settings = get_settings()
    if not settings.enable_billing:
        return "premium"

    subscription = await repository.get_subscription_for_user(db, user_id)
    if subscription is None:
        return "free"
    return "premium" if subscription.status in ("active", "trialing") else "free"


def should_blur(tier: EffectiveTier) -> bool:
    return tier == "free"


def blur_match_explanation(
    explanation: str | None, *, tier: EffectiveTier
) -> tuple[str | None, bool]:
    """Return teaser text and is_blurred — never ship real explanation when blurred."""
    if not should_blur(tier):
        return explanation, False
    if explanation:
        return MATCH_EXPLANATION_TEASER, True
    return None, False


def apply_cv_feedback_paywall(
    response: CvFeedbackResponse, *, tier: EffectiveTier
) -> CvFeedbackResponse:
    if not should_blur(tier):
        return response.model_copy(update={"is_blurred": False})
    return response.model_copy(
        update={
            "is_blurred": True,
            "strengths": CV_STRENGTHS_TEASER,
            "improvements": CV_IMPROVEMENTS_TEASER,
            "rewritten_bullets": [],
            "ats_score_methodology": CV_METHODOLOGY_TEASER,
        }
    )


def _subscription_to_response(
    subscription: UserSubscription | None,
    *,
    effective_tier: EffectiveTier,
) -> UserSubscriptionResponse:
    if subscription is None:
        return UserSubscriptionResponse(
            plan_tier="free",
            status="none",
            current_period_end=None,
            stripe_customer_id=None,
            stripe_subscription_id=None,
            effective_tier=effective_tier,
        )
    return UserSubscriptionResponse(
        plan_tier=subscription.plan_tier,
        status=subscription.status,
        current_period_end=subscription.current_period_end,
        stripe_customer_id=subscription.stripe_customer_id,
        stripe_subscription_id=subscription.stripe_subscription_id,
        effective_tier=effective_tier,
    )


async def get_subscription_status(db: AsyncSession, user_id: UUID) -> UserSubscriptionResponse:
    tier = await get_effective_tier(db, user_id)
    subscription = await repository.get_subscription_for_user(db, user_id)
    return _subscription_to_response(subscription, effective_tier=tier)


async def create_checkout_session_for_user(
    db: AsyncSession,
    user: User,
    *,
    success_url: str,
    cancel_url: str,
) -> CheckoutSessionResponse:
    settings = get_settings()
    if not settings.enable_billing:
        raise ValidationAppError("Billing is not enabled")

    stripe_client = get_stripe_client()
    subscription = await repository.get_subscription_for_user(db, user.id)
    if subscription is not None:
        customer_id = subscription.stripe_customer_id
    else:
        # Persist immediately so repeat Upgrade clicks reuse this customer instead of
        # orphaning a new Stripe Customer on every abandoned checkout attempt.
        customer_id = await stripe_client.create_customer(user_id=user.id, email=user.email)
        await repository.create_subscription(
            db,
            user_id=user.id,
            stripe_customer_id=customer_id,
            plan_tier="free",
            status="incomplete",
        )

    url = await stripe_client.create_checkout_session(
        customer_id=customer_id,
        price_id=settings.stripe_price_id_premium,
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=str(user.id),
    )
    return CheckoutSessionResponse(url=url)


async def create_portal_session_for_user(
    db: AsyncSession,
    user: User,
    *,
    return_url: str,
) -> PortalSessionResponse:
    settings = get_settings()
    if not settings.enable_billing:
        raise ValidationAppError("Billing is not enabled")

    subscription = await repository.get_subscription_for_user(db, user.id)
    if subscription is None:
        raise NotFoundError("No billing account found")

    stripe_client = get_stripe_client()
    url = await stripe_client.create_billing_portal_session(
        customer_id=subscription.stripe_customer_id,
        return_url=return_url,
    )
    return PortalSessionResponse(url=url)


def _stripe_ts_to_datetime(value: int | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=UTC)


def _plan_tier_from_stripe_status(status: str) -> str:
    return "premium" if status in ("active", "trialing") else "free"


def _stripe_obj_get(obj: Any, key: str) -> Any:
    """Read a field from a Stripe object or plain dict webhook payload."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _period_end_from_subscription(subscription_obj: Any) -> int | None:
    """Basil stores current_period_end on items.data[0]; older APIs use the top-level field."""
    items = _stripe_obj_get(subscription_obj, "items")
    if isinstance(items, dict):
        data = items.get("data") or []
    else:
        data = getattr(items, "data", None) or []

    if data:
        item_period_end = _stripe_obj_get(data[0], "current_period_end")
        if item_period_end is not None:
            return int(item_period_end)

    top_level = _stripe_obj_get(subscription_obj, "current_period_end")
    if top_level is None:
        return None
    return int(top_level)


async def handle_webhook_event(db: AsyncSession, event: stripe.Event) -> None:
    event_type = event.type
    data_object = event.data.object

    if event_type == "checkout.session.completed":
        await _handle_checkout_session_completed(db, data_object)
    elif event_type == "customer.subscription.updated":
        await _handle_subscription_updated(db, data_object)
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(db, data_object)


async def _handle_checkout_session_completed(db: AsyncSession, session: Any) -> None:
    client_reference_id = _stripe_obj_get(session, "client_reference_id")
    if not client_reference_id:
        return

    user_id = UUID(str(client_reference_id))
    customer_id = _stripe_obj_get(session, "customer")
    subscription_id = _stripe_obj_get(session, "subscription")
    if not customer_id:
        return

    existing = await repository.get_subscription_for_user(db, user_id)
    if existing is not None:
        await repository.update_subscription(
            db,
            existing,
            stripe_subscription_id=str(subscription_id) if subscription_id else None,
            plan_tier="premium",
            status="active",
        )
        return

    await repository.create_subscription(
        db,
        user_id=user_id,
        stripe_customer_id=str(customer_id),
        stripe_subscription_id=str(subscription_id) if subscription_id else None,
        plan_tier="premium",
        status="active",
    )


async def _handle_subscription_updated(db: AsyncSession, subscription_obj: Any) -> None:
    customer_id = _stripe_obj_get(subscription_obj, "customer")
    if not customer_id:
        return

    db_sub = await repository.get_subscription_by_stripe_customer_id(db, str(customer_id))
    if db_sub is None:
        return

    status = _stripe_obj_get(subscription_obj, "status")
    sub_id = _stripe_obj_get(subscription_obj, "id")
    period_end = _period_end_from_subscription(subscription_obj)

    await repository.update_subscription(
        db,
        db_sub,
        stripe_subscription_id=str(sub_id) if sub_id else None,
        status=str(status),
        plan_tier=_plan_tier_from_stripe_status(str(status)),
        current_period_end=_stripe_ts_to_datetime(period_end),
    )


async def _handle_subscription_deleted(db: AsyncSession, subscription_obj: Any) -> None:
    customer_id = _stripe_obj_get(subscription_obj, "customer")
    if not customer_id:
        return

    db_sub = await repository.get_subscription_by_stripe_customer_id(db, str(customer_id))
    if db_sub is None:
        return

    await repository.update_subscription(
        db,
        db_sub,
        status="canceled",
        plan_tier="free",
    )
