"""Self-service TOTP MFA endpoints (§8.15). All gated by `Depends(VerifiedUser)`
only — any user manages their own MFA, no special permission needed."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import VerifiedUser
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.dependencies.rate_limit import enforce_admin_mfa_verify_rate_limit
from app.modules.admin import mfa
from app.modules.admin.privileged_operations import (
    begin_idempotent_operation,
    canonical_payload_hash,
    complete_idempotent_operation,
    require_idempotency_key,
)
from app.modules.admin.schemas import (
    MfaEnrollRequest,
    MfaEnrollResponse,
    MfaStatusResponse,
    MfaVerifyRequest,
)

router = APIRouter(prefix="/api/admin/mfa", tags=["admin"], route_class=EnvelopeAPIRoute)


@router.post(
    "/enroll",
    response_model=MfaEnrollResponse,
    dependencies=[Depends(enforce_admin_mfa_verify_rate_limit)],
)
async def enroll_mfa(
    current_user: VerifiedUser,
    payload: MfaEnrollRequest | None = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    db: AsyncSession = Depends(get_db_session),
) -> MfaEnrollResponse:
    normalized_key = require_idempotency_key("mfa.enrollment_started", idempotency_key)
    state, replay = await begin_idempotent_operation(
        db,
        caller_user_id=current_user.id,
        operation_id="mfa.enrollment_started",
        idempotency_key=normalized_key,
        request_hash=canonical_payload_hash(
            {"current_code_present": bool(payload.current_code if payload else None)}
        ),
    )
    if replay is not None:
        return MfaEnrollResponse.model_validate(replay.response_body["mfa"])

    result = await mfa.enroll_mfa(
        db,
        current_user,
        current_code=payload.current_code if payload else None,
    )
    if state is not None:
        await complete_idempotent_operation(
            db,
            state,
            response_status=200,
            response_body={"mfa": result.model_dump(mode="json")},
        )
        await db.commit()
    return result


@router.post(
    "/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(enforce_admin_mfa_verify_rate_limit)],
    response_model=None,
)
async def confirm_mfa_enrollment(
    payload: MfaVerifyRequest,
    current_user: VerifiedUser,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    normalized_key = require_idempotency_key("mfa.enrollment_confirmed", idempotency_key)
    state, replay = await begin_idempotent_operation(
        db,
        caller_user_id=current_user.id,
        operation_id="mfa.enrollment_confirmed",
        idempotency_key=normalized_key,
        request_hash=canonical_payload_hash({"code": payload.code}),
    )
    if replay is not None:
        return
    await mfa.confirm_enrollment(db, current_user, payload.code)
    if state is not None:
        await complete_idempotent_operation(
            db,
            state,
            response_status=204,
            response_body={},
        )
        await db.commit()


@router.post(
    "/disable",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    dependencies=[Depends(enforce_admin_mfa_verify_rate_limit)],
)
async def disable_mfa(
    payload: MfaVerifyRequest,
    current_user: VerifiedUser,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    normalized_key = require_idempotency_key("mfa.disabled", idempotency_key)
    state, replay = await begin_idempotent_operation(
        db,
        caller_user_id=current_user.id,
        operation_id="mfa.disabled",
        idempotency_key=normalized_key,
        request_hash=canonical_payload_hash({"code": payload.code}),
    )
    if replay is not None:
        return
    await mfa.disable_mfa(db, current_user, payload.code)
    if state is not None:
        await complete_idempotent_operation(
            db,
            state,
            response_status=204,
            response_body={},
        )
        await db.commit()


@router.get("/status", response_model=MfaStatusResponse)
async def get_mfa_status(current_user: VerifiedUser) -> MfaStatusResponse:
    return MfaStatusResponse(
        mfa_enabled=current_user.mfa_enabled,
        mfa_enrolled_at=current_user.mfa_enrolled_at,
    )
