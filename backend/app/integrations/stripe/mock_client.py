"""In-process Stripe stand-in for local billing without hitting Stripe's API.

Checkout and portal URLs point at backend mock pages. Webhook signature
verification still uses the real ``stripe.Webhook.construct_event``.
``STRIPE_API_BASE`` is ignored in mock mode (it is a live-client hook).
"""

from __future__ import annotations

import os
from typing import cast
from urllib.parse import urlencode
from uuid import UUID, uuid4

import stripe

from app.core.config import get_settings

_MOCK_CHECKOUT_SESSIONS: dict[str, dict[str, str]] = {}


def _public_base() -> str:
    return os.environ.get("STRIPE_MOCK_PUBLIC_BASE", "http://127.0.0.1:8000").rstrip("/")


def get_mock_checkout_session(session_id: str) -> dict[str, str] | None:
    """Return the stored mock checkout session, or ``None`` if unknown."""
    return _MOCK_CHECKOUT_SESSIONS.get(session_id)


def clear_mock_sessions() -> None:
    """Drop all in-memory mock checkout sessions (tests)."""
    _MOCK_CHECKOUT_SESSIONS.clear()


class MockStripeClient:
    """Same four methods as ``StripeClient``, without setting Stripe SDK globals."""

    async def create_customer(self, *, user_id: UUID, email: str) -> str:
        return f"cus_mock_{uuid4().hex}"

    async def create_checkout_session(
        self,
        *,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        client_reference_id: str,
    ) -> str:
        session_id = f"cs_mock_{uuid4().hex}"
        _MOCK_CHECKOUT_SESSIONS[session_id] = {
            "customer_id": customer_id,
            "price_id": price_id,
            "success_url": success_url,
            "cancel_url": cancel_url,
            "client_reference_id": client_reference_id,
        }
        return f"{_public_base()}/api/billing/mock/checkout?session_id={session_id}"

    async def create_billing_portal_session(self, *, customer_id: str, return_url: str) -> str:
        query = urlencode({"customer_id": customer_id, "return_url": return_url})
        return f"{_public_base()}/api/billing/mock/portal?{query}"

    def verify_webhook_signature(self, payload: bytes, signature_header: str) -> stripe.Event:
        settings = get_settings()
        webhook_secret = settings.stripe_webhook_secret.get_secret_value()
        event = stripe.Webhook.construct_event(
            payload,
            signature_header,
            webhook_secret,
            api_key=settings.stripe_secret_key.get_secret_value(),
        )
        return cast("stripe.Event", event)
