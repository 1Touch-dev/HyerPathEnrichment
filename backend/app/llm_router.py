from app.config import get_settings
from app.providers.llm import (
    LLMDecision,
    heuristic_compare,
    litellm_compare,
    ollama_compare,
    trace,
)

__all__ = ["LLMDecision", "LiteLLMDisambiguator"]


class LiteLLMDisambiguator:
    """Identity disambiguator with a config-selected backend.

    ``LLM_MODE=stub`` (free default) keeps the heuristic string match.
    ``ollama`` uses a local model; ``litellm`` uses the LiteLLM proxy with a
    fallback chain. Prompt assembly lives in ``providers.llm.build_disambiguation_messages``.
    The ``compare`` signature is unchanged so the orchestrator and confidence
    scoring never need to know which backend answered.
    """

    async def compare(self, left: str, right: str) -> LLMDecision:
        settings = get_settings()
        mode = settings.llm_mode.strip().lower()
        if mode == "litellm":
            decision = await litellm_compare(left, right, settings)
        elif mode == "ollama":
            decision = await ollama_compare(left, right, settings)
        else:
            decision = heuristic_compare(left, right)

        trace(
            "identity-disambiguation",
            {
                "mode": mode,
                "same_identity": decision.same_identity,
                "confidence": decision.confidence,
                "reason": decision.reason,
            },
        )
        return decision
