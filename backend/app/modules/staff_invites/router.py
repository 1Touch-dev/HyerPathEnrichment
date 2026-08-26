"""FastAPI router for staff invites. Creation requires ("users", "write") permission
(reusing the existing admin RBAC dependency); the token-lookup endpoint is public and
unauthenticated -- it only needs to answer "is this invite still valid?" for a
pending-signup UI."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
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
)
async def create_invite(
    body: StaffInviteCreate,
    user: User = Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db_session),
) -> StaffInviteResponse:
    # Resend-upsert edge case: reuse a still-pending, unexpired invite for the same
    # email instead of creating a duplicate row.
    existing = await repository.get_pending_invite_for_email(db, body.email)
    if existing:
        return StaffInviteResponse.model_validate(existing)

    invite = await repository.create_invite(
        db, email=body.email, role_name=body.role_name, invited_by=user.id
    )
    return StaffInviteResponse.model_validate(invite)


@public_router.get("/staff-invites/{token}", response_model=PublicStaffInviteResponse)
async def get_invite(
    token: str, db: AsyncSession = Depends(get_db_session)
) -> PublicStaffInviteResponse:
    """Unauthenticated -- no CurrentUser/VerifiedUser dependency. This is the
    endpoint a pending-signup UI calls to display invite details before the
    invitee has an account."""
    invite = await repository.get_invite_by_token(db, token)
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
    if invite.accepted_at is not None:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invite already accepted")
    if _ensure_aware(invite.expires_at) < datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invite has expired")

    inviter: User | None = None
    if invite.invited_by is not None:
        result = await db.execute(select(User).where(User.id == invite.invited_by))
        inviter = result.scalar_one_or_none()

    return PublicStaffInviteResponse(
        invited_by_name=f"{inviter.first_name} {inviter.last_name}" if inviter else None,
        role_name=invite.role_name,
        email=invite.email,
        expires_at=invite.expires_at,
    )
