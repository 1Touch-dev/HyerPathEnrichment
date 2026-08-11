"""Budget alert system for cost monitoring."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings
from app.observability.cost_tracking import (
    BUDGET_THRESHOLD_EXCEEDED,
    get_daily_cost,
    get_daily_llm_cost,
    get_monthly_cost,
    get_monthly_llm_cost,
)

logger = logging.getLogger(__name__)


async def check_budget_threshold() -> None:
    """Check if daily budget threshold has been exceeded.

    Checks current daily spending against DAILY_COST_THRESHOLD_USD.
    Logs an alert if threshold is exceeded.
    """
    settings = get_settings()

    if not settings.ENABLE_BUDGET_ALERTS:
        return

    today = datetime.now(UTC).date().isoformat()

    # Get daily costs
    embedding_costs = await get_daily_cost(today)
    llm_costs = await get_daily_llm_cost(today)

    total_daily_cost = embedding_costs["cost_usd"] + llm_costs["cost_usd"]

    if total_daily_cost >= settings.DAILY_COST_THRESHOLD_USD:
        BUDGET_THRESHOLD_EXCEEDED.labels(threshold_type="daily").inc()

        alert_details = {
            "threshold": settings.DAILY_COST_THRESHOLD_USD,
            "current": total_daily_cost,
            "date": today,
            "embedding_cost": embedding_costs["cost_usd"],
            "llm_cost": llm_costs["cost_usd"],
        }

        send_budget_alert("daily_threshold_exceeded", alert_details)


async def check_monthly_burn_rate() -> None:
    """Check if monthly budget threshold has been exceeded.

    Checks current monthly spending against MONTHLY_COST_THRESHOLD_USD.
    Logs an alert if threshold is exceeded.
    """
    settings = get_settings()

    if not settings.ENABLE_BUDGET_ALERTS:
        return

    month = datetime.now(UTC).strftime("%Y-%m")

    # Get monthly costs
    embedding_costs = await get_monthly_cost(month)
    llm_costs = await get_monthly_llm_cost(month)

    total_monthly_cost = embedding_costs["cost_usd"] + llm_costs["cost_usd"]

    if total_monthly_cost >= settings.MONTHLY_COST_THRESHOLD_USD:
        BUDGET_THRESHOLD_EXCEEDED.labels(threshold_type="monthly").inc()

        alert_details = {
            "threshold": settings.MONTHLY_COST_THRESHOLD_USD,
            "current": total_monthly_cost,
            "month": month,
            "embedding_cost": embedding_costs["cost_usd"],
            "llm_cost": llm_costs["cost_usd"],
        }

        send_budget_alert("monthly_threshold_exceeded", alert_details)


def send_budget_alert(alert_type: str, details: dict[str, Any]) -> None:
    """Send budget alert notification.

    Currently logs alert. Can be extended to send emails, Slack messages, etc.

    Args:
        alert_type: Type of alert (e.g., "daily_threshold_exceeded")
        details: Alert details dict
    """
    logger.warning(
        f"Budget alert: {alert_type}",
        extra={
            "alert_type": alert_type,
            "details": details,
        },
    )

    # Future: Send email, Slack notification, PagerDuty alert, etc.
