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


@pytest.fixture(autouse=True)
def _signal_webhook_test_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin a known webhook token so tests do not depend on local .env secrets."""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "changedetection_api_key", "test-signal-token")
    monkeypatch.setattr(get_settings(), "notify_webhook_url", "")


SIGNAL_HEADERS = {"X-Signal-Token": "test-signal-token"}


def _post_signal(client: TestClient, watch_id: str, title: str, url: str) -> None:
    with patch("app.modules.signals.router.notify_change_signal", new_callable=AsyncMock):
        response = client.post(
            "/api/signals/changedetection",
            headers=SIGNAL_HEADERS,
            json={
                "watch_uuid": watch_id,
                "watch_title": title,
                "watch_url": url,
            },
        )
    assert response.status_code == 202


def test_list_signals_pagination(client: TestClient, superuser, auth_headers) -> None:
    _post_signal(client, "watch-a", "Alpha", "https://alpha.example")
    _post_signal(client, "watch-b", "Beta", "https://beta.example")
    _post_signal(client, "watch-c", "Gamma", "https://gamma.example")

    staff_headers = auth_headers(superuser.id)
    page_one = client.get("/api/signals?limit=2&offset=0", headers=staff_headers)
    assert page_one.status_code == 200
    payload = page_one.json()["data"]
    assert payload["total"] >= 3
    assert payload["limit"] == 2
    assert payload["offset"] == 0
    assert len(payload["signals"]) == 2

    page_two = client.get("/api/signals?limit=2&offset=2", headers=staff_headers)
    assert page_two.status_code == 200
    payload_two = page_two.json()["data"]
    assert payload_two["limit"] == 2
    assert payload_two["offset"] == 2
    assert len(payload_two["signals"]) >= 1

    page_one_ids = {item["id"] for item in page_one.json()["data"]["signals"]}
    page_two_ids = {item["id"] for item in payload_two["signals"]}
    assert page_one_ids.isdisjoint(page_two_ids)


def test_list_signals_requires_bearer(client: TestClient) -> None:
    response = client.get("/api/signals")
    assert response.status_code == 401
    assert "authorization" in response.json()["error"]["message"].lower()


def test_list_signals_rejects_roleless_verified_user(
    client: TestClient, regular_user, auth_headers
) -> None:
    response = client.get("/api/signals", headers=auth_headers(regular_user.id))
    assert response.status_code == 403
    assert response.json()["error"]["message"] == "Staff access required"


def test_webhook_persists_before_notify(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    superuser,
    auth_headers,
) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "changedetection_api_key", "test-signal-token")
    monkeypatch.setattr(get_settings(), "notify_webhook_url", "")

    watch_id = "persist-watch-1"
    with patch("app.modules.signals.router.notify_change_signal", new_callable=AsyncMock) as notify:
        response = client.post(
            "/api/signals/changedetection",
            headers={"X-Signal-Token": "test-signal-token"},
            json={
                "watch_uuid": watch_id,
                "watch_title": "Persist Test",
                "watch_url": "https://persist.example",
            },
        )

    assert response.status_code == 202
    notify.assert_awaited_once()

    listing = client.get(
        "/api/signals?limit=10&offset=0",
        headers=auth_headers(superuser.id),
    )
    assert listing.status_code == 200
    signals = listing.json()["data"]["signals"]
    match = next((item for item in signals if item["watch_id"] == watch_id), None)
    assert match is not None
    assert match["title"] == "Persist Test"
    assert match["url"] == "https://persist.example"
    assert match["source"] == "changedetection"
