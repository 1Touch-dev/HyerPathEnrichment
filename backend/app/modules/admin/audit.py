"""Admin audit log writer + ASGI fallback middleware. See Decision 2 for why
this is router-adjacent explicit calls plus a fallback, not a literal port of
the case study's Express `req.audit()` middleware."""

from __future__ import annotations

import contextvars
import logging
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import (
    generate_request_id,
    get_request_id,
    is_valid_request_id,
    sanitize_path,
    scrub_identifier,
    scrub_sensitive_data,
)
from app.modules.admin.models import AdminAuditLog
from app.observability.security_metrics import record_audit

logger = logging.getLogger(__name__)


@dataclass
class _AuditCaptureState:
    captured: bool = False


_audit_capture_state: contextvars.ContextVar[_AuditCaptureState | None] = contextvars.ContextVar(
    "admin_audit_capture_state", default=None
)

# Matches a dashed or undashed UUID (or any other 32-36 char hex/dash
# dynamic-ID segment) so path-based fallback actions group by route shape
# (e.g. "/api/admin/users/{id}/status") instead of embedding the literal ID.
_DYNAMIC_ID_SEGMENT_RE = re.compile(r"/[0-9a-fA-F-]{32,36}(?=/|$)")

# AdminAuditLog.action is sa.String(64) (see
# backend/alembic/versions/035_admin_audit_logs.py). A plain
# f"{method}_{path}" for a mutation route with a raw UUID segment (e.g.
# "patch_/api/admin/users/<uuid>/status") is well over 64 chars — invisible
# on SQLite's untyped TEXT column, but raises StringDataRightTruncationError
# on real Postgres *after* the real business logic already committed.
_ACTION_MAX_LENGTH = 64
_PENDING_EXPLICIT_AUDITS_KEY = "pending_explicit_audit_metric_ids"


def _finish_explicit_audit_metrics(session: Session, outcome: str) -> None:
    pending = session.info.pop(_PENDING_EXPLICIT_AUDITS_KEY, set())
    if pending:
        record_audit("explicit", outcome, count=len(pending))


@event.listens_for(Session, "after_commit")
def _record_committed_explicit_audits(session: Session) -> None:
    if not session.in_nested_transaction():
        _finish_explicit_audit_metrics(session, "success")


@event.listens_for(Session, "after_rollback")
def _record_rolled_back_explicit_audits(session: Session) -> None:
    if not session.in_nested_transaction():
        _finish_explicit_audit_metrics(session, "failure")


def _build_fallback_action(method: str, path: str) -> str:
    """Build the fallback audit ``action`` string.

    Process order (before applying the 64-char column cap):
    1. Replace genuinely dynamic path segments (32-36 hex/dash IDs) with
       ``{id}`` so the route shape is preserved without embedding literal IDs.
    2. Pass the normalized path through ``sanitize_path`` to pseudonymize any
       remaining dynamic segment that is NOT a known static route word.
    3. Construct the full ``method_path`` string from the sanitized result.
    4. If the result exceeds the column limit, trim from the LEFT (left
       ellipsis) so the identifying SUFFIX (e.g. ``/moderate``, ``/decide``,
       ``/retry``) is always preserved rather than the high-cardinality prefix.

    Static route action words (``moderate``, ``decide``, ``feature-flags``,
    ``retry``, etc.) are in ``_SAFE_PATH_SEGMENTS`` in ``core/logging.py`` and
    will NOT be pseudonymized by ``sanitize_path``.
    """
    normalized_path = sanitize_path(_DYNAMIC_ID_SEGMENT_RE.sub("/{id}", path))
    action = f"{method.lower()}_{normalized_path}"
    if len(action) <= _ACTION_MAX_LENGTH:
        return action
    # Trim from the left to preserve the identifying suffix.
    return action[-_ACTION_MAX_LENGTH:]


