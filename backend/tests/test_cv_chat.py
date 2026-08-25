"""Tests for CvChatService. OpenAI calls mocked per RULE.md 'no live external calls in CI'."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.auth.models import User
from app.clients.llm_tools import RECORD_CV_ANSWER_TOOL
from app.domain.cv_completeness import PROGRESSIVE_FIELDS
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
        extracted_data={"email": "jane@example.com"},  # 1 of 11 required fields present
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


async def test_get_session_returns_owned_session(db, test_user, completed_document):
    service = CvChatService(db)
    started = await service.start_session(str(completed_document.id), test_user.id)
    fetched = await service.get_session(started.session_id, test_user.id)
    assert fetched.session_id == started.session_id
    assert fetched.document_id == str(completed_document.id)
    assert len(fetched.messages) >= 1


async def test_get_session_404_for_invalid_uuid(db, test_user):
    service = CvChatService(db)
    with pytest.raises(HTTPException) as exc_info:
        await service.get_session("608992a1-4b5d-4f59-ac87-64f437869f3", test_user.id)
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Chat session not found"


async def test_get_session_404_for_other_user(db, test_user, completed_document):
    service = CvChatService(db)
    started = await service.start_session(str(completed_document.id), test_user.id)
    with pytest.raises(HTTPException) as exc_info:
        await service.get_session(started.session_id, uuid4())
    assert exc_info.value.status_code == 404


async def test_start_session_no_missing_fields_asks_progressive_question(db, test_user):
    """With all REQUIRED_FIELDS present but no progressive fields answered yet, the session
    stays active and asks the first progressive question instead of completing immediately —
    completion now requires both required AND progressive fields to be resolved."""
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
            "github_url": "https://github.com/jane",
            "portfolio_url": "https://jane.dev",
            "technical_skills": ["python"],
            "total_years_experience": 5.0,
            "highest_degree": "BS Computer Science",
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

    assert response.status == "active"
    assert response.missing_fields_at_start == []
    assert len(response.messages) == 1
    assert response.messages[0].role == "assistant"
    assert response.messages[0].field_name == "interests"


async def test_start_session_all_fields_present_completes_immediately(db, test_user):
    """Only when both required AND progressive fields are already present does start_session
    mark the session completed immediately, with no greeting message."""
    doc = CandidateDocument(
        id=uuid4(),
        user_id=test_user.id,
        document_type="cv",
        original_filename="cv.pdf",
        storage_path="documents/x/y.pdf",
        file_hash="fullcv-and-progressive",
        file_size_bytes=1000,
        raw_text="Jane Doe",
        extracted_data={
            "email": "jane@example.com",
            "phone": "555-0100",
            "linkedin_url": "https://linkedin.com/in/jane",
            "github_url": "https://github.com/jane",
            "portfolio_url": "https://jane.dev",
            "technical_skills": ["python"],
            "total_years_experience": 5.0,
            "highest_degree": "BS Computer Science",
            "desired_roles": ["engineer"],
            "desired_locations": ["remote"],
            "remote_preference": "remote",
            "interests": ["hiking"],
            "learning_style": "hands_on",
            "prep_timeline_weeks": 4,
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


async def test_post_message_no_api_key_reprompts_without_http_call(
    db, test_user, completed_document
):
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


async def test_post_message_completes_when_all_fields_already_resolved(
    db, test_user, completed_document
):
    """If missing_fields_at_start and PROGRESSIVE_FIELDS minus fields_resolved are both empty
    (e.g. resolved out of band), the next post_message call marks the session completed with a
    409, rather than crashing."""
    service = CvChatService(db)
    session_response = await service.start_session(str(completed_document.id), test_user.id)
    session = await service._get_owned_session(session_response.session_id, test_user.id)
    session.fields_resolved = [*session.missing_fields_at_start, *PROGRESSIVE_FIELDS]
    await db.commit()

    with pytest.raises(HTTPException) as exc_info:
        await service.post_message(session_response.session_id, test_user.id, "hi")
    assert exc_info.value.status_code == 409


async def test_post_message_advances_to_progressive_after_last_required_field_resolved(
    db, test_user
):
    """Applying the tool call for the *last* remaining required field transitions the session
    into the progressive-profiling phase (asks the first progressive question) instead of
    completing — completion now requires progressive fields too."""
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
            "github_url": "https://github.com/jane",
            "portfolio_url": "https://jane.dev",
            "technical_skills": ["python"],
            "total_years_experience": 5.0,
            "highest_degree": "BS Computer Science",
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

    assert turn.session.status == "active"
    assert "email" in turn.session.fields_resolved
    assert turn.assistant_message.field_name == "interests"


async def test_call_llm_with_tool_returns_none_on_http_error(db, test_user, completed_document):
    mock_client = AsyncMock()
    service = CvChatService(db, http_client=mock_client)
    service._settings.openai_api_key = "sk-test"
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("boom"))

    result = await service._call_llm_with_tool("phone", "What's your phone?", "555-0100")
    assert result is None


async def test_call_llm_with_tool_returns_none_on_malformed_tool_arguments(
    db, test_user, completed_document
):
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
                            {
                                "function": {
                                    "name": "record_cv_answer",
                                    "arguments": "not valid json",
                                }
                            }
                        ]
                    }
                }
            ]
        }
    )
    mock_client.post = AsyncMock(return_value=mock_response)

    result = await service._call_llm_with_tool("phone", "What's your phone?", "555-0100")
    assert result is None


async def test_apply_field_value_splits_comma_separated_list_field(
    db, test_user, completed_document
):
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


async def test_apply_field_value_invalid_years_experience_becomes_none(
    db, test_user, completed_document
):
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


def test_record_cv_answer_tool_is_strict_mode():
    """OpenAI strict mode requires an explicit opt-in; verify it's set on the shared tool schema."""
    assert RECORD_CV_ANSWER_TOOL["function"]["strict"] is True
    properties = RECORD_CV_ANSWER_TOOL["function"]["parameters"]["properties"]
    required = RECORD_CV_ANSWER_TOOL["function"]["parameters"]["required"]
    # Strict mode requires every property to be listed in `required` (nullable, not omitted).
    assert set(properties.keys()) == {"field_name", "value", "values"}
    assert set(required) == {"field_name", "value", "values"}


