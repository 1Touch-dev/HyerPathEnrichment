from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import text

try:
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
except ImportError:  # pragma: no cover - optional runtime dependency fallback
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

    def generate_latest(*args: Any, **kwargs: Any) -> bytes:
        return b""

from app.config import get_settings
from app.database.session import SessionLocal, database_schema_at_head
from app.infrastructure.redis import get_redis_client
from app.models import HealthResponse

router = APIRouter(tags=["health"])


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
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"not ready: {type(exc).__name__}",
        ) from exc
    return HealthResponse(status="ready", service=settings.app_name)


@router.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)
