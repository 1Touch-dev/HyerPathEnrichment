"""Admin audit log writer + ASGI fallback middleware. See Decision 2 for why
this is router-adjacent explicit calls plus a fallback, not a literal port of
the case study's Express `req.audit()` middleware."""

from __future__ import annotations

import contextvars
import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.modules.admin.models import AdminAuditLog

logger = logging.getLogger(__name__)

_audit_captured: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "admin_audit_captured", default=False
)


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
) -> AdminAuditLog:
    """Call this explicitly at the point in a router/service where actor/target/
    before/after are all known. Marks the request as already-audited so the
    fallback middleware does not double-log it."""
    record = AdminAuditLog(
        id=uuid4(),
        actor_user_id=actor_user_id,
        impersonated_by=impersonated_by,
        action=action,
        target_type=target_type,
        target_id=target_id,
        before=before,
        after=after,
        ip_address=ip_address,
        captured_by="explicit",
    )
    db.add(record)
    await db.flush()
    _audit_captured.set(True)
    logger.info(
        "admin audit action=%s target_type=%s target_id=%s actor=%s",
        action,
        target_type,
        target_id,
        str(actor_user_id)[:8] if actor_user_id else None,
    )
    return record


class AdminAuditFallbackMiddleware(BaseHTTPMiddleware):
    """Defense-in-depth: logs a generic entry for any mutating /api/admin request
    whose handler did not call `record_admin_action()`. Uses a fresh DB session
    (not the request's, which may have already been closed/committed by the
    time this runs) so a forgotten explicit call never produces total silence."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        token = _audit_captured.set(False)
        try:
            response = await call_next(request)
        finally:
            captured = _audit_captured.get()
            _audit_captured.reset(token)

        is_admin_mutation = request.url.path.startswith("/api/admin") and request.method in {
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
        }
        if is_admin_mutation and not captured and response.status_code < 500:
            await self._log_fallback(request, response)
        return response

    @staticmethod
    async def _log_fallback(request: Request, response: Response) -> None:
        from app.database.session import get_db_session_context

        actor_id = getattr(request.state, "user_id", None)
        async with get_db_session_context() as db:
            db.add(
                AdminAuditLog(
                    id=uuid4(),
                    actor_user_id=actor_id,
                    action=f"{request.method.lower()}_{request.url.path}",
                    target_type="unclassified",
                    target_id=None,
                    before=None,
                    after={"status_code": response.status_code},
                    ip_address=request.client.host if request.client else None,
                    captured_by="fallback",
                )
            )
            await db.commit()
