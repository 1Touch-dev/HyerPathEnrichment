"""Data-access layer for staff invites. Plain async functions, not a class --
matches app/modules/portfolio/repository.py's style."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.staff_invites.models import StaffInvite


async def get_invite_by_token(db: AsyncSession, token: str) -> StaffInvite | None:
    result = await db.execute(select(StaffInvite).where(StaffInvite.token == token))
    return result.scalar_one_or_none()


async def get_pending_invite_for_email(db: AsyncSession, email: str) -> StaffInvite | None:
    """Pending (accepted_at IS NULL) and unexpired invite for this email, if any.
    Backs the resend-upsert edge case -- do not create a second row for the
    same still-pending, unexpired email."""
    result = await db.execute(
        select(StaffInvite).where(
            StaffInvite.email == email,
            StaffInvite.accepted_at.is_(None),
            StaffInvite.expires_at >= datetime.now(UTC),
        )
    )
    return result.scalar_one_or_none()


async def create_invite(
    db: AsyncSession, *, email: str, role_name: str, invited_by: UUID | None
) -> StaffInvite:
    invite = StaffInvite(
        id=uuid4(),
        email=email,
        role_name=role_name,
        invited_by=invited_by,
        token=secrets.token_urlsafe(32),
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return invite
