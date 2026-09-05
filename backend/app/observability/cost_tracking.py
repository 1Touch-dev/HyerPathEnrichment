"""Cost tracking for OpenAI API usage and embeddings.

Tracks token usage, API calls, and costs for embedding generation.
Uses Redis counters for real-time metrics and Prometheus for monitoring.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from prometheus_client import Counter, Gauge, Histogram
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

# LLM metrics
LLM_TOKENS_TOTAL = Counter(
    "llm_tokens_total",
    "Total tokens processed by LLMs",
    ["model", "token_type", "operation"],
)

LLM_REQUESTS_TOTAL = Counter(
    "llm_requests_total",
    "Total LLM API requests",
    ["model", "operation", "status"],
)

LLM_COST_USD = Counter(
    "llm_cost_usd_total",
    "Total cost in USD for LLM operations",
    ["model", "operation"],
)

# Cost per 1M tokens (as of 2026)
EMBEDDING_COSTS = {
    "text-embedding-3-small": 0.02,  # $0.02 per 1M tokens
    "text-embedding-3-large": 0.13,  # $0.13 per 1M tokens
    "text-embedding-ada-002": 0.10,  # $0.10 per 1M tokens (legacy)
}

# LLM pricing (per 1M tokens)
LLM_PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
}

# Legacy separate cost dicts (kept for backward compatibility)
LLM_INPUT_COSTS = {
    "gpt-4o-mini": 0.15,
    "gpt-4o": 2.50,
    "gpt-4-turbo": 10.00,
}

LLM_OUTPUT_COSTS = {
    "gpt-4o-mini": 0.60,
    "gpt-4o": 10.00,
    "gpt-4-turbo": 30.00,
}

# Additional metrics for budget monitoring
LLM_TOKENS_PER_REQUEST = Histogram(
    "llm_tokens_per_request",
    "Distribution of tokens per LLM request",
    ["model"],
    buckets=[100, 500, 1000, 2000, 5000, 10000],
)

USER_COST_USD = Gauge(
    "user_cost_usd",
    "Total cost attributed to each user",
    ["user_id"],
)

BUDGET_THRESHOLD_EXCEEDED = Counter(
    "budget_threshold_exceeded_total",
    "Number of times budget thresholds were exceeded",
    ["threshold_type"],
)


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


async def get_daily_cost(date: str | None = None) -> dict[str, Any]:
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


async def get_monthly_cost(month: str | None = None) -> dict[str, Any]:
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


async def get_total_cost() -> dict[str, Any]:
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


async def track_llm_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    operation: str = "feedback",
    user_id: str | None = None,
) -> None:
    """Track LLM operation cost and metrics.

    Updates:
    - Redis daily/monthly counters
    - Prometheus metrics

    Args:
        model: OpenAI model name (e.g. "gpt-4o-mini")
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        operation: Operation type (e.g. "feedback", "cv_extraction")
        user_id: Optional user ID for per-user tracking
    """
    # Calculate cost
    input_cost_per_1m = LLM_INPUT_COSTS.get(model, 0.15)
    output_cost_per_1m = LLM_OUTPUT_COSTS.get(model, 0.60)

    input_cost_usd = (input_tokens / 1_000_000) * input_cost_per_1m
    output_cost_usd = (output_tokens / 1_000_000) * output_cost_per_1m
    total_cost_usd = input_cost_usd + output_cost_usd

    # Update Prometheus metrics
    LLM_TOKENS_TOTAL.labels(model=model, token_type="input", operation=operation).inc(input_tokens)
    LLM_TOKENS_TOTAL.labels(model=model, token_type="output", operation=operation).inc(
        output_tokens
    )
    LLM_REQUESTS_TOTAL.labels(model=model, operation=operation, status="success").inc()
    LLM_COST_USD.labels(model=model, operation=operation).inc(total_cost_usd)

    # Update Redis counters
    try:
        redis = get_redis()
        today = datetime.now(UTC).date().isoformat()
        month = datetime.now(UTC).strftime("%Y-%m")

        # Daily counters
        redis.hincrby(f"llm:cost:daily:{today}", "input_tokens", input_tokens)
        redis.hincrby(f"llm:cost:daily:{today}", "output_tokens", output_tokens)
        redis.hincrbyfloat(f"llm:cost:daily:{today}", "cost_usd", total_cost_usd)
        redis.expire(f"llm:cost:daily:{today}", 86400 * 7)  # Keep 7 days

        # Monthly counters
        redis.hincrby(f"llm:cost:monthly:{month}", "input_tokens", input_tokens)
        redis.hincrby(f"llm:cost:monthly:{month}", "output_tokens", output_tokens)
        redis.hincrbyfloat(f"llm:cost:monthly:{month}", "cost_usd", total_cost_usd)
        redis.expire(f"llm:cost:monthly:{month}", 86400 * 90)  # Keep 90 days

        # All-time counters
        redis.hincrby("llm:cost:total", "input_tokens", input_tokens)
        redis.hincrby("llm:cost:total", "output_tokens", output_tokens)
        redis.hincrbyfloat("llm:cost:total", "cost_usd", total_cost_usd)

        # Per-operation counters
        redis.hincrby(f"llm:cost:operation:{operation}", "input_tokens", input_tokens)
        redis.hincrby(f"llm:cost:operation:{operation}", "output_tokens", output_tokens)
        redis.hincrbyfloat(f"llm:cost:operation:{operation}", "cost_usd", total_cost_usd)

        # Per-user tracking if user_id provided
        if user_id:
            redis.hincrby(f"llm:cost:user:{user_id}", "input_tokens", input_tokens)
            redis.hincrby(f"llm:cost:user:{user_id}", "output_tokens", output_tokens)
            redis.hincrbyfloat(f"llm:cost:user:{user_id}", "cost_usd", total_cost_usd)
            redis.expire(f"llm:cost:user:{user_id}", 86400 * 90)  # Keep 90 days

        logger.info(
            f"Tracked LLM cost: {operation}, {input_tokens} in/{output_tokens} out tokens, ${total_cost_usd:.4f}",
            extra={
                "model": model,
                "operation": operation,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": total_cost_usd,
                "user_id": user_id,
                "date": today,
            },
        )

    except Exception as e:
        logger.warning(
            "Failed to track LLM cost in Redis",
            extra={"error": str(e)},
            exc_info=True,
        )


def track_llm_failure(model: str, operation: str = "feedback") -> None:
    """Track failed LLM API request.

    Args:
        model: OpenAI model name
        operation: Operation type
    """
    LLM_REQUESTS_TOTAL.labels(model=model, operation=operation, status="failure").inc()


async def get_daily_llm_cost(date: str | None = None) -> dict[str, Any]:
    """Get LLM costs for a specific date.

    Args:
        date: ISO date string (YYYY-MM-DD), defaults to today

    Returns:
        Dict with input_tokens, output_tokens, cost_usd
    """
    if date is None:
        date = datetime.now(UTC).date().isoformat()

    try:
        redis = get_redis()
        data = redis.hgetall(f"llm:cost:daily:{date}")

        if not data:
            return {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

        return {
            "input_tokens": int(data.get(b"input_tokens", 0)),
            "output_tokens": int(data.get(b"output_tokens", 0)),
            "cost_usd": float(data.get(b"cost_usd", 0.0)),
        }
    except Exception as e:
        logger.error("Failed to get daily LLM cost", extra={"error": str(e)}, exc_info=True)
        return {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}


async def get_monthly_llm_cost(month: str | None = None) -> dict[str, Any]:
    """Get LLM costs for a specific month.

    Args:
        month: Month string (YYYY-MM), defaults to current month

    Returns:
        Dict with input_tokens, output_tokens, cost_usd
    """
    if month is None:
        month = datetime.now(UTC).strftime("%Y-%m")

    try:
        redis = get_redis()
        data = redis.hgetall(f"llm:cost:monthly:{month}")

        if not data:
            return {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

        return {
            "input_tokens": int(data.get(b"input_tokens", 0)),
            "output_tokens": int(data.get(b"output_tokens", 0)),
            "cost_usd": float(data.get(b"cost_usd", 0.0)),
        }
    except Exception as e:
        logger.error("Failed to get monthly LLM cost", extra={"error": str(e)}, exc_info=True)
        return {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}


async def get_user_costs(limit: int = 10) -> list[dict[str, Any]]:
    """Get top users by cost.

    Args:
        limit: Maximum number of users to return

    Returns:
        List of dicts with user_id, input_tokens, output_tokens, cost_usd
    """
    try:
        redis = get_redis()
        user_keys = redis.keys("llm:cost:user:*")

        user_costs: list[dict[str, Any]] = []
        for key in user_keys:
            key_str = key.decode() if isinstance(key, bytes) else key
            user_id = key_str.split(":")[-1]
            data = redis.hgetall(key)

            if data:
                user_costs.append(
                    {
                        "user_id": user_id,
                        "input_tokens": int(data.get(b"input_tokens", 0)),
                        "output_tokens": int(data.get(b"output_tokens", 0)),
                        "cost_usd": float(data.get(b"cost_usd", 0.0)),
                    }
                )

        # Sort by cost descending
        user_costs.sort(key=lambda x: float(x["cost_usd"]), reverse=True)
        return user_costs[:limit]

    except Exception as e:
        logger.error("Failed to get user costs", extra={"error": str(e)}, exc_info=True)
        return []
