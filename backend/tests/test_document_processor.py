"""Unit tests for document processing service.

Tests PDF/DOCX parsing, file validation, security checks, and deduplication.
"""

from __future__ import annotations


import pytest

from app.services.document_processor import DocumentProcessor, DocumentProcessingError
from app.storage.document_storage import (
    DocumentStorageClient,
    DocumentStorageError,
    MAX_FILE_SIZE_BYTES,
    compute_file_hash,
    validate_file_size,
    validate_mime_type,
)


@pytest.fixture
def processor() -> DocumentProcessor:
    """Create document processor instance."""
    return DocumentProcessor()


@pytest.fixture
def storage_client() -> DocumentStorageClient:
    """Create document storage client instance."""
    return DocumentStorageClient()


@pytest.fixture
def sample_pdf_data() -> bytes:
    """Create minimal valid PDF data for testing."""
    # Minimal PDF structure
    pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/Resources <<
/Font <<
/F1 <<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
>>
>>
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF Content) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000317 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
410
%%EOF
"""
    return pdf_content


@pytest.fixture
def sample_docx_data() -> bytes:
    """Create minimal valid DOCX data for testing."""
    try:
        import docx
        from io import BytesIO

        doc = docx.Document()
        doc.add_paragraph("Test DOCX Content")
        doc.add_paragraph("This is a sample resume.")

        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer.read()
    except ImportError:
        pytest.skip("python-docx not installed")


# ── Document Processing Tests ──────────────────────────────────────


def test_extract_pdf_text(processor: DocumentProcessor, sample_pdf_data: bytes) -> None:
    """Test PDF text extraction with valid file."""
    result = processor.extract_pdf_text(sample_pdf_data)

    assert "text" in result
    assert "Test PDF Content" in result["text"]
    assert result["page_count"] == 1
    assert result["token_count"] > 0
    assert "metadata" in result


def test_extract_pdf_text_corrupted_file(processor: DocumentProcessor) -> None:
    """Test PDF extraction fails with corrupted file."""
    corrupted_pdf = b"Not a PDF file"

    with pytest.raises(DocumentProcessingError, match="Failed to process PDF"):
        processor.extract_pdf_text(corrupted_pdf)


def test_extract_pdf_text_empty_file(processor: DocumentProcessor) -> None:
    """Test PDF extraction fails with empty file."""
    empty_pdf = b""

    with pytest.raises(DocumentProcessingError):
        processor.extract_pdf_text(empty_pdf)


def test_extract_docx_text(processor: DocumentProcessor, sample_docx_data: bytes) -> None:
    """Test DOCX text extraction with valid file."""
    result = processor.extract_docx_text(sample_docx_data)

    assert "text" in result
    assert "Test DOCX Content" in result["text"]
    assert "sample resume" in result["text"]
    assert result["paragraph_count"] >= 2
    assert result["token_count"] > 0
    assert "metadata" in result


def test_extract_docx_text_corrupted_file(processor: DocumentProcessor) -> None:
    """Test DOCX extraction fails with corrupted file."""
    corrupted_docx = b"Not a DOCX file"

    with pytest.raises(DocumentProcessingError, match="Failed to process DOCX"):
        processor.extract_docx_text(corrupted_docx)


def test_process_document_pdf(processor: DocumentProcessor, sample_pdf_data: bytes) -> None:
    """Test document processing routes to PDF handler."""
    result = processor.process_document(sample_pdf_data, "application/pdf")

    assert "text" in result
    assert "page_count" in result


def test_process_document_docx(processor: DocumentProcessor, sample_docx_data: bytes) -> None:
    """Test document processing routes to DOCX handler."""
    result = processor.process_document(
        sample_docx_data,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    assert "text" in result
    assert "paragraph_count" in result


def test_process_document_unsupported_type(processor: DocumentProcessor) -> None:
    """Test document processing fails with unsupported MIME type."""
    with pytest.raises(DocumentProcessingError, match="Unsupported MIME type"):
        processor.process_document(b"test", "application/unknown")


# ── Storage Validation Tests ───────────────────────────────────────


def test_validate_file_size_valid() -> None:
    """Test file size validation passes for valid size."""
    validate_file_size(1024)  # 1KB
    validate_file_size(MAX_FILE_SIZE_BYTES)  # Max size
    # Should not raise


def test_validate_file_size_exceeds_limit() -> None:
    """Test file size validation fails for oversized file."""
    with pytest.raises(DocumentStorageError, match="exceeds maximum"):
        validate_file_size(MAX_FILE_SIZE_BYTES + 1)


def test_validate_mime_type_pdf() -> None:
    """Test MIME type validation for PDF."""
    ext = validate_mime_type("application/pdf")
    assert ext == "pdf"


def test_validate_mime_type_docx() -> None:
    """Test MIME type validation for DOCX."""
    ext = validate_mime_type(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert ext == "docx"


def test_validate_mime_type_with_charset() -> None:
    """Test MIME type validation strips charset."""
    ext = validate_mime_type("application/pdf; charset=utf-8")
    assert ext == "pdf"


def test_validate_mime_type_unsupported() -> None:
    """Test MIME type validation fails for unsupported type."""
    with pytest.raises(DocumentStorageError, match="Unsupported file type"):
        validate_mime_type("application/x-msword")  # Old .doc format


def test_compute_file_hash() -> None:
    """Test file hash computation for deduplication."""
    data1 = b"test document content"
    data2 = b"test document content"
    data3 = b"different content"

    hash1 = compute_file_hash(data1)
    hash2 = compute_file_hash(data2)
    hash3 = compute_file_hash(data3)

    # Same content produces same hash
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 hex length

    # Different content produces different hash
    assert hash1 != hash3


# ── Storage Upload Tests ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_document_valid_pdf(
    storage_client: DocumentStorageClient,
    sample_pdf_data: bytes,
) -> None:
    """Test document upload with valid PDF."""
    storage_path, file_hash, file_size = await storage_client.upload_document(
        sample_pdf_data,
        "resume.pdf",
        "application/pdf",
        "user-123",
        "cv",
    )

    assert storage_path.startswith("documents/user-123/cv/")
    assert storage_path.endswith(".pdf")
    assert len(file_hash) == 64
    assert file_size == len(sample_pdf_data)


@pytest.mark.asyncio
async def test_upload_document_valid_docx(
    storage_client: DocumentStorageClient,
    sample_docx_data: bytes,
) -> None:
    """Test document upload with valid DOCX."""
    storage_path, file_hash, file_size = await storage_client.upload_document(
        sample_docx_data,
        "resume.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "user-456",
        "cv",
    )

    assert storage_path.startswith("documents/user-456/cv/")
    assert storage_path.endswith(".docx")
    assert len(file_hash) == 64
    assert file_size == len(sample_docx_data)


@pytest.mark.asyncio
async def test_upload_document_exceeds_size_limit(
    storage_client: DocumentStorageClient,
) -> None:
    """Test document upload fails when file exceeds size limit."""
    oversized_data = b"x" * (MAX_FILE_SIZE_BYTES + 1)

    with pytest.raises(DocumentStorageError, match="exceeds maximum"):
        await storage_client.upload_document(
            oversized_data,
            "huge.pdf",
            "application/pdf",
            "user-789",
            "cv",
        )


@pytest.mark.asyncio
async def test_upload_document_unsupported_type(
    storage_client: DocumentStorageClient,
) -> None:
    """Test document upload fails with unsupported MIME type."""
    with pytest.raises(DocumentStorageError, match="Unsupported file type"):
        await storage_client.upload_document(
            b"test",
            "document.txt",
            "text/plain",
            "user-999",
            "cv",
        )


@pytest.mark.asyncio
async def test_upload_document_corrupted_file(
    storage_client: DocumentStorageClient,
) -> None:
    """Test document upload fails with corrupted/empty file."""
    tiny_file = b"x" * 50  # Less than 100 bytes

    with pytest.raises(DocumentStorageError, match="corrupted or empty"):
        await storage_client.upload_document(
            tiny_file,
            "corrupted.pdf",
            "application/pdf",
            "user-111",
            "cv",
        )


@pytest.mark.asyncio
async def test_duplicate_upload_different_hash(
    storage_client: DocumentStorageClient,
    sample_pdf_data: bytes,
) -> None:
    """Test uploading same file produces same hash (for deduplication)."""
    # Upload same file twice
    path1, hash1, size1 = await storage_client.upload_document(
        sample_pdf_data,
        "resume1.pdf",
        "application/pdf",
        "user-222",
        "cv",
    )

    path2, hash2, size2 = await storage_client.upload_document(
        sample_pdf_data,
        "resume2.pdf",
        "application/pdf",
        "user-222",
        "cv",
    )

    # Different storage paths (unique IDs)
    assert path1 != path2

    # But same file hash (for deduplication detection)
    assert hash1 == hash2
    assert size1 == size2


# ── Coverage Summary ───────────────────────────────────────────────
# This test suite covers:
# - PDF parsing (valid, corrupted, empty)
# - DOCX parsing (valid, corrupted)
# - File validation (size, MIME type, corrupted)
# - Security checks (size limits, type validation)
# - Deduplication (file hashing)
# - Storage operations (upload, path generation)
# - Error handling for all failure modes
#
# Expected coverage: >80% for:
# - app/services/document_processor.py
# - app/storage/document_storage.py
