"""Signal list API tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


AUTH_HEADERS = {"Authorization": "Bearer change-me"}


def _post_signal(client: TestClient, watch_id: str, title: str, url: str) -> None:
    with patch("app.modules.signals.router.notify_change_signal", new_callable=AsyncMock):
        response = client.post(
            "/api/signals/changedetection",
            json={
                "watch_uuid": watch_id,
                "watch_title": title,
                "watch_url": url,
            },
        )
    assert response.status_code == 202


def test_list_signals_pagination(client: TestClient) -> None:
    _post_signal(client, "watch-a", "Alpha", "https://alpha.example")
    _post_signal(client, "watch-b", "Beta", "https://beta.example")
    _post_signal(client, "watch-c", "Gamma", "https://gamma.example")

    page_one = client.get("/api/signals?limit=2&offset=0", headers=AUTH_HEADERS)
    assert page_one.status_code == 200
    payload = page_one.json()
    assert payload["total"] >= 3
    assert payload["limit"] == 2
    assert payload["offset"] == 0
    assert len(payload["signals"]) == 2

    page_two = client.get("/api/signals?limit=2&offset=2", headers=AUTH_HEADERS)
    assert page_two.status_code == 200
    payload_two = page_two.json()
    assert payload_two["limit"] == 2
    assert payload_two["offset"] == 2
    assert len(payload_two["signals"]) >= 1

    page_one_ids = {item["id"] for item in page_one.json()["signals"]}
    page_two_ids = {item["id"] for item in payload_two["signals"]}
    assert page_one_ids.isdisjoint(page_two_ids)


def test_list_signals_requires_bearer(client: TestClient) -> None:
    response = client.get("/api/signals")
    assert response.status_code == 401
    assert response.json()["detail"] == "unauthorized"


def test_webhook_persists_before_notify(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "changedetection_api_key", "")
    monkeypatch.setattr(get_settings(), "notify_webhook_url", "")

    watch_id = "persist-watch-1"
    with patch("app.modules.signals.router.notify_change_signal", new_callable=AsyncMock) as notify:
        response = client.post(
            "/api/signals/changedetection",
            json={
                "watch_uuid": watch_id,
                "watch_title": "Persist Test",
                "watch_url": "https://persist.example",
            },
        )

    assert response.status_code == 202
    notify.assert_awaited_once()

    listing = client.get("/api/signals?limit=10&offset=0", headers=AUTH_HEADERS)
    assert listing.status_code == 200
    signals = listing.json()["signals"]
    match = next((item for item in signals if item["watch_id"] == watch_id), None)
    assert match is not None
    assert match["title"] == "Persist Test"
    assert match["url"] == "https://persist.example"
    assert match["source"] == "changedetection"
