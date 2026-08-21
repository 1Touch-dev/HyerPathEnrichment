"""System health: self-checks always real; Prometheus panel fail-soft when
PROMETHEUS_QUERY_URL unset (mocked HTTP when set, per 'no live external
calls') (phase2_admin_module.md §9.9).

INDIRECT: the plan's sketch does
`monkeypatch.setattr("app.core.config.get_settings().prometheus_query_url", ...)`,
which is invalid Python (setattr's second argument must be a string attribute
name, not a dotted call expression) and also fights `get_settings()`'s
`@lru_cache` — mutating the cached instance would leak into every other test
using it. Adapted to `monkeypatch.setattr(settings, "prometheus_query_url", ...)`
on the actual cached instance, which is what the plan's intent requires and is
this repo's normal way to override settings in tests (see
`app.core.config.get_settings`).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_health_without_prometheus_configured(db_session, monkeypatch, mock_redis):
    from app.core.config import get_settings
    from app.modules.admin.health import get_system_health

    settings = get_settings()
    monkeypatch.setattr(settings, "prometheus_query_url", "")

    result = await get_system_health(db_session)
    assert result.prometheus_configured is False
    assert result.signals == {}
    assert result.database_ok is True


async def test_health_prometheus_unreachable_fails_soft(db_session, monkeypatch, mock_redis):
    """INDIRECT (judgment call): mocks the HTTP client to raise a connection
    error rather than pointing at a real unreachable host, per 'no live
    external calls in CI' (RULE.md) — a real DNS/connect attempt could be slow
    or flaky depending on the sandbox's network policy, whereas this is
    instant and deterministic while still exercising the exact `except
    Exception` fail-soft branch in app/modules/admin/health.py."""
    from unittest.mock import patch

    from app.core.config import get_settings
    from app.modules.admin.health import get_system_health

    settings = get_settings()
    monkeypatch.setattr(settings, "prometheus_query_url", "http://unreachable:9090")

    with patch(
        "app.modules.admin.health.httpx.AsyncClient",
        side_effect=ConnectionError("mocked: prometheus unreachable"),
    ):
        result = await get_system_health(db_session)

    assert result.prometheus_configured is True
    assert all(v is None for v in result.signals.values())


async def test_health_prometheus_configured_and_reachable_returns_signals(
    db_session, monkeypatch, mock_redis
):
    """Complements the fail-soft test above: when Prometheus IS reachable, the
    four golden signals are parsed from its response shape. Mocks the HTTP
    call per 'no live external calls in CI' (RULE.md) — never hits a real
    Prometheus."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.core.config import get_settings
    from app.modules.admin.health import get_system_health

    settings = get_settings()
    monkeypatch.setattr(settings, "prometheus_query_url", "http://prometheus:9090")

    def _fake_response(url, params=None):
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"data": {"result": [{"value": [0, "1.5"]}]}}
        return response

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=_fake_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.modules.admin.health.httpx.AsyncClient", return_value=mock_client):
        result = await get_system_health(db_session)

    assert result.prometheus_configured is True
    assert result.signals["latency_p95_seconds"] == 1.5
    assert result.signals["traffic_requests_per_sec"] == 1.5


async def test_health_database_ok_and_redis_ok_true_under_normal_conditions(db_session, mock_redis):
    from app.modules.admin.health import get_system_health

    result = await get_system_health(db_session)
    assert result.database_ok is True
    assert result.redis_ok is True
    assert result.database_latency_ms >= 0
    assert result.redis_latency_ms >= 0
