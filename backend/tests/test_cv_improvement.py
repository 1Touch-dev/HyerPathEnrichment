"""Tests for generate_cv_improvement() and its parser."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.services.feedback_generator import _parse_cv_improvement_response, generate_cv_improvement


def test_parse_cv_improvement_response_valid_json():
    content = (
        '{"ats_score": 72, "strengths": ["Clear structure"], '
        '"improvements": ["Add metrics"], '
        '"rewritten_bullets": [{"original": "Made code faster", '
        '"rewritten": "Reduced API latency by optimizing caching", "rationale": "Adds impact"}]}'
    )
    result = _parse_cv_improvement_response(content)
    assert result["ats_score"] == 72
    assert len(result["rewritten_bullets"]) == 1
    assert result["rewritten_bullets"][0]["original"] == "Made code faster"


def test_parse_cv_improvement_response_malformed_falls_back():
    result = _parse_cv_improvement_response("not json at all")
    assert result["ats_score"] == 0
    assert result["rewritten_bullets"] == []


def test_parse_cv_improvement_response_clamps_score_high():
    content = '{"ats_score": 150, "strengths": [], "improvements": [], "rewritten_bullets": []}'
    result = _parse_cv_improvement_response(content)
    assert result["ats_score"] == 100


def test_parse_cv_improvement_response_clamps_score_low():
    content = '{"ats_score": -10, "strengths": [], "improvements": [], "rewritten_bullets": []}'
    result = _parse_cv_improvement_response(content)
    assert result["ats_score"] == 0


def test_parse_cv_improvement_response_caps_bullets_and_lists():
    bullets = ", ".join(
        f'{{"original": "orig {i}", "rewritten": "new {i}", "rationale": "r{i}"}}' for i in range(8)
    )
    strengths = ", ".join(f'"s{i}"' for i in range(8))
    improvements = ", ".join(f'"i{i}"' for i in range(8))
    content = (
        f'{{"ats_score": 50, "strengths": [{strengths}], '
        f'"improvements": [{improvements}], "rewritten_bullets": [{bullets}]}}'
    )
    result = _parse_cv_improvement_response(content)
    assert len(result["rewritten_bullets"]) == 5
    assert len(result["strengths"]) == 4
    assert len(result["improvements"]) == 4


def test_parse_cv_improvement_response_drops_incomplete_bullets():
    content = (
        '{"ats_score": 50, "strengths": [], "improvements": [], '
        '"rewritten_bullets": [{"original": "", "rewritten": "x", "rationale": "y"}, '
        '{"original": "ok", "rewritten": "better", "rationale": "why"}]}'
    )
    result = _parse_cv_improvement_response(content)
    assert len(result["rewritten_bullets"]) == 1
    assert result["rewritten_bullets"][0]["original"] == "ok"


def test_parse_cv_improvement_response_non_list_fields_default_to_empty():
    """If the LLM returns strengths/improvements/rewritten_bullets as the wrong type
    (e.g. a string instead of a list), each defaults to an empty list rather than raising."""
    content = (
        '{"ats_score": 50, "strengths": "not a list", "improvements": "also not a list", '
        '"rewritten_bullets": "still not a list"}'
    )
    result = _parse_cv_improvement_response(content)
    assert result["strengths"] == []
    assert result["improvements"] == []
    assert result["rewritten_bullets"] == []


async def test_generate_cv_improvement_empty_text_short_circuits():
    settings = Settings(openai_api_key="sk-test")
    result, tokens = await generate_cv_improvement("", None, settings)
    assert result["ats_score"] == 0
    assert tokens == {"input_tokens": 0, "output_tokens": 0}


async def test_generate_cv_improvement_no_api_key_raises():
    settings = Settings(openai_api_key="")
    with pytest.raises(ValueError):
        await generate_cv_improvement("Some CV text here", None, settings)


async def test_generate_cv_improvement_calls_openai_and_parses():
    settings = Settings(openai_api_key="sk-test")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(
        return_value={
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"ats_score": 80, "strengths": [], "improvements": [], '
                            '"rewritten_bullets": []}'
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }
    )
    with patch("app.services.feedback_generator.httpx.AsyncClient") as mock_client_cls:
        mock_post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__.return_value.post = mock_post
        result, tokens = await generate_cv_improvement("Some CV text here", "Software Engineer", settings)

    assert result["ats_score"] == 80
    assert tokens["input_tokens"] == 100
    assert tokens["output_tokens"] == 50


async def test_generate_cv_improvement_truncates_long_cv_text():
    settings = Settings(openai_api_key="sk-test")
    long_text = "x" * 20000

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(
        return_value={
            "choices": [{"message": {"content": '{"ats_score": 10, "strengths": [], "improvements": [], "rewritten_bullets": []}'}}],
            "usage": {},
        }
    )
    with patch("app.services.feedback_generator.httpx.AsyncClient") as mock_client_cls:
        mock_post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__.return_value.post = mock_post
        await generate_cv_improvement(long_text, None, settings)

    sent_kwargs = mock_post.call_args.kwargs
    sent_content = sent_kwargs["json"]["messages"][1]["content"]
    assert len(sent_content) <= 12000 + len("CV text:\n")
