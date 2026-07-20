"""Shared success/error response envelopes for the HTTP API."""

from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class SuccessResponse(BaseModel, Generic[T]):
    success: Literal[True] = True
    data: T
    message: str | None = None
    meta: dict[str, Any] | None = None


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any | None = None
    status_code: int


class ErrorResponse(BaseModel):
    success: Literal[False] = False
    error: ErrorBody
    meta: dict[str, Any] | None = None


def success_envelope(
    data: Any,
    *,
    message: str | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return SuccessResponse(data=data, message=message, meta=meta).model_dump()


def error_envelope(
    *,
    code: str,
    message: str,
    status_code: int,
    details: Any | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            details=details,
            status_code=status_code,
        ),
        meta=meta,
    ).model_dump()
