"""Browser push notification delivery (Web Push API) — fail-soft, mirrors notify.py."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pywebpush import WebPushException, webpush
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.job_matching.models import PushSubscription

logger = logging.getLogger(__name__)


async def subscribe(db: AsyncSession, user_id: UUID, endpoint: str, p256dh: str, auth: str) -> None:
    """Upsert a push subscription by `endpoint`.

    If a subscription with this endpoint already exists, its `user_id`/keys/
    `last_used_at` are updated (covers a browser re-subscribing, or a subscription
    endpoint being reassigned to a different logged-in user on a shared device).
    Otherwise a new row is inserted.
    """
    result = await db.execute(select(PushSubscription).where(PushSubscription.endpoint == endpoint))
    existing = result.scalar_one_or_none()

    if existing:
        existing.user_id = user_id
        existing.p256dh_key = p256dh
        existing.auth_key = auth
        existing.last_used_at = datetime.now(UTC)
        await db.commit()
        return

    db.add(
        PushSubscription(
            user_id=user_id,
            endpoint=endpoint,
            p256dh_key=p256dh,
            auth_key=auth,
        )
    )
    await db.commit()


async def unsubscribe(db: AsyncSession, user_id: UUID, endpoint: str) -> None:
    """Delete the subscription matching both `user_id` and `endpoint`.

    Scoped to `user_id` so one user can't delete another user's subscription.
    """
    result = await db.execute(
        select(PushSubscription).where(
            PushSubscription.user_id == user_id, PushSubscription.endpoint == endpoint
        )
    )
    existing = result.scalar_one_or_none()
    if existing is None:
        return

    await db.delete(existing)
    await db.commit()


async def send_push_notification(subscription: PushSubscription, payload: dict[str, Any]) -> bool:
    """Send a Web Push notification to a single subscription. Never raises.

    Returns True if the push succeeded, False otherwise (fail-soft — mirrors
    `_post_webhook`'s "never raises" convention).
    """
    settings = get_settings()

    try:
        await asyncio.to_thread(
            webpush,
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {
                    "p256dh": subscription.p256dh_key,
                    "auth": subscription.auth_key,
                },
            },
            data=json.dumps(payload),
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject},
        )
        return True
    except WebPushException:
        logger.warning("push notification delivery failed", exc_info=True)
        return False
