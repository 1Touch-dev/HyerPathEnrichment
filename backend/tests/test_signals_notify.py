"""Change-signal webhook and notify provider tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.clients.notify import notify_change_signal


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_changedetection_webhook_accepts_without_token_when_key_unset(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "changedetection_api_key", "")
    monkeypatch.setattr(get_settings(), "notify_webhook_url", "")

    with patch("app.modules.signals.router.notify_change_signal", new_callable=AsyncMock) as notify:
        response = client.post(
            "/api/signals/changedetection",
            json={
                "watch_uuid": "abc-123",
                "watch_title": "Acme Careers",
                "watch_url": "https://acme.example/careers",
            },
        )

    assert response.status_code == 202
    assert response.json()["data"] == {"status": "accepted"}
    notify.assert_awaited_once_with(
        watch_id="abc-123",
        title="Acme Careers",
        url="https://acme.example/careers",
        timestamp=None,
    )


def test_changedetection_webhook_rejects_invalid_token(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "changedetection_api_key", "secret-token")

    response = client.post(
        "/api/signals/changedetection",
        json={"watch_uuid": "abc-123"},
    )

    assert response.status_code == 401


def test_changedetection_webhook_accepts_valid_token(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "changedetection_api_key", "secret-token")
    monkeypatch.setattr(get_settings(), "notify_webhook_url", "")

    with patch("app.modules.signals.router.notify_change_signal", new_callable=AsyncMock):
        response = client.post(
            "/api/signals/changedetection",
            headers={"X-Signal-Token": "secret-token"},
            json={"uuid": "def-456", "title": "News", "url": "https://news.example"},
        )

    assert response.status_code == 202


@pytest.mark.asyncio
async def test_notify_skipped_when_webhook_url_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "notify_webhook_url", "")

    sent = await notify_change_signal(
        watch_id="w1",
        title="Example",
        url="https://example.com",
    )

    assert sent is False


@pytest.mark.asyncio
async def test_notify_posts_non_pii_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "notify_webhook_url", "https://hooks.example/notify")

    with patch("httpx.AsyncClient") as client_cls:
        client = AsyncMock()
        response = AsyncMock()
        response.raise_for_status = lambda: None
        client.post = AsyncMock(return_value=response)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client_cls.return_value = client

        sent = await notify_change_signal(
            watch_id="w1",
            title="Careers",
            url="https://acme.example/jobs",
            timestamp="1710000000",
        )

    assert sent is True
    client.post.assert_awaited_once()
    call_kwargs = client.post.await_args.kwargs
    assert call_kwargs["json"] == {
        "source": "changedetection",
        "watch_id": "w1",
        "title": "Careers",
        "url": "https://acme.example/jobs",
        "timestamp": "1710000000",
    }


@pytest.mark.asyncio
async def test_notify_fail_soft_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "notify_webhook_url", "https://hooks.example/notify")

    with patch("httpx.AsyncClient") as client_cls:
        client = AsyncMock()
        client.post = AsyncMock(side_effect=httpx.HTTPError("boom"))
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client_cls.return_value = client

        sent = await notify_change_signal(
            watch_id="w1",
            title="Careers",
            url="https://acme.example/jobs",
        )

    assert sent is False
