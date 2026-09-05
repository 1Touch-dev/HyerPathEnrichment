"""Integration tests for Foundation Week 1 - Document Processing Pipeline.

Tests the complete flow:
1. Upload CV (PDF/DOCX)
2. Parse document text
3. Chunk text semantically
4. Generate embeddings
5. Store in pgvector
6. Vector similarity search
7. CV data extraction

These tests require:
- Postgres with pgvector extension
- Redis (for RQ)
- OpenAI API key
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.config import get_settings
from app.database.session import get_db_session
from app.main import app
from tests.migration_helpers import postgres_test_url

# These tests exercise the full document pipeline (Postgres+pgvector for vector
# search, a real OpenAI API key for embeddings, and a worker consuming jobs) and
# cannot produce meaningful results against the default SQLite/FakeRedis test
# setup used for the rest of the suite.
pytestmark = pytest.mark.skipif(
    not postgres_test_url(),
    reason="requires TEST_DATABASE_URL (Postgres+pgvector) and a real OpenAI API key",
)

# Test fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_CV_PDF = FIXTURES_DIR / "sample_cv.pdf"
SAMPLE_CV_DOCX = FIXTURES_DIR / "sample_cv.docx"
SAMPLE_CV_MINIMAL = FIXTURES_DIR / "sample_cv_minimal.pdf"


def unwrap_envelope(response):
    """Extract data from API envelope format.

    The API wraps responses in: {'success': True, 'data': {...}, 'message': None, 'meta': None}
    This helper extracts just the 'data' portion for easier testing.
    """
    body = response.json()
    if "data" in body and body.get("success"):
        return body["data"]
    return body


@pytest.fixture
def test_user_id():
    """Generate a test user ID."""
    return uuid4()


@pytest.fixture
def auth_headers(test_user_id):
    """Generate auth headers for test user."""
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.api_token}",
        "X-Test-User-ID": str(test_user_id),
    }


class TestDocumentUploadFlow:
    """Test document upload and parsing."""

    @pytest.mark.asyncio
    async def test_upload_pdf_complete_flow(self, auth_headers, test_user_id):
        """Test uploading a complete PDF CV through the API."""
        if not SAMPLE_CV_PDF.exists():
            pytest.skip("Test fixture not found. Run: python tests/fixtures/generate_test_cvs.py")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Upload document
            with open(SAMPLE_CV_PDF, "rb") as f:
                response = await client.post(
                    "/api/documents/upload",
                    files={"file": ("sample_cv.pdf", f, "application/pdf")},
                    headers=auth_headers,
                )

            if response.status_code != 200:
                print(f"ERROR: Status {response.status_code}")
                print(f"Response body: {response.text}")
            assert response.status_code == 200
            data = unwrap_envelope(response)
            assert "job_id" in data
            job_id = data["job_id"]

            # Poll job status (wait up to 30 seconds)
            for _ in range(30):
                response = await client.get(
                    f"/api/documents/jobs/{job_id}",
                    headers=auth_headers,
                )
                assert response.status_code == 200
                job_data = unwrap_envelope(response)

                if job_data["status"] in ["completed", "failed"]:
                    break

                await asyncio.sleep(1)

            # Verify job completed successfully
            assert job_data["status"] == "completed"
            assert "document_id" in job_data
            document_id = job_data["document_id"]

            # Get document details
            response = await client.get(
                f"/api/documents/{document_id}",
                headers=auth_headers,
            )
            assert response.status_code == 200
            doc = unwrap_envelope(response)

            # Verify document metadata
            assert doc["document_type"] == "pdf"
            assert doc["processing_status"] == "completed"
            assert doc["raw_text"] is not None
        assert len(doc["raw_text"]) > 100  # Should have extracted text

    @pytest.mark.asyncio
    async def test_upload_docx_complete_flow(self, auth_headers):
        """Test uploading a DOCX CV."""
        if not SAMPLE_CV_DOCX.exists():
            pytest.skip("Test fixture not found")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            with open(SAMPLE_CV_DOCX, "rb") as f:
                response = await client.post(
                    "/api/documents/upload",
                    files={
                        "file": (
                            "sample_cv.docx",
                            f,
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        )
                    },
                    headers=auth_headers,
                )

            assert response.status_code == 200
            data = unwrap_envelope(response)
            assert "job_id" in data

    @pytest.mark.asyncio
    async def test_duplicate_upload_detected(self, auth_headers):
        """Test that duplicate files are detected via SHA256 hash."""
        if not SAMPLE_CV_PDF.exists():
            pytest.skip("Test fixture not found")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Upload first time
            with open(SAMPLE_CV_PDF, "rb") as f:
                response1 = await client.post(
                    "/api/documents/upload",
                    files={"file": ("cv1.pdf", f, "application/pdf")},
                    headers=auth_headers,
                )
            assert response1.status_code == 200
            _job_id_1 = unwrap_envelope(response1)["job_id"]

            # Wait for processing
            await asyncio.sleep(5)

            # Upload same file again
            with open(SAMPLE_CV_PDF, "rb") as f:
                response2 = await client.post(
                    "/api/documents/upload",
                    files={"file": ("cv2.pdf", f, "application/pdf")},
                    headers=auth_headers,
                )

            # Should either reject or return existing document
            assert response2.status_code in [200, 409]  # 409 = Conflict (duplicate)


class TestEmbeddingGeneration:
    """Test embedding generation and vector storage."""

    @pytest.mark.asyncio
    async def test_embeddings_generated_after_upload(self, auth_headers):
        """Test that embeddings are automatically generated after document processing."""
        if not SAMPLE_CV_PDF.exists():
            pytest.skip("Test fixture not found")

        settings = get_settings()
        if not settings.enable_embeddings:
            pytest.skip("Embeddings disabled")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Upload document
            with open(SAMPLE_CV_PDF, "rb") as f:
                response = await client.post(
                    "/api/documents/upload",
                    files={"file": ("cv.pdf", f, "application/pdf")},
                    headers=auth_headers,
                )

            _job_id = unwrap_envelope(response)["job_id"]

            # Wait for full pipeline (parsing + embedding)
            await asyncio.sleep(15)

            # Check that embeddings exist in database
            async for db in get_db_session():
                embeddings = await db.execute(
                    text(
                        "SELECT COUNT(*) FROM document_embeddings WHERE document_id IN "
                        "(SELECT id FROM candidate_documents WHERE user_id = :user_id)"
                    ),
                    {"user_id": auth_headers["X-Test-User-ID"]},
                )
                count = embeddings.scalar()
                assert count > 0, "No embeddings found after processing"


class TestVectorSearch:
    """Test semantic similarity search."""

    @pytest.mark.asyncio
    async def test_semantic_search(self, auth_headers):
        """Test vector similarity search across documents."""
        settings = get_settings()
        if not settings.enable_embeddings:
            pytest.skip("Embeddings disabled")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Search for backend engineers
            response = await client.post(
                "/api/documents/search",
                json={"query": "Senior Python Backend Engineer with API experience", "limit": 10},
                headers=auth_headers,
            )

        assert response.status_code == 200
        results = unwrap_envelope(response)
        assert "results" in results
        assert isinstance(results["results"], list)

        # If documents exist, should return similarity scores
        if results["results"]:
            for result in results["results"]:
                assert "document_id" in result
                assert "similarity_score" in result
                assert 0.0 <= result["similarity_score"] <= 1.0

    @pytest.mark.asyncio
    async def test_search_relevance(self, auth_headers):
        """Test that search results are ranked by relevance."""
        settings = get_settings()
        if not settings.enable_embeddings:
            pytest.skip("Embeddings disabled")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/documents/search",
                json={"query": "machine learning engineer", "limit": 5},
                headers=auth_headers,
            )

            results = response.json()["results"]
            if len(results) >= 2:
                # Scores should be in descending order
                scores = [r["similarity_score"] for r in results]
                assert scores == sorted(scores, reverse=True)


class TestCVExtraction:
    """Test structured CV data extraction."""

    @pytest.mark.asyncio
    async def test_cv_data_extraction(self, auth_headers):
        """Test that CV data is extracted into structured format."""
        if not SAMPLE_CV_PDF.exists():
            pytest.skip("Test fixture not found")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Upload document
            with open(SAMPLE_CV_PDF, "rb") as f:
                response = await client.post(
                    "/api/documents/upload",
                    files={"file": ("cv.pdf", f, "application/pdf")},
                    headers=auth_headers,
                )

            job_id = unwrap_envelope(response)["job_id"]

            # Wait for full pipeline
            await asyncio.sleep(20)

            # Get job status to find document_id
            response = await client.get(
                f"/api/documents/jobs/{job_id}",
                headers=auth_headers,
            )
            document_id = unwrap_envelope(response)["document_id"]

            # Get extracted CV data
            response = await client.get(
                f"/api/documents/{document_id}/cv-data",
                headers=auth_headers,
            )

            assert response.status_code == 200
            cv_data = unwrap_envelope(response)

            # Verify structured fields
            assert "personal_info" in cv_data or "name" in cv_data
            assert "experience" in cv_data or "work_history" in cv_data
            assert "skills" in cv_data

    @pytest.mark.asyncio
    async def test_cv_completeness_score(self, auth_headers):
        """Test that completeness score is calculated."""
        if not SAMPLE_CV_MINIMAL.exists():
            pytest.skip("Test fixture not found")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Upload minimal CV
            with open(SAMPLE_CV_MINIMAL, "rb") as f:
                response = await client.post(
                    "/api/documents/upload",
                    files={"file": ("minimal.pdf", f, "application/pdf")},
                    headers=auth_headers,
                )

            job_id = unwrap_envelope(response)["job_id"]
            await asyncio.sleep(20)

            # Get CV data
            response = await client.get(
                f"/api/documents/jobs/{job_id}",
                headers=auth_headers,
            )
            document_id = unwrap_envelope(response)["document_id"]

            response = await client.get(
                f"/api/documents/{document_id}/cv-data",
                headers=auth_headers,
            )

            cv_data = unwrap_envelope(response)

            # Minimal CV should have lower completeness
            if "completeness_score" in cv_data:
                assert cv_data["completeness_score"] < 0.8


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_malformed_pdf_rejected(self, auth_headers):
        """Test that corrupted PDFs are rejected gracefully."""
        malformed_path = FIXTURES_DIR / "malformed.pdf"
        if not malformed_path.exists():
            pytest.skip("Test fixture not found")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            with open(malformed_path, "rb") as f:
                response = await client.post(
                    "/api/documents/upload",
                    files={"file": ("bad.pdf", f, "application/pdf")},
                    headers=auth_headers,
                )

            # Should either reject upfront or fail gracefully
            if response.status_code == 200:
                job_id = unwrap_envelope(response)["job_id"]
                await asyncio.sleep(5)

                # Check job failed
                response = await client.get(
                    f"/api/documents/jobs/{job_id}",
                    headers=auth_headers,
                )
                job_data = unwrap_envelope(response)
                assert job_data["status"] == "failed"

    @pytest.mark.asyncio
    async def test_file_too_large_rejected(self, auth_headers):
        """Test that files over 10MB are rejected."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Create 11MB of fake data
            large_file = b"x" * (11 * 1024 * 1024)

            response = await client.post(
                "/api/documents/upload",
                files={"file": ("large.pdf", large_file, "application/pdf")},
                headers=auth_headers,
            )

            assert response.status_code == 413  # Payload too large

    @pytest.mark.asyncio
    async def test_invalid_file_type_rejected(self, auth_headers):
        """Test that non-PDF/DOCX files are rejected."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/documents/upload",
                files={"file": ("script.exe", b"fake exe", "application/x-msdownload")},
                headers=auth_headers,
            )

            assert response.status_code == 400  # Bad request


class TestCostMonitoring:
    """Test cost tracking for embeddings and LLM usage."""

    @pytest.mark.asyncio
    async def test_cost_tracking_enabled(self):
        """Test that cost tracking metrics are being recorded."""
        from app.observability.cost_tracking import get_daily_cost

        # Should return cost data without errors
        cost_data = await get_daily_cost()
        assert isinstance(cost_data, dict)
        assert "embeddings" in cost_data or "total" in cost_data


class TestFullPipeline:
    """End-to-end pipeline tests."""

    @pytest.mark.asyncio
    async def test_complete_pipeline_e2e(self, auth_headers):
        """Test complete flow: Upload → Parse → Chunk → Embed → Search.

        This is the acceptance test for Foundation Week 1.
        """
        if not SAMPLE_CV_PDF.exists():
            pytest.skip("Test fixture not found")

        settings = get_settings()
        if not settings.enable_embeddings:
            pytest.skip("Embeddings disabled")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Step 1: Upload CV
            with open(SAMPLE_CV_PDF, "rb") as f:
                response = await client.post(
                    "/api/documents/upload",
                    files={"file": ("john_doe_cv.pdf", f, "application/pdf")},
                    headers=auth_headers,
                )

            assert response.status_code == 200
            job_id = unwrap_envelope(response)["job_id"]

            # Step 2: Wait for processing (parsing + chunking + embedding + extraction)
            max_wait = 60  # 60 seconds max
            for _ in range(max_wait):
                response = await client.get(
                    f"/api/documents/jobs/{job_id}",
                    headers=auth_headers,
                )
                job_data = unwrap_envelope(response)

                if job_data["status"] == "completed":
                    break
                elif job_data["status"] == "failed":
                    pytest.fail(f"Job failed: {job_data.get('error')}")

                await asyncio.sleep(1)

            assert job_data["status"] == "completed"
            document_id = job_data["document_id"]

            # Step 3: Verify document exists with parsed text
            response = await client.get(
                f"/api/documents/{document_id}",
                headers=auth_headers,
            )
            doc = unwrap_envelope(response)
            assert doc["raw_text"] is not None
            assert "john" in doc["raw_text"].lower()

            # Step 4: Verify embeddings generated
            async for db in get_db_session():
                from sqlalchemy import text

                result = await db.execute(
                    text("SELECT COUNT(*) FROM document_embeddings WHERE document_id = :doc_id"),
                    {"doc_id": document_id},
                )
                embedding_count = result.scalar()
                assert embedding_count > 0, "No embeddings generated"

            # Step 5: Search for similar documents
            response = await client.post(
                "/api/documents/search",
                json={"query": "Senior Backend Engineer Python FastAPI", "limit": 5},
                headers=auth_headers,
            )
            results = unwrap_envelope(response)["results"]

            # Should find the uploaded document
            doc_ids = [r["document_id"] for r in results]
            assert str(document_id) in doc_ids, "Uploaded document not found in search"

            # Step 6: Verify CV data extracted
            response = await client.get(
                f"/api/documents/{document_id}/cv-data",
                headers=auth_headers,
            )
            cv_data = unwrap_envelope(response)
            assert cv_data is not None

            print("\n✅ Full pipeline test PASSED!")
            print(f"   - Document uploaded: {document_id}")
            print(f"   - Embeddings generated: {embedding_count}")
            print(f"   - Search results: {len(results)}")
