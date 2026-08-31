"""FastAPI router for unauthenticated brand landing-page lookups. Mirrors
app/modules/portfolio/router.py's public_router pattern exactly: a separate
APIRouter with its own EnvelopeAPIRoute, no CurrentUser dependency, 404 on
missing/inactive."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.brands import repository
from app.modules.brands.public_schemas import PublicBrandResponse

public_router = APIRouter(
    prefix="/api/brands", tags=["brands-public"], route_class=EnvelopeAPIRoute
)


@public_router.get("/public/{slug}", response_model=PublicBrandResponse)
async def get_public_brand(
    slug: str, db: AsyncSession = Depends(get_db_session)
) -> PublicBrandResponse:
    """Unauthenticated — no CurrentUser dependency. This is the endpoint the
    public brand landing page calls; a brand's tier-config sub-pages read the
    same payload rather than a separate endpoint."""
    brand = await repository.get_brand_by_slug(db, slug)
    if brand is None or not brand.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
    return PublicBrandResponse(
        name=brand.name,
        slug=brand.slug,
        landing_page_tier_config=brand.landing_page_tier_config,
    )