async def record_admin_action(
    db: AsyncSession,
    *,
    actor_user_id: UUID | None,
    action: str,
    target_type: str,
    target_id: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    ip_address: str | None = None,
    impersonated_by: UUID | None = None,
    impersonation_session_id: UUID | None = None,
    request_id: str | None = None,
    outcome: str = "success",
) -> AdminAuditLog:
    """Call this explicitly at the point in a router/service where actor/target/
    before/after are all known. Marks the request as already-audited so the
    fallback middleware does not double-log it."""
    capture_state = _audit_capture_state.get()
    resolved_request_id = request_id or get_request_id()
    if resolved_request_id is None:
        if capture_state is not None:
            raise RuntimeError("Request context unavailable for explicit admin audit")
        resolved_request_id = generate_request_id(non_request=True)
    elif not is_valid_request_id(resolved_request_id):
        resolved_request_id = generate_request_id()
    else:
        resolved_request_id = scrub_identifier(resolved_request_id)

    record = AdminAuditLog(
        id=uuid4(),
        actor_user_id=actor_user_id,
        impersonated_by=impersonated_by,
        action=action,
        target_type=target_type,
        target_id=target_id,
        before=scrub_sensitive_data(before),
        after=scrub_sensitive_data(after),
        ip_address=ip_address,
        captured_by="explicit",
        request_id=resolved_request_id,
        outcome=outcome,
        impersonation_session_id=impersonation_session_id,
    )
    db.add(record)
    try:
        await db.flush()
    except Exception:
        record_audit("explicit", "failure")
        raise
    pending = db.sync_session.info.setdefault(_PENDING_EXPLICIT_AUDITS_KEY, set())
    pending.add(record.id)
    if capture_state is not None:
        # BaseHTTPMiddleware runs the endpoint in a child task. ContextVar
        # assignments do not propagate back, but mutating this inherited
        # request-scoped holder does.
        capture_state.captured = True
    logger.info(
        "admin audit action=%s target_type=%s",
        action,
        target_type,
    )
    return record


class AdminAuditFallbackMiddleware(BaseHTTPMiddleware):
    """Defense-in-depth: logs a generic entry for any mutating /api/admin request
    whose handler did not call `record_admin_action()`. Uses a fresh DB session
    (not the request's, which may have already been closed/committed by the
    time this runs) so a forgotten explicit call never produces total silence."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        capture_state = _AuditCaptureState()
        token = _audit_capture_state.set(capture_state)
        try:
            response = await call_next(request)
        finally:
            _audit_capture_state.reset(token)

        is_privileged_mutation = (
            request.url.path.startswith("/api/admin") or request.url.path == "/api/staff-invites"
        ) and request.method in {
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
        }
        if is_privileged_mutation and not capture_state.captured and response.status_code < 500:
            await self._log_fallback(request, response)
        return response

    @staticmethod
    async def _log_fallback(request: Request, response: Response) -> None:
        from app.database.session import get_db_session_context

        actor_id = getattr(request.state, "user_id", None)
        request_id = getattr(request.state, "request_id", None) or get_request_id()
        if not is_valid_request_id(request_id):
            request_id = generate_request_id()
        else:
            request_id = scrub_identifier(request_id)
        try:
            async with get_db_session_context() as db:
                db.add(
                    AdminAuditLog(
                        id=uuid4(),
                        actor_user_id=actor_id,
                        action=_build_fallback_action(request.method, request.url.path),
                        target_type="unclassified",
                        target_id=None,
                        before=None,
                        after={"status_code": response.status_code},
                        ip_address=request.client.host if request.client else None,
                        captured_by="fallback",
                        request_id=request_id,
                        outcome="success" if response.status_code < 400 else "denied",
                        impersonated_by=getattr(request.state, "impersonated_by", None),
                        impersonation_session_id=getattr(
                            request.state, "impersonation_session_id", None
                        ),
                    )
                )
                await db.commit()
            record_audit("fallback", "anomaly")
        except Exception:
            record_audit("fallback", "failure")
            logger.critical(
                "admin audit fallback persistence failed",
                extra={
                    "audit_capture": "fallback",
                    "audit_outcome": "failure",
                    "request_id": request_id,
                },
            )
