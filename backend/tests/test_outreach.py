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
            test_user.id, OutreachDraftRequest(company_name="Acme", document_id=str(uuid4()))
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
            test_user.id, OutreachDraftRequest(company_name="Acme", document_id=str(doc.id))
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
            test_user.id, OutreachDraftRequest(company_name="Acme", document_id=str(doc.id))
        )
        assert first_result["rq_job_id"] == "rq-job-123"

        with pytest.raises(HTTPException) as exc_info:
            await service.request_draft(
                test_user.id, OutreachDraftRequest(company_name="Acme", document_id=str(doc.id))
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
