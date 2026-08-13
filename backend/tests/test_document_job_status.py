"""Tests for app.workers.tasks.document (RQ worker entrypoint for CV/document processing).

Covers the DocumentJob.status transition bug found during the WSL-native live-test
against a real Postgres database: GET /api/documents/jobs/{job_id} reads
DocumentJob.status/progress, but process_document_job only ever updated
CandidateDocument.processing_status, so the polling endpoint showed "pending"
forever even after processing actually completed successfully.

Uses the same sync-entrypoint testing pattern as test_job_matching_worker.py:
process_document_job is a sync function that wraps asyncio.run(...), so tests
here are plain sync `def test_...` (no @pytest.mark.asyncio) and use
SyncSessionLocal to seed/inspect rows.
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.auth.models import User
from app.database.session import SyncSessionLocal
from app.database.session import engine as _async_engine
from app.modules.documents.models import CandidateDocument, DocumentJob
from app.workers.tasks.document import process_document_job

FAKE_EXTRACTION_RESULT = {
    "text": "Experienced backend engineer skilled in Python and SQL.",
    "token_count": 10,
    "page_count": 1,
    "metadata": {},
}


@pytest.fixture(autouse=True)
def _isolate_async_engine_per_test():
    """See test_job_matching_worker.py for why this is required: each
    asyncio.run(...) call in process_document_job gets its own event loop, and
    pooled DB connections must never cross loops."""
    asyncio.run(_async_engine.dispose())
    yield
    asyncio.run(_async_engine.dispose())


def _create_user(**overrides) -> User:
    with SyncSessionLocal() as session:
        fields = {
            "email": f"doc-worker-{uuid.uuid4().hex[:10]}@example.com",
            "first_name": "Doc",
            "last_name": "Candidate",
            "is_verified": True,
        }
        fields.update(overrides)
        user = User(**fields)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def _create_document(user_id, **overrides) -> CandidateDocument:
    with SyncSessionLocal() as session:
        fields = {
            "user_id": user_id,
            "document_type": "cv",
            "original_filename": "resume.pdf",
            "storage_path": f"/tmp/{uuid.uuid4().hex}.pdf",
            "file_hash": uuid.uuid4().hex,
            "file_size_bytes": 2048,
            "processing_status": "pending",
        }
        fields.update(overrides)
        doc = CandidateDocument(**fields)
        session.add(doc)
        session.commit()
        session.refresh(doc)
        return doc


def _create_job(user_id, document_id, **overrides) -> DocumentJob:
    with SyncSessionLocal() as session:
        fields = {
            "user_id": user_id,
            "document_id": document_id,
            "job_type": "upload",
            "status": "pending",
            "progress": 0.0,
        }
        fields.update(overrides)
        job = DocumentJob(**fields)
        session.add(job)
        session.commit()
        session.refresh(job)
        return job


def _get_job(job_id) -> DocumentJob:
    with SyncSessionLocal() as session:
        return session.get(DocumentJob, job_id)


def _get_document(document_id) -> CandidateDocument:
    with SyncSessionLocal() as session:
        return session.get(CandidateDocument, document_id)


def test_successful_processing_marks_document_job_completed():
    """Regression test: DocumentJob.status must reach 'completed' (not stay
    'pending') once process_document_job finishes successfully, since
    GET /api/documents/jobs/{job_id} reads DocumentJob.status, not
    CandidateDocument.processing_status."""
    user = _create_user()
    doc = _create_document(user.id)
    job = _create_job(user.id, doc.id)

    mock_processor = MagicMock()
    mock_processor.process_document.return_value = dict(FAKE_EXTRACTION_RESULT)

    with (
        patch("app.workers.tasks.document.DocumentProcessor", return_value=mock_processor),
        patch("app.workers.queue.get_redis_connection"),
        patch("rq.Queue"),
    ):
        process_document_job(str(doc.id), b"%PDF-1.4 fake", "application/pdf")

    updated_job = _get_job(job.id)
    assert updated_job.status == "completed"
    assert updated_job.progress == 1.0  # fraction (0.0-1.0), not a percentage

    updated_doc = _get_document(doc.id)
    assert updated_doc.processing_status == "completed"


def test_failed_processing_marks_document_job_failed():
    """When document processing raises, DocumentJob.status must transition to
    'failed' (not stay 'pending' forever) so pollers see a terminal state."""
    user = _create_user()
    # No underlying CandidateDocument row with this ID -> the worker's own
    # "not found in database" ValueError path, one of the two DB-write branches
    # this task can take.
    missing_document_id = str(uuid.uuid4())
    job = _create_job(user.id, uuid.UUID(missing_document_id))

    with pytest.raises(ValueError, match="not found in database"):
        process_document_job(missing_document_id, b"%PDF-1.4 fake", "application/pdf")

    updated_job = _get_job(job.id)
    assert updated_job.status == "failed"
    assert updated_job.error is not None
