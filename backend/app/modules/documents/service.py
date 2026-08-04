"""Business logic for document processing and management."""

from __future__ import annotations

import hashlib
import logging
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from redis import Redis
from rq import Queue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.models import CandidateDocument, DocumentJob
from app.modules.documents.schemas import (
    CVDataResponse,
    DocumentDetailResponse,
    DocumentMetadata,
    DocumentUploadResponse,
    JobStatusResponse,
    SearchRequest,
    SearchResult,
)
from app.workers.queue import QUEUE_DOCUMENT, get_redis_connection

logger = logging.getLogger(__name__)


# Allowed file types and size limits
ALLOWED_MIME_TYPES = {
    "application/pdf": [".pdf"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
    "application/msword": [".doc"],
}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


class DocumentService:
    """Service for document upload, processing, and retrieval."""

    def __init__(self, db: AsyncSession, redis_conn: Redis | None = None):
        """Initialize document service.

        Args:
            db: Database session
            redis_conn: Redis connection (created if not provided)
        """
        self.db = db
        self.redis_conn = redis_conn or get_redis_connection()

    async def upload_document(
        self,
        file: UploadFile,
        user_id: UUID,
        document_type: str = "cv",
    ) -> DocumentUploadResponse:
        """Upload and enqueue document for processing.

        Args:
            file: Uploaded file
            user_id: User ID
            document_type: Type of document (cv, cover_letter)

        Returns:
            Upload response with job_id and document_id

        Raises:
            HTTPException: If validation fails
        """
        # Validate file type
        if file.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_MIME_TYPES.keys())}",
            )

        # Read file data
        file_data = await file.read()
        file_size = len(file_data)

        # Validate file size
        if file_size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size: {MAX_FILE_SIZE_BYTES / (1024 * 1024):.0f} MB",
            )

        # Calculate file hash for deduplication
        file_hash = hashlib.sha256(file_data).hexdigest()

        # Check for duplicate
        result = await self.db.execute(
            select(CandidateDocument).where(
                CandidateDocument.user_id == user_id,
                CandidateDocument.file_hash == file_hash,
            )
        )
        existing_doc = result.scalar_one_or_none()

        if existing_doc:
            logger.info(
                "Duplicate document detected",
                extra={
                    "user_id": str(user_id)[:8],
                    "file_hash": file_hash[:16],
                    "existing_doc_id": str(existing_doc.id),
                },
            )
            return DocumentUploadResponse(
                job_id="",  # No new job
                document_id=str(existing_doc.id),
                message="Document already exists",
            )

        # Create document record
        storage_path = f"documents/{user_id}/{file_hash}{_get_file_extension(file.filename or '')}"
        document = CandidateDocument(
            user_id=user_id,
            document_type=document_type,
            original_filename=file.filename or "unknown",
            storage_path=storage_path,
            file_hash=file_hash,
            file_size_bytes=file_size,
            processing_status="pending",
        )
        self.db.add(document)
        await self.db.flush()

        # Create job record
        job = DocumentJob(
            user_id=user_id,
            document_id=document.id,
            job_type="upload",
            status="pending",
            progress=0.0,
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(document)
        await self.db.refresh(job)

        # Enqueue to RQ
        try:
            queue = Queue(QUEUE_DOCUMENT, connection=self.redis_conn)
            rq_job = queue.enqueue(
                "app.workers.tasks.document.process_document_job",
                str(document.id),
                file_data,
                file.content_type,
                job_timeout=300,  # 5 minutes
            )

            logger.info(
                "Document enqueued for processing",
                extra={
                    "job_id": str(job.id),
                    "document_id": str(document.id),
                    "rq_job_id": rq_job.id,
                    "user_id": str(user_id)[:8],
                },
            )

        except Exception as e:
            logger.error(
                "Failed to enqueue document",
                exc_info=True,
                extra={"job_id": str(job.id), "error": str(e)},
            )
            # Mark job as failed
            job.status = "failed"
            job.error = f"Failed to enqueue: {str(e)}"
            await self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to enqueue document for processing",
            )

        return DocumentUploadResponse(
            job_id=str(job.id),
            document_id=str(document.id),
            message="Document uploaded successfully",
        )

    async def get_job_status(self, job_id: str, user_id: UUID) -> JobStatusResponse:
        """Get job status.

        Args:
            job_id: Job UUID
            user_id: User ID (for authorization)

        Returns:
            Job status

        Raises:
            HTTPException: If job not found or unauthorized
        """
        result = await self.db.execute(
            select(DocumentJob).where(
                DocumentJob.id == UUID(job_id),
                DocumentJob.user_id == user_id,
            )
        )
        job = result.scalar_one_or_none()

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found",
            )

        return JobStatusResponse(
            job_id=str(job.id),
            status=job.status,
            progress=job.progress,
            document_id=str(job.document_id) if job.document_id else None,
            result=job.result,
            error=job.error,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )

    async def search_documents(
        self,
        search_request: SearchRequest,
        user_id: UUID,
    ) -> list[SearchResult]:
        """Semantic search across candidate documents.

        Args:
            search_request: Search query and filters
            user_id: User ID (for authorization)

        Returns:
            List of search results

        Note:
            This is a placeholder implementation. Actual semantic search
            requires vector embeddings from Agent 2's work.
        """
        # TODO: Implement semantic search with vector embeddings
        # For now, return empty results
        logger.warning(
            "Semantic search not yet implemented",
            extra={"query": search_request.query, "user_id": str(user_id)[:8]},
        )
        return []

    async def get_document_by_id(self, document_id: str, user_id: UUID) -> DocumentDetailResponse:
        """Get document by ID.

        Args:
            document_id: Document UUID
            user_id: User ID (for authorization)

        Returns:
            Document details

        Raises:
            HTTPException: If document not found or unauthorized
        """
        result = await self.db.execute(
            select(CandidateDocument).where(
                CandidateDocument.id == UUID(document_id),
                CandidateDocument.user_id == user_id,
            )
        )
        document = result.scalar_one_or_none()

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

        return DocumentDetailResponse(
            document_id=str(document.id),
            document_type=document.document_type,
            original_filename=document.original_filename,
            file_size_bytes=document.file_size_bytes,
            processing_status=document.processing_status,
            raw_text=document.raw_text,
            extracted_data=document.extracted_data,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

    async def get_cv_data(self, document_id: str, user_id: UUID) -> CVDataResponse:
        """Get structured CV data.

        Args:
            document_id: Document UUID
            user_id: User ID (for authorization)

        Returns:
            Structured CV data

        Raises:
            HTTPException: If document not found or unauthorized
        """
        result = await self.db.execute(
            select(CandidateDocument).where(
                CandidateDocument.id == UUID(document_id),
                CandidateDocument.user_id == user_id,
            )
        )
        document = result.scalar_one_or_none()

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

        return CVDataResponse(
            document_id=str(document.id),
            extracted_data=document.extracted_data or {},
            raw_text=document.raw_text,
            processing_status=document.processing_status,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

    async def list_documents(self, user_id: UUID, limit: int = 50) -> list[DocumentMetadata]:
        """List user's documents.

        Args:
            user_id: User ID
            limit: Max documents to return

        Returns:
            List of document metadata
        """
        result = await self.db.execute(
            select(CandidateDocument)
            .where(CandidateDocument.user_id == user_id)
            .order_by(CandidateDocument.created_at.desc())
            .limit(limit)
        )
        documents = result.scalars().all()

        return [
            DocumentMetadata(
                document_id=str(doc.id),
                document_type=doc.document_type,
                original_filename=doc.original_filename,
                file_size_bytes=doc.file_size_bytes,
                processing_status=doc.processing_status,
                created_at=doc.created_at,
            )
            for doc in documents
        ]


def _get_file_extension(filename: str) -> str:
    """Extract file extension from filename."""
    if "." in filename:
        return "." + filename.rsplit(".", 1)[-1].lower()
    return ""
