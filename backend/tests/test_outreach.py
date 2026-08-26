"""Tests for outreach drafting, editing, and sending. Perplexity + OpenAI mocked."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException

from app.auth.models import User
from app.clients.perplexity import PerplexityClient
from app.modules.documents.models import CandidateDocument
from app.modules.outreach.models import OutreachMessage
from app.modules.outreach.schemas import OutreachDraftRequest, OutreachEditRequest
from app.modules.outreach.service import OutreachService


@pytest.fixture
async def test_user(db):
    user = User(
        id=uuid4(),
        email=f"outreach-{uuid4().hex[:8]}@example.com",
        first_name="Jane",
        last_name="User",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def test_perplexity_client_returns_empty_summary_when_no_api_key(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    client = PerplexityClient()
    result = await client.get_company_context("Acme Corp")
    assert result == {"summary": "", "source": "none"}
    get_settings.cache_clear()


async def test_perplexity_client_fails_soft_on_http_error(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-test")
    from app.core.config import get_settings

    get_settings.cache_clear()
    client = PerplexityClient()
    with patch.object(
        client._client, "post", new=AsyncMock(side_effect=httpx.ConnectError("network error"))
    ):
        result = await client.get_company_context("Acme Corp")
    assert result["source"] == "none"
    get_settings.cache_clear()


async def test_perplexity_client_returns_summary_on_success(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-test")
    from app.core.config import get_settings

    get_settings.cache_clear()
    client = PerplexityClient()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(
        return_value={"choices": [{"message": {"content": "  Acme makes widgets.  "}}]}
    )
    with patch.object(client._client, "post", new=AsyncMock(return_value=mock_response)):
        result = await client.get_company_context("Acme Corp", role_title="Engineer")
    assert result == {"summary": "Acme makes widgets.", "source": "perplexity"}
    get_settings.cache_clear()


async def test_perplexity_client_retries_transient_error_then_succeeds(monkeypatch):
    """Proves with_transient_retry is wired into get_company_context's post() call."""
    monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-test")
    from app.core.config import get_settings

    get_settings.cache_clear()
    client = PerplexityClient()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(
        return_value={"choices": [{"message": {"content": "Acme is hiring."}}]}
    )
    mock_post = AsyncMock(side_effect=[httpx.ConnectError("network blip"), mock_response])
    with patch.object(client._client, "post", new=mock_post):
        result = await client.get_company_context("Acme Corp")

    assert mock_post.call_count == 2
    assert result == {"summary": "Acme is hiring.", "source": "perplexity"}
    get_settings.cache_clear()


async def test_edit_draft_rejects_editing_sent_message(db, test_user):
    message = OutreachMessage(
        id=uuid4(),
        user_id=test_user.id,
        company_name="Acme",
        subject="Hi",
        body="Body",
        status="sent",
        sent_at=datetime.now(UTC),
    )
    db.add(message)
    await db.commit()

    service = OutreachService(db, redis_conn=MagicMock())
    with pytest.raises(HTTPException) as exc_info:
        await service.edit_draft(
            test_user.id, str(message.id), OutreachEditRequest(subject="New", body="New body")
        )
    assert exc_info.value.status_code == 409


async def test_edit_draft_updates_subject_and_body(db, test_user):
    message = OutreachMessage(
        id=uuid4(),
        user_id=test_user.id,
        company_name="Acme",
        subject="Hi",
        body="Body",
        status="draft",
    )
    db.add(message)
    await db.commit()

    service = OutreachService(db, redis_conn=MagicMock())
    result = await service.edit_draft(
        test_user.id, str(message.id), OutreachEditRequest(subject="New", body="New body")
    )
    assert result.subject == "New"
    assert result.body == "New body"


async def test_edit_draft_404_for_unowned_message(db, test_user):
    other_id = uuid4()
    message = OutreachMessage(
        id=uuid4(),
        user_id=other_id,
        company_name="Acme",
        subject="Hi",
        body="Body",
        status="draft",
    )
    db.add(message)
    await db.commit()

    service = OutreachService(db, redis_conn=MagicMock())
    with pytest.raises(HTTPException) as exc_info:
        await service.edit_draft(
            test_user.id, str(message.id), OutreachEditRequest(subject="New", body="New body")
        )
    assert exc_info.value.status_code == 404


async def test_send_message_appends_disclosure_footer_and_marks_sent(db, test_user):
    message = OutreachMessage(
        id=uuid4(),
        user_id=test_user.id,
        company_name="Acme",
        subject="Hi",
        body="Original body with no footer.",
        status="draft",
        message_type="email",
        recipient_email="hiring@acme.com",
    )
    db.add(message)
    await db.commit()

    service = OutreachService(db, redis_conn=MagicMock())
    result = await service.send_message(
        test_user.id, str(message.id), sender_email="jane@example.com", sender_name="jane"
    )

    assert result.status == "sent"
    assert "unsubscribe" in result.body.lower() or "prefer not to receive" in result.body.lower()
    assert "jane@example.com" in result.body
    assert result.sent_at is not None
    assert "/app/privacy" in result.body


