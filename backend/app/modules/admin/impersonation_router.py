"""Support-impersonation endpoints (§8.15). `end`/`status` operate on the
caller's *own* current session — resolved via `request.state.impersonated_by`
(set by `get_current_user_from_cookie` per §8.16) plus the current user's id,
since neither the JWT's `jti` nor an "active session" lookup has an existing
repository helper to call without editing an already-merged file's body."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
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
from app.modules.admin.privileged_operations import (
    begin_idempotent_operation,
    canonical_payload_hash,
    complete_idempotent_operation,
    require_idempotency_key,
)
from app.modules.admin.schemas import (
    ImpersonationStartRequest,
    ImpersonationStartResponse,
    ImpersonationStatusResponse,
)

router = APIRouter(prefix="/api/admin/impersonation", tags=["admin"], route_class=EnvelopeAPIRoute)


async def _get_active_session(
    db: AsyncSession,
    *,
    session_id: UUID,
    admin_user_id: UUID,
    target_user_id: UUID,
) -> ImpersonationSession | None:
    result = await db.execute(
        select(ImpersonationSession).where(
            ImpersonationSession.id == session_id,
            ImpersonationSession.admin_user_id == admin_user_id,
            ImpersonationSession.target_user_id == target_user_id,
            ImpersonationSession.ended_at.is_(None),
            ImpersonationSession.revoked_at.is_(None),
            ImpersonationSession.expires_at > datetime.now(UTC),
        )
    )
    return result.scalar_one_or_none()


async def _forbid_while_impersonating(request: Request) -> None:
    if getattr(request.state, "impersonated_by", None) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "You are already impersonating a user. End that session before starting a new one.",
        )


@router.post(
    "/start/{user_id}",
    response_model=ImpersonationStartResponse,
    dependencies=[
        Depends(enforce_admin_impersonation_start_rate_limit),
        Depends(_forbid_while_impersonating),
    ],
)
async def start_impersonation(
    user_id: UUID,
    payload: ImpersonationStartRequest,
    request: Request,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    current_user: User = Depends(require_permission("impersonation", "start")),
    db: AsyncSession = Depends(get_db_session),
) -> ImpersonationStartResponse:
    normalized_key = require_idempotency_key("impersonation.started", idempotency_key)
    state, replay = await begin_idempotent_operation(
        db,
        caller_user_id=current_user.id,
        operation_id="impersonation.started",
        idempotency_key=normalized_key,
        request_hash=canonical_payload_hash({"user_id": user_id, "reason": payload.reason}),
    )
    if replay is not None:
        return ImpersonationStartResponse.model_validate(replay.response_body["impersonation"])

    result = await impersonation.start_impersonation(
        db,
        admin=current_user,
        target_user_id=user_id,
        reason=payload.reason,
        mfa_code=payload.mfa_code,
        response=response,
        ip_address=get_client_ip(request),
    )
    if state is not None:
        await complete_idempotent_operation(
            db,
            state,
            response_status=200,
            response_body={
                "impersonation": result.model_dump(mode="json"),
            },
        )
        await db.commit()
    return result


@router.post("/end", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def end_impersonation(
    request: Request,
    response: Response,
    current_user: VerifiedUser,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    admin_user_id = getattr(request.state, "impersonated_by", None)
    if admin_user_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Not currently impersonating")
    token_jti = getattr(request.state, "token_jti", None)
    if token_jti is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid impersonation session")

    normalized_key = require_idempotency_key("impersonation.ended", idempotency_key)
    state, replay = await begin_idempotent_operation(
        db,
        caller_user_id=admin_user_id,
        operation_id="impersonation.ended",
        idempotency_key=normalized_key,
        request_hash=canonical_payload_hash({"jti": token_jti}),
    )
    if replay is not None:
        return

    await impersonation.end_impersonation(
        db,
        admin_user_id=admin_user_id,
        jti=token_jti,
        response=response,
        ip_address=get_client_ip(request),
    )
    if state is not None:
        await complete_idempotent_operation(
            db,
            state,
            response_status=204,
            response_body={},
        )
        await db.commit()


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

    session_id = getattr(request.state, "impersonation_session_id", None)
    if session_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid impersonation session")
    session = await _get_active_session(
        db,
        session_id=session_id,
        admin_user_id=admin_user_id,
        target_user_id=current_user.id,
    )
    if session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Impersonation session is not active")
    admin = await repository.get_user_by_id(db, admin_user_id)
    return ImpersonationStatusResponse(
        is_impersonating=True,
        admin_user_id=admin_user_id,
        admin_email=admin.email if admin else None,
        target_user_id=current_user.id,
        expires_at=session.expires_at if session else None,
    )
