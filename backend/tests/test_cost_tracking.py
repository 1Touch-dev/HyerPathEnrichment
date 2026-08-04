"""Tests for cost tracking observability."""

import pytest
from datetime import datetime, UTC
from unittest.mock import MagicMock, patch

from app.observability.cost_tracking import (
    track_embedding_cost,
    get_daily_cost,
    get_monthly_cost,
    get_total_cost,
    track_embedding_failure,
    update_queue_size,
    EMBEDDING_COSTS,
)


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis = MagicMock()
    redis.hincrby = MagicMock()
    redis.hincrbyfloat = MagicMock()
    redis.hgetall = MagicMock(return_value={})
    redis.expire = MagicMock()
    return redis


@pytest.mark.asyncio
async def test_track_embedding_cost(mock_redis):
    """Test tracking embedding cost updates Redis and Prometheus."""
    with patch("app.observability.cost_tracking.get_redis", return_value=mock_redis):
        await track_embedding_cost(
            model="text-embedding-3-small",
            tokens=1000,
            num_embeddings=10,
        )

        # Check Redis calls
        assert mock_redis.hincrby.called
        assert mock_redis.hincrbyfloat.called

        # Should have daily, monthly, and total counters
        daily_calls = [c for c in mock_redis.hincrby.call_args_list if "daily" in str(c)]
        monthly_calls = [c for c in mock_redis.hincrby.call_args_list if "monthly" in str(c)]
        total_calls = [c for c in mock_redis.hincrby.call_args_list if "total" in str(c)]

        assert len(daily_calls) >= 1
        assert len(monthly_calls) >= 1
        assert len(total_calls) >= 1


@pytest.mark.asyncio
async def test_track_embedding_cost_calculation():
    """Test cost calculation is correct."""
    mock_redis = MagicMock()

    with patch("app.observability.cost_tracking.get_redis", return_value=mock_redis):
        # text-embedding-3-small: $0.02 per 1M tokens
        # 1000 tokens = $0.00002
        await track_embedding_cost(
            model="text-embedding-3-small",
            tokens=1000,
            num_embeddings=10,
        )

        # Check that cost was calculated correctly
        cost_calls = [c for c in mock_redis.hincrbyfloat.call_args_list if "cost_usd" in str(c)]
        assert len(cost_calls) >= 1

        # Cost should be approximately 0.00002
        for call in cost_calls:
            cost_value = call[0][2] if len(call[0]) > 2 else call[1].get("amount", 0)
            assert 0.00001 < cost_value < 0.00003


@pytest.mark.asyncio
async def test_track_embedding_cost_large_model():
    """Test cost calculation for large model."""
    mock_redis = MagicMock()

    with patch("app.observability.cost_tracking.get_redis", return_value=mock_redis):
        # text-embedding-3-large: $0.13 per 1M tokens
        await track_embedding_cost(
            model="text-embedding-3-large",
            tokens=1_000_000,
            num_embeddings=1000,
        )

        # Check that higher cost is tracked
        cost_calls = [c for c in mock_redis.hincrbyfloat.call_args_list if "cost_usd" in str(c)]
        assert len(cost_calls) >= 1

        # Cost should be approximately $0.13
        for call in cost_calls:
            cost_value = call[0][2] if len(call[0]) > 2 else call[1].get("amount", 0)
            assert 0.12 < cost_value < 0.14


@pytest.mark.asyncio
async def test_track_embedding_cost_unknown_model():
    """Test tracking cost for unknown model uses default."""
    mock_redis = MagicMock()

    with patch("app.observability.cost_tracking.get_redis", return_value=mock_redis):
        await track_embedding_cost(
            model="unknown-model",
            tokens=1000,
            num_embeddings=10,
        )

        # Should use default cost (text-embedding-3-small)
        cost_calls = [c for c in mock_redis.hincrbyfloat.call_args_list if "cost_usd" in str(c)]
        assert len(cost_calls) >= 1


@pytest.mark.asyncio
async def test_track_embedding_cost_redis_failure():
    """Test that Redis failures are handled gracefully."""
    mock_redis = MagicMock()
    mock_redis.hincrby.side_effect = Exception("Redis connection failed")

    with patch("app.observability.cost_tracking.get_redis", return_value=mock_redis):
        # Should not raise exception
        await track_embedding_cost(
            model="text-embedding-3-small",
            tokens=1000,
            num_embeddings=10,
        )


