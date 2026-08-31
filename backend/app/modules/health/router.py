from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import text

try:
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
except ImportError:  # pragma: no cover - optional runtime dependency fallback
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

    def _generate_latest_noop(*_args: Any, **_kwargs: Any) -> bytes:
        return b""

    generate_latest = _generate_latest_noop

from app.core.api_route import EnvelopeAPIRoute
from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError, ServiceUnavailableError, UnauthorizedError
from app.core.responses import success_envelope
from app.database.session import SessionLocal, database_schema_at_head
from app.domain.enrichment import HealthResponse
from app.infrastructure.redis import get_redis_client
from app.observability.error_tracking import capture_exception, flush_error_tracking

router = APIRouter(tags=["health"], route_class=EnvelopeAPIRoute)

_PROD_LIKE = frozenset({"production", "staging"})


def _metrics_expected_token(settings: Settings) -> str:
    """Prefer dedicated scrape token; fall back to API_TOKEN."""
    dedicated = settings.metrics_token.strip()
    return dedicated or settings.api_token.strip()


def _extract_bearer_or_api_token(authorization: str | None, x_api_token: str | None) -> str:
    if x_api_token and x_api_token.strip():
        return x_api_token.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", service=settings.app_name)


@router.get("/ready", response_model=HealthResponse)
async def ready() -> HealthResponse:
    settings = get_settings()
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
            if not await database_schema_at_head(session):
                raise RuntimeError("schema not at alembic head")
        await get_redis_client().ping()
    except Exception as exc:
        raise ServiceUnavailableError(
            f"not ready: {type(exc).__name__}",
            meta={"reason": type(exc).__name__},
        ) from exc
    return HealthResponse(status="ready", service=settings.app_name)


@router.get("/metrics")
async def metrics(
    request: Request,
    settings: Settings = Depends(get_settings),
    authorization: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
) -> PlainTextResponse:
    """Prometheus scrape endpoint.

    Open in development when no ``METRICS_TOKEN`` is set. Staging/production
    (or any env with ``METRICS_TOKEN`` set) require Bearer / ``X-API-Token``.
    """
    env = settings.app_env.strip().lower()
    require_auth = env in _PROD_LIKE or bool(settings.metrics_token.strip())
    if require_auth:
        expected = _metrics_expected_token(settings)
        provided = _extract_bearer_or_api_token(authorization, x_api_token)
        if not expected or not provided or not hmac.compare_digest(provided, expected):
            raise UnauthorizedError("metrics scrape token required")
    _ = request  # reserved for future scrape IP allowlists
    return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)


@router.post("/internal/error-tracking-probe")
async def error_tracking_probe(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    """E2E-only probe: capture a known exception when explicitly enabled."""
    if not settings.enable_error_tracking_probe:
        raise NotFoundError("not found")
    exc = RuntimeError("e2e error tracking probe")
    capture_exception(exc, tags={"probe": "e2e"})
    flush_error_tracking()
    return success_envelope({"status": "captured"})
