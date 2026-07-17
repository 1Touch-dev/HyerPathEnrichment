from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

_USERNAME_TOKEN_RE = re.compile(r"[a-z0-9]+")

_DISAMBIGUATION_SYSTEM = """\
You are an identity disambiguation assistant for OSINT enrichment.

Given a known target identity (A) and a candidate social handle (B), decide if B \
likely belongs to the same real person as A.

Input format:
- A: pipe-separated fields — username | email | linkedin_url | company (some may be empty)
- B: pipe-separated fields — platform | username | profile_url

Scoring rubric (confidence is 0.0–1.0; the pipeline keeps B only when \
same_identity is true AND confidence >= 0.7):
- Strong match (same person): username variants (jane_doe ≈ jane-doe), email/handle \
alignment, consistent professional context → confidence >= 0.75
- Uncertain: common names, weak partial overlap only → same_identity false OR confidence < 0.7
- Clear mismatch: unrelated username, bot/brand/org account → same_identity false, low confidence

Respond ONLY with compact JSON (no markdown):
{"same_identity": bool, "confidence": float, "reason": str}
"""

_DISAMBIGUATION_FEW_SHOTS = """\
Examples:
A: jane-doe | jane.doe@acme.com
B: X | jane_doe | https://x.com/jane_doe
→ {"same_identity": true, "confidence": 0.88, "reason": "username variant and email context align"}

A: jane-doe | jane.doe@acme.com
B: GitHub | totally-unrelated-bot-xyz-999 | https://github.com/totally-unrelated-bot-xyz-999
→ {"same_identity": false, "confidence": 0.12, "reason": "username unrelated to target"}

A: smith | john@example.com
B: Reddit | smith42 | https://reddit.com/u/smith42
→ {"same_identity": false, "confidence": 0.45, "reason": "common surname only; insufficient evidence"}
"""


@dataclass(slots=True)
class LLMDecision:
    same_identity: bool
    confidence: float
    reason: str


def build_disambiguation_messages(left: str, right: str) -> list[dict[str, str]]:
    """Build system + user chat messages for identity disambiguation."""
    user_content = (
        f"{_DISAMBIGUATION_FEW_SHOTS}\n"
        "Now evaluate:\n"
        f"A (known target): {left}\n"
        f"B (OSINT candidate): {right}"
    )
    return [
        {"role": "system", "content": _DISAMBIGUATION_SYSTEM},
        {"role": "user", "content": user_content},
    ]


def _normalize_username_tokens(text: str) -> set[str]:
    return {token for token in _USERNAME_TOKEN_RE.findall(text.lower()) if len(token) >= 4}


def _compact_username(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _username_field(value: str, *, index: int) -> str:
    parts = [part.strip() for part in value.split("|")]
    if 0 <= index < len(parts):
        return parts[index].lower()
    return value.strip().lower()


def heuristic_compare(left: str, right: str) -> LLMDecision:
    """Free default: string-match heuristic with username token overlap, no network."""
    normalized_left = left.strip().lower()
    normalized_right = right.strip().lower()
    target_username = _username_field(normalized_left, index=0)
    candidate_username = _username_field(normalized_right, index=1)
    left_tokens = _normalize_username_tokens(target_username)
    right_tokens = _normalize_username_tokens(candidate_username)
    token_overlap = bool(left_tokens & right_tokens)

    same = (
        _compact_username(target_username) == _compact_username(candidate_username)
        or target_username == candidate_username
        or target_username in candidate_username
        or candidate_username in target_username
        or token_overlap
    )
    confidence = 0.91 if same else 0.24
    return LLMDecision(same_identity=same, confidence=confidence, reason="heuristic string match")


def _clamp_confidence(value: float) -> float:
    return max(0.0, min(1.0, value))


def _parse_decision(content: str, fallback: LLMDecision) -> LLMDecision:
    try:
        start = content.index("{")
        end = content.rindex("}") + 1
        data = json.loads(content[start:end])
        return LLMDecision(
            same_identity=bool(data.get("same_identity", fallback.same_identity)),
            confidence=_clamp_confidence(float(data.get("confidence", fallback.confidence))),
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
                    "messages": build_disambiguation_messages(left, right),
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

    messages = build_disambiguation_messages(left, right)
    async with httpx.AsyncClient(timeout=120.0) as client:
        for model in models:
            try:
                response = await client.post(
                    f"{base.rstrip('/')}/v1/chat/completions",
                    headers=headers,
                    json={"model": model, "messages": messages},
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
