"""Stripe webhook route tests — signature rejection, idempotency, real signature verify."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import stripe
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.password import hash_password
from app.core.config import get_settings
from app.modules.billing.models import StripeWebhookEvent, UserSubscription


def _stripe_signature_header(payload: bytes, secret: str) -> str:
    """Build a valid Stripe-Signature header for ``secret`` (no live Stripe account needed)."""
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload.decode('utf-8')}".encode()
    signature = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


def test_webhook_rejects_missing_signature(client: TestClient) -> None:
    with patch("app.modules.billing.webhook_router.get_stripe_client") as mock_factory:
        mock_factory.return_value.verify_webhook_signature.side_effect = (
            stripe.SignatureVerificationError("bad sig", "sig_header")
        )
        response = client.post(
            "/api/billing/webhooks/stripe",
            content=b"{}",
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 400


def test_webhook_rejects_invalid_real_signature(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise real ``construct_event`` path — bad signature must 400 without mocking verify."""
    settings = get_settings()
    monkeypatch.setattr(settings, "stripe_secret_key", SecretStr("sk_test_local"))
    monkeypatch.setattr(settings, "stripe_webhook_secret", SecretStr("whsec_test_local_secret"))

    response = client.post(
        "/api/billing/webhooks/stripe",
        content=b'{"id":"evt_bad"}',
        headers={
            "Content-Type": "application/json",
            "stripe-signature": "t=1,v1=deadbeef",
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_webhook_accepts_real_signed_checkout_session_completed(
    client: TestClient,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Full webhook route with a locally signed Stripe-shaped payload (no Stripe CLI/keys)."""
    webhook_secret = "whsec_test_real_sig_verify"
    settings = get_settings()
    monkeypatch.setattr(settings, "stripe_secret_key", SecretStr("sk_test_local"))
    monkeypatch.setattr(settings, "stripe_webhook_secret", SecretStr(webhook_secret))

    user = User(
        email=f"webhook-real-{uuid4().hex[:8]}@example.com",
        first_name="Hook",
        last_name="Real",
        hashed_password=hash_password("password123"),
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    event_id = f"evt_{uuid4().hex}"
    customer_id = f"cus_{uuid4().hex[:12]}"
    subscription_id = f"sub_{uuid4().hex[:12]}"
    payload = json.dumps(
        {
            "id": event_id,
            "object": "event",
            "api_version": "2024-06-20",
            "created": int(time.time()),
            "livemode": False,
            "pending_webhooks": 1,
            "request": {"id": None, "idempotency_key": None},
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": f"cs_{uuid4().hex[:12]}",
                    "object": "checkout.session",
                    "client_reference_id": str(user.id),
                    "customer": customer_id,
                    "subscription": subscription_id,
                    "mode": "subscription",
                    "status": "complete",
                }
            },
        }
    ).encode("utf-8")

    response = client.post(
        "/api/billing/webhooks/stripe",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "stripe-signature": _stripe_signature_header(payload, webhook_secret),
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "processed"

    result = await db.execute(select(UserSubscription).where(UserSubscription.user_id == user.id))
    sub = result.scalar_one_or_none()
    assert sub is not None
    assert sub.stripe_customer_id == customer_id
    assert sub.stripe_subscription_id == subscription_id
    assert sub.status == "active"
    assert sub.plan_tier == "premium"

    ledger = await db.execute(
        select(StripeWebhookEvent).where(StripeWebhookEvent.stripe_event_id == event_id)
    )
    assert ledger.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_webhook_idempotent_on_duplicate_event_id(
    client: TestClient,
    db: AsyncSession,
) -> None:
    user = User(
        email=f"webhook-{uuid4().hex[:8]}@example.com",
        first_name="Hook",
        last_name="Test",
        hashed_password=hash_password("password123"),
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    event_id = f"evt_{uuid4().hex}"
    fake_event = MagicMock()
    fake_event.id = event_id
    fake_event.type = "checkout.session.completed"
    fake_event.data.object = {
        "client_reference_id": str(user.id),
        "customer": f"cus_{uuid4().hex[:8]}",
        "subscription": f"sub_{uuid4().hex[:8]}",
    }

    payload = json.dumps({"id": event_id}).encode()

    with patch("app.modules.billing.webhook_router.get_stripe_client") as mock_factory:
        mock_factory.return_value.verify_webhook_signature.return_value = fake_event

        first = client.post(
            "/api/billing/webhooks/stripe",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "stripe-signature": "test_sig",
            },
        )
        second = client.post(
            "/api/billing/webhooks/stripe",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "stripe-signature": "test_sig",
            },
        )

    assert first.status_code == 200
    assert first.json()["status"] == "processed"
    assert second.status_code == 200
    assert second.json()["status"] == "already_processed"

    result = await db.execute(select(UserSubscription).where(UserSubscription.user_id == user.id))
    assert result.scalar_one_or_none() is not None

    ledger = await db.execute(
        select(StripeWebhookEvent).where(StripeWebhookEvent.stripe_event_id == event_id)
    )
    assert ledger.scalar_one_or_none() is not None


def _assert_period_end_unix(actual: datetime | None, expected_unix: int) -> None:
    """Compare stored period end to a unix timestamp (SQLite may drop tzinfo)."""
    assert actual is not None
    aware = actual if actual.tzinfo is not None else actual.replace(tzinfo=UTC)
    assert int(aware.timestamp()) == expected_unix


async def _seed_user_subscription(
    db: AsyncSession,
    *,
    status: str,
    plan_tier: str,
) -> tuple[User, str]:
    user = User(
        email=f"webhook-period-{uuid4().hex[:8]}@example.com",
        first_name="Hook",
        last_name="Period",
        hashed_password=hash_password("password123"),
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    customer_id = f"cus_{uuid4().hex[:12]}"
    db.add(
        UserSubscription(
            user_id=user.id,
            stripe_customer_id=customer_id,
            status=status,
            plan_tier=plan_tier,
            current_period_end=None,
        )
    )
    await db.commit()
    return user, customer_id


def _signed_stripe_event_bytes(
    event_type: str,
    data_object: dict,
    *,
    event_id: str,
) -> bytes:
    return json.dumps(
        {
            "id": event_id,
            "object": "event",
            "api_version": "2024-06-20",
            "created": int(time.time()),
            "livemode": False,
            "pending_webhooks": 1,
            "request": {"id": None, "idempotency_key": None},
            "type": event_type,
            "data": {"object": data_object},
        }
    ).encode("utf-8")


def _enable_signed_webhooks(monkeypatch: pytest.MonkeyPatch, webhook_secret: str) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "stripe_secret_key", SecretStr("sk_test_local"))
    monkeypatch.setattr(settings, "stripe_webhook_secret", SecretStr(webhook_secret))


@pytest.mark.asyncio
async def test_webhook_subscription_updated_basil_period_end(
    client: TestClient,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Basil payloads put current_period_end on items.data[0], not the subscription root."""
    webhook_secret = "whsec_test_basil_period_end"
    _enable_signed_webhooks(monkeypatch, webhook_secret)

    user, customer_id = await _seed_user_subscription(db, status="incomplete", plan_tier="free")
    user_id = user.id
    subscription_id = f"sub_{uuid4().hex[:12]}"
    now = int(time.time())
    period_end = now + 30 * 24 * 3600
    period_start = period_end - 30 * 24 * 3600
    event_id = f"evt_{uuid4().hex}"

    subscription_object = {
        "id": subscription_id,
        "object": "subscription",
        "customer": customer_id,
        "status": "active",
        "items": {
            "object": "list",
            "data": [
                {
                    "id": "si_1",
                    "object": "subscription_item",
                    "current_period_end": period_end,
                    "current_period_start": period_start,
                }
            ],
        },
    }
    assert "current_period_end" not in subscription_object

    payload = _signed_stripe_event_bytes(
        "customer.subscription.updated",
        subscription_object,
        event_id=event_id,
    )
    response = client.post(
        "/api/billing/webhooks/stripe",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "stripe-signature": _stripe_signature_header(payload, webhook_secret),
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "processed"

    db.expire_all()
    result = await db.execute(select(UserSubscription).where(UserSubscription.user_id == user_id))
    sub = result.scalar_one()
    _assert_period_end_unix(sub.current_period_end, period_end)
    assert sub.status == "active"
    assert sub.plan_tier == "premium"
    assert sub.stripe_subscription_id == subscription_id


@pytest.mark.asyncio
async def test_webhook_subscription_updated_legacy_top_level_period_end(
    client: TestClient,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Older Stripe API versions still send current_period_end on the subscription itself."""
    webhook_secret = "whsec_test_legacy_period_end"
    _enable_signed_webhooks(monkeypatch, webhook_secret)

    user, customer_id = await _seed_user_subscription(db, status="incomplete", plan_tier="free")
    user_id = user.id
    subscription_id = f"sub_{uuid4().hex[:12]}"
    period_end = int(time.time()) + 30 * 24 * 3600
    event_id = f"evt_{uuid4().hex}"

    payload = _signed_stripe_event_bytes(
        "customer.subscription.updated",
        {
            "id": subscription_id,
            "object": "subscription",
            "customer": customer_id,
            "status": "active",
            "current_period_end": period_end,
            "items": {"object": "list", "data": []},
        },
        event_id=event_id,
    )
    response = client.post(
        "/api/billing/webhooks/stripe",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "stripe-signature": _stripe_signature_header(payload, webhook_secret),
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "processed"

    db.expire_all()
    result = await db.execute(select(UserSubscription).where(UserSubscription.user_id == user_id))
    sub = result.scalar_one()
    _assert_period_end_unix(sub.current_period_end, period_end)


@pytest.mark.asyncio
async def test_webhook_subscription_deleted_sets_canceled_free(
    client: TestClient,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    webhook_secret = "whsec_test_sub_deleted"
    _enable_signed_webhooks(monkeypatch, webhook_secret)

    user, customer_id = await _seed_user_subscription(db, status="active", plan_tier="premium")
    user_id = user.id
    event_id = f"evt_{uuid4().hex}"
    payload = _signed_stripe_event_bytes(
        "customer.subscription.deleted",
        {
            "id": f"sub_{uuid4().hex[:12]}",
            "object": "subscription",
            "customer": customer_id,
            "status": "canceled",
        },
        event_id=event_id,
    )
    response = client.post(
        "/api/billing/webhooks/stripe",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "stripe-signature": _stripe_signature_header(payload, webhook_secret),
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "processed"

    db.expire_all()
    result = await db.execute(select(UserSubscription).where(UserSubscription.user_id == user_id))
    sub = result.scalar_one()
    assert sub.status == "canceled"
    assert sub.plan_tier == "free"
