"""Thin async wrapper around the Stripe SDK.

Every blocking Stripe SDK call is dispatched via ``asyncio.to_thread(...)``,
matching the convention used for blocking Selenium calls in
``app.integrations.linkedin.client`` (e.g. ``connect_selenium``,
``scrape_on_driver``). ``verify_webhook_signature`` is the one exception: it
is CPU-bound signature verification, not a blocking network call, so it stays
synchronous per the spec's own ``def`` (not ``async def``) signature.
"""

from __future__ import annotations

import asyncio
from typing import Protocol, cast
from uuid import UUID

import stripe

from app.core.config import get_settings


class StripeClientProtocol(Protocol):
    """Shared surface for the live Stripe wrapper and the in-process mock."""

    async def create_customer(self, *, user_id: UUID, email: str) -> str: ...

    async def create_checkout_session(
        self,
        *,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        client_reference_id: str,
    ) -> str: ...

    async def create_billing_portal_session(self, *, customer_id: str, return_url: str) -> str: ...

    def verify_webhook_signature(self, payload: bytes, signature_header: str) -> stripe.Event: ...


class StripeClient:
    """Wraps the Stripe SDK for customer, checkout, and billing-portal flows."""

    def __init__(self, api_key: str | None = None) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.stripe_secret_key.get_secret_value()
        stripe.api_key = self._api_key
        api_base = settings.stripe_api_base.strip()
        if api_base:
            stripe.api_base = api_base

    async def create_customer(self, *, user_id: UUID, email: str) -> str:
        """Create a Stripe customer for ``user_id`` and return its Stripe customer ID."""
        customer = await asyncio.to_thread(
            stripe.Customer.create,
            email=email,
            metadata={"user_id": str(user_id)},
            api_key=self._api_key,
        )
        return customer.id

    async def create_checkout_session(
        self,
        *,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        client_reference_id: str,
    ) -> str:
        """Create a Checkout Session and return its hosted URL."""
        session = await asyncio.to_thread(
            stripe.checkout.Session.create,
            customer=customer_id,
            client_reference_id=client_reference_id,
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            api_key=self._api_key,
        )
        if session.url is None:
            raise RuntimeError("Stripe checkout session created without a hosted URL")
        return session.url

    async def create_billing_portal_session(self, *, customer_id: str, return_url: str) -> str:
        """Create a Billing Portal session and return its hosted URL."""
        session = await asyncio.to_thread(
            stripe.billing_portal.Session.create,
            customer=customer_id,
            return_url=return_url,
            api_key=self._api_key,
        )
        return session.url

    def verify_webhook_signature(self, payload: bytes, signature_header: str) -> stripe.Event:
        """Verify and construct a Stripe webhook event from the raw request payload."""
        settings = get_settings()
        webhook_secret = settings.stripe_webhook_secret.get_secret_value()
        event = stripe.Webhook.construct_event(
            payload, signature_header, webhook_secret, api_key=self._api_key
        )
        return cast("stripe.Event", event)


def get_stripe_client() -> StripeClientProtocol:
    """Return the live or in-process mock client based on ``STRIPE_MODE``."""
    settings = get_settings()
    if settings.stripe_mode == "mock":
        from app.integrations.stripe.mock_client import MockStripeClient

        return MockStripeClient()
    return StripeClient()
