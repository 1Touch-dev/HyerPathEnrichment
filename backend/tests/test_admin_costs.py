"""Tests for admin cost API endpoints."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.models import User
from app.main import app


@pytest.fixture
def superuser():
    """Mock superuser for testing."""
    user = MagicMock(spec=User)
    user.id = "test-superuser-id"
    user.email = "admin@example.com"
    user.is_verified = True
    user.is_superuser = True
    user.is_active = True
    user.deleted_at = None
    return user


@pytest.fixture
def regular_user():
    """Mock regular user for testing."""
    user = MagicMock(spec=User)
    user.id = "test-user-id"
    user.email = "user@example.com"
    user.is_verified = True
    user.is_superuser = False
    user.is_active = True
    user.deleted_at = None
    return user


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


def test_admin_cost_endpoints_require_auth(client):
    """Test that admin endpoints require authentication."""
    endpoints = [
        "/api/admin/costs/daily",
        "/api/admin/costs/monthly",
        "/api/admin/costs/total",
        "/api/admin/costs/top-users",
        "/api/admin/costs/breakdown",
    ]

    for endpoint in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 401


def test_admin_cost_endpoints_require_superuser(client, regular_user):
    """Test that admin endpoints require superuser access."""
    with patch("app.modules.admin.router.require_superuser") as mock_require:
        mock_require.side_effect = Exception("Forbidden")

        response = client.get("/api/admin/costs/daily")
        assert response.status_code != 200  # Should fail


@pytest.mark.asyncio
async def test_get_daily_costs_superuser(superuser):
    """Test getting daily costs as superuser."""
    from app.modules.admin.router import get_daily_costs

    with patch("app.modules.admin.router.get_daily_cost") as mock_embed:
        with patch("app.modules.admin.router.get_daily_llm_cost") as mock_llm:
            mock_embed.return_value = {
                "tokens": 5000,
                "embeddings": 50,
                "cost_usd": 0.1,
            }
            mock_llm.return_value = {
                "input_tokens": 10000,
                "output_tokens": 5000,
                "cost_usd": 0.05,
            }

            response = await get_daily_costs(date="2026-08-06", _user=superuser)

            assert response.date == "2026-08-06"
            assert response.embeddings.cost_usd == 0.1
            assert response.llm.cost_usd == 0.05
            assert abs(response.total_cost_usd - 0.15) < 0.001


@pytest.mark.asyncio
async def test_get_monthly_costs_superuser(superuser):
    """Test getting monthly costs as superuser."""
    from app.modules.admin.router import get_monthly_costs

    with patch("app.modules.admin.router.get_monthly_cost") as mock_embed:
        with patch("app.modules.admin.router.get_monthly_llm_cost") as mock_llm:
            mock_embed.return_value = {
                "tokens": 150000,
                "embeddings": 1500,
                "cost_usd": 3.0,
            }
            mock_llm.return_value = {
                "input_tokens": 500000,
                "output_tokens": 250000,
                "cost_usd": 1.5,
            }

            response = await get_monthly_costs(month="2026-08", _user=superuser)

            assert response.month == "2026-08"
            assert response.embeddings.cost_usd == 3.0
            assert response.llm.cost_usd == 1.5
            assert response.total_cost_usd == 4.5


@pytest.mark.asyncio
async def test_get_total_costs_superuser(superuser):
    """Test getting total costs as superuser."""
    from app.modules.admin.router import get_total_costs

    with patch("app.modules.admin.router.get_total_cost") as mock_embed:
        with patch("app.workers.queue.get_redis_connection") as mock_redis_conn:
            mock_embed.return_value = {
                "tokens": 5000000,
                "embeddings": 50000,
                "cost_usd": 100.0,
            }

            mock_redis = MagicMock()
            mock_redis.hgetall.return_value = {
                b"input_tokens": b"10000000",
                b"output_tokens": b"5000000",
                b"cost_usd": b"50.0",
            }
            mock_redis_conn.return_value = mock_redis

            response = await get_total_costs(_user=superuser)

            assert response.embeddings.cost_usd == 100.0
            assert response.llm.cost_usd == 50.0
            assert response.total_cost_usd == 150.0


@pytest.mark.asyncio
async def test_get_top_users_superuser(superuser):
    """Test getting top users by cost as superuser."""
    from app.modules.admin.router import get_top_users

    with patch("app.modules.admin.router.get_user_costs") as mock_get_users:
        mock_get_users.return_value = [
            {
                "user_id": "user1",
                "input_tokens": 20000,
                "output_tokens": 10000,
                "cost_usd": 0.20,
            },
            {
                "user_id": "user2",
                "input_tokens": 10000,
                "output_tokens": 5000,
                "cost_usd": 0.10,
            },
        ]

        response = await get_top_users(limit=10, _user=superuser)

        assert len(response.users) == 2
        assert response.users[0].user_id == "user1"
        assert response.users[0].cost_usd == 0.20


@pytest.mark.asyncio
async def test_get_cost_breakdown_superuser(superuser):
    """Test getting cost breakdown as superuser."""
    from app.modules.admin.router import get_cost_breakdown

    with patch("app.modules.admin.router.get_daily_cost") as mock_daily_embed:
        with patch("app.modules.admin.router.get_daily_llm_cost") as mock_daily_llm:
            with patch("app.modules.admin.router.get_monthly_cost") as mock_monthly_embed:
                with patch("app.modules.admin.router.get_monthly_llm_cost") as mock_monthly_llm:
                    with patch("app.modules.admin.router.get_total_cost") as mock_total_embed:
                        with patch("app.workers.queue.get_redis_connection") as mock_redis_conn:
                            # Mock daily
                            mock_daily_embed.return_value = {
                                "tokens": 5000,
                                "embeddings": 50,
                                "cost_usd": 0.1,
                            }
                            mock_daily_llm.return_value = {
                                "input_tokens": 10000,
                                "output_tokens": 5000,
                                "cost_usd": 0.05,
                            }

                            # Mock monthly
                            mock_monthly_embed.return_value = {
                                "tokens": 150000,
                                "embeddings": 1500,
                                "cost_usd": 3.0,
                            }
                            mock_monthly_llm.return_value = {
                                "input_tokens": 500000,
                                "output_tokens": 250000,
                                "cost_usd": 1.5,
                            }

                            # Mock total
                            mock_total_embed.return_value = {
                                "tokens": 5000000,
                                "embeddings": 50000,
                                "cost_usd": 100.0,
                            }

                            mock_redis = MagicMock()
                            mock_redis.hgetall.return_value = {
                                b"input_tokens": b"10000000",
                                b"output_tokens": b"5000000",
                                b"cost_usd": b"50.0",
                            }
                            mock_redis_conn.return_value = mock_redis

                            response = await get_cost_breakdown(_user=superuser)

                            assert abs(response.daily.total_cost_usd - 0.15) < 0.001
                            assert response.monthly.total_cost_usd == 4.5
                            assert response.total.total_cost_usd == 150.0


def test_cost_summary_schema():
    """Test CostSummary response model."""
    from app.modules.admin.router import CostSummary

    summary = CostSummary(
        tokens=5000,
        embeddings=50,
        input_tokens=None,
        output_tokens=None,
        cost_usd=0.1,
    )

    assert summary.tokens == 5000
    assert summary.embeddings == 50
    assert summary.cost_usd == 0.1


def test_user_cost_schema():
    """Test UserCost response model."""
    from app.modules.admin.router import UserCost

    user_cost = UserCost(
        user_id="test-user",
        input_tokens=10000,
        output_tokens=5000,
        cost_usd=0.15,
    )

    assert user_cost.user_id == "test-user"
    assert user_cost.input_tokens == 10000
    assert user_cost.cost_usd == 0.15
