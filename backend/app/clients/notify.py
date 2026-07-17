"""Generic outbound notification webhook — fail-soft when unset."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


async def notify_change_signal(
    *,
    watch_id: str,
    title: str,
    url: str,
    timestamp: str | None = None,
) -> bool:
    """POST non-PII change metadata to NOTIFY_WEBHOOK_URL. No-op when unset."""
    settings = get_settings()
    webhook_url = settings.notify_webhook_url.strip()
    if not webhook_url:
        return False

    payload = {
        "source": "changedetection",
        "watch_id": watch_id,
        "title": title,
        "url": url,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(webhook_url, json=payload)
            response.raise_for_status()
        return True
    except httpx.HTTPError:
        logger.warning("notify webhook POST failed", exc_info=True)
        return False
