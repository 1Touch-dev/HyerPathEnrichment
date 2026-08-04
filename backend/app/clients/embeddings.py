"""OpenAI embeddings client with retry logic and cost tracking.

Generates text embeddings using OpenAI's text-embedding-3-small model.
Supports batch processing up to 100 texts and includes exponential backoff retry logic.
"""

from __future__ import annotations

import asyncio
import logging

import tiktoken
from openai import AsyncOpenAI, OpenAIError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Default model: text-embedding-3-small (1536 dimensions, $0.02/1M tokens)
DEFAULT_MODEL = "text-embedding-3-small"
DEFAULT_DIMENSIONS = 1536
MAX_BATCH_SIZE = 100
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # 2, 4, 8 seconds


class EmbeddingsClient:
    """OpenAI embeddings client with batch processing and retry logic.

    Usage:
        client = EmbeddingsClient()
        embeddings = await client.generate_embeddings(["text1", "text2"])

        # Single text
        embedding = await client.generate_embedding("single text")
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        dimensions: int = DEFAULT_DIMENSIONS,
    ):
        """Initialize embeddings client.

        Args:
            api_key: OpenAI API key (defaults to settings.OPENAI_API_KEY)
            model: Embedding model name (default: text-embedding-3-small)
            dimensions: Embedding dimensions (default: 1536)
        """
        settings = get_settings()
        self.api_key = api_key or settings.openai_api_key
        self.model = model
        self.dimensions = dimensions
        self.client = AsyncOpenAI(api_key=self.api_key)

        # Token counting for cost tracking
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fallback to cl100k_base if model not found
            self.encoding = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using model's tokenizer.

        Args:
            text: Input text

        Returns:
            Token count
        """
        return len(self.encoding.encode(text))

    async def generate_embedding(self, text: str, *, retry: int = 0) -> tuple[list[float], int]:
        """Generate embedding for a single text with retry logic.

        Args:
            text: Input text to embed
            retry: Current retry attempt (internal use)

        Returns:
            Tuple of (embedding vector, token count)

        Raises:
            OpenAIError: If all retries fail
        """
        if not text.strip():
            logger.warning("Empty text provided for embedding, returning zero vector")
            return [0.0] * self.dimensions, 0

        token_count = self.count_tokens(text)

        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=[text],
                dimensions=self.dimensions,
            )
            embedding = response.data[0].embedding

            logger.debug(
                "Generated embedding",
                extra={"tokens": token_count, "dimensions": len(embedding)},
            )

            return embedding, token_count

        except OpenAIError as e:
            if retry < MAX_RETRIES:
                wait_seconds = RETRY_BACKOFF_BASE**retry
                logger.warning(
                    f"OpenAI API error (attempt {retry + 1}/{MAX_RETRIES + 1}), "
                    f"retrying in {wait_seconds}s",
                    extra={"error": str(e), "retry": retry},
                )
                await asyncio.sleep(wait_seconds)
                return await self.generate_embedding(text, retry=retry + 1)

            logger.error(
                "OpenAI API error after max retries",
                extra={"error": str(e), "retries": MAX_RETRIES},
                exc_info=True,
            )
            raise

    async def generate_embeddings(
        self, texts: list[str], *, retry: int = 0
    ) -> list[tuple[list[float], int]]:
        """Generate embeddings for multiple texts with batch processing and retry.

        Automatically batches requests into MAX_BATCH_SIZE chunks.

        Args:
            texts: List of input texts to embed
            retry: Current retry attempt (internal use)

        Returns:
            List of tuples (embedding vector, token count) in same order as input

        Raises:
            OpenAIError: If all retries fail
        """
        if not texts:
            return []

        # Filter out empty texts and track indices
        non_empty_texts = []
        non_empty_indices = []
        for i, text in enumerate(texts):
            if text.strip():
                non_empty_texts.append(text)
                non_empty_indices.append(i)

        if not non_empty_texts:
            logger.warning("All texts empty, returning zero vectors")
            return [([0.0] * self.dimensions, 0) for _ in texts]

        # Process in batches of MAX_BATCH_SIZE
        all_embeddings: list[tuple[list[float], int]] = []

        for batch_start in range(0, len(non_empty_texts), MAX_BATCH_SIZE):
            batch = non_empty_texts[batch_start : batch_start + MAX_BATCH_SIZE]
            token_counts = [self.count_tokens(text) for text in batch]

            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=batch,
                    dimensions=self.dimensions,
                )

                batch_embeddings = [
                    (data.embedding, token_counts[data.index]) for data in response.data
                ]
                all_embeddings.extend(batch_embeddings)

                logger.info(
                    f"Generated {len(batch)} embeddings (batch {batch_start // MAX_BATCH_SIZE + 1})",
                    extra={
                        "batch_size": len(batch),
                        "total_tokens": sum(token_counts),
                    },
                )

            except OpenAIError as e:
                if retry < MAX_RETRIES:
                    wait_seconds = RETRY_BACKOFF_BASE**retry
                    logger.warning(
                        f"OpenAI API error in batch {batch_start // MAX_BATCH_SIZE + 1} "
                        f"(attempt {retry + 1}/{MAX_RETRIES + 1}), retrying in {wait_seconds}s",
                        extra={"error": str(e), "retry": retry},
                    )
                    await asyncio.sleep(wait_seconds)
                    return await self.generate_embeddings(texts, retry=retry + 1)

                logger.error(
                    "OpenAI API error after max retries",
                    extra={"error": str(e), "retries": MAX_RETRIES},
                    exc_info=True,
                )
                raise

        # Reconstruct full result list with zero vectors for empty texts
        results: list[tuple[list[float], int]] = []
        embedding_iter = iter(all_embeddings)

        for i in range(len(texts)):
            if i in non_empty_indices:
                results.append(next(embedding_iter))
            else:
                results.append(([0.0] * self.dimensions, 0))

        return results


async def get_embeddings_client(
    model: str | None = None, dimensions: int | None = None
) -> EmbeddingsClient:
    """Factory function to get embeddings client with settings defaults.

    Args:
        model: Override default model
        dimensions: Override default dimensions

    Returns:
        Configured EmbeddingsClient instance
    """
    settings = get_settings()
    return EmbeddingsClient(
        api_key=settings.openai_api_key,
        model=model or DEFAULT_MODEL,
        dimensions=dimensions or DEFAULT_DIMENSIONS,
    )
