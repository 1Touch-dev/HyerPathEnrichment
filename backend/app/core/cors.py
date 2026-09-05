"""Per-brand CORS origin resolution (docs/adr/0019-tenancy-model.md).

A brand's ``custom_domain`` needs to be allowed to make credentialed
cross-origin requests against this API. That is purely a routing/presentation
concern -- Brand is never a data-isolation boundary -- so it lives here
alongside the rest of the CORS wiring rather than in `app/modules/brands/`.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.modules.brands.models import Brand

# Mutable on purpose: `app/main.py`'s `CORSMiddleware` is constructed once,
# holding a reference to this exact list object (not a copy) as its
# `allow_origins`. `app/core/lifespan.py`'s startup sequence mutates this list
# in place (via `CORS_ORIGINS[:] = ...`) after resolving brand domains, so the
# already-registered middleware picks up the change -- CORSMiddleware itself
# never re-resolves `allow_origins`, it only reads whatever list it was given.
CORS_ORIGINS: list[str] = list(get_settings().cors_allowed_origins)


async def resolve_cors_origins(settings: Settings, db: AsyncSession) -> list[str]:
    """Static CORS_ALLOWED_ORIGINS plus every active brand's custom_domain,
    deduplicated. Called once at startup (see app/core/lifespan.py), not
    per-request -- CORSMiddleware does not support per-request origin
    resolution, and a live DB query per preflight would add latency to every
    OPTIONS request. Brands that add a custom_domain after this app process
    started need a restart (or a future admin-triggered reload) to take
    effect -- this tradeoff is acceptable because custom-domain changes are
    rare, admin-initiated events, not something end users trigger. This is a
    pure presentation/routing concern -- it has no bearing on data access
    (docs/adr/0019-tenancy-model.md).

    A no-op beyond returning the static allowlist when
    ``settings.enable_brand_cors_origins`` is False, so existing deployments
    are unaffected until they opt in.
    """
    origins = set(settings.cors_allowed_origins)
    if settings.enable_brand_cors_origins:
        result = await db.execute(
            select(Brand.custom_domain).where(
                Brand.custom_domain.is_not(None), Brand.is_active.is_(True)
            )
        )
        origins.update(row[0] for row in result.all() if row[0])
    return sorted(origins)
