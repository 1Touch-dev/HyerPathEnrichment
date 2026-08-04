"""Vector similarity search service with pgvector and SQLite fallback.

Stores document embeddings in PostgreSQL with pgvector extension for efficient similarity search.
Falls back to Python-based cosine similarity when using SQLite.
"""

from __future__ import annotations

import logging
import math
from typing import TypedDict
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class SearchResult(TypedDict):
    """Type for similarity search results."""

    document_id: str
    chunk_index: int
    chunk_text: str
    similarity: float
    token_count: int


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two vectors.

    Fallback implementation for SQLite (no pgvector).

    Args:
        vec1: First embedding vector
        vec2: Second embedding vector

    Returns:
        Cosine similarity score (0-1, higher is more similar)
    """
    if len(vec1) != len(vec2):
        logger.warning(
            "Vector dimension mismatch",
            extra={"vec1_dim": len(vec1), "vec2_dim": len(vec2)},
        )
        return 0.0

    # Dot product
    dot = sum(a * b for a, b in zip(vec1, vec2))

    # Magnitudes
    mag1 = math.sqrt(sum(a * a for a in vec1))
    mag2 = math.sqrt(sum(b * b for b in vec2))

    if mag1 == 0 or mag2 == 0:
        return 0.0

    return dot / (mag1 * mag2)


async def store_embeddings(
    session: AsyncSession,
    document_id: UUID,
    chunks_with_embeddings: list[tuple[dict, list[float], int]],
) -> None:
    """Store document chunk embeddings in database.

    Args:
        session: Database session
        document_id: Parent document UUID
        chunks_with_embeddings: List of (chunk_dict, embedding_vector, token_count)
            where chunk_dict has keys: chunk_text, chunk_index, start_char, end_char
    """
    from app.modules.documents.models import DocumentEmbedding

    embeddings = []
    for chunk, embedding, token_count in chunks_with_embeddings:
        emb = DocumentEmbedding(
            document_id=document_id,
            chunk_index=chunk["chunk_index"],
            chunk_text=chunk["chunk_text"],
            embedding=embedding,
            token_count=token_count,
        )
        embeddings.append(emb)

    session.add_all(embeddings)
    await session.commit()

    logger.info(
        f"Stored {len(embeddings)} embeddings for document {document_id}",
        extra={
            "document_id": str(document_id),
            "num_chunks": len(embeddings),
            "total_tokens": sum(e.token_count for e in embeddings),
        },
    )


async def similarity_search(
    session: AsyncSession,
    query_embedding: list[float],
    limit: int = 10,
    document_id: UUID | None = None,
    similarity_threshold: float = 0.5,
) -> list[SearchResult]:
    """Search for similar document chunks using vector similarity.

    Uses pgvector cosine similarity on PostgreSQL, falls back to Python implementation
    on SQLite.

    Args:
        session: Database session
        query_embedding: Query embedding vector
        limit: Maximum number of results to return
        document_id: Optional filter to single document
        similarity_threshold: Minimum similarity score (0-1)

    Returns:
        List of SearchResult dicts sorted by similarity (highest first)
    """
    from app.modules.documents.models import DocumentEmbedding

    settings = get_settings()
    is_postgres = "postgresql" in settings.database_url.lower()

    if is_postgres:
        # Use pgvector cosine similarity (1 - cosine_distance)
        # cosine_distance is <=> operator in pgvector
        # similarity = 1 - cosine_distance
        query_stmt = select(
            DocumentEmbedding.document_id,
            DocumentEmbedding.chunk_index,
            DocumentEmbedding.chunk_text,
            DocumentEmbedding.token_count,
            # Cast to numeric for comparison
            (1 - text("embedding <=> :query_embedding")).label("similarity"),
        ).where((1 - text("embedding <=> :query_embedding")) >= similarity_threshold)

        if document_id:
            query_stmt = query_stmt.where(DocumentEmbedding.document_id == document_id)

        query_stmt = (
            query_stmt.order_by(text("similarity DESC"))
            .limit(limit)
            .params(query_embedding=query_embedding)
        )

        try:
            result = await session.execute(query_stmt)
            rows = result.all()

            results: list[SearchResult] = [
                {
                    "document_id": str(row.document_id),
                    "chunk_index": row.chunk_index,
                    "chunk_text": row.chunk_text,
                    "similarity": float(row.similarity),
                    "token_count": row.token_count,
                }
                for row in rows
            ]

            logger.info(
                f"pgvector search found {len(results)} results",
                extra={
                    "num_results": len(results),
                    "threshold": similarity_threshold,
                    "document_id": str(document_id) if document_id else None,
                },
            )

            return results

        except Exception as e:
            logger.error(
                "pgvector search failed, falling back to Python implementation",
                extra={"error": str(e)},
                exc_info=True,
            )
            # Fall through to Python implementation

    # SQLite fallback: fetch all embeddings and compute similarity in Python
    logger.info("Using Python-based cosine similarity (SQLite mode)")

    query_stmt = select(DocumentEmbedding)
    if document_id:
        query_stmt = query_stmt.where(DocumentEmbedding.document_id == document_id)

    result = await session.execute(query_stmt)
    all_embeddings = result.scalars().all()

    # Compute similarities
    scored_results: list[tuple[float, DocumentEmbedding]] = []
    for emb in all_embeddings:
        similarity = cosine_similarity(query_embedding, emb.embedding)
        if similarity >= similarity_threshold:
            scored_results.append((similarity, emb))

    # Sort by similarity descending
    scored_results.sort(key=lambda x: x[0], reverse=True)

    # Take top N
    top_results = scored_results[:limit]

    results: list[SearchResult] = [
        {
            "document_id": str(emb.document_id),
            "chunk_index": emb.chunk_index,
            "chunk_text": emb.chunk_text,
            "similarity": similarity,
            "token_count": emb.token_count,
        }
        for similarity, emb in top_results
    ]

    logger.info(
        f"Python similarity search found {len(results)} results",
        extra={
            "total_checked": len(all_embeddings),
            "num_results": len(results),
            "threshold": similarity_threshold,
        },
    )

    return results


async def delete_document_embeddings(session: AsyncSession, document_id: UUID) -> None:
    """Delete all embeddings for a document.

    Args:
        session: Database session
        document_id: Document UUID to delete embeddings for
    """
    from app.modules.documents.models import DocumentEmbedding

    query = select(DocumentEmbedding).where(DocumentEmbedding.document_id == document_id)
    result = await session.execute(query)
    embeddings = result.scalars().all()

    for emb in embeddings:
        await session.delete(emb)

    await session.commit()

    logger.info(
        f"Deleted {len(embeddings)} embeddings for document {document_id}",
        extra={"document_id": str(document_id), "num_deleted": len(embeddings)},
    )
