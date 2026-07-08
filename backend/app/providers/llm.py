from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LLMDecision:
    same_identity: bool
    confidence: float
    reason: str


_PROMPT = (
    "You are an identity disambiguation assistant. Decide whether the two "
    "identifiers below refer to the same person. Respond ONLY with compact JSON "
    '{{"same_identity": bool, "confidence": float between 0 and 1, "reason": str}}.\n'
    "A: {left}\nB: {right}"
)


def heuristic_compare(left: str, right: str) -> LLMDecision:
    """Free default: pure string-match heuristic, no network."""
    normalized_left = left.strip().lower()
    normalized_right = right.strip().lower()
    same = (
        normalized_left == normalized_right
        or normalized_left in normalized_right
        or normalized_right in normalized_left
    )
    confidence = 0.91 if same else 0.24
    return LLMDecision(same_identity=same, confidence=confidence, reason="heuristic string match")


def _parse_decision(content: str, fallback: LLMDecision) -> LLMDecision:
    try:
        start = content.index("{")
        end = content.rindex("}") + 1
        data = json.loads(content[start:end])
        return LLMDecision(
            same_identity=bool(data.get("same_identity", fallback.same_identity)),
            confidence=float(data.get("confidence", fallback.confidence)),
            reason=str(data.get("reason", "llm decision")),
        )
    except (ValueError, TypeError, KeyError):
        return fallback


async def ollama_compare(left: str, right: str, settings: Settings) -> LLMDecision:
    """Free/local backend: a self-hosted Ollama model."""
    fallback = heuristic_compare(left, right)
    base = settings.ollama_base_url.strip()
    if not base:
        return fallback
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{base.rstrip('/')}/api/chat",
                json={
                    "model": settings.ollama_model,
                    "stream": False,
                    "messages": [{"role": "user", "content": _PROMPT.format(left=left, right=right)}],
                },
            )
            response.raise_for_status()
            content = response.json().get("message", {}).get("content", "")
            return _parse_decision(content, fallback)
    except (httpx.HTTPError, ValueError):
        logger.warning("ollama disambiguation failed; using heuristic", exc_info=True)
        return fallback


async def litellm_compare(left: str, right: str, settings: Settings) -> LLMDecision:
    """Paid-ready backend: a LiteLLM proxy with a model fallback chain."""
    fallback = heuristic_compare(left, right)
    base = settings.litellm_api_base.strip()
    if not base:
        return fallback

    models = [settings.litellm_model] + [
        item.strip() for item in settings.litellm_fallbacks.split(",") if item.strip()
    ]
    headers = {"Content-Type": "application/json"}
    if settings.litellm_api_key.strip():
        headers["Authorization"] = f"Bearer {settings.litellm_api_key.strip()}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        for model in models:
            try:
                response = await client.post(
                    f"{base.rstrip('/')}/v1/chat/completions",
                    headers=headers,
                    json={
                        "model": model,
                        "messages": [
                            {"role": "user", "content": _PROMPT.format(left=left, right=right)}
                        ],
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                return _parse_decision(content, fallback)
            except (httpx.HTTPError, ValueError, KeyError, IndexError):
                logger.warning("litellm model %s failed; trying next", model, exc_info=True)
                continue
    return fallback


def trace(name: str, metadata: dict[str, object]) -> None:
    """Best-effort Langfuse trace. No-op when unconfigured or SDK absent."""
    settings = _settings()
    if not (settings.langfuse_host.strip() and settings.langfuse_public_key.strip()):
        return
    try:
        from langfuse import Langfuse

        client = Langfuse(
            host=settings.langfuse_host.strip(),
            public_key=settings.langfuse_public_key.strip(),
            secret_key=settings.langfuse_secret_key.strip(),
        )
        client.trace(name=name, metadata=metadata)
    except Exception:
        logger.warning("langfuse trace failed", exc_info=True)


def _settings() -> Settings:
    from app.config import get_settings

    return get_settings()
