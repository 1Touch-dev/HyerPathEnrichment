from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.domain.enrichment import SuppressionCheckResponse, SuppressionRequest
from app.modules.opt_out.service import get_opt_out_service

router = APIRouter(prefix="/api", tags=["opt-out"], route_class=EnvelopeAPIRoute)


@router.post("/opt-out", status_code=202)
async def create_opt_out(
    request: SuppressionRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    service = get_opt_out_service(db)
    await service.register(request.identifier, request.reason)
    return {"status": "accepted"}


@router.get("/opt-out/check", response_model=SuppressionCheckResponse)
async def check_opt_out(
    identifier: str,
    db: AsyncSession = Depends(get_db_session),
) -> SuppressionCheckResponse:
    service = get_opt_out_service(db)
    return SuppressionCheckResponse(
        identifier=identifier,
        suppressed=await service.is_suppressed(identifier),
    )
