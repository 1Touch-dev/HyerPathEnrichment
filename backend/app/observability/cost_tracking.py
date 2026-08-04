"""Cost tracking for OpenAI API usage and embeddings.

Tracks token usage, API calls, and costs for embedding generation.
Uses Redis counters for real-time metrics and Prometheus for monitoring.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from prometheus_client import Counter, Gauge
from redis import Redis

from app.workers.queue import get_redis_connection

logger = logging.getLogger(__name__)

# Prometheus metrics
EMBEDDING_TOKENS_TOTAL = Counter(
    "embedding_tokens_total",
    "Total tokens processed for embeddings",
    ["model"],
)

EMBEDDING_REQUESTS_TOTAL = Counter(
    "embedding_requests_total",
    "Total embedding API requests",
    ["model", "status"],
)

EMBEDDING_COST_USD = Counter(
    "embedding_cost_usd_total",
    "Total cost in USD for embeddings",
    ["model"],
)

EMBEDDING_QUEUE_SIZE = Gauge(
    "embedding_queue_size",
    "Number of pending embedding jobs",
)

# Cost per 1M tokens (as of 2026)
EMBEDDING_COSTS = {
    "text-embedding-3-small": 0.02,  # $0.02 per 1M tokens
    "text-embedding-3-large": 0.13,  # $0.13 per 1M tokens
    "text-embedding-ada-002": 0.10,  # $0.10 per 1M tokens (legacy)
}


def get_redis() -> Redis:
    """Get Redis connection for cost tracking."""
    return get_redis_connection()


async def track_embedding_cost(
    model: str,
    tokens: int,
    num_embeddings: int,
) -> None:
    """Track embedding generation cost and metrics.

    Updates:
    - Redis daily/monthly counters
    - Prometheus metrics

    Args:
        model: OpenAI model name (e.g. "text-embedding-3-small")
        tokens: Total tokens processed
        num_embeddings: Number of embeddings generated
    """
    # Calculate cost
    cost_per_1m = EMBEDDING_COSTS.get(model, 0.02)  # Default to small model
    cost_usd = (tokens / 1_000_000) * cost_per_1m

    # Update Prometheus metrics
    EMBEDDING_TOKENS_TOTAL.labels(model=model).inc(tokens)
    EMBEDDING_REQUESTS_TOTAL.labels(model=model, status="success").inc(num_embeddings)
    EMBEDDING_COST_USD.labels(model=model).inc(cost_usd)

    # Update Redis counters
    try:
        redis = get_redis()
        today = datetime.now(UTC).date().isoformat()
        month = datetime.now(UTC).strftime("%Y-%m")

        # Daily counters
        redis.hincrby(f"embedding:cost:daily:{today}", "tokens", tokens)
        redis.hincrby(f"embedding:cost:daily:{today}", "embeddings", num_embeddings)
        redis.hincrbyfloat(f"embedding:cost:daily:{today}", "cost_usd", cost_usd)
        redis.expire(f"embedding:cost:daily:{today}", 86400 * 7)  # Keep 7 days

        # Monthly counters
        redis.hincrby(f"embedding:cost:monthly:{month}", "tokens", tokens)
        redis.hincrby(f"embedding:cost:monthly:{month}", "embeddings", num_embeddings)
        redis.hincrbyfloat(f"embedding:cost:monthly:{month}", "cost_usd", cost_usd)
        redis.expire(f"embedding:cost:monthly:{month}", 86400 * 90)  # Keep 90 days

        # All-time counters
        redis.hincrby("embedding:cost:total", "tokens", tokens)
        redis.hincrby("embedding:cost:total", "embeddings", num_embeddings)
        redis.hincrbyfloat("embedding:cost:total", "cost_usd", cost_usd)

        logger.info(
            f"Tracked embedding cost: {num_embeddings} embeddings, {tokens} tokens, ${cost_usd:.4f}",
            extra={
                "model": model,
                "tokens": tokens,
                "num_embeddings": num_embeddings,
                "cost_usd": cost_usd,
                "date": today,
            },
        )

    except Exception as e:
        logger.warning(
            "Failed to track embedding cost in Redis",
            extra={"error": str(e)},
            exc_info=True,
        )


async def get_daily_cost(date: str | None = None) -> dict:
    """Get embedding costs for a specific date.

    Args:
        date: ISO date string (YYYY-MM-DD), defaults to today

    Returns:
        Dict with tokens, embeddings, cost_usd
    """
    if date is None:
        date = datetime.now(UTC).date().isoformat()

    try:
        redis = get_redis()
        data = redis.hgetall(f"embedding:cost:daily:{date}")

        if not data:
            return {"tokens": 0, "embeddings": 0, "cost_usd": 0.0}

        return {
            "tokens": int(data.get(b"tokens", 0)),
            "embeddings": int(data.get(b"embeddings", 0)),
            "cost_usd": float(data.get(b"cost_usd", 0.0)),
        }
    except Exception as e:
        logger.error("Failed to get daily cost", extra={"error": str(e)}, exc_info=True)
        return {"tokens": 0, "embeddings": 0, "cost_usd": 0.0}


async def get_monthly_cost(month: str | None = None) -> dict:
    """Get embedding costs for a specific month.

    Args:
        month: Month string (YYYY-MM), defaults to current month

    Returns:
        Dict with tokens, embeddings, cost_usd
    """
    if month is None:
        month = datetime.now(UTC).strftime("%Y-%m")

    try:
        redis = get_redis()
        data = redis.hgetall(f"embedding:cost:monthly:{month}")

        if not data:
            return {"tokens": 0, "embeddings": 0, "cost_usd": 0.0}

        return {
            "tokens": int(data.get(b"tokens", 0)),
            "embeddings": int(data.get(b"embeddings", 0)),
            "cost_usd": float(data.get(b"cost_usd", 0.0)),
        }
    except Exception as e:
        logger.error("Failed to get monthly cost", extra={"error": str(e)}, exc_info=True)
        return {"tokens": 0, "embeddings": 0, "cost_usd": 0.0}


async def get_total_cost() -> dict:
    """Get all-time embedding costs.

    Returns:
        Dict with tokens, embeddings, cost_usd
    """
    try:
        redis = get_redis()
        data = redis.hgetall("embedding:cost:total")

        if not data:
            return {"tokens": 0, "embeddings": 0, "cost_usd": 0.0}

        return {
            "tokens": int(data.get(b"tokens", 0)),
            "embeddings": int(data.get(b"embeddings", 0)),
            "cost_usd": float(data.get(b"cost_usd", 0.0)),
        }
    except Exception as e:
        logger.error("Failed to get total cost", extra={"error": str(e)}, exc_info=True)
        return {"tokens": 0, "embeddings": 0, "cost_usd": 0.0}


def track_embedding_failure(model: str) -> None:
    """Track failed embedding API request.

    Args:
        model: OpenAI model name
    """
    EMBEDDING_REQUESTS_TOTAL.labels(model=model, status="failure").inc()


def update_queue_size(size: int) -> None:
    """Update embedding queue size metric.

    Args:
        size: Current queue size
    """
    EMBEDDING_QUEUE_SIZE.set(size)
