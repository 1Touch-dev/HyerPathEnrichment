"""FastAPI router for outreach drafting/editing/sending."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.dependencies.rate_limit import enforce_outreach_send_rate_limit
from app.modules.outreach.schemas import (
    OutreachDraftRequest,
    OutreachEditRequest,
    OutreachListResponse,
    OutreachMessageResponse,
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
