"""RQ worker task: generate an ephemeral, on-demand tailored resume version for
one candidate + target company/role pair. Mirrors
backend/app/workers/tasks/outreach.py's _draft_with_llm LLM-call shape
(Perplexity company context -> GPT-4o-mini JSON-mode call) but returns its
result directly as the RQ job's return value instead of writing a new
database row — see task-orchestration/machine-2-parallel-tracks/
10-resume-tailoring.md's Goal section for why. Does not import from or modify
app.workers.tasks.outreach / app.modules.outreach — independent feature that
happens to share a calling convention.
"""

from __future__ import annotations

import asyncio
import json
import logging
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.database.orm_registry  # noqa: F401
from app.clients.perplexity import PerplexityClient
from app.clients.retry import with_transient_retry
from app.core.config import Settings, get_settings
from app.database.session import SessionLocal, engine
from app.domain.candidate import CVData
from app.infrastructure.redis import close_redis
from app.modules.documents.models import CandidateDocument

logger = logging.getLogger(__name__)

_TAILOR_SYSTEM_PROMPT = """
You are tailoring a candidate's resume/CV content for a specific target company and
(optionally) a specific role there, using ONLY the candidate's real, existing background —
never invent skills, employers, dates, or achievements the candidate did not provide. Reorder
and re-emphasize existing bullet points and skills to foreground what is most relevant to the
target company/role, and lightly rephrase (not fabricate) bullet points to use language closer
to the target company's domain, drawing on the provided public company context if given. Return
JSON: {"summary": <string, 2-3 sentence professional summary tailored to this target>,
"emphasized_skills": [<string>, ...], "reordered_bullets": [<string>, ...]}. If the provided
candidate background is too sparse to tailor meaningfully, still return the same JSON shape with
your best-effort output rather than an error.
""".strip()


def tailor_resume_job(
    user_id: str, document_id: str, target_company: str, target_role: str | None = None
) -> dict[str, object]:
    return asyncio.run(_tailor_resume_job(user_id, document_id, target_company, target_role))


async def _tailor_resume_job(
    user_id: str, document_id: str, target_company: str, target_role: str | None = None
) -> dict[str, object]:
    try:
        async with SessionLocal() as session:
            doc_result = await session.execute(
                select(CandidateDocument).where(
                    CandidateDocument.id == UUID(document_id),
                    CandidateDocument.user_id == UUID(user_id),
                )
            )
            document = doc_result.scalar_one_or_none()
            if not document or document.processing_status != "completed":
                raise ValueError(
                    f"Document {document_id} not found or not fully processed for user {user_id}"
                )

            cv_data = (
                CVData(**(document.extracted_data or {})) if document.extracted_data else CVData()
            )

            perplexity = PerplexityClient()
            context = await perplexity.get_company_context(target_company, target_role)

            settings = get_settings()
            tailored = await _tailor_with_llm(
                cv_data, target_company, target_role, context["summary"], settings, session
            )
            tailored["research_degraded"] = context["source"] != "perplexity"
            return tailored
    finally:
        await close_redis()
        await engine.dispose()


async def _demand_context_line_for_tailoring(
    cv_data: CVData, target_role: str | None, settings: Settings, db: AsyncSession
) -> str | None:
    """One short, factual line about job-market demand for the tailoring target role,
    or (if no target_role given) the candidate's first desired_roles entry with actual
    snapshot data; None if the flag is off, no role signal is available, or no
    snapshot data exists for any candidate role. Mirrors
    backend/app/workers/tasks/outreach.py's _demand_context_line
    (07-demand-intelligence-resume-integration.md) exactly: same flag-gated,
    additive, early-return-before-any-query contract, applied here to the
    resume-tailoring prompt instead of the outreach-drafting prompt.

    The `app.modules.demand_intelligence` import below is deliberately deferred
    (module-local, not top-of-file) rather than a top-level import: this track
    was built in parallel with track 02 (which owns that module) in the same
    working tree, and the module may not exist yet at import time depending on
    dispatch/merge order. Deferring the import means this file always loads
    cleanly regardless of that ordering, while the flag-off default keeps the
    import (and the whole demand-intelligence read path) unreached in the
    common case anyway — see the release-blocking "byte-identical when
    disabled, zero extra DB calls when disabled" requirement this mirrors.
    """
    if not settings.enable_demand_intelligence_in_resume_tailoring:
        return None
    role_candidates = ([target_role] if target_role else []) + list(cv_data.desired_roles or [])
    if not role_candidates:
        return None

    from app.modules.demand_intelligence.service import get_top_countries_for_role

    for role in role_candidates:
        snapshots = await get_top_countries_for_role(db, role, limit=3)
        if snapshots:
            countries = ", ".join(s.country_iso2.upper() for s in snapshots)
            return (
                f"Note: recent job-market data shows the highest current demand for "
                f"{role} is in {countries}. If relevant to the candidate's own stated "
                f"background, you may reflect this market context lightly (e.g. framing "
                f"relevant experience/skills in a way that resonates with that market) — "
                f"never state or imply the candidate is open to relocating or working "
                f"remotely in a specific location unless the candidate's own background "
                f"already says so."
            )
    return None


async def _tailor_with_llm(
    cv_data: CVData,
    target_company: str,
    target_role: str | None,
    company_context: str,
    settings: Settings,
    db: AsyncSession,
) -> dict[str, object]:
    api_key = settings.openai_api_key.strip()
    if not api_key:
        return {
            "summary": (
                f"{cv_data.current_role or 'Experienced professional'} with "
                f"{cv_data.total_years_experience or 'several'} years of experience, "
                f"interested in opportunities at {target_company}."
            ),
            "emphasized_skills": cv_data.technical_skills[:8],
            "reordered_bullets": [],
        }

    candidate_summary = (
        f"Current role: {cv_data.current_role or 'N/A'}. "
        f"Skills: {', '.join(cv_data.technical_skills)}. "
        f"Years of experience: {cv_data.total_years_experience or 'N/A'}. "
        f"Work history: {json.dumps(cv_data.work_history or [])}."
    )
    user_content = (
        f"Candidate background: {candidate_summary}\n"
        f"Target company: {target_company}\n"
        f"Target role: {target_role or 'not specified'}\n"
        f"Public company context: {company_context or '(none available)'}"
    )

    demand_line = await _demand_context_line_for_tailoring(cv_data, target_role, settings, db)
    if demand_line:
        user_content = f"{user_content}\n{demand_line}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        # raise_for_status() must run *inside* the retried operation, not after
        # with_transient_retry returns — httpx doesn't raise on 4xx/5xx by itself,
        # so calling it outside would mean status-code errors (429/502/503/504)
        # never actually trigger a retry, only network-level failures would.
        async def _do_post() -> httpx.Response:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": _TAILOR_SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.3,
                },
            )
            resp.raise_for_status()
            return resp

        response = await with_transient_retry(_do_post)
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return {
            "summary": parsed.get("summary", ""),
            "emphasized_skills": parsed.get("emphasized_skills", []),
            "reordered_bullets": parsed.get("reordered_bullets", []),
        }
