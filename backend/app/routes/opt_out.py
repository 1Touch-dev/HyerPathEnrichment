from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SuppressionCheckResponse, SuppressionRequest
from app.services import get_orchestrator
from app.storage.db import get_db_session

router = APIRouter(prefix="/api", tags=["opt-out"])


@router.post("/opt-out", status_code=202)
async def create_opt_out(
    request: SuppressionRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    orchestrator = get_orchestrator(db)
    await orchestrator.register_opt_out(request.identifier, request.reason)
    return {"status": "accepted"}


@router.get("/opt-out/check", response_model=SuppressionCheckResponse)
async def check_opt_out(
    identifier: str,
    db: AsyncSession = Depends(get_db_session),
) -> SuppressionCheckResponse:
    orchestrator = get_orchestrator(db)
    return SuppressionCheckResponse(identifier=identifier, suppressed=await orchestrator.check_suppression(identifier))
