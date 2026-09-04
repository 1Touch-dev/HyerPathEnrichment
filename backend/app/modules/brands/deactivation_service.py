"""Service layer for turning a brand's public presentation on/off.

See task-orchestration/post-tenancy-features/03-org-offboarding-and-deletion.md —
a Brand is presentation-only, never a data owner, in this model
(docs/adr/0019-tenancy-model.md). Deactivating (or reactivating) a brand has
zero cascading effect on candidates, recruiters, job matches, outreach
messages, documents, or portfolios; it only flips `Brand.is_active` and
records an admin audit entry. Fully reversible at any time — no grace period,
no staged pipeline, nothing irreversible in scope.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.audit import record_admin_action
from app.modules.brands import repository
from app.modules.brands.models import Brand


async def _log_brand_action(
    db: AsyncSession,
    *,
    brand_id: UUID,
    actor_id: UUID,
    action: str,
    before: dict[str, bool] | None,
    after: dict[str, object] | None,
    ip_address: str | None,
) -> None:
    await record_admin_action(
        db,
        actor_user_id=actor_id,
        action=f"brand.{action}",
        target_type="brand",
        target_id=str(brand_id),
        before=before,
        after=after,
        ip_address=ip_address,
    )


async def deactivate_brand(
    db: AsyncSession,
    *,
    brand_id: UUID,
    actor_id: UUID,
    reason: str | None,
    ip_address: str | None = None,
) -> Brand:
    brand = await stage_deactivate_brand(
        db,
        brand_id=brand_id,
        actor_id=actor_id,
        reason=reason,
        ip_address=ip_address,
    )
    await db.commit()
    return brand


async def stage_deactivate_brand(
    db: AsyncSession,
    *,
    brand_id: UUID,
    actor_id: UUID,
    reason: str | None,
    ip_address: str | None = None,
) -> Brand:
    """Turn a brand's public presentation off. No cascading effect on candidates,
    recruiters, or any of their data — a Brand is presentation-only, never a data
    owner, in this model. Fully reversible via reactivate_brand below."""
    brand = await repository.get_brand_by_id(db, brand_id)
    if brand is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")

    before = {"is_active": brand.is_active}
    brand.is_active = False
    await db.flush()
    after: dict[str, object] = {"is_active": brand.is_active, "reason": reason}

    await _log_brand_action(
        db,
        brand_id=brand_id,
        actor_id=actor_id,
        action="deactivate",
        before=before,
        after=after,
        ip_address=ip_address,
    )
    return brand


async def reactivate_brand(
    db: AsyncSession,
    *,
    brand_id: UUID,
    actor_id: UUID,
    ip_address: str | None = None,
) -> Brand:
    brand = await stage_reactivate_brand(
        db,
        brand_id=brand_id,
        actor_id=actor_id,
        ip_address=ip_address,
    )
    await db.commit()
    return brand


async def stage_reactivate_brand(
    db: AsyncSession,
    *,
    brand_id: UUID,
    actor_id: UUID,
    ip_address: str | None = None,
) -> Brand:
    """Undo. No grace period, no staged pipeline — there is nothing irreversible
    to have committed to in the first place, so re-activation is always available."""
    brand = await repository.get_brand_by_id(db, brand_id)
    if brand is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")

    before = {"is_active": brand.is_active}
    brand.is_active = True
    await db.flush()
    after: dict[str, object] = {"is_active": brand.is_active}

    await _log_brand_action(
        db,
        brand_id=brand_id,
        actor_id=actor_id,
        action="reactivate",
        before=before,
        after=after,
        ip_address=ip_address,
    )
    return brand
