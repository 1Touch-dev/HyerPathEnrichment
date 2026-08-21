"""Support-impersonation endpoints (§8.15). `end`/`status` operate on the
caller's *own* current session — resolved via `request.state.impersonated_by`
(set by `get_current_user_from_cookie` per §8.16) plus the current user's id,
since neither the JWT's `jti` nor an "active session" lookup has an existing
repository helper to call without editing an already-merged file's body."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import VerifiedUser, get_client_ip
from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.dependencies.rate_limit import enforce_admin_impersonation_start_rate_limit
from app.modules.admin import impersonation, repository
from app.modules.admin.models import ImpersonationSession
from app.modules.admin.permissions import require_permission
from app.modules.admin.schemas import (
    ImpersonationStartRequest,
    ImpersonationStartResponse,
    ImpersonationStatusResponse,
)

router = APIRouter(prefix="/api/admin/impersonation", tags=["admin"], route_class=EnvelopeAPIRoute)


async def _get_active_session(
    db: AsyncSession, *, admin_user_id: UUID, target_user_id: UUID
) -> ImpersonationSession | None:
    result = await db.execute(
        select(ImpersonationSession)
        .where(
            ImpersonationSession.admin_user_id == admin_user_id,
            ImpersonationSession.target_user_id == target_user_id,
            ImpersonationSession.ended_at.is_(None),
        )
        .order_by(ImpersonationSession.started_at.desc())
    )
    return result.scalars().first()


@router.post(
    "/start/{user_id}",
    response_model=ImpersonationStartResponse,
    dependencies=[Depends(enforce_admin_impersonation_start_rate_limit)],
)
async def start_impersonation(
    user_id: UUID,
    payload: ImpersonationStartRequest,
    request: Request,
    response: Response,
    current_user: User = Depends(require_permission("impersonation", "start")),
    db: AsyncSession = Depends(get_db_session),
) -> ImpersonationStartResponse:
    return await impersonation.start_impersonation(
        db,
        admin=current_user,
        target_user_id=user_id,
        reason=payload.reason,
        mfa_code=payload.mfa_code,
        response=response,
        ip_address=get_client_ip(request),
    )


@router.post("/end", status_code=status.HTTP_204_NO_CONTENT)
async def end_impersonation(
    request: Request,
    response: Response,
    current_user: VerifiedUser,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    admin_user_id = getattr(request.state, "impersonated_by", None)
    if admin_user_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Not currently impersonating")

    session = await _get_active_session(
        db, admin_user_id=admin_user_id, target_user_id=current_user.id
    )
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Impersonation session not found")

    await impersonation.end_impersonation(
        db,
        admin_user_id=admin_user_id,
        jti=session.token_jti,
        response=response,
        ip_address=get_client_ip(request),
    )


@router.get("/status", response_model=ImpersonationStatusResponse)
async def get_impersonation_status(
    request: Request,
    current_user: VerifiedUser,
    db: AsyncSession = Depends(get_db_session),
) -> ImpersonationStatusResponse:
    admin_user_id = getattr(request.state, "impersonated_by", None)
    if admin_user_id is None:
        return ImpersonationStatusResponse(
            is_impersonating=False,
            admin_user_id=None,
            admin_email=None,
            target_user_id=None,
            expires_at=None,
        )

    session = await _get_active_session(
        db, admin_user_id=admin_user_id, target_user_id=current_user.id
    )
    admin = await repository.get_user_by_id(db, admin_user_id)
    return ImpersonationStatusResponse(
        is_impersonating=True,
        admin_user_id=admin_user_id,
        admin_email=admin.email if admin else None,
        target_user_id=current_user.id,
        expires_at=session.expires_at if session else None,
    )
