from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.dsar import get_dsar, process_dsar
from app.models import DsarRequest, DsarResponse
from app.storage.db import get_db_session

router = APIRouter(prefix="/api", tags=["dsar"])


@router.post("/dsar", response_model=DsarResponse, status_code=status.HTTP_201_CREATED)
async def create_dsar(
    request: DsarRequest,
    db: AsyncSession = Depends(get_db_session),
) -> DsarResponse:
    return await process_dsar(db, request)


@router.get("/dsar/{dsar_id}", response_model=DsarResponse)
async def read_dsar(
    dsar_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> DsarResponse:
    record = await get_dsar(db, dsar_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="dsar request not found")
    return record
