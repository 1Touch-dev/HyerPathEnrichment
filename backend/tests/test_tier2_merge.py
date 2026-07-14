"""Tier 2 merge: prefer higher confidence on platform/username collision."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.models import EnrichmentRequest
from app.workers.runner import PipelineOrchestrator


@pytest.fixture
def orchestrator() -> PipelineOrchestrator:
    return PipelineOrchestrator(db=AsyncMock())


@pytest.mark.asyncio
async def test_merge_prefers_higher_handle_confidence(orchestrator: PipelineOrchestrator) -> None:
    request = EnrichmentRequest(username="jane")
    payloads: list[dict[str, Any]] = [
        {
            "handles": [
                {
                    "platform": "Github",
                    "username": "jane",
                    "profile_url": "https://github.com/jane",
                    "confidence": 0.75,
                    "metadata": {"provider": "Sherlock", "matched": True},
                }
            ],
            "sources": ["Sherlock"],
        },
        {
            "handles": [
                {
                    "platform": "Github",
                    "username": "jane",
                    "profile_url": "https://github.com/jane",
                    "confidence": 0.85,
                    "metadata": {"provider": "Maigret", "matched": True},
                }
            ],
            "sources": ["Maigret"],
        },
    ]

    dossier = await orchestrator._merge(request, payloads)

    assert len(dossier.handles) == 1
    assert dossier.handles[0].confidence == pytest.approx(0.85)
    assert dossier.handles[0].metadata.get("provider") == "Maigret"
    assert set(dossier.sources) == {"Sherlock", "Maigret"}


@pytest.mark.asyncio
async def test_merge_keeps_first_when_incoming_confidence_lower(
    orchestrator: PipelineOrchestrator,
) -> None:
    request = EnrichmentRequest(username="jane")
    payloads: list[dict[str, Any]] = [
        {
            "handles": [
                {
                    "platform": "Github",
                    "username": "jane",
                    "profile_url": "https://github.com/jane",
                    "confidence": 0.85,
                    "metadata": {"provider": "Maigret", "matched": True},
                }
            ],
            "sources": ["Maigret"],
        },
        {
            "handles": [
                {
                    "platform": "Github",
                    "username": "jane",
                    "profile_url": "https://github.com/jane-alt",
                    "confidence": 0.75,
                    "metadata": {"provider": "Sherlock", "matched": True},
                }
            ],
            "sources": ["Sherlock"],
        },
    ]

    dossier = await orchestrator._merge(request, payloads)

    assert len(dossier.handles) == 1
    assert dossier.handles[0].confidence == pytest.approx(0.85)
    assert dossier.handles[0].metadata.get("provider") == "Maigret"
    assert dossier.handles[0].profile_url == "https://github.com/jane"
