"""LLM-generated 'why this job matches you' explanations.

Per Decision 3 (phase2_module1.md §3): the LLM is given the pre-computed score
and breakdown as facts. It must never invent or restate a different score —
only explain the given one using specific CV/JD evidence, per JobMatchAI's and
Synapse's confirmed "separate scoring from explanation" pattern.
"""

from __future__ import annotations

import json
import logging

import httpx

from app.core.config import Settings
from app.modules.job_matching.models import JobMatch, JobPosting

logger = logging.getLogger(__name__)

EXPLANATION_SYSTEM_PROMPT = """
You are explaining why a job posting was matched to a candidate.

You will be given:
- The job title, company, and description excerpt
- A pre-computed match score and its breakdown (similarity, salary fit, location fit)

Your ONLY job is to explain, in 1-3 sentences, WHY this score makes sense, citing
specific evidence from the job description. You must NOT invent a different score,
you must NOT contradict the given score, and you must NOT make claims not
supported by the provided text.

Return JSON: {"explanation": "..."}
""".strip()


def _build_explanation_messages(match: JobMatch, posting: JobPosting) -> list[dict[str, str]]:
    user_content = f"""
Job Title: {posting.title}
Company: {posting.company}
Description excerpt: {(posting.description_raw or "")[:1500]}

Pre-computed match score: {match.overall_score}/100
Score breakdown: {json.dumps(match.score_breakdown)}

Explain why this score makes sense, citing specific evidence from the description.
""".strip()
    return [
        {"role": "system", "content": EXPLANATION_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


async def generate_match_explanation(
    match: JobMatch, posting: JobPosting, settings: Settings
) -> tuple[str, dict[str, int]]:
    """Generate a grounded explanation for a pre-computed match score.

    Returns:
        Tuple of (explanation, token_usage).
        token_usage dict has 'input_tokens' and 'output_tokens' keys.

    Raises:
        httpx.HTTPError: If the API request fails.
        ValueError: If the response cannot be parsed.
    """
    api_key = settings.openai_api_key.strip()
    if not api_key:
        raise ValueError("OpenAI API key not configured")

    messages = _build_explanation_messages(match, posting)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": messages,
                "response_format": {"type": "json_object"},
                "temperature": 0.2,
            },
        )
        response.raise_for_status()
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        usage = result.get("usage", {})
        token_usage = {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        }

        try:
            data = json.loads(content)
            explanation = str(data.get("explanation", "")).strip()
            if not explanation:
                raise ValueError("Empty explanation returned")
            return explanation, token_usage
        except (json.JSONDecodeError, KeyError) as exc:
            raise ValueError(f"Invalid explanation JSON: {exc}") from exc
