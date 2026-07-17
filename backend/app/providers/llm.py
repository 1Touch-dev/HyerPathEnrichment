"""Compatibility shim — prefer app.clients.llm."""

from app.clients.llm import (  # noqa: F401
    LLMDecision,
    _clamp_confidence,
    _compact_username,
    _normalize_username_tokens,
    _parse_decision,
    _settings,
    _username_field,
    build_disambiguation_messages,
    heuristic_compare,
    litellm_compare,
    ollama_compare,
    trace,
)

__all__ = [
    "LLMDecision",
    "_clamp_confidence",
    "_compact_username",
    "_normalize_username_tokens",
    "_parse_decision",
    "_settings",
    "_username_field",
    "build_disambiguation_messages",
    "heuristic_compare",
    "litellm_compare",
    "ollama_compare",
    "trace",
]
