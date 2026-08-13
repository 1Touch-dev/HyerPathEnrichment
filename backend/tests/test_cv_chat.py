"""Tests for CvChatService. OpenAI calls mocked per RULE.md 'no live external calls in CI'."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.auth.models import User
from app.modules.documents.cv_chat_service import CvChatService
from app.modules.documents.models import CandidateDocument


@pytest.fixture
async def test_user(db):
    user = User(
        id=uuid4(),
        email=f"cv-chat-{uuid4().hex[:8]}@example.com",
        first_name="Test",
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
        file_hash="abc123",
        file_size_bytes=1000,
        raw_text="Jane Doe, Software Engineer",
        extracted_data={"email": "jane@example.com"},  # 1 of 8 required fields present
        processing_status="completed",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def test_start_session_creates_session_with_missing_fields(db, test_user, completed_document):
    service = CvChatService(db)
    response = await service.start_session(str(completed_document.id), test_user.id)

    assert response.status == "active"
    assert "email" not in response.missing_fields_at_start  # already present
    assert "phone" in response.missing_fields_at_start
    assert len(response.messages) == 1
    assert response.messages[0].role == "assistant"


async def test_start_session_resumes_existing_active_session(db, test_user, completed_document):
    service = CvChatService(db)
    first = await service.start_session(str(completed_document.id), test_user.id)
    second = await service.start_session(str(completed_document.id), test_user.id)
    assert first.session_id == second.session_id


async def test_start_session_rejects_unprocessed_document(db, test_user, completed_document):
    completed_document.processing_status = "pending"
    await db.commit()
    service = CvChatService(db)
    with pytest.raises(HTTPException) as exc_info:
        await service.start_session(str(completed_document.id), test_user.id)
    assert exc_info.value.status_code == 409


async def test_start_session_404_for_unowned_document(db, test_user, completed_document):
    service = CvChatService(db)
    with pytest.raises(HTTPException) as exc_info:
        await service.start_session(str(completed_document.id), uuid4())
    assert exc_info.value.status_code == 404


async def test_start_session_no_missing_fields_completes_immediately(db, test_user):
    doc = CandidateDocument(
        id=uuid4(),
        user_id=test_user.id,
        document_type="cv",
        original_filename="cv.pdf",
        storage_path="documents/x/y.pdf",
        file_hash="fullcv",
        file_size_bytes=1000,
        raw_text="Jane Doe",
        extracted_data={
            "email": "jane@example.com",
            "phone": "555-0100",
            "linkedin_url": "https://linkedin.com/in/jane",
            "technical_skills": ["python"],
            "total_years_experience": 5.0,
            "desired_roles": ["engineer"],
            "desired_locations": ["remote"],
            "remote_preference": "remote",
        },
        processing_status="completed",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    service = CvChatService(db)
    response = await service.start_session(str(doc.id), test_user.id)

    assert response.status == "completed"
    assert response.missing_fields_at_start == []
    assert response.messages == []


async def test_post_message_applies_tool_call_and_advances(db, test_user, completed_document):
    mock_client = AsyncMock()
    service = CvChatService(db, http_client=mock_client)
    session_response = await service.start_session(str(completed_document.id), test_user.id)

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(
        return_value={
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "record_cv_answer",
                                    "arguments": '{"field_name": "phone", "value": "555-0100"}',
                                }
                            }
                        ]
                    }
                }
            ]
        }
    )
    mock_client.post = AsyncMock(return_value=mock_response)
    service._settings.openai_api_key = "sk-test"
    turn = await service.post_message(session_response.session_id, test_user.id, "It's 555-0100")

    assert "phone" in turn.session.fields_resolved
    assert turn.assistant_message.role == "assistant"


async def test_post_message_no_tool_call_reprompts_same_field(db, test_user, completed_document):
    mock_client = AsyncMock()
    service = CvChatService(db, http_client=mock_client)
    session_response = await service.start_session(str(completed_document.id), test_user.id)

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value={"choices": [{"message": {}}]})  # no tool_calls
    mock_client.post = AsyncMock(return_value=mock_response)
    service._settings.openai_api_key = "sk-test"
    turn = await service.post_message(session_response.session_id, test_user.id, "huh?")

    assert turn.session.fields_resolved == []  # no field resolved yet


async def test_post_message_no_api_key_reprompts_without_http_call(db, test_user, completed_document):
    """When openai_api_key is empty, _call_llm_with_tool short-circuits without an HTTP call."""
    mock_client = AsyncMock()
    service = CvChatService(db, http_client=mock_client)
    session_response = await service.start_session(str(completed_document.id), test_user.id)
    service._settings.openai_api_key = ""

    turn = await service.post_message(session_response.session_id, test_user.id, "550-0100")

    mock_client.post.assert_not_called()
    assert turn.session.fields_resolved == []


async def test_post_message_enforces_turn_limit(db, test_user, completed_document):
    mock_client = AsyncMock()
    service = CvChatService(db, http_client=mock_client)
    service._settings.cv_chat_max_turns = 1  # tight limit for the test
    session_response = await service.start_session(str(completed_document.id), test_user.id)

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value={"choices": [{"message": {}}]})
    mock_client.post = AsyncMock(return_value=mock_response)
    service._settings.openai_api_key = "sk-test"

    await service.post_message(session_response.session_id, test_user.id, "one")
    with pytest.raises(HTTPException) as exc_info:
        await service.post_message(session_response.session_id, test_user.id, "two")
    assert exc_info.value.status_code == 409


async def test_post_message_404_for_unknown_session(db, test_user):
    service = CvChatService(db)
    with pytest.raises(HTTPException) as exc_info:
        await service.post_message(str(uuid4()), test_user.id, "hi")
    assert exc_info.value.status_code == 404


async def test_post_message_rejects_non_active_session(db, test_user, completed_document):
    service = CvChatService(db)
    session_response = await service.start_session(str(completed_document.id), test_user.id)
    session = await service._get_owned_session(session_response.session_id, test_user.id)
    session.status = "completed"
    await db.commit()

    with pytest.raises(HTTPException) as exc_info:
        await service.post_message(session_response.session_id, test_user.id, "hi")
    assert exc_info.value.status_code == 409


async def test_post_message_completes_when_all_fields_already_resolved(db, test_user, completed_document):
    """If missing_fields_at_start minus fields_resolved is empty (e.g. resolved out of band),
    the next post_message call marks the session completed with a 409, rather than crashing."""
    service = CvChatService(db)
    session_response = await service.start_session(str(completed_document.id), test_user.id)
    session = await service._get_owned_session(session_response.session_id, test_user.id)
    session.fields_resolved = list(session.missing_fields_at_start)
    await db.commit()

    with pytest.raises(HTTPException) as exc_info:
        await service.post_message(session_response.session_id, test_user.id, "hi")
    assert exc_info.value.status_code == 409


async def test_post_message_completes_session_after_last_field_resolved(db, test_user):
    """Applying the tool call for the *last* remaining field transitions status to completed
    and returns the closing message, instead of asking another question."""
    doc = CandidateDocument(
        id=uuid4(),
        user_id=test_user.id,
        document_type="cv",
        original_filename="cv.pdf",
        storage_path="documents/x/y.pdf",
        file_hash=f"onefield-{uuid4().hex}",
        file_size_bytes=1000,
        raw_text="Jane Doe",
        extracted_data={
            "phone": "555-0100",
            "linkedin_url": "https://linkedin.com/in/jane",
            "technical_skills": ["python"],
            "total_years_experience": 5.0,
            "desired_roles": ["engineer"],
            "desired_locations": ["remote"],
            "remote_preference": "remote",
            # "email" is the only missing field
        },
        processing_status="completed",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    mock_client = AsyncMock()
    service = CvChatService(db, http_client=mock_client)
    session_response = await service.start_session(str(doc.id), test_user.id)
    assert session_response.missing_fields_at_start == ["email"]

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(
        return_value={
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "record_cv_answer",
                                    "arguments": '{"field_name": "email", "value": "jane@example.com"}',
                                }
                            }
                        ]
                    }
                }
            ]
        }
    )
    mock_client.post = AsyncMock(return_value=mock_response)
    service._settings.openai_api_key = "sk-test"

    turn = await service.post_message(session_response.session_id, test_user.id, "jane@example.com")

    assert turn.session.status == "completed"
    assert "complete" in turn.assistant_message.content.lower()


async def test_call_llm_with_tool_returns_none_on_http_error(db, test_user, completed_document):
    mock_client = AsyncMock()
    service = CvChatService(db, http_client=mock_client)
    service._settings.openai_api_key = "sk-test"
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("boom"))

    result = await service._call_llm_with_tool("phone", "What's your phone?", "555-0100")
    assert result is None


async def test_call_llm_with_tool_returns_none_on_malformed_tool_arguments(db, test_user, completed_document):
    mock_client = AsyncMock()
    service = CvChatService(db, http_client=mock_client)
    service._settings.openai_api_key = "sk-test"

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(
        return_value={
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {"function": {"name": "record_cv_answer", "arguments": "not valid json"}}
                        ]
                    }
                }
            ]
        }
    )
    mock_client.post = AsyncMock(return_value=mock_response)

    result = await service._call_llm_with_tool("phone", "What's your phone?", "555-0100")
    assert result is None


async def test_apply_field_value_splits_comma_separated_list_field(db, test_user, completed_document):
    service = CvChatService(db)
    session_response = await service.start_session(str(completed_document.id), test_user.id)
    session = await service._get_owned_session(session_response.session_id, test_user.id)

    await service._apply_field_value(session, "technical_skills", "python, go , rust,")
    await db.commit()

    result = await db.execute(
        select(CandidateDocument).where(CandidateDocument.id == completed_document.id)
    )
    document = result.scalar_one()
    assert document.extracted_data["technical_skills"] == ["python", "go", "rust"]


async def test_apply_field_value_parses_numeric_years_experience(db, test_user, completed_document):
    service = CvChatService(db)
    session_response = await service.start_session(str(completed_document.id), test_user.id)
    session = await service._get_owned_session(session_response.session_id, test_user.id)

    await service._apply_field_value(session, "total_years_experience", "7.5")
    await db.commit()

    result = await db.execute(
        select(CandidateDocument).where(CandidateDocument.id == completed_document.id)
    )
    document = result.scalar_one()
    assert document.extracted_data["total_years_experience"] == 7.5


async def test_apply_field_value_invalid_years_experience_becomes_none(db, test_user, completed_document):
    service = CvChatService(db)
    session_response = await service.start_session(str(completed_document.id), test_user.id)
    session = await service._get_owned_session(session_response.session_id, test_user.id)

    await service._apply_field_value(session, "total_years_experience", "a lot")
    await db.commit()

    result = await db.execute(
        select(CandidateDocument).where(CandidateDocument.id == completed_document.id)
    )
    document = result.scalar_one()
    assert document.extracted_data["total_years_experience"] is None
