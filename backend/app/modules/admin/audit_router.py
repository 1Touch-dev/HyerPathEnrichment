"""Audit log listing endpoint (§8.15). Manually maps ORM rows to response
schema (matching service.py's `_user_to_response` convention) since
`AdminAuditLogEntryResponse` has no `from_attributes` config to touch."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.admin import repository
from app.modules.admin.models import AdminAuditLog
from app.modules.admin.permissions import require_permission
from app.modules.admin.schemas import AdminAuditLogEntryResponse, AdminAuditLogListResponse

router = APIRouter(prefix="/api/admin/audit-logs", tags=["admin"], route_class=EnvelopeAPIRoute)


def _to_response(log: AdminAuditLog) -> AdminAuditLogEntryResponse:
    return AdminAuditLogEntryResponse(
        id=log.id,
        actor_user_id=log.actor_user_id,
        impersonated_by=log.impersonated_by,
        action=log.action,
        target_type=log.target_type,
        target_id=log.target_id,
        before=log.before,
        after=log.after,
        ip_address=log.ip_address,
        captured_by=log.captured_by,
        created_at=log.created_at,
    )


@router.get("", response_model=AdminAuditLogListResponse)
async def list_audit_logs(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    action: str | None = Query(default=None),
    _user: User = Depends(require_permission("audit_logs", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminAuditLogListResponse:
    rows, next_cursor, has_more = await repository.list_audit_logs(
        db, cursor=cursor, limit=limit, action=action
    )
    return AdminAuditLogListResponse(
        items=[_to_response(row) for row in rows],
        next_cursor=next_cursor,
        has_more=has_more,
    )
