"""Shared structured logging for API and RQ workers.

Uses stdlib ``logging`` only (no structlog). JSON in staging/production by
default; human-readable text locally. Compatible with Sentry
``LoggingIntegration`` when ``configure_logging`` runs *before*
``init_error_tracking``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import sys
import traceback
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from datetime import UTC, datetime
from enum import Enum
from typing import Any, cast
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.config import Settings, get_settings

_JSON_ENVS = frozenset({"staging", "production"})
_REDACTED = "[REDACTED]"
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_UUID_TEXT_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)
_CANONICAL_PSEUDONYM_RE = re.compile(r"^redacted-[0-9a-f]{16}$")
_CANONICAL_KEY_RE = re.compile(r"^key-(?:[0-9a-f]{16}|unknown)(?:-\d+)?$")
_CANONICAL_COMPONENT_RE = re.compile(r"^(?:host|segment|value)-[0-9a-f]{16}$")
_IDENTIFIER_KEY_RE = re.compile(
    r"(?:^id$|_id$)",
    re.IGNORECASE,
)
_SENSITIVE_KEY_RE = re.compile(
    r"(?:^|_)(?:authorization|password|passwd|secret|api_key|access_token|"
    r"refresh_token|invite_token|bearer|mfa_code|mfa_secret|totp|otp|"
    r"recovery_code|verification_code|args|kwargs|payload|response|response_body|"
    r"raw_response)(?:$|_)",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])")
_LINKEDIN_RE = re.compile(
    r"https?://(?:[\w-]+\.)?linkedin\.com/[^\s\"'<>]+",
    re.IGNORECASE,
)
_BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_MFA_CODE_RE = re.compile(r"(?<!\d)\d{6,8}(?!\d)")
_CREDENTIAL_CANDIDATE_RE = re.compile(r"(?<!\S)[^\s,;{}\[\]\"']{12,}(?!\S)")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(authorization|password|passwd|secret(?:[_-]?key)?|client[_-]?secret|"
    r"private[_-]?key|api[_-]?key|token|access[_-]?token|refresh[_-]?token|"
    r"invite[_-]?token|mfa[_-]?(?:code|secret)|totp|otp)"
    r"(\s*[:=]\s*)([^\s,;}\]]+)"
)
_HTTP_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_PATH_IN_TEXT_RE = re.compile(
    r"(?<![:/\w])/(?:[A-Za-z0-9._~%-]+/)*[A-Za-z0-9._~%-]+(?:\?[^\s\"'<>]*)?"
)

_SAFE_MAPPING_KEYS = frozenset(
    {
        # Shared logging and correlation schema.
        "timestamp",
        "level",
        "logger",
        "message",
        "service",
        "exception",
        "request_id",
        "job_id",
        "action_id",
        "audit_id",
        "session_id",
        "user_id",
        "target_id",
        "trace_id",
        "span_id",
        "parent_span_id",
        "thread_id",
        "status_code",
        "action",
        "outcome",
        "result",
        "role_name",
        "email",
        "profile",
        "failed_job",
        # Sentry event, request, exception, frame, and breadcrumb schema.
        "event_id",
        "platform",
        "server_name",
        "release",
        "dist",
        "environment",
        "transaction",
        "transaction_info",
        "culprit",
        "logentry",
        "threads",
        "stacktrace",
        "request",
        "contexts",
        "breadcrumbs",
        "modules",
        "debug_meta",
        "sdk",
        "tags",
        "extra",
        "fingerprint",
        "template",
        "values",
        "value",
        "type",
        "mechanism",
        "handled",
        "synthetic",
        "data",
        "headers",
        "method",
        "url",
        "path",
        "query",
        "query_string",
        "cookies",
        "env",
        "frames",
        "filename",
        "abs_path",
        "function",
        "module",
        "lineno",
        "colno",
        "pre_context",
        "context_line",
        "post_context",
        "vars",
        "in_app",
        "category",
        "name",
        "version",
        "description",
        "integrations",
        "packages",
        "package",
        "meta",
        "inferred_content_type",
        "instruction_offset",
        "addr_mode",
        "raw_function",
        "sourcemap_error",
        "op",
        "status",
        "origin",
        "runtime",
        "os",
        "device",
        "app",
        "browser",
        "response",
        "content-type",
        "user-agent",
        "http.method",
        "http.path",
    }
)
_SAFE_PATH_SEGMENTS = frozenset(
    {
        "api",
        "admin",
        "auth",
        "staff-invites",
        "health",
        "ready",
        "metrics",
        "enrich",
        "queues",
        "failed",
        "retry",
        "impersonation",
        "start",
        "end",
        "status",
        "mfa",
        "disable",
        "enable",
        "enroll",
        "confirm",
        "users",
        "user-accounts",
        "roles",
        "permissions",
        "feature-flags",
        "review-queue",
        "documents",
        "upload",
        "outreach",
        "portfolio",
        "job-postings",
        "questions",
        "practice-audio",
        "manual-job-entries",
        "interview-schedules",
        "applications",
        "system-health",
        "costs",
        "internal",
        "error-tracking-probe",
        # Admin-specific action verbs and sub-resource paths (fallback audit).
        "moderate",
        "decide",
        "audit-logs",
        "ai-actions",
        "job-swipe",
        "analytics",
        "daily",
        "monthly",
        "total",
        "top-users",
        "breakdown",
        "job-matches",
        "recruiter",
        "brands",
        "billing",
        "webhooks",
        "stripe",
        "checkout",
        "portal",
        "public",
        "cv-chat",
        "sessions",
        "swipe",
        "practice",
        "audio",
        "signals",
        "changedetection",
        "dsar",
        "opt-out",
        "p",
        "{id}",
        "{job_id}",
        "{name}",
        "{target_user_id}",
        "{token}",
        "{user_id}",
    }
)
_PATH_VALUE_KEYS = frozenset({"path", "http.path"})
_URL_VALUE_KEYS = frozenset({"url", "abs_path", "filename"})
_QUERY_VALUE_KEYS = frozenset({"query", "query_string"})

_request_id_ctx: ContextVar[str | None] = ContextVar("log_request_id", default=None)
_job_id_ctx: ContextVar[str | None] = ContextVar("log_job_id", default=None)

_configured = False

# Every attribute stdlib `logging.LogRecord` sets on itself. Anything else on a
# record (i.e. what callers pass via `extra={...}`) is a custom field callers
# actually want logged. Without this, `extra=` was a complete no-op for every
# call site outside this module — `question_generator.py`'s "response":
# "<the actual OpenAI error body>", the audio/feedback tracing fields added
# for interview-practice debugging, etc. all vanished. Only the two ad-hoc
# `request_id`/`job_id` fields were ever hand-picked out below; that undocumented
# allowlist is exactly why "why is my extra= data missing from the log line"
# kept coming up.
_STANDARD_LOG_RECORD_ATTRS = frozenset(
    logging.LogRecord(
        name="", level=0, pathname="", lineno=0, msg="", args=(), exc_info=None
    ).__dict__
) | {"message", "asctime", "taskName"}


def _looks_like_bare_credential(value: str) -> bool:
    if len(value) < 12:
        return False
    classes = sum(
        (
            any(char.islower() for char in value),
            any(char.isupper() for char in value),
            any(char.isdigit() for char in value),
            any(not char.isalnum() for char in value),
        )
    )
    return classes >= 2


def _identifier_is_sensitive(value: str) -> bool:
    if (
        _EMAIL_RE.search(value)
        or _LINKEDIN_RE.search(value)
        or _BEARER_RE.search(value)
        or _SECRET_ASSIGNMENT_RE.search(value)
        or _MFA_CODE_RE.fullmatch(value)
    ):
        return True
    lowered = value.casefold()
    if any(marker in lowered for marker in ("token", "password", "passwd", "secret")):
        return True
    classes = sum(
        (
            any(char.islower() for char in value),
            any(char.isupper() for char in value),
            any(char.isdigit() for char in value),
            any(not char.isalnum() for char in value),
        )
    )
    return (len(value) >= 12 and classes == 4) or (len(value) >= 24 and classes >= 3)


def scrub_identifier(value: Any) -> str:
    """Retain ordinary IDs; pseudonymize credential/PII-shaped or unknown IDs."""
    if isinstance(value, UUID):
        return str(value)
    if not isinstance(value, str):
        return _REDACTED
    if _CANONICAL_PSEUDONYM_RE.fullmatch(value):
        return value
    if _UUID_TEXT_RE.fullmatch(value):
        return value
    if not _identifier_is_sensitive(value):
        return value
    return _pseudonym(value, prefix="redacted")


def _pseudonym(value: str, *, prefix: str) -> str:
    secret = get_settings().SECRET_KEY.encode("utf-8")
    digest = hmac.new(secret, value.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
    return f"{prefix}-{digest}"


def sanitize_query_string(value: str) -> str:
    """Preserve query shape while pseudonymizing every key and value.

    Total function: any parse/encode error returns a deterministic fallback.
    """
    try:
        pairs = parse_qsl(value.removeprefix("?"), keep_blank_values=True)
        sanitized = [
            (
                _scrub_mapping_key(key),
                (
                    item_value
                    if _CANONICAL_COMPONENT_RE.fullmatch(item_value)
                    else _pseudonym(item_value, prefix="value")
                ),
            )
            for key, item_value in pairs
        ]
        return urlencode(sanitized)
    except Exception:
        return "[malformed-query]"


def sanitize_path(value: str) -> str:
    """Preserve explicitly known route segments and pseudonymize all others.

    Total function: any unexpected parse/encode error returns ``[malformed-path]``.
    """
    try:
        path, separator, query = value.partition("?")
        sanitized_segments = []
        for segment in path.split("/"):
            if not segment:
                sanitized_segments.append("")
                continue
            decoded = segment.casefold()
            sanitized_segments.append(
                segment
                if decoded in _SAFE_PATH_SEGMENTS or _CANONICAL_COMPONENT_RE.fullmatch(segment)
                else _pseudonym(segment, prefix="segment")
            )
        sanitized_path = "/".join(sanitized_segments)
        if separator:
            return f"{sanitized_path}?{sanitize_query_string(query)}"
        return sanitized_path
    except Exception:
        return "[malformed-path]"


def sanitize_url(value: str) -> str:
    """Sanitize URL hosts, path segments, and all query values structurally.

    Total function: any malformed input (bad port, truncated IPv6 bracket,
    empty scheme, oversized value) returns ``[malformed-url]`` instead of
    raising, so attacker-controlled values can never break logging formatters
    or Sentry hooks.
    """
    try:
        parsed = urlsplit(value)
        if not parsed.scheme or not parsed.netloc:
            return sanitize_path(value)
        hostname = parsed.hostname or ""
        safe_host = (
            hostname
            if hostname in {"localhost", "testserver", "127.0.0.1"}
            or _CANONICAL_COMPONENT_RE.fullmatch(hostname)
            else _pseudonym(hostname, prefix="host")
        )
        try:
            port = parsed.port
        except ValueError:
            port = None
        if port is not None:
            safe_host = f"{safe_host}:{port}"
        return urlunsplit(
            (
                parsed.scheme if parsed.scheme in {"http", "https"} else "https",
                safe_host,
                sanitize_path(parsed.path),
                sanitize_query_string(parsed.query),
                "",
            )
        )
    except Exception:
        return "[malformed-url]"


def _scrub_text(value: str) -> str:
    value = _EMAIL_RE.sub(_REDACTED, value)
    value = _HTTP_URL_RE.sub(lambda match: sanitize_url(match.group(0)), value)
    value = _PATH_IN_TEXT_RE.sub(lambda match: sanitize_path(match.group(0)), value)
    value = _BEARER_RE.sub(f"Bearer {_REDACTED}", value)
    value = _SECRET_ASSIGNMENT_RE.sub(
        lambda match: f"{match.group(1)}{match.group(2)}{_REDACTED}",
        value,
    )
    value = _MFA_CODE_RE.sub(_REDACTED, value)
    return _CREDENTIAL_CANDIDATE_RE.sub(
        lambda match: (
            match.group(0)
            if match.group(0).startswith("/") and sanitize_path(match.group(0)) == match.group(0)
            else (_REDACTED if _looks_like_bare_credential(match.group(0)) else match.group(0))
        ),
        value,
    )


def scrub_sensitive_data(value: Any, *, key: str | None = None) -> Any:
    """Recursively replace common credentials and identifiers with a marker.

    Correlation identifiers such as ``request_id``, ``job_id``, and action
    names are deliberately not treated as secrets.
    """
    if key is not None and _SENSITIVE_KEY_RE.search(key):
        return _REDACTED
    if key is not None and _IDENTIFIER_KEY_RE.search(key):
        return scrub_identifier(value)
    if key in _PATH_VALUE_KEYS and isinstance(value, str):
        return sanitize_path(value)
    if key in _URL_VALUE_KEYS and isinstance(value, str):
        return sanitize_url(value)
    if key in _QUERY_VALUE_KEYS and isinstance(value, str):
        return sanitize_query_string(value)
    if value is None or type(value) in (bool, int, float):
        return value
    if isinstance(value, str):
        return _scrub_text(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return scrub_sensitive_data(value.value, key=key)
    if type(value) is dict:
        scrubbed: dict[str, Any] = {}
        for item_key, item_value in value.items():
            original_key = item_key if isinstance(item_key, str) else None
            safe_key = _scrub_mapping_key(original_key)
            candidate = safe_key
            suffix = 2
            while candidate in scrubbed:
                candidate = f"{safe_key}-{suffix}"
                suffix += 1
            scrubbed[candidate] = scrub_sensitive_data(
                item_value,
                key=original_key,
            )
        return scrubbed
    if type(value) is list:
        return [scrub_sensitive_data(item) for item in value]
    if type(value) is tuple:
        return tuple(scrub_sensitive_data(item) for item in value)
    if type(value) is set:
        return [scrub_sensitive_data(item) for item in value]
    return _REDACTED


def _scrub_mapping_key(key: str | None) -> str:
    if key is None:
        return "key-unknown"
    if key in _SAFE_MAPPING_KEYS or _CANONICAL_KEY_RE.fullmatch(key):
        return key
    return _pseudonym(key, prefix="key")


def _scrub_log_argument(value: Any) -> Any:
    if value is None or type(value) in (bool, int, float):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, str) and _REQUEST_ID_RE.fullmatch(value):
        return scrub_identifier(value)
    return _REDACTED


def _safe_log_message(record: logging.LogRecord) -> str:
    message = scrub_sensitive_data(record.msg)
    if not isinstance(message, str):
        return _REDACTED
    if not record.args:
        return message
    arguments: dict[str, Any] | tuple[Any, ...]
    if type(record.args) is dict:
        arguments = {
            key if isinstance(key, str) else "unknown": _scrub_log_argument(value)
            for key, value in record.args.items()
        }
    elif type(record.args) is tuple:
        arguments = tuple(_scrub_log_argument(value) for value in record.args)
    else:
        arguments = (_REDACTED,)
    try:
        return message % arguments
    except (KeyError, TypeError, ValueError):
        return message


def _safe_exception_text(
    exc_info: (tuple[type[BaseException], BaseException, Any] | tuple[None, None, None]),
) -> str:
    exc_type, _exc, tb = exc_info
    if exc_type is None:
        return ""
    lines = ["Traceback (most recent call last):"]
    for frame in traceback.extract_tb(tb):
        lines.append(f'  File "{frame.filename}", line {frame.lineno}, in {frame.name}')
    lines.append(f"{exc_type.__name__}: {_REDACTED}")
    return "\n".join(lines)


def is_valid_request_id(value: str | None) -> bool:
    return bool(value and _REQUEST_ID_RE.fullmatch(value))


def generate_request_id(*, non_request: bool = False) -> str:
    prefix = "system-" if non_request else ""
    return f"{prefix}{uuid.uuid4()}"


def _extra_fields(record: logging.LogRecord) -> dict[str, Any]:
    """Return whatever a caller passed via ``extra={...}``, correlation
    fields excluded (those are handled separately by ``_correlation_fields``).
    """
    fields = {
        key: value
        for key, value in record.__dict__.items()
        if key not in _STANDARD_LOG_RECORD_ATTRS and key not in ("request_id", "job_id")
    }
    return cast(dict[str, Any], scrub_sensitive_data(fields))


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
        fields["request_id"] = (
            scrub_identifier(request_id)
            if isinstance(request_id, str) and is_valid_request_id(request_id)
            else generate_request_id()
        )
    if job_id:
        fields["job_id"] = scrub_identifier(job_id)
    return fields


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per line with stable required keys."""

    def __init__(self, *, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": _safe_log_message(record),
            "service": self.service,
        }
        payload.update(_correlation_fields(record))
        payload.update(_extra_fields(record))
        if record.exc_info:
            payload["exception"] = _safe_exception_text(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Human-readable local format with optional correlation suffixes."""

    def __init__(self, *, service: str) -> None:
        super().__init__(
            fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        original_msg, original_args = record.msg, record.args
        original_exc_info, original_exc_text = record.exc_info, record.exc_text
        try:
            record.msg = _safe_log_message(record)
            record.args = ()
            record.exc_info = None
            record.exc_text = None
            base = super().format(record)
        finally:
            record.msg, record.args, record.exc_info, record.exc_text = (
                original_msg,
                original_args,
                original_exc_info,
                original_exc_text,
            )
        if original_exc_info:
            base = f"{base}\n{_safe_exception_text(original_exc_info)}"
        extras = _correlation_fields(record)
        parts = [f"service={self.service}"]
        if "request_id" in extras:
            parts.append(f"request_id={extras['request_id']}")
        if "job_id" in extras:
            parts.append(f"job_id={extras['job_id']}")
        suffix = f"({' '.join(parts)})"

        custom_fields = _extra_fields(record)
        if not custom_fields:
            return f"{base} {suffix}"

        # Multi-line JSON blob (e.g. a full OpenAI error body, or interview
        # feedback's question/answer/raw-LLM-response tracing) is unreadable
        # crammed onto the base line — indent it on its own line instead.
        extras_json = json.dumps(custom_fields, ensure_ascii=False, indent=2)
        return f"{base} {suffix}\n  extra: {extras_json}"


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

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get("x-request-id", "").strip()
        request_id = (
            scrub_identifier(incoming) if is_valid_request_id(incoming) else generate_request_id()
        )
        request.state.request_id = request_id
        token = _request_id_ctx.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            _request_id_ctx.reset(token)
