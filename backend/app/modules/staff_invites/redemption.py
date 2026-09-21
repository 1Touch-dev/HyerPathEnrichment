"""Transactional staff-invite redemption during account registration."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.modules.admin import service as admin_service
from app.modules.admin.models import Role
from app.modules.staff_invites.models import StaffInvite


async def persist_registration(
    db: AsyncSession,
    *,
    user: User,
    invite: StaffInvite | None,
    invite_role: Role | None,
    ip_address: str | None,
) -> User:
    """Persist a user and valid invite effects in one database transaction.

    User creation, recruiter role assignment, its explicit audit row, and
    invite consumption either commit together or are all rolled back.
    """
    try:
        db.add(user)
        await db.flush()

        if invite is not None and invite_role is not None:
            if invite.invited_by is None:
                raise ValueError("a redeemable staff invite requires an inviter")
            await admin_service.stage_role_assignment(
                db,
                actor_id=invite.invited_by,
                target_user_id=user.id,
                role_id=invite_role.id,
                ip_address=ip_address,
            )
            invite.accepted_at = datetime.now(UTC)
            invite.accepted_by_user_id = user.id
            invite.token = None
            await db.flush()

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    await db.refresh(user)
    return user
