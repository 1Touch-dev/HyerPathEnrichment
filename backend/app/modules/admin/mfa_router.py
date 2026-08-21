"""Self-service TOTP MFA endpoints (§8.15). All gated by `Depends(VerifiedUser)`
only — any user manages their own MFA, no special permission needed."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import VerifiedUser
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.dependencies.rate_limit import enforce_admin_mfa_verify_rate_limit
from app.modules.admin import mfa
from app.modules.admin.schemas import MfaEnrollResponse, MfaStatusResponse, MfaVerifyRequest

router = APIRouter(prefix="/api/admin/mfa", tags=["admin"], route_class=EnvelopeAPIRoute)


@router.post("/enroll", response_model=MfaEnrollResponse)
async def enroll_mfa(
    current_user: VerifiedUser,
    db: AsyncSession = Depends(get_db_session),
) -> MfaEnrollResponse:
    return await mfa.enroll_mfa(db, current_user)


@router.post(
    "/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(enforce_admin_mfa_verify_rate_limit)],
)
async def confirm_mfa_enrollment(
    payload: MfaVerifyRequest,
    current_user: VerifiedUser,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    await mfa.confirm_enrollment(db, current_user, payload.code)


@router.post("/disable", status_code=status.HTTP_204_NO_CONTENT)
async def disable_mfa(
    current_user: VerifiedUser,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    await mfa.disable_mfa(db, current_user)


@router.get("/status", response_model=MfaStatusResponse)
async def get_mfa_status(current_user: VerifiedUser) -> MfaStatusResponse:
    return MfaStatusResponse(
        mfa_enabled=current_user.mfa_enabled,
        mfa_enrolled_at=current_user.mfa_enrolled_at,
    )
