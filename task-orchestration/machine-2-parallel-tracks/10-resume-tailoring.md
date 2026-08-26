# Machine 2, Track 10 — Ephemeral Resume Tailoring

## Depends on

The existing outreach-drafting LLM call shape in `backend/app/workers/tasks/outreach.py`
(`_draft_with_llm`'s RQ-job + OpenAI-chat-completions-with-`json_object`-response-format pattern)
and `backend/app/clients/perplexity.py`'s `PerplexityClient.get_company_context` (reused as-is for
the "target company" context this feature personalizes against — same client, same fail-soft
"empty summary, not an exception" contract). Also depends on `backend/app/domain/candidate.py`'s
`CVData` as the input shape (read-only).

**Closing a dangling promise:** `02-country-demand-intelligence.md`'s "India/Middle East
resume-personalization consumer" section already names this file as a *future consumer* of its
`get_top_countries_for_role()` read path, but until the "Demand-intelligence context injection"
section below was added, this file's own dependency list never actually included `02` — the
promise was one-directional and undischarged. This chunk now depends on `02-country-demand-
intelligence.md`'s `get_top_countries_for_role(db, role_query, limit)` function (same read path,
same signature, same "most recent snapshot, `role_bucket` case-insensitive substring match" read
semantics `07-demand-intelligence-resume-integration.md` already established as the read-side
convention) and mirrors `07`'s own `_demand_context_line` shape and flag-gated, additive,
byte-identical-when-disabled contract — see "Demand-intelligence context injection" below.

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

- `backend/app/core/config.py` — new `enable_demand_intelligence_in_resume_tailoring` flag, see
  "Demand-intelligence context injection" below. No migration file — see Goal section (this flag
  addition is config-only, not a schema change).

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

**Cross-reference (2026-08-26): AI-agent supervision.** Per
`machine-2-parallel-tracks/04-rbac-admin-platform.md`'s new "AI-agent supervision
(audit/oversight view)" section (leadership-confirmed scope: "ai agent supervision, of all job
applications cvs eyes"), `_tailor_resume_job` must insert an `AiActionAuditLog` row
(`action_type="resume_tailoring"`, `candidate_user_id=user_id`, `triggered_by_user_id=None` — the
candidate triggers their own tailoring, there is no recruiter in this loop, per this chunk's
Router section's own "no recruiter-facing variant is built here" note, `related_id=None` since
the tailored output itself is never persisted, `summary` carrying `target_company`/`target_role`
as short text) after generating the tailored result, alongside (not instead of) RQ's own
result-TTL storage. This is a small, additive write — it does not create a `TailoredResume`
row and does not weaken this chunk's own release-blocking "no-persistence" invariant (see
Goal section and the "No-persistence regression test" in Verification below): the audit-log row
records *that a tailoring event happened*, never the generated resume text itself. If `04`'s
`AiActionAuditLog` table doesn't exist yet when this chunk is implemented, this write is a
no-op/deferred TODO flagged in the PR description, not a hard blocker for this chunk's own core
tailoring functionality.

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

## Demand-intelligence context injection

**Closes `02-country-demand-intelligence.md`'s dangling "future consumer" promise.** `02`'s own
"India/Middle East resume-personalization consumer" section already names this file as a future
consumer of its `CountryDemandSnapshot` data; this section is what actually discharges that
promise. It mirrors `07-demand-intelligence-resume-integration.md`'s design for outreach drafting
exactly — same flag-gated, additive, byte-identical-when-disabled contract, same
`get_top_countries_for_role` read path — applied to this chunk's resume-tailoring prompt instead
of outreach's drafting prompt.

