"""Business logic for document processing and management."""

from __future__ import annotations

import hashlib
import logging
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from redis import Redis
from rq import Callback, Queue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.embeddings import get_embeddings_client
from app.core.file_sniff import claimed_mime_matches_bytes
from app.domain.candidate import CVData
from app.domain.cv_completeness import completeness_score, compute_missing_fields
from app.modules.documents.models import (
    DOCUMENT_READY_STATUSES,
    CandidateDocument,
    CvChatSession,
    CvFeedbackReport,
    DocumentJob,
)
from app.modules.documents.schemas import (
    CvCompletenessResponse,
    CVDataResponse,
    CvFeedbackResponse,
    DocumentDetailResponse,
    DocumentMetadata,
    DocumentUploadResponse,
    JobStatusResponse,
    RewrittenBullet,
    SearchRequest,
    SearchResult,
)
from app.services.feedback_generator import ATS_SCORE_METHODOLOGY
from app.services.vector_search import similarity_search
from app.storage.document_storage import DocumentStorageClient, DocumentStorageError
from app.workers.queue import QUEUE_DOCUMENT, QUEUE_FEEDBACK, get_redis_connection

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
        self.storage = DocumentStorageClient()

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

        if not claimed_mime_matches_bytes(file.content_type, file_data):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content does not match declared Content-Type",
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
            # Create a job record with status="duplicate" for tracking.
            # progress is a 0.0-1.0 fraction (JobStatusResponse.progress has
            # ge=0.0, le=1.0) — not a percentage.
            job = DocumentJob(
                user_id=user_id,
                document_id=existing_doc.id,
                job_type="upload",
                status="duplicate",
                progress=1.0,
            )
            self.db.add(job)
            await self.db.commit()
            await self.db.refresh(job)

            return DocumentUploadResponse(
                job_id=str(job.id),
                document_id=str(existing_doc.id),
                message="Document already exists",
            )

        # Create document record: persist bytes to storage first so we never
        # leave an orphaned DB row pointing at a storage_path that was never
        # actually written.
        try:
            storage_path, _, _ = await self.storage.upload_document(
                file_data,
                file.filename or "unknown",
                file.content_type or "application/octet-stream",
                str(user_id),
                document_type,
            )
        except DocumentStorageError as exc:
            logger.error(
                "Failed to persist document to storage",
                exc_info=True,
                extra={"user_id": str(user_id)[:8], "error": str(exc)},
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to store document: {exc}",
            )

        document = CandidateDocument(
            user_id=user_id,
            document_type=document_type,
            original_filename=file.filename or "unknown",
            storage_path=storage_path,
            mime_type=file.content_type,
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
                str(job.id),
                job_timeout=300,  # 5 minutes
                on_failure=Callback(
                    "app.workers.tasks.document.on_document_job_failure", timeout=30
                ),
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
            job.error = f"Failed to enqueue: {e!s}"
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
        """Semantic search across candidate documents using vector embeddings.

        Args:
            search_request: Search query and filters
            user_id: User ID (for authorization)

        Returns:
            List of search results
        """
        # Step 1: Generate query embedding
        embeddings_client = get_embeddings_client()
        query_embedding, _ = await embeddings_client.generate_embedding(search_request.query)

        # Step 2: Vector similarity search
        raw_results = await similarity_search(
            session=self.db,
            query_embedding=query_embedding,
            limit=search_request.limit or 10,
            similarity_threshold=0.5,
        )

        # Step 3: Authorization filter (user can only search their own documents)
        if raw_results:
            doc_ids = [UUID(r["document_id"]) for r in raw_results]
            auth_query = select(CandidateDocument).where(
                CandidateDocument.id.in_(doc_ids),
                CandidateDocument.user_id == user_id,
            )
            authorized = await self.db.execute(auth_query)
            authorized_docs = {str(doc.id): doc for doc in authorized.scalars()}

            # Filter to only authorized documents
            raw_results = [r for r in raw_results if r["document_id"] in authorized_docs]

            # Step 4: Map to API schema
            return [
                SearchResult(
                    document_id=r["document_id"],
                    similarity_score=r["similarity"],
                    cv_data=authorized_docs[r["document_id"]].extracted_data or {},
                    excerpt=r["chunk_text"][:200],
                )
                for r in raw_results
            ]

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

    async def delete_document(self, document_id: str, user_id: UUID) -> None:
        """Delete a document and its associated data.

        Args:
            document_id: Document UUID
            user_id: User ID (for authorization)

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

        # Delete document (cascade deletes embeddings and jobs)
        await self.db.delete(document)
        await self.db.commit()

        logger.info(
            "Document deleted",
            extra={
                "document_id": document_id,
                "user_id": str(user_id)[:8],
            },
        )

    async def reprocess_document(self, document_id: str, user_id: UUID) -> DocumentUploadResponse:
        """Reprocess an existing document.

        Creates a new processing job for an existing document.

        Args:
            document_id: Document UUID
            user_id: User ID (for authorization)

        Returns:
            Upload response with new job_id

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

        # Legacy rows predate storage-backed uploads (no mime_type, and their
        # storage_path was never actually written to R2/local cache), so there
        # are no bytes to re-extract from.
        if document.mime_type is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This document predates file storage support and cannot be "
                    "reprocessed automatically — re-upload it instead."
                ),
            )

        try:
            file_data = await self.storage.download_document(document.storage_path)
        except DocumentStorageError as exc:
            logger.error(
                "Failed to download document for reprocessing",
                exc_info=True,
                extra={"document_id": document_id, "error": str(exc)},
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stored file could not be retrieved: {exc}",
            )

        # Reset processing status
        document.processing_status = "pending"
        document.raw_text = None
        document.extracted_data = None

        # Create new job record
        job = DocumentJob(
            user_id=user_id,
            document_id=document.id,
            job_type="reprocess",
            status="pending",
            progress=0.0,
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)

        # Enqueue to RQ, mirroring upload_document's enqueue logic exactly.
        try:
            queue = Queue(QUEUE_DOCUMENT, connection=self.redis_conn)
            rq_job = queue.enqueue(
                "app.workers.tasks.document.process_document_job",
                str(document.id),
                file_data,
                document.mime_type,
                str(job.id),
                job_timeout=300,  # 5 minutes
                on_failure=Callback(
                    "app.workers.tasks.document.on_document_job_failure", timeout=30
                ),
            )

            logger.info(
                "Document reprocess job enqueued",
                extra={
                    "job_id": str(job.id),
                    "document_id": str(document.id),
                    "rq_job_id": rq_job.id,
                    "user_id": str(user_id)[:8],
                },
            )

        except Exception as e:
            logger.error(
                "Failed to enqueue document reprocessing",
                exc_info=True,
                extra={"job_id": str(job.id), "error": str(e)},
            )
            # Mark job as failed
            job.status = "failed"
            job.error = f"Failed to enqueue: {e!s}"
            await self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to enqueue document for reprocessing",
            )

        return DocumentUploadResponse(
            job_id=str(job.id),
            document_id=str(document.id),
            message="Document queued for reprocessing",
        )

    async def get_completeness(self, document_id: str, user_id: UUID) -> CvCompletenessResponse:
        """Compute completeness for a processed document (Decision 1)."""
        document = await self._get_owned_document(document_id, user_id)
        cv_data = CVData(**(document.extracted_data or {})) if document.extracted_data else CVData()
        missing = compute_missing_fields(cv_data)

        active_session = await self.db.execute(
            select(CvChatSession).where(
                CvChatSession.document_id == document.id, CvChatSession.status == "active"
            )
        )
        return CvCompletenessResponse(
            document_id=str(document.id),
            completeness_score=completeness_score(cv_data),
            missing_fields=missing,
            has_active_chat_session=active_session.scalar_one_or_none() is not None,
        )

    async def request_cv_feedback(
        self, document_id: str, user_id: UUID, target_role: str | None
    ) -> DocumentUploadResponse:
        """Enqueue CV improvement generation (Decision 3). Reuses QUEUE_FEEDBACK — no new queue."""
        document = await self._get_owned_document(document_id, user_id)
        if document.processing_status not in DOCUMENT_READY_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Document must finish processing before requesting feedback",
            )

        job = DocumentJob(
            user_id=user_id,
            document_id=document.id,
            job_type="cv_feedback",
            status="pending",
            progress=0.0,
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)

        try:
            queue = Queue(QUEUE_FEEDBACK, connection=self.redis_conn)
            queue.enqueue(
                "app.workers.tasks.cv_improvement.generate_cv_improvement_job",
                str(document.id),
                str(job.id),
                target_role,
                job_timeout=120,
            )
        except Exception as e:
            job.status = "failed"
            job.error = f"Failed to enqueue: {e!s}"
            await self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to enqueue CV feedback generation",
            )

        return DocumentUploadResponse(
            job_id=str(job.id),
            document_id=str(document.id),
            message="CV feedback generation started",
        )

    async def get_latest_cv_feedback(self, document_id: str, user_id: UUID) -> CvFeedbackResponse:
        document = await self._get_owned_document(document_id, user_id)
        result = await self.db.execute(
            select(CvFeedbackReport)
            .where(CvFeedbackReport.document_id == document.id)
            .order_by(CvFeedbackReport.created_at.desc())
            .limit(1)
        )
        report = result.scalar_one_or_none()
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No feedback report yet"
            )
        return self._feedback_to_response(report)

    async def accept_cv_feedback_bullet(
        self, document_id: str, user_id: UUID, report_id: str, bullet_index: int
    ) -> CvFeedbackResponse:
        """Explicit candidate 'accept' — this is the ONLY path that constitutes endorsement (Decision 3)."""
        await self._get_owned_document(document_id, user_id)
        result = await self.db.execute(
            select(CvFeedbackReport).where(
                CvFeedbackReport.id == UUID(report_id), CvFeedbackReport.user_id == user_id
            )
        )
        report = result.scalar_one_or_none()
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Feedback report not found"
            )
        if bullet_index < 0 or bullet_index >= len(report.rewritten_bullets):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid bullet index"
            )
        if bullet_index not in report.accepted_bullet_indices:
            report.accepted_bullet_indices = [*report.accepted_bullet_indices, bullet_index]
            await self.db.commit()
            await self.db.refresh(report)
        return self._feedback_to_response(report)

    async def _get_owned_document(self, document_id: str, user_id: UUID) -> CandidateDocument:
        result = await self.db.execute(
            select(CandidateDocument).where(
                CandidateDocument.id == UUID(document_id), CandidateDocument.user_id == user_id
            )
        )
        document = result.scalar_one_or_none()
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        return document

    def _feedback_to_response(self, report: CvFeedbackReport) -> CvFeedbackResponse:
        return CvFeedbackResponse(
            report_id=str(report.id),
            document_id=str(report.document_id),
            target_role=report.target_role,
            ats_score=report.ats_score,
            ats_score_methodology=ATS_SCORE_METHODOLOGY,
            strengths=report.strengths,
            improvements=report.improvements,
            rewritten_bullets=[RewrittenBullet(**b) for b in report.rewritten_bullets],
            accepted_bullet_indices=report.accepted_bullet_indices,
            created_at=report.created_at,
        )


def _get_file_extension(filename: str) -> str:
    """Extract file extension from filename."""
    if "." in filename:
        return "." + filename.rsplit(".", 1)[-1].lower()
    return ""
