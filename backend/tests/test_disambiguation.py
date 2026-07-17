"""LLM handle disambiguation: keep/drop by DISAMBIGUATION_THRESHOLD."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.domain.enrichment import EnrichmentRequest
from app.domain.dossier import SocialHandle
from app.core.config import get_settings
from app.clients.llm import LLMDecision
from app.enrichers.pipeline import Pipeline


@pytest.fixture
def orchestrator() -> Pipeline:
    return Pipeline(db=AsyncMock())


@pytest.fixture
def request_identity() -> EnrichmentRequest:
    return EnrichmentRequest(username="jane-doe", email="jane@acme.com", requested_tiers=["tier2", "tier3"])


def _handle(platform: str, username: str, confidence: float) -> SocialHandle:
    return SocialHandle(
        platform=platform,
        username=username,
        profile_url=f"https://example.com/{username}",
        confidence=confidence,
    )


@pytest.mark.asyncio
async def test_low_conf_handle_kept_when_llm_confirms(
    orchestrator: Pipeline,
    request_identity: EnrichmentRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "disambiguation_threshold", 0.7)
    orchestrator.llm.compare = AsyncMock(
        return_value=LLMDecision(same_identity=True, confidence=0.85, reason="match")
    )

    kept, dropped = await orchestrator._disambiguate_handles(
        request_identity,
        [_handle("X", "jane-doe", 0.4), _handle("GitHub", "jane-doe", 0.9)],
    )

    assert dropped == 0
    assert len(kept) == 2
    low = next(h for h in kept if h.platform == "X")
    assert low.confidence == pytest.approx(0.85)
    orchestrator.llm.compare.assert_awaited_once()


@pytest.mark.asyncio
async def test_low_conf_handle_dropped_when_llm_rejects(
    orchestrator: Pipeline,
    request_identity: EnrichmentRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "disambiguation_threshold", 0.7)
    orchestrator.llm.compare = AsyncMock(
        return_value=LLMDecision(same_identity=False, confidence=0.2, reason="different person")
    )

    kept, dropped = await orchestrator._disambiguate_handles(
        request_identity,
        [_handle("X", "random-user", 0.4), _handle("GitHub", "jane-doe", 0.9)],
    )

    assert dropped == 1
    assert len(kept) == 1
    assert kept[0].platform == "GitHub"
    assert kept[0].confidence == pytest.approx(0.9)
    orchestrator.llm.compare.assert_awaited_once()


@pytest.mark.asyncio
async def test_low_conf_dropped_when_llm_confidence_below_threshold(
    orchestrator: Pipeline,
    request_identity: EnrichmentRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "disambiguation_threshold", 0.7)
    orchestrator.llm.compare = AsyncMock(
        return_value=LLMDecision(same_identity=True, confidence=0.55, reason="weak match")
    )

    kept, dropped = await orchestrator._disambiguate_handles(
        request_identity,
        [_handle("Reddit", "maybe-jane", 0.3)],
    )

    assert dropped == 1
    assert kept == []


@pytest.mark.asyncio
async def test_merge_applies_disambiguation(
    orchestrator: Pipeline,
    request_identity: EnrichmentRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "disambiguation_threshold", 0.7)
    orchestrator.llm.compare = AsyncMock(
        return_value=LLMDecision(same_identity=False, confidence=0.1, reason="no")
    )

    payloads: list[dict[str, Any]] = [
        {
            "handles": [
                {
                    "platform": "X",
                    "username": "noise",
                    "profile_url": "https://x.com/noise",
                    "confidence": 0.35,
                },
                {
                    "platform": "GitHub",
                    "username": "jane-doe",
                    "profile_url": "https://github.com/jane-doe",
                    "confidence": 0.9,
                },
            ],
            "sources": ["test"],
        }
    ]

    dossier = await orchestrator._merge(request_identity, payloads)

    assert len(dossier.handles) == 1
    assert dossier.handles[0].platform == "GitHub"
    assert dossier.metadata.get("disambiguation_dropped") == 1
    identity = next(item for item in dossier.confidence if item.label == "identity-match")
    assert "llm disambiguation dropped: 1" in identity.evidence
