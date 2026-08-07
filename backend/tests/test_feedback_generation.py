"""Tests for interview feedback generation service."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.services.feedback_generator import (
    FEEDBACK_DIMENSIONS,
    InterviewFeedback,
    _build_feedback_messages,
    _parse_feedback_response,
    generate_interview_feedback,
)


# Override DB setup fixture for this module
@pytest.fixture(scope="module", autouse=True)
def skip_db_setup():
    """Skip database migrations for these unit tests."""
    return None


def test_feedback_dimensions_defined():
    """Verify all rubric dimensions are defined."""
    assert len(FEEDBACK_DIMENSIONS) == 4
    assert "clarity" in FEEDBACK_DIMENSIONS
    assert "technical_accuracy" in FEEDBACK_DIMENSIONS
    assert "completeness" in FEEDBACK_DIMENSIONS
    assert "communication_skills" in FEEDBACK_DIMENSIONS


def test_build_feedback_messages():
    """Messages include system prompt and user question/answer."""
    question = "Explain REST APIs"
    answer = "REST is..."

    messages = _build_feedback_messages(question, answer)

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert "rubric" in messages[0]["content"].lower()
    assert messages[1]["role"] == "user"
    assert question in messages[1]["content"]
    assert answer in messages[1]["content"]


def test_parse_feedback_response_valid():
    """Valid JSON response parses correctly."""
    content = """
    {
        "overall_score": 85.5,
        "dimension_scores": {
            "clarity": 22.0,
            "technical_accuracy": 20.5,
            "completeness": 21.0,
            "communication_skills": 22.0
        },
        "strengths": [
            "Clear explanation",
            "Good examples"
        ],
        "improvements": [
            "Add more detail",
            "Improve structure"
        ],
        "detailed_feedback": "This is detailed feedback."
    }
    """

    feedback = _parse_feedback_response(content, strict=True)

    assert feedback["overall_score"] == 85.5
    assert len(feedback["dimension_scores"]) == 4
    assert feedback["dimension_scores"]["clarity"] == 22.0
    assert len(feedback["strengths"]) == 2
    assert len(feedback["improvements"]) == 2
    assert "detailed feedback" in feedback["detailed_feedback"].lower()


def test_parse_feedback_response_clamps_scores():
    """Out-of-range scores are clamped to valid ranges."""
    content = """
    {
        "overall_score": 150.0,
        "dimension_scores": {
            "clarity": 30.0,
            "technical_accuracy": -5.0,
            "completeness": 15.0,
            "communication_skills": 20.0
        },
        "strengths": ["Good"],
        "improvements": ["Better"],
        "detailed_feedback": "Feedback"
    }
    """

    feedback = _parse_feedback_response(content, strict=False)

    # Overall score clamped to 100
    assert feedback["overall_score"] == 100.0

    # Dimension scores clamped to 0-25
    assert feedback["dimension_scores"]["clarity"] == 25.0
    assert feedback["dimension_scores"]["technical_accuracy"] == 0.0
    assert feedback["dimension_scores"]["completeness"] == 15.0


def test_parse_feedback_response_invalid_json_strict():
    """Invalid JSON raises error in strict mode."""
    content = "Not valid JSON at all"

    with pytest.raises(ValueError, match="Invalid feedback JSON"):
        _parse_feedback_response(content, strict=True)


def test_parse_feedback_response_invalid_json_fallback():
    """Invalid JSON returns fallback in non-strict mode."""
    content = "Not valid JSON at all"

    feedback = _parse_feedback_response(content, strict=False)

    # Fallback values
    assert feedback["overall_score"] == 50.0
    assert len(feedback["dimension_scores"]) == 4
    assert all(v == 12.5 for v in feedback["dimension_scores"].values())
    assert feedback["strengths"] == ["Response provided"]
    assert "Unable to generate" in feedback["detailed_feedback"]


def test_parse_feedback_response_missing_fields():
    """Missing fields handled gracefully."""
    content = """
    {
        "overall_score": 70.0,
        "dimension_scores": {}
    }
    """

    feedback = _parse_feedback_response(content, strict=False)

    assert feedback["overall_score"] == 70.0
    assert feedback["strengths"] == []
    assert feedback["improvements"] == []
    assert feedback["detailed_feedback"] == ""


@pytest.mark.asyncio
async def test_generate_interview_feedback_empty_answer():
    """Empty answer returns zero-score feedback without API call."""
    settings = Settings(openai_api_key="test-key")

    feedback, tokens = await generate_interview_feedback(
        question="Explain REST",
        answer="",
        settings=settings,
    )

    assert feedback["overall_score"] == 0.0
    assert all(v == 0.0 for v in feedback["dimension_scores"].values())
    assert "no answer" in feedback["detailed_feedback"].lower()
    assert tokens["input_tokens"] == 0
    assert tokens["output_tokens"] == 0


@pytest.mark.asyncio
async def test_generate_interview_feedback_no_api_key():
    """Missing API key raises ValueError."""
    settings = Settings(openai_api_key="")

    with pytest.raises(ValueError, match="OpenAI API key not configured"):
        await generate_interview_feedback(
            question="Explain REST",
            answer="REST is...",
            settings=settings,
        )


@pytest.mark.asyncio
async def test_generate_interview_feedback_success():
    """Successful API call returns valid feedback."""
    settings = Settings.model_construct(openai_api_key="test-key")

    mock_response = {
        "choices": [
            {
                "message": {
                    "content": """
                    {
                        "overall_score": 82.0,
                        "dimension_scores": {
                            "clarity": 21.0,
                            "technical_accuracy": 20.0,
                            "completeness": 20.0,
                            "communication_skills": 21.0
                        },
                        "strengths": ["Clear explanation", "Good examples"],
                        "improvements": ["Add more depth", "Include edge cases"],
                        "detailed_feedback": "Strong answer with good examples."
                    }
                    """
                }
            }
        ],
        "usage": {
            "prompt_tokens": 150,
            "completion_tokens": 200,
        },
    }

    with patch("httpx.AsyncClient") as mock_client_class:
        # Create mock client instance
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock the post response
        mock_response_obj = AsyncMock()
        mock_response_obj.raise_for_status = lambda: None
        mock_response_obj.json = AsyncMock(return_value=mock_response)
        mock_client.post = AsyncMock(return_value=mock_response_obj)

        feedback, tokens = await generate_interview_feedback(
            question="Explain REST APIs",
            answer="REST is an architectural style...",
            settings=settings,
        )

        # Verify API was called
        assert mock_client.post.called
        call_args = mock_client.post.call_args
        call_kwargs = call_args.kwargs

        assert "https://api.openai.com" in call_args.args[0]
        assert call_kwargs["headers"]["Authorization"] == "Bearer test-key"
        assert call_kwargs["json"]["model"] == "gpt-4o-mini"
        assert call_kwargs["json"]["response_format"]["type"] == "json_object"
        assert call_kwargs["json"]["temperature"] == 0.3

        # Verify feedback structure
        assert feedback["overall_score"] == 82.0
        assert len(feedback["dimension_scores"]) == 4
        assert len(feedback["strengths"]) == 2
        assert len(feedback["improvements"]) == 2
        assert "strong answer" in feedback["detailed_feedback"].lower()

        # Verify token usage
        assert tokens["input_tokens"] == 150
        assert tokens["output_tokens"] == 200


@pytest.mark.asyncio
async def test_generate_interview_feedback_api_error():
    """API errors are propagated."""
    settings = Settings.model_construct(openai_api_key="test-key")

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock response that raises error
        def raise_api_error():
            raise Exception("API Error")
        
        mock_response_obj = AsyncMock()
        mock_response_obj.raise_for_status = raise_api_error
        mock_client.post = AsyncMock(return_value=mock_response_obj)

        with pytest.raises(Exception, match="API Error"):
            await generate_interview_feedback(
                question="Explain REST",
                answer="REST is...",
                settings=settings,
            )


def test_feedback_structure_type():
    """InterviewFeedback TypedDict has correct structure."""
    feedback: InterviewFeedback = {
        "overall_score": 85.0,
        "dimension_scores": {
            "clarity": 22.0,
            "technical_accuracy": 21.0,
            "completeness": 21.0,
            "communication_skills": 21.0,
        },
        "strengths": ["Clear", "Accurate"],
        "improvements": ["More detail"],
        "detailed_feedback": "Good work",
    }

    assert isinstance(feedback["overall_score"], float)
    assert isinstance(feedback["dimension_scores"], dict)
    assert isinstance(feedback["strengths"], list)
    assert isinstance(feedback["improvements"], list)
    assert isinstance(feedback["detailed_feedback"], str)


@pytest.mark.asyncio
async def test_generate_feedback_token_usage_tracking():
    """Token usage is correctly extracted from API response."""
    settings = Settings.model_construct(openai_api_key="test-key")

    mock_response = {
        "choices": [
            {
                "message": {
                    "content": """
                    {
                        "overall_score": 75.0,
                        "dimension_scores": {"clarity": 18.0, "technical_accuracy": 19.0, "completeness": 19.0, "communication_skills": 19.0},
                        "strengths": ["Good"],
                        "improvements": ["Better"],
                        "detailed_feedback": "Feedback"
                    }
                    """
                }
            }
        ],
        "usage": {
            "prompt_tokens": 250,
            "completion_tokens": 150,
        },
    }

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        mock_response_obj = AsyncMock()
        mock_response_obj.raise_for_status = AsyncMock()
        mock_response_obj.json = AsyncMock(return_value=mock_response)
        mock_client.post = AsyncMock(return_value=mock_response_obj)

        _, tokens = await generate_interview_feedback(
            question="Test question",
            answer="Test answer",
            settings=settings,
        )

        # Verify cost calculation
        input_cost = (250 / 1_000_000) * 0.15  # $0.15 per 1M tokens
        output_cost = (150 / 1_000_000) * 0.60  # $0.60 per 1M tokens
        total_cost = input_cost + output_cost

        assert tokens["input_tokens"] == 250
        assert tokens["output_tokens"] == 150
        # Cost should be around $0.000128
        assert total_cost < 0.001  # Less than 0.1 cents
