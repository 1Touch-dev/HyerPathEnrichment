# Machine 2, Track 10 — Ephemeral Resume Tailoring

## Depends on

The existing outreach-drafting LLM call shape in `backend/app/workers/tasks/outreach.py`
(`_draft_with_llm`'s RQ-job + OpenAI-chat-completions-with-`json_object`-response-format pattern)
and `backend/app/clients/perplexity.py`'s `PerplexityClient.get_company_context` (reused as-is for
the "target company" context this feature personalizes against — same client, same fail-soft
"empty summary, not an exception" contract). Also depends on `backend/app/domain/candidate.py`'s
`CVData` as the input shape (read-only).

## Goal — ephemeral, on-demand, explicitly NOT a new persisted document type

Given a candidate's existing base resume/CV data and a target company (+ optional target role),
generate a tailored resume version via one LLM call, returned directly to the caller. **This
output is never persisted as its own row/table.** Every request regenerates the tailored version
fresh from the candidate's current `CandidateDocument.extracted_data` — there is no
`TailoredResume` model, no new migration, no new table anywhere in this chunk.

This mirrors how `backend/app/modules/outreach/service.py`'s `send_message()` already documents
real SMTP sending as explicitly out of scope for that feature — this chunk similarly documents,
up front, that "regenerate tailored resume text" is the entire feature; a candidate who wants to
keep a particular tailored version does so by copying the returned text themselves (into their
own document editor, wherever that lives, exactly as `send_message()`'s docstring already
describes "the candidate is expected to copy/send the text themselves" for outreach today). If a
future chunk wants a "save this tailored version" feature, that is new persisted-storage scope
requiring a real decision (a new table, retention/deletion rules, etc.) — do not add one here
speculatively.

**Why ephemeral, not persisted:** a tailored resume is regenerated per company/role pair on
demand; persisting every generation would create unbounded per-candidate storage growth with no
natural retention boundary (unlike `CvFeedbackReport`, which is bounded — one report per
document-processing event) and would raise a data-retention question (is a stale tailored
version for a company the candidate never actually applied to worth keeping?) that this chunk
does not need to answer, because the feature works correctly without ever answering it.

## Files to create

- `backend/app/modules/resume_tailoring/__init__.py`
- `backend/app/modules/resume_tailoring/schemas.py`
- `backend/app/modules/resume_tailoring/service.py`
- `backend/app/modules/resume_tailoring/router.py`
- `backend/app/workers/tasks/resume_tailoring.py`

## Files to edit

- None outside the new module/task file above. No migration file — see Goal section.

## Design: mirror outreach's RQ-job shape, but the RQ result IS the ephemeral store

`OutreachService.request_draft` enqueues a job and returns `{"rq_job_id": ..., "message": ...}`
immediately (async, non-blocking, per the existing convention `03`'s dependent chunks all
inherit). This chunk follows the exact same enqueue-and-poll shape — **but where outreach
persists its result onto a new `OutreachMessage` row, this chunk deliberately does not create any
row at all.** Instead, it relies on RQ's own built-in job-result storage: RQ keeps a job's return
value in Redis for `result_ttl` seconds after completion (default 500s; this chunk sets it
explicitly, see below), retrievable via `Queue.fetch_job(job_id).result` — the exact same
`queue.fetch_job(job_id)` accessor `backend/app/modules/admin/queues_service.py` already uses for
introspecting job state. This gives genuinely ephemeral storage (bounded TTL, no DB row, expires
automatically) using infrastructure that already exists in this repo, rather than inventing a new
cache mechanism.

```python
# backend/app/workers/queue.py — no edit needed to this file itself, but this
# chunk's enqueue call (in resume_tailoring/service.py) must pass a generous
# result_ttl explicitly, since the RQ default (500s) may be too short for a
# candidate to review a tailored resume before it expires:
queue.enqueue(
    "app.workers.tasks.resume_tailoring.tailor_resume_job",
    str(user_id),
    document_id,
    target_company,
    target_role,
    job_timeout=60,
    result_ttl=1800,  # 30 minutes — long enough to review/copy, short enough to
                       # stay genuinely ephemeral, not a de facto permanent store
)
```

