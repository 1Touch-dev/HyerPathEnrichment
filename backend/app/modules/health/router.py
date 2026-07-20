from typing import Any

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from sqlalchemy import text

try:
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
except ImportError:  # pragma: no cover - optional runtime dependency fallback
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

    def _generate_latest_noop(*_args: Any, **_kwargs: Any) -> bytes:
        return b""

    generate_latest = _generate_latest_noop  # type: ignore[assignment]

from app.core.api_route import EnvelopeAPIRoute
from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError
from app.database.session import SessionLocal, database_schema_at_head
from app.domain.enrichment import HealthResponse
from app.infrastructure.redis import get_redis_client

router = APIRouter(tags=["health"], route_class=EnvelopeAPIRoute)


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
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)
