"""Perplexity Agent API client — company-context lookup for outreach drafting (Decision 5/7).

Follows the same raw-httpx convention as cv_extractor.py / feedback_generator.py's
OpenAI calls, not the openai SDK — this repo's established "own the HTTP call" style.

Sonar chat completions (`POST /chat/completions`, model `sonar`) now returns 403
and requires the Agent API (`POST /v1/responses`). `preset=fast` is the grounded
web-search replacement for Sonar.
"""

from __future__ import annotations

import logging

import httpx

from app.clients.retry import with_transient_retry
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


def _collect_text(content: object, chunks: list[str]) -> None:
    if isinstance(content, str):
        chunks.append(content)
        return
    if not isinstance(content, list):
        return
    for part in content:
        if isinstance(part, str):
            chunks.append(part)
        elif isinstance(part, dict):
            text = part.get("text")
            if isinstance(text, str):
                chunks.append(text)


def _agent_response_text(data: object) -> str:
    """Read the assistant text from an Agent API `/v1/responses` body.

    The raw JSON often omits the SDK's `output_text` helper and nests the
    answer under `output[].content[].text`.
    """
    if not isinstance(data, dict):
        raise ValueError("Perplexity response was not an object")
    direct = data.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    chunks: list[str] = []
    output = data.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            _collect_text(item.get("content"), chunks)
    summary = "\n".join(part.strip() for part in chunks if part.strip())
    if not summary:
        raise KeyError("output_text")
    return summary


class PerplexityClient:
    """Thin wrapper over Perplexity's Agent API responses endpoint."""

    def __init__(self, http_client: httpx.AsyncClient | None = None):
        self._settings = get_settings()
        # Web-grounded agent calls are slower than the old chat-completions path.
        self._client = http_client or httpx.AsyncClient(timeout=60.0)

    async def get_company_context(
        self, company_name: str, role_title: str | None = None
    ) -> dict[str, str]:
        """Return {"summary": str, "source": "perplexity"} or a fail-soft empty summary.

        Never raises — outreach generation must still work (with a shorter,
        less-personalized message) if Perplexity is unavailable or unconfigured.
        """
        api_key = self._settings.perplexity_api_key.strip()
        if not api_key:
            return {"summary": "", "source": "none"}

        role_line = (
            f" The candidate is looking at a '{role_title}' role there." if role_title else ""
        )
        user_content = f"Company: {company_name}.{role_line} Summarize public information relevant to outreach."

        try:
            # raise_for_status() must run *inside* the retried operation, not after
            # with_transient_retry returns — httpx doesn't raise on 4xx/5xx by itself,
            # so calling it outside would mean status-code errors (429/502/503/504)
            # never actually trigger a retry, only network-level failures would.
            async def _do_post() -> httpx.Response:
                resp = await self._client.post(
                    f"{self._settings.perplexity_api_base.rstrip('/')}/v1/responses",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "preset": "fast",
                        "instructions": _COMPANY_CONTEXT_SYSTEM_PROMPT,
                        "input": user_content,
                        "temperature": 0.2,
                        # The prompt asks for under 150 words; cap the billable output.
                        "max_output_tokens": 400,
                    },
                )
                resp.raise_for_status()
                return resp

            response = await with_transient_retry(_do_post)
            summary = _agent_response_text(response.json())
            return {"summary": summary, "source": "perplexity"}
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            logger.warning("Perplexity company-context lookup failed", extra={"error": str(exc)})
            return {"summary": "", "source": "none"}
