"""Metrics for parallel tier execution monitoring"""

import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

try:
    from prometheus_client import Counter, Histogram, Gauge

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

if PROMETHEUS_AVAILABLE:
    tier_executions_total = Counter(
        "enrichment_tier_executions_total", "Total tier executions", ["tier", "status"]
    )

    tier_duration_seconds = Histogram(
        "enrichment_tier_duration_seconds",
        "Tier execution duration in seconds",
        ["tier"],
        buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1200, 1800],
    )

    parallel_tiers_active = Gauge(
        "enrichment_parallel_tiers_active", "Currently active parallel tier executions"
    )


@asynccontextmanager
async def track_tier_execution(tier_name: str) -> AsyncIterator[None]:
    """Context manager to track tier execution metrics"""
    if not PROMETHEUS_AVAILABLE:
        yield
        return

    start = time.time()
    parallel_tiers_active.inc()

    try:
        yield
        tier_executions_total.labels(tier=tier_name, status="success").inc()
    except Exception:
        tier_executions_total.labels(tier=tier_name, status="failure").inc()
        raise
    finally:
        duration = time.time() - start
        tier_duration_seconds.labels(tier=tier_name).observe(duration)
        parallel_tiers_active.dec()
