"""Central exception handlers that emit ErrorResponse envelopes."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.responses import Response

from app.core.errors import AppError
from app.core.responses import error_envelope

logger = logging.getLogger(__name__)


def _http_exception_code(status_code: int) -> str:
    mapping = {
        400: "VALIDATION_ERROR",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMIT_EXCEEDED",
        503: "SERVICE_UNAVAILABLE",
    }
    return mapping.get(status_code, "INTERNAL_ERROR" if status_code >= 500 else "VALIDATION_ERROR")


def _detail_message(detail: Any) -> str:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        parts = []
        for item in detail:
            if isinstance(item, dict) and item.get("msg"):
                parts.append(str(item["msg"]))
            else:
                parts.append(str(item))
        return ", ".join(parts) if parts else "request failed"
    return str(detail) if detail is not None else "request failed"


def _jsonable_details(details: Any) -> Any:
    return jsonable_encoder(details, custom_encoder={Exception: str})


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> Response:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_envelope(
                code=exc.code,
                message=exc.message,
                status_code=exc.status_code,
                details=_jsonable_details(exc.details) if exc.details is not None else None,
                meta=exc.meta,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_request: Request, exc: RequestValidationError) -> Response:
        return JSONResponse(
            status_code=422,
            content=error_envelope(
                code="VALIDATION_ERROR",
                message="validation error",
                status_code=422,
                details=_jsonable_details(exc.errors()),
                meta=None,
            ),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> Response:
        message = _detail_message(exc.detail)
        status_code = exc.status_code
        return JSONResponse(
            status_code=status_code,
            content=error_envelope(
                code=_http_exception_code(status_code),
                message=message,
                status_code=status_code,
                details=_jsonable_details(exc.detail) if not isinstance(exc.detail, str) else None,
                meta=None,
            ),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception) -> Response:
        logger.exception("Unhandled exception: %s", type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content=error_envelope(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred.",
                status_code=500,
                details=None,
                meta=None,
            ),
        )
