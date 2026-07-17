"""Manual probe: disambiguation via local Ollama (no vendor keys).

Run from backend/ after starting Ollama:
  LLM_MODE=ollama OLLAMA_BASE_URL=http://localhost:11434 python scripts/_probe_ollama_disambiguation.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.models import EnrichmentRequest, SocialHandle
from app.enrichers.pipeline import Pipeline


async def main() -> None:
    settings = get_settings()
    print("mode", settings.llm_mode)
    print("ollama_base", settings.ollama_base_url)
    print("ollama_model", settings.ollama_model)
    assert settings.llm_mode == "ollama", settings.llm_mode
    assert settings.ollama_base_url.strip(), "OLLAMA_BASE_URL required"

    orch = Pipeline(db=AsyncMock())
    request = EnrichmentRequest(
        username="jane-doe",
        email="jane.doe@acme.com",
        requested_tiers=["tier2", "tier3"],
    )
    handles = [
        SocialHandle(
            platform="X",
            username="jane_doe",
            profile_url="https://x.com/jane_doe",
            confidence=0.35,
        ),
        SocialHandle(
            platform="GitHub",
            username="totally-unrelated-bot-xyz-999",
            profile_url="https://github.com/totally-unrelated-bot-xyz-999",
            confidence=0.40,
        ),
        SocialHandle(
            platform="GitHub",
            username="jane-doe",
            profile_url="https://github.com/jane-doe",
            confidence=0.9,
        ),
    ]
    kept, dropped = await orch._disambiguate_handles(request, handles)
    print(
        "kept",
        [(h.platform, h.username, round(h.confidence, 2)) for h in kept],
        "dropped",
        dropped,
    )
    names = {(h.platform, h.username) for h in kept}
    assert ("GitHub", "jane-doe") in names
    assert ("GitHub", "totally-unrelated-bot-xyz-999") not in names
    print("PASS: disambiguation via Ollama")


if __name__ == "__main__":
    asyncio.run(main())
