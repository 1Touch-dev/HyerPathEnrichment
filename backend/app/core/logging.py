"""Shared structured logging for API and RQ workers.

Uses stdlib ``logging`` only (no structlog). JSON in staging/production by
default; human-readable text locally. Compatible with Sentry
``LoggingIntegration`` when ``configure_logging`` runs *before*
``init_error_tracking``.
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.config import Settings, get_settings

_JSON_ENVS = frozenset({"staging", "production"})

_request_id_ctx: ContextVar[str | None] = ContextVar("log_request_id", default=None)
_job_id_ctx: ContextVar[str | None] = ContextVar("log_job_id", default=None)

_configured = False


def get_request_id() -> str | None:
    return _request_id_ctx.get()


def get_job_id() -> str | None:
    return _job_id_ctx.get()


def set_request_id(request_id: str | None) -> None:
    _request_id_ctx.set(request_id)


def set_job_id(job_id: str | None) -> None:
    _job_id_ctx.set(job_id)


def resolve_log_format(settings: Settings | None = None) -> str:
    """Return ``json`` or ``text``.

    Explicit ``LOG_FORMAT`` wins; otherwise ``json`` when ``APP_ENV`` is
    staging/production, else ``text``.
    """
    cfg = settings if settings is not None else get_settings()
    explicit = cfg.log_format.strip().lower()
    if explicit in ("json", "text"):
        return explicit
    if cfg.app_env.strip().lower() in _JSON_ENVS:
        return "json"
    return "text"


def _correlation_fields(record: logging.LogRecord) -> dict[str, str]:
    fields: dict[str, str] = {}
    request_id = getattr(record, "request_id", None) or get_request_id()
    job_id = getattr(record, "job_id", None) or get_job_id()
    if request_id:
        fields["request_id"] = str(request_id)
    if job_id:
        fields["job_id"] = str(job_id)
    return fields


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per line with stable required keys."""

    def __init__(self, *, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service,
        }
        payload.update(_correlation_fields(record))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """Human-readable local format with optional correlation suffixes."""

    def __init__(self, *, service: str) -> None:
        super().__init__(
            fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras = _correlation_fields(record)
        parts = [f"service={self.service}"]
        if "request_id" in extras:
            parts.append(f"request_id={extras['request_id']}")
        if "job_id" in extras:
            parts.append(f"job_id={extras['job_id']}")
        return f"{base} ({' '.join(parts)})"


def configure_logging(
    settings: Settings | None = None,
    *,
    force: bool = False,
) -> str:
    """Configure the root logger once. Returns the resolved format (``json``|``text``).

    Safe to call repeatedly; subsequent calls are no-ops unless ``force=True``.
    Call before Sentry ``LoggingIntegration`` so the SDK can attach its handler.
    """
    global _configured
    if _configured and not force:
        cfg = settings if settings is not None else get_settings()
        return resolve_log_format(cfg)

    cfg = settings if settings is not None else get_settings()
    fmt = resolve_log_format(cfg)
    level_name = cfg.log_level.strip().upper() or "INFO"
    level = getattr(logging, level_name, logging.INFO)
    service = cfg.log_service.strip() or "hyrepath-enrichment"

    handler = logging.StreamHandler(sys.stdout)
    if fmt == "json":
        handler.setFormatter(JsonFormatter(service=service))
    else:
        handler.setFormatter(TextFormatter(service=service))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Keep noisy libraries quieter unless explicitly debugging.
    if level > logging.DEBUG:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)

    _configured = True
    return fmt


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind ``request_id`` (from ``X-Request-ID`` or a new UUID) for the request."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        incoming = request.headers.get("x-request-id", "").strip()
        request_id = incoming or str(uuid.uuid4())
        token = _request_id_ctx.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            _request_id_ctx.reset(token)