async def test_post_message_uses_values_array_for_list_field(db, test_user):
    """A tool call returning `values: [...]` (strict-mode array) for a list field must land
    as an actual list in extracted_data, not get flattened into a single joined string."""
    doc = CandidateDocument(
        id=uuid4(),
        user_id=test_user.id,
        document_type="cv",
        original_filename="cv.pdf",
        storage_path="documents/x/y.pdf",
        file_hash=f"skills-only-{uuid4().hex}",
        file_size_bytes=1000,
        raw_text="Jane Doe",
        extracted_data={
            "email": "jane@example.com",
            "phone": "555-0100",
            "linkedin_url": "https://linkedin.com/in/jane",
            "github_url": "https://github.com/jane",
            "portfolio_url": "https://jane.dev",
            "total_years_experience": 5.0,
            "highest_degree": "BS Computer Science",
            "desired_roles": ["engineer"],
            "desired_locations": ["remote"],
            "remote_preference": "remote",
            # "technical_skills" is the only missing field
        },
        processing_status="completed",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    mock_client = AsyncMock()
    service = CvChatService(db, http_client=mock_client)
    session_response = await service.start_session(str(doc.id), test_user.id)
    assert session_response.missing_fields_at_start == ["technical_skills"]

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
                                    "arguments": (
                                        '{"field_name": "technical_skills", "value": null, '
                                        '"values": ["Python", "SQL", "Go"]}'
                                    ),
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

    turn = await service.post_message(
        session_response.session_id, test_user.id, "Python, SQL, and Go"
    )

    assert "technical_skills" in turn.session.fields_resolved
    result = await db.execute(select(CandidateDocument).where(CandidateDocument.id == doc.id))
    document = result.scalar_one()
    assert document.extracted_data["technical_skills"] == ["Python", "SQL", "Go"]


async def test_call_llm_with_tool_retries_transient_error_then_succeeds(
    db, test_user, completed_document
):
    """The first HTTP call raises a transient error (503); the retry helper should retry
    and succeed on the second attempt rather than failing the whole turn."""
    mock_client = AsyncMock()
    service = CvChatService(db, http_client=mock_client)
    service._settings.openai_api_key = "sk-test"

    transient_error = httpx.HTTPStatusError(
        "Service Unavailable", request=MagicMock(), response=MagicMock(status_code=503)
    )

    success_response = MagicMock()
    success_response.raise_for_status = MagicMock()
    success_response.json = MagicMock(
        return_value={
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "record_cv_answer",
                                    "arguments": '{"field_name": "phone", "value": "555-0100", "values": null}',
                                }
                            }
                        ]
                    }
                }
            ]
        }
    )

    mock_client.post = AsyncMock(side_effect=[transient_error, success_response])

    result = await service._call_llm_with_tool("phone", "What's your phone?", "555-0100")

    assert result == ("phone", "555-0100")
    assert mock_client.post.call_count == 2