**Precedent.** LinkedIn's own Economic Graph/Skills Graph engineering work documents using
aggregate labor-market/skills-demand data to steer job-seeker-facing guidance at platform scale
(https://economicgraph.linkedin.com/blog/Quantifying-skills-gaps-with-the-economic-graph,
https://www.linkedin.com/blog/engineering/skills-graph/building-linkedin-s-skills-graph-to-power-a-skills-first-world),
and Indeed Hiring Lab's own large-sample research is explicit that skill/market strategy should
vary by location, not be treated as one global signal
(https://www.hiringlab.org/2026/04/09/skill-set-match-in-job-postings/). Both support the general
principle this section applies (market-demand data should inform job-seeker-facing content,
varying by location) — see "Ambiguities resolved" below for the honest limit of what these
sources actually establish.

**Config flag.** Add to `backend/app/core/config.py`, following the exact naming convention
`07-demand-intelligence-resume-integration.md`'s own `enable_demand_intelligence_in_outreach`
flag establishes (verified against that file directly — see its "Config flag" section):

```python
# Demand intelligence -> resume-tailoring integration (machine-2/10): inject a
# short, factual country-demand context line into the resume-tailoring prompt
# when a target role (or, absent that, one of the candidate's desired_roles) has
# CountryDemandSnapshot data. Mirrors enable_demand_intelligence_in_outreach's
# contract exactly (07-demand-intelligence-resume-integration.md). Default False
# — additive, low-risk, but off until validated against real tailored output;
# also has no effect unless enable_demand_intelligence (02's flag) is also True.
enable_demand_intelligence_in_resume_tailoring: bool = Field(
    default=False, alias="ENABLE_DEMAND_INTELLIGENCE_IN_RESUME_TAILORING"
)
```

**Wiring.** Import the same read path `07` already established:

```python
from app.modules.demand_intelligence.service import get_top_countries_for_role
```

Add a helper in `backend/app/workers/tasks/resume_tailoring.py`, mirroring `07`'s
`_demand_context_line` shape (same early-return-before-any-query contract, same "check role
candidates in order, stop at the first one with snapshot data" behavior) but sourced from this
chunk's own `target_role` parameter first — since a resume-tailoring request already carries an
explicit target role, unlike outreach drafting, which only has the candidate's `desired_roles` to
go on — falling back to `cv_data.desired_roles` when `target_role` is unset:

```python
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
    resume-tailoring prompt instead of the outreach-drafting prompt."""
    if not settings.enable_demand_intelligence_in_resume_tailoring:
        return None
    role_candidates = ([target_role] if target_role else []) + list(cv_data.desired_roles or [])
    if not role_candidates:
        return None
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
```

Threading `db: AsyncSession` into `_tailor_with_llm` is a signature change, same as `07`'s
identical note for `_draft_with_llm` — `_tailor_with_llm` is currently called from
`_tailor_resume_job`, which already holds an open `session` (`async with SessionLocal() as
session:`, per the Design section above); pass that same session through rather than opening a
second one. Append the returned line to `user_content` when not `None`, after the existing
company-context line and before any closing instruction (this chunk's current `user_content`
construction — see the Design section's `_tailor_with_llm` code above — has no closing
instruction after the company-context line today, so in practice this is simply the new last
line):

```python
    demand_line = await _demand_context_line_for_tailoring(cv_data, target_role, settings, db)
    if demand_line:
        user_content = f"{user_content}\n{demand_line}"
```

**Keyword-stuffing risk (named tradeoff).** Injecting market-demand language into a tailoring
prompt raises the same risk any keyword-optimization mechanism raises: over-optimizing resume
text for a machine-readable signal rather than a human reader. General resume-tooling guidance —
this is secondary-source consensus circulating across resume-optimization commentary, **not**
primary documentation from any specific named vendor, and this file is explicit about that
distinction rather than attributing it to one — converges around roughly 1.5-3% keyword density
as a rough ceiling before tailoring reads as stuffed, and a simpler practical test: "would a human
reader notice this phrase is there for a machine, not for them?" This chunk's mitigation is the
prompt language itself (`_TAILOR_SYSTEM_PROMPT`, unchanged by this section, already instructs
"lightly rephrase, not fabricate") plus the demand line's own explicit "if relevant" framing above
— this section does not add a numeric keyword-density check or scorer, since that would be new
scope disproportionate to a one-line, flag-gated prompt addition; it is named here as a tradeoff
the flag-gate and human review (mirroring `03`'s identical rollout recommendation for its own new
LLM-prompt mechanism) should watch for before enabling broadly.

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
- **Is the "inject one demand-data sentence into a resume-tailoring LLM prompt" mechanism itself
  a proven, published pattern?** No, and this file says so honestly rather than overclaiming: no
  source cited in "Demand-intelligence context injection" above (LinkedIn's Economic Graph/Skills
  Graph blog posts, Indeed Hiring Lab's location-variance research) describes this *exact*
  mechanism — injecting a single factual sentence into a resume-tailoring LLM prompt. Those
  sources establish the general principle that market-demand data should inform job-seeker-facing
  content and should vary by location; the specific "one-sentence prompt injection" delivery
  mechanism is this doc set's own small, additive invention, directly analogous to (but no more
  proven than) `07-demand-intelligence-resume-integration.md`'s identical invention for the
  outreach-drafting prompt. Accordingly this section ships with the same posture `07` shipped
  with: flag off by default (`enable_demand_intelligence_in_resume_tailoring`), byte-identical to
  pre-change output when disabled, the injected line explicitly framed to the LLM as optional/
  "if relevant" context (see the `_demand_context_line_for_tailoring` docstring/return value
  above), and an explicit instruction never to fabricate relocation/remote-work willingness the
  candidate has not themselves expressed — this last point is a resume-tailoring-specific risk
  `07`'s outreach version did not need to guard against in the same way, since a resume is a
  document a candidate submits as their own representation, not a message a candidate is actively
  drafting and can immediately edit before sending.

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
- `backend/app/modules/demand_intelligence/` (created by `02`) — read-only import of
  `get_top_countries_for_role`; no changes to that module's models/service/router/schemas, the
  identical Do-not-touch scope `07-demand-intelligence-resume-integration.md` already holds
  itself to for the same import.
- `backend/app/modules/outreach/models.py`, `schemas.py`, `service.py`,
  `backend/app/workers/tasks/outreach.py` — this section reuses the *pattern* `07` established
  for outreach, but does not import from or modify outreach's own module; the two
  `_demand_context_line*` helpers are independent functions in independent files that happen to
  share a shape.
- Do not build any embedding, ranking, or "best country to target" scoring logic — see
  `07-demand-intelligence-resume-integration.md`'s Goal section's explicit JUDE-architecture scope
  cut, which this section inherits unchanged rather than re-litigating.
- Do not add a keyword-density scorer/checker — see "Keyword-stuffing risk (named tradeoff)"
  above for why this is named as a risk to watch for in human review, not built as an automated
  gate in this chunk.

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
- **Regression test (required, byte-identical check) for demand-intelligence injection:** with
  `enable_demand_intelligence_in_resume_tailoring` off (the default), assert the constructed
  `user_content` for a given `cv_data`/`target_company`/`target_role`/company-context combination
  is byte-identical to the `user_content` that would have been constructed before this section's
  changes — the same regression bar `07-demand-intelligence-resume-integration.md` holds its own
  identical flag to.
- Test: with the flag on and a `target_role` (or, absent that, a `cv_data.desired_roles` entry)
  that has `CountryDemandSnapshot` data, assert the prompt sent to the mocked LLM call includes
  the demand-context line, formatted with the correct top-country codes.
- Test: with the flag on but no `CountryDemandSnapshot` rows matching `target_role` or any of
  `cv_data.desired_roles`, assert the prompt is unaffected (no stray "Note: ..." line, no
  exception) — mirrors `07`'s identical no-match test.
- Test: assert `_demand_context_line_for_tailoring` does not call `get_top_countries_for_role` at
  all when the flag is off (mock/spy on the import and assert zero calls) — mirrors `07`'s
  identical "zero extra DB round-trips when disabled" requirement.
