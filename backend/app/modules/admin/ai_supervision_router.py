"""AI-agent supervision (audit/oversight) endpoints.

See task-orchestration/machine-2-parallel-tracks/04-rbac-admin-platform.md's
"AI-agent supervision (audit/oversight view)" section: "a list of what the AI
did, who/what triggered it, and a way to drill into each one" -- explicitly
not a dashboards/analytics platform.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.admin import ai_supervision_service
from app.modules.admin.ai_supervision_models import AiActionAuditLog
from app.modules.admin.ai_supervision_schemas import (
    AiActionAuditLogListResponse,
    AiActionAuditLogResponse,
)
from app.modules.admin.permissions import require_permission

router = APIRouter(prefix="/api/admin/ai-actions", tags=["admin"], route_class=EnvelopeAPIRoute)


def _to_response(row: AiActionAuditLog) -> AiActionAuditLogResponse:
    return AiActionAuditLogResponse(
        id=row.id,
        action_type=row.action_type,
        candidate_user_id=row.candidate_user_id,
        triggered_by_user_id=row.triggered_by_user_id,
        related_id=row.related_id,
        summary=row.summary,
        created_at=row.created_at,
    )


@router.get("", response_model=AiActionAuditLogListResponse)
async def list_ai_actions(
    candidate_id: UUID | None = Query(default=None),
    recruiter_id: UUID | None = Query(default=None),
    action_type: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    _user: User = Depends(require_permission("ai_supervision", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> AiActionAuditLogListResponse:
    rows, next_cursor, has_more = await ai_supervision_service.list_ai_actions(
        db,
        candidate_id=candidate_id,
        recruiter_id=recruiter_id,
        action_type=action_type,
        since=since,
        until=until,
        cursor=cursor,
        limit=limit,
    )
    return AiActionAuditLogListResponse(
        items=[_to_response(row) for row in rows],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get("/{action_id}", response_model=AiActionAuditLogResponse)
async def get_ai_action(
    action_id: UUID,
    _user: User = Depends(require_permission("ai_supervision", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> AiActionAuditLogResponse:
    row = await ai_supervision_service.get_ai_action(db, action_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI action not found")
    return _to_response(row)
