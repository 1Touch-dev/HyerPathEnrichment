from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.observability.http_metrics import refresh_queue_depth_metric


def test_metrics_expose_http_request_counters_after_traffic() -> None:
    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code == 200
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    body = metrics.text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body
    assert "rq_queue_length" in body


def test_refresh_queue_depth_metric_sets_gauge_from_snapshot() -> None:
    with (
        patch(
            "app.observability.health_alerts.queue_depth_snapshot",
            return_value={"queued": 4, "failed": 1},
        ),
        patch("app.observability.http_metrics.rq_queue_length.set") as set_gauge,
    ):
        refresh_queue_depth_metric()
    set_gauge.assert_called_once_with(4)
