"""Admin API routes for outreach message moderation (Admin Module, Phase 2).

Query/response logic lives directly in this router (not admin/repository.py
or admin/service.py) since this chunk lands alongside six sibling moderation
routers in parallel worktrees and must stay scoped to the single new file
assigned to it — see the batch's shared-file avoidance list.

`admin_blocked` is enforced in `OutreachService.send_message()`
(`app/modules/outreach/service.py`), which raises a 403 if a candidate
attempts to send a message an admin has blocked here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_client_ip
from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.dependencies.rate_limit import enforce_admin_moderation_rate_limit
from app.modules.admin.audit import record_admin_action
from app.modules.admin.pagination import decode_cursor, encode_cursor
from app.modules.admin.permissions import require_permission
from app.modules.admin.privileged_operations import (
    begin_idempotent_operation,
    canonical_payload_hash,
    complete_idempotent_operation,
    require_idempotency_key,
)
from app.modules.outreach.models import OutreachMessage

router = APIRouter(prefix="/api/admin/outreach", tags=["admin"], route_class=EnvelopeAPIRoute)


class AdminOutreachMessageResponse(BaseModel):
    id: UUID
    user_id: UUID
    job_match_id: UUID | None
    recipient_role_title: str | None
    company_name: str
    subject: str
    body: str
    status: str
    admin_blocked: bool
    sent_at: datetime | None
    created_at: datetime


class AdminOutreachMessageListResponse(BaseModel):
    items: list[AdminOutreachMessageResponse]
    next_cursor: str | None
    has_more: bool


class ModerateOutreachMessageRequest(BaseModel):
    admin_blocked: bool
    reason: str | None = Field(default=None, max_length=1000)


def _to_response(message: OutreachMessage) -> AdminOutreachMessageResponse:
    return AdminOutreachMessageResponse(
        id=message.id,
        user_id=message.user_id,
        job_match_id=message.job_match_id,
        recipient_role_title=message.recipient_role_title,
        company_name=message.company_name,
        subject=message.subject,
        body=message.body,
        status=message.status,
        admin_blocked=message.admin_blocked,
        sent_at=message.sent_at,
        created_at=message.created_at,
    )


@router.get("", response_model=AdminOutreachMessageListResponse)
async def list_outreach_messages(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    admin_blocked: bool | None = Query(default=None),
    _user: User = Depends(require_permission("outreach", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminOutreachMessageListResponse:
    query = select(OutreachMessage).order_by(
        OutreachMessage.created_at.desc(), OutreachMessage.id.desc()
    )
    if status_filter is not None:
        query = query.where(OutreachMessage.status == status_filter)
    if admin_blocked is not None:
        query = query.where(OutreachMessage.admin_blocked == admin_blocked)
    if cursor:
        created_at, entity_id = decode_cursor(cursor)
        query = query.where(
            (OutreachMessage.created_at < created_at)
            | ((OutreachMessage.created_at == created_at) & (OutreachMessage.id < UUID(entity_id)))
        )
    query = query.limit(limit + 1)

    rows = list((await db.execute(query)).scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None

    return AdminOutreachMessageListResponse(
        items=[_to_response(row) for row in rows],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get("/{message_id}", response_model=AdminOutreachMessageResponse)
async def get_outreach_message(
    message_id: UUID,
    _user: User = Depends(require_permission("outreach", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminOutreachMessageResponse:
    message = await db.get(OutreachMessage, message_id)
    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Outreach message not found"
        )
    return _to_response(message)


@router.post(
    "/{message_id}/moderate",
    response_model=AdminOutreachMessageResponse,
    dependencies=[Depends(enforce_admin_moderation_rate_limit)],
)
async def moderate_outreach_message(
    message_id: UUID,
    payload: ModerateOutreachMessageRequest,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    current_user: User = Depends(require_permission("outreach", "moderate")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminOutreachMessageResponse:
    normalized_key = require_idempotency_key("outreach.moderate", idempotency_key)
    state, replay = await begin_idempotent_operation(
        db,
        caller_user_id=current_user.id,
        operation_id="outreach.moderate",
        idempotency_key=normalized_key,
        request_hash=canonical_payload_hash(
            {
                "message_id": message_id,
                "admin_blocked": payload.admin_blocked,
                "reason": payload.reason,
            }
        ),
    )
    if replay is not None:
        return AdminOutreachMessageResponse.model_validate(replay.response_body["message"])

    message = await db.get(OutreachMessage, message_id)
    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Outreach message not found"
        )

    before = {"admin_blocked": message.admin_blocked}
    message.admin_blocked = payload.admin_blocked
    await db.flush()
    after = {"admin_blocked": message.admin_blocked, "reason": payload.reason}

    await record_admin_action(
        db,
        actor_user_id=current_user.id,
        action="outreach.moderate",
        target_type="outreach_message",
        target_id=str(message_id),
        before=before,
        after=after,
        ip_address=get_client_ip(request),
    )
    response = _to_response(message)
    if state is not None:
        await complete_idempotent_operation(
            db,
            state,
            response_status=200,
            response_body={"message": response.model_dump(mode="json")},
        )
    await db.commit()
    await db.refresh(message)
    return response
