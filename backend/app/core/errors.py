"""Application error types for uniform API error envelopes."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base error mapped to ErrorResponse by the central exception handler."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        details: Any | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        self.meta = meta


class UnauthorizedError(AppError):
    def __init__(
        self,
        message: str = "unauthorized",
        *,
        details: Any | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        super().__init__("UNAUTHORIZED", message, 401, details, meta)


class ForbiddenError(AppError):
    def __init__(
        self,
        message: str = "forbidden",
        *,
        details: Any | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        super().__init__("FORBIDDEN", message, 403, details, meta)


class NotFoundError(AppError):
    def __init__(
        self,
        message: str = "not found",
        *,
        details: Any | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        super().__init__("NOT_FOUND", message, 404, details, meta)


class ConflictError(AppError):
    def __init__(
        self,
        message: str = "conflict",
        *,
        details: Any | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        super().__init__("CONFLICT", message, 409, details, meta)


class ValidationAppError(AppError):
    def __init__(
        self,
        message: str = "validation error",
        *,
        details: Any | None = None,
        meta: dict[str, Any] | None = None,
        status_code: int = 400,
    ) -> None:
        super().__init__("VALIDATION_ERROR", message, status_code, details, meta)


class RateLimitError(AppError):
    def __init__(
        self,
        message: str = "rate limit exceeded",
        *,
        details: Any | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        super().__init__("RATE_LIMIT_EXCEEDED", message, 429, details, meta)


class ServiceUnavailableError(AppError):
    def __init__(
        self,
        message: str = "service unavailable",
        *,
        details: Any | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        super().__init__("SERVICE_UNAVAILABLE", message, 503, details, meta)


class InternalError(AppError):
    def __init__(
        self,
        message: str = "An unexpected error occurred.",
        *,
        details: Any | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        super().__init__("INTERNAL_ERROR", message, 500, details, meta)