## `backend/app/workers/tasks/resume_tailoring.py`

```python
"""RQ worker task: generate an ephemeral, on-demand tailored resume version for
one candidate + target company/role pair. Mirrors
backend/app/workers/tasks/outreach.py's _draft_with_llm LLM-call shape (Perplexity
company context -> GPT-4o-mini JSON-mode call) but returns its result directly as
the RQ job's return value instead of writing a new database row — see this
module's parent 10-resume-tailoring.md Goal section for why."""

from __future__ import annotations

import asyncio
import json
import logging
from uuid import UUID

import httpx
from sqlalchemy import select

import app.database.orm_registry  # noqa: F401
from app.clients.perplexity import PerplexityClient
from app.clients.retry import with_transient_retry
from app.core.config import get_settings
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
            tailored = await _tailor_with_llm(cv_data, target_company, target_role, context["summary"], settings)
            tailored["research_degraded"] = context["source"] != "perplexity"
            return tailored
    finally:
        await close_redis()
        await engine.dispose()


async def _tailor_with_llm(
    cv_data: CVData,
    target_company: str,
    target_role: str | None,
    company_context: str,
    settings,
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

    async with httpx.AsyncClient(timeout=60.0) as client:
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
```

Note the deliberate absence of any `session.add(...)`/`session.commit()` writing a new row in
`_tailor_resume_job` — the function reads `CandidateDocument` (existing, unmodified) and returns a
plain dict; it never persists the tailored output anywhere except RQ's own TTL-bound result
store, per the Goal section.

## `backend/app/modules/resume_tailoring/schemas.py`

```python
from __future__ import annotations

from pydantic import BaseModel, Field


class TailorResumeRequest(BaseModel):
    document_id: str
    target_company: str = Field(..., min_length=1, max_length=255)
    target_role: str | None = Field(default=None, max_length=255)


class TailorResumeJobResponse(BaseModel):
    rq_job_id: str
    message: str = "Resume tailoring started"


class TailoredResumeResultResponse(BaseModel):
    status: str  # "queued" | "started" | "finished" | "failed" | "not_found"
    summary: str | None = None
    emphasized_skills: list[str] = Field(default_factory=list)
    reordered_bullets: list[str] = Field(default_factory=list)
    research_degraded: bool | None = None
```

## `backend/app/modules/resume_tailoring/service.py`

```python
async def request_tailoring(
    db: AsyncSession, *, user_id: UUID, body: TailorResumeRequest, redis_conn: Redis
) -> TailorResumeJobResponse:
    """Verifies the candidate owns a completed document (same check
    OutreachService.request_draft already performs), then enqueues
    tailor_resume_job with an explicit result_ttl=1800. No lock/dedup key is
    needed here the way outreach's request_draft uses one — regenerating the same
    tailoring twice is not "duplicate work" worth blocking (unlike outreach,
    where two drafts to the same company could confuse a candidate about which
    to send); this feature is explicitly idempotent-safe to call repeatedly."""
    ...


def get_tailoring_result(rq_job_id: str, redis_conn: Redis) -> TailoredResumeResultResponse:
    """Queue.fetch_job(rq_job_id) — same accessor queues_service.py already uses.
    Maps RQ's get_status() ('queued'/'started'/'finished'/'failed') plus, when
    finished, job.result (the dict _tailor_resume_job returned) into the response
    schema above. Returns status='not_found' if fetch_job returns None (job
    expired past its result_ttl, or the id never existed) rather than 404ing —
    letting the caller decide how to present 'this has expired, please
    regenerate' rather than baking that into an HTTP status code."""
    ...
```

## `backend/app/modules/resume_tailoring/router.py`

