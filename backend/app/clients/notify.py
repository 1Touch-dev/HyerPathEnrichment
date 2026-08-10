"""Generic outbound notification webhook — fail-soft when unset."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def _post_webhook(payload: dict[str, Any], *, url: str | None = None) -> bool:
    """POST JSON to `url`, or NOTIFY_WEBHOOK_URL when `url` is unset. No-op when neither is set. Never raises."""
    webhook_url = (url or get_settings().notify_webhook_url).strip()
    if not webhook_url:
        return False

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(webhook_url, json=payload)
            response.raise_for_status()
        return True
    except httpx.HTTPError:
        logger.warning("notify webhook POST failed", exc_info=True)
        return False


async def notify_change_signal(
    *,
    watch_id: str,
    title: str,
    url: str,
    timestamp: str | None = None,
) -> bool:
    """POST non-PII change metadata to NOTIFY_WEBHOOK_URL. No-op when unset."""
    return await _post_webhook(
        {
            "source": "changedetection",
            "watch_id": watch_id,
            "title": title,
            "url": url,
            "timestamp": timestamp or datetime.now(UTC).isoformat(),
        }
    )


async def notify_ops_alert(
    *,
    alert: str,
    summary: str,
    severity: str = "critical",
    details: dict[str, str] | None = None,
) -> bool:
    """POST a non-PII ops alert to NOTIFY_WEBHOOK_URL. No-op when unset.

    Payload never includes identifiers, emails, dossier fields, or request bodies.
    """
    payload: dict[str, Any] = {
        "source": "hyrepath-ops",
        "alert": alert,
        "severity": severity,
        "summary": summary,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if details:
        # Only string scalars; callers must not pass PII.
        payload["details"] = {str(k): str(v) for k, v in details.items()}
    return await _post_webhook(payload)


async def notify_job_match(
    *,
    webhook_url: str,
    candidate_id: str,
    matches: list[dict[str, Any]],
) -> bool:
    """POST a job-match digest event to the candidate's configured webhook_url.

    Unlike `notify_change_signal`/`notify_ops_alert` (which always target the shared
    `NOTIFY_WEBHOOK_URL` ops sink), job-match notifications are per-candidate, so
    `webhook_url` is passed straight through to `_post_webhook`'s `url` override
    instead of relying on settings.

    Args:
        webhook_url: Candidate-configured webhook target URL.
        candidate_id: Candidate's user ID.
        matches: Top matches, each with title/company/score/url (see
            `_send_match_digest_async`'s `matches` context shape).

    Returns:
        True if the POST succeeded, False otherwise (never raises — `_post_webhook`
        is fail-soft).
    """
    payload: dict[str, Any] = {
        "source": "hyrepath-job-matching",
        "event": "job_match_digest",
        "candidate_id": candidate_id,
        "matches": matches,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    return await _post_webhook(payload, url=webhook_url)
