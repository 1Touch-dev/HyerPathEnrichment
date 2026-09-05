"""Tests for the CORS allowlist and tightened method/header configuration.

Covers two layers:
  1. A fresh, purpose-built Starlette/FastAPI app whose ``CORSMiddleware`` is
     constructed with the exact same kwargs as ``app/main.py`` but a
     deterministic, controlled ``allow_origins`` list. This avoids fighting
     the shared ``app.main.app`` singleton (whose CORS middleware was already
     constructed at import time from whatever ``.env``/defaults were in
     effect) and lets us assert precise allow/deny behavior for origins,
     methods, and headers.
  2. The real ``app.main.app`` instance, to exercise the actual wiring
     end-to-end against whatever origin(s) ``get_settings().cors_allowed_origins``
     currently reports (reflecting the real, already-loaded config).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.cors import resolve_cors_origins
from app.main import app as real_app
from app.modules.brands.models import Brand

DISALLOWED_ORIGIN = "https://evil-not-allowed.example.com"
FRESH_ALLOWED_ORIGIN = "https://allowed.example.com"


def _build_fresh_cors_app() -> FastAPI:
    """Minimal app mirroring main.py's exact CORSMiddleware kwargs.

    Only ``allow_origins`` differs (a fixed, known value) so origin/method/
    header allow-vs-deny behavior can be asserted deterministically.
    """
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[FRESH_ALLOWED_ORIGIN],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["*"],
        max_age=600,
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


# ---------------------------------------------------------------------------
# Fresh, controlled app: origin allow/deny
# ---------------------------------------------------------------------------


def test_fresh_app_preflight_allowed_origin_succeeds() -> None:
    client = TestClient(_build_fresh_cors_app())
    response = client.options(
        "/health",
        headers={
            "Origin": FRESH_ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == FRESH_ALLOWED_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"


def test_fresh_app_preflight_disallowed_origin_rejected() -> None:
    client = TestClient(_build_fresh_cors_app())
    response = client.options(
        "/health",
        headers={
            "Origin": DISALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    # Starlette's CORSMiddleware returns 400 for a disallowed preflight and
    # never adds an Access-Control-Allow-Origin header for that origin.
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_fresh_app_simple_request_disallowed_origin_no_acao_header() -> None:
    """A simple (non-preflight) GET still succeeds, but without ACAO echoed back."""
    client = TestClient(_build_fresh_cors_app())
    response = client.get("/health", headers={"Origin": DISALLOWED_ORIGIN})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "access-control-allow-origin" not in response.headers


def test_fresh_app_simple_request_allowed_origin_echoes_acao_header() -> None:
    """Sanity check contrasting the disallowed case: allowed origin does get ACAO."""
    client = TestClient(_build_fresh_cors_app())
    response = client.get("/health", headers={"Origin": FRESH_ALLOWED_ORIGIN})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == FRESH_ALLOWED_ORIGIN


# ---------------------------------------------------------------------------
# Fresh, controlled app: tightened allow_methods
# ---------------------------------------------------------------------------


def test_fresh_app_preflight_allowed_method_permitted() -> None:
    client = TestClient(_build_fresh_cors_app())
    response = client.options(
        "/health",
        headers={
            "Origin": FRESH_ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "DELETE",
        },
    )
    assert response.status_code == 200
    assert "DELETE" in response.headers["access-control-allow-methods"]


def test_fresh_app_preflight_disallowed_method_rejected() -> None:
    client = TestClient(_build_fresh_cors_app())
    response = client.options(
        "/health",
        headers={
            "Origin": FRESH_ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "TRACE",
        },
    )
    assert response.status_code == 400
    assert "TRACE" not in response.headers["access-control-allow-methods"]


# ---------------------------------------------------------------------------
# Fresh, controlled app: tightened allow_headers
# ---------------------------------------------------------------------------


def test_fresh_app_preflight_allowed_headers_succeeds() -> None:
    client = TestClient(_build_fresh_cors_app())
    response = client.options(
        "/health",
        headers={
            "Origin": FRESH_ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization, Content-Type",
        },
    )
    assert response.status_code == 200


def test_fresh_app_preflight_disallowed_header_rejected() -> None:
    client = TestClient(_build_fresh_cors_app())
    response = client.options(
        "/health",
        headers={
            "Origin": FRESH_ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Custom-Nonsense-Header",
        },
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Fresh, controlled app: max_age
# ---------------------------------------------------------------------------


def test_fresh_app_preflight_max_age_600() -> None:
    client = TestClient(_build_fresh_cors_app())
    response = client.options(
        "/health",
        headers={
            "Origin": FRESH_ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-max-age"] == "600"


# ---------------------------------------------------------------------------
# Real app.main.app: end-to-end wiring against the actual configured allowlist
# ---------------------------------------------------------------------------


def test_real_app_preflight_allowed_origin_succeeds() -> None:
    real_allowed_origin = get_settings().cors_allowed_origins[0]
    client = TestClient(real_app)
    response = client.options(
        "/health",
        headers={
            "Origin": real_allowed_origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == real_allowed_origin
    assert response.headers["access-control-allow-credentials"] == "true"


def test_real_app_preflight_disallowed_origin_rejected() -> None:
    assert DISALLOWED_ORIGIN not in get_settings().cors_allowed_origins
    client = TestClient(real_app)
    response = client.options(
        "/health",
        headers={
            "Origin": DISALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


# ---------------------------------------------------------------------------
# Settings.cors_allowed_origins unit tests (no HTTP)
# ---------------------------------------------------------------------------


def test_cors_allowed_origins_parses_comma_separated_list() -> None:
    settings = Settings(
        CORS_ALLOWED_ORIGINS="https://a.example.com, https://b.example.com",
        FRONTEND_URL="https://ignored.example.com",
    )
    assert settings.cors_allowed_origins == [
        "https://a.example.com",
        "https://b.example.com",
    ]


def test_cors_allowed_origins_falls_back_to_frontend_url() -> None:
    settings = Settings(CORS_ALLOWED_ORIGINS="", FRONTEND_URL="https://fallback.example.com")
    assert settings.cors_allowed_origins == ["https://fallback.example.com"]


def test_cors_allowed_origins_falls_back_to_localhost() -> None:
    settings = Settings(CORS_ALLOWED_ORIGINS="", FRONTEND_URL="")
    assert settings.cors_allowed_origins == ["http://localhost:3000"]


# ---------------------------------------------------------------------------
# resolve_cors_origins: per-brand custom_domain retrofit
# (machine-1-tenancy-core/04-cors-and-ratelimit-retrofit.md)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_cors_origins_disabled_flag_is_byte_for_byte_unchanged(db_session) -> None:
    """enable_brand_cors_origins=False (default) must leave the resolved
    allow-list identical to the static settings-based list, even when active
    brands with custom_domain rows exist -- regression safety for existing
    deployments that haven't opted in."""
    db_session.add(
        Brand(
            name="Untouched Co",
            slug="untouched-co",
            custom_domain="careers.untouched.example.com",
            is_active=True,
        )
    )
    await db_session.commit()

    settings = Settings(
        CORS_ALLOWED_ORIGINS="https://a.example.com,https://b.example.com",
        enable_brand_cors_origins=False,
    )
    origins = await resolve_cors_origins(settings, db_session)
    assert origins == sorted(settings.cors_allowed_origins)
    assert "careers.untouched.example.com" not in origins


