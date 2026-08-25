#!/usr/bin/env python3
"""Periodic cleanup worker that runs maintenance tasks."""

import asyncio
import logging
from datetime import UTC, datetime

# Import ORM registry FIRST to register all models with SQLAlchemy
import app.database.orm_registry  # noqa: F401
from app.core.config import get_settings
from app.workers.tasks.cleanup import cleanup_orphaned_jobs

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s", "service": "hyrepath-enrichment"}',
)
logger = logging.getLogger(__name__)

# Demand intelligence's daily snapshot job runs far less often than the 5-minute
# cleanup loop (once per UTC day is sufficient for a day-granularity aggregate) —
# tracked by the last date it ran to avoid recomputing on every 5-minute tick.
_last_demand_snapshot_date: object | None = None


async def _maybe_run_demand_intelligence_snapshot() -> None:
    """No-op when ``enable_demand_intelligence`` is false (mirrors enable_tier1's
    gating pattern) or when today's snapshot has already been computed."""
    global _last_demand_snapshot_date

    settings = get_settings()
    if not settings.enable_demand_intelligence:
        return

    today = datetime.now(UTC).date()
    if _last_demand_snapshot_date == today:
        return

    from app.database.session import SessionLocal
    from app.modules.demand_intelligence.service import compute_daily_snapshot

    try:
        async with SessionLocal() as session:
            written = await compute_daily_snapshot(session, target_date=today)
        logger.info(f"Demand intelligence snapshot complete: {written} rows written")
        _last_demand_snapshot_date = today
    except Exception as e:
        logger.error(
            f"Demand intelligence snapshot task failed: {e}",
            exc_info=True,
            extra={"error": str(e), "error_type": type(e).__name__},
        )


async def run_cleanup_loop(interval_seconds: int = 300) -> None:
    """Run cleanup tasks in a loop.

    Args:
        interval_seconds: How often to run cleanup (default: 300 = 5 minutes)
    """
    logger.info(f"Starting cleanup worker (interval: {interval_seconds}s)")

    while True:
        try:
            logger.info("Running orphaned job cleanup...")
            count = await cleanup_orphaned_jobs(max_age_minutes=15)
            logger.info(f"Cleanup complete: {count} jobs fixed")
        except Exception as e:
            logger.error(
                f"Cleanup task failed: {e}",
                exc_info=True,
                extra={"error": str(e), "error_type": type(e).__name__},
            )

        await _maybe_run_demand_intelligence_snapshot()

        # Sleep until next run
        logger.debug(f"Sleeping for {interval_seconds} seconds")
        await asyncio.sleep(interval_seconds)


def main() -> None:
    """Entry point for cleanup worker."""
    settings = get_settings()

    # Get interval from environment or use default
    interval = (
        int(settings.cleanup_interval_seconds)
        if hasattr(settings, "cleanup_interval_seconds")
        else 300
    )

    logger.info(
        "Cleanup worker starting",
        extra={
            "interval_seconds": interval,
            "max_age_minutes": 15,
        },
    )

    asyncio.run(run_cleanup_loop(interval_seconds=interval))


if __name__ == "__main__":
    main()
