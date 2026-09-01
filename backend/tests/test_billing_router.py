"""Billing router tests — checkout, portal, subscription."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.password import hash_password
from app.core.config import get_settings
from app.modules.billing import repository
from tests.envelope_helpers import assert_error, assert_success


@pytest.fixture
async def billing_user(db: AsyncSession) -> User:
    user = User(
        email=f"billing-router-{uuid4().hex[:8]}@example.com",
        first_name="Bill",
        last_name="Candidate",
        hashed_password=hash_password("password123"),
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _enable_billing(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_billing", True)
    monkeypatch.setattr(settings, "stripe_secret_key", SecretStr("sk_test_x"))
    monkeypatch.setattr(settings, "stripe_webhook_secret", SecretStr("whsec_test"))
    monkeypatch.setattr(settings, "stripe_price_id_premium", "price_test")


def _headers(user_id) -> dict[str, str]:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.api_token}",
        "X-Test-User-ID": str(user_id),
    }


def test_subscription_requires_auth(client: TestClient) -> None:
    response = client.get("/api/billing/subscription")
    assert_error(response, 401)


def test_subscription_free_user(client: TestClient, billing_user: User) -> None:
    data = assert_success(
        client.get("/api/billing/subscription", headers=_headers(billing_user.id))
    )
    assert data["plan_tier"] == "free"
    assert data["effective_tier"] == "premium"  # billing disabled in tests by default


@patch("app.modules.billing.service.StripeClient")
@pytest.mark.asyncio
async def test_checkout_session_returns_url_and_persists_incomplete_subscription(
    mock_client_cls: AsyncMock,
    client: TestClient,
    billing_user: User,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_billing(monkeypatch)

    mock_client = mock_client_cls.return_value
    mock_client.create_customer = AsyncMock(return_value="cus_test")
    mock_client.create_checkout_session = AsyncMock(
        return_value="https://checkout.stripe.test/session"
    )

    data = assert_success(
        client.post(
            "/api/billing/checkout-session",
            headers=_headers(billing_user.id),
            json={
                "success_url": "https://app.example/success",
                "cancel_url": "https://app.example/cancel",
            },
        )
    )
    assert data["url"] == "https://checkout.stripe.test/session"
    mock_client.create_customer.assert_awaited_once()

    sub = await repository.get_subscription_for_user(db, billing_user.id)
    assert sub is not None
    assert sub.stripe_customer_id == "cus_test"
    assert sub.status == "incomplete"
    assert sub.plan_tier == "free"
    assert sub.stripe_subscription_id is None


@patch("app.modules.billing.service.StripeClient")
@pytest.mark.asyncio
async def test_repeat_checkout_reuses_existing_stripe_customer(
    mock_client_cls: AsyncMock,
    client: TestClient,
    billing_user: User,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_billing(monkeypatch)

    await repository.create_subscription(
        db,
        user_id=billing_user.id,
        stripe_customer_id="cus_existing",
        plan_tier="free",
        status="incomplete",
    )

    mock_client = mock_client_cls.return_value
    mock_client.create_customer = AsyncMock(return_value="cus_should_not_be_used")
    mock_client.create_checkout_session = AsyncMock(
        return_value="https://checkout.stripe.test/session2"
    )

    data = assert_success(
        client.post(
            "/api/billing/checkout-session",
            headers=_headers(billing_user.id),
            json={
                "success_url": "https://app.example/success",
                "cancel_url": "https://app.example/cancel",
            },
        )
    )
    assert data["url"] == "https://checkout.stripe.test/session2"
    mock_client.create_customer.assert_not_awaited()
    mock_client.create_checkout_session.assert_awaited_once()
    assert mock_client.create_checkout_session.await_args.kwargs["customer_id"] == "cus_existing"


def test_portal_session_404_without_subscription(
    client: TestClient,
    billing_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_billing(monkeypatch)

    response = client.post(
        "/api/billing/portal-session",
        headers=_headers(billing_user.id),
        json={"return_url": "https://app.example/settings"},
    )
    assert_error(response, 404)


@pytest.fixture
async def subscribed_user(db: AsyncSession, billing_user: User) -> User:
    await repository.create_subscription(
        db,
        user_id=billing_user.id,
        stripe_customer_id=f"cus_{uuid4().hex[:8]}",
    )
    return billing_user


@patch("app.modules.billing.service.StripeClient")
def test_portal_session_returns_url(
    mock_client_cls: AsyncMock,
    client: TestClient,
    subscribed_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_billing(monkeypatch)

    mock_client = mock_client_cls.return_value
    mock_client.create_billing_portal_session = AsyncMock(
        return_value="https://billing.stripe.test/portal"
    )

    data = assert_success(
        client.post(
            "/api/billing/portal-session",
            headers=_headers(subscribed_user.id),
            json={"return_url": "https://app.example/settings"},
        )
    )
    assert data["url"] == "https://billing.stripe.test/portal"
