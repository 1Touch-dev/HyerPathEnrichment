"""FastAPI router for document management API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.documents.schemas import (
    CVDataResponse,
    DocumentMetadata,
    DocumentUploadResponse,
    JobStatusResponse,
    SearchRequest,
    SearchResult,
)
from app.modules.documents.service import DocumentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"], route_class=EnvelopeAPIRoute)


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
    file: UploadFile = File(..., description="Document file (PDF, DOCX)"),
    document_type: str = Query(default="cv", pattern="^(cv|cover_letter)$"),
) -> DocumentUploadResponse:
    """Upload candidate document (CV or cover letter).

    The document is enqueued for processing. Use the returned job_id
    to poll for processing status.

    Args:
        file: Uploaded file (PDF or DOCX)
        document_type: Type of document (cv or cover_letter)
        current_user: Authenticated user
        db: Database session

    Returns:
        Upload response with job_id for status polling

    Raises:
        400: Invalid file type or format
        413: File too large
        500: Failed to enqueue
    """
    service = DocumentService(db)
    return await service.upload_document(file, current_user.id, document_type)


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> JobStatusResponse:
    """Poll document processing job status.

    Returns current status, progress, and result/error when complete.

    Args:
        job_id: Job UUID
        current_user: Authenticated user
        db: Database session

    Returns:
        Job status with progress and result

    Raises:
        404: Job not found
    """
    service = DocumentService(db)
    return await service.get_job_status(job_id, current_user.id)


@router.post("/search", response_model=list[SearchResult])
async def search_documents(
    search_request: SearchRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> list[SearchResult]:
    """Semantic search across candidate documents.

    Uses vector embeddings to find semantically similar content.
    Requires document processing and embedding generation to be complete.

    Args:
        search_request: Search query and filters
        current_user: Authenticated user
        db: Database session

    Returns:
        List of search results with similarity scores

    Note:
        This endpoint requires Agent 2's embedding worker to be operational.
        Returns empty results if embeddings are not available.
    """
    service = DocumentService(db)
    return await service.search_documents(search_request, current_user.id)


@router.get("/{document_id}/cv-data", response_model=CVDataResponse)
async def get_cv_data(
    document_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> CVDataResponse:
    """Get structured CV data from processed document.

    Returns extracted CV data including personal info, experience, education, etc.

    Args:
        document_id: Document UUID
        current_user: Authenticated user
        db: Database session

    Returns:
        Structured CV data

    Raises:
        404: Document not found
    """
    service = DocumentService(db)
    return await service.get_cv_data(document_id, current_user.id)


@router.get("", response_model=list[DocumentMetadata])
async def list_documents(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[DocumentMetadata]:
    """List user's uploaded documents.

    Returns metadata for all documents owned by the current user.

    Args:
        limit: Maximum number of documents to return
        current_user: Authenticated user
        db: Database session

    Returns:
        List of document metadata
    """
    service = DocumentService(db)
    return await service.list_documents(current_user.id, limit)
