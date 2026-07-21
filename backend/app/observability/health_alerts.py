"""Probe API health endpoints and notify on failure (no PII)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.clients.notify import notify_ops_alert

logger = logging.getLogger(__name__)

_PROBE_PATHS = ("/health", "/ready")


@dataclass(frozen=True)
class HealthProbeResult:
    path: str
    ok: bool
    status_code: int | None
    reason: str


async def probe_health_endpoints(
    base_url: str,
    *,
    timeout: float = 10.0,
) -> list[HealthProbeResult]:
    """GET ``/health`` and ``/ready``; return one result per path."""
    root = base_url.rstrip("/")
    results: list[HealthProbeResult] = []
    async with httpx.AsyncClient(timeout=timeout) as client:
        for path in _PROBE_PATHS:
            url = f"{root}{path}"
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    results.append(
                        HealthProbeResult(
                            path=path,
                            ok=True,
                            status_code=response.status_code,
                            reason="ok",
                        )
                    )
                else:
                    results.append(
                        HealthProbeResult(
                            path=path,
                            ok=False,
                            status_code=response.status_code,
                            reason=f"http_{response.status_code}",
                        )
                    )
            except httpx.HTTPError as exc:
                results.append(
                    HealthProbeResult(
                        path=path,
                        ok=False,
                        status_code=None,
                        reason=type(exc).__name__,
                    )
                )
    return results


def queue_depth_snapshot() -> dict[str, int] | None:
    """Best-effort RQ queue depth / failed count. None when Redis unavailable."""
    try:
        from app.workers.queue import get_queue

        queue = get_queue()
        return {
            "queued": len(queue),
            "failed": queue.failed_job_registry.count,
        }
    except Exception:
        logger.debug("queue depth snapshot failed", exc_info=True)
        return None


async def notify_on_health_failure(
    base_url: str,
    *,
    timeout: float = 10.0,
    queue_depth_warn: int = 100,
    queue_failed_warn: int = 5,
) -> bool:
    """Probe health; POST ops alert if any check fails or queue thresholds trip.

    Returns True when a webhook POST was attempted and succeeded.
    """
    probes = await probe_health_endpoints(base_url, timeout=timeout)
    failures = [p for p in probes if not p.ok]
    details: dict[str, str] = {
        p.path.lstrip("/"): f"{p.reason}" + (f"/{p.status_code}" if p.status_code else "")
        for p in probes
    }

    queue = queue_depth_snapshot()
    queue_alert = False
    if queue is not None:
        details["queue_queued"] = str(queue["queued"])
        details["queue_failed"] = str(queue["failed"])
        if queue["queued"] >= queue_depth_warn or queue["failed"] >= queue_failed_warn:
            queue_alert = True

    if not failures and not queue_alert:
        return False

    if failures:
        alert = "api_health_failed"
        summary = f"Health probe failed for {base_url.rstrip('/')}: " + ", ".join(
            f"{p.path}={p.reason}" for p in failures
        )
        severity = "critical"
    else:
        alert = "queue_depth_or_failures"
        summary = (
            f"RQ queue thresholds exceeded (queued>={queue_depth_warn} "
            f"or failed>={queue_failed_warn})"
        )
        severity = "warning"

    return await notify_ops_alert(
        alert=alert,
        summary=summary,
        severity=severity,
        details=details,
    )
