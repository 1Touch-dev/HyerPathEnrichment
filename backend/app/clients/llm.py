from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

import httpx

from app.core.config import Settings

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

_JOB_QUERY_SYSTEM = """\
You are a job search query optimizer for multiple job boards.

Given a job title, location, and country, generate optimized search parameters for each job board.

Job board requirements:
- LinkedIn: Separate search_term and location fields. Location can be "City" or "City, State/Country"
- Indeed: Needs country_indeed (lowercase country name like "india", "usa") and location. Works best with "City, State" or "City, Country"
- Glassdoor: Requires "City, State" or "City, Country" format. Single-word locations often fail
- Google Jobs: Uses natural language google_search_term. MUST use "near" keyword (not "in") and job board syntax like "software engineer jobs near Mumbai, India" or "backend developer jobs near San Francisco, CA"
- ZipRecruiter: Similar to LinkedIn, separate search_term and location

Location normalization rules:
- Bengaluru → "Bengaluru, Karnataka" (add state)
- Mumbai → "Mumbai, Maharashtra" (add state)
- San Francisco → "San Francisco, CA" (add state abbreviation)
- London → "London, England" or "London, UK" (add country/region)
- Ambiguous cities: Add state/province/country for clarity

Google Jobs specific rules:
- ALWAYS use "jobs near" format, never "jobs in"
- Example: "software engineer jobs near Mumbai, India" (correct)
- Example: "software engineer jobs in Mumbai" (incorrect)
- Keep it simple: "[job title] jobs near [location]"
- Do NOT add time filters unless specifically requested

Respond ONLY with compact JSON (no markdown):
{
  "linkedin": {"search_term": str, "location": str},
  "indeed": {"search_term": str, "location": str, "country_indeed": str},
  "glassdoor": {"search_term": str, "location": str},
  "google": {"google_search_term": str},
  "zip_recruiter": {"search_term": str, "location": str}
}
"""

