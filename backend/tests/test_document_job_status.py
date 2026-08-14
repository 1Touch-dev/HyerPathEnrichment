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
import types
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.auth.models import User
from app.database.session import SyncSessionLocal
from app.database.session import engine as _async_engine
from app.modules.documents.models import CandidateDocument, DocumentJob
from app.workers.tasks.document import on_document_job_failure, process_document_job

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
        process_document_job(str(doc.id), b"%PDF-1.4 fake", "application/pdf", str(job.id))

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
        process_document_job(missing_document_id, b"%PDF-1.4 fake", "application/pdf", str(job.id))

    updated_job = _get_job(job.id)
    assert updated_job.status == "failed"
    assert updated_job.error is not None


def test_unclassified_exception_marks_document_job_failed():
    """Closes Gap 1: a plain RuntimeError (not DocumentProcessingError/ValueError)
    raised from processing must still mark DocumentJob/CandidateDocument as
    'failed' via the collapsed except Exception handler, not just the
    previously-special-cased exception types."""
    user = _create_user()
    doc = _create_document(user.id)
    job = _create_job(user.id, doc.id)

    mock_processor = MagicMock()
    mock_processor.process_document.side_effect = RuntimeError("boom")

    with (
        patch("app.workers.tasks.document.DocumentProcessor", return_value=mock_processor),
        patch("app.workers.queue.get_redis_connection"),
        patch("rq.Queue"),
        pytest.raises(RuntimeError, match="boom"),
    ):
        process_document_job(str(doc.id), b"%PDF-1.4 fake", "application/pdf", str(job.id))

    updated_job = _get_job(job.id)
    assert updated_job.status == "failed"
    assert updated_job.error is not None
    assert "boom" in updated_job.error

    updated_doc = _get_document(doc.id)
    assert updated_doc.processing_status == "failed"


def test_job_id_scoping_leaves_other_pending_job_for_same_document_untouched():
    """Closes Gap 3: when a document has two DocumentJob rows (mirroring the
    reprocess_document hazard of an extra pending job for a document already
    being processed by an original upload job), processing one job by its
    specific job_id must not flip the other job's status by matching on
    document_id + status=='pending'."""
    user = _create_user()
    doc = _create_document(user.id)
    first_job = _create_job(user.id, doc.id)
    second_job = _create_job(user.id, doc.id)

    mock_processor = MagicMock()
    mock_processor.process_document.return_value = dict(FAKE_EXTRACTION_RESULT)

    with (
        patch("app.workers.tasks.document.DocumentProcessor", return_value=mock_processor),
        patch("app.workers.queue.get_redis_connection"),
        patch("rq.Queue"),
    ):
        process_document_job(str(doc.id), b"%PDF-1.4 fake", "application/pdf", str(first_job.id))

    updated_first_job = _get_job(first_job.id)
    assert updated_first_job.status == "completed"

    updated_second_job = _get_job(second_job.id)
    assert updated_second_job.status == "pending"


def test_failure_callback_marks_pending_job_failed():
    """Closes Gap 2: on_document_job_failure (the RQ on_failure callback) must
    mark a still-'pending' DocumentJob/CandidateDocument as 'failed' when
    invoked for a worker crash/timeout where no Python except in the task body
    ever ran."""
    user = _create_user()
    doc = _create_document(user.id)
    job = _create_job(user.id, doc.id)

    fake_job = types.SimpleNamespace(
        args=(str(doc.id), b"%PDF-1.4 fake", "application/pdf", str(job.id))
    )

    on_document_job_failure(
        fake_job,
        connection=None,
        exc_type=RuntimeError,
        exc_value=RuntimeError("worker crashed"),
        exc_traceback=None,
    )

    updated_job = _get_job(job.id)
    assert updated_job.status == "failed"
    assert updated_job.error is not None

    updated_doc = _get_document(doc.id)
    assert updated_doc.processing_status == "failed"


def test_failure_callback_is_noop_on_already_terminal_job():
    """The on_document_job_failure callback must be idempotent: if the normal
    in-task exception handler already marked the job 'completed' (or 'failed')
    before RQ's worker-maintenance process invokes the callback, the callback
    must never clobber that terminal state."""
    user = _create_user()
    doc = _create_document(user.id, processing_status="completed")
    job = _create_job(user.id, doc.id, status="completed")

    fake_job = types.SimpleNamespace(
        args=(str(doc.id), b"%PDF-1.4 fake", "application/pdf", str(job.id))
    )

    on_document_job_failure(
        fake_job,
        connection=None,
        exc_type=RuntimeError,
        exc_value=RuntimeError("worker crashed"),
        exc_traceback=None,
    )

    updated_job = _get_job(job.id)
    assert updated_job.status == "completed"

    updated_doc = _get_document(doc.id)
    assert updated_doc.processing_status == "completed"
