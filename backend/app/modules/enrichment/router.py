from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enrichment import (
    EnrichmentJobListResponse,
    EnrichmentJobResponse,
    EnrichmentRequest,
)
from app.modules.enrichment.service import get_enrichment_service
from app.dependencies.rate_limit import enforce_async_rate_limit, enforce_sync_rate_limit
from app.database.session import get_db_session

router = APIRouter(tags=["enrichment"])


@router.post(
    "/enrich",
    response_model=EnrichmentJobResponse,
    status_code=202,
    dependencies=[Depends(enforce_async_rate_limit)],
)
async def create_enrichment_job(
    request: EnrichmentRequest,
    db: AsyncSession = Depends(get_db_session),
) -> EnrichmentJobResponse:
    service = get_enrichment_service(db)
    return await service.enrich_async(request)


@router.get("/enrich", response_model=EnrichmentJobListResponse)
async def list_enrichment_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> EnrichmentJobListResponse:
    service = get_enrichment_service(db)
    return await service.list_jobs(limit, offset)


@router.get("/enrich/{job_id}", response_model=EnrichmentJobResponse)
async def get_enrichment_job(
    job_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> EnrichmentJobResponse:
    service = get_enrichment_service(db)
    return await service.get_job(job_id)


@router.post(
    "/enrich/sync",
    response_model=EnrichmentJobResponse,
    dependencies=[Depends(enforce_sync_rate_limit)],
)
async def create_sync_enrichment(
    request: EnrichmentRequest,
    db: AsyncSession = Depends(get_db_session),
) -> EnrichmentJobResponse:
    service = get_enrichment_service(db)
    return await service.enrich_sync(request)
