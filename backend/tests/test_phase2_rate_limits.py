"""Chunk 5: tiered rate limits on documents/upload, signals/changedetection webhook,
and job-matching/scan.

Covers `app.dependencies.rate_limit.enforce_documents_upload_rate_limit`,
`enforce_signals_webhook_rate_limit`, and `enforce_job_matching_scan_rate_limit`, all of
which delegate to the same `_enforce`/`_client_id`/`_host_client_id` helpers already
exercised for `sync`/`async`/`compliance`/`auth` scopes (see `test_api_envelopes.py`).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from tests.envelope_helpers import assert_error, assert_success


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _no_signal_webhook_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the public changedetection webhook focused on rate limiting, not token
    auth or outbound notifications (mirrors `test_signals_list.py`)."""
    monkeypatch.setattr(get_settings(), "changedetection_api_key", "")
    monkeypatch.setattr(get_settings(), "notify_webhook_url", "")


def _auth_headers(user_id: str | None = None) -> dict[str, str]:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.api_token}",
        "X-Test-User-ID": user_id or str(uuid4()),
    }


def _post_upload(client: TestClient, headers: dict[str, str]):
    """A minimal fake byte blob is sufficient: the rate-limit dependency runs before
    the route body ever parses the file, so we only care about 429 vs not-429."""
    return client.post(
        "/api/documents/upload",
        headers=headers,
        files={"file": ("test.pdf", b"%PDF-1.4 fake-test-content", "application/pdf")},
    )


def _post_webhook(client: TestClient, watch_id: str = "test-1"):
    with patch("app.modules.signals.router.notify_change_signal", new_callable=AsyncMock):
        return client.post(
            "/api/signals/changedetection",
            json={
                "watch_uuid": watch_id,
                "watch_title": "Test",
                "watch_url": "https://example.com",
            },
        )


def _post_scan(client: TestClient, headers: dict[str, str]):
    """`job_matching/service.py` does `from rq import Queue`, binding its own module-level
    name at import time, so patching `rq.Queue` (as the autouse `fake_redis` fixture does
    for documents) does not reach it -- patch it directly here, same as
    `test_job_matching_api.py::test_trigger_scan_returns_enqueued`."""
    with patch("app.modules.job_matching.service.Queue") as mock_queue_cls:
        mock_queue_cls.return_value.enqueue = MagicMock(return_value=None)
        return client.post("/api/job-matching/scan", headers=headers)


# ---------------------------------------------------------------------------
# Per-route: exceeding the limit returns 429 with the expected envelope
# ---------------------------------------------------------------------------


def test_documents_upload_rate_limit_exceeded(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "max_documents_upload_requests_per_minute", 2)
    headers = _auth_headers()

    assert _post_upload(client, headers).status_code != 429
    assert _post_upload(client, headers).status_code != 429

    body = assert_error(_post_upload(client, headers), 429, "RATE_LIMIT_EXCEEDED")
    assert body["meta"] == {"scope": "documents", "limit_per_minute": 2}


def test_signals_webhook_rate_limit_exceeded(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "max_signals_webhook_requests_per_minute", 2)

    assert_success(_post_webhook(client, "watch-1"), 202)
    assert_success(_post_webhook(client, "watch-2"), 202)

    body = assert_error(_post_webhook(client, "watch-3"), 429, "RATE_LIMIT_EXCEEDED")
    assert body["meta"] == {"scope": "signals", "limit_per_minute": 2}


def test_job_matching_scan_rate_limit_exceeded(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "max_job_matching_scan_requests_per_minute", 2)
    headers = _auth_headers()

    assert_success(_post_scan(client, headers))
    assert_success(_post_scan(client, headers))

    body = assert_error(_post_scan(client, headers), 429, "RATE_LIMIT_EXCEEDED")
    assert body["meta"] == {"scope": "job_matching", "limit_per_minute": 2}


