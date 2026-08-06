"""Budget monitoring worker task."""

from __future__ import annotations

import asyncio
import logging

from app.observability.budget_alerts import check_budget_threshold, check_monthly_burn_rate
from app.workers.queue import queue

logger = logging.getLogger(__name__)


@queue.job("budget_check", timeout=30)
def check_budget_job() -> None:
    """Run budget checks (daily and monthly thresholds).

    This job should be scheduled to run periodically (e.g., hourly)
    to check if budget thresholds have been exceeded.
    """
    logger.info("Running budget check job")

    try:
        # Run async checks
        asyncio.run(_run_budget_checks())

        logger.info("Budget check completed successfully")

    except Exception as e:
        logger.error(f"Budget check failed: {e}", exc_info=True)
        raise


async def _run_budget_checks() -> None:
    """Run budget threshold checks."""
    await check_budget_threshold()
    await check_monthly_burn_rate()
