"""Perplexity Sonar API client — company-context lookup for outreach drafting (Decision 5/7).

Follows the same raw-httpx convention as cv_extractor.py / feedback_generator.py's
OpenAI calls, not the openai SDK — this repo's established "own the HTTP call" style.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Constrained deliberately to PUBLIC company information only — never a named
# private individual beyond a public job title (RULE.md "public data only",
# see phase2_module2.md §0 and Decision 5).
_COMPANY_CONTEXT_SYSTEM_PROMPT = """
You are a research assistant. Given a company name and (optionally) a job title,
summarize PUBLIC information only: recent company news, product launches, company
mission/values from their official site, and general hiring trends. Do not search
for or report on any named private individual's personal information beyond a
public job title the user already provided. If you cannot find public information,
say so plainly. Keep the summary under 150 words.
""".strip()


class PerplexityClient:
    """Thin wrapper over Perplexity's OpenAI-compatible chat completions endpoint."""

    def __init__(self, http_client: httpx.AsyncClient | None = None):
        self._settings = get_settings()
        self._client = http_client or httpx.AsyncClient(timeout=30.0)

    async def get_company_context(self, company_name: str, role_title: str | None = None) -> dict[str, str]:
        """Return {"summary": str, "source": "perplexity"} or a fail-soft empty summary.

        Never raises — outreach generation must still work (with a shorter,
        less-personalized message) if Perplexity is unavailable or unconfigured.
        """
        api_key = self._settings.perplexity_api_key.strip()
        if not api_key:
            return {"summary": "", "source": "none"}

        role_line = f" The candidate is looking at a '{role_title}' role there." if role_title else ""
        user_content = f"Company: {company_name}.{role_line} Summarize public information relevant to outreach."

        try:
            response = await self._client.post(
                f"{self._settings.perplexity_api_base}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "sonar",
                    "messages": [
                        {"role": "system", "content": _COMPANY_CONTEXT_SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    "temperature": 0.2,
                },
            )
            response.raise_for_status()
            data = response.json()
            summary = data["choices"][0]["message"]["content"]
            return {"summary": summary.strip(), "source": "perplexity"}
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            logger.warning("Perplexity company-context lookup failed", extra={"error": str(exc)})
            return {"summary": "", "source": "none"}