# ---------------------------------------------------------------------------
# Bucket key derivation: Authorization-header-scoped, not per simulated test user
# ---------------------------------------------------------------------------


def test_documents_upload_bucket_scoped_by_auth_header_not_test_user_id(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`_client_id` hashes the raw `Authorization` header value, not `X-Test-User-ID`.
    Two different simulated users sending the same Authorization header must still
    share (and be able to exhaust) the same rate-limit bucket."""
    monkeypatch.setattr(get_settings(), "max_documents_upload_requests_per_minute", 2)
    authorization = {"Authorization": f"Bearer {get_settings().api_token}"}

    first = _post_upload(client, {**authorization, "X-Test-User-ID": str(uuid4())})
    second = _post_upload(client, {**authorization, "X-Test-User-ID": str(uuid4())})
    assert first.status_code != 429
    assert second.status_code != 429

    third = _post_upload(client, {**authorization, "X-Test-User-ID": str(uuid4())})
    body = assert_error(third, 429, "RATE_LIMIT_EXCEEDED")
    assert body["meta"] == {"scope": "documents", "limit_per_minute": 2}


# ---------------------------------------------------------------------------
# Cross-endpoint independence: distinct scope prefixes keep buckets separate
# ---------------------------------------------------------------------------


def test_cross_endpoint_rate_limits_are_independent(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exhausting the `documents` bucket must not affect the `job_matching` bucket,
    even when both calls carry the identical Authorization header (the full scope key
    is `f"{prefix}:{client_id}"`, so differing prefixes keep them separate)."""
    monkeypatch.setattr(get_settings(), "max_documents_upload_requests_per_minute", 1)
    monkeypatch.setattr(get_settings(), "max_job_matching_scan_requests_per_minute", 1)
    headers = _auth_headers()

    assert _post_upload(client, headers).status_code != 429
    assert_error(_post_upload(client, headers), 429, "RATE_LIMIT_EXCEEDED")

    first_scan = _post_scan(client, headers)
    assert first_scan.status_code != 429
    assert_success(first_scan)

    body = assert_error(_post_scan(client, headers), 429, "RATE_LIMIT_EXCEEDED")
    assert body["meta"] == {"scope": "job_matching", "limit_per_minute": 1}


# ---------------------------------------------------------------------------
# Defaults sanity check
# ---------------------------------------------------------------------------


def test_rate_limit_defaults_match_spec() -> None:
    settings = get_settings()
    assert settings.max_documents_upload_requests_per_minute == 10
    assert settings.max_signals_webhook_requests_per_minute == 30
    assert settings.max_job_matching_scan_requests_per_minute == 5


# ---------------------------------------------------------------------------
# Precise per-route wiring: sibling routes on the same router are unaffected
# ---------------------------------------------------------------------------


def test_documents_sibling_route_unaffected_by_upload_rate_limit(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "max_documents_upload_requests_per_minute", 1)
    headers = _auth_headers()

    assert _post_upload(client, headers).status_code != 429
    assert_error(_post_upload(client, headers), 429, "RATE_LIMIT_EXCEEDED")

    sibling = client.get("/api/documents", headers=headers)
    assert sibling.status_code != 429


def test_signals_sibling_route_unaffected_by_webhook_rate_limit(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "max_signals_webhook_requests_per_minute", 1)

    assert_success(_post_webhook(client, "watch-x"), 202)
    assert_error(_post_webhook(client, "watch-y"), 429, "RATE_LIMIT_EXCEEDED")

    sibling = client.get("/api/signals", headers=_auth_headers())
    assert sibling.status_code != 429


def test_job_matching_sibling_route_unaffected_by_scan_rate_limit(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "max_job_matching_scan_requests_per_minute", 1)
    headers = _auth_headers()

    assert_success(_post_scan(client, headers))
    assert_error(_post_scan(client, headers), 429, "RATE_LIMIT_EXCEEDED")

    sibling = client.get("/api/job-matching/preferences", headers=headers)
    assert sibling.status_code != 429
