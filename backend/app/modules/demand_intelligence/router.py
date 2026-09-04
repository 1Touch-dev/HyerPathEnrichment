"""FastAPI router for country-demand intelligence read endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import VerifiedUser
from app.auth.models import User
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.admin.permissions import require_permission
from app.modules.demand_intelligence import repository, service
from app.modules.demand_intelligence.schemas import CountryDemandRow, TopCountriesResponse

router = APIRouter(
    prefix="/api/demand-intelligence", tags=["demand-intelligence"], route_class=EnvelopeAPIRoute
)


@router.get("/top-countries", response_model=TopCountriesResponse)
async def get_top_countries(
    role: str,
    user: VerifiedUser,
    _permission_ok: User = Depends(require_permission("analytics", "read")),
    limit: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
) -> TopCountriesResponse:
    del user
    top_snapshots = await service.get_top_countries_for_role(db, role, limit)
    if not top_snapshots:
        return TopCountriesResponse(role=role, results=[], generated_at=datetime.now(UTC))

    latest_date = top_snapshots[0].snapshot_date
    all_snapshots_for_role = await repository.get_snapshots_for_role(db, role, latest_date)

    results = [
        CountryDemandRow(
            country_iso2=snapshot.country_iso2,
            role_bucket=snapshot.role_bucket,
            posting_count=snapshot.posting_count,
            remote_posting_count=snapshot.remote_posting_count,
            avg_salary_min=snapshot.avg_salary_min,
            avg_salary_max=snapshot.avg_salary_max,
            snapshot_date=snapshot.snapshot_date,
            tier=await service.classify_country_tier(snapshot, all_snapshots_for_role),
        )
        for snapshot in top_snapshots
    ]
    return TopCountriesResponse(role=role, results=results, generated_at=datetime.now(UTC))
