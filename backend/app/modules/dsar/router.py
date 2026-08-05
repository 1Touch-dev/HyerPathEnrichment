from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import VerifiedUser
from app.auth.models import User
from app.compliance.dsar import get_dsar, process_dsar
from app.core.api_route import EnvelopeAPIRoute
from app.core.errors import NotFoundError
from app.database.session import get_db_session
from app.domain.enrichment import DsarRequest, DsarResponse

router = APIRouter(prefix="/api", tags=["dsar"], route_class=EnvelopeAPIRoute)


@router.post("/dsar", response_model=DsarResponse, status_code=status.HTTP_201_CREATED)
async def create_dsar(
    request: DsarRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(VerifiedUser),
) -> DsarResponse:
    """
    Create a new DSAR (Data Subject Access Request).

    Requires authenticated and verified user.
    DSAR requests are tied to the authenticated user for access control.
    """
    return await process_dsar(db, request, current_user.id)


@router.get("/dsar/{dsar_id}", response_model=DsarResponse)
async def read_dsar(
    dsar_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(VerifiedUser),
) -> DsarResponse:
    """
    Retrieve a DSAR request by ID.

    Requires authenticated and verified user.
    Users can only access their own DSAR requests.
    """
    record = await get_dsar(db, dsar_id, current_user.id)
    if record is None:
        raise NotFoundError("dsar request not found", meta={"dsar_id": dsar_id})
    return record
