from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, status

from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.post("/changedetection", status_code=status.HTTP_202_ACCEPTED)
async def changedetection_webhook(
    payload: dict[str, Any],
    x_signal_token: str | None = Header(default=None),
) -> dict[str, str]:
    """Consume changedetection.io change notifications.

    Unauthenticated by design (external self-hosted watcher posts here), but an
    optional shared secret can be required via CHANGEDETECTION_API_KEY. Only
    non-PII fields (watch id/title/url of the monitored page) are logged.
    """
    settings = get_settings()
    expected = settings.changedetection_api_key.strip()
    if expected and x_signal_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid signal token")

    logger.info(
        "changedetection signal received: watch=%s title=%s",
        payload.get("watch_uuid") or payload.get("uuid") or "unknown",
        payload.get("watch_title") or payload.get("title") or "unknown",
    )
    return {"status": "accepted"}