_JOB_QUERY_FEW_SHOTS = """\
Examples:

Input: job_title="Software Engineer", location="Bengaluru", country="India"
→ {
  "linkedin": {"search_term": "Software Engineer", "location": "Bengaluru, Karnataka, India"},
  "indeed": {"search_term": "Software Engineer", "location": "Bengaluru, Karnataka", "country_indeed": "india"},
  "glassdoor": {"search_term": "Software Engineer", "location": "Bengaluru, Karnataka"},
  "google": {"google_search_term": "Software Engineer jobs near Bengaluru, Karnataka, India"},
  "zip_recruiter": {"search_term": "Software Engineer", "location": "Bengaluru, India"}
}

Input: job_title="Backend Developer", location="San Francisco", country="USA"
→ {
  "linkedin": {"search_term": "Backend Developer", "location": "San Francisco, CA"},
  "indeed": {"search_term": "Backend Developer", "location": "San Francisco, CA", "country_indeed": "usa"},
  "glassdoor": {"search_term": "Backend Developer", "location": "San Francisco, CA"},
  "google": {"google_search_term": "Backend Developer jobs near San Francisco, CA"},
  "zip_recruiter": {"search_term": "Backend Developer", "location": "San Francisco, CA"}
}

Input: job_title="Data Scientist", location="London", country=None
→ {
  "linkedin": {"search_term": "Data Scientist", "location": "London, UK"},
  "indeed": {"search_term": "Data Scientist", "location": "London", "country_indeed": "uk"},
  "glassdoor": {"search_term": "Data Scientist", "location": "London, England"},
  "google": {"google_search_term": "Data Scientist jobs near London, UK"},
  "zip_recruiter": {"search_term": "Data Scientist", "location": "London, UK"}
}
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


def build_job_query_messages(
    job_title: str, location: str | None, country: str | None
) -> list[dict[str, str]]:
    """Build system + user chat messages for job query optimization."""
    location_str = f'"{location}"' if location else "None"
    country_str = f'"{country}"' if country else "None"

    user_content = (
        f"{_JOB_QUERY_FEW_SHOTS}\n"
        "Now optimize:\n"
        f'Input: job_title="{job_title}", location={location_str}, country={country_str}'
    )
    return [
        {"role": "system", "content": _JOB_QUERY_SYSTEM},
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


def _parse_job_queries(content: str) -> dict[str, dict[str, str]] | None:
    """Parse LLM response containing job board query optimizations.

    Returns None if parsing fails (triggers fallback to manual logic).
    """
    try:
        start = content.index("{")
        end = content.rindex("}") + 1
        data: dict[str, dict[str, str]] = json.loads(content[start:end])

        # Validate structure - must have all 5 boards
        required_boards = {"linkedin", "indeed", "glassdoor", "google", "zip_recruiter"}
        if not all(board in data for board in required_boards):
            logger.warning("LLM job query response missing required boards")
            return None

        # Validate each board has required fields
        if not isinstance(data.get("linkedin"), dict):
            return None
        if not isinstance(data.get("indeed"), dict):
            return None
        if not isinstance(data.get("glassdoor"), dict):
            return None
        if not isinstance(data.get("google"), dict):
            return None
        if not isinstance(data.get("zip_recruiter"), dict):
            return None

        return data
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        logger.warning("Failed to parse LLM job query response", exc_info=True)
        return None


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


async def litellm_optimize_job_query(
    job_title: str,
    location: str | None,
    country: str | None,
    settings: Settings,
) -> dict[str, dict[str, str]] | None:
    """Use LiteLLM to optimize job search queries for multiple job boards.

    Args:
        job_title: Job title to search for
        location: Location string (city, state, etc.)
        country: Country name
        settings: App settings with LiteLLM configuration

    Returns:
        Dictionary mapping board names to their optimized query parameters,
        or None if LLM optimization fails (triggers fallback to manual logic).

    Example return:
        {
            "linkedin": {"search_term": "Software Engineer", "location": "Mumbai, India"},
            "indeed": {"search_term": "Software Engineer", "location": "Mumbai, Maharashtra", "country_indeed": "india"},
            "glassdoor": {"search_term": "Software Engineer", "location": "Mumbai, Maharashtra"},
            "google": {"google_search_term": "Software Engineer jobs in Mumbai, Maharashtra, India"},
            "zip_recruiter": {"search_term": "Software Engineer", "location": "Mumbai, India"}
        }
    """
    base = settings.litellm_api_base.strip()
    if not base:
        logger.info("LiteLLM not configured, using manual job query logic")
        return None

    models = [settings.litellm_model] + [
        item.strip() for item in settings.litellm_fallbacks.split(",") if item.strip()
    ]
    headers = {"Content-Type": "application/json"}
    if settings.litellm_api_key.strip():
        headers["Authorization"] = f"Bearer {settings.litellm_api_key.strip()}"

    messages = build_job_query_messages(job_title, location, country)

    async with httpx.AsyncClient(timeout=120.0) as client:
        for model in models:
            try:
                logger.debug(f"Calling LiteLLM for job query optimization with model {model}")
                response = await client.post(
                    f"{base.rstrip('/')}/v1/chat/completions",
                    headers=headers,
                    json={"model": model, "messages": messages},
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]

                queries = _parse_job_queries(content)
                if queries:
                    logger.info(
                        f"LLM optimized job queries for {len(queries)} boards",
                        extra={"job_title": job_title, "location": location, "country": country},
                    )
                    trace(
                        "job-query-optimization",
                        {
                            "job_title": job_title,
                            "location": location,
                            "country": country,
                            "model": model,
                            "boards": list(queries.keys()),
                        },
                    )
                    return queries
                else:
                    logger.warning(f"LiteLLM model {model} returned invalid job query format")
                    continue

            except (httpx.HTTPError, ValueError, KeyError, IndexError, json.JSONDecodeError):
                logger.warning(
                    f"LiteLLM job query optimization failed with model {model}; trying next",
                    exc_info=True,
                )
                continue

    logger.warning("All LiteLLM models failed for job query optimization, using manual logic")
    return None


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


class LiteLLMDisambiguator:
    """Identity disambiguator with a config-selected backend.

    ``LLM_MODE=stub`` (free default) keeps the heuristic string match.
    ``ollama`` uses a local model; ``litellm`` uses the LiteLLM proxy with a
    fallback chain. Prompt assembly lives in ``build_disambiguation_messages``.
    The ``compare`` signature is unchanged so the orchestrator and confidence
    scoring never need to know which backend answered.
    """

    async def compare(self, left: str, right: str) -> LLMDecision:
        settings = _settings()
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


def _settings() -> Settings:
    from app.core.config import get_settings

    return get_settings()
