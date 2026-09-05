"""Tests for ephemeral, on-demand resume tailoring (machine-2 track 10).

OpenAI/Perplexity are mocked at the worker-test level (test_resume_tailoring_
worker.py); these tests cover the service layer's enqueue/poll contract and
the release-blocking "genuinely ephemeral, never persisted" invariant.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import inspect

from app.auth.models import User
from app.modules.documents.models import CandidateDocument
from app.modules.resume_tailoring.schemas import TailorResumeRequest
from app.modules.resume_tailoring.service import get_tailoring_result, request_tailoring


@pytest.fixture
async def test_user(db):
    user = User(
        id=uuid4(),
        email=f"resume-tailoring-{uuid4().hex[:8]}@example.com",
        first_name="Jane",
        last_name="User",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def completed_document(db, test_user):
    doc = CandidateDocument(
        id=uuid4(),
        user_id=test_user.id,
        document_type="cv",
        original_filename="cv.pdf",
        storage_path="documents/x/y.pdf",
        file_hash=f"resume-tailoring-{uuid4().hex}",
        file_size_bytes=1000,
        raw_text="Jane Doe",
        extracted_data={"current_role": "Backend Engineer", "technical_skills": ["python"]},
        processing_status="completed",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def test_request_tailoring_enqueues_job_for_completed_document(
    db, test_user, completed_document
):
    mock_queue_cls = MagicMock()
    mock_queue_instance = MagicMock()
    mock_queue_instance.enqueue.return_value = MagicMock(id="rq-job-123")
    mock_queue_cls.return_value = mock_queue_instance

    with patch("app.modules.resume_tailoring.service.Queue", mock_queue_cls):
        result = await request_tailoring(
            db,
            user_id=test_user.id,
            body=TailorResumeRequest(document_id=str(completed_document.id), target_company="Acme"),
            redis_conn=MagicMock(),
        )

    assert result.rq_job_id == "rq-job-123"
    mock_queue_instance.enqueue.assert_called_once()
    call_args = mock_queue_instance.enqueue.call_args
    assert call_args.kwargs["result_ttl"] == 1800


async def test_request_tailoring_requires_a_processed_cv(db, test_user):
    with pytest.raises(HTTPException) as exc_info:
        await request_tailoring(
            db,
            user_id=test_user.id,
            body=TailorResumeRequest(document_id=str(uuid4()), target_company="Acme"),
            redis_conn=MagicMock(),
        )
    assert exc_info.value.status_code == 409


async def test_request_tailoring_rejects_document_not_owned_by_caller(db, test_user):
    other_user_id = uuid4()
    doc = CandidateDocument(
        id=uuid4(),
        user_id=other_user_id,
        document_type="cv",
        original_filename="cv.pdf",
        storage_path="documents/x/y.pdf",
        file_hash=f"resume-tailoring-{uuid4().hex}",
        file_size_bytes=1000,
        processing_status="completed",
    )
    db.add(doc)
    await db.commit()

    with pytest.raises(HTTPException) as exc_info:
        await request_tailoring(
            db,
            user_id=test_user.id,
            body=TailorResumeRequest(document_id=str(doc.id), target_company="Acme"),
            redis_conn=MagicMock(),
        )
    assert exc_info.value.status_code == 409


async def test_request_tailoring_rejects_incomplete_document(db, test_user):
    doc = CandidateDocument(
        id=uuid4(),
        user_id=test_user.id,
        document_type="cv",
        original_filename="cv.pdf",
        storage_path="documents/x/y.pdf",
        file_hash=f"resume-tailoring-{uuid4().hex}",
        file_size_bytes=1000,
        processing_status="processing",
    )
    db.add(doc)
    await db.commit()

    with pytest.raises(HTTPException) as exc_info:
        await request_tailoring(
            db,
            user_id=test_user.id,
            body=TailorResumeRequest(document_id=str(doc.id), target_company="Acme"),
            redis_conn=MagicMock(),
        )
    assert exc_info.value.status_code == 409


def test_get_tailoring_result_returns_not_found_for_missing_job():
    mock_queue_cls = MagicMock()
    mock_queue_instance = MagicMock()
    mock_queue_instance.fetch_job.return_value = None
    mock_queue_cls.return_value = mock_queue_instance

    with patch("app.modules.resume_tailoring.service.Queue", mock_queue_cls):
        result = get_tailoring_result("expired-job-id", MagicMock())

    assert result.status == "not_found"


def test_get_tailoring_result_returns_queued_status_without_content():
    mock_job = MagicMock()
    mock_job.get_status.return_value = "queued"
    mock_queue_cls = MagicMock()
    mock_queue_instance = MagicMock()
    mock_queue_instance.fetch_job.return_value = mock_job
    mock_queue_cls.return_value = mock_queue_instance

    with patch("app.modules.resume_tailoring.service.Queue", mock_queue_cls):
        result = get_tailoring_result("job-id", MagicMock())

    assert result.status == "queued"
    assert result.summary is None


def test_get_tailoring_result_returns_finished_status_with_content():
    mock_job = MagicMock()
    mock_job.get_status.return_value = "finished"
    mock_job.result = {
        "summary": "Tailored summary",
        "emphasized_skills": ["python", "sql"],
        "reordered_bullets": ["Did a thing"],
        "research_degraded": False,
    }
    mock_queue_cls = MagicMock()
    mock_queue_instance = MagicMock()
    mock_queue_instance.fetch_job.return_value = mock_job
    mock_queue_cls.return_value = mock_queue_instance

    with patch("app.modules.resume_tailoring.service.Queue", mock_queue_cls):
        result = get_tailoring_result("job-id", MagicMock())

    assert result.status == "finished"
    assert result.summary == "Tailored summary"
    assert result.emphasized_skills == ["python", "sql"]
    assert result.reordered_bullets == ["Did a thing"]
    assert result.research_degraded is False


async def _table_names(engine) -> set[str]:
    async with engine.connect() as conn:
        return await conn.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))


async def test_no_persistence_regression_full_cycle_writes_no_new_row_or_table(
    db, test_user, completed_document, db_engine
):
    """Release-blocking regression test: after a full request_tailoring -> job
    execution -> get_tailoring_result cycle, no new table exists anywhere in
    the schema, and the source CandidateDocument row is completely unchanged
    (this feature never mutates or persists anything besides RQ's own
    TTL-bound result store)."""
    before_updated_at = completed_document.updated_at
    before_extracted_data = dict(completed_document.extracted_data or {})

    tables_before = await _table_names(db_engine)

    mock_queue_cls = MagicMock()
    mock_queue_instance = MagicMock()
    mock_queue_instance.enqueue.return_value = MagicMock(id="rq-job-ephemeral")
    mock_queue_cls.return_value = mock_queue_instance

    with patch("app.modules.resume_tailoring.service.Queue", mock_queue_cls):
        enqueue_result = await request_tailoring(
            db,
            user_id=test_user.id,
            body=TailorResumeRequest(document_id=str(completed_document.id), target_company="Acme"),
            redis_conn=MagicMock(),
        )

    # Simulate the worker having executed the job and RQ storing its result.
    mock_job = MagicMock()
    mock_job.get_status.return_value = "finished"
    mock_job.result = {
        "summary": "Tailored summary",
        "emphasized_skills": ["python"],
        "reordered_bullets": [],
        "research_degraded": True,
    }
    mock_fetch_queue_cls = MagicMock()
    mock_fetch_queue_instance = MagicMock()
    mock_fetch_queue_instance.fetch_job.return_value = mock_job
    mock_fetch_queue_cls.return_value = mock_fetch_queue_instance

    with patch("app.modules.resume_tailoring.service.Queue", mock_fetch_queue_cls):
        result = get_tailoring_result(enqueue_result.rq_job_id, MagicMock())

    assert result.status == "finished"
    assert result.summary == "Tailored summary"

    tables_after = await _table_names(db_engine)
    assert tables_after == tables_before
    assert not any("tailor" in t.lower() for t in tables_after)

    await db.refresh(completed_document)
    assert completed_document.updated_at == before_updated_at
    assert dict(completed_document.extracted_data or {}) == before_extracted_data
