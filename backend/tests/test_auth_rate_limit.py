"""Tests for auth-route rate limiting (Chunk 3).

Covers ``app.dependencies.rate_limit.enforce_auth_rate_limit`` and its wiring
onto ``POST /auth/register``, ``POST /auth/login``, ``POST /auth/verify-email``,
and ``POST /auth/resend-verification`` in ``app.auth.router``. All four routes
share a single rate-limit bucket keyed only by client IP
(``f"auth:{_host_client_id(request)}"``), not by route.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.dependencies.rate_limit import _host_client_id
from app.main import app
from tests.envelope_helpers import assert_error


def _unique_email() -> str:
    return f"ratelimit-{uuid4().hex}@example.com"


def _register_payload(email: str | None = None) -> dict[str, str]:
    return {
        "email": email or _unique_email(),
        "password": "Password123",
        "first_name": "Rate",
        "last_name": "Limit",
    }


def test_host_client_id_is_stable_and_distinguishes_hosts() -> None:
    """Same host string yields the same id; different hosts yield different ids."""
    request_a = SimpleNamespace(client=SimpleNamespace(host="1.2.3.4"))
    request_b = SimpleNamespace(client=SimpleNamespace(host="5.6.7.8"))

    id_a_first = _host_client_id(request_a)
    id_a_second = _host_client_id(request_a)
    id_b = _host_client_id(request_b)

    assert id_a_first == id_a_second
    assert id_a_first != id_b
    # Sanity: it's a stable, non-trivial hex digest, not the raw host.
    assert id_a_first != "1.2.3.4"
    assert len(id_a_first) == 16


def test_register_rate_limited_after_configured_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """First N register calls succeed; the (N+1)th gets a 429 envelope."""
    monkeypatch.setattr(get_settings(), "max_auth_requests_per_minute", 3)
    client = TestClient(app)

    for _ in range(3):
        response = client.post("/auth/register", json=_register_payload())
        assert response.status_code != 429

    body = assert_error(
        client.post("/auth/register", json=_register_payload()),
        429,
        "RATE_LIMIT_EXCEEDED",
    )
    assert body["error"]["message"] == "rate limit exceeded"
    assert body["meta"] == {"scope": "auth", "limit_per_minute": 3}


def test_register_calls_under_limit_are_not_rate_limited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A call below the configured limit must not be 429."""
    monkeypatch.setattr(get_settings(), "max_auth_requests_per_minute", 5)
    client = TestClient(app)

    response = client.post("/auth/register", json=_register_payload())
    assert response.status_code != 429
    assert response.status_code == 201


def test_auth_rate_limit_bucket_is_shared_across_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """register + login + resend-verification share ONE bucket, not one each."""
    monkeypatch.setattr(get_settings(), "max_auth_requests_per_minute", 4)
    client = TestClient(app)

    # 2 calls to /auth/register
    for _ in range(2):
        response = client.post("/auth/register", json=_register_payload())
        assert response.status_code != 429

    # 2 calls to /auth/login (bad creds are fine -- only the pre-route gate matters)
    for _ in range(2):
        response = client.post(
            "/auth/login",
            json={"email": _unique_email(), "password": "whatever-not-real"},
        )
        assert response.status_code != 429

    # 5th call overall, to a DIFFERENT route in the same auth scope, must 429.
    body = assert_error(
        client.post(
            "/auth/resend-verification",
            json={"email": _unique_email()},
        ),
        429,
        "RATE_LIMIT_EXCEEDED",
    )
    assert body["meta"] == {"scope": "auth", "limit_per_minute": 4}


def test_login_rate_limited_after_configured_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Login alone trips the 429 once its shared bucket is exhausted."""
    monkeypatch.setattr(get_settings(), "max_auth_requests_per_minute", 2)
    client = TestClient(app)

    for _ in range(2):
        response = client.post(
            "/auth/login",
            json={"email": _unique_email(), "password": "whatever-not-real"},
        )
        assert response.status_code != 429

    body = assert_error(
        client.post(
            "/auth/login",
            json={"email": _unique_email(), "password": "whatever-not-real"},
        ),
        429,
        "RATE_LIMIT_EXCEEDED",
    )
    assert body["meta"] == {"scope": "auth", "limit_per_minute": 2}


def test_verify_email_is_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    """verify-email is gated: a 2nd call once the limit of 1 is used up gets 429."""
    monkeypatch.setattr(get_settings(), "max_auth_requests_per_minute", 1)
    client = TestClient(app)

    first = client.post("/auth/verify-email", json={"token": "fake-token"})
    assert first.status_code != 429

    body = assert_error(
        client.post("/auth/verify-email", json={"token": "fake-token"}),
        429,
        "RATE_LIMIT_EXCEEDED",
    )
    assert body["meta"] == {"scope": "auth", "limit_per_minute": 1}


def test_resend_verification_is_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    """resend-verification is gated: a 2nd call with limit=1 gets 429."""
    monkeypatch.setattr(get_settings(), "max_auth_requests_per_minute", 1)
    client = TestClient(app)

    first = client.post("/auth/resend-verification", json={"email": _unique_email()})
    assert first.status_code != 429

    body = assert_error(
        client.post("/auth/resend-verification", json={"email": _unique_email()}),
        429,
        "RATE_LIMIT_EXCEEDED",
    )
    assert body["meta"] == {"scope": "auth", "limit_per_minute": 1}


def test_unrelated_auth_routes_are_not_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    """/auth/me, /auth/logout, /auth/refresh, /auth/delete-account don't share the scope."""
    monkeypatch.setattr(get_settings(), "max_auth_requests_per_minute", 1)
    client = TestClient(app)

    # Exhaust the shared auth-scope bucket via a gated route first.
    exhausting = client.post("/auth/register", json=_register_payload())
    assert exhausting.status_code != 429
    exhausted = client.post("/auth/register", json=_register_payload())
    assert exhausted.status_code == 429

    # None of these are wired with enforce_auth_rate_limit, so despite the
    # bucket above being exhausted, they must never return 429 (they will
    # likely 401 due to missing/invalid cookie auth, which is expected).
    me_response = client.get("/auth/me")
    assert me_response.status_code != 429

    logout_response = client.post("/auth/logout")
    assert logout_response.status_code != 429

    refresh_response = client.post("/auth/refresh")
    assert refresh_response.status_code != 429

    delete_response = client.post("/auth/delete-account")
    assert delete_response.status_code != 429
