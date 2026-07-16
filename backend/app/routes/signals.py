from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import SignalListResponse
from app.providers.notify import notify_change_signal
from app.signals.store import create_signal, list_signals
from app.storage.db import get_db_session

logger = logging.getLogger(__name__)

webhook_router = APIRouter(prefix="/api/signals", tags=["signals"])
list_router = APIRouter(prefix="/api/signals", tags=["signals"])
router = webhook_router


def _parse_changedetection_payload(
    payload: dict[str, Any],
) -> tuple[str, str, str, str | None]:
    """Extract non-PII watch metadata from a changedetection.io webhook body."""
    watch_id = str(
        payload.get("watch_uuid") or payload.get("uuid") or payload.get("watch_id") or "unknown"
    )
    title = str(payload.get("watch_title") or payload.get("title") or "unknown")
    url = str(payload.get("watch_url") or payload.get("url") or payload.get("link") or "")
    raw_ts = payload.get("timestamp") or payload.get("last_changed")
    timestamp = str(raw_ts) if raw_ts is not None else None
    return watch_id, title, url, timestamp


@webhook_router.post("/changedetection", status_code=status.HTTP_202_ACCEPTED)
async def changedetection_webhook(
    payload: dict[str, Any],
    x_signal_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Consume changedetection.io change notifications."""
    settings = get_settings()
    expected = settings.changedetection_api_key.strip()
    if expected and x_signal_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid signal token")

    watch_id, title, url, timestamp = _parse_changedetection_payload(payload)

    logger.info(
        "changedetection signal received: watch=%s title=%s",
        watch_id,
        title,
    )
    await create_signal(
        db,
        watch_id=watch_id,
        title=title,
        url=url,
        timestamp=timestamp,
    )
    await notify_change_signal(
        watch_id=watch_id,
        title=title,
        url=url,
        timestamp=timestamp,
    )
    return {"status": "accepted"}


@list_router.get("", response_model=SignalListResponse)
async def read_signals(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> SignalListResponse:
    items, total = await list_signals(db, limit, offset)
    return SignalListResponse(
        signals=items,
        total=total,
        limit=max(1, min(limit, 100)),
        offset=max(0, offset),
    )
