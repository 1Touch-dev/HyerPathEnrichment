"""E2E: disambiguation through in-compose LiteLLM proxy. Run inside api container."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from app.config import get_settings
from app.models import EnrichmentRequest, SocialHandle
from app.workers.runner import PipelineOrchestrator


async def main() -> None:
    settings = get_settings()
    print("mode", settings.llm_mode)
    print("base", settings.litellm_api_base)
    print("model", settings.litellm_model)
    assert settings.llm_mode == "litellm", settings.llm_mode
    assert "litellm" in settings.litellm_api_base, settings.litellm_api_base

    orch = PipelineOrchestrator(db=AsyncMock())
    request = EnrichmentRequest(username="jane-doe", email="jane.doe@acme.com")
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
    print("PASS: disambiguation via LiteLLM proxy")


if __name__ == "__main__":
    asyncio.run(main())