@pytest.mark.parametrize("message_type", ["generic", "custom"])
async def test_send_message_omits_disclosure_footer_for_non_email_types(
    db, test_user, message_type
):
    message = OutreachMessage(
        id=uuid4(),
        user_id=test_user.id,
        company_name="Acme",
        subject="Hi",
        body="Original body with no footer.",
        status="draft",
        message_type=message_type,
        recipient_linkedin_url=(
            "https://www.linkedin.com/in/jane-recruiter" if message_type == "linkedin" else None
        ),
    )
    db.add(message)
    await db.commit()

    service = OutreachService(db, redis_conn=MagicMock())
    result = await service.send_message(
        test_user.id, str(message.id), sender_email="jane@example.com", sender_name="jane"
    )

    assert result.status == "sent"
    assert result.body == "Original body with no footer."
    assert "unsubscribe" not in result.body.lower()
    assert "prefer not to receive" not in result.body.lower()


async def test_send_message_for_linkedin_type_enqueues_task_and_stays_draft(db, test_user):
    """Machine-2/06: sending a linkedin-type message no longer marks it 'sent'
    immediately — it enqueues a LinkedInSendTask for a human operator, and status
    stays 'draft' until that operator confirms they performed the action
    themselves (linkedin_send_service.complete_task)."""
    message = OutreachMessage(
        id=uuid4(),
        user_id=test_user.id,
        company_name="Acme",
        subject="Hi",
        body="Original body with no footer.",
        status="draft",
        message_type="linkedin",
        recipient_linkedin_url="https://www.linkedin.com/in/jane-recruiter",
    )
    db.add(message)
    await db.commit()

    service = OutreachService(db, redis_conn=MagicMock())
    result = await service.send_message(
        test_user.id, str(message.id), sender_email="jane@example.com", sender_name="jane"
    )

    assert result.status == "draft"
    assert result.body == "Original body with no footer."

    from sqlalchemy import select

    from app.modules.outreach.linkedin_send_models import LinkedInSendTask

    task_result = await db.execute(
        select(LinkedInSendTask).where(LinkedInSendTask.outreach_message_id == message.id)
    )
    task = task_result.scalar_one()
    assert task.linkedin_profile_url == "https://www.linkedin.com/in/jane-recruiter"
    assert task.status == "pending"


async def test_send_message_rejects_already_sent(db, test_user):
    message = OutreachMessage(
        id=uuid4(),
        user_id=test_user.id,
        company_name="Acme",
        subject="Hi",
        body="Body",
        status="sent",
        sent_at=datetime.now(UTC),
    )
    db.add(message)
    await db.commit()

    service = OutreachService(db, redis_conn=MagicMock())
    with pytest.raises(HTTPException) as exc_info:
        await service.send_message(
            test_user.id, str(message.id), sender_email="jane@example.com", sender_name="jane"
        )
    assert exc_info.value.status_code == 409


async def test_send_message_rejects_admin_blocked_message(db, test_user):
    message = OutreachMessage(
        id=uuid4(),
        user_id=test_user.id,
        company_name="Acme",
        subject="Hi",
        body="Body",
        status="draft",
        admin_blocked=True,
    )
    db.add(message)
    await db.commit()

    service = OutreachService(db, redis_conn=MagicMock())
    with pytest.raises(HTTPException) as exc_info:
        await service.send_message(
            test_user.id, str(message.id), sender_email="jane@example.com", sender_name="jane"
        )
    assert exc_info.value.status_code == 403

    await db.refresh(message)
    assert message.status == "draft"
    assert message.sent_at is None


async def test_send_message_allows_message_with_admin_blocked_false(db, test_user):
    message = OutreachMessage(
        id=uuid4(),
        user_id=test_user.id,
        company_name="Acme",
        subject="Hi",
        body="Original body with no footer.",
        status="draft",
        message_type="email",
        recipient_email="hiring@acme.com",
        admin_blocked=False,
    )
    db.add(message)
    await db.commit()

    service = OutreachService(db, redis_conn=MagicMock())
    result = await service.send_message(
        test_user.id, str(message.id), sender_email="jane@example.com", sender_name="jane"
    )

    assert result.status == "sent"


