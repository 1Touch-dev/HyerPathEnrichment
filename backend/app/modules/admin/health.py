"""System health: real Postgres/Redis pings always; Prometheus four-golden-
signals panel only when PROMETHEUS_QUERY_URL is set (fail-soft, per this
repo's existing optional-backend convention)."""

from __future__ import annotations

import time

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.infrastructure.redis import get_redis_client
from app.modules.admin.schemas import SystemHealthResponse


async def get_system_health(db: AsyncSession) -> SystemHealthResponse:
    settings = get_settings()

    db_start = time.monotonic()
    database_ok = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        database_ok = False
    database_latency_ms = (time.monotonic() - db_start) * 1000

    redis_start = time.monotonic()
    redis_ok = True
    try:
        client = get_redis_client()
        await client.ping()
    except Exception:
        redis_ok = False
    redis_latency_ms = (time.monotonic() - redis_start) * 1000

    signals: dict[str, float | None] = {}
    prometheus_configured = bool(settings.prometheus_query_url)
    if prometheus_configured:
        signals = await _query_golden_signals(settings.prometheus_query_url)

    return SystemHealthResponse(
        database_ok=database_ok,
        database_latency_ms=round(database_latency_ms, 2),
        redis_ok=redis_ok,
        redis_latency_ms=round(redis_latency_ms, 2),
        prometheus_configured=prometheus_configured,
        signals=signals,
    )


async def _query_golden_signals(base_url: str) -> dict[str, float | None]:
    """Latency, traffic, errors, saturation — per docs/admin-module-research.md
    §2's SRE-book citation. Queries this repo's own existing Prometheus metrics
    (tier_metrics, job_matching_metrics), never invents new metric names."""
    queries = {
        "latency_p95_seconds": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
        "traffic_requests_per_sec": "sum(rate(http_requests_total[5m]))",
        "error_rate": 'sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))',
        "queue_depth_saturation": "sum(rq_queue_length)",
    }
    results: dict[str, float | None] = {}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            for signal_name, query in queries.items():
                response = await client.get(f"{base_url}/api/v1/query", params={"query": query})
                response.raise_for_status()
                data = response.json()
                result = data.get("data", {}).get("result", [])
                results[signal_name] = float(result[0]["value"][1]) if result else None
    except Exception:
        # Fail-soft: Prometheus unreachable or misconfigured is not a 500 for
        # the whole health page — matches this repo's other optional-backend
        # conventions (LLM_MODE stub, R2->local fallback).
        return dict.fromkeys(queries, None)
    return results
