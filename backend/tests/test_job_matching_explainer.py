"""Tests for job match explanation generation (LLM-backed, mocked)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.core.config import Settings
from app.modules.job_matching.explainer import (
    EXPLANATION_SYSTEM_PROMPT,
    _build_explanation_messages,
    generate_match_explanation,
)
from app.modules.job_matching.models import JobMatch, JobPosting


# Override DB setup fixture for this module (pure unit tests, no DB needed).
@pytest.fixture(scope="module", autouse=True)
def skip_db_setup():
    """Skip database migrations for these unit tests."""
    return None


def _make_posting(**overrides) -> JobPosting:
    defaults = {
        "title": "Senior Backend Engineer",
        "company": "Acme Corp",
        "description_raw": "We need a backend engineer with Python and SQL experience.",
    }
    defaults.update(overrides)
    return JobPosting(**defaults)


def _make_match(**overrides) -> JobMatch:
    defaults = {
        "overall_score": 87.5,
        "score_breakdown": {"similarity": 0.9, "salary_fit": 0.8, "location_fit": 1.0},
    }
    defaults.update(overrides)
    return JobMatch(**defaults)


def test_build_explanation_messages_truncates_description_and_includes_facts():
    """User message truncates description_raw to 1500 chars and includes score facts."""
    long_description = "X" * 2000
    posting = _make_posting(
        title="Staff Data Scientist",
        company="Widgets Inc",
        description_raw=long_description,
    )
    match = _make_match(
        overall_score=72.0,
        score_breakdown={"similarity": 0.6, "salary_fit": 0.7, "location_fit": 0.9},
    )

    messages = _build_explanation_messages(match, posting)

    assert len(messages) == 2
    system_message, user_message = messages

    assert system_message["role"] == "system"
    assert system_message["content"] == EXPLANATION_SYSTEM_PROMPT

    assert user_message["role"] == "user"
    content = user_message["content"]
    assert "Staff Data Scientist" in content
    assert "Widgets Inc" in content
    assert "72.0" in content
    assert json.dumps(match.score_breakdown) in content

    # Description is truncated to the first 1500 chars (not the full 2000-char string).
    assert ("X" * 1500) in content
    assert ("X" * 1501) not in content


@pytest.mark.asyncio
async def test_generate_match_explanation_success():
    """Successful API call returns the parsed explanation string."""
    settings = Settings.model_construct(openai_api_key="test-key")
    posting = _make_posting()
    match = _make_match()

    mock_api_response = {
        "choices": [
            {
                "message": {
                    "content": '{"explanation": "This matches because ..."}',
                }
            }
        ],
        "usage": {"prompt_tokens": 321, "completion_tokens": 47},
    }

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        mock_response_obj = Mock()
        mock_response_obj.raise_for_status = Mock(return_value=None)
        mock_response_obj.json = Mock(return_value=mock_api_response)
        mock_client.post = AsyncMock(return_value=mock_response_obj)

        result = await generate_match_explanation(match, posting, settings)

        explanation, token_usage = result
        assert explanation == "This matches because ..."
        assert token_usage == {"input_tokens": 321, "output_tokens": 47}

        assert mock_client.post.called
        call_args = mock_client.post.call_args
        call_kwargs = call_args.kwargs

        assert call_args.args[0] == "https://api.openai.com/v1/chat/completions"
        assert call_kwargs["headers"]["Authorization"] == "Bearer test-key"
        assert call_kwargs["json"]["model"] == "gpt-4o-mini"
        assert call_kwargs["json"]["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_generate_match_explanation_missing_api_key():
    """Missing API key raises ValueError without attempting any HTTP call."""
    settings = Settings.model_construct(openai_api_key="")
    posting = _make_posting()
    match = _make_match()

    with patch("httpx.AsyncClient") as mock_client_class:
        with pytest.raises(ValueError, match="not configured"):
            await generate_match_explanation(match, posting, settings)

        # No client should ever have been constructed/entered/posted to.
        assert not mock_client_class.called


@pytest.mark.asyncio
async def test_generate_match_explanation_whitespace_api_key():
    """Whitespace-only API key is treated as missing (settings.openai_api_key.strip())."""
    settings = Settings.model_construct(openai_api_key="   ")
    posting = _make_posting()
    match = _make_match()

    with patch("httpx.AsyncClient") as mock_client_class:
        with pytest.raises(ValueError, match="not configured"):
            await generate_match_explanation(match, posting, settings)

        assert not mock_client_class.called


@pytest.mark.asyncio
async def test_generate_match_explanation_invalid_json_content():
    """Non-JSON LLM content raises ValueError mentioning invalid JSON."""
    settings = Settings.model_construct(openai_api_key="test-key")
    posting = _make_posting()
    match = _make_match()

    mock_api_response = {
        "choices": [{"message": {"content": "not json at all"}}],
    }

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        mock_response_obj = Mock()
        mock_response_obj.raise_for_status = Mock(return_value=None)
        mock_response_obj.json = Mock(return_value=mock_api_response)
        mock_client.post = AsyncMock(return_value=mock_response_obj)

        with pytest.raises(ValueError, match="Invalid explanation JSON"):
            await generate_match_explanation(match, posting, settings)


@pytest.mark.asyncio
async def test_generate_match_explanation_missing_explanation_key():
    """Valid JSON missing the 'explanation' key yields an empty string, which then

    hits the 'Empty explanation returned' path via data.get("explanation", "") —
    NOT the JSON-decode/KeyError branch.
    """
    settings = Settings.model_construct(openai_api_key="test-key")
    posting = _make_posting()
    match = _make_match()

    mock_api_response = {
        "choices": [{"message": {"content": '{"foo": "bar"}'}}],
    }

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        mock_response_obj = Mock()
        mock_response_obj.raise_for_status = Mock(return_value=None)
        mock_response_obj.json = Mock(return_value=mock_api_response)
        mock_client.post = AsyncMock(return_value=mock_response_obj)

        with pytest.raises(ValueError, match="Empty explanation"):
            await generate_match_explanation(match, posting, settings)


@pytest.mark.asyncio
async def test_generate_match_explanation_whitespace_only_explanation():
    """Whitespace-only 'explanation' value strips to empty and raises ValueError."""
    settings = Settings.model_construct(openai_api_key="test-key")
    posting = _make_posting()
    match = _make_match()

    mock_api_response = {
        "choices": [{"message": {"content": '{"explanation": "   "}'}}],
    }

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        mock_response_obj = Mock()
        mock_response_obj.raise_for_status = Mock(return_value=None)
        mock_response_obj.json = Mock(return_value=mock_api_response)
        mock_client.post = AsyncMock(return_value=mock_response_obj)

        with pytest.raises(ValueError, match="Empty explanation"):
            await generate_match_explanation(match, posting, settings)


@pytest.mark.asyncio
async def test_generate_match_explanation_http_error_propagates():
    """An exception raised by response.raise_for_status() propagates uncaught."""
    settings = Settings.model_construct(openai_api_key="test-key")
    posting = _make_posting()
    match = _make_match()

    def raise_api_error():
        raise Exception("API Error")

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        mock_response_obj = Mock()
        mock_response_obj.raise_for_status = raise_api_error
        mock_client.post = AsyncMock(return_value=mock_response_obj)

        with pytest.raises(Exception, match="API Error"):
            await generate_match_explanation(match, posting, settings)
