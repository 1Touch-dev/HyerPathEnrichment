"""Semantic text chunking for document processing.

Chunks documents into semantic segments with token-aware splitting.
Uses LangChain RecursiveCharacterTextSplitter with tiktoken for accurate token counting.
"""

from __future__ import annotations

import logging
from typing import TypedDict

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)


class ChunkDict(TypedDict):
    """Typed dict for chunk metadata."""

    chunk_text: str
    chunk_index: int
    token_count: int
    start_char: int
    end_char: int


def chunk_document(text: str, max_tokens: int = 512, overlap: int = 50) -> list[ChunkDict]:
    """Chunk document into semantic segments respecting token limits.

    Uses RecursiveCharacterTextSplitter with paragraph-aware splitting (\n\n boundaries).
    Token counting via tiktoken ensures accurate 512-token limit per chunk.

    Args:
        text: Document text to chunk
        max_tokens: Maximum tokens per chunk (default 512)
        overlap: Token overlap between chunks (default 50)

    Returns:
        List of chunk dictionaries with text, index, token count, and char positions.

    Example:
        >>> chunks = chunk_document("Long document text...", max_tokens=512, overlap=50)
        >>> for chunk in chunks:
        ...     print(f"Chunk {chunk['chunk_index']}: {chunk['token_count']} tokens")
    """
    if not text.strip():
        return []

    # Use cl100k_base encoding (OpenAI GPT-3.5/4 tokenizer)
    encoding = tiktoken.get_encoding("cl100k_base")

    def _token_length(txt: str) -> int:
        return len(encoding.encode(txt))

    # Paragraph-aware splitting with \n\n as primary separator
    # Use token count as length function
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_tokens,
        chunk_overlap=overlap,
        length_function=_token_length,
        separators=["\n\n", "\n", ". ", " ", ""],
        is_separator_regex=False,
    )

    try:
        raw_chunks = splitter.split_text(text)
    except Exception:
        logger.warning("Text splitter failed; returning single chunk", exc_info=True)
        return [
            {
                "chunk_text": text,
                "chunk_index": 0,
                "token_count": _token_length(text),
                "start_char": 0,
                "end_char": len(text),
            }
        ]

    chunks: list[ChunkDict] = []
    current_pos = 0

    for idx, chunk_text in enumerate(raw_chunks):
        # Find chunk start position in original text
        # Handle overlap by searching from current position
        start_char = text.find(chunk_text, current_pos)
        if start_char == -1:
            # Fallback if exact match fails (shouldn't happen but defensive)
            start_char = current_pos

        end_char = start_char + len(chunk_text)
        token_count = _token_length(chunk_text)

        chunks.append(
            {
                "chunk_text": chunk_text,
                "chunk_index": idx,
                "token_count": token_count,
                "start_char": start_char,
                "end_char": end_char,
            }
        )

        # Move current position forward (account for overlap)
        current_pos = end_char

    logger.info(
        "Chunked document into %d segments",
        len(chunks),
        extra={
            "total_chars": len(text),
            "avg_tokens_per_chunk": sum(c["token_count"] for c in chunks) / len(chunks)
            if chunks
            else 0,
        },
    )

    return chunks
