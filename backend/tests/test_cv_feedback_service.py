"""Direct service-layer unit tests for DocumentService's Module 2 methods:
get_completeness, request_cv_feedback, get_latest_cv_feedback, accept_cv_feedback_bullet.

Router-level coverage for these already exists in tests/test_module2_api.py; this file
exercises DocumentService directly (mocked Redis/Queue, real SQLite test DB), following the
direct-service-unit-test pattern established in tests/test_portfolio.py and tests/test_outreach.py.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.auth.models import User
from app.modules.documents.models import (
    CandidateDocument,
    CvChatSession,
    CvFeedbackReport,
    DocumentJob,
)
from app.modules.documents.service import DocumentService


@pytest.fixture
async def test_user(db):
    user = User(
        id=uuid4(),
        email=f"cv-feedback-{uuid4().hex[:8]}@example.com",
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
        file_hash=f"cv-feedback-{uuid4().hex}",
        file_size_bytes=1000,
        raw_text="Jane Doe, Backend Engineer",
        extracted_data={"email": "jane@example.com", "technical_skills": ["python"]},
        processing_status="completed",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


@pytest.fixture
async def pending_document(db, test_user):
    doc = CandidateDocument(
        id=uuid4(),
        user_id=test_user.id,
        document_type="cv",
        original_filename="cv.pdf",
        storage_path="documents/x/y2.pdf",
        file_hash=f"cv-feedback-pending-{uuid4().hex}",
        file_size_bytes=1000,
        processing_status="pending",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


def _service(db) -> DocumentService:
    return DocumentService(db, redis_conn=MagicMock())


# ---------------------------------------------------------------------------
# get_completeness
# ---------------------------------------------------------------------------


async def test_get_completeness_no_active_session_reports_missing_fields(
    db, test_user, completed_document
):
    service = _service(db)
    result = await service.get_completeness(str(completed_document.id), test_user.id)

    assert result.document_id == str(completed_document.id)
    assert result.has_active_chat_session is False
    # extracted_data only sets email + technical_skills, so the other REQUIRED_FIELDS are missing
    assert "email" not in result.missing_fields
    assert "technical_skills" not in result.missing_fields
    assert "phone" in result.missing_fields
    assert 0.0 < result.completeness_score < 1.0


async def test_get_completeness_reports_active_chat_session(db, test_user, completed_document):
    session = CvChatSession(
        id=uuid4(),
        user_id=test_user.id,
        document_id=completed_document.id,
        status="active",
    )
    db.add(session)
    await db.commit()

    service = _service(db)
    result = await service.get_completeness(str(completed_document.id), test_user.id)
    assert result.has_active_chat_session is True


async def test_get_completeness_ignores_completed_chat_session(db, test_user, completed_document):
    session = CvChatSession(
        id=uuid4(),
        user_id=test_user.id,
        document_id=completed_document.id,
        status="completed",
    )
    db.add(session)
    await db.commit()

    service = _service(db)
    result = await service.get_completeness(str(completed_document.id), test_user.id)
    assert result.has_active_chat_session is False


async def test_get_completeness_with_no_extracted_data_reports_all_fields_missing(db, test_user):
    doc = CandidateDocument(
        id=uuid4(),
        user_id=test_user.id,
        document_type="cv",
        original_filename="cv.pdf",
        storage_path="documents/x/z.pdf",
        file_hash=f"cv-feedback-empty-{uuid4().hex}",
        file_size_bytes=1000,
        processing_status="pending",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    service = _service(db)
    result = await service.get_completeness(str(doc.id), test_user.id)
    assert result.completeness_score == 0.0
    assert len(result.missing_fields) == 11


async def test_get_completeness_404_for_unowned_document(db, test_user, completed_document):
    service = _service(db)
    with pytest.raises(HTTPException) as exc_info:
        await service.get_completeness(str(completed_document.id), uuid4())
    assert exc_info.value.status_code == 404


async def test_get_completeness_404_for_unknown_document(db, test_user):
    service = _service(db)
    with pytest.raises(HTTPException) as exc_info:
        await service.get_completeness(str(uuid4()), test_user.id)
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# request_cv_feedback
# ---------------------------------------------------------------------------


async def test_request_cv_feedback_enqueues_job_for_completed_document(
    db, test_user, completed_document
):
    mock_queue_cls = MagicMock()
    mock_queue_instance = MagicMock()
    mock_queue_cls.return_value = mock_queue_instance

    service = _service(db)
    with patch("app.modules.documents.service.Queue", mock_queue_cls):
        result = await service.request_cv_feedback(
            str(completed_document.id), test_user.id, "Backend Engineer"
        )

    assert result.document_id == str(completed_document.id)
    assert result.message == "CV feedback generation started"
    mock_queue_instance.enqueue.assert_called_once()
    call_args = mock_queue_instance.enqueue.call_args
    assert call_args.args[0] == "app.workers.tasks.cv_improvement.generate_cv_improvement_job"
    assert call_args.args[1] == str(completed_document.id)
    assert call_args.args[3] == "Backend Engineer"

    job_result = await db.get(DocumentJob, UUID(result.job_id))
    assert job_result is not None
    assert job_result.status == "pending"
    assert job_result.job_type == "cv_feedback"


async def test_request_cv_feedback_rejects_document_not_yet_completed(
    db, test_user, pending_document
):
    service = _service(db)
    with pytest.raises(HTTPException) as exc_info:
        await service.request_cv_feedback(str(pending_document.id), test_user.id, None)
    assert exc_info.value.status_code == 409


async def test_request_cv_feedback_404_for_unowned_document(db, test_user, completed_document):
    service = _service(db)
    with pytest.raises(HTTPException) as exc_info:
        await service.request_cv_feedback(str(completed_document.id), uuid4(), None)
    assert exc_info.value.status_code == 404


async def test_request_cv_feedback_marks_job_failed_on_enqueue_error(
    db, test_user, completed_document
):
    mock_queue_cls = MagicMock()
    mock_queue_instance = MagicMock()
    mock_queue_instance.enqueue.side_effect = RuntimeError("redis down")
    mock_queue_cls.return_value = mock_queue_instance

    service = _service(db)
    with patch("app.modules.documents.service.Queue", mock_queue_cls):
        with pytest.raises(HTTPException) as exc_info:
            await service.request_cv_feedback(str(completed_document.id), test_user.id, None)
    assert exc_info.value.status_code == 500

    jobs = (
        (
            await db.execute(
                select(DocumentJob).where(
                    DocumentJob.document_id == completed_document.id,
                    DocumentJob.job_type == "cv_feedback",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(jobs) == 1
    assert jobs[0].status == "failed"
    assert "redis down" in jobs[0].error


# ---------------------------------------------------------------------------
# get_latest_cv_feedback
# ---------------------------------------------------------------------------


async def test_get_latest_cv_feedback_returns_most_recent_report(db, test_user, completed_document):
    older = CvFeedbackReport(
        id=uuid4(),
        document_id=completed_document.id,
        user_id=test_user.id,
        target_role="Backend Engineer",
        ats_score=60,
        strengths=["Old strength"],
        improvements=["Old improvement"],
        rewritten_bullets=[{"original": "a", "rewritten": "b", "rationale": "c"}],
        accepted_bullet_indices=[],
    )
    db.add(older)
    await db.commit()

    newer = CvFeedbackReport(
        id=uuid4(),
        document_id=completed_document.id,
        user_id=test_user.id,
        target_role="Senior Backend Engineer",
        ats_score=85,
        strengths=["New strength"],
        improvements=["New improvement"],
        rewritten_bullets=[{"original": "x", "rewritten": "y", "rationale": "z"}],
        accepted_bullet_indices=[],
    )
    db.add(newer)
    await db.commit()

    service = _service(db)
    result = await service.get_latest_cv_feedback(str(completed_document.id), test_user.id)
    assert result.report_id == str(newer.id)
    assert result.ats_score == 85


async def test_get_latest_cv_feedback_404_when_no_report_yet(db, test_user, completed_document):
    service = _service(db)
    with pytest.raises(HTTPException) as exc_info:
        await service.get_latest_cv_feedback(str(completed_document.id), test_user.id)
    assert exc_info.value.status_code == 404


async def test_get_latest_cv_feedback_404_for_unowned_document(db, test_user, completed_document):
    service = _service(db)
    with pytest.raises(HTTPException) as exc_info:
        await service.get_latest_cv_feedback(str(completed_document.id), uuid4())
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# accept_cv_feedback_bullet
# ---------------------------------------------------------------------------


@pytest.fixture
async def feedback_report(db, test_user, completed_document):
    report = CvFeedbackReport(
        id=uuid4(),
        document_id=completed_document.id,
        user_id=test_user.id,
        target_role="Backend Engineer",
        ats_score=70,
        strengths=["Strong background"],
        improvements=["Add metrics"],
        rewritten_bullets=[
            {"original": "Did work", "rewritten": "Did great work", "rationale": "clarity"},
            {"original": "Wrote code", "rewritten": "Shipped feature X", "rationale": "impact"},
        ],
        accepted_bullet_indices=[],
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


async def test_accept_cv_feedback_bullet_appends_index(
    db, test_user, completed_document, feedback_report
):
    service = _service(db)
    result = await service.accept_cv_feedback_bullet(
        str(completed_document.id), test_user.id, str(feedback_report.id), 0
    )
    assert result.accepted_bullet_indices == [0]


async def test_accept_cv_feedback_bullet_is_idempotent(
    db, test_user, completed_document, feedback_report
):
    service = _service(db)
    await service.accept_cv_feedback_bullet(
        str(completed_document.id), test_user.id, str(feedback_report.id), 1
    )
    result = await service.accept_cv_feedback_bullet(
        str(completed_document.id), test_user.id, str(feedback_report.id), 1
    )
    assert result.accepted_bullet_indices == [1]


async def test_accept_cv_feedback_bullet_rejects_negative_index(
    db, test_user, completed_document, feedback_report
):
    service = _service(db)
    with pytest.raises(HTTPException) as exc_info:
        await service.accept_cv_feedback_bullet(
            str(completed_document.id), test_user.id, str(feedback_report.id), -1
        )
    assert exc_info.value.status_code == 400


async def test_accept_cv_feedback_bullet_rejects_out_of_range_index(
    db, test_user, completed_document, feedback_report
):
    service = _service(db)
    with pytest.raises(HTTPException) as exc_info:
        await service.accept_cv_feedback_bullet(
            str(completed_document.id), test_user.id, str(feedback_report.id), 2
        )
    assert exc_info.value.status_code == 400


async def test_accept_cv_feedback_bullet_404_for_unknown_report(db, test_user, completed_document):
    service = _service(db)
    with pytest.raises(HTTPException) as exc_info:
        await service.accept_cv_feedback_bullet(
            str(completed_document.id), test_user.id, str(uuid4()), 0
        )
    assert exc_info.value.status_code == 404


async def test_accept_cv_feedback_bullet_404_for_unowned_document(
    db, test_user, completed_document, feedback_report
):
    """Caller doesn't own the document at all — fails the _get_owned_document check first."""
    service = _service(db)
    with pytest.raises(HTTPException) as exc_info:
        await service.accept_cv_feedback_bullet(
            str(completed_document.id), uuid4(), str(feedback_report.id), 0
        )
    assert exc_info.value.status_code == 404


async def test_accept_cv_feedback_bullet_404_when_report_owned_by_different_user(
    db, test_user, completed_document
):
    """Document is owned by the caller, but the report row belongs to a different user_id —
    the second query's `CvFeedbackReport.user_id == user_id` filter must still reject it."""
    other_user = User(
        id=uuid4(),
        email=f"cv-feedback-other-{uuid4().hex[:8]}@example.com",
        first_name="Other",
        last_name="User",
        is_active=True,
        is_verified=True,
    )
    db.add(other_user)
    report = CvFeedbackReport(
        id=uuid4(),
        document_id=completed_document.id,
        user_id=other_user.id,
        target_role="Backend Engineer",
        ats_score=70,
        strengths=["Strong background"],
        improvements=["Add metrics"],
        rewritten_bullets=[
            {"original": "Did work", "rewritten": "Did great work", "rationale": "clarity"}
        ],
        accepted_bullet_indices=[],
    )
    db.add(report)
    await db.commit()

    service = _service(db)
    with pytest.raises(HTTPException) as exc_info:
        await service.accept_cv_feedback_bullet(
            str(completed_document.id), test_user.id, str(report.id), 0
        )
    assert exc_info.value.status_code == 404
