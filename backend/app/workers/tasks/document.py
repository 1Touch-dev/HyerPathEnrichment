"""Document processing RQ worker task.

Background task for processing uploaded candidate documents (PDF/DOCX).
Extracts text, stores file, updates database, and chains to embedding worker.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from rq import Queue
from sqlalchemy import select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

# Import ORM registry FIRST to register all models
import app.database.orm_registry  # noqa: F401
from app.database.session import SessionLocal, SyncSessionLocal, engine
from app.infrastructure.redis import close_redis
from app.modules.admin.moderation_flagging import flag_if_needed
from app.modules.documents.models import CandidateDocument, DocumentJob
from app.services.document_processor import DocumentProcessor

logger = logging.getLogger(__name__)


def process_document_job(document_id: str, file_data: bytes, mime_type: str, job_id: str) -> None:
    """RQ entrypoint (sync) for document processing.

    Args:
        document_id: UUID of candidate_documents record
        file_data: Raw file bytes
        mime_type: MIME type of uploaded file
        job_id: UUID of the DocumentJob record the client polls for status
    """
    asyncio.run(_process_document_job(document_id, file_data, mime_type, job_id))


async def _process_document_job(
    document_id: str,
    file_data: bytes,
    mime_type: str,
    job_id: str,
) -> None:
    """Process document: extract text, update DB, chain to embedding worker.

    This is the core async implementation. It:
    1. Validates the document exists in DB
    2. Processes the file (extract text)
    3. Updates the DB with extracted text and metadata
    4. Chains to embedding_generation queue for vector storage
    """
    session: AsyncSession | None = None

    try:
        async with SessionLocal() as session:
            # Validate document exists. Use the ORM (not a raw text() query) so the
            # Uuid-typed id column gets proper bind-parameter coercion — document_id
            # arrives here as a hyphenated str (from str(document.id) at enqueue time),
            # which does not match SQLite's non-hyphenated stored hex representation
            # under a raw string comparison.
            doc_result = await session.execute(
                select(CandidateDocument).where(CandidateDocument.id == UUID(document_id))
            )
            doc_row = doc_result.scalar_one_or_none()

            if doc_row is None:
                raise ValueError(f"Document {document_id} not found in database")

            user_id = str(doc_row.user_id)
            document_type = str(doc_row.document_type)

            logger.info(
                "Processing document",
                extra={
                    "document_id": document_id,
                    "user_id": user_id[:8],
                    "mime_type": mime_type,
                    "file_size": len(file_data),
                },
            )

            # Process document
            processor = DocumentProcessor()
            extraction_result = processor.process_document(file_data, mime_type)

            # Fail-soft structured CV extraction (skills, role, experience, etc.) layered
            # on top of the raw text/metadata extraction above. A failure here must never
            # break document processing — only the structured fields are lost.
            cv_structured_data: dict[str, object] = {}
            if document_type == "cv":
                try:
                    from app.core.config import get_settings
                    from app.services.cv_extractor import extract_cv_data

                    settings = get_settings()
                    cv_data = await extract_cv_data(extraction_result["text"], settings)
                    if cv_data.completeness_score > 0.0:
                        cv_structured_data = cv_data.model_dump()
                    else:
                        logger.warning(
                            "CV structured extraction returned empty/low-completeness result",
                            extra={"document_id": document_id, "user_id": user_id[:8]},
                        )
                except Exception as cv_exc:
                    logger.warning(
                        "CV structured extraction failed; continuing without structured fields",
                        exc_info=True,
                        extra={
                            "document_id": document_id,
                            "user_id": user_id[:8],
                            "error": str(cv_exc),
                        },
                    )

            # Update database with extracted content
            await session.execute(
                sa_update(CandidateDocument)
                .where(CandidateDocument.id == UUID(document_id))
                .values(
                    raw_text=extraction_result["text"],
                    extracted_data={
                        "token_count": extraction_result["token_count"],
                        "page_count": extraction_result.get("page_count"),
                        "paragraph_count": extraction_result.get("paragraph_count"),
                        "metadata": extraction_result.get("metadata", {}),
                        **cv_structured_data,
                    },
                    processing_status="completed",
                ),
            )
            # Mirror the terminal state onto the DocumentJob row the client is
            # actually polling (GET /api/documents/jobs/{job_id}) — without this,
            # that endpoint shows "pending" forever even after the document itself
            # finishes processing, since it reads DocumentJob.status, not
            # CandidateDocument.processing_status. progress is a 0.0-1.0 fraction
            # (JobStatusResponse.progress has ge=0.0, le=1.0) — not a percentage.
            # Scoped by the specific job's primary key (job_id) rather than
            # document_id+"pending", since a document can have multiple
            # DocumentJob rows (e.g. reprocess) and only this job's row should
            # transition here.
            await session.execute(
                sa_update(DocumentJob)
                .where(DocumentJob.id == UUID(job_id))
                .values(status="completed", progress=1.0)
            )
            await session.commit()

            logger.info(
                "Document processed successfully",
                extra={
                    "document_id": document_id,
                    "token_count": extraction_result["token_count"],
                    "text_length": len(extraction_result["text"]),
                },
            )

            # Soft-moderation flagging (Batch 1 admin module): runs after the
            # document's own success is already committed, so a flagging
            # failure can never affect processing_status/DocumentJob.status.
            # All document types are flagged (not just "cv") — any uploaded
            # candidate file's extracted text can carry spam/abuse content.
            # flag_if_needed is internally fail-open (see moderation_flagging.py),
            # but this call site still wraps it defensively: the test suite
            # mocks flag_if_needed directly, which bypasses that internal
            # safety net entirely, so this try/except is the only thing
            # guaranteeing a broken/changed flagging implementation can never
            # break document processing.
            try:
                await flag_if_needed(
                    session,
                    resource_type="document",
                    resource_id=UUID(document_id),
                    text_fields=[extraction_result["text"]],
                )
            except Exception:
                logger.warning(
                    "flag_if_needed raised unexpectedly; ignoring (fail-open)",
                    exc_info=True,
                    extra={"document_id": document_id},
                )

            # Chain to embedding generation queue
            # NOTE: This assumes embedding worker exists - part of Agent 2's work
            max_chain_attempts = 3
            chain_attempt = 0
            chain_success = False

            while chain_attempt < max_chain_attempts and not chain_success:
                try:
                    from app.workers.queue import QUEUE_EMBEDDING, get_redis_connection

                    redis_conn = get_redis_connection()
                    embedding_queue = Queue(QUEUE_EMBEDDING, connection=redis_conn)

                    # Enqueue embedding job with document_id (worker fetches text from DB)
                    embedding_queue.enqueue(
                        "app.workers.tasks.embedding.run_embedding_job",
                        document_id,
                        job_timeout=300,  # 5 minutes
                    )

                    logger.info(
                        "Chained to embedding queue",
                        extra={"document_id": document_id, "queue": QUEUE_EMBEDDING},
                    )
                    chain_success = True
                except Exception as chain_exc:
                    chain_attempt += 1
                    if chain_attempt == max_chain_attempts:
                        # Final failure - log but don't crash document processing
                        logger.warning(
                            "Failed to chain to embedding queue after max attempts",
                            exc_info=True,
                            extra={
                                "document_id": document_id,
                                "error": str(chain_exc),
                                "attempts": chain_attempt,
                            },
                        )
                    else:
                        # Retry with brief delay
                        logger.warning(
                            f"Failed to chain to embedding queue (attempt {chain_attempt}/{max_chain_attempts}), retrying",
                            extra={"document_id": document_id, "error": str(chain_exc)},
                        )
                        await asyncio.sleep(1)

    except Exception as exc:
        logger.error(
            "Document processing failed",
            exc_info=True,
            extra={"document_id": document_id, "job_id": job_id, "error": str(exc)},
        )

        # Mark as failed in database
        try:
            if session is not None:
                await session.rollback()

            async with SessionLocal() as recovery_session:
                await recovery_session.execute(
                    sa_update(CandidateDocument)
                    .where(CandidateDocument.id == UUID(document_id))
                    .values(processing_status="failed"),
                )
                await recovery_session.execute(
                    sa_update(DocumentJob)
                    .where(DocumentJob.id == UUID(job_id))
                    .values(status="failed", error=str(exc))
                )
                await recovery_session.commit()
        except Exception:
            logger.error(
                "Failed to mark document as failed",
                exc_info=True,
                extra={"document_id": document_id, "job_id": job_id},
            )

        raise

    finally:
        await close_redis()
        await engine.dispose()


def on_document_job_failure(
    job: Any,
    connection: Any,
    exc_type: Any,
    exc_value: Any,
    exc_traceback: Any,
) -> None:
    """RQ ``on_failure`` callback: safety net for cases where no Python
    ``except`` in `_process_document_job` ever ran at all — a `job_timeout`
    exceeded or a killed/abandoned worker process (RQ's `AbandonedJobError`).
    RQ's worker-maintenance process invokes `on_failure` callbacks for these
    cases too, not just for in-task exceptions.

    Must never raise: RQ callbacks have their own timeout/failure handling,
    and letting an exception escape here would crash the RQ maintenance
    process. Idempotent: only updates rows still in "pending" state, so it
    never clobbers a terminal state already written by the normal in-task
    exception handler (which may have run first).
    """
    try:
        document_id = job.args[0]
        job_id = job.args[3]
    except Exception:
        logger.error(
            "on_document_job_failure: could not extract document_id/job_id from job.args",
            exc_info=True,
        )
        return

    try:
        error_message = f"Worker-level failure: {exc_type.__name__}: {exc_value}"
    except Exception:
        error_message = "Worker-level failure (details unavailable)"

    logger.error(
        "Document job failed at the RQ worker level (timeout or crashed/abandoned worker)",
        extra={"document_id": document_id, "job_id": job_id, "error": error_message},
    )

    try:
        with SyncSessionLocal() as session:
            session.execute(
                sa_update(DocumentJob)
                .where(DocumentJob.id == UUID(job_id), DocumentJob.status == "pending")
                .values(status="failed", error=error_message)
            )
            session.execute(
                sa_update(CandidateDocument)
                .where(
                    CandidateDocument.id == UUID(document_id),
                    CandidateDocument.processing_status == "pending",
                )
                .values(processing_status="failed")
            )
            session.commit()
    except Exception:
        logger.error(
            "on_document_job_failure: failed to mark job/document as failed",
            exc_info=True,
            extra={"document_id": document_id, "job_id": job_id},
        )


def check_worker_health(queue_name: str) -> bool:
    """Health check for document worker.

    Args:
        queue_name: Name of queue to check

    Returns:
        True if worker is healthy
    """
    try:
        from app.workers.queue import get_redis_connection

        redis_conn = get_redis_connection()

        # Test Redis connectivity with ping
        redis_conn.ping()

        # Test write operation
        test_key = f"health_check:{queue_name}"
        redis_conn.setex(test_key, 10, "ok")

        queue = Queue(queue_name, connection=redis_conn)

        # Check if we can connect and get queue length
        queue_len = len(queue)
        logger.debug(f"Health check: queue {queue_name} has {queue_len} jobs")
        return True
    except Exception as exc:
        logger.error(f"Health check failed: {exc}", exc_info=True)
        return False
