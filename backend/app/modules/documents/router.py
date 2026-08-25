"""FastAPI router for document management API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.dependencies.rate_limit import enforce_documents_upload_rate_limit
from app.modules.documents.cv_chat_service import CvChatService
from app.modules.documents.schemas import (
    AcceptBulletRequest,
    CvChatMessageRequest,
    CvChatSessionResponse,
    CvChatTurnResponse,
    CvCompletenessResponse,
    CVDataResponse,
    CvFeedbackRequest,
    CvFeedbackResponse,
    DocumentDetailResponse,
    DocumentMetadata,
    DocumentUploadResponse,
    JobStatusResponse,
    SearchRequest,
    SearchResponse,
)
from app.modules.documents.service import DocumentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"], route_class=EnvelopeAPIRoute)


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(enforce_documents_upload_rate_limit)],
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


@router.post("/search", response_model=SearchResponse)
async def search_documents(
    search_request: SearchRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> SearchResponse:
    """Semantic search across candidate documents.

    Uses vector embeddings to find semantically similar content.
    Requires document processing and embedding generation to be complete.

    Args:
        search_request: Search query and filters
        current_user: Authenticated user
        db: Database session

    Returns:
        Search response with results list

    Note:
        This endpoint requires Agent 2's embedding worker to be operational.
        Returns empty results if embeddings are not available.
    """
    service = DocumentService(db)
    results = await service.search_documents(search_request, current_user.id)
    return SearchResponse(results=results)


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> DocumentDetailResponse:
    """Get document details by ID.

    Returns complete document information including extracted text and metadata.

    Args:
        document_id: Document UUID
        current_user: Authenticated user
        db: Database session

    Returns:
        Document details

    Raises:
        404: Document not found
    """
    service = DocumentService(db)
    return await service.get_document_by_id(document_id, current_user.id)


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


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a document and its associated data.

    Deletes the document record, embeddings, and associated jobs.
    Cascade delete handles embeddings automatically.

    Args:
        document_id: Document UUID
        current_user: Authenticated user
        db: Database session

    Raises:
        404: Document not found
    """
    service = DocumentService(db)
    await service.delete_document(document_id, current_user.id)


@router.post("/{document_id}/reprocess", response_model=DocumentUploadResponse)
async def reprocess_document(
    document_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> DocumentUploadResponse:
    """Reprocess an existing document.

    Creates a new processing job for an existing document.
    Useful for reprocessing failed jobs or updating extracted data.

    Args:
        document_id: Document UUID
        current_user: Authenticated user
        db: Database session

    Returns:
        Upload response with new job_id

    Raises:
        404: Document not found
    """
    service = DocumentService(db)
    return await service.reprocess_document(document_id, current_user.id)


@router.get("/{document_id}/completeness", response_model=CvCompletenessResponse)
async def get_completeness(
    document_id: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)
) -> CvCompletenessResponse:
    """Missing-field completeness check (Decision 1). Drives the 'let's finish your CV' prompt."""
    service = DocumentService(db)
    return await service.get_completeness(document_id, current_user.id)


@router.post("/{document_id}/cv-chat/sessions", response_model=CvChatSessionResponse)
async def start_cv_chat_session(
    document_id: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)
) -> CvChatSessionResponse:
    """Start (or resume) the missing-info chatbot for a document."""
    service = CvChatService(db)
    return await service.start_session(document_id, current_user.id)


@router.get("/cv-chat/sessions/{session_id}", response_model=CvChatSessionResponse)
async def get_cv_chat_session(
    session_id: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)
) -> CvChatSessionResponse:
    """Fetch an owned CV-completeness chat session by id."""
    service = CvChatService(db)
    return await service.get_session(session_id, current_user.id)


@router.post("/cv-chat/sessions/{session_id}/messages", response_model=CvChatTurnResponse)
async def post_cv_chat_message(
    session_id: str,
    body: CvChatMessageRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> CvChatTurnResponse:
    """One turn-based (non-streamed, Decision 2) chatbot exchange."""
    service = CvChatService(db)
    return await service.post_message(session_id, current_user.id, body.content)


@router.post("/{document_id}/feedback", response_model=DocumentUploadResponse)
async def request_cv_feedback(
    document_id: str,
    body: CvFeedbackRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> DocumentUploadResponse:
    """Enqueue AI CV-improvement generation (Decision 3)."""
    service = DocumentService(db)
    return await service.request_cv_feedback(document_id, current_user.id, body.target_role)


@router.get("/{document_id}/feedback", response_model=CvFeedbackResponse)
async def get_cv_feedback(
    document_id: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)
) -> CvFeedbackResponse:
    """Latest CV-improvement report for a document."""
    service = DocumentService(db)
    return await service.get_latest_cv_feedback(document_id, current_user.id)


@router.post("/{document_id}/feedback/{report_id}/accept", response_model=CvFeedbackResponse)
async def accept_cv_feedback_bullet(
    document_id: str,
    report_id: str,
    body: AcceptBulletRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> CvFeedbackResponse:
    """Explicitly accept one rewritten bullet — the only way a suggestion is endorsed (Decision 3)."""
    service = DocumentService(db)
    return await service.accept_cv_feedback_bullet(
        document_id, current_user.id, report_id, body.bullet_index
    )
