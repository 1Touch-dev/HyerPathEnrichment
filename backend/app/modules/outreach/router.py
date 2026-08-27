"""FastAPI router for outreach drafting/editing/sending."""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.dependencies.rate_limit import enforce_outreach_send_rate_limit
from app.modules.outreach.schemas import (
    CompanyTier,
    CompanyTierResponse,
    OutreachDraftRequest,
    OutreachEditRequest,
    OutreachListResponse,
    OutreachMessageResponse,
    SetCompanyTierRequest,
)
from app.modules.outreach.service import OutreachService

router = APIRouter(prefix="/api/outreach", tags=["outreach"], route_class=EnvelopeAPIRoute)


@router.post("/drafts")
async def request_draft(
    body: OutreachDraftRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return await OutreachService(db).request_draft(current_user.id, body)


@router.get("", response_model=OutreachListResponse)
async def list_messages(
    current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)
) -> OutreachListResponse:
    return await OutreachService(db).list_my_messages(current_user.id)


@router.patch("/{message_id}", response_model=OutreachMessageResponse)
async def edit_draft(
    message_id: str,
    body: OutreachEditRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> OutreachMessageResponse:
    return await OutreachService(db).edit_draft(current_user.id, message_id, body)


@router.post(
    "/{message_id}/send",
    response_model=OutreachMessageResponse,
    dependencies=[Depends(enforce_outreach_send_rate_limit)],
)
async def send_message(
    message_id: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)
) -> OutreachMessageResponse:
    """Appends the mandatory disclosure footer (Decision 5) and marks the draft as sent."""
    return await OutreachService(db).send_message(
        current_user.id,
        message_id,
        sender_email=current_user.email,
        sender_name=current_user.email.split("@")[0],
    )


@router.put("/company-tier", response_model=CompanyTierResponse)
async def set_company_tier(
    body: SetCompanyTierRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> CompanyTierResponse:
    """Manual, human-set employer tier classification (machine-2/03) — upserts by
    company_name; no permission beyond the existing gate protecting the other
    outreach endpoints in this router is required.

    ``update_notes`` is derived from Pydantic's native ``model_fields_set``
    rather than an ``is None`` check on ``body.notes`` — the latter can't tell
    "the client didn't send `notes` at all" apart from "the client explicitly
    sent `notes: null`", and the former (omitted) must never clear an existing
    note while the latter (explicit null) must."""
    row = await OutreachService(db).set_company_tier(
        company_name=body.company_name,
        tier=body.tier,
        set_by_user_id=current_user.id,
        notes=body.notes,
        update_notes="notes" in body.model_fields_set,
    )
    return CompanyTierResponse(
        company_name=row.company_name,
        tier=cast(CompanyTier, row.tier),
        notes=row.notes,
        updated_at=row.updated_at,
    )


@router.get("/company-tier", response_model=CompanyTierResponse | None)
async def get_company_tier(
    company_name: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> CompanyTierResponse | None:
    row = await OutreachService(db).get_company_tier(company_name)
    if row is None:
        return None
    return CompanyTierResponse(
        company_name=row.company_name,
        tier=cast(CompanyTier, row.tier),
        notes=row.notes,
        updated_at=row.updated_at,
    )