async def test_send_message_uses_absolute_privacy_url_when_configured(db, test_user, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("APP_PUBLIC_BASE_URL", "https://app.hyrepath.com")
    get_settings.cache_clear()

    message = OutreachMessage(
        id=uuid4(),
        user_id=test_user.id,
        company_name="Acme",
        subject="Hi",
        body="Original body with no footer.",
        status="draft",
        recipient_email="hiring@acme.com",
    )
    db.add(message)
    await db.commit()

    service = OutreachService(db, redis_conn=MagicMock())
    result = await service.send_message(
        test_user.id, str(message.id), sender_email="jane@example.com", sender_name="jane"
    )

    assert "https://app.hyrepath.com/app/privacy" in result.body
    get_settings.cache_clear()


async def test_send_message_404_for_unowned_message(db, test_user):
    other_id = uuid4()
    message = OutreachMessage(
        id=uuid4(),
        user_id=other_id,
        company_name="Acme",
        subject="Hi",
        body="Body",
        status="draft",
    )
    db.add(message)
    await db.commit()

    service = OutreachService(db, redis_conn=MagicMock())
    with pytest.raises(HTTPException) as exc_info:
        await service.send_message(
            test_user.id, str(message.id), sender_email="jane@example.com", sender_name="jane"
        )
    assert exc_info.value.status_code == 404


async def test_list_my_messages_returns_only_own_messages(db, test_user):
    other_id = uuid4()
    mine = OutreachMessage(
        id=uuid4(),
        user_id=test_user.id,
        company_name="Acme",
        subject="Hi",
        body="Body",
        status="draft",
    )
    theirs = OutreachMessage(
        id=uuid4(), user_id=other_id, company_name="Beta", subject="Hi", body="Body", status="draft"
    )
    db.add_all([mine, theirs])
    await db.commit()

    service = OutreachService(db, redis_conn=MagicMock())
    result = await service.list_my_messages(test_user.id)
    assert len(result.messages) == 1
    assert result.messages[0].company_name == "Acme"


async def test_request_draft_rejects_when_feature_disabled(db, test_user, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("OUTREACH_ENABLED", "false")
    get_settings.cache_clear()
    service = OutreachService(db, redis_conn=MagicMock())
    with pytest.raises(HTTPException) as exc_info:
        await service.request_draft(
            test_user.id, OutreachDraftRequest(company_name="Acme", document_id=str(uuid4()))
        )
    assert exc_info.value.status_code == 403
    get_settings.cache_clear()


async def test_request_draft_requires_a_processed_cv(db, test_user):
    service = OutreachService(db, redis_conn=MagicMock())
    with pytest.raises(HTTPException) as exc_info:
        await service.request_draft(
            test_user.id,
            OutreachDraftRequest(
                company_name="Acme",
                document_id=str(uuid4()),
                message_type="linkedin",
                recipient_linkedin_url="https://www.linkedin.com/in/hiring-manager",
            ),
        )
    assert exc_info.value.status_code == 409


async def test_request_draft_enqueues_job_for_completed_document(db, test_user):
    doc = CandidateDocument(
        id=uuid4(),
        user_id=test_user.id,
        document_type="cv",
        original_filename="cv.pdf",
        storage_path="documents/x/y.pdf",
        file_hash=f"outreach-{uuid4().hex}",
        file_size_bytes=1000,
        raw_text="Jane Doe",
        processing_status="completed",
    )
    db.add(doc)
    await db.commit()

    mock_queue_cls = MagicMock()
    mock_queue_instance = MagicMock()
    mock_queue_instance.enqueue.return_value = MagicMock(id="rq-job-123")
    mock_queue_cls.return_value = mock_queue_instance

    service = OutreachService(db, redis_conn=MagicMock())
    with patch("app.modules.outreach.service.Queue", mock_queue_cls):
        result = await service.request_draft(
            test_user.id,
            OutreachDraftRequest(
                company_name="Acme",
                document_id=str(doc.id),
                message_type="linkedin",
                recipient_linkedin_url="https://www.linkedin.com/in/hiring-manager",
            ),
        )

    assert result["rq_job_id"] == "rq-job-123"
    mock_queue_instance.enqueue.assert_called_once()


async def test_request_draft_second_call_rejected_while_lock_held(db, test_user):
    """A repeated request_draft for the same (user, company, job_match=None) within the
    60s lock window must raise 409 instead of enqueueing a duplicate job."""
    doc = CandidateDocument(
        id=uuid4(),
        user_id=test_user.id,
        document_type="cv",
        original_filename="cv.pdf",
        storage_path="documents/x/y.pdf",
        file_hash=f"outreach-{uuid4().hex}",
        file_size_bytes=1000,
        raw_text="Jane Doe",
        processing_status="completed",
    )
    db.add(doc)
    await db.commit()

    mock_queue_cls = MagicMock()
    mock_queue_instance = MagicMock()
    mock_queue_instance.enqueue.return_value = MagicMock(id="rq-job-123")
    mock_queue_cls.return_value = mock_queue_instance

    redis_conn = MagicMock()
    redis_conn.set.side_effect = [True, None]

    service = OutreachService(db, redis_conn=redis_conn)
    with patch("app.modules.outreach.service.Queue", mock_queue_cls):
        first_result = await service.request_draft(
            test_user.id,
            OutreachDraftRequest(
                company_name="Acme",
                document_id=str(doc.id),
                message_type="linkedin",
                recipient_linkedin_url="https://www.linkedin.com/in/hiring-manager",
            ),
        )
        assert first_result["rq_job_id"] == "rq-job-123"

        with pytest.raises(HTTPException) as exc_info:
            await service.request_draft(
                test_user.id,
                OutreachDraftRequest(
                    company_name="Acme",
                    document_id=str(doc.id),
                    message_type="linkedin",
                    recipient_linkedin_url="https://www.linkedin.com/in/hiring-manager",
                ),
            )

    assert exc_info.value.status_code == 409
    assert redis_conn.set.call_count == 2
    mock_queue_instance.enqueue.assert_called_once()


async def test_to_response_marks_research_degraded_true_when_source_none(db, test_user):
    message = OutreachMessage(
        id=uuid4(),
        user_id=test_user.id,
        company_name="Acme",
        subject="Hi",
        body="Body",
        status="draft",
        company_context_used={"summary": "", "source": "none"},
    )
    db.add(message)
    await db.commit()

    service = OutreachService(db, redis_conn=MagicMock())
    result = await service.list_my_messages(test_user.id)
    assert len(result.messages) == 1
    assert result.messages[0].research_degraded is True


async def test_to_response_marks_research_degraded_false_when_source_perplexity(db, test_user):
    message = OutreachMessage(
        id=uuid4(),
        user_id=test_user.id,
        company_name="Acme",
        subject="Hi",
        body="Body",
        status="draft",
        company_context_used={"summary": "Acme makes widgets.", "source": "perplexity"},
    )
    db.add(message)
    await db.commit()

    service = OutreachService(db, redis_conn=MagicMock())
    result = await service.list_my_messages(test_user.id)
    assert len(result.messages) == 1
    assert result.messages[0].research_degraded is False


async def test_request_draft_rejects_custom_type_missing_instruction(db, test_user):
    service = OutreachService(db, redis_conn=MagicMock())
    with pytest.raises(HTTPException) as exc_info:
        await service.request_draft(
            test_user.id,
            OutreachDraftRequest(
                company_name="Acme", document_id=str(uuid4()), message_type="custom"
            ),
        )
    assert exc_info.value.status_code == 400


async def test_request_draft_rejects_custom_type_blank_instruction(db, test_user):
    service = OutreachService(db, redis_conn=MagicMock())
    with pytest.raises(HTTPException) as exc_info:
        await service.request_draft(
            test_user.id,
            OutreachDraftRequest(
                company_name="Acme",
                document_id=str(uuid4()),
                message_type="custom",
                custom_instruction="   ",
            ),
        )
    assert exc_info.value.status_code == 400


async def test_request_draft_concurrent_lock_scoped_per_message_type(db, test_user):
    """Two simultaneous requests for the same company but different message_types must
    both succeed — the lock key includes message_type so they don't collide."""
    doc = CandidateDocument(
        id=uuid4(),
        user_id=test_user.id,
        document_type="cv",
        original_filename="cv.pdf",
        storage_path="documents/x/y.pdf",
        file_hash=f"outreach-{uuid4().hex}",
        file_size_bytes=1000,
        raw_text="Jane Doe",
        processing_status="completed",
    )
    db.add(doc)
    await db.commit()

    mock_queue_cls = MagicMock()
    mock_queue_instance = MagicMock()
    mock_queue_instance.enqueue.return_value = MagicMock(id="rq-job-123")
    mock_queue_cls.return_value = mock_queue_instance

    real_locks: dict[str, str] = {}

    def _fake_set(key, value, nx=False, ex=None):
        if nx and key in real_locks:
            return None
        real_locks[key] = value
        return True

    redis_conn = MagicMock()
    redis_conn.set.side_effect = _fake_set

    service = OutreachService(db, redis_conn=redis_conn)
    with patch("app.modules.outreach.service.Queue", mock_queue_cls):
        email_result = await service.request_draft(
            test_user.id,
            OutreachDraftRequest(
                company_name="Acme",
                document_id=str(doc.id),
                message_type="email",
                recipient_email="hiring@acme.com",
            ),
        )
        linkedin_result = await service.request_draft(
            test_user.id,
            OutreachDraftRequest(
                company_name="Acme",
                document_id=str(doc.id),
                message_type="linkedin",
                recipient_linkedin_url="https://www.linkedin.com/in/hiring-manager",
            ),
        )

    assert email_result["rq_job_id"] == "rq-job-123"
    assert linkedin_result["rq_job_id"] == "rq-job-123"
    assert mock_queue_instance.enqueue.call_count == 2


async def test_request_draft_concurrent_lock_rejects_same_message_type(db, test_user):
    """Two simultaneous requests for the same company AND same message_type — the
    second must be rejected, exactly like the pre-Module-G behavior."""
    doc = CandidateDocument(
        id=uuid4(),
        user_id=test_user.id,
        document_type="cv",
        original_filename="cv.pdf",
        storage_path="documents/x/y.pdf",
        file_hash=f"outreach-{uuid4().hex}",
        file_size_bytes=1000,
        raw_text="Jane Doe",
        processing_status="completed",
    )
    db.add(doc)
    await db.commit()

    mock_queue_cls = MagicMock()
    mock_queue_instance = MagicMock()
    mock_queue_instance.enqueue.return_value = MagicMock(id="rq-job-123")
    mock_queue_cls.return_value = mock_queue_instance

    redis_conn = MagicMock()
    redis_conn.set.side_effect = [True, None]

    service = OutreachService(db, redis_conn=redis_conn)
    with patch("app.modules.outreach.service.Queue", mock_queue_cls):
        first_result = await service.request_draft(
            test_user.id,
            OutreachDraftRequest(
                company_name="Acme",
                document_id=str(doc.id),
                message_type="linkedin",
                recipient_linkedin_url="https://www.linkedin.com/in/hiring-manager",
            ),
        )
        assert first_result["rq_job_id"] == "rq-job-123"

        with pytest.raises(HTTPException) as exc_info:
            await service.request_draft(
                test_user.id,
                OutreachDraftRequest(
                    company_name="Acme",
                    document_id=str(doc.id),
                    message_type="linkedin",
                    recipient_linkedin_url="https://www.linkedin.com/in/hiring-manager",
                ),
            )

    assert exc_info.value.status_code == 409
    mock_queue_instance.enqueue.assert_called_once()


async def test_edit_draft_rejects_oversized_linkedin_subject(db, test_user):
    from app.core.config import get_settings

    settings = get_settings()
    message = OutreachMessage(
        id=uuid4(),
        user_id=test_user.id,
        company_name="Acme",
        subject="Hi",
        body="Body",
        status="draft",
        message_type="linkedin",
    )
    db.add(message)
    await db.commit()

    oversized_subject = "S" * (settings.outreach_linkedin_inmail_subject_max_chars + 1)
    service = OutreachService(db, redis_conn=MagicMock())
    with pytest.raises(HTTPException) as exc_info:
        await service.edit_draft(
            test_user.id,
            str(message.id),
            OutreachEditRequest(subject=oversized_subject, body="fine"),
        )
    assert exc_info.value.status_code == 422
    assert "LinkedIn messages are limited to" in exc_info.value.detail


async def test_edit_draft_rejects_oversized_linkedin_body(db, test_user):
    from app.core.config import get_settings

    settings = get_settings()
    message = OutreachMessage(
        id=uuid4(),
        user_id=test_user.id,
        company_name="Acme",
        subject="Hi",
        body="Body",
        status="draft",
        message_type="linkedin",
    )
    db.add(message)
    await db.commit()

    oversized_body = "B" * (settings.outreach_linkedin_inmail_body_max_chars + 1)
    service = OutreachService(db, redis_conn=MagicMock())
    with pytest.raises(HTTPException) as exc_info:
        await service.edit_draft(
            test_user.id,
            str(message.id),
            OutreachEditRequest(subject="fine", body=oversized_body),
        )
    assert exc_info.value.status_code == 422
    assert "LinkedIn messages are limited to" in exc_info.value.detail


async def test_edit_draft_accepts_valid_length_linkedin_edit(db, test_user):
    message = OutreachMessage(
        id=uuid4(),
        user_id=test_user.id,
        company_name="Acme",
        subject="Hi",
        body="Body",
        status="draft",
        message_type="linkedin",
    )
    db.add(message)
    await db.commit()

    service = OutreachService(db, redis_conn=MagicMock())
    result = await service.edit_draft(
        test_user.id,
        str(message.id),
        OutreachEditRequest(subject="Short subject", body="Short body"),
    )
    assert result.subject == "Short subject"
    assert result.body == "Short body"


@pytest.mark.parametrize("message_type", ["email", "generic", "custom"])
async def test_edit_draft_linkedin_guard_does_not_apply_to_other_types(db, test_user, message_type):
    """Non-LinkedIn message types must be unaffected by the LinkedIn length guard, even
    with a body far longer than the LinkedIn InMail limit."""
    from app.core.config import get_settings

    settings = get_settings()
    message = OutreachMessage(
        id=uuid4(),
        user_id=test_user.id,
        company_name="Acme",
        subject="Hi",
        body="Body",
        status="draft",
        message_type=message_type,
    )
    db.add(message)
    await db.commit()

    oversized_body = "B" * (settings.outreach_linkedin_inmail_body_max_chars + 500)
    service = OutreachService(db, redis_conn=MagicMock())
    result = await service.edit_draft(
        test_user.id,
        str(message.id),
        OutreachEditRequest(subject="fine", body=oversized_body),
    )
    assert result.body == oversized_body


# --- machine-2/03: strategy dimension + company tier ---


async def test_request_draft_rejects_warm_referral_missing_context(db, test_user):
    doc = CandidateDocument(
        id=uuid4(),
        user_id=test_user.id,
        document_type="cv",
        original_filename="cv.pdf",
        storage_path="documents/x/y.pdf",
        file_hash=f"outreach-{uuid4().hex}",
        file_size_bytes=1000,
        raw_text="Jane Doe",
        processing_status="completed",
    )
    db.add(doc)
    await db.commit()

    service = OutreachService(db, redis_conn=MagicMock())
    with pytest.raises(HTTPException) as exc_info:
        await service.request_draft(
            test_user.id,
            OutreachDraftRequest(
                company_name="Acme",
                document_id=str(doc.id),
                strategy="warm_referral",
            ),
        )
    assert exc_info.value.status_code == 400


async def test_request_draft_rejects_warm_referral_blank_context(db, test_user):
    doc = CandidateDocument(
        id=uuid4(),
        user_id=test_user.id,
        document_type="cv",
        original_filename="cv.pdf",
        storage_path="documents/x/y.pdf",
        file_hash=f"outreach-{uuid4().hex}",
        file_size_bytes=1000,
        raw_text="Jane Doe",
        processing_status="completed",
    )
    db.add(doc)
    await db.commit()

    service = OutreachService(db, redis_conn=MagicMock())
    with pytest.raises(HTTPException) as exc_info:
        await service.request_draft(
            test_user.id,
            OutreachDraftRequest(
                company_name="Acme",
                document_id=str(doc.id),
                strategy="warm_referral",
                referral_context="   ",
            ),
        )
    assert exc_info.value.status_code == 400


async def test_request_draft_allows_warm_referral_with_context(db, test_user):
    doc = CandidateDocument(
        id=uuid4(),
        user_id=test_user.id,
        document_type="cv",
        original_filename="cv.pdf",
        storage_path="documents/x/y.pdf",
        file_hash=f"outreach-{uuid4().hex}",
        file_size_bytes=1000,
        raw_text="Jane Doe",
        processing_status="completed",
    )
    db.add(doc)
    await db.commit()

    mock_queue_cls = MagicMock()
    mock_queue_instance = MagicMock()
    mock_queue_instance.enqueue.return_value = MagicMock(id="rq-job-123")
    mock_queue_cls.return_value = mock_queue_instance

    service = OutreachService(db, redis_conn=MagicMock())
    with patch("app.modules.outreach.service.Queue", mock_queue_cls):
        result = await service.request_draft(
            test_user.id,
            OutreachDraftRequest(
                company_name="Acme",
                document_id=str(doc.id),
                message_type="linkedin",
                recipient_linkedin_url="https://www.linkedin.com/in/hiring-manager",
                strategy="warm_referral",
                referral_context="Introduced by Jane Doe",
            ),
        )

    assert result["rq_job_id"] == "rq-job-123"
    call_args = mock_queue_instance.enqueue.call_args
    assert "Introduced by Jane Doe" in call_args.args


async def test_request_draft_defaults_strategy_to_direct_pitch(db, test_user):
    """Backward-compat: existing callers that don't pass `strategy` keep working
    (default is direct_pitch, matching today's implicit behavior)."""
    doc = CandidateDocument(
        id=uuid4(),
        user_id=test_user.id,
        document_type="cv",
        original_filename="cv.pdf",
        storage_path="documents/x/y.pdf",
        file_hash=f"outreach-{uuid4().hex}",
        file_size_bytes=1000,
        raw_text="Jane Doe",
        processing_status="completed",
    )
    db.add(doc)
    await db.commit()

    mock_queue_cls = MagicMock()
    mock_queue_instance = MagicMock()
    mock_queue_instance.enqueue.return_value = MagicMock(id="rq-job-123")
    mock_queue_cls.return_value = mock_queue_instance

    service = OutreachService(db, redis_conn=MagicMock())
    with patch("app.modules.outreach.service.Queue", mock_queue_cls):
        result = await service.request_draft(
            test_user.id,
            OutreachDraftRequest(
                company_name="Acme",
                document_id=str(doc.id),
                message_type="linkedin",
                recipient_linkedin_url="https://www.linkedin.com/in/hiring-manager",
            ),
        )

    assert result["rq_job_id"] == "rq-job-123"
    call_args = mock_queue_instance.enqueue.call_args
    assert "direct_pitch" in call_args.args


async def test_set_company_tier_creates_new_row(db, test_user):
    company_name = f"Acme-{uuid4().hex[:8]}"
    service = OutreachService(db, redis_conn=MagicMock())
    row = await service.set_company_tier(
        company_name=company_name,
        tier="premium",
        set_by_user_id=test_user.id,
        notes="Well-known employer",
    )
    assert row.company_name == company_name
    assert row.tier == "premium"
    assert row.notes == "Well-known employer"
    assert row.set_by_user_id == test_user.id


async def test_set_company_tier_upserts_existing_row_in_place(db, test_user):
    """Re-setting an existing employer's tier overwrites in place rather than
    creating a duplicate row (exercises company_name's unique-constraint upsert)."""
    from sqlalchemy import func, select

    from app.modules.outreach.models import EmployerCompanyTier

    company_name = f"Acme-{uuid4().hex[:8]}"
    service = OutreachService(db, redis_conn=MagicMock())
    first = await service.set_company_tier(
        company_name=company_name, tier="premium", set_by_user_id=test_user.id, notes=None
    )
    other_user_id = uuid4()
    second = await service.set_company_tier(
        company_name=company_name,
        tier="outsourcing",
        set_by_user_id=other_user_id,
        notes="Changed my mind",
    )

    assert first.id == second.id
    assert second.tier == "outsourcing"
    assert second.notes == "Changed my mind"
    assert second.set_by_user_id == other_user_id

    count_result = await db.execute(
        select(func.count())
        .select_from(EmployerCompanyTier)
        .where(EmployerCompanyTier.company_name == company_name)
    )
    assert count_result.scalar_one() == 1


async def test_get_company_tier_returns_none_for_unset_employer(db, test_user):
    service = OutreachService(db, redis_conn=MagicMock())
    result = await service.get_company_tier(f"Nonexistent Co {uuid4().hex[:8]}")
    assert result is None


async def test_get_company_tier_returns_set_row(db, test_user):
    company_name = f"Acme-{uuid4().hex[:8]}"
    service = OutreachService(db, redis_conn=MagicMock())
    await service.set_company_tier(
        company_name=company_name, tier="outsourcing", set_by_user_id=test_user.id, notes=None
    )
    result = await service.get_company_tier(company_name)
    assert result is not None
    assert result.tier == "outsourcing"


# --- machine-2/03: LLM company-tier classifier + set_by override preservation ---


async def test_set_company_tier_always_writes_set_by_recruiter(db, test_user):
    """The recruiter-facing PUT path (OutreachService.set_company_tier) always
    writes set_by='recruiter', regardless of any prior value."""
    company_name = f"Acme-{uuid4().hex[:8]}"
    service = OutreachService(db, redis_conn=MagicMock())
    row = await service.set_company_tier(
        company_name=company_name, tier="premium", set_by_user_id=test_user.id, notes=None
    )
    assert row.set_by == "recruiter"


async def test_recruiter_put_always_overwrites_regardless_of_existing_set_by(db, test_user):
    """A recruiter's own explicit PUT /company-tier call always overwrites,
    regardless of the existing row's set_by -- including a row the classifier
    itself previously wrote (set_by='llm')."""
    from app.modules.outreach.repository import set_company_tier

    company_name = f"Acme-{uuid4().hex[:8]}"
    await set_company_tier(
        db,
        company_name=company_name,
        tier="outsourcing",
        set_by="llm",
        set_by_user_id=None,
        notes=None,
    )

    service = OutreachService(db, redis_conn=MagicMock())
    row = await service.set_company_tier(
        company_name=company_name,
        tier="premium",
        set_by_user_id=test_user.id,
        notes="Recruiter call",
    )
    assert row.tier == "premium"
    assert row.set_by == "recruiter"
    assert row.set_by_user_id == test_user.id
    assert row.notes == "Recruiter call"


async def test_apply_classified_company_tier_preserves_recruiter_override(db, test_user):
    """Release-blocking: seed a row with set_by='recruiter', then invoke the
    classifier's write path for the same company_name with a different tier --
    the row must be completely unchanged (tier, set_by, set_by_user_id all
    still the recruiter's original values)."""
    from app.modules.outreach.repository import get_company_tier
    from app.modules.outreach.service import apply_classified_company_tier

    company_name = f"Acme-{uuid4().hex[:8]}"
    service = OutreachService(db, redis_conn=MagicMock())
    original = await service.set_company_tier(
        company_name=company_name,
        tier="premium",
        set_by_user_id=test_user.id,
        notes="Recruiter judgment",
    )

    result = await apply_classified_company_tier(db, company_name, "outsourcing")

    assert result.tier == "premium"
    assert result.set_by == "recruiter"
    assert result.set_by_user_id == test_user.id
    assert result.notes == "Recruiter judgment"

    refetched = await get_company_tier(db, company_name)
    assert refetched.tier == original.tier
    assert refetched.set_by == original.set_by
    assert refetched.set_by_user_id == original.set_by_user_id


async def test_apply_classified_company_tier_overwrites_llm_row(db):
    """Companion test: a set_by='llm' row IS overwritten by a subsequent
    classifier run -- the skip logic is specific to set_by='recruiter', not a
    blanket "never update" rule."""
    from app.modules.outreach.repository import set_company_tier
    from app.modules.outreach.service import apply_classified_company_tier

    company_name = f"Acme-{uuid4().hex[:8]}"
    await set_company_tier(
        db,
        company_name=company_name,
        tier="outsourcing",
        set_by="llm",
        set_by_user_id=None,
        notes=None,
    )

    result = await apply_classified_company_tier(db, company_name, "premium")

    assert result.tier == "premium"
    assert result.set_by == "llm"
    assert result.set_by_user_id is None


async def test_apply_classified_company_tier_creates_row_when_none_exists(db):
    """No prior row for this employer -- the classifier's write path creates
    one with set_by='llm' and set_by_user_id=None (no human actor)."""
    from app.modules.outreach.service import apply_classified_company_tier

    company_name = f"NewCo-{uuid4().hex[:8]}"
    result = await apply_classified_company_tier(db, company_name, "premium")

    assert result.tier == "premium"
    assert result.set_by == "llm"
    assert result.set_by_user_id is None


# --- machine-2/05: CAN-SPAM send compliance ---


async def test_request_draft_rejects_email_type_missing_recipient_email(db, test_user):
    doc = CandidateDocument(
        id=uuid4(),
        user_id=test_user.id,
        document_type="cv",
        original_filename="cv.pdf",
        storage_path="documents/x/y.pdf",
        file_hash=f"outreach-{uuid4().hex}",
        file_size_bytes=1000,
        raw_text="Jane Doe",
        processing_status="completed",
    )
    db.add(doc)
    await db.commit()

    service = OutreachService(db, redis_conn=MagicMock())
    with pytest.raises(HTTPException) as exc_info:
        await service.request_draft(
            test_user.id,
            OutreachDraftRequest(
                company_name="Acme", document_id=str(doc.id), message_type="email"
            ),
        )
    assert exc_info.value.status_code == 400


@pytest.mark.parametrize("message_type", ["linkedin", "generic", "custom"])
async def test_request_draft_does_not_require_recipient_email_for_non_email_types(
    db, test_user, message_type
):
    doc = CandidateDocument(
        id=uuid4(),
        user_id=test_user.id,
        document_type="cv",
        original_filename="cv.pdf",
        storage_path="documents/x/y.pdf",
        file_hash=f"outreach-{uuid4().hex}",
        file_size_bytes=1000,
        raw_text="Jane Doe",
        processing_status="completed",
    )
    db.add(doc)
    await db.commit()

    mock_queue_cls = MagicMock()
    mock_queue_instance = MagicMock()
    mock_queue_instance.enqueue.return_value = MagicMock(id="rq-job-123")
    mock_queue_cls.return_value = mock_queue_instance

    custom_instruction = "Say hi" if message_type == "custom" else None
    recipient_linkedin_url = (
        "https://www.linkedin.com/in/hiring-manager" if message_type == "linkedin" else None
    )
    service = OutreachService(db, redis_conn=MagicMock())
    with patch("app.modules.outreach.service.Queue", mock_queue_cls):
        result = await service.request_draft(
            test_user.id,
            OutreachDraftRequest(
                company_name="Acme",
                document_id=str(doc.id),
                message_type=message_type,
                custom_instruction=custom_instruction,
                recipient_linkedin_url=recipient_linkedin_url,
            ),
        )

    assert result["rq_job_id"] == "rq-job-123"


async def test_request_draft_email_type_threads_recipient_email_to_enqueue(db, test_user):
    doc = CandidateDocument(
        id=uuid4(),
        user_id=test_user.id,
        document_type="cv",
        original_filename="cv.pdf",
        storage_path="documents/x/y.pdf",
        file_hash=f"outreach-{uuid4().hex}",
        file_size_bytes=1000,
        raw_text="Jane Doe",
        processing_status="completed",
    )
    db.add(doc)
    await db.commit()

    mock_queue_cls = MagicMock()
    mock_queue_instance = MagicMock()
    mock_queue_instance.enqueue.return_value = MagicMock(id="rq-job-123")
    mock_queue_cls.return_value = mock_queue_instance

    service = OutreachService(db, redis_conn=MagicMock())
    with patch("app.modules.outreach.service.Queue", mock_queue_cls):
        result = await service.request_draft(
            test_user.id,
            OutreachDraftRequest(
                company_name="Acme",
                document_id=str(doc.id),
                message_type="email",
                recipient_email="hiring@acme.com",
            ),
        )

    assert result["rq_job_id"] == "rq-job-123"
    call_args = mock_queue_instance.enqueue.call_args
    assert "hiring@acme.com" in call_args.args


async def test_send_message_rejects_email_type_missing_recipient_email(db, test_user):
    """A draft created before this chunk shipped may have recipient_email=None; sending
    it must fail defensively rather than silently sending unchecked."""
    message = OutreachMessage(
        id=uuid4(),
        user_id=test_user.id,
        company_name="Acme",
        subject="Hi",
        body="Body",
        status="draft",
        message_type="email",
        recipient_email=None,
    )
    db.add(message)
    await db.commit()

    service = OutreachService(db, redis_conn=MagicMock())
    with pytest.raises(HTTPException) as exc_info:
        await service.send_message(
            test_user.id, str(message.id), sender_email="jane@example.com", sender_name="jane"
        )
    assert exc_info.value.status_code == 422

    await db.refresh(message)
    assert message.status == "draft"


async def test_send_message_rejects_suppressed_recipient_and_leaves_draft_unsent(db, test_user):
    from app.compliance.suppression import add_suppression

    await add_suppression(db, "blocked@acme.com", reason="opted out")

    message = OutreachMessage(
        id=uuid4(),
        user_id=test_user.id,
        company_name="Acme",
        subject="Hi",
        body="Original body with no footer.",
        status="draft",
        message_type="email",
        recipient_email="blocked@acme.com",
    )
    db.add(message)
    await db.commit()

    service = OutreachService(db, redis_conn=MagicMock())
    with pytest.raises(HTTPException) as exc_info:
        await service.send_message(
            test_user.id, str(message.id), sender_email="jane@example.com", sender_name="jane"
        )
    assert exc_info.value.status_code == 403

    await db.refresh(message)
    assert message.status == "draft"
    assert message.sent_at is None
    assert message.body == "Original body with no footer."
    assert message.suppression_checked_at is None


async def test_send_message_succeeds_for_non_suppressed_recipient_and_sets_checked_at(
    db, test_user, monkeypatch
):
    from app.core.config import get_settings

    monkeypatch.setenv("OUTREACH_PHYSICAL_ADDRESS", "123 Main St, San Francisco, CA")
    get_settings.cache_clear()

    message = OutreachMessage(
        id=uuid4(),
        user_id=test_user.id,
        company_name="Acme",
        subject="Hi",
        body="Original body with no footer.",
        status="draft",
        message_type="email",
        recipient_email="hiring@acme.com",
    )
    db.add(message)
    await db.commit()

    service = OutreachService(db, redis_conn=MagicMock())
    result = await service.send_message(
        test_user.id, str(message.id), sender_email="jane@example.com", sender_name="jane"
    )

    assert result.status == "sent"
    assert "123 Main St, San Francisco, CA" in result.body

    await db.refresh(message)
    assert message.suppression_checked_at is not None
    get_settings.cache_clear()
