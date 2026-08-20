"""Heuristic + LLM-judge moderation flagging cascade for the review queue
(Batch 1). Deliberately simple heuristics — see plan: this is NOT meant to be
sophisticated, just a cheap first-pass filter before the (also fail-open)
LLM judge. Reuses cv_extractor.py's exact httpx.AsyncClient + OpenAI JSON-mode
call pattern for the LLM step."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.admin.models import AdminReviewQueueItem

logger = logging.getLogger(__name__)

# Deliberately small and generic — a real deny-list is out of scope for this
# task (see moderation-flagging design note). Case-insensitive substring match.
_DENY_LIST = [
    "buy followers now",
    "click here to win",
    "guaranteed income",
    "wire transfer fee",
    "nude photos",
    "kill yourself",
]

_LLM_JUDGE_PROMPT = """
You are a content-moderation classifier for a job-search platform.
Given a piece of user- or platform-sourced text, decide whether it violates
platform policy (spam, harassment, illegal content, scams).

Return valid JSON matching this schema:
{"flagged": bool, "reason": string or null}

Be conservative: only flag clear violations, not borderline or ambiguous text.
""".strip()


def run_heuristic_check(text_fields: list[str]) -> str | None:
    """Pure/sync deny-word check over the joined text fields. Returns a short
    flag_reason string on match, else None."""
    joined = " ".join(text_fields).lower()
    for term in _DENY_LIST:
        if term in joined:
            return f"Heuristic match: deny-listed term '{term}'"
    return None


async def run_llm_judge(resource_type: str, text_fields: list[str]) -> tuple[bool, str | None]:
    """Ask the LLM to classify the joined text for platform-policy violations.
    MUST be fail-open: any failure (missing key, network/timeout, non-2xx,
    malformed JSON) returns (False, None) rather than raising."""
    try:
        settings = get_settings()
        api_key = settings.openai_api_key.strip()
        if not api_key:
            logger.warning("OpenAI API key not configured; skipping LLM judge")
            return False, None

        joined_text = "\n".join(text_fields)[:4000]
        messages = [
            {"role": "system", "content": _LLM_JUDGE_PROMPT},
            {
                "role": "user",
                "content": f"Resource type: {resource_type}\n\nText:\n{joined_text}",
            },
        ]
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = {
            "model": "gpt-4o-mini",
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            raw_data = json.loads(content)

            flagged = bool(raw_data.get("flagged", False))
            reason = raw_data.get("reason")
            reason = str(reason) if reason is not None else None
            return flagged, reason

    except Exception as exc:
        logger.warning(
            "LLM judge failed; failing open (not flagged)",
            exc_info=True,
            extra={"error_type": type(exc).__name__, "resource_type": resource_type},
        )
        return False, None


async def flag_if_needed(
    db: AsyncSession,
    *,
    resource_type: str,
    resource_id: UUID,
    text_fields: list[str],
) -> AdminReviewQueueItem | None:
    """Orchestrates the heuristic -> LLM-judge flagging cascade. Fail-open at
    the top level: callers (worker tasks) must never have their own
    create/update action fail because flagging errored."""
    try:
        heuristic_reason = run_heuristic_check(text_fields)
        if heuristic_reason is not None:
            item = AdminReviewQueueItem(
                resource_type=resource_type,
                resource_id=resource_id,
                status="pending",
                flag_reason=heuristic_reason,
                flag_source="heuristic",
                flagged_at=datetime.now(UTC),
            )
            db.add(item)
            await db.flush()
            return item

        flagged, llm_reason = await run_llm_judge(resource_type, text_fields)
        if flagged:
            item = AdminReviewQueueItem(
                resource_type=resource_type,
                resource_id=resource_id,
                status="pending",
                flag_reason=llm_reason,
                flag_source="llm_judge",
                flagged_at=datetime.now(UTC),
            )
            db.add(item)
            await db.flush()
            return item

        return None

    except Exception:
        logger.warning(
            "flag_if_needed failed unexpectedly; failing open (no flag created)",
            exc_info=True,
            extra={"resource_type": resource_type, "resource_id": str(resource_id)},
        )
        return None