async def test_post_message_completes_turn_after_transient_retry(db, test_user, completed_document):
    """End-to-end: post_message still completes the turn when the first LLM call is
    transiently rejected and the second succeeds."""
    mock_client = AsyncMock()
    service = CvChatService(db, http_client=mock_client)
    session_response = await service.start_session(str(completed_document.id), test_user.id)
    service._settings.openai_api_key = "sk-test"

    transient_error = httpx.HTTPStatusError(
        "Service Unavailable", request=MagicMock(), response=MagicMock(status_code=503)
    )

    success_response = MagicMock()
    success_response.raise_for_status = MagicMock()
    success_response.json = MagicMock(
        return_value={
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "record_cv_answer",
                                    "arguments": '{"field_name": "phone", "value": "555-0100", "values": null}',
                                }
                            }
                        ]
                    }
                }
            ]
        }
    )

    mock_client.post = AsyncMock(side_effect=[transient_error, success_response])

    turn = await service.post_message(session_response.session_id, test_user.id, "It's 555-0100")

    assert "phone" in turn.session.fields_resolved
    assert mock_client.post.call_count == 2


def _tool_call_response(field_name: str, value: str) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(
        return_value={
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "record_cv_answer",
                                    "arguments": (
                                        f'{{"field_name": "{field_name}", "value": "{value}"}}'
                                    ),
                                }
                            }
                        ]
                    }
                }
            ]
        }
    )
    return resp


def _text_response(content: str) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value={"choices": [{"message": {"content": content}}]})
    return resp


def _all_required_fields_extracted_data() -> dict:
    return {
        "email": "jane@example.com",
        "phone": "555-0100",
        "linkedin_url": "https://linkedin.com/in/jane",
        "github_url": "https://github.com/jane",
        "portfolio_url": "https://jane.dev",
        "technical_skills": ["python"],
        "total_years_experience": 5.0,
        "highest_degree": "BS Computer Science",
        "desired_roles": ["engineer"],
        "desired_locations": ["remote"],
        "remote_preference": "remote",
    }