```
POST /api/resume-tailoring          -> request_tailoring   (returns {rq_job_id, message})
GET  /api/resume-tailoring/{rq_job_id} -> get_tailoring_result (poll for the result)
```

Both endpoints require authentication only (`VerifiedUser`), same as outreach's own
draft-request endpoint — no new permission resource needed; a candidate tailoring their own
resume needs no elevated permission, and (per this chunk's scope) no recruiter-facing variant is
built here — if a recruiter should be able to trigger tailoring on a candidate's behalf later,
that is an extension of `09`'s recruiter-action pattern, not this chunk (this chunk is
scoped to the candidate acting on their own document only; `document_id`/`user_id` ownership is
checked exactly like every other candidate-owned-document endpoint in this codebase).

## Ambiguities resolved

- **Should this reuse `OutreachMessage`/a variant of it instead of a brand-new module?** No —
  `OutreachMessage` represents a message sent *to a third party* (a hiring manager), with
  CAN-SPAM/suppression/send-tracking concerns that don't apply here at all (a tailored resume is
  never "sent" anywhere by this feature; it's returned to the candidate who requested it). Reusing
  that model would pull in unrelated columns (`recipient_email`, `sent_at`, `admin_blocked`) that
  make no sense for this feature and would need to be nullable/unused, which is worse than a
  small, purpose-built module.
- **Why RQ result-TTL instead of just calling the LLM synchronously in the request handler?**
  Either would work functionally (the LLM call itself takes a few seconds). RQ is chosen to
  literally mirror "the same LLM-call shape as the existing outreach drafting pipeline," per this
  chunk's explicit brief — outreach's `request_draft` is async/enqueue-and-poll, so this feature
  follows the same shape for consistency with the one existing precedent in this codebase for
  "candidate-facing on-demand LLM generation," rather than introducing a second, synchronous
  calling convention for a materially similar feature.
- **What happens if the candidate's document is still processing?** Same 409 `CandidateDocument`
  ownership/completeness check as `OutreachService.request_draft` — this chunk does not invent a
  different completeness rule.

## Do not touch

- `backend/app/modules/outreach/` — read-only reference for its LLM-call shape; no import from
  this chunk's code into `outreach`'s modules or vice versa, they remain fully independent
  features that happen to share a calling convention.
- `backend/app/modules/documents/cv_chat_service.py`, `service.py` — `CandidateDocument` is read
  only in this chunk; nothing here writes back to `extracted_data` (unlike the CV chatbot, which
  does write back) — tailoring never mutates the candidate's stored base resume data.
- Do not add a new Alembic migration, table, or column anywhere in this chunk — see Goal section;
  this is the single most important boundary here.
- `backend/app/clients/perplexity.py` — reused read-only via `get_company_context`; not modified.

## Verification

- Test: `request_tailoring` for a candidate with a `processing_status="completed"` document
  enqueues a job and returns an `rq_job_id`.
- Test: `request_tailoring` for a document not owned by the caller, or not yet processed, 404s/409s
  (mirroring outreach's existing equivalent checks).
- Test: `_tailor_with_llm` with the OpenAI call mocked returns a dict matching
  `TailoredResumeResultResponse`'s shape; when the API key is unset, returns the offline fallback
  without raising (mirrors `_draft_with_llm`'s own no-api-key fallback branch).
- Test: `get_tailoring_result` on a completed job returns `status="finished"` plus the tailored
  content; on an expired/unknown job id returns `status="not_found"`, not a 500.
- **No-persistence regression test (release-blocking for this chunk):** after a full
  `request_tailoring` -> job execution -> `get_tailoring_result` cycle, assert no new row exists in
  any table this chunk could plausibly have written to (query `CandidateDocument` for the same
  document and assert `extracted_data`/`updated_at` are unchanged; assert no new table this chunk
  might have been tempted to add actually exists in the schema) — enforces the "genuinely
  ephemeral, not persisted" requirement structurally, not just by omission in this doc.