@pytest.mark.asyncio
async def test_get_daily_cost(mock_redis):
    """Test retrieving daily cost."""
    mock_redis.hgetall.return_value = {
        b"tokens": b"5000",
        b"embeddings": b"50",
        b"cost_usd": b"0.001",
    }

    with patch("app.observability.cost_tracking.get_redis", return_value=mock_redis):
        cost = await get_daily_cost("2026-08-04")

        assert cost["tokens"] == 5000
        assert cost["embeddings"] == 50
        assert cost["cost_usd"] == 0.001


@pytest.mark.asyncio
async def test_get_daily_cost_no_data(mock_redis):
    """Test retrieving daily cost with no data."""
    mock_redis.hgetall.return_value = {}

    with patch("app.observability.cost_tracking.get_redis", return_value=mock_redis):
        cost = await get_daily_cost("2026-08-04")

        assert cost["tokens"] == 0
        assert cost["embeddings"] == 0
        assert cost["cost_usd"] == 0.0


@pytest.mark.asyncio
async def test_get_daily_cost_default_today(mock_redis):
    """Test that get_daily_cost defaults to today."""
    mock_redis.hgetall.return_value = {}

    with patch("app.observability.cost_tracking.get_redis", return_value=mock_redis):
        _ = await get_daily_cost()

        # Should be called with today's date
        today = datetime.now(UTC).date().isoformat()
        mock_redis.hgetall.assert_called_with(f"embedding:cost:daily:{today}")


@pytest.mark.asyncio
async def test_get_monthly_cost(mock_redis):
    """Test retrieving monthly cost."""
    mock_redis.hgetall.return_value = {
        b"tokens": b"150000",
        b"embeddings": b"1500",
        b"cost_usd": b"0.03",
    }

    with patch("app.observability.cost_tracking.get_redis", return_value=mock_redis):
        cost = await get_monthly_cost("2026-08")

        assert cost["tokens"] == 150000
        assert cost["embeddings"] == 1500
        assert cost["cost_usd"] == 0.03


@pytest.mark.asyncio
async def test_get_monthly_cost_default_current(mock_redis):
    """Test that get_monthly_cost defaults to current month."""
    mock_redis.hgetall.return_value = {}

    with patch("app.observability.cost_tracking.get_redis", return_value=mock_redis):
        _ = await get_monthly_cost()

        # Should be called with current month
        month = datetime.now(UTC).strftime("%Y-%m")
        mock_redis.hgetall.assert_called_with(f"embedding:cost:monthly:{month}")


@pytest.mark.asyncio
async def test_get_total_cost(mock_redis):
    """Test retrieving total cost."""
    mock_redis.hgetall.return_value = {
        b"tokens": b"5000000",
        b"embeddings": b"50000",
        b"cost_usd": b"0.10",
    }

    with patch("app.observability.cost_tracking.get_redis", return_value=mock_redis):
        cost = await get_total_cost()

        assert cost["tokens"] == 5000000
        assert cost["embeddings"] == 50000
        assert cost["cost_usd"] == 0.10

        mock_redis.hgetall.assert_called_with("embedding:cost:total")


@pytest.mark.asyncio
async def test_get_cost_redis_failure(mock_redis):
    """Test that cost retrieval failures return zeros."""
    mock_redis.hgetall.side_effect = Exception("Redis error")

    with patch("app.observability.cost_tracking.get_redis", return_value=mock_redis):
        cost = await get_daily_cost()

        # Should return zeros instead of raising
        assert cost["tokens"] == 0
        assert cost["embeddings"] == 0
        assert cost["cost_usd"] == 0.0


def test_track_embedding_failure():
    """Test tracking embedding failure updates Prometheus."""
    with patch("app.observability.cost_tracking.EMBEDDING_REQUESTS_TOTAL") as mock_counter:
        track_embedding_failure("text-embedding-3-small")

        # Should increment failure counter
        mock_counter.labels.assert_called_with(model="text-embedding-3-small", status="failure")
        mock_counter.labels.return_value.inc.assert_called_once()


def test_update_queue_size():
    """Test updating queue size gauge."""
    with patch("app.observability.cost_tracking.EMBEDDING_QUEUE_SIZE") as mock_gauge:
        update_queue_size(42)

        mock_gauge.set.assert_called_with(42)


def test_embedding_costs_defined():
    """Test that embedding costs are defined for known models."""
    assert "text-embedding-3-small" in EMBEDDING_COSTS
    assert "text-embedding-3-large" in EMBEDDING_COSTS
    assert "text-embedding-ada-002" in EMBEDDING_COSTS

    # Check costs are reasonable
    assert EMBEDDING_COSTS["text-embedding-3-small"] < EMBEDDING_COSTS["text-embedding-3-large"]
