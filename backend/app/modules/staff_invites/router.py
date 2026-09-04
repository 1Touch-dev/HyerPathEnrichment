"""FastAPI router for staff invites. Creation requires ("users", "write") permission
(reusing the existing admin RBAC dependency); the token-lookup endpoint is public and
unauthenticated -- it only needs to answer "is this invite still valid?" for a
pending-signup UI."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_client_ip
from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.core.errors import ForbiddenError, InternalError, ValidationAppError
from app.core.logging import get_request_id
from app.database.session import get_db_session
from app.dependencies.rate_limit import enforce_admin_mfa_verify_rate_limit
from app.modules.admin.mfa import verify_mfa_code
from app.modules.admin.models import Role
from app.modules.admin.permissions import require_permission
from app.modules.staff_invites import repository
from app.modules.staff_invites.schemas import (
    PublicStaffInviteResponse,
    StaffInviteCreate,
    StaffInviteResponse,
)

router = APIRouter(prefix="/api", tags=["staff-invites"], route_class=EnvelopeAPIRoute)
public_router = APIRouter(
    prefix="/api", tags=["staff-invites-public"], route_class=EnvelopeAPIRoute
)


def _ensure_aware(dt: datetime) -> datetime:
    """SQLite does not persist tzinfo even for DateTime(timezone=True) columns,
    so values read back from the DB come back naive. Treat naive values as UTC
    to allow safe comparison against datetime.now(UTC). Matches the identical
    helper in app/auth/refresh_tokens.py."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


@router.post(
    "/staff-invites",
    response_model=StaffInviteResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_admin_mfa_verify_rate_limit)],
)
async def create_invite(
    body: StaffInviteCreate,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=255),
    ],
    user: User = Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db_session),
) -> StaffInviteResponse:
    if not idempotency_key.strip():
        raise ValidationAppError("Idempotency-Key must not be blank")
    if body.confirmation_email.casefold() != body.email.casefold():
        raise ValidationAppError("Typed confirmation must match the invite email")
    if not user.mfa_enabled or not verify_mfa_code(user, body.mfa_code.get_secret_value()):
        raise ForbiddenError("Recent step-up authentication required")
    request_id = get_request_id()
    if not request_id:
        raise InternalError("Request context unavailable")
    invite, plaintext_token = await repository.create_invite(
        db,
        email=body.email,
        role_name=body.role_name,
        invited_by=user.id,
        request_id=request_id,
        idempotency_key=idempotency_key,
        ip_address=get_client_ip(request),
    )
    return StaffInviteResponse.model_validate(invite).model_copy(
        update={"invite_token": plaintext_token}
    )


@public_router.get("/staff-invites/{token}", response_model=PublicStaffInviteResponse)
async def get_invite(
    token: str, db: AsyncSession = Depends(get_db_session)
) -> PublicStaffInviteResponse:
    """Unauthenticated -- no CurrentUser/VerifiedUser dependency. This is the
    endpoint a pending-signup UI calls to display invite details before the
    invitee has an account."""
    invite = await repository.get_invite_by_token(db, token)
    recruiter_role_id = await db.scalar(select(Role.id).where(Role.name == "recruiter"))
    inviter: User | None = None
    if invite is not None and invite.invited_by is not None:
        inviter = await db.get(User, invite.invited_by)
    if (
        invite is None
        or invite.accepted_at is not None
        or invite.revoked_at is not None
        or invite.role_name != "recruiter"
        or invite.role_id != recruiter_role_id
        or invite.invited_by is None
        or inviter is None
        or not inviter.is_active
        or inviter.deleted_at is not None
        or _ensure_aware(invite.expires_at) < datetime.now(UTC)
    ):
        # Bearer-token callers must not be able to distinguish an unknown
        # credential from an expired, revoked, replayed, or unsafe-role one.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite unavailable",
        )

    return PublicStaffInviteResponse(
        invited_by_name=f"{inviter.first_name} {inviter.last_name}" if inviter else None,
        role_name=invite.role_name,
        email=invite.email,
        expires_at=invite.expires_at,
    )
