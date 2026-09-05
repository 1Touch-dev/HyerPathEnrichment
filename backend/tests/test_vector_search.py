"""Tests for vector similarity search with pgvector and SQLite fallback."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.vector_search import (
    cosine_similarity,
    delete_document_embeddings,
    similarity_search,
    store_embeddings,
)


def test_cosine_similarity():
    """Test cosine similarity calculation."""
    vec1 = [1.0, 0.0, 0.0]
    vec2 = [1.0, 0.0, 0.0]

    similarity = cosine_similarity(vec1, vec2)
    assert similarity == pytest.approx(1.0)

    vec3 = [0.0, 1.0, 0.0]
    similarity = cosine_similarity(vec1, vec3)
    assert similarity == pytest.approx(0.0)

    vec4 = [1.0, 1.0, 0.0]
    similarity = cosine_similarity(vec1, vec4)
    assert 0.0 < similarity < 1.0


def test_cosine_similarity_dimension_mismatch():
    """Test cosine similarity with mismatched dimensions."""
    vec1 = [1.0, 0.0, 0.0]
    vec2 = [1.0, 0.0]

    similarity = cosine_similarity(vec1, vec2)
    assert similarity == 0.0


def test_cosine_similarity_zero_vectors():
    """Test cosine similarity with zero vectors."""
    vec1 = [0.0, 0.0, 0.0]
    vec2 = [1.0, 0.0, 0.0]

    similarity = cosine_similarity(vec1, vec2)
    assert similarity == 0.0


@pytest.mark.asyncio
async def test_store_embeddings():
    """Test storing embeddings in database."""
    mock_session = AsyncMock()
    document_id = uuid4()

    chunks_with_embeddings = [
        (
            {"chunk_text": "chunk 1", "chunk_index": 0, "start_char": 0, "end_char": 10},
            [0.1] * 1536,
            50,
        ),
        (
            {"chunk_text": "chunk 2", "chunk_index": 1, "start_char": 10, "end_char": 20},
            [0.2] * 1536,
            60,
        ),
    ]

    await store_embeddings(mock_session, document_id, chunks_with_embeddings)

    # Check that embeddings were added
    assert mock_session.add_all.called
    embeddings = mock_session.add_all.call_args[0][0]
    assert len(embeddings) == 2

    # Check that commit was called
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_store_embeddings_empty():
    """Test storing empty embeddings list."""
    mock_session = AsyncMock()
    document_id = uuid4()

    await store_embeddings(mock_session, document_id, [])

    # Should still call add_all with empty list
    assert mock_session.add_all.called
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_similarity_search_postgres():
    """Test similarity search with PostgreSQL/pgvector."""
    mock_session = AsyncMock()
    query_embedding = [0.1] * 1536

    # Mock PostgreSQL dialect
    with patch("app.services.vector_search.get_settings") as mock_settings:
        mock_settings.return_value.database_url = "postgresql://localhost/test"

        # Mock query results
        mock_row = MagicMock()
        mock_row.document_id = uuid4()
        mock_row.chunk_index = 0
        mock_row.chunk_text = "test chunk"
        mock_row.similarity = 0.85
        mock_row.token_count = 50

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]

        mock_session.execute = AsyncMock(return_value=mock_result)

        results = await similarity_search(
            mock_session,
            query_embedding,
            limit=10,
            similarity_threshold=0.5,
        )

        assert len(results) == 1
        assert results[0]["chunk_text"] == "test chunk"
        assert results[0]["similarity"] == 0.85
        assert mock_session.execute.called


@pytest.mark.asyncio
async def test_similarity_search_sqlite_fallback():
    """Test similarity search with SQLite fallback."""
    mock_session = AsyncMock()
    query_embedding = [1.0] + [0.0] * 1535

    # Mock SQLite dialect
    with patch("app.services.vector_search.get_settings") as mock_settings:
        mock_settings.return_value.database_url = "sqlite:///test.db"

        # Mock embeddings in database
        from app.modules.documents.models import DocumentEmbedding

        doc_id = uuid4()
        mock_emb1 = DocumentEmbedding(
            id=uuid4(),
            document_id=doc_id,
            chunk_index=0,
            chunk_text="similar chunk",
            embedding=[0.9] + [0.0] * 1535,  # High similarity
            token_count=50,
        )
        mock_emb2 = DocumentEmbedding(
            id=uuid4(),
            document_id=doc_id,
            chunk_index=1,
            chunk_text="different chunk",
            embedding=[0.0, 1.0] + [0.0] * 1534,  # Low similarity
            token_count=60,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_emb1, mock_emb2]
        mock_session.execute = AsyncMock(return_value=mock_result)

        results = await similarity_search(
            mock_session,
            query_embedding,
            limit=10,
            similarity_threshold=0.5,
        )

        # Should only return the similar one
        assert len(results) == 1
        assert results[0]["chunk_text"] == "similar chunk"
        assert results[0]["similarity"] > 0.8


@pytest.mark.asyncio
async def test_similarity_search_with_document_filter():
    """Test similarity search filtered by document ID."""
    mock_session = AsyncMock()
    query_embedding = [0.1] * 1536
    target_doc_id = uuid4()

    with patch("app.services.vector_search.get_settings") as mock_settings:
        mock_settings.return_value.database_url = "postgresql://localhost/test"

        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        _ = await similarity_search(
            mock_session,
            query_embedding,
            limit=10,
            document_id=target_doc_id,
        )

        # Check that query was executed with document filter
        assert mock_session.execute.called


@pytest.mark.asyncio
async def test_similarity_search_threshold():
    """Test similarity search respects threshold."""
    mock_session = AsyncMock()
    # Query vector pointing in direction [1, 0, 0, ...]
    query_embedding = [1.0] + [0.0] * 1535

    with patch("app.services.vector_search.get_settings") as mock_settings:
        mock_settings.return_value.database_url = "sqlite:///test.db"

        from app.modules.documents.models import DocumentEmbedding

        doc_id = uuid4()
        # Create embeddings with different similarities
        # High similarity: [0.9, 0.1, 0, ...] - mostly aligned with query
        # Low similarity: [0.3, 0.7, 0, ...] - less aligned with query
        mock_emb1 = DocumentEmbedding(
            id=uuid4(),
            document_id=doc_id,
            chunk_index=0,
            chunk_text="high similarity",
            embedding=[0.9, 0.1] + [0.0] * 1534,  # cos_sim ~0.994
            token_count=50,
        )
        mock_emb2 = DocumentEmbedding(
            id=uuid4(),
            document_id=doc_id,
            chunk_index=1,
            chunk_text="low similarity",
            embedding=[0.3, 0.7] + [0.0] * 1534,  # cos_sim ~0.391
            token_count=60,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_emb1, mock_emb2]
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Search with high threshold
        results = await similarity_search(
            mock_session,
            query_embedding,
            limit=10,
            similarity_threshold=0.7,
        )

        # Should only return high similarity one
        assert len(results) == 1
        assert results[0]["chunk_text"] == "high similarity"


@pytest.mark.asyncio
async def test_similarity_search_limit():
    """Test similarity search respects limit."""
    mock_session = AsyncMock()
    query_embedding = [1.0] + [0.0] * 1535

    with patch("app.services.vector_search.get_settings") as mock_settings:
        mock_settings.return_value.database_url = "sqlite:///test.db"

        from app.modules.documents.models import DocumentEmbedding

        doc_id = uuid4()
        # Create 5 similar embeddings
        mock_embeddings = []
        for i in range(5):
            mock_emb = DocumentEmbedding(
                id=uuid4(),
                document_id=doc_id,
                chunk_index=i,
                chunk_text=f"chunk {i}",
                embedding=[0.9] + [0.0] * 1535,
                token_count=50,
            )
            mock_embeddings.append(mock_emb)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_embeddings
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Search with limit 3
        results = await similarity_search(
            mock_session,
            query_embedding,
            limit=3,
            similarity_threshold=0.5,
        )

        # Should only return 3 results
        assert len(results) == 3


@pytest.mark.asyncio
async def test_delete_document_embeddings():
    """Test deleting embeddings for a document."""
    mock_session = AsyncMock()
    document_id = uuid4()

    # Mock existing embeddings
    from app.modules.documents.models import DocumentEmbedding

    mock_emb1 = DocumentEmbedding(
        id=uuid4(),
        document_id=document_id,
        chunk_index=0,
        chunk_text="chunk 1",
        embedding=[0.1] * 1536,
        token_count=50,
    )
    mock_emb2 = DocumentEmbedding(
        id=uuid4(),
        document_id=document_id,
        chunk_index=1,
        chunk_text="chunk 2",
        embedding=[0.2] * 1536,
        token_count=60,
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_emb1, mock_emb2]
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.delete = AsyncMock()

    await delete_document_embeddings(mock_session, document_id)

    # Check that both embeddings were deleted
    assert mock_session.delete.call_count == 2
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_delete_document_embeddings_none_exist():
    """Test deleting embeddings when none exist."""
    mock_session = AsyncMock()
    document_id = uuid4()

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    await delete_document_embeddings(mock_session, document_id)

    # Should still commit (no-op)
    assert mock_session.commit.called
    # But no delete calls
    assert not mock_session.delete.called
