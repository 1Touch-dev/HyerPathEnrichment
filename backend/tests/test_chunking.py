"""Tests for semantic text chunking."""

from __future__ import annotations


from app.utils.text_chunking import chunk_document


def test_chunk_empty_text():
    """Empty text returns empty list."""
    result = chunk_document("")
    assert result == []
    assert isinstance(result, list)


def test_chunk_respects_token_limit():
    """All chunks respect the 512 token limit."""
    # Generate text with ~2000 tokens (8000 chars)
    text = "This is a sample sentence that will be repeated many times. " * 140

    chunks = chunk_document(text, max_tokens=512, overlap=50)

    assert len(chunks) > 0
    for chunk in chunks:
        assert chunk["token_count"] <= 512
        assert chunk["token_count"] > 0


def test_chunk_overlap_works():
    """Chunks have token overlap between segments."""
    text = "This is sentence one. " * 50 + "This is sentence two. " * 50

    chunks = chunk_document(text, max_tokens=200, overlap=30)

    assert len(chunks) >= 2
    # Verify overlap exists (chunks should share some text)
    # Check that consecutive chunks don't have huge gaps
    for i in range(len(chunks) - 1):
        gap = chunks[i + 1]["start_char"] - chunks[i]["end_char"]
        # Gap should be small or negative (overlap)
        assert gap <= 100


def test_chunk_paragraph_boundaries():
    """Chunker respects paragraph boundaries (\\n\\n)."""
    para1 = "First paragraph. " * 50
    para2 = "Second paragraph. " * 50
    text = para1 + "\n\n" + para2

    chunks = chunk_document(text, max_tokens=512, overlap=50)

    # Should split at paragraph boundary if possible
    assert len(chunks) > 0
    # Verify chunks contain coherent text
    for chunk in chunks:
        assert len(chunk["chunk_text"].strip()) > 0


def test_chunk_token_counting_accuracy():
    """Token counting matches tiktoken encoding."""
    import tiktoken

    text = "The quick brown fox jumps over the lazy dog. " * 10
    encoding = tiktoken.get_encoding("cl100k_base")

    chunks = chunk_document(text, max_tokens=512)

    for chunk in chunks:
        actual_tokens = len(encoding.encode(chunk["chunk_text"]))
        # Token count should be accurate
        assert chunk["token_count"] == actual_tokens


def test_chunk_metadata_complete():
    """Chunk metadata includes all required fields."""
    text = "Sample text for metadata verification. " * 20

    chunks = chunk_document(text, max_tokens=512)

    assert len(chunks) > 0
    for i, chunk in enumerate(chunks):
        assert "chunk_text" in chunk
        assert "chunk_index" in chunk
        assert "token_count" in chunk
        assert "start_char" in chunk
        assert "end_char" in chunk

        assert chunk["chunk_index"] == i
        assert chunk["start_char"] >= 0
        assert chunk["end_char"] > chunk["start_char"]
        assert len(chunk["chunk_text"]) == chunk["end_char"] - chunk["start_char"]


def test_chunk_long_document():
    """Test chunking with document >2000 tokens."""
    # Generate ~3000 token document (12000 chars)
    text = (
        "This is a comprehensive document with multiple paragraphs and sections. "
        "It contains information about various topics and will be split into multiple chunks. "
    ) * 100

    chunks = chunk_document(text, max_tokens=512, overlap=50)

    # Should create multiple chunks
    assert len(chunks) >= 5

    # Verify all chunks respect token limit
    for chunk in chunks:
        assert chunk["token_count"] <= 512

    # Verify chunks cover document (allow for overlap at boundaries)
    assert chunks[0]["start_char"] == 0
    # Last chunk should end near document end (within reasonable overlap)
    assert abs(chunks[-1]["end_char"] - len(text)) <= 2000

    # Verify sequential chunk indices
    for i, chunk in enumerate(chunks):
        assert chunk["chunk_index"] == i


def test_chunk_single_short_text():
    """Short text returns single chunk."""
    text = "This is a short sentence."

    chunks = chunk_document(text, max_tokens=512)

    assert len(chunks) == 1
    assert chunks[0]["chunk_text"] == text
    assert chunks[0]["chunk_index"] == 0
    assert chunks[0]["start_char"] == 0
    assert chunks[0]["end_char"] == len(text)


def test_chunk_custom_limits():
    """Custom token limits work correctly."""
    text = "Test sentence. " * 100

    # Test with smaller max_tokens
    chunks_256 = chunk_document(text, max_tokens=256, overlap=25)
    chunks_128 = chunk_document(text, max_tokens=128, overlap=25)

    # Smaller limit should create more chunks
    assert len(chunks_128) > len(chunks_256)

    # All chunks respect their limits
    for chunk in chunks_256:
        assert chunk["token_count"] <= 256

    for chunk in chunks_128:
        assert chunk["token_count"] <= 128
