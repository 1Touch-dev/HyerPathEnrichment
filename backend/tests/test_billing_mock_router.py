"""Mock Stripe checkout/portal pages — signed webhooks, premium then cancel."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.password import hash_password
from app.core.config import get_settings
from app.integrations.stripe.mock_client import clear_mock_sessions
from app.modules.billing.models import UserSubscription
from tests.envelope_helpers import assert_success


@pytest.fixture
async def billing_user(db: AsyncSession) -> User:
    user = User(
        email=f"billing-mock-{uuid4().hex[:8]}@example.com",
        first_name="Bill",
        last_name="Mock",
        hashed_password=hash_password("password123"),
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
def _enable_mock_billing(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_billing", True)
    monkeypatch.setattr(settings, "stripe_mode", "mock")
    monkeypatch.setattr(settings, "stripe_secret_key", SecretStr("sk_test_mock"))
    monkeypatch.setattr(settings, "stripe_webhook_secret", SecretStr("whsec_test_local_secret"))
    monkeypatch.setattr(settings, "stripe_price_id_premium", "price_mock_premium")
    clear_mock_sessions()


def _headers(user_id) -> dict[str, str]:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.api_token}",
        "X-Test-User-ID": str(user_id),
    }


def _start_checkout(
    client: TestClient,
    user: User,
    *,
    success_url: str = "https://app.example/success",
    cancel_url: str = "https://app.example/cancel",
) -> tuple[str, str]:
    data = assert_success(
        client.post(
            "/api/billing/checkout-session",
            headers=_headers(user.id),
            json={"success_url": success_url, "cancel_url": cancel_url},
        )
    )
    url = data["url"]
    session_id = parse_qs(urlparse(url).query)["session_id"][0]
    return url, session_id


def test_checkout_session_url_points_at_mock_page(
    client: TestClient,
    billing_user: User,
    _enable_mock_billing: None,
) -> None:
    url, session_id = _start_checkout(client, billing_user)
    assert "/api/billing/mock/checkout" in url
    assert "session_id=" in url
    assert session_id


def test_mock_checkout_page_returns_html(
    client: TestClient,
    billing_user: User,
    _enable_mock_billing: None,
) -> None:
    _url, session_id = _start_checkout(client, billing_user)
    response = client.get(f"/api/billing/mock/checkout?session_id={session_id}")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "Confirm" in response.text
    assert "Cancel" in response.text


def test_confirm_upgrades_to_premium(
    client: TestClient,
    billing_user: User,
    _enable_mock_billing: None,
) -> None:
    _url, session_id = _start_checkout(client, billing_user)
    confirm = client.post(
        "/api/billing/mock/checkout/confirm",
        data={"session_id": session_id},
        follow_redirects=False,
    )
    assert confirm.status_code == 303
    assert confirm.headers["location"] == "https://app.example/success"

    data = assert_success(
        client.get("/api/billing/subscription", headers=_headers(billing_user.id))
    )
    assert data["effective_tier"] == "premium"
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_second_confirm_is_idempotent(
    client: TestClient,
    billing_user: User,
    db: AsyncSession,
    _enable_mock_billing: None,
) -> None:
    _url, session_id = _start_checkout(client, billing_user)
    first = client.post(
        "/api/billing/mock/checkout/confirm",
        data={"session_id": session_id},
        follow_redirects=False,
    )
    second = client.post(
        "/api/billing/mock/checkout/confirm",
        data={"session_id": session_id},
        follow_redirects=False,
    )
    assert first.status_code == 303
    assert second.status_code == 303

    user_id = billing_user.id
    db.expire_all()
    result = await db.execute(select(UserSubscription).where(UserSubscription.user_id == user_id))
    rows = result.scalars().all()
    assert len(rows) == 1

    data = assert_success(client.get("/api/billing/subscription", headers=_headers(user_id)))
    assert data["effective_tier"] == "premium"


def test_portal_cancel_returns_to_free(
    client: TestClient,
    billing_user: User,
    _enable_mock_billing: None,
) -> None:
    _url, session_id = _start_checkout(client, billing_user)
    confirm = client.post(
        "/api/billing/mock/checkout/confirm",
        data={"session_id": session_id},
        follow_redirects=False,
    )
    assert confirm.status_code == 303

    portal = assert_success(
        client.post(
            "/api/billing/portal-session",
            headers=_headers(billing_user.id),
            json={"return_url": "https://app.example/settings"},
        )
    )
    portal_url = portal["url"]
    assert "/api/billing/mock/portal" in portal_url
    query = parse_qs(urlparse(portal_url).query)
    customer_id = query["customer_id"][0]
    return_url = query["return_url"][0]

    cancel = client.post(
        "/api/billing/mock/portal/cancel",
        data={"customer_id": customer_id, "return_url": return_url},
        follow_redirects=False,
    )
    assert cancel.status_code == 303
    assert cancel.headers["location"] == "https://app.example/settings"

    data = assert_success(
        client.get("/api/billing/subscription", headers=_headers(billing_user.id))
    )
    assert data["effective_tier"] == "free"
    assert data["status"] == "canceled"


def test_mock_checkout_404_when_stripe_mode_is_live(client: TestClient) -> None:
    response = client.get("/api/billing/mock/checkout?session_id=x")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_confirm_sets_basil_period_end(
    client: TestClient,
    billing_user: User,
    db: AsyncSession,
    _enable_mock_billing: None,
) -> None:
    _url, session_id = _start_checkout(client, billing_user)
    confirm = client.post(
        "/api/billing/mock/checkout/confirm",
        data={"session_id": session_id},
        follow_redirects=False,
    )
    assert confirm.status_code == 303

    user_id = billing_user.id
    db.expire_all()
    result = await db.execute(select(UserSubscription).where(UserSubscription.user_id == user_id))
    sub = result.scalar_one()
    assert sub.current_period_end is not None
