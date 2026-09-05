"""Mock Stripe Checkout and Billing Portal pages for local billing.

Cookie-auth is off (same as Stripe-hosted pages). Confirm/cancel POSTs HMAC-signed
events through ``/api/billing/webhooks/stripe`` so signature verification,
idempotency, and handlers stay on the production path. Endpoints 404 unless
``stripe_mode=mock`` at request time.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from html import escape
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.config import get_settings
from app.integrations.stripe.mock_client import get_mock_checkout_session

_THIRTY_DAYS_SECONDS = 30 * 24 * 3600


async def require_mock_stripe_mode() -> None:
    """404 unless mock mode — request-time so TestClient can monkeypatch settings."""
    if get_settings().stripe_mode != "mock":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


router = APIRouter(
    prefix="/api/billing/mock",
    tags=["billing"],
    dependencies=[Depends(require_mock_stripe_mode)],
)


def _stripe_signature_header(payload: bytes, secret: str) -> str:
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload.decode('utf-8')}".encode()
    signature = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


def _event_bytes(event_id: str, event_type: str, data_object: dict[str, Any]) -> bytes:
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


def _require_checkout_session(session_id: str) -> dict[str, str]:
    session = get_mock_checkout_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unknown checkout session"
        )
    return session


def _subscription_id_for_session(session_id: str) -> str:
    return f"sub_mock_{session_id}"


async def _deliver_signed_event(request: Request, payload: bytes) -> None:
    secret = get_settings().stripe_webhook_secret.get_secret_value()
    header = _stripe_signature_header(payload, secret)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=request.app),
        base_url="http://testserver",
    ) as http:
        resp = await http.post(
            "/api/billing/webhooks/stripe",
            content=payload,
            headers={"stripe-signature": header, "Content-Type": "application/json"},
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Mock webhook delivery failed",
        )


def _checkout_completed_payload(session_id: str, session: dict[str, str]) -> bytes:
    subscription_id = _subscription_id_for_session(session_id)
    return _event_bytes(
        f"evt_mock_cs_{session_id}",
        "checkout.session.completed",
        {
            "id": session_id,
            "object": "checkout.session",
            "client_reference_id": session["client_reference_id"],
            "customer": session["customer_id"],
            "subscription": subscription_id,
            "mode": "subscription",
            "status": "complete",
        },
    )


def _subscription_updated_payload(session_id: str, session: dict[str, str]) -> bytes:
    period_end = int(time.time()) + _THIRTY_DAYS_SECONDS
    period_start = period_end - _THIRTY_DAYS_SECONDS
    subscription_id = _subscription_id_for_session(session_id)
    return _event_bytes(
        f"evt_mock_su_{session_id}",
        "customer.subscription.updated",
        {
            "id": subscription_id,
            "object": "subscription",
            "customer": session["customer_id"],
            "status": "active",
            "items": {
                "object": "list",
                "data": [
                    {
                        "id": "si_mock_1",
                        "object": "subscription_item",
                        "current_period_end": period_end,
                        "current_period_start": period_start,
                    }
                ],
            },
        },
    )


def _subscription_deleted_payload(customer_id: str) -> bytes:
    return _event_bytes(
        f"evt_mock_sd_{customer_id}",
        "customer.subscription.deleted",
        {
            "id": f"sub_mock_{customer_id}",
            "object": "subscription",
            "customer": customer_id,
            "status": "canceled",
        },
    )


@router.get("/checkout", response_class=HTMLResponse)
async def mock_checkout_page(session_id: str) -> HTMLResponse:
    _require_checkout_session(session_id)
    safe_id = escape(session_id, quote=True)
    html = f"""<!DOCTYPE html>
<html>
<head><title>Mock Stripe Checkout</title></head>
<body>
  <h1>Mock checkout</h1>
  <form method="post" action="/api/billing/mock/checkout/confirm">
    <input type="hidden" name="session_id" value="{safe_id}">
    <button type="submit">Confirm</button>
  </form>
  <form method="post" action="/api/billing/mock/checkout/cancel">
    <input type="hidden" name="session_id" value="{safe_id}">
    <button type="submit">Cancel</button>
  </form>
</body>
</html>"""
    return HTMLResponse(content=html)


@router.post("/checkout/confirm")
async def mock_checkout_confirm(
    request: Request,
    session_id: str = Form(...),
) -> RedirectResponse:
    session = _require_checkout_session(session_id)
    await _deliver_signed_event(request, _checkout_completed_payload(session_id, session))
    await _deliver_signed_event(request, _subscription_updated_payload(session_id, session))
    return RedirectResponse(url=session["success_url"], status_code=status.HTTP_303_SEE_OTHER)


@router.post("/checkout/cancel")
async def mock_checkout_cancel(session_id: str = Form(...)) -> RedirectResponse:
    session = _require_checkout_session(session_id)
    return RedirectResponse(url=session["cancel_url"], status_code=status.HTTP_303_SEE_OTHER)


@router.get("/portal", response_class=HTMLResponse)
async def mock_portal_page(customer_id: str, return_url: str) -> HTMLResponse:
    safe_customer = escape(customer_id, quote=True)
    safe_return = escape(return_url, quote=True)
    html = f"""<!DOCTYPE html>
<html>
<head><title>Mock Stripe Billing Portal</title></head>
<body>
  <h1>Mock billing portal</h1>
  <form method="post" action="/api/billing/mock/portal/cancel">
    <input type="hidden" name="customer_id" value="{safe_customer}">
    <input type="hidden" name="return_url" value="{safe_return}">
    <button type="submit">Cancel subscription</button>
  </form>
</body>
</html>"""
    return HTMLResponse(content=html)


@router.post("/portal/cancel")
async def mock_portal_cancel(
    request: Request,
    customer_id: str = Form(...),
    return_url: str = Form(...),
) -> RedirectResponse:
    await _deliver_signed_event(request, _subscription_deleted_payload(customer_id))
    return RedirectResponse(url=return_url, status_code=status.HTTP_303_SEE_OTHER)
