"""FastAPI router for the portfolio module. Public slug lookup is intentionally unauthenticated."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.portfolio.schemas import (
    PortfolioItemRequest,
    PortfolioItemResponse,
    PortfolioProfileRequest,
    PortfolioProfileResponse,
    PublicPortfolioResponse,
)
from app.modules.portfolio.service import PortfolioService

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"], route_class=EnvelopeAPIRoute)
public_router = APIRouter(prefix="/api/portfolio", tags=["portfolio-public"], route_class=EnvelopeAPIRoute)


@router.put("/profile", response_model=PortfolioProfileResponse)
async def upsert_profile(
    body: PortfolioProfileRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> PortfolioProfileResponse:
    return await PortfolioService(db).upsert_profile(current_user.id, body)


@router.get("/profile", response_model=PortfolioProfileResponse)
async def get_my_profile(
    current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)
) -> PortfolioProfileResponse:
    return await PortfolioService(db).get_my_profile(current_user.id)


@router.post("/items", response_model=PortfolioItemResponse, status_code=status.HTTP_201_CREATED)
async def add_item(
    body: PortfolioItemRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> PortfolioItemResponse:
    return await PortfolioService(db).add_item(current_user.id, body)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)
) -> None:
    await PortfolioService(db).delete_item(current_user.id, item_id)


@public_router.get("/public/{slug}", response_model=PublicPortfolioResponse)
async def get_public_profile(
    slug: str, db: AsyncSession = Depends(get_db_session)
) -> PublicPortfolioResponse:
    """Unauthenticated — no CurrentUser dependency. This is the endpoint the public /p/{slug} page calls."""
    return await PortfolioService(db).get_public_profile(slug)
