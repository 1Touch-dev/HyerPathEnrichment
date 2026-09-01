"""Stripe webhook route tests — signature rejection, idempotency, real signature verify."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
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
    with patch("app.modules.billing.webhook_router.StripeClient") as mock_cls:
        mock_cls.return_value.verify_webhook_signature.side_effect = (
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

    with patch("app.modules.billing.webhook_router.StripeClient") as mock_cls:
        mock_cls.return_value.verify_webhook_signature.return_value = fake_event

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