async def test_start_session_asks_first_progressive_question_when_required_complete(db, test_user):
    """A CVData with all REQUIRED_FIELDS resolved and no progressive fields answered yet does
    NOT complete the session — it asks the first progressive question (interests) next."""
    doc = CandidateDocument(
        id=uuid4(),
        user_id=test_user.id,
        document_type="cv",
        original_filename="cv.pdf",
        storage_path="documents/x/y.pdf",
        file_hash=f"progressive-start-{uuid4().hex}",
        file_size_bytes=1000,
        raw_text="Jane Doe",
        extracted_data=_all_required_fields_extracted_data(),
        processing_status="completed",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    service = CvChatService(db)
    response = await service.start_session(str(doc.id), test_user.id)

    assert response.status == "active"
    assert response.missing_fields_at_start == []
    assert len(response.messages) == 1
    assert response.messages[0].field_name == "interests"


async def test_post_message_prep_strategy_suggestion_fires_exactly_once(db, test_user):
    """Answering learning_style then prep_timeline_weeks (order-independent per the tool's
    reported field_name) triggers the prep-strategy-suggestion LLM call exactly once, even
    though the session continues afterward (interests is still unanswered)."""
    doc = CandidateDocument(
        id=uuid4(),
        user_id=test_user.id,
        document_type="cv",
        original_filename="cv.pdf",
        storage_path="documents/x/y.pdf",
        file_hash=f"prep-strategy-{uuid4().hex}",
        file_size_bytes=1000,
        raw_text="Jane Doe",
        extracted_data=_all_required_fields_extracted_data(),
        processing_status="completed",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    mock_client = AsyncMock()
    service = CvChatService(db, http_client=mock_client)
    session_response = await service.start_session(str(doc.id), test_user.id)
    service._settings.openai_api_key = "sk-test"
    # get_settings() is process-wide lru_cache'd, so an earlier test in this module
    # (test_post_message_enforces_turn_limit) mutating cv_chat_max_turns leaks into this
    # Settings singleton; reset it here so this multi-turn test is self-contained regardless
    # of execution order.
    service._settings.cv_chat_max_turns = 20

    tool_responses = iter(
        [
            _tool_call_response("learning_style", "hands_on"),
            _tool_call_response("prep_timeline_weeks", "4"),
            _tool_call_response("interests", "hiking, chess"),
        ]
    )
    generation_response = _text_response("Focus on mock interviews early, then drill weak spots.")
    generation_call_count = [0]

    async def _post_side_effect(*args, **kwargs):
        payload = kwargs["json"]
        if "tools" in payload:
            return next(tool_responses)
        generation_call_count[0] += 1
        return generation_response

    mock_client.post = AsyncMock(side_effect=_post_side_effect)

    turn1 = await service.post_message(session_response.session_id, test_user.id, "hands on")
    assert "learning_style" in turn1.session.fields_resolved
    assert generation_call_count[0] == 0  # only one of the two prep-relevant fields is known

    turn2 = await service.post_message(session_response.session_id, test_user.id, "4 weeks")
    assert "prep_timeline_weeks" in turn2.session.fields_resolved
    assert generation_call_count[0] == 1  # both prep-relevant fields now known: fires once
    assert turn2.session.status == "active"  # interests still unanswered

    result = await service.db.execute(
        select(CandidateDocument).where(CandidateDocument.id == doc.id)
    )
    document = result.scalar_one()
    assert document.extracted_data["prep_strategy_suggestion"] == (
        "Focus on mock interviews early, then drill weak spots."
    )

    session_after_turn2 = await service._session_response(
        await service._get_owned_session(session_response.session_id, test_user.id)
    )
    suggestion_messages = [
        m
        for m in session_after_turn2.messages
        if m.content.startswith("One more thing before we wrap up —")
    ]
    assert len(suggestion_messages) == 1

    turn3 = await service.post_message(session_response.session_id, test_user.id, "hiking, chess")
    assert "interests" in turn3.session.fields_resolved
    assert turn3.session.status == "completed"
    assert generation_call_count[0] == 1  # unchanged: no double-generation on later messages


async def test_apply_field_value_stores_interests_as_list(db, test_user, completed_document):
    """`interests` is a list field like technical_skills/desired_roles/desired_locations, so a
    comma-separated answer must be split into a real list, not left as one joined string."""
    service = CvChatService(db)
    session_response = await service.start_session(str(completed_document.id), test_user.id)
    session = await service._get_owned_session(session_response.session_id, test_user.id)

    await service._apply_field_value(session, "interests", "hiking, chess, cooking")
    await db.commit()

    result = await db.execute(
        select(CandidateDocument).where(CandidateDocument.id == completed_document.id)
    )
    document = result.scalar_one()
    assert document.extracted_data["interests"] == ["hiking", "chess", "cooking"]
