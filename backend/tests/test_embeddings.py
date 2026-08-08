"""Tests for OpenAI embeddings client with retry logic and cost tracking."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.clients.embeddings import (
    DEFAULT_DIMENSIONS,
    DEFAULT_MODEL,
    MAX_RETRIES,
    EmbeddingsClient,
    get_embeddings_client,
)


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    mock_data = MagicMock()
    mock_data.embedding = [0.1] * 1536
    mock_data.index = 0

    mock_response = MagicMock()
    mock_response.data = [mock_data]
    return mock_response


@pytest.fixture
def embeddings_client():
    """Create embeddings client with test API key."""
    return EmbeddingsClient(api_key="test-key")


@pytest.mark.asyncio
async def test_generate_embedding_success(embeddings_client, mock_openai_response):
    """Test successful embedding generation for single text."""
    with patch.object(
        embeddings_client.client.embeddings, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_openai_response

        embedding, token_count = await embeddings_client.generate_embedding("test text")

        assert len(embedding) == DEFAULT_DIMENSIONS
        assert token_count > 0
        mock_create.assert_called_once()


@pytest.mark.asyncio
async def test_generate_embedding_empty_text(embeddings_client):
    """Test embedding generation with empty text returns zero vector."""
    embedding, token_count = await embeddings_client.generate_embedding("")

    assert len(embedding) == DEFAULT_DIMENSIONS
    assert all(x == 0.0 for x in embedding)
    assert token_count == 0


@pytest.mark.asyncio
async def test_generate_embedding_retry_logic(embeddings_client, mock_openai_response):
    """Test retry logic on OpenAI API failure."""
    from openai import APIError

    with patch.object(
        embeddings_client.client.embeddings, "create", new_callable=AsyncMock
    ) as mock_create:
        # Create mock request object
        from unittest.mock import MagicMock

        mock_request = MagicMock()

        # Fail twice, then succeed
        mock_create.side_effect = [
            APIError("Rate limit exceeded", request=mock_request, body={}),
            APIError("Rate limit exceeded", request=mock_request, body={}),
            mock_openai_response,
        ]

        embedding, _token_count = await embeddings_client.generate_embedding("test text")

        assert len(embedding) == DEFAULT_DIMENSIONS
        assert mock_create.call_count == 3


@pytest.mark.asyncio
async def test_generate_embedding_max_retries_exceeded(embeddings_client):
    """Test that max retries are respected."""
    from openai import APIError

    with patch.object(
        embeddings_client.client.embeddings, "create", new_callable=AsyncMock
    ) as mock_create:
        # Create mock request object
        from unittest.mock import MagicMock

        mock_request = MagicMock()

        mock_create.side_effect = APIError("Persistent error", request=mock_request, body={})

        with pytest.raises(APIError):
            await embeddings_client.generate_embedding("test text")

        assert mock_create.call_count == MAX_RETRIES + 1


@pytest.mark.asyncio
async def test_generate_embeddings_batch(embeddings_client):
    """Test batch embedding generation."""
    texts = ["text 1", "text 2", "text 3"]

    with patch.object(
        embeddings_client.client.embeddings, "create", new_callable=AsyncMock
    ) as mock_create:
        # Mock batch response
        mock_data_list = []
        for i in range(len(texts)):
            mock_data = MagicMock()
            mock_data.embedding = [0.1 * (i + 1)] * 1536
            mock_data.index = i
            mock_data_list.append(mock_data)

        mock_response = MagicMock()
        mock_response.data = mock_data_list
        mock_create.return_value = mock_response

        results = await embeddings_client.generate_embeddings(texts)

        assert len(results) == len(texts)
        for embedding, token_count in results:
            assert len(embedding) == DEFAULT_DIMENSIONS
            assert token_count > 0


@pytest.mark.asyncio
async def test_generate_embeddings_empty_list(embeddings_client):
    """Test batch generation with empty list."""
    results = await embeddings_client.generate_embeddings([])
    assert results == []


@pytest.mark.asyncio
async def test_generate_embeddings_with_empty_texts(embeddings_client):
    """Test batch generation with some empty texts."""
    texts = ["text 1", "", "text 3"]

    with patch.object(
        embeddings_client.client.embeddings, "create", new_callable=AsyncMock
    ) as mock_create:
        # Mock response for 2 non-empty texts
        mock_data_list = []
        for i in [0, 1]:  # Only 2 embeddings
            mock_data = MagicMock()
            mock_data.embedding = [0.1 * (i + 1)] * 1536
            mock_data.index = i
            mock_data_list.append(mock_data)

        mock_response = MagicMock()
        mock_response.data = mock_data_list
        mock_create.return_value = mock_response

        results = await embeddings_client.generate_embeddings(texts)

        assert len(results) == 3
        # Check that middle one is zero vector
        assert all(x == 0.0 for x in results[1][0])


@pytest.mark.asyncio
async def test_generate_embeddings_large_batch(embeddings_client):
    """Test batch processing splits into MAX_BATCH_SIZE chunks."""
    from app.clients.embeddings import MAX_BATCH_SIZE

    # Create 150 texts (should be split into 2 batches)
    texts = [f"text {i}" for i in range(150)]

    with patch.object(
        embeddings_client.client.embeddings, "create", new_callable=AsyncMock
    ) as mock_create:

        def create_mock_response(batch_size):
            mock_data_list = []
            for i in range(batch_size):
                mock_data = MagicMock()
                mock_data.embedding = [0.1] * 1536
                mock_data.index = i
                mock_data_list.append(mock_data)

            mock_response = MagicMock()
            mock_response.data = mock_data_list
            return mock_response

        # First call: 100 texts, second call: 50 texts
        mock_create.side_effect = [
            create_mock_response(MAX_BATCH_SIZE),
            create_mock_response(50),
        ]

        results = await embeddings_client.generate_embeddings(texts)

        assert len(results) == 150
        assert mock_create.call_count == 2


def test_count_tokens(embeddings_client):
    """Test token counting."""
    text = "This is a test sentence for token counting."
    token_count = embeddings_client.count_tokens(text)

    # Should be > 0 and reasonable
    assert token_count > 0
    assert token_count < 20  # Simple sentence shouldn't have too many tokens


@pytest.mark.asyncio
async def test_get_embeddings_client_factory():
    """Test factory function with settings."""
    with patch("app.clients.embeddings.get_settings") as mock_settings:
        mock_settings.return_value.openai_api_key = "test-api-key"

        client = await get_embeddings_client()

        assert isinstance(client, EmbeddingsClient)
        assert client.model == DEFAULT_MODEL
        assert client.dimensions == DEFAULT_DIMENSIONS


@pytest.mark.asyncio
async def test_get_embeddings_client_custom_params():
    """Test factory function with custom parameters."""
    with patch("app.clients.embeddings.get_settings") as mock_settings:
        mock_settings.return_value.openai_api_key = "test-api-key"

        client = await get_embeddings_client(model="text-embedding-3-large", dimensions=3072)

        assert client.model == "text-embedding-3-large"
        assert client.dimensions == 3072