@pytest.mark.asyncio
async def test_resolve_cors_origins_includes_active_brand_custom_domain(db_session) -> None:
    """With the flag on, an active brand's non-null custom_domain is added to
    the resolved allow-list; a second active brand with custom_domain=None
    contributes nothing."""
    db_session.add(
        Brand(
            name="Acme Recruiting",
            slug="acme-recruiting",
            custom_domain="careers.acme.example.com",
            is_active=True,
        )
    )
    db_session.add(
        Brand(
            name="No Domain Brand",
            slug="no-domain-brand",
            custom_domain=None,
            is_active=True,
        )
    )
    await db_session.commit()

    settings = Settings(
        CORS_ALLOWED_ORIGINS="https://a.example.com",
        enable_brand_cors_origins=True,
    )
    origins = await resolve_cors_origins(settings, db_session)
    assert "careers.acme.example.com" in origins
    assert "https://a.example.com" in origins
    # The domain-less brand must not inject e.g. "None" or an empty string.
    assert None not in origins
    assert "" not in origins


@pytest.mark.asyncio
async def test_resolve_cors_origins_excludes_inactive_brand_custom_domain(db_session) -> None:
    """An inactive brand's custom_domain is excluded even though it is
    non-null -- only active brands' domains may accept credentialed CORS
    requests."""
    db_session.add(
        Brand(
            name="Retired Brand",
            slug="retired-brand",
            custom_domain="careers.retired.example.com",
            is_active=False,
        )
    )
    await db_session.commit()

    settings = Settings(
        CORS_ALLOWED_ORIGINS="https://a.example.com",
        enable_brand_cors_origins=True,
    )
    origins = await resolve_cors_origins(settings, db_session)
    assert "careers.retired.example.com" not in origins
    assert "https://a.example.com" in origins
