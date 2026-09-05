"""Admin moderation endpoints for manually-added job entries (Admin Module —
Module 4 admin visibility/moderation surface, migration 046). Soft-delete/
restore toggle on `ManualJobEntry.deleted_at`, mirroring
`documents_router.py`'s `moderate_document` implementation for
`CandidateDocument.deleted_at`."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
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
from app.modules.manual_jobs.models import ManualJobEntry

router = APIRouter(
    prefix="/api/admin/manual-job-entries", tags=["admin"], route_class=EnvelopeAPIRoute
)


class AdminManualJobEntryResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    company: str
    location: str | None
    source_label: str | None
    source_url: str | None
    notes: str | None
    created_at: datetime
    deleted_at: datetime | None


class AdminManualJobEntryListResponse(BaseModel):
    items: list[AdminManualJobEntryResponse]
    next_cursor: str | None
    has_more: bool


class ModerateManualJobEntryRequest(BaseModel):
    action: Literal["soft_delete", "restore"]
    reason: str | None = Field(default=None, max_length=500)


def _to_response(entry: ManualJobEntry) -> AdminManualJobEntryResponse:
    return AdminManualJobEntryResponse(
        id=entry.id,
        user_id=entry.user_id,
        title=entry.title,
        company=entry.company,
        location=entry.location,
        source_label=entry.source_label,
        source_url=entry.source_url,
        notes=entry.notes,
        created_at=entry.created_at,
        deleted_at=entry.deleted_at,
    )


async def _get_entry_or_404(db: AsyncSession, entry_id: UUID) -> ManualJobEntry:
    result = await db.execute(select(ManualJobEntry).where(ManualJobEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Manual job entry not found"
        )
    return entry


@router.get("", response_model=AdminManualJobEntryListResponse)
async def list_manual_job_entries(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    deleted: bool | None = Query(default=None),
    _user: User = Depends(require_permission("manual_job_entries", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminManualJobEntryListResponse:
    query = select(ManualJobEntry).order_by(
        ManualJobEntry.created_at.desc(), ManualJobEntry.id.desc()
    )
    if deleted is not None:
        if deleted:
            query = query.where(ManualJobEntry.deleted_at.is_not(None))
        else:
            query = query.where(ManualJobEntry.deleted_at.is_(None))
    if cursor:
        created_at, entity_id = decode_cursor(cursor)
        query = query.where(
            (ManualJobEntry.created_at < created_at)
            | ((ManualJobEntry.created_at == created_at) & (ManualJobEntry.id < UUID(entity_id)))
        )
    query = query.limit(limit + 1)

    rows = list((await db.execute(query)).scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None

    return AdminManualJobEntryListResponse(
        items=[_to_response(r) for r in rows],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get("/{entry_id}", response_model=AdminManualJobEntryResponse)
async def get_manual_job_entry(
    entry_id: UUID,
    _user: User = Depends(require_permission("manual_job_entries", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminManualJobEntryResponse:
    entry = await _get_entry_or_404(db, entry_id)
    return _to_response(entry)


@router.post(
    "/{entry_id}/moderate",
    response_model=AdminManualJobEntryResponse,
    dependencies=[Depends(enforce_admin_moderation_rate_limit)],
)
async def moderate_manual_job_entry(
    entry_id: UUID,
    payload: ModerateManualJobEntryRequest,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    current_user: User = Depends(require_permission("manual_job_entries", "moderate")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminManualJobEntryResponse:
    normalized_key = require_idempotency_key("manual_job_entries.moderate", idempotency_key)
    state, replay = await begin_idempotent_operation(
        db,
        caller_user_id=current_user.id,
        operation_id="manual_job_entries.moderate",
        idempotency_key=normalized_key,
        request_hash=canonical_payload_hash(
            {"entry_id": entry_id, "action": payload.action, "reason": payload.reason}
        ),
    )
    if replay is not None:
        return AdminManualJobEntryResponse.model_validate(replay.response_body["entry"])

    entry = await _get_entry_or_404(db, entry_id)

    before = {"deleted_at": entry.deleted_at.isoformat() if entry.deleted_at else None}
    if payload.action == "soft_delete":
        entry.deleted_at = datetime.now(UTC)
    else:
        entry.deleted_at = None
    await db.flush()
    after = {
        "deleted_at": entry.deleted_at.isoformat() if entry.deleted_at else None,
        "reason": payload.reason,
    }

    await record_admin_action(
        db,
        actor_user_id=current_user.id,
        action="manual_job_entries.moderate",
        target_type="manual_job_entry",
        target_id=str(entry_id),
        before=before,
        after=after,
        ip_address=get_client_ip(request),
    )
    response = _to_response(entry)
    if state is not None:
        await complete_idempotent_operation(
            db,
            state,
            response_status=200,
            response_body={"entry": response.model_dump(mode="json")},
        )
    await db.commit()
    return response
