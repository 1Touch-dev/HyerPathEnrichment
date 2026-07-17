"""LLM disambiguation policy — keep/drop low-confidence handles."""

from __future__ import annotations

import logging

from app.core.config import get_settings
from app.domain.dossier import SocialHandle
from app.domain.enrichment import EnrichmentRequest
from app.clients.llm import LiteLLMDisambiguator

logger = logging.getLogger(__name__)


def target_identity(request: EnrichmentRequest) -> str:
    parts = [
        request.username,
        request.email,
        request.linkedin_url,
        request.company,
    ]
    return " | ".join(part for part in parts if part) or "unknown"


async def disambiguate_handles(
    request: EnrichmentRequest,
    handles: list[SocialHandle],
    *,
    llm: LiteLLMDisambiguator | None = None,
) -> tuple[list[SocialHandle], int]:
    """Keep high-confidence handles; LLM-gate the rest against DISAMBIGUATION_THRESHOLD."""
    disambiguator = llm or LiteLLMDisambiguator()
    threshold = get_settings().disambiguation_threshold
    target = target_identity(request)
    kept: list[SocialHandle] = []
    dropped = 0

    for handle in handles:
        if handle.confidence >= threshold:
            kept.append(handle)
            continue

        evidence = f"{handle.platform} | {handle.username} | {handle.profile_url}"
        decision = await disambiguator.compare(target, evidence)
        if decision.same_identity and decision.confidence >= threshold:
            handle.confidence = max(handle.confidence, decision.confidence)
            kept.append(handle)
        else:
            dropped += 1
            logger.info(
                "dropped ambiguous handle %s/%s (same=%s llm_conf=%.2f)",
                handle.platform,
                handle.username,
                decision.same_identity,
                decision.confidence,
            )

    return kept, dropped
