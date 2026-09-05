"""Admin moderation endpoints for candidate documents. Distinct mechanism from
the candidate-facing hard `delete_document()` in `app/modules/documents/router.py` —
this is an admin-only soft-delete/restore toggle on `CandidateDocument.deleted_at`,
never wired to the candidate-facing delete path. Pydantic models are defined
inline here (matching `app/modules/admin/router.py`'s pattern) rather than in
`schemas.py`, which every Batch-1 Admin Module chunk deliberately leaves untouched."""

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
from app.modules.documents.models import CandidateDocument

router = APIRouter(prefix="/api/admin/documents", tags=["admin"], route_class=EnvelopeAPIRoute)


class AdminDocumentResponse(BaseModel):
    id: UUID
    user_id: UUID
    document_type: str
    original_filename: str
    mime_type: str | None
    file_size_bytes: int
    processing_status: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class AdminDocumentListResponse(BaseModel):
    items: list[AdminDocumentResponse]
    next_cursor: str | None
    has_more: bool


class ModerateDocumentRequest(BaseModel):
    action: Literal["soft_delete", "restore"]
    reason: str | None = Field(default=None, max_length=500)


def _document_to_response(document: CandidateDocument) -> AdminDocumentResponse:
    return AdminDocumentResponse(
        id=document.id,
        user_id=document.user_id,
        document_type=document.document_type,
        original_filename=document.original_filename,
        mime_type=document.mime_type,
        file_size_bytes=document.file_size_bytes,
        processing_status=document.processing_status,
        created_at=document.created_at,
        updated_at=document.updated_at,
        deleted_at=document.deleted_at,
    )


async def _get_document_or_404(db: AsyncSession, document_id: UUID) -> CandidateDocument:
    result = await db.execute(select(CandidateDocument).where(CandidateDocument.id == document_id))
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


@router.get("", response_model=AdminDocumentListResponse)
async def list_documents(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    processing_status: str | None = Query(default=None),
    deleted: bool | None = Query(default=None),
    _user: User = Depends(require_permission("documents", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminDocumentListResponse:
    query = select(CandidateDocument).order_by(
        CandidateDocument.created_at.desc(), CandidateDocument.id.desc()
    )
    if processing_status is not None:
        query = query.where(CandidateDocument.processing_status == processing_status)
    if deleted is not None:
        if deleted:
            query = query.where(CandidateDocument.deleted_at.is_not(None))
        else:
            query = query.where(CandidateDocument.deleted_at.is_(None))
    if cursor:
        created_at, entity_id = decode_cursor(cursor)
        query = query.where(
            (CandidateDocument.created_at < created_at)
            | (
                (CandidateDocument.created_at == created_at)
                & (CandidateDocument.id < UUID(entity_id))
            )
        )
    query = query.limit(limit + 1)

    rows = list((await db.execute(query)).scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None

    return AdminDocumentListResponse(
        items=[_document_to_response(doc) for doc in rows],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get("/{document_id}", response_model=AdminDocumentResponse)
async def get_document(
    document_id: UUID,
    _user: User = Depends(require_permission("documents", "read")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminDocumentResponse:
    document = await _get_document_or_404(db, document_id)
    return _document_to_response(document)


@router.post(
    "/{document_id}/moderate",
    response_model=AdminDocumentResponse,
    dependencies=[Depends(enforce_admin_moderation_rate_limit)],
)
async def moderate_document(
    document_id: UUID,
    payload: ModerateDocumentRequest,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    current_user: User = Depends(require_permission("documents", "moderate")),
    db: AsyncSession = Depends(get_db_session),
) -> AdminDocumentResponse:
    normalized_key = require_idempotency_key("documents.moderate", idempotency_key)
    state, replay = await begin_idempotent_operation(
        db,
        caller_user_id=current_user.id,
        operation_id="documents.moderate",
        idempotency_key=normalized_key,
        request_hash=canonical_payload_hash(
            {"document_id": document_id, "action": payload.action, "reason": payload.reason}
        ),
    )
    if replay is not None:
        return AdminDocumentResponse.model_validate(replay.response_body["document"])

    document = await _get_document_or_404(db, document_id)

    before = {"deleted_at": document.deleted_at.isoformat() if document.deleted_at else None}
    if payload.action == "soft_delete":
        document.deleted_at = datetime.now(UTC)
    else:
        document.deleted_at = None
    await db.flush()
    after = {
        "deleted_at": document.deleted_at.isoformat() if document.deleted_at else None,
        "reason": payload.reason,
    }

    await record_admin_action(
        db,
        actor_user_id=current_user.id,
        action="documents.moderate",
        target_type="document",
        target_id=str(document_id),
        before=before,
        after=after,
        ip_address=get_client_ip(request),
    )
    response = _document_to_response(document)
    if state is not None:
        await complete_idempotent_operation(
            db,
            state,
            response_status=200,
            response_body={"document": response.model_dump(mode="json")},
        )
    await db.commit()
    return response
