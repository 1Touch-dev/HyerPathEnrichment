from dataclasses import dataclass


@dataclass(slots=True)
class LLMDecision:
    same_identity: bool
    confidence: float
    reason: str


class LiteLLMDisambiguator:
    async def compare(self, left: str, right: str) -> LLMDecision:
        normalized_left = left.strip().lower()
        normalized_right = right.strip().lower()
        same = normalized_left == normalized_right or normalized_left in normalized_right or normalized_right in normalized_left
        confidence = 0.91 if same else 0.24
        reason = "heuristic match pending LiteLLM integration"
        return LLMDecision(same_identity=same, confidence=confidence, reason=reason)
