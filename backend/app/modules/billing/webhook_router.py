"""Stripe webhook endpoint — signature auth only, no cookie auth."""

from __future__ import annotations

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db_session
from app.integrations.stripe.client import StripeClient
from app.modules.billing import repository, service

router = APIRouter(prefix="/api/billing/webhooks", tags=["billing"])


@router.post("/stripe", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")

    try:
        event = StripeClient().verify_webhook_signature(payload, signature)
    except stripe.SignatureVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature"
        ) from exc

    if await repository.event_already_processed(db, event.id):
        return {"status": "already_processed"}

    await service.handle_webhook_event(db, event)
    await repository.mark_event_processed(db, event.id, event.type)
    return {"status": "processed"}
