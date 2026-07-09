import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.observability.tier1_metrics import tier1_cache_hits_total, tier1_scrape_total


def test_tier1_metrics_increment_without_error() -> None:
    tier1_cache_hits_total.inc()
    tier1_scrape_total.labels(outcome="success").inc()


def test_metrics_endpoint_returns_200() -> None:
    tier1_cache_hits_total.inc()
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
