"""Live disambiguation via Gemini OpenAI-compatible API (no LiteLLM container)."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

for raw in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, _, value = line.partition("=")
    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

os.environ["LLM_MODE"] = "litellm"
os.environ["LITELLM_API_BASE"] = "https://generativelanguage.googleapis.com/v1beta/openai"
os.environ["LITELLM_API_KEY"] = os.environ.get("GEMINI_API_KEY", "")
os.environ["LITELLM_MODEL"] = "gemini-2.5-flash"
os.environ["LITELLM_FALLBACKS"] = "gemini-flash-latest"
os.environ["DISAMBIGUATION_THRESHOLD"] = "0.7"

from app.config import get_settings
from app.models import EnrichmentRequest, SocialHandle
from app.providers.llm import litellm_compare
from app.enrichers.pipeline import Pipeline

get_settings.cache_clear()


async def main() -> None:
    settings = get_settings()
    print(f"base={settings.litellm_api_base}")
    print(f"model={settings.litellm_model} fallbacks={settings.litellm_fallbacks}")

    decision = await litellm_compare(
        "jane doe | jane.doe@acme.com | https://linkedin.com/in/jane-doe",
        "X | jane_doe | https://x.com/jane_doe",
        settings,
    )
    print(
        f"compare: same={decision.same_identity} "
        f"conf={decision.confidence:.2f} reason={decision.reason!r}"
    )

    orch = Pipeline(db=AsyncMock())
    request = EnrichmentRequest(
        username="jane-doe",
        email="jane.doe@acme.com",
        linkedin_url="https://linkedin.com/in/jane-doe",
        requested_tiers=["tier1", "tier2", "tier3"],
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
    print(f"kept={len(kept)} dropped={dropped}")
    for handle in kept:
        print(f"  KEEP {handle.platform}/{handle.username} conf={handle.confidence:.2f}")

    names = {(h.platform, h.username) for h in kept}
    assert ("GitHub", "jane-doe") in names, "high-conf handle must remain"
    assert ("GitHub", "totally-unrelated-bot-xyz-999") not in names, "unrelated low-conf must drop"
    print("PASS: live Gemini disambiguation keep/drop behaved as expected")


if __name__ == "__main__":
    asyncio.run(main())
