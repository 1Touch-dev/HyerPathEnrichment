"""Tests for `app.integrations.stripe.client.StripeClient`.

Mocking convention follows `tests/test_linkedin_browser.py`'s pattern for
`app.integrations.linkedin.client` (patch `asyncio.to_thread` in the target
module's namespace and assert it was invoked with the expected target
function/kwargs, rather than letting the real thread-pool dispatch run).

NOTE on the "no hosted URL" test below: it targets `create_checkout_session`
raising `RuntimeError` (not the old bare `assert session.url is not None`)
when Stripe returns a session without a hosted URL. That fix landed via
`fix/stripe-client-bugs` and is merged into this branch; the test passes
against the real, current `client.py`.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import stripe

from app.integrations.stripe.client import StripeClient


@pytest.fixture
def stripe_client() -> StripeClient:
    return StripeClient(api_key="sk_test_dummy")


# ---------------------------------------------------------------------------
# create_customer
# ---------------------------------------------------------------------------


async def test_create_customer_dispatches_via_to_thread_and_returns_customer_id(
    stripe_client: StripeClient,
) -> None:
    user_id = uuid4()
    fake_customer = SimpleNamespace(id="cus_123")

    with (
        patch(
            "app.integrations.stripe.client.asyncio.to_thread", new_callable=AsyncMock
        ) as mock_to_thread,
        patch("stripe.Customer.create") as mock_create,
    ):
        mock_to_thread.return_value = fake_customer
        result = await stripe_client.create_customer(user_id=user_id, email="a@example.com")

    assert result == "cus_123"
    mock_to_thread.assert_awaited_once_with(
        mock_create,
        email="a@example.com",
        metadata={"user_id": str(user_id)},
        api_key="sk_test_dummy",
    )
    # The real SDK call must never run directly on the event loop.
    mock_create.assert_not_called()


# ---------------------------------------------------------------------------
# create_checkout_session
# ---------------------------------------------------------------------------


async def test_create_checkout_session_dispatches_via_to_thread_and_returns_url(
    stripe_client: StripeClient,
) -> None:
    fake_session = SimpleNamespace(url="https://checkout.stripe.com/session/abc")

    with (
        patch(
            "app.integrations.stripe.client.asyncio.to_thread", new_callable=AsyncMock
        ) as mock_to_thread,
        patch("stripe.checkout.Session.create") as mock_create,
    ):
        mock_to_thread.return_value = fake_session
        result = await stripe_client.create_checkout_session(
            customer_id="cus_123",
            price_id="price_123",
            success_url="https://app.example.com/success",
            cancel_url="https://app.example.com/cancel",
            client_reference_id="user-123",
        )

    assert result == "https://checkout.stripe.com/session/abc"
    mock_to_thread.assert_awaited_once_with(
        mock_create,
        customer="cus_123",
        client_reference_id="user-123",
        line_items=[{"price": "price_123", "quantity": 1}],
        mode="subscription",
        success_url="https://app.example.com/success",
        cancel_url="https://app.example.com/cancel",
        api_key="sk_test_dummy",
    )
    mock_create.assert_not_called()


async def test_create_checkout_session_raises_runtime_error_when_no_hosted_url(
    stripe_client: StripeClient,
) -> None:
    """A session with `url=None` must raise `RuntimeError`, not rely on a
    bare `assert` (which is stripped under `-O` and raises the wrong
    exception type otherwise). Fix landed via `fix/stripe-client-bugs`.
    """
    fake_session = SimpleNamespace(url=None)

    with (
        patch(
            "app.integrations.stripe.client.asyncio.to_thread", new_callable=AsyncMock
        ) as mock_to_thread,
        patch("stripe.checkout.Session.create"),
    ):
        mock_to_thread.return_value = fake_session
        with pytest.raises(RuntimeError):
            await stripe_client.create_checkout_session(
                customer_id="cus_123",
                price_id="price_123",
                success_url="https://app.example.com/success",
                cancel_url="https://app.example.com/cancel",
                client_reference_id="user-123",
            )


# ---------------------------------------------------------------------------
# create_billing_portal_session
# ---------------------------------------------------------------------------


async def test_create_billing_portal_session_dispatches_via_to_thread_and_returns_url(
    stripe_client: StripeClient,
) -> None:
    fake_session = SimpleNamespace(url="https://billing.stripe.com/session/xyz")

    with (
        patch(
            "app.integrations.stripe.client.asyncio.to_thread", new_callable=AsyncMock
        ) as mock_to_thread,
        patch("stripe.billing_portal.Session.create") as mock_create,
    ):
        mock_to_thread.return_value = fake_session
        result = await stripe_client.create_billing_portal_session(
            customer_id="cus_123",
            return_url="https://app.example.com/account",
        )

    assert result == "https://billing.stripe.com/session/xyz"
    mock_to_thread.assert_awaited_once_with(
        mock_create,
        customer="cus_123",
        return_url="https://app.example.com/account",
        api_key="sk_test_dummy",
    )
    mock_create.assert_not_called()


# ---------------------------------------------------------------------------
# verify_webhook_signature — the one sync exception (CPU-bound signature
# verification, not a blocking network call), per client.py's own docstring.
# ---------------------------------------------------------------------------


def test_verify_webhook_signature_is_sync_not_coroutine_function(
    stripe_client: StripeClient,
) -> None:
    import asyncio as asyncio_module

    assert not asyncio_module.iscoroutinefunction(stripe_client.verify_webhook_signature)


def test_verify_webhook_signature_returns_event_without_using_to_thread(
    stripe_client: StripeClient,
) -> None:
    fake_event = MagicMock(spec=stripe.Event)
    fake_settings = SimpleNamespace(
        stripe_webhook_secret=SimpleNamespace(get_secret_value=lambda: "whsec_test")
    )

    with (
        patch("app.integrations.stripe.client.asyncio.to_thread") as mock_to_thread,
        patch("stripe.Webhook.construct_event", return_value=fake_event) as mock_construct,
        patch("app.integrations.stripe.client.get_settings", return_value=fake_settings),
    ):
        result = stripe_client.verify_webhook_signature(b"payload-bytes", "sig-header")

    assert result is fake_event
    mock_construct.assert_called_once_with(
        b"payload-bytes", "sig-header", "whsec_test", api_key="sk_test_dummy"
    )
    mock_to_thread.assert_not_called()
