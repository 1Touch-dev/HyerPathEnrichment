"""LLM provider: prompt assembly, parse hardening, and backend wiring."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.config import Settings
from app.clients.llm import (
    LLMDecision,
    _parse_decision,
    build_disambiguation_messages,
    heuristic_compare,
    ollama_compare,
)


def test_build_disambiguation_messages_structure() -> None:
    messages = build_disambiguation_messages(
        "jane-doe | jane@acme.com",
        "X | jane_doe | https://x.com/jane_doe",
    )

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "jane-doe | jane@acme.com" in messages[1]["content"]
    assert "X | jane_doe | https://x.com/jane_doe" in messages[1]["content"]
    assert "same_identity" in messages[0]["content"]


def test_parse_decision_valid_json() -> None:
    fallback = LLMDecision(same_identity=False, confidence=0.1, reason="fallback")
    content = 'Here is the result:\n{"same_identity": true, "confidence": 0.85, "reason": "match"}'

    decision = _parse_decision(content, fallback)

    assert decision.same_identity is True
    assert decision.confidence == pytest.approx(0.85)
    assert decision.reason == "match"


def test_parse_decision_clamps_confidence() -> None:
    fallback = LLMDecision(same_identity=False, confidence=0.1, reason="fallback")
    content = '{"same_identity": true, "confidence": 1.5, "reason": "high"}'

    decision = _parse_decision(content, fallback)

    assert decision.confidence == pytest.approx(1.0)


def test_parse_decision_malformed_fallback() -> None:
    fallback = LLMDecision(same_identity=False, confidence=0.1, reason="fallback")

    decision = _parse_decision("not json at all", fallback)

    assert decision is fallback


def test_heuristic_compare_username_variant() -> None:
    decision = heuristic_compare(
        "jane-doe | jane@acme.com",
        "X | jane_doe | https://x.com/jane_doe",
    )

    assert decision.same_identity is True
    assert decision.confidence == pytest.approx(0.91)


def test_heuristic_compare_rejects_unrelated() -> None:
    decision = heuristic_compare(
        "jane-doe | jane@acme.com",
        "GitHub | totally-unrelated-bot | https://github.com/totally-unrelated-bot",
    )

    assert decision.same_identity is False
    assert decision.confidence == pytest.approx(0.24)


@pytest.mark.asyncio
async def test_ollama_compare_uses_messages() -> None:
    settings = Settings(
        OLLAMA_BASE_URL="http://ollama:11434",
        OLLAMA_MODEL="llama3.1",
    )
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "message": {
            "content": '{"same_identity": true, "confidence": 0.8, "reason": "ok"}',
        },
    }

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.clients.llm.httpx.AsyncClient", return_value=mock_client):
        decision = await ollama_compare("jane-doe", "X | jane_doe | https://x.com/jane_doe", settings)

    assert decision.same_identity is True
    assert decision.confidence == pytest.approx(0.8)
    payload = mock_client.post.await_args.kwargs["json"]
    roles = [msg["role"] for msg in payload["messages"]]
    assert roles == ["system", "user"]


@pytest.mark.asyncio
async def test_ollama_compare_http_failure_fallback() -> None:
    settings = Settings(
        OLLAMA_BASE_URL="http://ollama:11434",
        OLLAMA_MODEL="llama3.1",
    )

    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("down"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.clients.llm.httpx.AsyncClient", return_value=mock_client):
        decision = await ollama_compare(
            "jane-doe | jane@acme.com",
            "GitHub | totally-unrelated-bot | https://github.com/totally-unrelated-bot",
            settings,
        )

    assert decision.same_identity is False
    assert decision.confidence == pytest.approx(0.24)
