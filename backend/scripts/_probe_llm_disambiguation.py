"""Live probe: OpenAI + Gemini keys, fallback loop, handle keep/drop.

Does not print secrets. Run from backend/:
  python scripts/_probe_llm_disambiguation.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Load backend/.env into os.environ before Settings is constructed.
_env = ROOT / ".env"
if _env.exists():
    for raw in _env.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)

from app.core.config import Settings, get_settings
from app.domain.enrichment import EnrichmentRequest
from app.domain.dossier import SocialHandle
from app.providers.llm import LLMDecision, litellm_compare
from app.enrichers.pipeline import Pipeline


def _mask(value: str) -> str:
    if len(value) < 8:
        return "(set)" if value else "(empty)"
    return f"{value[:4]}…{value[-4:]} (len={len(value)})"


async def _openai_direct(settings: Settings) -> None:
    key = settings.openai_key if hasattr(settings, "openai_key") else os.environ.get("OPENAI_API_KEY", "")
    # Settings may not expose OPENAI — read from env
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    print("\n[1] OpenAI direct chat completions")
    if not key:
        print("  FAIL: OPENAI_API_KEY missing")
        return
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": 'Reply with JSON only: {"ok": true}'}],
                "max_tokens": 20,
            },
        )
        print(f"  status={response.status_code}")
        if response.status_code >= 400:
            print(f"  body={response.text[:300]}")
            return
        content = response.json()["choices"][0]["message"]["content"]
        print(f"  ok content={content[:120]!r}")


async def _gemini_direct() -> None:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    print("\n[2] Gemini OpenAI-compatible endpoint")
    if not key:
        print("  FAIL: GEMINI_API_KEY missing")
        return
    # Google OpenAI-compat surface (no LiteLLM proxy required for this probe)
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": "gemini-2.0-flash",
                "messages": [{"role": "user", "content": 'Reply with JSON only: {"ok": true}'}],
            },
        )
        print(f"  status={response.status_code}")
        if response.status_code >= 400:
            print(f"  body={response.text[:400]}")
            return
        content = response.json()["choices"][0]["message"]["content"]
        print(f"  ok content={content[:120]!r}")


async def _app_litellm_compare_via_openai() -> None:
    """Exercise providers.llm.litellm_compare against OpenAI (proxy substitute)."""
    print("\n[3] app litellm_compare via OpenAI base (primary path)")
    get_settings.cache_clear()
    os.environ["LLM_MODE"] = "litellm"
    os.environ["LITELLM_API_BASE"] = "https://api.openai.com"
    os.environ["LITELLM_API_KEY"] = os.environ.get("OPENAI_API_KEY", "")
    os.environ["LITELLM_MODEL"] = "gpt-4o-mini"
    os.environ["LITELLM_FALLBACKS"] = ""
    get_settings.cache_clear()
    settings = get_settings()
    decision = await litellm_compare(
        "jane doe | jane@acme.com",
        "X | jane_doe | https://x.com/jane_doe",
        settings,
    )
    print(
        f"  same_identity={decision.same_identity} "
        f"confidence={decision.confidence:.2f} reason={decision.reason!r}"
    )


async def _app_fallback_loop() -> None:
    """Prove fallback: bad primary model then gpt-4o-mini on OpenAI."""
    print("\n[4] fallback loop (bad model -> gpt-4o-mini on OpenAI)")
    get_settings.cache_clear()
    os.environ["LITELLM_API_BASE"] = "https://api.openai.com"
    os.environ["LITELLM_API_KEY"] = os.environ.get("OPENAI_API_KEY", "")
    os.environ["LITELLM_MODEL"] = "this-model-does-not-exist-xyz"
    os.environ["LITELLM_FALLBACKS"] = "gpt-4o-mini"
    get_settings.cache_clear()
    settings = get_settings()
    decision = await litellm_compare(
        "jane doe",
        "GitHub | janedoe | https://github.com/janedoe",
        settings,
    )
    print(
        f"  same_identity={decision.same_identity} "
        f"confidence={decision.confidence:.2f} reason={decision.reason!r}"
    )
    if decision.reason == "heuristic string match":
        print("  WARN: fell all the way to heuristic — fallback did not recover")
    else:
        print("  ok: recovered via fallback model")


async def _disambiguate_keep_and_drop() -> None:
    print("\n[5] _disambiguate_handles keep + drop with live LLM")
    get_settings.cache_clear()
    os.environ["LLM_MODE"] = "litellm"
    os.environ["LITELLM_API_BASE"] = "https://api.openai.com"
    os.environ["LITELLM_API_KEY"] = os.environ.get("OPENAI_API_KEY", "")
    os.environ["LITELLM_MODEL"] = "gpt-4o-mini"
    os.environ["LITELLM_FALLBACKS"] = ""
    os.environ["DISAMBIGUATION_THRESHOLD"] = "0.7"
    get_settings.cache_clear()

    orch = Pipeline(db=AsyncMock())
    request = EnrichmentRequest(
        username="jane-doe",
        email="jane.doe@acme.com",
        linkedin_url="https://linkedin.com/in/jane-doe",
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
    print(f"  kept={len(kept)} dropped={dropped}")
    for handle in kept:
        print(f"  KEEP {handle.platform}/{handle.username} conf={handle.confidence:.2f}")
    assert any(h.confidence >= 0.7 for h in kept), "expected at least one trusted/high handle"
    assert dropped >= 1 or any(h.username == "jane_doe" for h in kept), (
        "expected either a drop of the unrelated handle or a boost of the matching low-conf one"
    )
    print("  ok: disambiguation loop exercised against live model")


async def main() -> None:
    print("Env check (masked):")
    print(f"  LLM_MODE={os.environ.get('LLM_MODE')!r}")
    print(f"  LITELLM_API_BASE={os.environ.get('LITELLM_API_BASE')!r}")
    print(f"  LITELLM_MODEL={os.environ.get('LITELLM_MODEL')!r}")
    print(f"  LITELLM_FALLBACKS={os.environ.get('LITELLM_FALLBACKS')!r}")
    print(f"  OPENAI_API_KEY={_mask(os.environ.get('OPENAI_API_KEY', ''))}")
    print(f"  GEMINI_API_KEY={_mask(os.environ.get('GEMINI_API_KEY', ''))}")
    note = os.environ.get("LITELLM_API_BASE", "")
    if "litellm:4000" in note:
        print(
            "\nNOTE: LITELLM_API_BASE=http://litellm:4000 only resolves inside Docker. "
            "This probe uses https://api.openai.com for the app path; Gemini is probed separately."
        )

    await _openai_direct(Settings())
    await _gemini_direct()
    await _app_litellm_compare_via_openai()
    await _app_fallback_loop()
    await _disambiguate_keep_and_drop()
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
