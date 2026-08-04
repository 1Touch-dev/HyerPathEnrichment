"""RQ task handler for embedding generation.

Processes document chunks and generates OpenAI embeddings for vector search.
Integrates with Agent 1's document processor and Agent 3's chunking.
"""

from __future__ import annotations

import logging
from uuid import UUID

from rq import get_current_job
from sqlalchemy import select

from app.clients.embeddings import get_embeddings_client
from app.database.session import get_db_session
from app.modules.documents.models import CandidateDocument
from app.observability.cost_tracking import track_embedding_cost
from app.services.vector_search import store_embeddings
from app.utils.text_chunking import chunk_document
from app.workers.queue import QUEUE_EMBEDDING, get_redis_connection

logger = logging.getLogger(__name__)


async def process_document_embeddings(document_id: str) -> dict:
    """Generate embeddings for a document's text chunks.

    Workflow:
    1. Fetch document from Agent 1's CandidateDocument table
    2. Use Agent 3's chunking to split text
    3. Generate embeddings via OpenAI
    4. Store in pgvector (or SQLite fallback)
    5. Track costs

    Args:
        document_id: UUID string of CandidateDocument

    Returns:
        Result dict with success status and metrics

    Raises:
        ValueError: If document not found or has no text
        Exception: On OpenAI API or database errors
    """
    doc_uuid = UUID(document_id)

    async with get_db_session() as session:
        # Fetch document
        query = select(CandidateDocument).where(CandidateDocument.id == doc_uuid)
        result = await session.execute(query)
        document = result.scalar_one_or_none()

        if not document:
            raise ValueError(f"Document {document_id} not found")

        if not document.raw_text or not document.raw_text.strip():
            raise ValueError(f"Document {document_id} has no text content")

        logger.info(
            f"Processing embeddings for document {document_id}",
            extra={
                "document_id": document_id,
                "filename": document.original_filename,
                "text_length": len(document.raw_text),
            },
        )

        # Step 1: Chunk document (Agent 3's functionality)
        chunks = chunk_document(document.raw_text, max_tokens=512, overlap=50)

        if not chunks:
            logger.warning(f"No chunks generated for document {document_id}")
            return {
                "success": False,
                "error": "No chunks generated",
                "document_id": document_id,
            }

        logger.info(
            f"Generated {len(chunks)} chunks for document {document_id}",
            extra={"document_id": document_id, "num_chunks": len(chunks)},
        )

        # Step 2: Generate embeddings
        embeddings_client = await get_embeddings_client()
        chunk_texts = [chunk["chunk_text"] for chunk in chunks]

        try:
            embeddings_with_tokens = await embeddings_client.generate_embeddings(chunk_texts)
        except Exception as e:
            logger.error(
                f"Failed to generate embeddings for document {document_id}",
                extra={"document_id": document_id, "error": str(e)},
                exc_info=True,
            )
            raise

        # Step 3: Store embeddings
        chunks_with_embeddings = [
            (chunk, embedding, token_count)
            for chunk, (embedding, token_count) in zip(chunks, embeddings_with_tokens)
        ]

        await store_embeddings(session, doc_uuid, chunks_with_embeddings)

        # Step 4: Track costs
        total_tokens = sum(token_count for _, _, token_count in chunks_with_embeddings)
        await track_embedding_cost(
            model="text-embedding-3-small",
            tokens=total_tokens,
            num_embeddings=len(chunks),
        )

        # Update document processing status
        document.processing_status = "embedded"
        await session.commit()

        result_data = {
            "success": True,
            "document_id": document_id,
            "num_chunks": len(chunks),
            "total_tokens": total_tokens,
            "avg_tokens_per_chunk": total_tokens / len(chunks) if chunks else 0,
        }

        logger.info(
            f"Successfully generated embeddings for document {document_id}",
            extra=result_data,
        )

        return result_data


def run_embedding_job(document_id: str) -> dict:
    """RQ worker entry point for embedding generation.

    Synchronous wrapper for async embedding processing.

    Args:
        document_id: UUID string of CandidateDocument

    Returns:
        Result dict from process_document_embeddings
    """
    import asyncio

    job = get_current_job()
    logger.info(
        "Starting embedding job",
        extra={
            "job_id": job.id if job else "unknown",
            "document_id": document_id,
            "queue": QUEUE_EMBEDDING,
        },
    )

    try:
        result = asyncio.run(process_document_embeddings(document_id))
        logger.info(
            "Embedding job completed",
            extra={"document_id": document_id, "result": result},
        )
        return result

    except Exception as e:
        logger.error(
            "Embedding job failed",
            extra={
                "document_id": document_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        raise


def check_worker_health(queue_name: str) -> bool:
    """Health check for embedding worker.

    Args:
        queue_name: Queue name to check (should be QUEUE_EMBEDDING)

    Returns:
        True if worker is healthy (queue accessible)
    """
    try:
        redis_conn = get_redis_connection()
        # Simple Redis ping
        redis_conn.ping()

        # Check if we can access the queue
        from rq import Queue

        queue = Queue(queue_name, connection=redis_conn)

        # If we can get queue length, we're healthy
        _ = len(queue)

        return True

    except Exception as e:
        logger.error(
            "Worker health check failed",
            extra={"queue": queue_name, "error": str(e)},
            exc_info=True,
        )
        return False
