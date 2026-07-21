"""Tests for ops health alerts and notify_ops_alert (mocked webhook)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.clients.notify import notify_ops_alert
from app.core.config import get_settings
from app.observability.health_alerts import (
    HealthProbeResult,
    notify_on_health_failure,
    probe_health_endpoints,
)


@pytest.mark.asyncio
async def test_notify_ops_alert_skipped_when_webhook_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "notify_webhook_url", "")

    sent = await notify_ops_alert(alert="api_health_failed", summary="down")

    assert sent is False


@pytest.mark.asyncio
async def test_notify_ops_alert_posts_non_pii_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "notify_webhook_url", "https://hooks.example/ops")

    with patch("httpx.AsyncClient") as client_cls:
        client = AsyncMock()
        response = AsyncMock()
        response.raise_for_status = lambda: None
        client.post = AsyncMock(return_value=response)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client_cls.return_value = client

        sent = await notify_ops_alert(
            alert="api_health_failed",
            summary="Health probe failed",
            severity="critical",
            details={"health": "ConnectError", "ready": "ok"},
        )

    assert sent is True
    payload = client.post.await_args.kwargs["json"]
    assert payload["source"] == "hyrepath-ops"
    assert payload["alert"] == "api_health_failed"
    assert payload["severity"] == "critical"
    assert "email" not in payload
    assert "identifier" not in payload
    assert payload["details"] == {"health": "ConnectError", "ready": "ok"}
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_probe_health_endpoints_marks_failures() -> None:
    healthy = MagicMock()
    healthy.status_code = 200
    unhealthy = MagicMock()
    unhealthy.status_code = 503

    with patch("httpx.AsyncClient") as client_cls:
        client = AsyncMock()
        client.get = AsyncMock(side_effect=[healthy, unhealthy])
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client_cls.return_value = client

        results = await probe_health_endpoints("http://api.example")

    assert results == [
        HealthProbeResult(path="/health", ok=True, status_code=200, reason="ok"),
        HealthProbeResult(path="/ready", ok=False, status_code=503, reason="http_503"),
    ]


@pytest.mark.asyncio
async def test_notify_on_health_failure_posts_when_probe_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "notify_webhook_url", "https://hooks.example/ops")

    probes = [
        HealthProbeResult(path="/health", ok=False, status_code=None, reason="ConnectError"),
        HealthProbeResult(path="/ready", ok=False, status_code=None, reason="ConnectError"),
    ]

    with (
        patch(
            "app.observability.health_alerts.probe_health_endpoints",
            new_callable=AsyncMock,
            return_value=probes,
        ),
        patch(
            "app.observability.health_alerts.queue_depth_snapshot",
            return_value={"queued": 0, "failed": 0},
        ),
        patch(
            "app.observability.health_alerts.notify_ops_alert",
            new_callable=AsyncMock,
            return_value=True,
        ) as notify,
    ):
        sent = await notify_on_health_failure("http://api.example")

    assert sent is True
    notify.assert_awaited_once()
    kwargs = notify.await_args.kwargs
    assert kwargs["alert"] == "api_health_failed"
    assert kwargs["severity"] == "critical"
    assert "health" in kwargs["details"]


@pytest.mark.asyncio
async def test_notify_on_health_failure_noop_when_healthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "notify_webhook_url", "https://hooks.example/ops")

    probes = [
        HealthProbeResult(path="/health", ok=True, status_code=200, reason="ok"),
        HealthProbeResult(path="/ready", ok=True, status_code=200, reason="ok"),
    ]

    with (
        patch(
            "app.observability.health_alerts.probe_health_endpoints",
            new_callable=AsyncMock,
            return_value=probes,
        ),
        patch(
            "app.observability.health_alerts.queue_depth_snapshot",
            return_value={"queued": 1, "failed": 0},
        ),
        patch(
            "app.observability.health_alerts.notify_ops_alert",
            new_callable=AsyncMock,
        ) as notify,
    ):
        sent = await notify_on_health_failure("http://api.example")

    assert sent is False
    notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_notify_on_queue_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "notify_webhook_url", "https://hooks.example/ops")

    probes = [
        HealthProbeResult(path="/health", ok=True, status_code=200, reason="ok"),
        HealthProbeResult(path="/ready", ok=True, status_code=200, reason="ok"),
    ]

    with (
        patch(
            "app.observability.health_alerts.probe_health_endpoints",
            new_callable=AsyncMock,
            return_value=probes,
        ),
        patch(
            "app.observability.health_alerts.queue_depth_snapshot",
            return_value={"queued": 150, "failed": 0},
        ),
        patch(
            "app.observability.health_alerts.notify_ops_alert",
            new_callable=AsyncMock,
            return_value=True,
        ) as notify,
    ):
        sent = await notify_on_health_failure("http://api.example", queue_depth_warn=100)

    assert sent is True
    assert notify.await_args.kwargs["alert"] == "queue_depth_or_failures"


@pytest.mark.asyncio
async def test_notify_ops_alert_fail_soft_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "notify_webhook_url", "https://hooks.example/ops")

    with patch("httpx.AsyncClient") as client_cls:
        client = AsyncMock()
        client.post = AsyncMock(side_effect=httpx.HTTPError("boom"))
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client_cls.return_value = client

        sent = await notify_ops_alert(alert="x", summary="y")

    assert sent is False
