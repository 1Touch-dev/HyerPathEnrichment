"""Document processing RQ worker task.

Background task for processing uploaded candidate documents (PDF/DOCX).
Extracts text, stores file, updates database, and chains to embedding worker.
"""

from __future__ import annotations

import asyncio
import logging

from rq import Queue
from sqlalchemy import text
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

# Import ORM registry FIRST to register all models
import app.database.orm_registry  # noqa: F401
from app.database.session import SessionLocal, engine
from app.infrastructure.redis import close_redis
from app.modules.documents.models import CandidateDocument
from app.services.document_processor import DocumentProcessingError, DocumentProcessor
from app.storage.document_storage import DocumentStorageError

logger = logging.getLogger(__name__)


def process_document_job(document_id: str, file_data: bytes, mime_type: str) -> None:
    """RQ entrypoint (sync) for document processing.

    Args:
        document_id: UUID of candidate_documents record
        file_data: Raw file bytes
        mime_type: MIME type of uploaded file
    """
    asyncio.run(_process_document_job(document_id, file_data, mime_type))


async def _process_document_job(
    document_id: str,
    file_data: bytes,
    mime_type: str,
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
            # Validate document exists
            result = await session.execute(
                text(
                    "SELECT id, user_id, storage_path, document_type "
                    "FROM candidate_documents WHERE id = :doc_id"
                ),
                {"doc_id": document_id},
            )
            doc_row = result.fetchone()

            if not doc_row:
                raise ValueError(f"Document {document_id} not found in database")

            user_id = str(doc_row[1])
            document_type = str(doc_row[3])

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
                .where(CandidateDocument.id == document_id)
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
            await session.commit()

            logger.info(
                "Document processed successfully",
                extra={
                    "document_id": document_id,
                    "token_count": extraction_result["token_count"],
                    "text_length": len(extraction_result["text"]),
                },
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

    except (DocumentProcessingError, DocumentStorageError, ValueError) as exc:
        logger.error(
            "Document processing failed",
            exc_info=True,
            extra={"document_id": document_id, "error": str(exc)},
        )

        # Mark as failed in database
        try:
            if session is not None:
                await session.rollback()

            async with SessionLocal() as recovery_session:
                await recovery_session.execute(
                    sa_update(CandidateDocument)
                    .where(CandidateDocument.id == document_id)
                    .values(processing_status="failed"),
                )
                await recovery_session.commit()
        except Exception:
            logger.error(
                "Failed to mark document as failed",
                exc_info=True,
                extra={"document_id": document_id},
            )

        raise

    except Exception as exc:
        logger.error(
            "Unexpected error in document processing",
            exc_info=True,
            extra={"document_id": document_id, "error_type": type(exc).__name__},
        )
        raise

    finally:
        await close_redis()
        await engine.dispose()


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
