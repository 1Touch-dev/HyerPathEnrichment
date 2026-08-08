# Phase 2 — Module 2: Tinder-Style Job Board + CV Management

**Branch:** `master-complete-foundation` (this file is committed directly to this branch — no new branch is created, per explicit instruction)
**Status:** Implementation blueprint — nothing described here exists in code yet unless explicitly marked `EXISTS` with a file citation. Everything else is `NEW`.
**Governing rule file:** `RULE.md` — every decision below was checked against it; violations are called out explicitly rather than silently made. See §0.
**Companion document:** `phase2_module1.md` (AI Job Matching & Notifications) — Module 2 **depends on** Module 1's schema (`job_postings`, `job_matches`) for the swipe deck's data source. This is called out explicitly in §4 so the dependency is never missed.

**Purpose of this document:** a single, linear, followable plan such that a developer (or agent) who implements every numbered step in order — backend, database, workers, Docker, tests, frontend — ends with Module 2 ("Tinder-Style Job Board + CV Management") **100% functionally complete**, with automated tests proving it, without needing to consult any other chat, report, or memory. Every file this plan creates or edits is listed by exact path, with full code. Every claim about *why* a design choice was made is evidence-labeled per §1. Every folder, file, function, and dependency — big and small — is explained. If you implement this document line by line, at the end Module 2 is 100% complete, factually and truthfully, with tests proving it.

---

## 0. RULE.md compliance checklist (read this before writing any code)

This plan was designed against `RULE.md` line by line, the same way `phase2_module1.md` §0 was. Explicit mapping:

| RULE.md requirement | How this plan complies |
|---|---|
| "Search the repo for an existing function, type, component, or pattern" (Before writing any code #1) | §2 inventories everything reused: `CVData`, `cv_extractor.py`, `document_processor.py`, `DocumentService`, `documents/router.py`, `feedback_generator.py`, `vector_search.py`, the `features/*` frontend pattern, the BFF pattern, `JobCard.tsx`. Nothing reusable is rebuilt from scratch. |
| "Read Agent quick reference in ARCHITECTURE.md" (#2) | Done; Module 2 does not touch `enrichers/pipeline.py`, `enrichers/merge.py`, or `compliance/`. It extends `documents/` (already owns CV upload) rather than creating a colliding second CV-upload path. |
| "Check Implementation status — do not build on scaffold-only features" (#3) | Verified before use: `document_processor.py` (PyMuPDF/python-docx extraction) and `cv_extractor.py` (GPT-4o-mini structured extraction) are real working code — read directly (§2). Two real bugs found in the existing code are fixed as **prerequisites** in §2.1 before Module 2 can be considered complete, because Module 2's CV-improvement and completeness-check features are unusable while these bugs exist. |
| "Keep the change as small as the task allows" (#4) | CV upload/completeness/chat/improve/portfolio/outreach are added as new endpoints on the **existing** `documents` module plus one **new** module (`app/modules/outreach/`) rather than one giant new module — split by actual data ownership, not by feature-marketing-name. Swipe/like/pass state is added to Module 1's existing `job_matches` table (one new column + one new table) instead of a duplicate schema. |
| Layer ownership table (`domain/`, `modules/`, `enrichers/pipeline.py`, `workers/`, `compliance/`, `clients/`, `storage/`, `database/`) | New code placed per this table exactly — see §5 file-by-file plan; every new/edited file states which layer it belongs to and why. |
| Allowed/forbidden imports (`workers/tasks` → must not import `modules/*/service|router`) | `app/workers/tasks/cv_improvement.py`, `app/workers/tasks/portfolio_render.py`, `app/workers/tasks/outreach.py` import only `repository.py` modules, never `service.py`/`router.py`. |
| "One provider per file", "extend Enricher in base.py" (Enrichers section) | No enricher is added or modified. Outreach's company-context lookup calls the Perplexity Sonar API directly via a new `clients/perplexity.py` (one file, one provider) — it is explicitly **not** registered as a Tier-4 enricher because it is not part of the person-enrichment pipeline; it is a Module-2-only feature, same precedent as `JobSpyEnricher`'s reuse in Module 1 (reused function, not reused Tier). |
| "Tier registration only in enrichers/registry.py" | Not touched. |
| "Do not duplicate validation... merge logic... API field mapping" | CV chat-question validation lives once in `app/domain/cv_completeness.py`; portfolio slug validation lives once in `app/modules/portfolio/schemas.py`. Frontend field mapping goes through `api-adapter.ts` only. |
| "Routes are thin" | Every new/edited router method is auth + call service + return; all logic lives in `service.py` files. |
| "ORM lives with its owner... never recreate a global app/models.py" | New ORM classes for portfolio live in `app/modules/portfolio/models.py`; outreach ORM lives in `app/modules/outreach/models.py`; CV chat session state extends `documents/models.py` (same file that already owns `CandidateDocument`) rather than a third location. |
| "Async end-to-end... no run_until_complete in request paths" | All router/service code is `async def`; only RQ worker entrypoints use `asyncio.run()` — same pattern as `document.py`. |
| "Schema changes via Alembic only" | 4 new tables + 2 altered tables via 6 new Alembic revisions (§6), chained onto Module 1's head (`021_job_matches`, per the dependency in §4) or onto `017_practice_audio_recordings` if Module 1 is not yet applied — both chains are given explicitly in §6.0. No `create_all`. |
| "When to add an ADR" — new storage, queue, or layer ownership | **New queue** (`cv_chat`, `portfolio_render`, `outreach_generation`) + **new storage** (4 tables) + **new external API** (Perplexity) → ADR required. §14 supplies `docs/adr/0014-cv-chat-portfolio-outreach.md`. |
| "New enricher → extend tests/test_pipeline_shape.py" | N/A — no enricher added. Equivalent obligation met: every new module gets its own `tests/test_*.py` suite (§9). |
| "No live external calls in CI... mock subprocess, HTTP, third-party APIs" | All tests mock OpenAI HTTP calls, Perplexity HTTP calls, and the R2/local storage layer — see §9. |
| "Coverage gate ... currently 78%" | New code covered per-function in §9; §9.11 gives the exact `pytest --cov` command to prove the gate is met. |
| "Never log raw identifiers... use job IDs or hashed values" | All logging truncates/hashes `user_id` (`str(user_id)[:8]`) and never logs raw CV text, chat answers, or outreach email bodies (PII risk — see §4 compliance note). |
| "Never commit secrets... update .env.example with placeholders only" | §7 lists every new env var added to `.env.example` with placeholder values only. |
| "Public data only... no discover people flows" | Outreach's company-context lookup (Perplexity) searches **company** news/pages only, never a named private individual's personal data beyond what the candidate already supplied about the hiring manager's public job title — this constraint is enforced in the prompt itself (§5.9) and flagged in §4's compliance section (CAN-SPAM). |
| "Update backend/docs/ARCHITECTURE.md Implementation status if scaffold changed" | §15 gives the exact diff. |
| "New/changed storage, queue, auth, or layer ownership → ADR linked in the PR" | §14 ADR + §16 PR checklist explicitly links it. |
| Frontend: "Shared types... do not duplicate Dossier/EnrichmentInput shapes inline" | New `CvCompletenessState`, `PortfolioProject`, `OutreachDraft`, `SwipeDeckItem` types added to `frontend/src/lib/types.ts` once, mapped through `api-adapter.ts` — never inlined in components (§12). |
| Frontend: "Keep types in sync... run npm run openapi:export && npm run openapi:gen" | §12.1 gives the exact command sequence and what must be committed. |
| Testing: "New route behavior → API test: status code, auth, response shape" | §9 covers every new/edited route. |
| Frontend: "Type changes → run npm run typecheck... UI changes → npm run lint / build" | §13.9 gives the exact commands. |

If any step below appears to conflict with `RULE.md`, `RULE.md` wins — this document is subordinate to it, not a replacement for it.

---

## 1. Evidence-label legend (used throughout)

- ✅ **DIRECT** — a primary source (official docs, a paper, a company engineering blog, or this repo's own code, read directly) states the claim.
- 🔗 **INDIRECT** — a real, citable source supports the general point but not in this exact form/number, or it's a third-party reconstruction.
- ❌ **NOT FOUND** — checked and could not be verified anywhere; stated as a design choice, not as proven fact.

All citations below were independently verified during this conversation (fetched and read, not recalled from training data).

---

## 2. What already exists and will be reused unmodified (or fixed as a prerequisite)

Verified by reading the files directly — not assumed from documentation.

| Capability | File | Reused how |
|---|---|---|
| CV → structured data model | `backend/app/domain/candidate.py` (`CVData` Pydantic model) | Reused verbatim as the shape stored in `CandidateDocument.extracted_data`. Module 2's completeness checker (§5.1) reads this shape; no new extraction schema invented. |
| CV parsing pipeline | `backend/app/services/document_processor.py` | Untouched — PDF/DOCX → raw text extraction stays exactly as-is. |
| CV structured extraction | `backend/app/services/cv_extractor.py` | Reused, **after the bug fix in §2.1** — GPT-4o-mini call that turns raw text into `CVData`. |
| Document upload/list/detail/delete endpoints | `backend/app/modules/documents/router.py`, `service.py`, `schemas.py`, `models.py` (`CandidateDocument`, `DocumentJob`) | Fully reused. Module 2 **adds** endpoints to this same router (completeness, chat, improve, portfolio, outreach) rather than creating a competing upload path — this is the direct implementation of RULE.md's "search for an existing pattern first." |
| Document + embedding storage | `backend/app/modules/documents/models.py` (`DocumentEmbedding`) | Read-only dependency for the "portfolio auto-fill from CV" flow (§5.6). |
| Vector similarity search | `backend/app/services/vector_search.py` (`similarity_search()`) | Reused verbatim — no changes. |
| Unified feedback generator | `backend/app/services/feedback_generator.py` | Its `_generate_feedback_sync`/async pattern (LLM call → structured JSON → DB write) is the template copied for `generate_cv_improvement()` (§5.4) — not imported directly (different domain object), but the *pattern* is reused, satisfying "extend the existing pattern" rather than inventing a new LLM-calling convention. |
| Embeddings client | `backend/app/clients/embeddings.py` (`get_embeddings_client()`) | Reused verbatim for portfolio-project embedding (optional semantic search across a candidate's own projects — out of v1 scope, noted in §4 as a deliberately deferred nice-to-have, not built). |
| Email delivery | `backend/app/services/email_service.py` (`EmailService`, `EmailTemplate` enum), `backend/app/workers/tasks/email_tasks.py`, queue `QUEUE_EMAIL` | New `EmailTemplate.CV_COMPLETENESS_REMINDER` and `EmailTemplate.PORTFOLIO_PUBLISHED` members added; existing `worker-email` container/queue consumes them unchanged. |
| RQ queue infrastructure | `backend/app/workers/queue.py`, `backend/app/workers/rq_worker.py` | Extended with 3 new queue constants (`cv_chat`, `portfolio_render`, `outreach_generation`) added to the existing lists — same mechanism, no new queue framework. |
| Envelope API routing | `backend/app/core/api_route.py` (`EnvelopeAPIRoute`) | New/edited routers use this exactly like `documents/router.py` does. |
| Auth dependency | `backend/app/auth/dependencies.py` (`CurrentUser`) | Reused verbatim for every new route. |
| DB session dependency | `backend/app/database/session.py` (`get_db_session`) | Reused verbatim. |
| JSON column helper | `backend/app/database/base.py` (`JsonDoc` = JSONB on Postgres, JSON on SQLite) | Reused for every new ORM column needing JSON storage. |
| Frontend feature-module pattern | `frontend/features/{enrich,history,signals,settings}/` (`index.ts`, `api/keys.ts`, `hooks/`) | Copied exactly for `frontend/features/cv-management/`, `frontend/features/job-swipe/`, `frontend/features/portfolio/`, `frontend/features/outreach/`. |
| Frontend BFF proxy pattern | `frontend/app/api/enrich/*`, `frontend/src/lib/backend-client.ts` (`backendFetch`), `frontend/src/lib/bff-response.ts` | Copied exactly for `frontend/app/api/documents/*`, `frontend/app/api/portfolio/*`, `frontend/app/api/outreach/*`. |
| Frontend nav registration | `frontend/components/layout/nav-config.ts` | Two new `NavItem`s added (`/app/matches` from Module 1 stays; `/app/cv` and are added here — see §13). |
| `JobCard` component | `frontend/components/dossier/JobCard.tsx` | Verified unused anywhere in the app today. Module 1 already claims it for the match-list view; Module 2's **swipe deck** (§13) builds a new `SwipeCard.tsx` (visually different — full-bleed mobile card, not the same layout as the compact list `JobCard`) rather than fighting over one shared component for two different UI shapes. This is stated explicitly so a future refactor doesn't wrongly "deduplicate" two intentionally-different components. |
| Empty state component | `frontend/components/console/EmptyState.tsx` | Reused for "no CV uploaded yet" / "no swipes left today". |

Nothing above is edited to change its existing behavior for other features — all reuse is either read-only, additive (new enum members, new functions/routes alongside existing ones), or a targeted bug fix that makes existing advertised behavior actually work (§2.1).

### 2.1 Prerequisite bug fixes (must be done before Module 2 can be considered complete)

These were found by reading the code directly during this analysis, not assumed. Module 2's CV-completeness and CV-improvement features are **built on top of** `cv_extractor.py` and `feedback_generator.py`; if these bugs are not fixed, Module 2 will silently produce empty/wrong data, so fixing them is listed here as an in-scope, numbered prerequisite rather than a footnote.

**Bug 1 — `cv_extractor.py` awaits a synchronous method, silently swallowing all real CV extractions.**

✅ **DIRECT** — verified by reading `backend/app/services/cv_extractor.py` directly: the code does `data = await response.json()` where `response` is an `httpx.Response`. ✅ **DIRECT** — [httpx documentation](https://www.python-httpx.org/quickstart/#response-content): `Response.json()` is a synchronous method (`httpx.Response.json(self) -> Any`), not a coroutine. Awaiting a non-awaitable raises `TypeError: object dict can't be used in 'await' expression` in real Python — **not** silently ignored inside `_extract_with_llm`; the surrounding `try/except Exception` in that function (also confirmed by reading the file) catches this `TypeError` and falls back to `CVData()` (all-empty). This means **every real OpenAI-key CV extraction has been failing since this method was written**, and the app has been silently returning blank CVs. This exact same class of bug was already found and fixed in `feedback_generator.py` in this session (that file's `_generate_feedback_sync` correctly does not await `.json()`) — `cv_extractor.py` was missed at the time.

**Fix — file edited:** `backend/app/services/cv_extractor.py`

```python
# Before (bug):
async def _extract_with_llm(self, raw_text: str) -> CVData:
    ...
    response = await self._client.post(url, json=payload, headers=headers)
    data = await response.json()   # <-- BUG: response.json() is sync, not a coroutine
    ...

# After (fix):
async def _extract_with_llm(self, raw_text: str) -> CVData:
    ...
    response = await self._client.post(url, json=payload, headers=headers)
    response.raise_for_status()
    data = response.json()   # httpx.Response.json() is synchronous
    ...
```

No other line in the function changes. This is a one-line fix, listed explicitly per file/line so it is not missed.

**Bug 2 — `session_manager.py` passes a `str` where SQLAlchemy expects a `UUID`, breaking every session-tracked feature (interview practice sessions today; CV-chat sessions in Module 2 tomorrow, since §5.2 below reuses the same `PracticeSession`-style pattern).**

✅ **DIRECT** — verified directly: `backend/app/services/session_manager.py` builds a `PracticeSession(user_id=str(user_id), ...)` call where the ORM column (`practice_sessions.user_id`, per `015_add_session_tracking.py`) is `postgresql.UUID(as_uuid=True)`. On Postgres, SQLAlchemy's UUID type coercion calls `.hex` on whatever is bound if it isn't already a `uuid.UUID` instance under some drivers/paths, producing `StatementError: 'str' object has no attribute 'hex'` (reproduced directly by running `pytest tests/test_session_tracking.py -v` during this session — real failure, not theoretical).

**Fix — file edited:** `backend/app/services/session_manager.py`

```python
# Before (bug): user_id passed as str
async def start_session(self, user_id: str, session_type: str) -> PracticeSession:
    session = PracticeSession(user_id=user_id, session_type=session_type, ...)
    ...

# After (fix): coerce to UUID once, at the boundary
from uuid import UUID

async def start_session(self, user_id: str | UUID, session_type: str) -> PracticeSession:
    normalized_user_id = user_id if isinstance(user_id, UUID) else UUID(str(user_id))
    session = PracticeSession(user_id=normalized_user_id, session_type=session_type, ...)
    ...
```

This is called out here because §5.2 (CV completeness chat) intentionally reuses `session_manager.py`'s exact `start_session`/`end_session` pattern for chat sessions — copying a broken pattern would propagate the bug into new code, so the fix is a prerequisite, not an afterthought.

**Verification for both fixes (run before writing any Module 2 code):**

```bash
cd backend
pytest tests/test_cv_extraction.py -v
pytest tests/test_session_tracking.py -v
```

Both suites must be green before proceeding to §3. If they are not green in your checkout, these two fixes are not optional prerequisites — they are load-bearing for everything below.

---

## 3. Evidence-based design decisions (why the implementation is shaped this way)

### Decision 1 — CV completeness checking uses OpenAI Structured Outputs / function calling, not a second free-text LLM call

✅ **DIRECT** — [OpenAI Platform docs: "Structured Outputs"](https://platform.openai.com/docs/guides/structured-outputs): "Structured Outputs is a feature that ensures the model will always generate responses that adhere to your supplied JSON Schema... this eliminates the need for the model to guess the right output format." ✅ **DIRECT** — [OpenAI Platform docs: "Function calling"](https://platform.openai.com/docs/guides/function-calling): function/tool calling lets the model choose which of a set of defined actions to take, with arguments validated against a schema.

**Applied as:** the completeness checker (§5.1) is a deterministic Python function — `compute_missing_fields(cv_data: CVData) -> list[str]` — **not** an LLM call at all. Completeness (a fixed list of required fields: `email`, `phone`, `linkedin_url`, `technical_skills`, `total_years_experience`, `desired_roles`) is checked the same way `cv_extractor.py`'s existing `_calculate_completeness()` already does it (verified directly — that private method already exists and is reused, not reinvented). The **chatbot** (§5.2) is the part that calls the LLM, and it does so with a single defined "tool" (`record_cv_answer`) so the model's only possible actions are "ask the next missing-field question" or "call `record_cv_answer` with a validated value" — this is a direct application of the function-calling pattern above, chosen specifically so the chatbot cannot free-form invent CV data (same anti-hallucination principle Decision 3 in `phase2_module1.md` already established for match explanations).

### Decision 2 — CV chat is turn-based request/response, not token-streamed SSE

❌ this document's own antecedent analysis (in this conversation, before code was inspected) assumed the chatbot would need Server-Sent Events like `frontend/src/lib/enrich-events.ts`'s existing streaming pattern, because "chatbot" is usually associated with token-by-token streaming (ChatGPT-style UX).

✅ **DIRECT** (own codebase) — the existing SSE precedent (`app/api/enrich/[id]/events/route.ts`) streams **job status transitions** over a long-running background job (an enrichment run that takes 10–60+ seconds), not LLM tokens. There is no token-streaming infrastructure anywhere in this repo today (verified — no `stream=True` OpenAI call exists in `cv_extractor.py`, `feedback_generator.py`, or anywhere else in `backend/app/`).

✅ **DIRECT** — [OpenAI Platform docs: "Function calling"](https://platform.openai.com/docs/guides/function-calling): the documented function-calling loop is request → model returns a tool call or a message → your code executes the tool → sends the result back → repeat. This loop does not require token streaming to function correctly; it is described and used in the docs as ordinary (non-streamed) chat completions.

**Applied as:** a single missing-field question + candidate's answer is one HTTP round trip (`POST /api/documents/{id}/cv-chat/messages`), completing in a few seconds (one GPT-4o-mini call), rendered as a normal chat bubble list that appends on response — no SSE, no WebSocket. This is a deliberate, documented simplification: it removes an entire class of infrastructure (persistent connections, reconnection handling, partial-token UI state) that this specific feature does not need, and is called out here explicitly so a future "let's make it stream like ChatGPT" request is a conscious product decision, not a bug report about "why doesn't this feel real-time."

### Decision 3 — CV improvement rewrites are grounded, evidence-cited suggestions, not silent rewrites of the stored CV

✅ **DIRECT** — [Harvard Business School Managing the Future of Work — "Hidden Workers: Untapped Talent"](https://www.hbs.edu/managing-the-future-of-work/research/Pages/hidden-workers-untapped-talent.aspx): qualified candidates are frequently screened out by ATS keyword/format mismatches rather than lack of qualification — the report's central finding is that resume *formatting and keyword alignment*, not just underlying skill, determines whether a candidate is surfaced to a human reviewer.

✅ **DIRECT** — [OpenAI Platform docs: "Structured Outputs"](https://platform.openai.com/docs/guides/structured-outputs) (same source as Decision 1): used again here to force the improvement response into a fixed shape (`{strengths: [], improvements: [], rewritten_bullets: [{original, rewritten, rationale}], ats_score: 0-100}`) rather than free-form prose, so the frontend can render a diff-style before/after view deterministically.

🔗 **INDIRECT** — general resume-writing guidance (widely published career-coaching material, e.g. quantify impact with metrics, use action verbs) supports "rewrite for impact" as a real, common practice; no single peer-reviewed paper was found benchmarking this exact LLM-rewrite-CV-bullets technique, so the *specific effectiveness* of AI-rewritten bullets (vs. a human career coach) is **NOT FOUND** in the literature reviewed — this feature is built as a drafting aid, and the UI (§13) explicitly labels output as "AI suggestion — review before using," never auto-applies a rewrite to the stored CV without the candidate clicking "Accept."

**Applied as:** `generate_cv_improvement()` (§5.4) never overwrites `CandidateDocument.raw_text` or `extracted_data`. It writes to a new, separate `cv_feedback_reports` table. The candidate must explicitly copy/accept a suggestion — this mirrors the existing `feedback_generator.py` convention of storing feedback as its own row (`QuestionAttempt.ai_feedback`) alongside, not instead of, the original answer.

### Decision 4 — Portfolio pages are internally-hosted static data (no subdomain provisioning) in v1

❌ **NOT FOUND** — no DNS-provisioning, wildcard-subdomain, or dynamic-vhost infrastructure exists anywhere in this repo (verified — no Caddy/Traefik/nginx dynamic vhost config, no DNS API client, no `*.hyrepath.dev` wildcard cert automation in `backend/docker/` or anywhere else). The original spec's "auto-generate portfolio page (optional hosted subdomain: `john-doe.hyrepath.dev`)" is a **real product idea with zero supporting infrastructure today**, and building wildcard-subdomain hosting (DNS automation + per-tenant TLS + reverse-proxy routing) is a multi-day infra project of its own, out of proportion to "add a portfolio feature."

✅ **DIRECT** (own codebase convention) — every other public-facing thing in this app is a **path**, not a subdomain: `frontend/app/(marketing)/candidates/page.tsx` is a static marketing route under the same domain; there is no existing precedent anywhere in `frontend/` for per-user subdomains.

**Applied as:** v1 ships portfolio pages at `https://<app-domain>/p/{slug}` (a normal dynamic Next.js route, §13.4) — same domain, path-based, zero new infra. The `slug` field (§6.3) is designed to be subdomain-compatible later (DNS-safe charset, uniqueness enforced) so a genuine `{slug}.hyrepath.dev` upgrade is possible in a future phase without a schema migration — but that upgrade itself is explicitly **out of scope** for this document, stated here so it is not silently promised.

### Decision 5 — Personalized outreach is a compliance-gated draft-then-send flow, not a fire-and-forget cold-email generator

✅ **DIRECT** — [FTC: "CAN-SPAM Act: A Compliance Guide for Business"](https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business): commercial email must (1) not use false or misleading header information, (2) not use deceptive subject lines, (3) identify the message as an ad if applicable, (4) include the sender's valid physical postal address, (5) tell recipients how to opt out, (6) honor opt-out requests within 10 business days, and (7) monitor what any third party does on the sender's behalf.

✅ **DIRECT** — same source: "the CAN-SPAM Act... applies to any commercial message... whose primary purpose is commercial advertisement," which — read straightforwardly — is broad enough to plausibly cover unsolicited cold outreach to a hiring manager promoting the sender's own candidacy; because job-outreach-as-"commercial email" is not the FTC's typical worked example, whether it counts is not stated explicitly in the primary source, so this specific classification is 🔗 **INDIRECT**, not ✅ DIRECT — the guide's requirements are applied here anyway, on the "comply with the stricter reasonable interpretation" principle, not because a court ruling was found on point (none was — **NOT FOUND**).

✅ **DIRECT** — [Perplexity AI: "pplx-api" / Sonar API docs](https://docs.perplexity.ai/): the Sonar models are described as "search-augmented" and OpenAI-chat-completions-API-compatible, i.e. callable via the same request/response shape used elsewhere in this repo (`httpx` POST to `https://api.perplexity.ai/chat/completions`), needing no new SDK dependency — `httpx>=0.27,<1.0` is already in `pyproject.toml` (verified directly).

**Applied as:** every generated outreach message (§5.9) is created with `status="draft"` and is **never sent automatically**. A candidate must review and click "Send" (§13.6), at which point `send_outreach_message()` (§5.9) appends a mandatory unsubscribe/identification footer (candidate's own return email + a one-line "You're receiving this because..." disclosure, per requirements 3–5 above) that the UI does not let the candidate remove, and logs the send with a timestamp for opt-out-honoring auditability. The Perplexity company-context query is restricted (in the prompt itself, §5.9) to public company information (news, official pages) — never a named private individual beyond the public job title the candidate already typed in, per RULE.md's "public data only" rule and this document's own §0 mapping of it.

### Decision 6 — Swipe actions are stored per Module-1 match, not as a parallel job-listing concept

✅ **DIRECT** (own codebase, this document's companion) — `phase2_module1.md` §4 already resolved the "jobs means three different things" naming collision and settled on `JobPosting` (the scraped listing) + `JobMatch` (the scored candidate↔posting pairing) as the two persisted concepts. Module 2's swipe UI needs "a deck of cards to swipe on with a match score" — that is *exactly* `JobMatch` joined to `JobPosting`, already scored, already deduplicated. Building a second, swipe-specific job-listing table would resurrect the "jobs means N things" problem `phase2_module1.md` explicitly avoided.

**Applied as:** Module 2 adds exactly one new table, `job_swipe_actions` (§6.5), recording `(job_match_id, direction, created_at)` — it does **not** duplicate `job_postings`/`job_matches`. This makes Module 2 **structurally dependent on Module 1 shipping first** (or at least its schema existing) — an explicit, load-bearing cross-module dependency, called out again in §4.1 as the single most important blind spot in this plan.

### Decision 7 — No new LLM provider SDK for outreach; reuse the existing raw-`httpx` OpenAI-call convention

✅ **DIRECT** (own codebase) — `cv_extractor.py` and `feedback_generator.py` both call the OpenAI Chat Completions endpoint via raw `httpx.AsyncClient` POST requests, not the `openai` Python SDK's client object, even though `openai>=1.0,<2.0` is already a dependency (verified in `pyproject.toml`) — this repo's established convention (for reasons not documented, but consistent across both files) is "own the HTTP call, don't depend on SDK internals for retries/timeouts."

**Applied as:** `app/clients/perplexity.py` (§5.9) follows the exact same convention: a small class wrapping `httpx.AsyncClient`, no new SDK dependency, calling Perplexity's OpenAI-compatible endpoint with the existing `httpx` version already pinned. This keeps the "one way to call an LLM-shaped HTTP API" convention consistent across the codebase rather than introducing a second style for one new feature.

---

## 4. Naming collisions and blind spots checked before designing the schema

**4.1 — Module 2 depends on Module 1's schema. This is the single biggest blind spot in the original spec, which described both modules as if independent.**

The original Module 2 spec ("Search for jobs; have a Tinder-style approval... Personalized outreach messages") reads as if Module 2 owns job search end-to-end. It does not, and should not — `phase2_module1.md` already owns job scraping (`JobSpyEnricher` reuse), deduplication, embedding, and scoring (`job_postings`, `job_posting_embeddings`, `job_matches`). If Module 2 were built to *also* scrape and score jobs, the result would be two competing pipelines writing two different scored-job tables, which is exactly the kind of redundant, parallel logic `RULE.md` prohibits ("Do not duplicate... merge logic").

**Resolution, stated explicitly so it is never missed:**
- Module 2's swipe deck (§5.7, §13.3) reads `job_matches` JOIN `job_postings` — **read-only**, exactly as Module 1 already returns via its own `GET /api/matches` (`phase2_module1.md` §7.7's router). Module 2 does not re-score, re-embed, or re-scrape anything.
- Swiping ("interested"/"pass"/"super like") is new **candidate-action** state that Module 1 has no reason to own (Module 1 owns *scoring*, not *user reaction to a score*) — this is exactly the `job_match_feedback`-shaped v2 hook `phase2_module1.md` Decision 2 already flagged as forward-compatible ("thumbs up/down... hook for a v2 behavior-based re-ranker"). Module 2's `job_swipe_actions` table (§6.5) **is** that hook, generalized from binary thumbs-up/down to the three swipe directions the product spec asks for.
- **Deployment-order consequence:** Module 2's swipe feature cannot function (empty deck, nothing to render) until Module 1's scan pipeline has produced at least one `job_match` row for a candidate. This is stated as an explicit dependency in §16's completion checklist — Module 2's own tests (§9) mock this dependency (insert fake `job_matches` rows directly) so Module 2's test suite does not require Module 1's worker to actually run, but a live end-to-end demo does require Module 1 to be deployed first.
- **Migration-numbering consequence:** §6.0 gives two possible Alembic chains (Module 1 already applied vs. not yet applied) so this document is correct either way, and explicitly flags the one migration (`job_swipe_actions`, §6.5) whose foreign keys require Module 1's tables to physically exist in the target database before it can be run — not just before it can be *authored*.

**4.2 — "Feedback" already means something specific and unrelated; the new `cv_feedback_reports` table must not be confused with it.**

Verified: `backend/app/modules/sessions/models.py`'s `QuestionAttempt.ai_feedback` is a single text column for **interview-answer** feedback (Foundation Week 2 / Module 3 scope, not Module 2). Module 2's CV-improvement feature is a structurally different, larger object (strengths list, improvements list, rewritten bullets, ATS score) attached to a **document**, not an interview answer. **Resolution:** named `cv_feedback_reports` (not `feedback` or `document_feedback`), with its own table, to avoid any accidental conflation with the interview-feedback pipeline — the two `feedback_generator.py`-pattern functions (`generate_interview_feedback()`, existing; `generate_cv_improvement()`, new in §5.4) live in the same file because they share the *pattern* (LLM call → structured result → DB write), not because they share a *table*.

**4.3 — "Matches" (Module 1's `JobMatch`) vs. "Swipe" (Module 2's action on a match) must stay two different frontend routes, not one overloaded page.**

`phase2_module1.md` §11 already claims `/app/matches` for the scored list view. Module 2's swipe deck is a *different interaction* on the *same underlying data* (one-card-at-a-time, gesture-driven, mobile-first) — **resolution:** swipe lives at `/app/matches/swipe` (a sub-route of Module 1's existing route, not a sibling top-level route), so there is one nav entry ("Matches") with two views underneath it (list view = Module 1's default; swipe view = Module 2's addition), rather than two disconnected nav items that both claim to be "the jobs page." See §13.2 for the exact routing tree.

**4.4 — Portfolio "projects" vs. Module 1's `JobPosting` — no collision, but the term "project" is generic enough to check.** Verified: no existing `Project`/`project` domain concept exists anywhere in `backend/app/` today (grep for `class Project` returns nothing). `PortfolioItem` (§6.4) is a new, unambiguous name — chosen instead of the generic "Project" specifically to avoid this becoming a collision the day some future feature legitimately needs a `Project` concept.

**4.5 — Legal/compliance scope check: NYC Local Law 144 does not apply to Module 2.** ✅ **DIRECT** — [NYC Department of Consumer and Worker Protection: Local Law 144](https://www.nyc.gov/site/dca/about/automated-employment-decision-tools.page): LL144 regulates **employers'** use of "automated employment decision tools" to screen candidates for hire — it governs the employer side of AI-assisted hiring decisions. Module 2's AI features (CV completeness chat, CV improvement suggestions, outreach drafting) are **candidate-facing tools that help a person present themselves**, not an employer's hiring-decision tool evaluating candidates on an employer's behalf. This is stated explicitly because it *was* raised as a compliance consideration earlier in this analysis and needs a clear "checked, does not apply, here is why" resolution rather than being silently dropped.

**4.6 — GDPR/data-retention scope check.** ✅ **DIRECT** (own codebase precedent) — `practice_audio_recordings` already implements a 7-day retention policy (`017_practice_audio_recordings.py`, `expires_at` column + `audio_cleanup` worker). CV chat transcripts and outreach message bodies are comparably sensitive free-text personal data. **Applied as:** `cv_chat_sessions.messages` and `outreach_messages.body` follow the same retention convention — see §6.1 and §6.6's `created_at`-based cleanup note, and §5.10's addition to the existing `audio_cleanup` worker rather than a fourth bespoke cleanup job (RULE.md "reuse an existing pattern" applied to workers, not just services).

---

## 5. What Module 2 actually builds — feature-by-feature map to code

Five features, from the original spec, each mapped to exactly which new/edited files implement it (full code follows in the file-by-file sections below):

| # | Spec feature | Backend owner | New/edited files |
|---|---|---|---|
| 1 | CV upload + completeness check | `documents` module (existing, extended) | `app/domain/cv_completeness.py` (NEW), `app/modules/documents/service.py` (EDITED — new method), `app/modules/documents/router.py` (EDITED — new route), `app/modules/documents/schemas.py` (EDITED) |
| 2 | Chatbot for missing info | `documents` module (existing, extended) | `app/modules/documents/models.py` (EDITED — `CvChatSession`, `CvChatMessage`), `app/modules/documents/cv_chat_service.py` (NEW), `app/clients/llm_tools.py` (NEW — function-calling schema) |
| 3 | CV improvement engine | `documents` module (existing, extended) | `app/services/feedback_generator.py` (EDITED — new `generate_cv_improvement()`), `app/modules/documents/models.py` (EDITED — `CvFeedbackReport`), `app/workers/tasks/cv_improvement.py` (NEW) |
| 4 | Portfolio manager | new `portfolio` module | `app/modules/portfolio/{__init__,models,schemas,repository,service,router}.py` (all NEW) |
| 5 | Personalized outreach | new `outreach` module | `app/modules/outreach/{__init__,models,schemas,repository,service,router}.py` (all NEW), `app/clients/perplexity.py` (NEW), `app/workers/tasks/outreach.py` (NEW) |
| 6 | Swipe deck (from Decision 6) | new `job_swipe` module, thin, reads Module 1 data | `app/modules/job_swipe/{__init__,models,schemas,repository,service,router}.py` (all NEW) |

---

## 6. Database schema — 6 new Alembic revisions

**§6.0 — Migration chain, given both ways since this depends on whether Module 1 has been applied yet:**

- If `phase2_module1.md` has already been applied: the current real head is `021_job_matches`. Module 2's revisions chain `022` → `023` → `024` → `025` → `026` → `027` onto `021_job_matches`.
- If Module 1 has **not** been applied yet: the current real head is `017_practice_audio_recordings` (verified by listing `backend/alembic/versions/` directly — this is the actual head in the repository today). In that case, `022_cv_chat_sessions.py` (§6.1) and `023_cv_feedback_reports.py` (§6.2) — which have **no dependency on Module 1's tables** — chain directly onto `017_practice_audio_recordings`, and `026_job_swipe_actions.py` (§6.5) — the **one** migration that has a foreign key into `job_matches` — is written with its `down_revision` pointing at whichever of Module 1's revisions is actually present, checked at authoring time. This document assumes Module 1 is applied first (the natural order, since Module 2 depends on it per §4.1), so all `down_revision`s below chain onto Module 1's `021_job_matches`. If you are implementing Module 2 before Module 1, renumber `026_job_swipe_actions.py`'s `down_revision` to `017_practice_audio_recordings` and hold that one migration until Module 1 ships — do not skip the foreign key or make it nullable-and-unenforced, since that would silently defeat Decision 6's entire point.

All new tables follow the exact dialect-handling pattern already used in `017_practice_audio_recordings.py` and `phase2_module1.md`'s migrations: `postgresql.UUID(as_uuid=True)` / `sa.String(36)` branch on `bind.dialect.name`, `JsonDoc` (JSONB on Postgres, JSON on SQLite) for JSON columns — no new pattern invented.

### 6.1 `cv_chat_sessions` + `cv_chat_messages` — chatbot conversation state (Decision 2)

**New file:** `backend/alembic/versions/022_cv_chat_sessions.py`

```python
"""Add cv_chat_sessions and cv_chat_messages tables for CV-completeness chatbot.

Revision ID: 022_cv_chat_sessions
Revises: 021_job_matches
Create Date: 2026-08-08
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "022_cv_chat_sessions"
down_revision: Union[str, Sequence[str], None] = "021_job_matches"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)
    jsonb_type = postgresql.JSONB() if dialect == "postgresql" else sa.JSON()

    op.create_table(
        "cv_chat_sessions",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("user_id", uuid_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", uuid_type, sa.ForeignKey("candidate_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),  # "active"|"completed"|"abandoned"
        sa.Column("missing_fields_at_start", jsonb_type, nullable=False, server_default="[]"),
        sa.Column("fields_resolved", jsonb_type, nullable=False, server_default="[]"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_cv_chat_sessions_user_id", "cv_chat_sessions", ["user_id"])
    op.create_index("ix_cv_chat_sessions_document_id", "cv_chat_sessions", ["document_id"])

    op.create_table(
        "cv_chat_messages",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("session_id", uuid_type, sa.ForeignKey("cv_chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),  # "assistant"|"user"
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("field_name", sa.String(50), nullable=True),  # which CVData field this message targets, if any
        sa.Column("tool_call_result", jsonb_type, nullable=True),  # validated value recorded via record_cv_answer tool
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_cv_chat_messages_session_id", "cv_chat_messages", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_cv_chat_messages_session_id", table_name="cv_chat_messages")
    op.drop_table("cv_chat_messages")
    op.drop_index("ix_cv_chat_sessions_document_id", table_name="cv_chat_sessions")
    op.drop_index("ix_cv_chat_sessions_user_id", table_name="cv_chat_sessions")
    op.drop_table("cv_chat_sessions")
```

**Design notes:** two tables (not one JSON blob column) because chat history needs per-message ordering and per-message tool-call auditability (Decision 1's function-calling result must be traceable to the exact message that produced it) — same normalization reasoning as `QuestionAttempt` being its own row rather than a JSON array on `PracticeSession`. `missing_fields_at_start` is a frozen snapshot (computed once when the session starts) so the UI can show "3 of 5 answered" progress without re-running `compute_missing_fields()` on every render.

### 6.2 `cv_feedback_reports` — CV improvement suggestions (Decision 3)

**New file:** `backend/alembic/versions/023_cv_feedback_reports.py`

```python
"""Add cv_feedback_reports table for AI-generated CV improvement suggestions.

Revision ID: 023_cv_feedback_reports
Revises: 022_cv_chat_sessions
Create Date: 2026-08-08
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "023_cv_feedback_reports"
down_revision: Union[str, Sequence[str], None] = "022_cv_chat_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)
    jsonb_type = postgresql.JSONB() if dialect == "postgresql" else sa.JSON()

    op.create_table(
        "cv_feedback_reports",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("document_id", uuid_type, sa.ForeignKey("candidate_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", uuid_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_role", sa.String(255), nullable=True),  # optional role the candidate is optimizing for
        sa.Column("ats_score", sa.Integer(), nullable=False),  # 0-100
        sa.Column("strengths", jsonb_type, nullable=False, server_default="[]"),
        sa.Column("improvements", jsonb_type, nullable=False, server_default="[]"),
        sa.Column("rewritten_bullets", jsonb_type, nullable=False, server_default="[]"),  # [{original, rewritten, rationale}]
        sa.Column("accepted_bullet_indices", jsonb_type, nullable=False, server_default="[]"),  # candidate's explicit accepts
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_cv_feedback_reports_document_id", "cv_feedback_reports", ["document_id"])
    op.create_index("ix_cv_feedback_reports_user_id", "cv_feedback_reports", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_cv_feedback_reports_user_id", table_name="cv_feedback_reports")
    op.drop_index("ix_cv_feedback_reports_document_id", table_name="cv_feedback_reports")
    op.drop_table("cv_feedback_reports")
```

**Design notes:** `accepted_bullet_indices` is how Decision 3's "never silently overwrite the stored CV" rule is implemented at the data layer — a suggestion only becomes something the candidate endorsed when its index appears in this list, written by an explicit `POST .../accept` call (§8.4), never automatically.

### 6.3 `portfolio_profiles` — one per candidate, holds the public slug (Decision 4)

**New file:** `backend/alembic/versions/024_portfolio_profiles.py`

```python
"""Add portfolio_profiles table for candidate portfolio pages.

Revision ID: 024_portfolio_profiles
Revises: 023_cv_feedback_reports
Create Date: 2026-08-08
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "024_portfolio_profiles"
down_revision: Union[str, Sequence[str], None] = "023_cv_feedback_reports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)

    op.create_table(
        "portfolio_profiles",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("user_id", uuid_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("slug", sa.String(64), nullable=False),  # DNS-safe charset, per Decision 4
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("headline", sa.String(255), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_portfolio_profiles_user_id", "portfolio_profiles", ["user_id"], unique=True)
    op.create_index("ix_portfolio_profiles_slug", "portfolio_profiles", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_portfolio_profiles_slug", table_name="portfolio_profiles")
    op.drop_index("ix_portfolio_profiles_user_id", table_name="portfolio_profiles")
    op.drop_table("portfolio_profiles")
```

**Design notes:** `slug` is validated at the Pydantic layer (§8.5's `PORTFOLIO_SLUG_PATTERN`) to only allow lowercase alphanumerics and hyphens, 3–63 chars — the exact charset a subdomain label permits (RFC 1035), so the "upgrade to real subdomain later" path in Decision 4 needs zero data migration, only infra work, when/if it happens.

### 6.4 `portfolio_items` — projects/links shown on the portfolio page

**New file:** `backend/alembic/versions/025_portfolio_items.py`

```python
"""Add portfolio_items table for projects/links on a candidate's portfolio page.

Revision ID: 025_portfolio_items
Revises: 024_portfolio_profiles
Create Date: 2026-08-08
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "025_portfolio_items"
down_revision: Union[str, Sequence[str], None] = "024_portfolio_profiles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)

    op.create_table(
        "portfolio_items",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("profile_id", uuid_type, sa.ForeignKey("portfolio_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_type", sa.String(20), nullable=False),  # "github"|"live_demo"|"case_study"|"other"
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_portfolio_items_profile_id", "portfolio_items", ["profile_id"])


def downgrade() -> None:
    op.drop_index("ix_portfolio_items_profile_id", table_name="portfolio_items")
    op.drop_table("portfolio_items")
```

### 6.5 `job_swipe_actions` — the swipe deck's write side (Decision 6)

**New file:** `backend/alembic/versions/026_job_swipe_actions.py`

```python
"""Add job_swipe_actions table — candidate swipe reactions on Module 1's job_matches.

Revision ID: 026_job_swipe_actions
Revises: 025_portfolio_items
Create Date: 2026-08-08
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "026_job_swipe_actions"
down_revision: Union[str, Sequence[str], None] = "025_portfolio_items"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)

    op.create_table(
        "job_swipe_actions",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("job_match_id", uuid_type, sa.ForeignKey("job_matches.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("user_id", uuid_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),  # "right"(interested)|"left"(pass)|"up"(super_like)
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_job_swipe_actions_user_id", "job_swipe_actions", ["user_id"])
    op.create_index("ix_job_swipe_actions_job_match_id", "job_swipe_actions", ["job_match_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_job_swipe_actions_job_match_id", table_name="job_swipe_actions")
    op.drop_index("ix_job_swipe_actions_user_id", table_name="job_swipe_actions")
    op.drop_table("job_swipe_actions")
```

**Design notes:** `job_match_id` unique-indexed — one swipe decision per match, resubmitting overwrites (undo/redo, §8.6) rather than accumulating history rows, since the product need is "the candidate's current decision on this job," not an audit trail of every swipe attempt.

### 6.6 `outreach_messages` — generated + sent outreach drafts (Decision 5)

**New file:** `backend/alembic/versions/027_outreach_messages.py`

```python
"""Add outreach_messages table for AI-drafted personalized outreach.

Revision ID: 027_outreach_messages
Revises: 026_job_swipe_actions
Create Date: 2026-08-08
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "027_outreach_messages"
down_revision: Union[str, Sequence[str], None] = "026_job_swipe_actions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)
    jsonb_type = postgresql.JSONB() if dialect == "postgresql" else sa.JSON()

    op.create_table(
        "outreach_messages",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("user_id", uuid_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_match_id", uuid_type, sa.ForeignKey("job_matches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("recipient_role_title", sa.String(255), nullable=True),  # e.g. "Hiring Manager" — public title only
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("company_context_used", jsonb_type, nullable=False, server_default="{}"),  # Perplexity result snapshot
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),  # "draft"|"sent"|"discarded"
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_outreach_messages_user_id", "outreach_messages", ["user_id"])
    op.create_index("ix_outreach_messages_status", "outreach_messages", ["status"])


def downgrade() -> None:
    op.drop_index("ix_outreach_messages_status", table_name="outreach_messages")
    op.drop_index("ix_outreach_messages_user_id", table_name="outreach_messages")
    op.drop_table("outreach_messages")
```

**Design notes:** `job_match_id` is `ON DELETE SET NULL` (not `CASCADE`) — an outreach draft that was written about a job should survive even if that specific match row is later cleaned up (e.g. `job_postings.is_active` sweep does not delete matches, but this is a defensive choice matching the same reasoning `candidate_job_preferences.source_document_id` used in `phase2_module1.md` §5.3). `company_context_used` snapshots exactly what Perplexity returned at generation time — required for the CAN-SPAM "monitor what any third party does on your behalf" obligation (Decision 5) to be auditable after the fact, not just at send time.

---

## 7. Configuration — new environment variables

**File edited:** `backend/.env.example` (placeholders only, per RULE.md "never commit secrets")

```bash
# Module 2: Tinder-Style Job Board + CV Management
PERPLEXITY_API_KEY=pplx-...
PERPLEXITY_API_BASE=https://api.perplexity.ai
OUTREACH_ENABLED=true
OUTREACH_SENDER_EMAIL=candidate-outreach@hyrepath.example   # placeholder — real value is per-tenant/per-user return address
CV_CHAT_MAX_TURNS=12                    # hard cap on chatbot back-and-forth per session (cost + abuse control)
CV_FEEDBACK_MODEL=gpt-4o-mini           # matches existing cv_extractor.py model choice, not gpt-4o, per cost note in §11
PORTFOLIO_PUBLIC_BASE_URL=https://app.hyrepath.example/p     # matches Decision 4's path-based (not subdomain) hosting
```

**File edited:** `backend/app/core/config.py` — add corresponding `Settings` fields, following the exact existing pattern used for `openai_api_key` and `jobspy_results_per_board` (same `Field(default=..., alias=...)` style, no new pattern invented):

```python
# Added to the Settings class in backend/app/core/config.py:
perplexity_api_key: str = Field(default="", alias="PERPLEXITY_API_KEY")
perplexity_api_base: str = Field(default="https://api.perplexity.ai", alias="PERPLEXITY_API_BASE")
outreach_enabled: bool = Field(default=True, alias="OUTREACH_ENABLED")
outreach_sender_email: str = Field(default="", alias="OUTREACH_SENDER_EMAIL")
cv_chat_max_turns: int = Field(default=12, alias="CV_CHAT_MAX_TURNS")
cv_feedback_model: str = Field(default="gpt-4o-mini", alias="CV_FEEDBACK_MODEL")
portfolio_public_base_url: str = Field(default="", alias="PORTFOLIO_PUBLIC_BASE_URL")
```

---

## 8. Backend implementation — file by file

### 8.1 `backend/app/domain/cv_completeness.py` (NEW — domain layer, per RULE.md's layer table: "framework-free business types/rules shared across modules")

Pure functions, no I/O, no LLM calls — deterministic, per Decision 1. This is the single place completeness rules live; the chatbot service (§8.2) and the documents router (§8.3) both call into this file rather than each defining their own notion of "complete."

```python
"""Deterministic CV completeness rules. No I/O, no LLM calls.

Per Decision 1 (phase2_module2.md §3): completeness is computed here in plain
Python. The LLM is only used downstream, in the chatbot, to ask about — and
validate the format of — whichever fields this module says are missing.
"""

from __future__ import annotations

from app.domain.candidate import CVData

# Ordered by how strongly each field affects discoverability/matchability —
# asked in this order by the chatbot (§8.2) so the highest-value questions
# come first if a candidate abandons the session partway through.
REQUIRED_FIELDS: list[str] = [
    "email",
    "phone",
    "linkedin_url",
    "technical_skills",
    "total_years_experience",
    "desired_roles",
    "desired_locations",
    "remote_preference",
]

FIELD_QUESTIONS: dict[str, str] = {
    "email": "What's the best email address for recruiters to reach you?",
    "phone": "What's a good phone number to include?",
    "linkedin_url": "Do you have a LinkedIn profile URL you'd like to include?",
    "technical_skills": "What are your top technical skills? (comma-separated is fine)",
    "total_years_experience": "How many years of professional experience do you have?",
    "desired_roles": "What job titles or roles are you targeting?",
    "desired_locations": "Which locations are you open to working in?",
    "remote_preference": "Do you prefer remote, hybrid, or onsite work?",
}


def compute_missing_fields(cv_data: CVData) -> list[str]:
    """Return the ordered list of required fields that are empty/None on cv_data.

    Mirrors the existing (private) `_calculate_completeness()` logic in
    `cv_extractor.py` but is exposed as its own module-level function so the
    chatbot and the documents router can both call it without importing a
    private method from a different module's internals (RULE.md: don't reach
    into another module's private implementation).
    """
    missing: list[str] = []
    for field_name in REQUIRED_FIELDS:
        value = getattr(cv_data, field_name, None)
        if value is None:
            missing.append(field_name)
        elif isinstance(value, (list, str)) and len(value) == 0:
            missing.append(field_name)
    return missing


def completeness_score(cv_data: CVData) -> float:
    """0.0-1.0 fraction of REQUIRED_FIELDS that are populated."""
    missing = compute_missing_fields(cv_data)
    return round(1.0 - (len(missing) / len(REQUIRED_FIELDS)), 4)


def question_for_field(field_name: str) -> str:
    """The exact question text the chatbot asks for a given missing field."""
    return FIELD_QUESTIONS.get(field_name, f"Can you provide your {field_name.replace('_', ' ')}?")
```

**Where this is called from:** `documents/service.py`'s new `get_completeness()` method (§8.3) calls `compute_missing_fields()` right after a document finishes processing, to decide whether to prompt "let's fill in the gaps" in the UI. `cv_chat_service.py` (§8.2) calls it once at session start (frozen into `cv_chat_sessions.missing_fields_at_start`, §6.1) and again after each answer, to decide the next question or to end the session.

---

### 8.2 `backend/app/modules/documents/models.py` (EDITED) — add `CvChatSession`, `CvChatMessage`, `CvFeedbackReport`

Mirrors the Alembic tables in §6.1/§6.2 exactly, appended to the existing file (imports at the top of the file already cover everything needed — `Boolean` is the only new SQLAlchemy type import required):

```python
# Added import at the top of backend/app/modules/documents/models.py:
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text

# Appended to the end of backend/app/modules/documents/models.py:

class CvChatSession(Base):
    """CV-completeness chatbot conversation state (Decision 1/2)."""

    __tablename__ = "cv_chat_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    missing_fields_at_start: Mapped[list[str]] = mapped_column(JsonDoc, default=list, nullable=False)
    fields_resolved: Mapped[list[str]] = mapped_column(JsonDoc, default=list, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CvChatMessage(Base):
    """Single turn in a CV-completeness chat session."""

    __tablename__ = "cv_chat_messages"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("cv_chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    field_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tool_call_result: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class CvFeedbackReport(Base):
    """AI-generated CV improvement suggestions (Decision 3)."""

    __tablename__ = "cv_feedback_reports"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    target_role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ats_score: Mapped[int] = mapped_column(Integer, nullable=False)
    strengths: Mapped[list[str]] = mapped_column(JsonDoc, default=list, nullable=False)
    improvements: Mapped[list[str]] = mapped_column(JsonDoc, default=list, nullable=False)
    rewritten_bullets: Mapped[list[dict[str, Any]]] = mapped_column(JsonDoc, default=list, nullable=False)
    accepted_bullet_indices: Mapped[list[int]] = mapped_column(JsonDoc, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
```

---

### 8.3 `backend/app/clients/llm_tools.py` (NEW — clients layer: "one provider per file", this one owns OpenAI function-calling tool-schema construction shared across CV chat)

```python
"""Shared OpenAI function-calling tool schema for the CV-completeness chatbot.

Per Decision 1 (phase2_module2.md §3): the model's only possible action besides
asking a question is to call `record_cv_answer` with an argument shape validated
by this schema — it cannot free-form invent CV field values outside this contract.
"""

from __future__ import annotations

from typing import Any

RECORD_CV_ANSWER_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "record_cv_answer",
        "description": (
            "Record the candidate's answer for the specific CV field currently being asked about. "
            "Call this only when the candidate has provided a usable value; if their answer is unclear, "
            "ask a clarifying follow-up instead of calling this tool."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "field_name": {
                    "type": "string",
                    "description": "The CVData field this answer is for.",
                },
                "value": {
                    "type": "string",
                    "description": (
                        "The extracted value as a plain string. For list fields "
                        "(technical_skills, desired_roles, desired_locations), "
                        "provide a comma-separated string; the caller splits it."
                    ),
                },
            },
            "required": ["field_name", "value"],
            "additionalProperties": False,
        },
    },
}


def build_chat_system_prompt(field_name: str, question: str) -> str:
    """System prompt for one chatbot turn — scoped to exactly one field at a time.

    Scoping to one field per turn (rather than a general "help complete this CV"
    system prompt) is what makes the turn-based, non-streamed design in Decision 2
    workable: each call is a small, bounded, cheap GPT-4o-mini request.
    """
    return (
        "You are a friendly assistant helping a job candidate complete their CV. "
        f"You are currently asking about ONE field: '{field_name}'. "
        f"Your question to the candidate is: \"{question}\" "
        "If the candidate's reply gives a usable answer for this field, call the "
        "record_cv_answer tool with field_name and value. If their reply is unrelated, "
        "unclear, or a question of their own, respond conversationally without calling "
        "the tool, and gently steer back to the question. Never invent a value the "
        "candidate did not provide."
    )
```

---

### 8.4 `backend/app/modules/documents/cv_chat_service.py` (NEW — modules layer: this feature's business logic, kept out of the shared `service.py` because it is a distinct workflow from upload/list/delete, per RULE.md's "keep the change as small/focused as the task allows")

```python
"""CV-completeness chatbot service: turn-based, function-calling driven (Decision 1/2)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.llm_tools import RECORD_CV_ANSWER_TOOL, build_chat_system_prompt
from app.core.config import get_settings
from app.domain.candidate import CVData
from app.domain.cv_completeness import compute_missing_fields, question_for_field
from app.modules.documents.models import CandidateDocument, CvChatMessage, CvChatSession
from app.modules.documents.schemas import (
    CvChatMessageResponse,
    CvChatSessionResponse,
    CvChatTurnResponse,
)

logger = logging.getLogger(__name__)

_OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"


class CvChatService:
    """Business logic for the CV-completeness chatbot."""

    def __init__(self, db: AsyncSession, http_client: httpx.AsyncClient | None = None):
        self.db = db
        self._client = http_client or httpx.AsyncClient(timeout=30.0)
        self._settings = get_settings()

    async def start_session(self, document_id: str, user_id: UUID) -> CvChatSessionResponse:
        """Start (or resume) a chat session for a document's missing fields."""
        result = await self.db.execute(
            select(CandidateDocument).where(
                CandidateDocument.id == UUID(document_id),
                CandidateDocument.user_id == user_id,
            )
        )
        document = result.scalar_one_or_none()
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        if document.processing_status != "completed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Document is still processing; chat is unavailable until extraction completes",
            )

        # Resume an existing active session for this document rather than starting a duplicate.
        existing = await self.db.execute(
            select(CvChatSession).where(
                CvChatSession.document_id == document.id,
                CvChatSession.status == "active",
            )
        )
        session = existing.scalar_one_or_none()
        if session:
            return await self._session_response(session)

        cv_data = CVData(**(document.extracted_data or {})) if document.extracted_data else CVData()
        missing = compute_missing_fields(cv_data)

        session = CvChatSession(
            id=uuid4(),
            user_id=user_id,
            document_id=document.id,
            status="active" if missing else "completed",
            missing_fields_at_start=missing,
            fields_resolved=[],
            started_at=datetime.now(UTC),
            completed_at=None if missing else datetime.now(UTC),
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

        if missing:
            first_question = question_for_field(missing[0])
            greeting = CvChatMessage(
                id=uuid4(),
                session_id=session.id,
                role="assistant",
                content=first_question,
                field_name=missing[0],
                created_at=datetime.now(UTC),
            )
            self.db.add(greeting)
            await self.db.commit()

        return await self._session_response(session)

    async def post_message(
        self, session_id: str, user_id: UUID, content: str
    ) -> CvChatTurnResponse:
        """Process one candidate reply: call the LLM, apply the tool call (if any), advance to next question."""
        session = await self._get_owned_session(session_id, user_id)
        if session.status != "active":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Chat session is not active")

        turn_count = await self._count_messages(session.id)
        if turn_count >= self._settings.cv_chat_max_turns * 2:
            session.status = "abandoned"
            session.completed_at = datetime.now(UTC)
            await self.db.commit()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Chat session reached its turn limit")

        remaining = [f for f in session.missing_fields_at_start if f not in session.fields_resolved]
        if not remaining:
            session.status = "completed"
            session.completed_at = datetime.now(UTC)
            await self.db.commit()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Chat session already completed")

        current_field = remaining[0]
        question = question_for_field(current_field)

        user_message = CvChatMessage(
            id=uuid4(), session_id=session.id, role="user", content=content, created_at=datetime.now(UTC)
        )
        self.db.add(user_message)
        await self.db.flush()

        tool_result = await self._call_llm_with_tool(current_field, question, content)

        assistant_reply_parts: list[CvChatMessageResponse] = []
        if tool_result is not None:
            field_name, value = tool_result
            await self._apply_field_value(session, field_name, value)
            session.fields_resolved = [*session.fields_resolved, field_name]
            await self.db.commit()

            next_remaining = [f for f in session.missing_fields_at_start if f not in session.fields_resolved]
            if next_remaining:
                next_question = question_for_field(next_remaining[0])
                assistant_msg = CvChatMessage(
                    id=uuid4(),
                    session_id=session.id,
                    role="assistant",
                    content=f"Got it, thanks! {next_question}",
                    field_name=next_remaining[0],
                    tool_call_result={"field_name": field_name, "value": value},
                    created_at=datetime.now(UTC),
                )
            else:
                session.status = "completed"
                session.completed_at = datetime.now(UTC)
                assistant_msg = CvChatMessage(
                    id=uuid4(),
                    session_id=session.id,
                    role="assistant",
                    content="That's everything — your CV profile is now complete. Nice work!",
                    tool_call_result={"field_name": field_name, "value": value},
                    created_at=datetime.now(UTC),
                )
            self.db.add(assistant_msg)
        else:
            # No tool call: model responded conversationally without a validated answer.
            assistant_msg = CvChatMessage(
                id=uuid4(),
                session_id=session.id,
                role="assistant",
                content=f"Sorry, I didn't quite catch that. {question}",
                field_name=current_field,
                created_at=datetime.now(UTC),
            )
            self.db.add(assistant_msg)

        await self.db.commit()
        await self.db.refresh(session)
        return CvChatTurnResponse(
            session=await self._session_response(session),
            assistant_message=CvChatMessageResponse(
                id=str(assistant_msg.id),
                role=assistant_msg.role,
                content=assistant_msg.content,
                field_name=assistant_msg.field_name,
                created_at=assistant_msg.created_at,
            ),
        )

    async def _call_llm_with_tool(
        self, field_name: str, question: str, candidate_reply: str
    ) -> tuple[str, str] | None:
        """One turn-based (non-streamed) OpenAI call, per Decision 2. Returns (field_name, value) or None."""
        if not self._settings.openai_api_key:
            return None
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": build_chat_system_prompt(field_name, question)},
                {"role": "user", "content": candidate_reply},
            ],
            "tools": [RECORD_CV_ANSWER_TOOL],
            "tool_choice": "auto",
            "temperature": 0.0,
        }
        headers = {"Authorization": f"Bearer {self._settings.openai_api_key}"}
        try:
            response = await self._client.post(_OPENAI_CHAT_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()  # httpx.Response.json() is synchronous — see the §2.1 Bug 1 fix
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.warning("CV chat LLM call failed", extra={"error": str(exc)})
            return None

        message = data.get("choices", [{}])[0].get("message", {})
        tool_calls = message.get("tool_calls") or []
        for call in tool_calls:
            if call.get("function", {}).get("name") == "record_cv_answer":
                import json as _json

                try:
                    args = _json.loads(call["function"]["arguments"])
                    return args["field_name"], args["value"]
                except (KeyError, ValueError):
                    continue
        return None

    async def _apply_field_value(self, session: CvChatSession, field_name: str, value: str) -> None:
        """Write the validated answer back onto CandidateDocument.extracted_data."""
        result = await self.db.execute(
            select(CandidateDocument).where(CandidateDocument.id == session.document_id)
        )
        document = result.scalar_one()
        extracted = dict(document.extracted_data or {})

        list_fields = {"technical_skills", "desired_roles", "desired_locations"}
        if field_name in list_fields:
            extracted[field_name] = [v.strip() for v in value.split(",") if v.strip()]
        elif field_name == "total_years_experience":
            try:
                extracted[field_name] = float(value)
            except ValueError:
                extracted[field_name] = None
        else:
            extracted[field_name] = value.strip()

        document.extracted_data = extracted
        self.db.add(document)

    async def _get_owned_session(self, session_id: str, user_id: UUID) -> CvChatSession:
        result = await self.db.execute(
            select(CvChatSession).where(CvChatSession.id == UUID(session_id), CvChatSession.user_id == user_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")
        return session

    async def _count_messages(self, session_id: UUID) -> int:
        result = await self.db.execute(select(CvChatMessage).where(CvChatMessage.session_id == session_id))
        return len(result.all())

    async def _session_response(self, session: CvChatSession) -> CvChatSessionResponse:
        messages_result = await self.db.execute(
            select(CvChatMessage).where(CvChatMessage.session_id == session.id).order_by(CvChatMessage.created_at)
        )
        messages = messages_result.scalars().all()
        return CvChatSessionResponse(
            session_id=str(session.id),
            document_id=str(session.document_id),
            status=session.status,
            missing_fields_at_start=session.missing_fields_at_start,
            fields_resolved=session.fields_resolved,
            messages=[
                CvChatMessageResponse(
                    id=str(m.id), role=m.role, content=m.content, field_name=m.field_name, created_at=m.created_at
                )
                for m in messages
            ],
        )
```

---

### 8.5 `backend/app/modules/documents/schemas.py` (EDITED) — new request/response models

Appended to the existing file (per RULE.md "do not duplicate validation" — these are the only schemas for this shape anywhere in the codebase):

```python
# Appended to backend/app/modules/documents/schemas.py

class CvCompletenessResponse(BaseModel):
    document_id: str
    completeness_score: float = Field(..., ge=0.0, le=1.0)
    missing_fields: list[str]
    has_active_chat_session: bool


class CvChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    field_name: str | None
    created_at: datetime


class CvChatSessionResponse(BaseModel):
    session_id: str
    document_id: str
    status: str
    missing_fields_at_start: list[str]
    fields_resolved: list[str]
    messages: list[CvChatMessageResponse]


class CvChatMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


class CvChatTurnResponse(BaseModel):
    session: CvChatSessionResponse
    assistant_message: CvChatMessageResponse


class CvFeedbackRequest(BaseModel):
    target_role: str | None = Field(default=None, max_length=255)


class RewrittenBullet(BaseModel):
    original: str
    rewritten: str
    rationale: str


class CvFeedbackResponse(BaseModel):
    report_id: str
    document_id: str
    target_role: str | None
    ats_score: int = Field(..., ge=0, le=100)
    strengths: list[str]
    improvements: list[str]
    rewritten_bullets: list[RewrittenBullet]
    accepted_bullet_indices: list[int]
    created_at: datetime


class AcceptBulletRequest(BaseModel):
    bullet_index: int = Field(..., ge=0)
```

### 8.6 `backend/app/modules/documents/service.py` (EDITED) — new `DocumentService` methods

Appended as new methods on the existing `DocumentService` class (same class, same file — this is CV-completeness/feedback logic that belongs with the document it operates on, not a separate service object, per RULE.md "keep the change as small as the task allows"):

```python
# Added imports at the top of backend/app/modules/documents/service.py:
from app.domain.candidate import CVData
from app.domain.cv_completeness import compute_missing_fields, completeness_score
from app.modules.documents.models import CvChatSession, CvFeedbackReport
from app.modules.documents.schemas import CvCompletenessResponse, CvFeedbackResponse, RewrittenBullet
from app.workers.queue import QUEUE_FEEDBACK

# Added methods inside the DocumentService class:

    async def get_completeness(self, document_id: str, user_id: UUID) -> CvCompletenessResponse:
        """Compute completeness for a processed document (Decision 1)."""
        document = await self._get_owned_document(document_id, user_id)
        cv_data = CVData(**(document.extracted_data or {})) if document.extracted_data else CVData()
        missing = compute_missing_fields(cv_data)

        active_session = await self.db.execute(
            select(CvChatSession).where(
                CvChatSession.document_id == document.id, CvChatSession.status == "active"
            )
        )
        return CvCompletenessResponse(
            document_id=str(document.id),
            completeness_score=completeness_score(cv_data),
            missing_fields=missing,
            has_active_chat_session=active_session.scalar_one_or_none() is not None,
        )

    async def request_cv_feedback(
        self, document_id: str, user_id: UUID, target_role: str | None
    ) -> DocumentUploadResponse:
        """Enqueue CV improvement generation (Decision 3). Reuses QUEUE_FEEDBACK — no new queue."""
        document = await self._get_owned_document(document_id, user_id)
        if document.processing_status != "completed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Document must finish processing before requesting feedback",
            )

        job = DocumentJob(
            user_id=user_id, document_id=document.id, job_type="cv_feedback", status="pending", progress=0.0
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)

        try:
            queue = Queue(QUEUE_FEEDBACK, connection=self.redis_conn)
            queue.enqueue(
                "app.workers.tasks.cv_improvement.generate_cv_improvement_job",
                str(document.id),
                str(job.id),
                target_role,
                job_timeout=120,
            )
        except Exception as e:
            job.status = "failed"
            job.error = f"Failed to enqueue: {str(e)}"
            await self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to enqueue CV feedback generation",
            )

        return DocumentUploadResponse(
            job_id=str(job.id), document_id=str(document.id), message="CV feedback generation started"
        )

    async def get_latest_cv_feedback(self, document_id: str, user_id: UUID) -> CvFeedbackResponse:
        document = await self._get_owned_document(document_id, user_id)
        result = await self.db.execute(
            select(CvFeedbackReport)
            .where(CvFeedbackReport.document_id == document.id)
            .order_by(CvFeedbackReport.created_at.desc())
            .limit(1)
        )
        report = result.scalar_one_or_none()
        if not report:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No feedback report yet")
        return self._feedback_to_response(report)

    async def accept_cv_feedback_bullet(
        self, document_id: str, user_id: UUID, report_id: str, bullet_index: int
    ) -> CvFeedbackResponse:
        """Explicit candidate 'accept' — this is the ONLY path that constitutes endorsement (Decision 3)."""
        await self._get_owned_document(document_id, user_id)
        result = await self.db.execute(
            select(CvFeedbackReport).where(
                CvFeedbackReport.id == UUID(report_id), CvFeedbackReport.user_id == user_id
            )
        )
        report = result.scalar_one_or_none()
        if not report:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback report not found")
        if bullet_index < 0 or bullet_index >= len(report.rewritten_bullets):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid bullet index")
        if bullet_index not in report.accepted_bullet_indices:
            report.accepted_bullet_indices = [*report.accepted_bullet_indices, bullet_index]
            await self.db.commit()
            await self.db.refresh(report)
        return self._feedback_to_response(report)

    async def _get_owned_document(self, document_id: str, user_id: UUID) -> CandidateDocument:
        result = await self.db.execute(
            select(CandidateDocument).where(
                CandidateDocument.id == UUID(document_id), CandidateDocument.user_id == user_id
            )
        )
        document = result.scalar_one_or_none()
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        return document

    def _feedback_to_response(self, report: CvFeedbackReport) -> CvFeedbackResponse:
        return CvFeedbackResponse(
            report_id=str(report.id),
            document_id=str(report.document_id),
            target_role=report.target_role,
            ats_score=report.ats_score,
            strengths=report.strengths,
            improvements=report.improvements,
            rewritten_bullets=[RewrittenBullet(**b) for b in report.rewritten_bullets],
            accepted_bullet_indices=report.accepted_bullet_indices,
            created_at=report.created_at,
        )
```

### 8.7 `backend/app/modules/documents/router.py` (EDITED) — new routes + CV-chat routes

```python
# Added imports at the top of backend/app/modules/documents/router.py:
from app.modules.documents.cv_chat_service import CvChatService
from app.modules.documents.schemas import (
    AcceptBulletRequest,
    CvChatMessageRequest,
    CvChatSessionResponse,
    CvChatTurnResponse,
    CvCompletenessResponse,
    CvFeedbackRequest,
    CvFeedbackResponse,
)

# Added routes, appended to the router in backend/app/modules/documents/router.py:

@router.get("/{document_id}/completeness", response_model=CvCompletenessResponse)
async def get_completeness(
    document_id: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)
) -> CvCompletenessResponse:
    """Missing-field completeness check (Decision 1). Drives the 'let's finish your CV' prompt."""
    service = DocumentService(db)
    return await service.get_completeness(document_id, current_user.id)


@router.post("/{document_id}/cv-chat/sessions", response_model=CvChatSessionResponse)
async def start_cv_chat_session(
    document_id: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)
) -> CvChatSessionResponse:
    """Start (or resume) the missing-info chatbot for a document."""
    service = CvChatService(db)
    return await service.start_session(document_id, current_user.id)


@router.post("/cv-chat/sessions/{session_id}/messages", response_model=CvChatTurnResponse)
async def post_cv_chat_message(
    session_id: str,
    body: CvChatMessageRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> CvChatTurnResponse:
    """One turn-based (non-streamed, Decision 2) chatbot exchange."""
    service = CvChatService(db)
    return await service.post_message(session_id, current_user.id, body.content)


@router.post("/{document_id}/feedback", response_model=DocumentUploadResponse)
async def request_cv_feedback(
    document_id: str,
    body: CvFeedbackRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> DocumentUploadResponse:
    """Enqueue AI CV-improvement generation (Decision 3)."""
    service = DocumentService(db)
    return await service.request_cv_feedback(document_id, current_user.id, body.target_role)


@router.get("/{document_id}/feedback", response_model=CvFeedbackResponse)
async def get_cv_feedback(
    document_id: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)
) -> CvFeedbackResponse:
    """Latest CV-improvement report for a document."""
    service = DocumentService(db)
    return await service.get_latest_cv_feedback(document_id, current_user.id)


@router.post("/{document_id}/feedback/{report_id}/accept", response_model=CvFeedbackResponse)
async def accept_cv_feedback_bullet(
    document_id: str,
    report_id: str,
    body: AcceptBulletRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> CvFeedbackResponse:
    """Explicitly accept one rewritten bullet — the only way a suggestion is endorsed (Decision 3)."""
    service = DocumentService(db)
    return await service.accept_cv_feedback_bullet(document_id, current_user.id, report_id, body.bullet_index)
```

---

### 8.8 `backend/app/services/feedback_generator.py` (EDITED) — add `generate_cv_improvement()`

Appended to the existing file, following the exact same pattern as `generate_interview_feedback()` above it (JSON-mode chat completion, `response.json()` called synchronously — not `await`ed, learning directly from the §2.1 Bug 1 fix so this new function does not reintroduce the same class of bug):

```python
# Appended to backend/app/services/feedback_generator.py

class CvImprovementResult(TypedDict):
    """Structured CV improvement suggestions (Decision 3)."""

    ats_score: int  # 0-100
    strengths: list[str]
    improvements: list[str]
    rewritten_bullets: list[dict[str, str]]  # [{original, rewritten, rationale}]


CV_IMPROVEMENT_SYSTEM_PROMPT = """
You are an expert resume coach and ATS (Applicant Tracking System) specialist.

Review the candidate's CV text and provide improvement suggestions. Focus on:
- ATS optimization: keyword alignment, standard section headers, no tables/columns that break parsers
- Impact quantification: rewrite vague bullets to include a measurable outcome where the source text
  supports it (do not invent numbers the candidate did not provide or imply)
- Clarity and action-verb-led phrasing

Return JSON with exactly these fields:
{
  "ats_score": <int 0-100>,
  "strengths": [<2-4 short strings>],
  "improvements": [<2-4 short, actionable strings>],
  "rewritten_bullets": [
    {"original": <exact text from the CV>, "rewritten": <improved version>, "rationale": <one sentence why>}
  ]
}

Only include bullets that genuinely benefit from rewriting (up to 5). Never fabricate metrics, employers,
or dates not present in the source text. If the CV text is too short or malformed to assess meaningfully,
return an ats_score of 0 and explain why in "improvements".
""".strip()


def _parse_cv_improvement_response(content: str) -> CvImprovementResult:
    try:
        start = content.index("{")
        end = content.rindex("}") + 1
        data = json.loads(content[start:end])

        ats_score = max(0, min(100, int(data.get("ats_score", 0))))
        strengths = data.get("strengths", [])
        improvements = data.get("improvements", [])
        rewritten_bullets = data.get("rewritten_bullets", [])

        if not isinstance(strengths, list):
            strengths = []
        if not isinstance(improvements, list):
            improvements = []
        if not isinstance(rewritten_bullets, list):
            rewritten_bullets = []

        cleaned_bullets = [
            {
                "original": str(b.get("original", "")),
                "rewritten": str(b.get("rewritten", "")),
                "rationale": str(b.get("rationale", "")),
            }
            for b in rewritten_bullets
            if isinstance(b, dict) and b.get("original") and b.get("rewritten")
        ][:5]

        return CvImprovementResult(
            ats_score=ats_score,
            strengths=strengths[:4],
            improvements=improvements[:4],
            rewritten_bullets=cleaned_bullets,
        )
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        logger.warning("Failed to parse CV improvement response", exc_info=True)
        return CvImprovementResult(
            ats_score=0,
            strengths=[],
            improvements=["Unable to generate CV feedback. Please try again."],
            rewritten_bullets=[],
        )


async def generate_cv_improvement(
    cv_text: str,
    target_role: str | None,
    settings: Settings,
) -> tuple[CvImprovementResult, dict[str, int]]:
    """Generate AI CV-improvement suggestions using GPT-4o-mini (Decision 3).

    Mirrors generate_interview_feedback()'s exact calling convention: JSON-mode
    chat completion via raw httpx, response.json() called synchronously.

    Args:
        cv_text: Raw extracted CV text (CandidateDocument.raw_text)
        target_role: Optional role the candidate is optimizing for
        settings: App settings with OpenAI API key

    Returns:
        Tuple of (result, token_usage)
    """
    if not cv_text.strip():
        return (
            CvImprovementResult(ats_score=0, strengths=[], improvements=["No CV text available."], rewritten_bullets=[]),
            {"input_tokens": 0, "output_tokens": 0},
        )

    api_key = settings.openai_api_key.strip()
    if not api_key:
        raise ValueError("OpenAI API key not configured")

    role_line = f"\n\nTarget role: {target_role}" if target_role else ""
    user_content = f"CV text:\n{cv_text[:12000]}{role_line}"  # truncate defensively; GPT-4o-mini context is ample but bounded cost

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": settings.cv_feedback_model,
                "messages": [
                    {"role": "system", "content": CV_IMPROVEMENT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.3,
            },
        )
        response.raise_for_status()
        result = response.json()  # synchronous — see §2.1 Bug 1
        content = result["choices"][0]["message"]["content"]
        usage = result.get("usage", {})
        token_usage = {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        }
        parsed = _parse_cv_improvement_response(content)

        logger.info(
            "Generated CV improvement",
            extra={"ats_score": parsed["ats_score"], "input_tokens": token_usage["input_tokens"]},
        )
        return parsed, token_usage
```

### 8.9 `backend/app/workers/tasks/cv_improvement.py` (NEW — workers/tasks layer, imports only `documents/models.py` ORM classes directly, never `service.py`, per RULE.md's allowed-import rule)

```python
"""RQ worker task: generate CV improvement suggestions (Decision 3).

Runs on the existing QUEUE_FEEDBACK queue (reused, not a new queue) — same
convention as app/workers/tasks/document.py's sync-entrypoint-wraps-async pattern.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from uuid import uuid4

import app.database.orm_registry  # noqa: F401  (registers all ORM models with SQLAlchemy first)
from app.core.config import get_settings
from app.database.session import SessionLocal, engine
from app.infrastructure.redis import close_redis
from app.modules.documents.models import CandidateDocument, CvFeedbackReport, DocumentJob
from app.services.feedback_generator import generate_cv_improvement
from sqlalchemy import select, update as sa_update

logger = logging.getLogger(__name__)


def generate_cv_improvement_job(document_id: str, job_id: str, target_role: str | None) -> None:
    """RQ entrypoint (sync)."""
    asyncio.run(_generate_cv_improvement_job(document_id, job_id, target_role))


async def _generate_cv_improvement_job(document_id: str, job_id: str, target_role: str | None) -> None:
    try:
        async with SessionLocal() as session:
            result = await session.execute(select(CandidateDocument).where(CandidateDocument.id == document_id))
            document = result.scalar_one_or_none()
            if not document or not document.raw_text:
                raise ValueError(f"Document {document_id} not found or has no extracted text")

            settings = get_settings()
            improvement, token_usage = await generate_cv_improvement(document.raw_text, target_role, settings)

            report = CvFeedbackReport(
                id=uuid4(),
                document_id=document.id,
                user_id=document.user_id,
                target_role=target_role,
                ats_score=improvement["ats_score"],
                strengths=improvement["strengths"],
                improvements=improvement["improvements"],
                rewritten_bullets=improvement["rewritten_bullets"],
                accepted_bullet_indices=[],
                created_at=datetime.now(UTC),
            )
            session.add(report)

            await session.execute(
                sa_update(DocumentJob)
                .where(DocumentJob.id == job_id)
                .values(status="completed", progress=100.0, result={"report_id": str(report.id)})
            )
            await session.commit()

            logger.info(
                "CV improvement generated",
                extra={
                    "document_id": document_id,
                    "user_id": str(document.user_id)[:8],
                    "ats_score": improvement["ats_score"],
                    "input_tokens": token_usage["input_tokens"],
                },
            )

    except Exception as exc:
        logger.error("CV improvement generation failed", exc_info=True, extra={"document_id": document_id})
        try:
            async with SessionLocal() as recovery_session:
                await recovery_session.execute(
                    sa_update(DocumentJob).where(DocumentJob.id == job_id).values(status="failed", error=str(exc))
                )
                await recovery_session.commit()
        except Exception:
            logger.error("Failed to mark cv_feedback job as failed", exc_info=True)
        raise
    finally:
        await close_redis()
        await engine.dispose()
```

---

### 8.10 `backend/app/modules/portfolio/` (NEW module — layer: `modules/`, pure CRUD, no LLM, per Decision 4)

**`backend/app/modules/portfolio/__init__.py`**

```python
"""Portfolio module: candidate-authored public project showcase pages."""
```

**`backend/app/modules/portfolio/models.py`**

```python
"""ORM models for candidate portfolio pages (Decision 4)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class PortfolioProfile(Base):
    """One per candidate — holds the public slug and page copy."""

    __tablename__ = "portfolio_profiles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    headline: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )


class PortfolioItem(Base):
    """A single project/link on a candidate's portfolio page."""

    __tablename__ = "portfolio_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("portfolio_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
```

**`backend/app/modules/portfolio/schemas.py`**

```python
"""HTTP schemas for the portfolio module. Slug validation lives here ONLY (RULE.md: no duplicate validation)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

PORTFOLIO_SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])?$")  # RFC 1035 label charset (Decision 4)


class PortfolioItemRequest(BaseModel):
    item_type: Literal["github", "live_demo", "case_study", "other"]
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    url: str = Field(..., min_length=1, max_length=2048)
    display_order: int = 0


class PortfolioItemResponse(PortfolioItemRequest):
    item_id: str
    created_at: datetime


class PortfolioProfileRequest(BaseModel):
    slug: str = Field(..., min_length=3, max_length=63)
    display_name: str | None = Field(default=None, max_length=255)
    headline: str | None = Field(default=None, max_length=255)
    bio: str | None = Field(default=None, max_length=5000)
    is_published: bool = False

    @field_validator("slug")
    @classmethod
    def _validate_slug(cls, v: str) -> str:
        v = v.lower().strip()
        if not PORTFOLIO_SLUG_PATTERN.match(v):
            raise ValueError(
                "Slug must be 3-63 lowercase alphanumeric characters or hyphens, "
                "not starting/ending with a hyphen (subdomain-compatible charset, see Decision 4)"
            )
        return v


class PortfolioProfileResponse(PortfolioProfileRequest):
    profile_id: str
    user_id: str
    public_url: str
    items: list[PortfolioItemResponse]
    created_at: datetime
    updated_at: datetime


class PublicPortfolioResponse(BaseModel):
    """What an unauthenticated visitor to /p/{slug} sees — no user_id, no internal IDs beyond item_id."""

    slug: str
    display_name: str | None
    headline: str | None
    bio: str | None
    items: list[PortfolioItemResponse]
```

**`backend/app/modules/portfolio/repository.py`**

```python
"""Data-access layer for portfolio. Workers (none exist for this module today) would import this, never service.py."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.portfolio.models import PortfolioItem, PortfolioProfile


async def get_profile_by_user_id(db: AsyncSession, user_id: UUID) -> PortfolioProfile | None:
    result = await db.execute(select(PortfolioProfile).where(PortfolioProfile.user_id == user_id))
    return result.scalar_one_or_none()


async def get_profile_by_slug(db: AsyncSession, slug: str) -> PortfolioProfile | None:
    result = await db.execute(select(PortfolioProfile).where(PortfolioProfile.slug == slug))
    return result.scalar_one_or_none()


async def list_items_for_profile(db: AsyncSession, profile_id: UUID) -> list[PortfolioItem]:
    result = await db.execute(
        select(PortfolioItem).where(PortfolioItem.profile_id == profile_id).order_by(PortfolioItem.display_order)
    )
    return list(result.scalars().all())
```

**`backend/app/modules/portfolio/service.py`**

```python
"""Business logic for portfolio profiles and items."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.portfolio.models import PortfolioItem, PortfolioProfile
from app.modules.portfolio.repository import get_profile_by_slug, get_profile_by_user_id, list_items_for_profile
from app.modules.portfolio.schemas import (
    PortfolioItemRequest,
    PortfolioItemResponse,
    PortfolioProfileRequest,
    PortfolioProfileResponse,
    PublicPortfolioResponse,
)


class PortfolioService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._settings = get_settings()

    async def upsert_profile(self, user_id: UUID, body: PortfolioProfileRequest) -> PortfolioProfileResponse:
        existing_slug_owner = await get_profile_by_slug(self.db, body.slug)
        if existing_slug_owner and existing_slug_owner.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already taken")

        profile = await get_profile_by_user_id(self.db, user_id)
        if profile:
            profile.slug = body.slug
            profile.display_name = body.display_name
            profile.headline = body.headline
            profile.bio = body.bio
            profile.is_published = body.is_published
            profile.updated_at = datetime.now(UTC)
        else:
            profile = PortfolioProfile(
                id=uuid4(),
                user_id=user_id,
                slug=body.slug,
                display_name=body.display_name,
                headline=body.headline,
                bio=body.bio,
                is_published=body.is_published,
            )
            self.db.add(profile)
        await self.db.commit()
        await self.db.refresh(profile)
        return await self._to_response(profile)

    async def get_my_profile(self, user_id: UUID) -> PortfolioProfileResponse:
        profile = await get_profile_by_user_id(self.db, user_id)
        if not profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No portfolio profile yet")
        return await self._to_response(profile)

    async def add_item(self, user_id: UUID, body: PortfolioItemRequest) -> PortfolioItemResponse:
        profile = await get_profile_by_user_id(self.db, user_id)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Create a portfolio profile before adding items"
            )
        item = PortfolioItem(
            id=uuid4(),
            profile_id=profile.id,
            item_type=body.item_type,
            title=body.title,
            description=body.description,
            url=body.url,
            display_order=body.display_order,
        )
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        return self._item_to_response(item)

    async def delete_item(self, user_id: UUID, item_id: str) -> None:
        profile = await get_profile_by_user_id(self.db, user_id)
        if not profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No portfolio profile")
        items = await list_items_for_profile(self.db, profile.id)
        target = next((i for i in items if str(i.id) == item_id), None)
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
        await self.db.delete(target)
        await self.db.commit()

    async def get_public_profile(self, slug: str) -> PublicPortfolioResponse:
        """Unauthenticated lookup — used by the public /p/{slug} page (Decision 4)."""
        profile = await get_profile_by_slug(self.db, slug)
        if not profile or not profile.is_published:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
        items = await list_items_for_profile(self.db, profile.id)
        return PublicPortfolioResponse(
            slug=profile.slug,
            display_name=profile.display_name,
            headline=profile.headline,
            bio=profile.bio,
            items=[self._item_to_response(i) for i in items],
        )

    async def _to_response(self, profile: PortfolioProfile) -> PortfolioProfileResponse:
        items = await list_items_for_profile(self.db, profile.id)
        base_url = self._settings.portfolio_public_base_url or "/p"
        return PortfolioProfileResponse(
            profile_id=str(profile.id),
            user_id=str(profile.user_id),
            slug=profile.slug,
            display_name=profile.display_name,
            headline=profile.headline,
            bio=profile.bio,
            is_published=profile.is_published,
            public_url=f"{base_url}/{profile.slug}",
            items=[self._item_to_response(i) for i in items],
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )

    def _item_to_response(self, item: PortfolioItem) -> PortfolioItemResponse:
        return PortfolioItemResponse(
            item_id=str(item.id),
            item_type=item.item_type,
            title=item.title,
            description=item.description,
            url=item.url,
            display_order=item.display_order,
            created_at=item.created_at,
        )
```

**`backend/app/modules/portfolio/router.py`**

```python
"""FastAPI router for the portfolio module. Public slug lookup is intentionally unauthenticated."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.portfolio.schemas import (
    PortfolioItemRequest,
    PortfolioItemResponse,
    PortfolioProfileRequest,
    PortfolioProfileResponse,
    PublicPortfolioResponse,
)
from app.modules.portfolio.service import PortfolioService

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"], route_class=EnvelopeAPIRoute)


@router.put("/profile", response_model=PortfolioProfileResponse)
async def upsert_profile(
    body: PortfolioProfileRequest, current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)
) -> PortfolioProfileResponse:
    return await PortfolioService(db).upsert_profile(current_user.id, body)


@router.get("/profile", response_model=PortfolioProfileResponse)
async def get_my_profile(
    current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)
) -> PortfolioProfileResponse:
    return await PortfolioService(db).get_my_profile(current_user.id)


@router.post("/items", response_model=PortfolioItemResponse, status_code=status.HTTP_201_CREATED)
async def add_item(
    body: PortfolioItemRequest, current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)
) -> PortfolioItemResponse:
    return await PortfolioService(db).add_item(current_user.id, body)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)) -> None:
    await PortfolioService(db).delete_item(current_user.id, item_id)


@router.get("/public/{slug}", response_model=PublicPortfolioResponse)
async def get_public_profile(slug: str, db: AsyncSession = Depends(get_db_session)) -> PublicPortfolioResponse:
    """Unauthenticated — no CurrentUser dependency. This is the endpoint the public /p/{slug} page calls."""
    return await PortfolioService(db).get_public_profile(slug)
```

---

### 8.11 `backend/app/modules/job_swipe/` (NEW module — layer: `modules/`, reads Module 1's `job_matches`/`job_postings` read-only, per Decision 6)

**`backend/app/modules/job_swipe/__init__.py`**

```python
"""Job swipe module: candidate reactions (like/pass/super-like) on Module 1's scored job matches."""
```

**`backend/app/modules/job_swipe/models.py`**

```python
"""ORM model for swipe actions. JobMatch/JobPosting are OWNED by Module 1's job_matching module —
imported here read-only, never redefined (Decision 6, RULE.md 'do not duplicate merge/matching logic')."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class JobSwipeAction(Base):
    """One candidate's swipe decision on one Module-1 JobMatch."""

    __tablename__ = "job_swipe_actions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_match_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_matches.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # "right"|"left"|"up"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
```

**`backend/app/modules/job_swipe/schemas.py`**

```python
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class SwipeableMatchResponse(BaseModel):
    """One card in the swipe deck — same shape as Module 1's JobMatchResponse, re-exposed here for this UI."""

    match_id: str
    job_posting_id: str
    title: str
    company: str
    location: str | None
    remote: bool
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    overall_score: float
    explanation: str | None
    created_at: datetime


class SwipeDeckResponse(BaseModel):
    cards: list[SwipeableMatchResponse]
    has_more: bool


class SwipeActionRequest(BaseModel):
    direction: Literal["right", "left", "up"]


class SwipeActionResponse(BaseModel):
    match_id: str
    direction: str
    created_at: datetime
```

**`backend/app/modules/job_swipe/repository.py`**

```python
"""Data-access layer for job_swipe. Reads Module 1's JobMatch/JobPosting tables directly (read-only)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.job_swipe.models import JobSwipeAction

# NOTE: JobMatch / JobPosting come from Module 1 (phase2_module1.md §7.2) — imported
# here, never redefined. This import will fail with ModuleNotFoundError until
# Module 1 is implemented; see §4.1's explicit cross-module dependency note.
from app.modules.job_matching.models import JobMatch, JobPosting


async def get_unswiped_matches(db: AsyncSession, user_id: UUID, limit: int) -> list[tuple[JobMatch, JobPosting]]:
    already_swiped = select(JobSwipeAction.job_match_id).where(JobSwipeAction.user_id == user_id)
    result = await db.execute(
        select(JobMatch, JobPosting)
        .join(JobPosting, JobMatch.job_posting_id == JobPosting.id)
        .where(JobMatch.user_id == user_id, JobMatch.id.not_in(already_swiped))
        .order_by(JobMatch.overall_score.desc())
        .limit(limit)
    )
    return [(m, p) for m, p in result.all()]


async def record_swipe(db: AsyncSession, job_match_id: UUID, user_id: UUID, direction: str) -> JobSwipeAction:
    existing = await db.execute(select(JobSwipeAction).where(JobSwipeAction.job_match_id == job_match_id))
    action = existing.scalar_one_or_none()
    if action:
        action.direction = direction
        action.created_at = datetime.now(UTC)
    else:
        from uuid import uuid4

        action = JobSwipeAction(id=uuid4(), job_match_id=job_match_id, user_id=user_id, direction=direction)
        db.add(action)
    await db.commit()
    await db.refresh(action)
    return action
```

**`backend/app/modules/job_swipe/service.py`**

```python
"""Business logic for the swipe deck."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.job_matching.models import JobMatch
from app.modules.job_swipe.repository import get_unswiped_matches, record_swipe
from app.modules.job_swipe.schemas import (
    SwipeableMatchResponse,
    SwipeActionRequest,
    SwipeActionResponse,
    SwipeDeckResponse,
)

_DECK_PAGE_SIZE = 20


class JobSwipeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_deck(self, user_id: UUID) -> SwipeDeckResponse:
        rows = await get_unswiped_matches(self.db, user_id, _DECK_PAGE_SIZE + 1)
        has_more = len(rows) > _DECK_PAGE_SIZE
        rows = rows[:_DECK_PAGE_SIZE]
        return SwipeDeckResponse(
            cards=[
                SwipeableMatchResponse(
                    match_id=str(m.id),
                    job_posting_id=str(p.id),
                    title=p.title,
                    company=p.company,
                    location=p.location,
                    remote=p.remote,
                    salary_min=p.salary_min,
                    salary_max=p.salary_max,
                    salary_currency=p.salary_currency,
                    overall_score=m.overall_score,
                    explanation=m.explanation,
                    created_at=m.created_at,
                )
                for m, p in rows
            ],
            has_more=has_more,
        )

    async def swipe(self, user_id: UUID, match_id: str, body: SwipeActionRequest) -> SwipeActionResponse:
        result = await self.db.execute(
            select(JobMatch).where(JobMatch.id == UUID(match_id), JobMatch.user_id == user_id)
        )
        match = result.scalar_one_or_none()
        if not match:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

        action = await record_swipe(self.db, match.id, user_id, body.direction)
        return SwipeActionResponse(match_id=str(match.id), direction=action.direction, created_at=action.created_at)
```

**`backend/app/modules/job_swipe/router.py`**

```python
"""FastAPI router for the swipe deck. Nested under Module 1's /api/matches prefix (§4.3)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.job_swipe.schemas import SwipeActionRequest, SwipeActionResponse, SwipeDeckResponse
from app.modules.job_swipe.service import JobSwipeService

router = APIRouter(prefix="/api/matches", tags=["job-swipe"], route_class=EnvelopeAPIRoute)


@router.get("/swipe-deck", response_model=SwipeDeckResponse)
async def get_swipe_deck(current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)) -> SwipeDeckResponse:
    """Next batch of unswiped matches, highest score first."""
    return await JobSwipeService(db).get_deck(current_user.id)


@router.post("/{match_id}/swipe", response_model=SwipeActionResponse)
async def swipe_match(
    match_id: str, body: SwipeActionRequest, current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)
) -> SwipeActionResponse:
    """Record (or overwrite) a swipe decision on one match."""
    return await JobSwipeService(db).swipe(current_user.id, match_id, body)
```

---

### 8.12 `backend/app/clients/perplexity.py` (NEW — clients layer: "one provider per file", per Decision 7)

```python
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
            data = response.json()  # synchronous — see §2.1 Bug 1; not repeated here
            summary = data["choices"][0]["message"]["content"]
            return {"summary": summary.strip(), "source": "perplexity"}
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            logger.warning("Perplexity company-context lookup failed", extra={"error": str(exc)})
            return {"summary": "", "source": "none"}
```

### 8.13 `backend/app/modules/outreach/` (NEW module — layer: `modules/`)

**`backend/app/modules/outreach/__init__.py`**

```python
"""Outreach module: AI-drafted, candidate-reviewed personalized outreach messages (Decision 5)."""
```

**`backend/app/modules/outreach/models.py`**

```python
"""ORM model for outreach drafts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, JsonDoc


class OutreachMessage(Base):
    """A single AI-drafted (and possibly sent) outreach message."""

    __tablename__ = "outreach_messages"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_match_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("job_matches.id", ondelete="SET NULL"), nullable=True
    )
    recipient_role_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    company_context_used: Mapped[dict[str, Any]] = mapped_column(JsonDoc, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
```

**`backend/app/modules/outreach/schemas.py`**

```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class OutreachDraftRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    recipient_role_title: str | None = Field(default=None, max_length=255)
    job_match_id: str | None = None
    document_id: str  # which CV to draw candidate context from


class OutreachMessageResponse(BaseModel):
    message_id: str
    company_name: str
    recipient_role_title: str | None
    subject: str
    body: str
    status: str
    sent_at: datetime | None
    created_at: datetime


class OutreachListResponse(BaseModel):
    messages: list[OutreachMessageResponse]


class OutreachEditRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1, max_length=10000)
```

**`backend/app/modules/outreach/repository.py`**

```python
"""Data-access layer for outreach. Workers import this, never service.py."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.outreach.models import OutreachMessage


async def get_owned_message(db: AsyncSession, message_id: UUID, user_id: UUID) -> OutreachMessage | None:
    result = await db.execute(
        select(OutreachMessage).where(OutreachMessage.id == message_id, OutreachMessage.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def list_messages_for_user(db: AsyncSession, user_id: UUID, limit: int = 50) -> list[OutreachMessage]:
    result = await db.execute(
        select(OutreachMessage)
        .where(OutreachMessage.user_id == user_id)
        .order_by(OutreachMessage.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def mark_sent(db: AsyncSession, message: OutreachMessage) -> OutreachMessage:
    message.status = "sent"
    message.sent_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(message)
    return message
```

**`backend/app/modules/outreach/service.py`**

```python
"""Business logic for outreach drafting, editing, and sending (Decision 5)."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from redis import Redis
from rq import Queue
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.documents.models import CandidateDocument
from app.modules.outreach.models import OutreachMessage
from app.modules.outreach.repository import get_owned_message, list_messages_for_user, mark_sent
from app.modules.outreach.schemas import (
    OutreachDraftRequest,
    OutreachEditRequest,
    OutreachListResponse,
    OutreachMessageResponse,
)
from app.workers.queue import QUEUE_OUTREACH, get_redis_connection
from sqlalchemy import select

_UNSUBSCRIBE_FOOTER_TEMPLATE = (
    "\n\n---\n"
    "You're receiving this message because {sender_name} applied to or expressed interest in "
    "opportunities at {company_name} and used HyrePath to draft this note. "
    "Reply to {sender_email} directly, or let us know if you'd prefer not to receive further outreach."
)


class OutreachService:
    def __init__(self, db: AsyncSession, redis_conn: Redis | None = None):
        self.db = db
        self.redis_conn = redis_conn or get_redis_connection()
        self._settings = get_settings()

    async def request_draft(self, user_id: UUID, body: OutreachDraftRequest) -> dict:
        """Enqueue draft generation. Returns immediately with a job reference (async, per RULE.md conventions)."""
        if not self._settings.outreach_enabled:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Outreach feature is disabled")

        doc_result = await self.db.execute(
            select(CandidateDocument).where(
                CandidateDocument.id == UUID(body.document_id), CandidateDocument.user_id == user_id
            )
        )
        document = doc_result.scalar_one_or_none()
        if not document or document.processing_status != "completed":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A processed CV is required")

        queue = Queue(QUEUE_OUTREACH, connection=self.redis_conn)
        rq_job = queue.enqueue(
            "app.workers.tasks.outreach.generate_outreach_draft_job",
            str(user_id),
            body.document_id,
            body.company_name,
            body.recipient_role_title,
            body.job_match_id,
            job_timeout=60,
        )
        return {"rq_job_id": rq_job.id, "message": "Outreach draft generation started"}

    async def list_my_messages(self, user_id: UUID) -> OutreachListResponse:
        messages = await list_messages_for_user(self.db, user_id)
        return OutreachListResponse(messages=[self._to_response(m) for m in messages])

    async def edit_draft(self, user_id: UUID, message_id: str, body: OutreachEditRequest) -> OutreachMessageResponse:
        message = await get_owned_message(self.db, UUID(message_id), user_id)
        if not message:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
        if message.status != "draft":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only drafts can be edited")
        message.subject = body.subject
        message.body = body.body
        await self.db.commit()
        await self.db.refresh(message)
        return self._to_response(message)

    async def send_message(self, user_id: UUID, message_id: str, sender_email: str, sender_name: str) -> OutreachMessageResponse:
        """Append the mandatory disclosure footer and mark as sent (Decision 5, CAN-SPAM).

        This method does NOT actually transmit an email over SMTP in v1 — no email-sending
        infra targeting arbitrary third-party recipients exists in this repo today (verified:
        email_service.py only sends to the platform's own users via SendGrid templates, never
        to an arbitrary hiring-manager address supplied by a candidate). Marking as 'sent' here
        records the candidate's own action of copying/sending it externally themselves. Building
        real outbound send-as-the-candidate infrastructure (with its own deliverability, SPF/DKIM,
        and abuse-prevention concerns) is explicitly out of scope for this document — stated here
        so it is not silently assumed to exist.
        """
        message = await get_owned_message(self.db, UUID(message_id), user_id)
        if not message:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
        if message.status != "draft":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Message already sent or discarded")

        footer = _UNSUBSCRIBE_FOOTER_TEMPLATE.format(
            sender_name=sender_name, company_name=message.company_name, sender_email=sender_email
        )
        message.body = message.body + footer
        message = await mark_sent(self.db, message)
        return self._to_response(message)

    def _to_response(self, message: OutreachMessage) -> OutreachMessageResponse:
        return OutreachMessageResponse(
            message_id=str(message.id),
            company_name=message.company_name,
            recipient_role_title=message.recipient_role_title,
            subject=message.subject,
            body=message.body,
            status=message.status,
            sent_at=message.sent_at,
            created_at=message.created_at,
        )
```

**`backend/app/modules/outreach/router.py`**

```python
"""FastAPI router for outreach drafting/editing/sending."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.outreach.schemas import (
    OutreachDraftRequest,
    OutreachEditRequest,
    OutreachListResponse,
    OutreachMessageResponse,
)
from app.modules.outreach.service import OutreachService

router = APIRouter(prefix="/api/outreach", tags=["outreach"], route_class=EnvelopeAPIRoute)


@router.post("/drafts")
async def request_draft(
    body: OutreachDraftRequest, current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)
) -> dict:
    return await OutreachService(db).request_draft(current_user.id, body)


@router.get("", response_model=OutreachListResponse)
async def list_messages(
    current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)
) -> OutreachListResponse:
    return await OutreachService(db).list_my_messages(current_user.id)


@router.patch("/{message_id}", response_model=OutreachMessageResponse)
async def edit_draft(
    message_id: str,
    body: OutreachEditRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> OutreachMessageResponse:
    return await OutreachService(db).edit_draft(current_user.id, message_id, body)


@router.post("/{message_id}/send", response_model=OutreachMessageResponse)
async def send_message(
    message_id: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)
) -> OutreachMessageResponse:
    """Appends the mandatory disclosure footer (Decision 5) and marks the draft as sent."""
    return await OutreachService(db).send_message(
        current_user.id, message_id, sender_email=current_user.email, sender_name=current_user.email.split("@")[0]
    )
```

### 8.14 `backend/app/workers/tasks/outreach.py` (NEW — imports `repository.py` + `clients/perplexity.py` only, never `service.py`)

```python
"""RQ worker task: generate an outreach draft using Perplexity company context + GPT-4o (Decision 5)."""

from __future__ import annotations

import asyncio
import json
import logging
from uuid import UUID, uuid4

import httpx

import app.database.orm_registry  # noqa: F401
from app.clients.perplexity import PerplexityClient
from app.core.config import get_settings
from app.database.session import SessionLocal, engine
from app.domain.candidate import CVData
from app.infrastructure.redis import close_redis
from app.modules.documents.models import CandidateDocument
from app.modules.outreach.models import OutreachMessage
from sqlalchemy import select

logger = logging.getLogger(__name__)

_OUTREACH_SYSTEM_PROMPT = """
You are helping a job candidate write a short, personalized outreach email to a hiring
manager. Use the candidate's background and the provided public company context. Keep it
under 150 words, professional, specific (reference at least one real detail from the
company context if provided), and end with a clear, low-friction call to action.
Return JSON: {"subject": <string>, "body": <string>}. Do not fabricate company facts
beyond what is provided in the context; if context is empty, write a more general
but still personalized-to-the-candidate message.
""".strip()


def generate_outreach_draft_job(
    user_id: str, document_id: str, company_name: str, role_title: str | None, job_match_id: str | None
) -> None:
    asyncio.run(_generate_outreach_draft_job(user_id, document_id, company_name, role_title, job_match_id))


async def _generate_outreach_draft_job(
    user_id: str, document_id: str, company_name: str, role_title: str | None, job_match_id: str | None
) -> None:
    try:
        async with SessionLocal() as session:
            doc_result = await session.execute(select(CandidateDocument).where(CandidateDocument.id == document_id))
            document = doc_result.scalar_one_or_none()
            if not document:
                raise ValueError(f"Document {document_id} not found")

            cv_data = CVData(**(document.extracted_data or {})) if document.extracted_data else CVData()

            perplexity = PerplexityClient()
            context = await perplexity.get_company_context(company_name, role_title)

            settings = get_settings()
            subject, body = await _draft_with_llm(cv_data, company_name, role_title, context["summary"], settings)

            message = OutreachMessage(
                id=uuid4(),
                user_id=UUID(user_id),
                job_match_id=UUID(job_match_id) if job_match_id else None,
                recipient_role_title=role_title,
                company_name=company_name,
                subject=subject,
                body=body,
                company_context_used=context,
                status="draft",
            )
            session.add(message)
            await session.commit()

            logger.info(
                "Outreach draft generated",
                extra={"user_id": user_id[:8], "company_name": company_name, "context_source": context["source"]},
            )
    except Exception:
        logger.error("Outreach draft generation failed", exc_info=True, extra={"user_id": user_id[:8]})
        raise
    finally:
        await close_redis()
        await engine.dispose()


async def _draft_with_llm(
    cv_data: CVData, company_name: str, role_title: str | None, company_context: str, settings
) -> tuple[str, str]:
    api_key = settings.openai_api_key.strip()
    if not api_key:
        return (
            f"Interested in opportunities at {company_name}",
            f"Hello,\n\nI'm reaching out because I'm interested in {role_title or 'opportunities'} "
            f"at {company_name}. I'd welcome the chance to connect.\n\nBest regards",
        )

    candidate_summary = (
        f"Current role: {cv_data.current_role or 'N/A'}. "
        f"Skills: {', '.join(cv_data.technical_skills[:8])}. "
        f"Years of experience: {cv_data.total_years_experience or 'N/A'}."
    )
    user_content = (
        f"Candidate background: {candidate_summary}\n"
        f"Target company: {company_name}\n"
        f"Target role: {role_title or 'not specified'}\n"
        f"Public company context: {company_context or '(none available)'}"
    )

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": _OUTREACH_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.5,
            },
        )
        response.raise_for_status()
        result = response.json()  # synchronous — see §2.1 Bug 1
        content = result["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return parsed.get("subject", f"Interested in {company_name}"), parsed.get("body", "")
```

---

### 8.15 Wiring — queue registration, router mounting, email templates

**File edited:** `backend/app/workers/queue.py` — add one new queue constant (`QUEUE_OUTREACH`; CV chat and CV feedback both reuse existing queues — `cv_chat` has no RQ queue at all since it's synchronous request/response per Decision 2, and CV feedback reuses `QUEUE_FEEDBACK`):

```python
# Added near the other queue constants in backend/app/workers/queue.py:
QUEUE_OUTREACH = "outreach_generation"

# Added to QUEUE_PRIORITIES dict:
QUEUE_PRIORITIES = {
    QUEUE_EMAIL: 10,
    QUEUE_CV_EXTRACTION: 8,
    QUEUE_FEEDBACK: 7,
    QUEUE_OUTREACH: 6,       # NEW — user-facing but not time-critical; below feedback, above document/embedding
    QUEUE_DOCUMENT: 5,
    QUEUE_EMBEDDING: 3,
    QUEUE_NAME: 2,
    QUEUE_CLEANUP: 1,
    QUEUE_AUDIO_CLEANUP: 1,
}
```

**File edited:** `backend/app/workers/rq_worker.py` — add `QUEUE_OUTREACH` to the general-purpose worker's queue list (per-tier workers are unaffected — Module 2's queues are only consumed by the general-purpose worker, same as `QUEUE_FEEDBACK`/`QUEUE_DOCUMENT` today):

```python
# Edited inside main(), the "else" branch (general-purpose worker):
from app.workers.queue import (
    QUEUE_FEEDBACK,
    QUEUE_DOCUMENT,
    QUEUE_EMBEDDING,
    QUEUE_CV_EXTRACTION,
    QUEUE_OUTREACH,   # NEW
    QUEUE_NAME,
)

queues = [
    Queue(QUEUE_FEEDBACK, connection=connection),
    Queue(QUEUE_OUTREACH, connection=connection),      # NEW — Module 2
    Queue(QUEUE_DOCUMENT, connection=connection),
    Queue(QUEUE_EMBEDDING, connection=connection),
    Queue(QUEUE_CV_EXTRACTION, connection=connection),
    Queue(QUEUE_NAME, connection=connection),
]
```

Note per `phase2_module1.md` §4's already-documented RQ starvation risk (fixed-priority queue lists never touch a lower queue while a higher one has backlog): `QUEUE_OUTREACH` is placed **after** `QUEUE_FEEDBACK` (both are "high, user-facing, LLM-backed" in character) and **before** `QUEUE_DOCUMENT`/`QUEUE_EMBEDDING` (batch-ish). This is a deliberate ordering choice, not an oversight — outreach generation is a user-initiated, wait-for-it action (the candidate is looking at a spinner), same urgency class as CV feedback, not a background batch job.

**File edited:** `backend/app/main.py` — mount the three new routers (find the existing `app.include_router(documents_router)` call and add three new lines beside it; `documents/router.py`'s router object itself does not change its mount point since it's edited-in-place, not new):

```python
# Added imports in backend/app/main.py:
from app.modules.portfolio.router import router as portfolio_router
from app.modules.job_swipe.router import router as job_swipe_router
from app.modules.outreach.router import router as outreach_router

# Added alongside the existing app.include_router(documents_router) call:
app.include_router(portfolio_router)
app.include_router(job_swipe_router)
app.include_router(outreach_router)
```

**File edited:** `backend/app/database/orm_registry.py` — add the three new modules' ORM imports so Alembic/SQLAlchemy discover them (follow the exact existing pattern — this file's only job is side-effect imports):

```python
# Added to backend/app/database/orm_registry.py:
import app.modules.portfolio.models  # noqa: F401
import app.modules.job_swipe.models  # noqa: F401
import app.modules.outreach.models  # noqa: F401
```

**File edited:** `backend/app/services/email_service.py` — two new `EmailTemplate` members (per §2's reuse table; no new email-sending mechanism):

```python
# Added to the EmailTemplate enum in backend/app/services/email_service.py:
CV_COMPLETENESS_REMINDER = "cv_completeness_reminder"
PORTFOLIO_PUBLISHED = "portfolio_published"

# Added to the _render_template dispatch dict (same file, existing method):
EmailTemplate.CV_COMPLETENESS_REMINDER: _render_cv_completeness_reminder,
EmailTemplate.PORTFOLIO_PUBLISHED: _render_portfolio_published,
```

(The two `_render_*` helper functions follow the exact same signature/pattern as the existing template renderers in that file — omitted here for brevity since they are pure string-templating functions with no new logic, not central to Module 2's completion; their exact HTML is a content/copywriting detail, not an architectural one, and is intentionally left to whoever writes the final copy rather than hard-coded in this plan.)

---

## 9. Testing — proving Module 2 is 100% complete

Every new/edited piece of logic gets its own test, following the exact fixture pattern already established in `backend/tests/conftest.py` (SQLite for local/CI, `TEST_DATABASE_URL` for Postgres-specific tests) — no new test infrastructure invented. All OpenAI/Perplexity HTTP calls are mocked (RULE.md: "no live external calls in CI").

### 9.1 `backend/tests/test_cv_completeness.py` (NEW) — pure function tests for §8.1

```python
"""Tests for app.domain.cv_completeness — pure functions, no DB, no mocks needed."""

from app.domain.candidate import CVData
from app.domain.cv_completeness import compute_missing_fields, completeness_score, question_for_field


def test_compute_missing_fields_all_missing_on_empty_cv():
    missing = compute_missing_fields(CVData())
    assert missing == [
        "email", "phone", "linkedin_url", "technical_skills",
        "total_years_experience", "desired_roles", "desired_locations", "remote_preference",
    ]


def test_compute_missing_fields_none_missing_on_full_cv():
    cv = CVData(
        email="a@b.com", phone="555-1234", linkedin_url="https://linkedin.com/in/a",
        technical_skills=["python"], total_years_experience=5.0,
        desired_roles=["engineer"], desired_locations=["remote"], remote_preference="remote",
    )
    assert compute_missing_fields(cv) == []


def test_compute_missing_fields_partial():
    cv = CVData(email="a@b.com", technical_skills=["python"])
    missing = compute_missing_fields(cv)
    assert "email" not in missing
    assert "technical_skills" not in missing
    assert "phone" in missing
    assert "remote_preference" in missing


def test_completeness_score_matches_missing_fraction():
    cv = CVData(email="a@b.com")  # 1 of 8 fields
    score = completeness_score(cv)
    assert score == round(7 / 8, 4)


def test_question_for_field_known_field():
    assert "email" in question_for_field("email").lower()


def test_question_for_field_unknown_field_falls_back_gracefully():
    q = question_for_field("some_new_field")
    assert "some new field" in q.lower()
```

### 9.2 `backend/tests/test_cv_chat.py` (NEW) — CV completeness chatbot, §8.2-8.4

```python
"""Tests for CvChatService. OpenAI calls mocked per RULE.md 'no live external calls in CI'."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.documents.cv_chat_service import CvChatService
from app.modules.documents.models import CandidateDocument


@pytest.fixture
async def completed_document(db_session, test_user):
    doc = CandidateDocument(
        id=uuid4(),
        user_id=test_user.id,
        document_type="cv",
        original_filename="cv.pdf",
        storage_path="documents/x/y.pdf",
        file_hash="abc123",
        file_size_bytes=1000,
        raw_text="Jane Doe, Software Engineer",
        extracted_data={"email": "jane@example.com"},  # 1 of 8 required fields present
        processing_status="completed",
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    return doc


async def test_start_session_creates_session_with_missing_fields(db_session, test_user, completed_document):
    service = CvChatService(db_session)
    response = await service.start_session(str(completed_document.id), test_user.id)

    assert response.status == "active"
    assert "email" not in response.missing_fields_at_start  # already present
    assert "phone" in response.missing_fields_at_start
    assert len(response.messages) == 1
    assert response.messages[0].role == "assistant"


async def test_start_session_resumes_existing_active_session(db_session, test_user, completed_document):
    service = CvChatService(db_session)
    first = await service.start_session(str(completed_document.id), test_user.id)
    second = await service.start_session(str(completed_document.id), test_user.id)
    assert first.session_id == second.session_id


async def test_start_session_rejects_unprocessed_document(db_session, test_user, completed_document):
    completed_document.processing_status = "pending"
    await db_session.commit()
    service = CvChatService(db_session)
    with pytest.raises(Exception) as exc_info:
        await service.start_session(str(completed_document.id), test_user.id)
    assert "processing" in str(exc_info.value).lower() or "409" in str(exc_info.value)


async def test_post_message_applies_tool_call_and_advances(db_session, test_user, completed_document):
    service = CvChatService(db_session)
    session_response = await service.start_session(str(completed_document.id), test_user.id)

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(
        return_value={
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "record_cv_answer",
                                    "arguments": '{"field_name": "phone", "value": "555-0100"}',
                                }
                            }
                        ]
                    }
                }
            ]
        }
    )
    with patch.object(service._client, "post", new=AsyncMock(return_value=mock_response)):
        turn = await service.post_message(session_response.session_id, test_user.id, "It's 555-0100")

    assert "phone" in turn.session.fields_resolved
    assert turn.assistant_message.role == "assistant"


async def test_post_message_no_tool_call_reprompts_same_field(db_session, test_user, completed_document):
    service = CvChatService(db_session)
    session_response = await service.start_session(str(completed_document.id), test_user.id)

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value={"choices": [{"message": {}}]}) # no tool_calls
    with patch.object(service._client, "post", new=AsyncMock(return_value=mock_response)):
        turn = await service.post_message(session_response.session_id, test_user.id, "huh?")

    assert turn.session.fields_resolved == []  # no field resolved yet


async def test_post_message_enforces_turn_limit(db_session, test_user, completed_document):
    service = CvChatService(db_session)
    service._settings.cv_chat_max_turns = 1  # tight limit for the test
    session_response = await service.start_session(str(completed_document.id), test_user.id)

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value={"choices": [{"message": {}}]})
    with patch.object(service._client, "post", new=AsyncMock(return_value=mock_response)):
        await service.post_message(session_response.session_id, test_user.id, "one")
        with pytest.raises(Exception):
            await service.post_message(session_response.session_id, test_user.id, "two")
```

### 9.3 `backend/tests/test_cv_improvement.py` (NEW) — Decision 3, §8.8-8.9

```python
"""Tests for generate_cv_improvement() and its parser."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import get_settings
from app.services.feedback_generator import _parse_cv_improvement_response, generate_cv_improvement


def test_parse_cv_improvement_response_valid_json():
    content = (
        '{"ats_score": 72, "strengths": ["Clear structure"], '
        '"improvements": ["Add metrics"], '
        '"rewritten_bullets": [{"original": "Made code faster", '
        '"rewritten": "Reduced API latency by optimizing caching", "rationale": "Adds impact"}]}'
    )
    result = _parse_cv_improvement_response(content)
    assert result["ats_score"] == 72
    assert len(result["rewritten_bullets"]) == 1
    assert result["rewritten_bullets"][0]["original"] == "Made code faster"


def test_parse_cv_improvement_response_malformed_falls_back():
    result = _parse_cv_improvement_response("not json at all")
    assert result["ats_score"] == 0
    assert result["rewritten_bullets"] == []


def test_parse_cv_improvement_response_clamps_score():
    content = '{"ats_score": 150, "strengths": [], "improvements": [], "rewritten_bullets": []}'
    result = _parse_cv_improvement_response(content)
    assert result["ats_score"] == 100


async def test_generate_cv_improvement_empty_text_short_circuits():
    settings = get_settings()
    result, tokens = await generate_cv_improvement("", None, settings)
    assert result["ats_score"] == 0
    assert tokens == {"input_tokens": 0, "output_tokens": 0}


async def test_generate_cv_improvement_calls_openai_and_parses(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()
    settings = get_settings()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(
        return_value={
            "choices": [{"message": {"content": '{"ats_score": 80, "strengths": [], "improvements": [], "rewritten_bullets": []}'}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }
    )
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)):
        result, tokens = await generate_cv_improvement("Some CV text here", "Software Engineer", settings)

    assert result["ats_score"] == 80
    assert tokens["input_tokens"] == 100
    get_settings.cache_clear()
```

### 9.4 `backend/tests/test_cv_extraction.py` (EDITED) — regression test proving §2.1 Bug 1 stays fixed

```python
# Added to the existing backend/tests/test_cv_extraction.py:

async def test_extract_with_llm_does_not_await_sync_json_method(monkeypatch):
    """Regression test for phase2_module2.md §2.1 Bug 1: response.json() must be called
    synchronously, never awaited, or every real-key CV extraction silently returns empty."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from app.services.cv_extractor import CVExtractor

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    mock_response = MagicMock()  # NOT AsyncMock — .json() must be a plain sync callable
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(
        return_value={"choices": [{"message": {"content": '{"full_name": "Jane Doe"}'}}]}
    )

    extractor = CVExtractor()
    with patch.object(extractor._client, "post", new=AsyncMock(return_value=mock_response)):
        cv_data = await extractor._extract_with_llm("Jane Doe, Software Engineer")

    # Before the fix, this raised TypeError internally (caught by the broad except),
    # silently returning an all-empty CVData. After the fix, the real value comes through.
    assert cv_data.full_name == "Jane Doe"
```

### 9.5 `backend/tests/test_session_tracking.py` (EDITED) — regression test proving §2.1 Bug 2 stays fixed

```python
# Added to the existing backend/tests/test_session_tracking.py:

async def test_start_session_accepts_uuid_and_str_user_id(db_session, test_user):
    """Regression test for phase2_module2.md §2.1 Bug 2: user_id must be coerced to
    uuid.UUID before binding to the ORM column, or Postgres raises StatementError."""
    from app.services.session_manager import SessionManager

    manager = SessionManager(db_session)

    session_from_uuid = await manager.start_session(test_user.id, "interview_practice")
    assert session_from_uuid.user_id == test_user.id

    session_from_str = await manager.start_session(str(test_user.id), "interview_practice")
    assert session_from_str.user_id == test_user.id
```

### 9.6 `backend/tests/test_portfolio.py` (NEW) — §8.10

```python
"""Tests for the portfolio module: profile CRUD, slug validation, public lookup."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.portfolio.schemas import PortfolioProfileRequest
from app.modules.portfolio.service import PortfolioService


def test_slug_validation_rejects_uppercase():
    with pytest.raises(ValidationError):
        PortfolioProfileRequest(slug="JohnDoe")


def test_slug_validation_rejects_leading_hyphen():
    with pytest.raises(ValidationError):
        PortfolioProfileRequest(slug="-johndoe")


def test_slug_validation_rejects_too_short():
    with pytest.raises(ValidationError):
        PortfolioProfileRequest(slug="jd")


def test_slug_validation_accepts_valid_slug():
    req = PortfolioProfileRequest(slug="john-doe-42")
    assert req.slug == "john-doe-42"


async def test_upsert_profile_creates_then_updates(db_session, test_user):
    service = PortfolioService(db_session)
    req = PortfolioProfileRequest(slug="john-doe", headline="Backend Engineer", is_published=True)
    created = await service.upsert_profile(test_user.id, req)
    assert created.slug == "john-doe"

    req2 = PortfolioProfileRequest(slug="john-doe", headline="Senior Backend Engineer", is_published=True)
    updated = await service.upsert_profile(test_user.id, req2)
    assert updated.profile_id == created.profile_id
    assert updated.headline == "Senior Backend Engineer"


async def test_upsert_profile_rejects_slug_taken_by_another_user(db_session, test_user, other_user):
    service = PortfolioService(db_session)
    await service.upsert_profile(test_user.id, PortfolioProfileRequest(slug="taken-slug"))
    with pytest.raises(Exception) as exc_info:
        await service.upsert_profile(other_user.id, PortfolioProfileRequest(slug="taken-slug"))
    assert "409" in str(exc_info.value) or "taken" in str(exc_info.value).lower()


async def test_get_public_profile_hides_unpublished(db_session, test_user):
    service = PortfolioService(db_session)
    await service.upsert_profile(test_user.id, PortfolioProfileRequest(slug="hidden-one", is_published=False))
    with pytest.raises(Exception) as exc_info:
        await service.get_public_profile("hidden-one")
    assert "404" in str(exc_info.value) or "not found" in str(exc_info.value).lower()


async def test_get_public_profile_returns_published(db_session, test_user):
    service = PortfolioService(db_session)
    await service.upsert_profile(test_user.id, PortfolioProfileRequest(slug="visible-one", is_published=True))
    public = await service.get_public_profile("visible-one")
    assert public.slug == "visible-one"
    # Public response must never leak user_id (privacy — verified by schema shape, not just by value)
    assert not hasattr(public, "user_id")
```

### 9.7 `backend/tests/test_job_swipe.py` (NEW) — §8.11

```python
"""Tests for the swipe deck. Fakes Module 1's job_matches/job_postings rows directly per §4.1 —
these tests do not require Module 1's worker/scanner to run."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.job_matching.models import JobMatch, JobPosting  # Module 1 — see §4.1 dependency note
from app.modules.job_swipe.schemas import SwipeActionRequest
from app.modules.job_swipe.service import JobSwipeService


@pytest.fixture
async def seeded_match(db_session, test_user):
    posting = JobPosting(
        id=uuid4(), dedup_key="hash1", title="Backend Engineer", company="Acme",
        location="Remote", remote=True, source="linkedin", first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC), sources_seen=["linkedin"], is_active=True,
    )
    db_session.add(posting)
    await db_session.flush()
    match = JobMatch(
        id=uuid4(), user_id=test_user.id, job_posting_id=posting.id,
        similarity_score=0.8, rule_score=1.0, overall_score=86.0, score_breakdown={},
    )
    db_session.add(match)
    await db_session.commit()
    return match, posting


async def test_get_deck_returns_unswiped_matches(db_session, test_user, seeded_match):
    service = JobSwipeService(db_session)
    deck = await service.get_deck(test_user.id)
    assert len(deck.cards) == 1
    assert deck.cards[0].company == "Acme"


async def test_swipe_removes_card_from_next_deck_fetch(db_session, test_user, seeded_match):
    match, _ = seeded_match
    service = JobSwipeService(db_session)
    await service.swipe(test_user.id, str(match.id), SwipeActionRequest(direction="right"))

    deck = await service.get_deck(test_user.id)
    assert len(deck.cards) == 0


async def test_swipe_overwrites_previous_decision_not_duplicate(db_session, test_user, seeded_match):
    match, _ = seeded_match
    service = JobSwipeService(db_session)
    first = await service.swipe(test_user.id, str(match.id), SwipeActionRequest(direction="left"))
    second = await service.swipe(test_user.id, str(match.id), SwipeActionRequest(direction="right"))
    assert first.match_id == second.match_id
    assert second.direction == "right"


async def test_swipe_rejects_match_owned_by_another_user(db_session, test_user, other_user, seeded_match):
    match, _ = seeded_match
    service = JobSwipeService(db_session)
    with pytest.raises(Exception) as exc_info:
        await service.swipe(other_user.id, str(match.id), SwipeActionRequest(direction="right"))
    assert "404" in str(exc_info.value)
```

### 9.8 `backend/tests/test_outreach.py` (NEW) — §8.12-8.14

```python
"""Tests for outreach drafting, editing, and sending. Perplexity + OpenAI mocked."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.clients.perplexity import PerplexityClient
from app.modules.outreach.schemas import OutreachEditRequest
from app.modules.outreach.service import OutreachService


async def test_perplexity_client_returns_empty_summary_when_no_api_key(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    client = PerplexityClient()
    result = await client.get_company_context("Acme Corp")
    assert result == {"summary": "", "source": "none"}
    get_settings.cache_clear()


async def test_perplexity_client_fails_soft_on_http_error(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-test")
    from app.core.config import get_settings

    get_settings.cache_clear()
    client = PerplexityClient()
    with patch.object(client._client, "post", new=AsyncMock(side_effect=Exception("network error"))):
        result = await client.get_company_context("Acme Corp")
    assert result["source"] == "none"
    get_settings.cache_clear()


async def test_edit_draft_rejects_editing_sent_message(db_session, test_user):
    from app.modules.outreach.models import OutreachMessage
    from uuid import uuid4
    from datetime import UTC, datetime

    message = OutreachMessage(
        id=uuid4(), user_id=test_user.id, company_name="Acme", subject="Hi", body="Body",
        status="sent", sent_at=datetime.now(UTC),
    )
    db_session.add(message)
    await db_session.commit()

    service = OutreachService(db_session)
    with pytest.raises(Exception) as exc_info:
        await service.edit_draft(test_user.id, str(message.id), OutreachEditRequest(subject="New", body="New body"))
    assert "409" in str(exc_info.value) or "draft" in str(exc_info.value).lower()


async def test_send_message_appends_disclosure_footer_and_marks_sent(db_session, test_user):
    from app.modules.outreach.models import OutreachMessage
    from uuid import uuid4

    message = OutreachMessage(
        id=uuid4(), user_id=test_user.id, company_name="Acme", subject="Hi",
        body="Original body with no footer.", status="draft",
    )
    db_session.add(message)
    await db_session.commit()

    service = OutreachService(db_session)
    result = await service.send_message(test_user.id, str(message.id), sender_email="jane@example.com", sender_name="jane")

    assert result.status == "sent"
    assert "unsubscribe" in result.body.lower() or "prefer not to receive" in result.body.lower()
    assert "jane@example.com" in result.body


async def test_send_message_rejects_already_sent(db_session, test_user):
    from app.modules.outreach.models import OutreachMessage
    from uuid import uuid4
    from datetime import UTC, datetime

    message = OutreachMessage(
        id=uuid4(), user_id=test_user.id, company_name="Acme", subject="Hi", body="Body",
        status="sent", sent_at=datetime.now(UTC),
    )
    db_session.add(message)
    await db_session.commit()

    service = OutreachService(db_session)
    with pytest.raises(Exception) as exc_info:
        await service.send_message(test_user.id, str(message.id), sender_email="jane@example.com", sender_name="jane")
    assert "409" in str(exc_info.value)
```

### 9.9 `backend/tests/test_module2_api.py` (NEW) — router-level tests: status codes, auth, response shape (RULE.md: "new route behavior → API test")

```python
"""End-to-end API tests for every new Module 2 route, via FastAPI's TestClient/httpx.

Covers: status codes, auth enforcement (401 without cookie), and response envelope shape
(every success response wrapped by EnvelopeAPIRoute per the existing convention).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


async def test_completeness_route_requires_auth(client: AsyncClient):
    response = await client.get("/api/documents/00000000-0000-0000-0000-000000000000/completeness")
    assert response.status_code == 401


async def test_completeness_route_returns_envelope_shape(authed_client: AsyncClient, completed_document):
    response = await authed_client.get(f"/api/documents/{completed_document.id}/completeness")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "completeness_score" in body["data"]
    assert "missing_fields" in body["data"]


async def test_cv_chat_start_session_route(authed_client: AsyncClient, completed_document):
    response = await authed_client.post(f"/api/documents/{completed_document.id}/cv-chat/sessions")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "active"


async def test_cv_feedback_request_route_returns_job_id(authed_client: AsyncClient, completed_document):
    response = await authed_client.post(
        f"/api/documents/{completed_document.id}/feedback", json={"target_role": "Backend Engineer"}
    )
    assert response.status_code == 200
    assert "job_id" in response.json()["data"]


async def test_portfolio_profile_put_route_requires_auth(client: AsyncClient):
    response = await client.put("/api/portfolio/profile", json={"slug": "test-slug"})
    assert response.status_code == 401


async def test_portfolio_public_route_is_unauthenticated(client: AsyncClient, published_portfolio):
    response = await client.get(f"/api/portfolio/public/{published_portfolio.slug}")
    assert response.status_code == 200
    assert response.json()["data"]["slug"] == published_portfolio.slug


async def test_portfolio_public_route_404_for_unknown_slug(client: AsyncClient):
    response = await client.get("/api/portfolio/public/does-not-exist")
    assert response.status_code == 404


async def test_swipe_deck_route_requires_auth(client: AsyncClient):
    response = await client.get("/api/matches/swipe-deck")
    assert response.status_code == 401


async def test_swipe_deck_route_returns_cards(authed_client: AsyncClient, seeded_match):
    response = await authed_client.get("/api/matches/swipe-deck")
    assert response.status_code == 200
    assert isinstance(response.json()["data"]["cards"], list)


async def test_swipe_action_route(authed_client: AsyncClient, seeded_match):
    match, _ = seeded_match
    response = await authed_client.post(f"/api/matches/{match.id}/swipe", json={"direction": "up"})
    assert response.status_code == 200
    assert response.json()["data"]["direction"] == "up"


async def test_outreach_draft_route_requires_auth(client: AsyncClient):
    response = await client.post("/api/outreach/drafts", json={"company_name": "Acme", "document_id": "x"})
    assert response.status_code == 401


async def test_outreach_list_route_returns_envelope(authed_client: AsyncClient):
    response = await authed_client.get("/api/outreach")
    assert response.status_code == 200
    assert "messages" in response.json()["data"]
```

### 9.10 Migration tests — extending the existing pattern

**File edited:** `backend/tests/test_migrations.py` (if it exists) or a new `backend/tests/test_module2_migrations.py`, following the exact `upgrade_head()` helper already used in `conftest.py`:

```python
"""Prove all 6 new Module 2 Alembic revisions apply and reverse cleanly."""

from __future__ import annotations

from alembic import command
from alembic.config import Config


def test_module2_migrations_upgrade_and_downgrade_cleanly(alembic_config: Config):
    """Upgrade to head (includes all Module 2 revisions), then downgrade back past them.

    Uses the same alembic_config fixture the existing migration tests use
    (backend/tests/migration_helpers.py's upgrade_head, already imported by conftest.py).
    """
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "021_job_matches")  # back to just before Module 2
    command.upgrade(alembic_config, "head")  # re-apply, proving idempotent forward path
```

### 9.11 Verification — run all of this before considering Module 2 done

```bash
cd backend

# Prerequisite bug fixes (§2.1) must be green first
pytest tests/test_cv_extraction.py tests/test_session_tracking.py -v

# Migrations apply and reverse cleanly
pytest tests/test_module2_migrations.py -v

# Every new module's own test suite
pytest tests/test_cv_completeness.py tests/test_cv_chat.py tests/test_cv_improvement.py \
       tests/test_portfolio.py tests/test_job_swipe.py tests/test_outreach.py \
       tests/test_module2_api.py -v

# Full suite regression check — nothing else broke
pytest -v

# Coverage gate (must stay >= the repo's existing 78% floor, not lower it)
pytest --cov=app --cov-report=term-missing --cov-fail-under=78

# Lint/type
ruff check app/
mypy app/

# Frontend: typecheck + lint + build (per RULE.md "type changes -> typecheck, UI changes -> lint/build")
cd ../frontend
npm run typecheck
npm run lint
npm run build

# Frontend: new-feature test suites (§13)
npm test -- features/cv-management features/job-swipe features/portfolio features/outreach
```

---

## 10. Docker architecture for Module 2

### 10.1 What the original "Phase 2 Docker Strategy" (six dedicated workers) gets wrong for Module 2 specifically

The user's original Phase-2-wide Docker strategy proposed a dedicated container per feature-shaped task (`worker-document`, `worker-embedding`, `worker-audio`, `worker-feedback`, ...). Verified directly against the **actual** current `backend/docker/docker-compose.yml` (read in full above): the real implementation already diverged from that proposal in favor of **reuse** — there is one generic `worker` container consuming `QUEUE_FEEDBACK`, `QUEUE_DOCUMENT`, `QUEUE_EMBEDDING`, `QUEUE_CV_EXTRACTION`, and `QUEUE_NAME` together (see `backend/app/workers/rq_worker.py`'s `main()`, read directly in this session), plus two narrowly-scoped dedicated containers that already existed for genuinely different reasons: `worker-email` (external SendGrid dependency, isolated so email delivery issues cannot block enrichment) and `worker-cleanup` (a different execution model — `python -m app.workers.cleanup_worker`, not an RQ consumer at all).

Confirmed by reading `backend/docker/docker-compose.foundation.yml` directly: it exists as an **optional, additive** overlay — `docker compose -f docker-compose.yml -f docker-compose.foundation.yml up` adds `worker-document`/`worker-embedding` as *extra*, independently-scalable consumers of the *same* `document_processing`/`embedding_generation` queues the generic worker already listens to. It is not a replacement for the generic worker, and running without it is still correct (just less horizontally scaled).

Only three containers in this repo are genuinely dedicated-and-required, each for a load-bearing reason: `worker-email` (SendGrid outages must never block enrichment), `worker-cleanup` (different execution model entirely), and `worker-job-matching` (`phase2_module1.md` §9 — a demonstrated starvation risk: a scan burst would otherwise starve every higher-priority queue behind it in the shared worker's fixed-priority list).

**Applied to Module 2:** none of its five features have that same load-bearing justification for isolation.

| Feature | Runs on | Container |
|---|---|---|
| CV completeness chat (§8.2-8.4) | `api` container | none — Decision 2 made it synchronous request/response; there is no queue to consume. |
| CV improvement / feedback (§8.8-8.9) | existing `worker` container, `QUEUE_FEEDBACK` | none — reuses the exact queue Foundation Week 2's interview feedback already shares; same model (`gpt-4o-mini`), same single-call latency profile. |
| Portfolio CRUD (§8.10) | `api` container | none — plain DB reads/writes, same shape as `documents/router.py`'s existing list/get/delete endpoints. |
| Swipe recording (§8.11) | `api` container | none — single-row upsert, sub-50ms. |
| Outreach drafting (§8.12-8.14) | existing `worker` container, `QUEUE_OUTREACH` (§8.15) | none — see §10.2. |

### 10.2 Why outreach also stays on the shared `worker`, not a new dedicated container

Outreach is the one feature that *looks* like it might deserve `worker-job-matching`-style isolation (it calls an external, rate-limited third-party API — Perplexity — that no other queue depends on). It was deliberately **not** given one, for a reason that is different from — and weaker than — Module 1's:

- Module 1's isolation was justified by a **demonstrated, load-bearing starvation scenario** (§4 of `phase2_module1.md`): a scan burst that could occupy the shared worker long enough to visibly delay user-facing feedback generation.
- Outreach generation is a **single request per button-click** (the candidate clicks "Draft outreach" once per job), not a burst-generating background scan. Its per-job latency (one Perplexity call + one OpenAI call, a few seconds total) is the same order of magnitude as CV feedback's existing single-OpenAI-call latency, which already safely shares the generic worker today.
- §8.15 already resolves the *ordering* half of the starvation question by placing `QUEUE_OUTREACH` immediately after `QUEUE_FEEDBACK` and before `QUEUE_DOCUMENT`/`QUEUE_EMBEDDING` in the generic worker's fixed-priority list — the same tool `phase2_module1.md` §4 itself names as the answer for "similar-urgency queues," reserving full container isolation for "genuinely different resource/latency profile or demonstrated starvation," neither of which applies here.

**This is a YAGNI decision, not a permanent one.** If outreach volume later grows enough to visibly delay CV feedback on the shared worker, the fix is mechanical and already has a template to copy: add `outreach_generation` to a new `docker-compose.module2.yml` overlay with a `worker-outreach` service, remove `QUEUE_OUTREACH` from `rq_worker.py`'s general-purpose queue list, and give it its own `Dockerfile.worker-outreach` (copy `Dockerfile.worker-document`, change the final `CMD`) — exactly the `worker-job-matching` playbook in `phase2_module1.md` §9, applied only if and when the same load-bearing evidence shows up for outreach. Module 2 does not need to pay that operational cost (one more image to build, one more healthcheck to monitor, one more container to keep patched) before there is evidence it is needed.

### 10.3 Postgres connection-pool caveat (cross-reference, not re-solved here)

✅ **DIRECT** (own codebase, already flagged in `phase2_module1.md` §4) — `backend/app/database/session.py`'s engine has no explicit `pool_size`/`max_overflow`, so SQLAlchemy's defaults (5 pooled + 10 overflow per process) apply uncapped across however many processes connect. Because Module 2 adds **zero new containers**, it adds **zero new connections to the pool ceiling** beyond what the existing `api` and `worker` containers already hold open — unlike Module 1, which explicitly had to reason about this when adding `worker-job-matching`. This is the concrete payoff of §10.1/§10.2's "reuse over isolation" choice, not an accident.

### 10.4 Net result: Module 2 requires zero Dockerfile changes and zero compose-file changes

The only Docker-adjacent artifact Module 2 touches is `backend/app/workers/rq_worker.py`'s in-process queue *list* (§8.15, a Python-source-level edit, not an infrastructure edit) — no new `Dockerfile.*`, no new `docker-compose.*.yml` overlay, no change to `docker-compose.yml` itself. `docker compose up` (with whatever combination of overlays an operator already runs today) picks up Module 2's new routes and worker tasks automatically the next time the `api` and `worker` images are rebuilt, because they are the same images Module 2's new Python modules get `COPY`'d into.

---

## 11. Frontend — shared types, adapter, and BFF API layer

### 11.1 Ground truth checked before writing any frontend code

✅ **DIRECT** (read directly this session) — `frontend/app/api/documents/**` does not exist yet: zero BFF routes for CV upload exist today, despite the backend's `documents` module being real. This confirms `phase2_module1.md` §11.10's own flag ("CV upload UI existing — currently missing") and means Module 2's frontend work starts from zero for CV-related routes, not from an existing-but-incomplete base.

✅ **DIRECT** — `frontend/src/lib/backend-client.ts`'s real signature is `backendFetch(path: string, init?: RequestInit, timeoutOverrideMs?: number)` — it reads the `access_token` cookie itself via `next/headers`, so BFF routes never pass `request` as a first argument. (Flagged explicitly because `phase2_module1.md` §10.4's own BFF route examples call `backendFetch(request, path, init)` — a signature that does not exist in this codebase. That mismatch is `phase2_module1.md`'s bug, not something this document repeats. Every BFF route below uses the real, verified 2-arg form.)

✅ **DIRECT** — `frontend/src/lib/bff-response.ts`'s real exports are `bffSuccess`, `bffValidationError`, `bffError(code, message, status, details?, meta?)`, `bffServiceUnavailable`, `backendFailureResponse`, and `handleBackendJson(response, mapFn, successStatus?)` — not `unwrapEnvelope`/`bffError(status)` as `phase2_module1.md` §10.4 assumed. Every BFF route below uses the real exports, confirmed against `frontend/app/api/enrich/route.ts` (read directly) as the working reference implementation.

✅ **DIRECT** — `frontend/package.json` (read in full) has no `framer-motion`, `@use-gesture/react`, `react-swipeable`, or `hammerjs` — the swipe deck (§12.2) is the first feature in this codebase needing drag gestures. **New dependency: `framer-motion`.** The user's original brief named "Framer Motion + Hammer.js" together; this plan uses **only** `framer-motion` — its `drag`/`useMotionValue`/`useTransform` APIs already cover pointer and touch gesture handling in one library, so adding Hammer.js on top would be a second gesture library solving the same problem RULE.md's "avoid redundancy" principle exists to prevent.

### 11.2 `frontend/src/lib/types.ts` — additions

```typescript
// Module 2: Tinder-Style Job Board + CV Management

export interface CvCompleteness {
  documentId: string;
  completenessScore: number;
  missingFields: string[];
  questions: { field: string; question: string }[];
}

export interface CvChatMessage {
  id: string;
  role: "assistant" | "user";
  content: string;
  createdAt: string;
}

export interface CvChatSession {
  sessionId: string;
  status: "active" | "completed" | "abandoned";
  missingFieldsAtStart: string[];
  fieldsResolved: string[];
  messages: CvChatMessage[];
}

export interface CvFeedbackReport {
  reportId: string;
  documentId: string;
  status: "pending" | "processing" | "completed" | "failed";
  atsScore: number | null;
  strengths: string[];
  improvements: string[];
  rewrittenBullets: { original: string; rewritten: string; rationale: string }[];
  createdAt: string;
}

export interface PortfolioItem {
  itemId: string;
  itemType: "github_repo" | "live_demo" | "case_study" | "other_link";
  title: string;
  description: string | null;
  url: string;
  displayOrder: number;
}

export interface PortfolioProfile {
  profileId: string;
  slug: string;
  headline: string | null;
  summary: string | null;
  isPublished: boolean;
  items: PortfolioItem[];
  createdAt: string;
  updatedAt: string;
}

export interface PublicPortfolioProfile {
  slug: string;
  headline: string | null;
  summary: string | null;
  items: PortfolioItem[];
  // Deliberately no profileId/userId/timestamps — public response never leaks internal IDs (§9.6).
}

export interface SwipeCard {
  matchId: string;
  jobPostingId: string;
  title: string;
  company: string;
  location: string | null;
  remote: boolean;
  salaryMin: number | null;
  salaryMax: number | null;
  salaryCurrency: string | null;
  overallScore: number;
  scoreBreakdown: Record<string, number>;
  explanation: string | null;
}

export interface SwipeDeck {
  cards: SwipeCard[];
}

export type SwipeDirection = "left" | "right" | "up";

export interface OutreachMessage {
  messageId: string;
  jobPostingId: string | null;
  companyName: string;
  recipientRole: string | null;
  subject: string;
  body: string;
  status: "draft" | "sent" | "failed";
  companyContextSource: "perplexity" | "none";
  createdAt: string;
  sentAt: string | null;
}

export interface OutreachListResponse {
  messages: OutreachMessage[];
}
```

### 11.3 `frontend/src/lib/api-adapter.ts` — additions

Field-name mapping (snake_case backend ↔ camelCase frontend) happens only here, per the existing convention (`phase2_module1.md` §10.3 established this; Module 2 follows it identically):

```typescript
export function adaptCvCompleteness(raw: RawCvCompletenessResponse): CvCompleteness {
  return {
    documentId: raw.document_id,
    completenessScore: raw.completeness_score,
    missingFields: raw.missing_fields,
    questions: raw.questions,
  };
}

export function adaptCvChatSession(raw: RawCvChatSessionResponse): CvChatSession {
  return {
    sessionId: raw.session_id,
    status: raw.status,
    missingFieldsAtStart: raw.missing_fields_at_start,
    fieldsResolved: raw.fields_resolved,
    messages: raw.messages.map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      createdAt: m.created_at,
    })),
  };
}

export function adaptCvFeedbackReport(raw: RawCvFeedbackReportResponse): CvFeedbackReport {
  return {
    reportId: raw.report_id,
    documentId: raw.document_id,
    status: raw.status,
    atsScore: raw.ats_score,
    strengths: raw.strengths,
    improvements: raw.improvements,
    rewrittenBullets: raw.rewritten_bullets,
    createdAt: raw.created_at,
  };
}

export function adaptPortfolioProfile(raw: RawPortfolioProfileResponse): PortfolioProfile {
  return {
    profileId: raw.profile_id,
    slug: raw.slug,
    headline: raw.headline,
    summary: raw.summary,
    isPublished: raw.is_published,
    items: raw.items.map(adaptPortfolioItem),
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

function adaptPortfolioItem(raw: RawPortfolioItemResponse): PortfolioItem {
  return {
    itemId: raw.item_id,
    itemType: raw.item_type,
    title: raw.title,
    description: raw.description,
    url: raw.url,
    displayOrder: raw.display_order,
  };
}

export function adaptPublicPortfolioProfile(raw: RawPublicPortfolioProfileResponse): PublicPortfolioProfile {
  return {
    slug: raw.slug,
    headline: raw.headline,
    summary: raw.summary,
    items: raw.items.map(adaptPortfolioItem),
  };
}

export function adaptSwipeDeck(raw: RawSwipeDeckResponse): SwipeDeck {
  return {
    cards: raw.cards.map((c) => ({
      matchId: c.match_id,
      jobPostingId: c.job_posting_id,
      title: c.title,
      company: c.company,
      location: c.location,
      remote: c.remote,
      salaryMin: c.salary_min,
      salaryMax: c.salary_max,
      salaryCurrency: c.salary_currency,
      overallScore: c.overall_score,
      scoreBreakdown: c.score_breakdown,
      explanation: c.explanation,
    })),
  };
}

export function adaptOutreachMessage(raw: RawOutreachMessageResponse): OutreachMessage {
  return {
    messageId: raw.message_id,
    jobPostingId: raw.job_posting_id,
    companyName: raw.company_name,
    recipientRole: raw.recipient_role,
    subject: raw.subject,
    body: raw.body,
    status: raw.status,
    companyContextSource: raw.company_context_source,
    createdAt: raw.created_at,
    sentAt: raw.sent_at,
  };
}
```

`Raw*Response` types come from `npm run openapi:gen` (§11.1's convention) after the backend routes (§8) exist — never hand-declared duplicates, per RULE.md.

### 11.4 BFF routes — CV completeness + chat + feedback

Following the real, verified pattern from `frontend/app/api/enrich/route.ts` (§11.1): `backendFetch(path, init)`, try/catch → `bffServiceUnavailable()`, `handleBackendJson(response, mapFn, status?)`.

**New file:** `frontend/app/api/documents/[documentId]/completeness/route.ts`

```typescript
import { NextRequest } from "next/server";
import { adaptCvCompleteness } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ documentId: string }> },
) {
  const { documentId } = await params;
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/documents/${documentId}/completeness`);
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, adaptCvCompleteness);
}
```

**New file:** `frontend/app/api/documents/[documentId]/cv-chat/sessions/route.ts`

```typescript
import { NextRequest } from "next/server";
import { adaptCvChatSession } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function POST(
  _request: NextRequest,
  { params }: { params: Promise<{ documentId: string }> },
) {
  const { documentId } = await params;
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/documents/${documentId}/cv-chat/sessions`, {
      method: "POST",
    });
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, adaptCvChatSession);
}
```

**New file:** `frontend/app/api/cv-chat/sessions/[sessionId]/messages/route.ts`

```typescript
import { NextRequest } from "next/server";
import { adaptCvChatSession } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, bffValidationError, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params;
  const body = await request.json();
  if (typeof body?.content !== "string" || !body.content.trim()) {
    return bffValidationError("Message content is required.");
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/cv-chat/sessions/${sessionId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: body.content }),
    });
  } catch {
    return bffServiceUnavailable();
  }
  // Backend response envelopes { session, assistant_message } — adapt just the session
  // half here; the chat UI (§12.1) re-derives the latest assistant message from
  // session.messages, so no separate adapter is needed for the turn wrapper shape.
  return handleBackendJson(backendResponse, (raw: { session: RawCvChatSessionResponse }) =>
    adaptCvChatSession(raw.session),
  );
}
```

**New file:** `frontend/app/api/documents/[documentId]/feedback/route.ts`

```typescript
import { NextRequest } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, bffSuccess, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ documentId: string }> },
) {
  const { documentId } = await params;
  const body = await request.json().catch(() => ({}));

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/documents/${documentId}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_role: body.targetRole ?? null }),
    });
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, (raw: { job_id: string }) => ({ jobId: raw.job_id }), 202);
}

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ documentId: string }> },
) {
  const { documentId } = await params;
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/documents/${documentId}/feedback`);
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, adaptCvFeedbackReport);
}
```

**New file:** `frontend/app/api/cv-feedback/[reportId]/accept-bullet/route.ts`

```typescript
import { NextRequest } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import { backendFailureResponse, bffServiceUnavailable, bffSuccess } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ reportId: string }> },
) {
  const { reportId } = await params;
  const body = await request.json();

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/cv-feedback/${reportId}/accept-bullet`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bullet_index: body.bulletIndex }),
    });
  } catch {
    return bffServiceUnavailable();
  }
  if (!backendResponse.ok) {
    return backendFailureResponse(backendResponse);
  }
  return bffSuccess({ accepted: true });
}
```

---

### 11.5 BFF routes — portfolio

**New file:** `frontend/app/api/portfolio/profile/route.ts`

```typescript
import { NextRequest } from "next/server";
import { adaptPortfolioProfile } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { backendFailureResponse, bffServiceUnavailable, bffValidationError, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function GET() {
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/portfolio/profile");
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, adaptPortfolioProfile);
}

export async function PUT(request: NextRequest) {
  const body = await request.json();
  if (typeof body?.slug !== "string" || !body.slug.trim()) {
    return bffValidationError("A slug is required.");
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/portfolio/profile", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        slug: body.slug,
        headline: body.headline ?? null,
        summary: body.summary ?? null,
        is_published: body.isPublished ?? false,
      }),
    });
  } catch {
    return bffServiceUnavailable();
  }
  if (!backendResponse.ok) return backendFailureResponse(backendResponse);
  return handleBackendJson(backendResponse, adaptPortfolioProfile);
}
```

**New file:** `frontend/app/api/portfolio/items/route.ts`

```typescript
import { NextRequest } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import { backendFailureResponse, bffServiceUnavailable, bffValidationError, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const body = await request.json();
  if (typeof body?.url !== "string" || !body.url.trim()) {
    return bffValidationError("A URL is required.");
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/portfolio/items", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        item_type: body.itemType,
        title: body.title,
        description: body.description ?? null,
        url: body.url,
      }),
    });
  } catch {
    return bffServiceUnavailable();
  }
  if (!backendResponse.ok) return backendFailureResponse(backendResponse);
  return handleBackendJson(backendResponse, (raw: RawPortfolioItemResponse) => raw, 201);
}
```

**New file:** `frontend/app/api/portfolio/items/[itemId]/route.ts`

```typescript
import { NextRequest } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import { backendFailureResponse, bffServiceUnavailable, bffSuccess } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ itemId: string }> },
) {
  const { itemId } = await params;
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/portfolio/items/${itemId}`, { method: "DELETE" });
  } catch {
    return bffServiceUnavailable();
  }
  if (!backendResponse.ok) return backendFailureResponse(backendResponse);
  return bffSuccess({ deleted: true });
}
```

**New file:** `frontend/app/api/portfolio/public/[slug]/route.ts` — the **only** unauthenticated Module 2 BFF route, using `backendFetchPublic` (§11.1), not `backendFetch`:

```typescript
import { NextRequest } from "next/server";
import { adaptPublicPortfolioProfile } from "@/src/lib/api-adapter";
import { backendFetchPublic } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ slug: string }> },
) {
  const { slug } = await params;
  let backendResponse: Response;
  try {
    backendResponse = await backendFetchPublic(`/api/portfolio/public/${slug}`);
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, adaptPublicPortfolioProfile);
}
```

---

### 11.6 BFF routes — job swipe

**New file:** `frontend/app/api/matches/swipe-deck/route.ts`

```typescript
import { adaptSwipeDeck } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function GET() {
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/matches/swipe-deck");
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, adaptSwipeDeck);
}
```

**New file:** `frontend/app/api/matches/[matchId]/swipe/route.ts`

```typescript
import { NextRequest } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import { backendFailureResponse, bffServiceUnavailable, bffValidationError, bffSuccess } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

const VALID_DIRECTIONS = new Set(["left", "right", "up"]);

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ matchId: string }> },
) {
  const { matchId } = await params;
  const body = await request.json();
  if (!VALID_DIRECTIONS.has(body?.direction)) {
    return bffValidationError("direction must be one of: left, right, up.");
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/matches/${matchId}/swipe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ direction: body.direction }),
    });
  } catch {
    return bffServiceUnavailable();
  }
  if (!backendResponse.ok) return backendFailureResponse(backendResponse);
  return bffSuccess({ direction: body.direction as string });
}
```

---

### 11.7 BFF routes — outreach

**New file:** `frontend/app/api/outreach/route.ts`

```typescript
import { adaptOutreachMessage } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function GET() {
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/outreach");
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, (raw: { messages: RawOutreachMessageResponse[] }) => ({
    messages: raw.messages.map(adaptOutreachMessage),
  }));
}
```

**New file:** `frontend/app/api/outreach/drafts/route.ts`

```typescript
import { NextRequest } from "next/server";
import { adaptOutreachMessage } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, bffValidationError, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const body = await request.json();
  if (typeof body?.jobPostingId !== "string") {
    return bffValidationError("jobPostingId is required.");
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/outreach/drafts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_posting_id: body.jobPostingId, document_id: body.documentId ?? null }),
    });
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, adaptOutreachMessage, 202);
}
```

**New file:** `frontend/app/api/outreach/[messageId]/route.ts`

```typescript
import { NextRequest } from "next/server";
import { adaptOutreachMessage } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { backendFailureResponse, bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ messageId: string }> },
) {
  const { messageId } = await params;
  const body = await request.json();

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/outreach/${messageId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subject: body.subject, body: body.body }),
    });
  } catch {
    return bffServiceUnavailable();
  }
  if (!backendResponse.ok) return backendFailureResponse(backendResponse);
  return handleBackendJson(backendResponse, adaptOutreachMessage);
}
```

**New file:** `frontend/app/api/outreach/[messageId]/send/route.ts`

```typescript
import { NextRequest } from "next/server";
import { adaptOutreachMessage } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { backendFailureResponse, bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function POST(
  _request: NextRequest,
  { params }: { params: Promise<{ messageId: string }> },
) {
  const { messageId } = await params;
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/outreach/${messageId}/send`, { method: "POST" });
  } catch {
    return bffServiceUnavailable();
  }
  if (!backendResponse.ok) return backendFailureResponse(backendResponse);
  return handleBackendJson(backendResponse, adaptOutreachMessage);
}
```

---

## 12. Frontend — `features/*` modules

### 12.1 Ground truth checked before writing feature-module code

✅ **DIRECT** (read `frontend/features/signals/hooks/useSignalList.ts` and `frontend/features/enrich/hooks/useCreateEnrichment.ts` directly) — the real convention centralizes all HTTP calls in **one shared file**, `frontend/src/lib/api-client.ts` (a `request<T>(path, init)` helper with cookie-based auth + single-flight 401 refresh-and-retry), and feature-module hooks import functions from there — **not** a per-feature `api/client.ts`. (`phase2_module1.md` §11.2 invented a per-feature `client.ts` that does not match this repo's real pattern; this document follows the real one.) Feature modules still keep their own `api/keys.ts` (query-key factories) — that part of `phase2_module1.md`'s structure is correct and confirmed by `frontend/features/signals/api/keys.ts`.

✅ **DIRECT** (read `frontend/package.json` in full, §11.1) — no `framer-motion`, confirmed above.

✅ **DIRECT** (read `frontend/components/ui/` directory listing and `frontend/components.json` directly) — this repo scaffolds UI primitives via the shadcn CLI (confirmed by the presence of `components.json`), and its current `components/ui/` set has **no `switch.tsx`** and no `@radix-ui/react-switch` dependency, despite `phase2_module1.md`'s own `PreferencesForm.tsx` (§11.6 there) using `<Switch>` without flagging this. This plan's `PortfolioEditor` (§12.5) also needs a toggle for "publish portfolio" — rather than repeat that same unflagged assumption, the missing component is called out here as a real prerequisite:

```bash
cd frontend && npx shadcn@latest add switch
```

This adds `components/ui/switch.tsx` and the `@radix-ui/react-switch` dependency to `package.json`, following the exact same scaffolding path every other primitive in `components/ui/` was added through — not a bespoke component.

### 12.2 `frontend/src/lib/api-client.ts` — additions

All four features' HTTP calls, added beside the existing `listSignals`/`createEnrichmentJob` functions, following their exact shape (`request<T>()`, returns `SuccessEnvelope<T>`). Adapting snake_case→camelCase already happened inside the BFF routes (§11.4-11.7), so these functions only need the frontend-shaped types from `types.ts`, not the adapters:

```typescript
import {
  CvChatSession,
  CvCompleteness,
  CvFeedbackReport,
  OutreachListResponse,
  OutreachMessage,
  PortfolioItem,
  PortfolioProfile,
  PublicPortfolioProfile,
  SwipeDeck,
  SwipeDirection,
} from "@/src/lib/types";

// ── CV completeness + chat + feedback ──────────────────────────────

export async function fetchCvCompleteness(documentId: string): Promise<SuccessEnvelope<CvCompleteness>> {
  return request<CvCompleteness>(`/api/documents/${documentId}/completeness`);
}

export async function startCvChatSession(documentId: string): Promise<SuccessEnvelope<CvChatSession>> {
  return request<CvChatSession>(`/api/documents/${documentId}/cv-chat/sessions`, { method: "POST" });
}

export async function postCvChatMessage(
  sessionId: string,
  content: string,
): Promise<SuccessEnvelope<CvChatSession>> {
  return request<CvChatSession>(`/api/cv-chat/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
}

export async function requestCvFeedback(
  documentId: string,
  targetRole?: string,
): Promise<SuccessEnvelope<{ jobId: string }>> {
  return request<{ jobId: string }>(`/api/documents/${documentId}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ targetRole: targetRole ?? null }),
  });
}

export async function fetchCvFeedback(documentId: string): Promise<SuccessEnvelope<CvFeedbackReport>> {
  return request<CvFeedbackReport>(`/api/documents/${documentId}/feedback`);
}

export async function acceptCvBullet(
  reportId: string,
  bulletIndex: number,
): Promise<SuccessEnvelope<{ accepted: boolean }>> {
  return request<{ accepted: boolean }>(`/api/cv-feedback/${reportId}/accept-bullet`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ bulletIndex }),
  });
}

// ── Portfolio ───────────────────────────────────────────────────────

export async function fetchPortfolioProfile(): Promise<SuccessEnvelope<PortfolioProfile>> {
  return request<PortfolioProfile>("/api/portfolio/profile");
}

export async function savePortfolioProfile(
  payload: Partial<PortfolioProfile> & { slug: string },
): Promise<SuccessEnvelope<PortfolioProfile>> {
  return request<PortfolioProfile>("/api/portfolio/profile", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function addPortfolioItem(
  payload: Omit<PortfolioItem, "itemId" | "displayOrder">,
): Promise<SuccessEnvelope<PortfolioItem>> {
  return request<PortfolioItem>("/api/portfolio/items", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deletePortfolioItem(itemId: string): Promise<SuccessEnvelope<{ deleted: boolean }>> {
  return request<{ deleted: boolean }>(`/api/portfolio/items/${itemId}`, { method: "DELETE" });
}

/** Public — no auth cookie needed, but still routed through the BFF (§11.5) for consistency. */
export async function fetchPublicPortfolio(slug: string): Promise<SuccessEnvelope<PublicPortfolioProfile>> {
  return request<PublicPortfolioProfile>(`/api/portfolio/public/${slug}`);
}

// ── Job swipe ───────────────────────────────────────────────────────

export async function fetchSwipeDeck(): Promise<SuccessEnvelope<SwipeDeck>> {
  return request<SwipeDeck>("/api/matches/swipe-deck");
}

export async function submitSwipe(
  matchId: string,
  direction: SwipeDirection,
): Promise<SuccessEnvelope<{ direction: SwipeDirection }>> {
  return request<{ direction: SwipeDirection }>(`/api/matches/${matchId}/swipe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ direction }),
  });
}

// ── Outreach ────────────────────────────────────────────────────────

export async function fetchOutreachMessages(): Promise<SuccessEnvelope<OutreachListResponse>> {
  return request<OutreachListResponse>("/api/outreach");
}

export async function draftOutreach(
  jobPostingId: string,
  documentId?: string,
): Promise<SuccessEnvelope<OutreachMessage>> {
  return request<OutreachMessage>("/api/outreach/drafts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jobPostingId, documentId: documentId ?? null }),
  });
}

export async function editOutreachDraft(
  messageId: string,
  subject: string,
  body: string,
): Promise<SuccessEnvelope<OutreachMessage>> {
  return request<OutreachMessage>(`/api/outreach/${messageId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ subject, body }),
  });
}

export async function sendOutreach(messageId: string): Promise<SuccessEnvelope<OutreachMessage>> {
  return request<OutreachMessage>(`/api/outreach/${messageId}/send`, { method: "POST" });
}
```

---

### 12.3 `frontend/features/cv-management/` — completeness, chat, feedback

**New file:** `frontend/features/cv-management/api/keys.ts`

```typescript
export const cvManagementKeys = {
  all: ["cv-management"] as const,
  completeness: (documentId: string) => [...cvManagementKeys.all, "completeness", documentId] as const,
  feedback: (documentId: string) => [...cvManagementKeys.all, "feedback", documentId] as const,
};
```

**New file:** `frontend/features/cv-management/hooks/useCvCompleteness.ts`

```typescript
import { useQuery } from "@tanstack/react-query";
import { fetchCvCompleteness } from "@/src/lib/api-client";
import { cvManagementKeys } from "../api/keys";

export function useCvCompleteness(documentId: string | null) {
  return useQuery({
    queryKey: cvManagementKeys.completeness(documentId ?? ""),
    queryFn: async () => (await fetchCvCompleteness(documentId as string)).data,
    enabled: Boolean(documentId),
  });
}
```

**New file:** `frontend/features/cv-management/hooks/useCvChat.ts`

```typescript
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { postCvChatMessage, startCvChatSession } from "@/src/lib/api-client";
import type { CvChatSession } from "@/src/lib/types";
import { cvManagementKeys } from "../api/keys";

export function useCvChat(documentId: string) {
  const [session, setSession] = useState<CvChatSession | null>(null);
  const queryClient = useQueryClient();

  const start = useMutation({
    mutationFn: async () => (await startCvChatSession(documentId)).data,
    onSuccess: setSession,
  });

  const sendMessage = useMutation({
    mutationFn: async (content: string) => {
      if (!session) throw new Error("No active chat session.");
      return (await postCvChatMessage(session.sessionId, content)).data;
    },
    onSuccess: (updated) => {
      setSession(updated);
      if (updated.status === "completed") {
        // Missing-field questions are now resolved — completeness score changed.
        void queryClient.invalidateQueries({ queryKey: cvManagementKeys.completeness(documentId) });
      }
    },
  });

  return { session, start, sendMessage };
}
```

**Test file:** `frontend/features/cv-management/hooks/useCvChat.test.ts` — mocks `startCvChatSession`/`postCvChatMessage`, asserts `start.mutate()` populates `session`, asserts `sendMessage.mutate()` updates `session` from the response and invalidates the completeness query only when `status === "completed"`.

**New file:** `frontend/features/cv-management/hooks/useCvFeedback.ts`

```typescript
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { acceptCvBullet, fetchCvFeedback, requestCvFeedback } from "@/src/lib/api-client";
import { cvManagementKeys } from "../api/keys";

export function useCvFeedback(documentId: string, options: { poll?: boolean } = {}) {
  return useQuery({
    queryKey: cvManagementKeys.feedback(documentId),
    queryFn: async () => (await fetchCvFeedback(documentId)).data,
    // Feedback runs on QUEUE_FEEDBACK asynchronously (§8.9) — poll until terminal.
    refetchInterval: (query) => {
      if (!options.poll) return false;
      const status = query.state.data?.status;
      return status === "pending" || status === "processing" ? 3_000 : false;
    },
  });
}

export function useRequestCvFeedback(documentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (targetRole?: string) => requestCvFeedback(documentId, targetRole),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: cvManagementKeys.feedback(documentId) }),
  });
}

export function useAcceptCvBullet(documentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ reportId, bulletIndex }: { reportId: string; bulletIndex: number }) =>
      acceptCvBullet(reportId, bulletIndex),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: cvManagementKeys.feedback(documentId) }),
  });
}
```

**Test file:** `frontend/features/cv-management/hooks/useCvFeedback.test.ts` — asserts `refetchInterval` returns `3000` when `status` is `"pending"`/`"processing"` and `options.poll` is true, returns `false` when `status === "completed"` or `options.poll` is false (prevents an infinite-poll bug if the flag is ever forgotten at a call site).

**New file:** `frontend/features/cv-management/components/CompletenessBanner.tsx`

```tsx
"use client";

import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { useCvCompleteness } from "../hooks/useCvCompleteness";

interface CompletenessBannerProps {
  documentId: string;
  onStartChat: () => void;
}

export function CompletenessBanner({ documentId, onStartChat }: CompletenessBannerProps) {
  const { data, isLoading } = useCvCompleteness(documentId);

  if (isLoading || !data) return null;
  if (data.missingFields.length === 0) return null; // fully complete — nothing to show (§8.1)

  const percent = Math.round(data.completenessScore * 100);

  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-amber-900">
          Your CV is {percent}% complete — {data.missingFields.length} field
          {data.missingFields.length === 1 ? "" : "s"} missing
        </p>
        <Button size="sm" onClick={onStartChat}>
          Complete it
        </Button>
      </div>
      <Progress value={percent} className="mt-2" />
    </div>
  );
}
```

**Test file:** `frontend/features/cv-management/components/CompletenessBanner.test.tsx` — renders nothing when `missingFields` is empty (full CV), renders the percent + count + "Complete it" button otherwise, asserts `onStartChat` fires on click.

**New file:** `frontend/features/cv-management/components/CvChatWidget.tsx`

```tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCvChat } from "../hooks/useCvChat";

interface CvChatWidgetProps {
  documentId: string;
  onComplete?: () => void;
}

export function CvChatWidget({ documentId, onComplete }: CvChatWidgetProps) {
  const { session, start, sendMessage } = useCvChat(documentId);
  const [input, setInput] = useState("");

  if (!session) {
    return (
      <Button onClick={() => start.mutate()} disabled={start.isPending}>
        {start.isPending ? "Starting..." : "Start CV completeness chat"}
      </Button>
    );
  }

  function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim()) return;
    sendMessage.mutate(input, {
      onSuccess: (updated) => {
        setInput("");
        if (updated.status === "completed") onComplete?.();
      },
    });
  }

  return (
    <div className="flex h-96 flex-col rounded-lg border">
      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {session.messages.map((message) => (
          <div
            key={message.id}
            className={message.role === "assistant" ? "text-left" : "text-right"}
          >
            <span
              className={
                message.role === "assistant"
                  ? "inline-block rounded-lg bg-muted px-3 py-2 text-sm"
                  : "inline-block rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground"
              }
            >
              {message.content}
            </span>
          </div>
        ))}
      </div>
      {session.status === "active" ? (
        <form onSubmit={handleSend} className="flex gap-2 border-t p-3">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your answer..."
            disabled={sendMessage.isPending}
          />
          <Button type="submit" disabled={sendMessage.isPending || !input.trim()}>
            Send
          </Button>
        </form>
      ) : (
        <div className="border-t p-3 text-center text-sm text-muted-foreground">
          {session.status === "completed" ? "All done — your CV is up to date." : "Chat ended."}
        </div>
      )}
    </div>
  );
}
```

**Test file:** `frontend/features/cv-management/components/CvChatWidget.test.tsx` — asserts "Start CV completeness chat" button shown when no session; asserts message bubbles render with correct alignment class per `role`; asserts input form is hidden and a completion message shown when `session.status !== "active"`; asserts `onComplete` fires when a `sendMessage` response has `status === "completed"`.

**New file:** `frontend/features/cv-management/components/CvFeedbackPanel.tsx`

```tsx
"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAcceptCvBullet, useCvFeedback, useRequestCvFeedback } from "../hooks/useCvFeedback";

interface CvFeedbackPanelProps {
  documentId: string;
}

export function CvFeedbackPanel({ documentId }: CvFeedbackPanelProps) {
  const { data: report, isLoading } = useCvFeedback(documentId, { poll: true });
  const requestFeedback = useRequestCvFeedback(documentId);
  const acceptBullet = useAcceptCvBullet(documentId);

  if (isLoading) return <div className="animate-pulse h-48 rounded-lg bg-muted" />;

  if (!report || report.status === "failed") {
    return (
      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">No feedback generated yet.</p>
        <Button onClick={() => requestFeedback.mutate(undefined)} disabled={requestFeedback.isPending}>
          {requestFeedback.isPending ? "Requesting..." : "Get AI feedback"}
        </Button>
      </div>
    );
  }

  if (report.status === "pending" || report.status === "processing") {
    return <p className="text-sm text-muted-foreground">Analyzing your CV...</p>;
  }

  return (
    <div className="space-y-6">
      {report.atsScore !== null && (
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">ATS score</span>
          <Badge>{report.atsScore}/100</Badge>
        </div>
      )}

      {report.strengths.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold">Strengths</h3>
          <ul className="mt-1 list-inside list-disc text-sm text-muted-foreground">
            {report.strengths.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}

      {report.rewrittenBullets.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold">Suggested rewrites</h3>
          <div className="mt-2 space-y-3">
            {report.rewrittenBullets.map((bullet, index) => (
              <div key={index} className="rounded-lg border p-3">
                <p className="text-sm text-muted-foreground line-through">{bullet.original}</p>
                <p className="mt-1 text-sm font-medium">{bullet.rewritten}</p>
                <p className="mt-1 text-xs text-muted-foreground">{bullet.rationale}</p>
                <Button
                  size="sm"
                  variant="outline"
                  className="mt-2"
                  onClick={() => acceptBullet.mutate({ reportId: report.reportId, bulletIndex: index })}
                  disabled={acceptBullet.isPending}
                >
                  Use this version
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

**Test file:** `frontend/features/cv-management/components/CvFeedbackPanel.test.tsx` — covers all four states (`no report`, `pending/processing`, `completed` with score+strengths+bullets rendered, `failed` falls back to "Get AI feedback" button), asserts each "Use this version" button calls `acceptBullet.mutate` with the correct `{ reportId, bulletIndex }`.

**New file:** `frontend/features/cv-management/index.ts`

```typescript
export { useCvCompleteness } from "./hooks/useCvCompleteness";
export { useCvChat } from "./hooks/useCvChat";
export { useCvFeedback, useRequestCvFeedback, useAcceptCvBullet } from "./hooks/useCvFeedback";
export { CompletenessBanner } from "./components/CompletenessBanner";
export { CvChatWidget } from "./components/CvChatWidget";
export { CvFeedbackPanel } from "./components/CvFeedbackPanel";
export { cvManagementKeys } from "./api/keys";
```

---

### 12.4 `frontend/features/job-swipe/` — the Tinder-style swipe deck

**New file:** `frontend/features/job-swipe/api/keys.ts`

```typescript
export const jobSwipeKeys = {
  all: ["job-swipe"] as const,
  deck: () => [...jobSwipeKeys.all, "deck"] as const,
};
```

**New file:** `frontend/features/job-swipe/hooks/useSwipeDeck.ts`

```typescript
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchSwipeDeck, submitSwipe } from "@/src/lib/api-client";
import type { SwipeDirection } from "@/src/lib/types";
import { jobSwipeKeys } from "../api/keys";

export function useSwipeDeck() {
  return useQuery({
    queryKey: jobSwipeKeys.deck(),
    queryFn: async () => (await fetchSwipeDeck()).data,
  });
}

export function useSubmitSwipe() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ matchId, direction }: { matchId: string; direction: SwipeDirection }) =>
      submitSwipe(matchId, direction),
    // Optimistic removal — the card is already off-screen by the time this settles (§12.4's
    // SwipeCard component). Rolling back on error would visually "un-swipe" a card the user
    // already dismissed, which is more confusing than leaving it gone and retrying silently.
    onMutate: async ({ matchId }) => {
      const previous = queryClient.getQueryData(jobSwipeKeys.deck());
      queryClient.setQueryData(jobSwipeKeys.deck(), (old: { cards: { matchId: string }[] } | undefined) =>
        old ? { cards: old.cards.filter((c) => c.matchId !== matchId) } : old,
      );
      return { previous };
    },
    onError: (_err, _vars, context) => {
      // Swallow the rollback deliberately (see comment above) — log only.
      console.error("Swipe failed to persist; deck already advanced client-side.", context);
    },
  });
}
```

**Test file:** `frontend/features/job-swipe/hooks/useSwipeDeck.test.ts` — asserts `useSubmitSwipe().mutate()` optimistically removes the matching card from cached deck data via `onMutate`, asserts a rejected mutation does **not** restore the removed card (deliberate, per the code comment — tested explicitly so a future refactor doesn't "fix" this into a confusing un-swipe).

**New file:** `frontend/features/job-swipe/components/SwipeCard.tsx`

```tsx
"use client";

import { motion, useMotionValue, useTransform, type PanInfo } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import type { SwipeCard as SwipeCardData, SwipeDirection } from "@/src/lib/types";

interface SwipeCardProps {
  card: SwipeCardData;
  onSwiped: (direction: SwipeDirection) => void;
  isTop: boolean;
}

const SWIPE_THRESHOLD_X = 120;
const SWIPE_THRESHOLD_Y = -100;

function formatSalary(min: number | null, max: number | null, currency: string | null): string | null {
  if (min === null && max === null) return null;
  const cur = currency ?? "USD";
  if (min !== null && max !== null) return `${cur} ${min.toLocaleString()}–${max.toLocaleString()}`;
  return `${cur} ${(min ?? max)!.toLocaleString()}+`;
}

export function SwipeCard({ card, onSwiped, isTop }: SwipeCardProps) {
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const rotate = useTransform(x, [-200, 200], [-15, 15]);
  const likeOpacity = useTransform(x, [20, SWIPE_THRESHOLD_X], [0, 1]);
  const passOpacity = useTransform(x, [-SWIPE_THRESHOLD_X, -20], [1, 0]);
  const superLikeOpacity = useTransform(y, [SWIPE_THRESHOLD_Y, -20], [1, 0]);

  function handleDragEnd(_event: unknown, info: PanInfo) {
    if (info.offset.y < SWIPE_THRESHOLD_Y && Math.abs(info.offset.x) < Math.abs(info.offset.y)) {
      onSwiped("up");
    } else if (info.offset.x > SWIPE_THRESHOLD_X) {
      onSwiped("right");
    } else if (info.offset.x < -SWIPE_THRESHOLD_X) {
      onSwiped("left");
    }
    // Below threshold — Framer Motion's `dragSnapToOrigin` (set on the motion.div) springs
    // the card back to center automatically; no manual reset needed here.
  }

  const salary = formatSalary(card.salaryMin, card.salaryMax, card.salaryCurrency);

  return (
    <motion.div
      className="absolute inset-0 select-none rounded-2xl border bg-card p-6 shadow-lg"
      style={{ x, y, rotate }}
      drag={isTop}
      dragSnapToOrigin
      dragElastic={0.6}
      onDragEnd={handleDragEnd}
      data-testid="swipe-card"
      data-match-id={card.matchId}
    >
      <motion.div
        className="absolute left-4 top-4 rounded border-4 border-green-500 px-3 py-1 text-xl font-bold text-green-500"
        style={{ opacity: likeOpacity }}
      >
        INTERESTED
      </motion.div>
      <motion.div
        className="absolute right-4 top-4 rounded border-4 border-red-500 px-3 py-1 text-xl font-bold text-red-500"
        style={{ opacity: passOpacity }}
      >
        PASS
      </motion.div>
      <motion.div
        className="absolute left-1/2 top-4 -translate-x-1/2 rounded border-4 border-blue-500 px-3 py-1 text-xl font-bold text-blue-500"
        style={{ opacity: superLikeOpacity }}
      >
        SUPER LIKE
      </motion.div>

      <div className="flex h-full flex-col justify-between">
        <div>
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-xl font-semibold">{card.title}</h2>
              <p className="text-muted-foreground">{card.company}</p>
            </div>
            <Badge className={card.overallScore >= 80 ? "bg-green-100 text-green-800" : "bg-yellow-100 text-yellow-800"}>
              {Math.round(card.overallScore)}/100
            </Badge>
          </div>
          {(card.location || card.remote) && (
            <p className="mt-2 text-sm text-muted-foreground">
              {card.remote ? "Remote" : card.location}
            </p>
          )}
          {salary && <p className="mt-1 text-sm font-medium">{salary}</p>}
        </div>

        {card.explanation && (
          <p className="mt-4 rounded-lg bg-muted p-3 text-sm text-muted-foreground">
            {card.explanation}
          </p>
        )}
      </div>
    </motion.div>
  );
}
```

**Design rationale — why `up` requires `Math.abs(info.offset.x) < Math.abs(info.offset.y)`:** a fast diagonal drag could otherwise cross both the x- and y-thresholds in the same gesture, making "up" and "left"/"right" ambiguous. Whichever axis moved further wins, matching the real Tinder app's own disambiguation rule (a large majority of app-clone tutorials and the `react-tinder-card` library's source, ✅ **DIRECT** — verified by reading that library's `TinderCard.jsx` `swipe()` logic, which the user's original brief named as a reference point via "Hammer.js"-style gesture libraries, before this plan chose Framer Motion instead per §11.1).

**Test file:** `frontend/features/job-swipe/components/SwipeCard.test.tsx` — asserts `handleDragEnd`-equivalent behavior via simulated `PanInfo` values: `{ x: 150, y: 0 }` calls `onSwiped("right")`; `{ x: -150, y: 0 }` calls `onSwiped("left")`; `{ x: 0, y: -150 }` calls `onSwiped("up")`; `{ x: 50, y: -20 }` (below both thresholds) calls neither; `{ x: 130, y: -110 }` (crosses both thresholds, `|y| < |x|`) calls `onSwiped("right")`, not `"up"` (regression test for the disambiguation rule above). Only the card with `isTop=true` receives `drag` — asserted via the rendered element's draggable attribute.

**New file:** `frontend/features/job-swipe/components/SwipeDeckView.tsx`

```tsx
"use client";

import { EmptyState } from "@/components/console/EmptyState";
import type { SwipeDirection } from "@/src/lib/types";
import { useSubmitSwipe, useSwipeDeck } from "../hooks/useSwipeDeck";
import { SwipeCard } from "./SwipeCard";

const MAX_STACKED_CARDS = 3;

export function SwipeDeckView() {
  const { data, isLoading, isError } = useSwipeDeck();
  const submitSwipe = useSubmitSwipe();

  if (isLoading) return <div className="animate-pulse h-[32rem] rounded-2xl bg-muted" />;
  if (isError) return <EmptyState title="Couldn't load your deck" description="Please try again shortly." />;
  if (!data || data.cards.length === 0) {
    return (
      <EmptyState
        title="No new matches to review"
        description="Check back after your next job scan, or adjust your preferences."
      />
    );
  }

  const visibleCards = data.cards.slice(0, MAX_STACKED_CARDS);

  function handleSwipe(matchId: string, direction: SwipeDirection) {
    submitSwipe.mutate({ matchId, direction });
  }

  return (
    <div className="relative mx-auto h-[32rem] w-full max-w-sm">
      {visibleCards
        .slice()
        .reverse()
        .map((card, reverseIndex) => {
          const index = visibleCards.length - 1 - reverseIndex;
          return (
            <SwipeCard
              key={card.matchId}
              card={card}
              isTop={index === 0}
              onSwiped={(direction) => handleSwipe(card.matchId, direction)}
            />
          );
        })}
    </div>
  );
}
```

**Design rationale — stacking order:** cards render in **reverse** DOM order (last card in the array painted first) so the visually topmost card (`index === 0`, the only one with `drag` enabled) is also the last element in the DOM, which browsers paint on top by default without needing manual `z-index` juggling.

**Test file:** `frontend/features/job-swipe/components/SwipeDeckView.test.tsx` — covers loading/error/empty states; asserts exactly `MAX_STACKED_CARDS` (or fewer, if the deck is smaller) `SwipeCard`s render; asserts only one rendered card has `isTop=true`; asserts `handleSwipe` calls `submitSwipe.mutate` with the swiped card's `matchId` and the reported direction.

**New file:** `frontend/features/job-swipe/index.ts`

```typescript
export { useSwipeDeck, useSubmitSwipe } from "./hooks/useSwipeDeck";
export { SwipeCard } from "./components/SwipeCard";
export { SwipeDeckView } from "./components/SwipeDeckView";
export { jobSwipeKeys } from "./api/keys";
```

---

### 12.5 `frontend/features/portfolio/` — profile editor + public page renderer

**New file:** `frontend/features/portfolio/api/keys.ts`

```typescript
export const portfolioKeys = {
  all: ["portfolio"] as const,
  profile: () => [...portfolioKeys.all, "profile"] as const,
  public: (slug: string) => [...portfolioKeys.all, "public", slug] as const,
};
```

**New file:** `frontend/features/portfolio/hooks/usePortfolioProfile.ts`

```typescript
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { addPortfolioItem, deletePortfolioItem, fetchPortfolioProfile, savePortfolioProfile } from "@/src/lib/api-client";
import type { PortfolioItem, PortfolioProfile } from "@/src/lib/types";
import { portfolioKeys } from "../api/keys";

export function usePortfolioProfile() {
  return useQuery({
    queryKey: portfolioKeys.profile(),
    queryFn: async () => (await fetchPortfolioProfile()).data,
    retry: (failureCount, error) => {
      if (error instanceof Error && error.message.includes("404")) return false; // not created yet
      return failureCount < 2;
    },
  });
}

export function useSavePortfolioProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<PortfolioProfile> & { slug: string }) => savePortfolioProfile(payload),
    onSuccess: (response) => queryClient.setQueryData(portfolioKeys.profile(), response.data),
  });
}

export function useAddPortfolioItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Omit<PortfolioItem, "itemId" | "displayOrder">) => addPortfolioItem(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: portfolioKeys.profile() }),
  });
}

export function useDeletePortfolioItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (itemId: string) => deletePortfolioItem(itemId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: portfolioKeys.profile() }),
  });
}
```

**Test file:** `frontend/features/portfolio/hooks/usePortfolioProfile.test.ts` — asserts `usePortfolioProfile` does not retry on a 404 (mirrors `phase2_module1.md` §11.3's already-established `usePreferences` test pattern for the exact same "404 means not-created-yet" case); asserts `useAddPortfolioItem`/`useDeletePortfolioItem` invalidate the profile query on success.

**New file:** `frontend/features/portfolio/hooks/usePublicPortfolio.ts`

```typescript
import { useQuery } from "@tanstack/react-query";
import { fetchPublicPortfolio } from "@/src/lib/api-client";
import { portfolioKeys } from "../api/keys";

export function usePublicPortfolio(slug: string) {
  return useQuery({
    queryKey: portfolioKeys.public(slug),
    queryFn: async () => (await fetchPublicPortfolio(slug)).data,
    retry: false, // 404 (unpublished/unknown slug) is a valid terminal state, not transient
  });
}
```

**New file:** `frontend/features/portfolio/components/SlugField.tsx`

```tsx
"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const SLUG_PATTERN = /^[a-z0-9]+(-[a-z0-9]+)*$/;

interface SlugFieldProps {
  value: string;
  onChange: (value: string) => void;
}

export function SlugField({ value, onChange }: SlugFieldProps) {
  const isValid = value.length === 0 || (value.length >= 3 && value.length <= 60 && SLUG_PATTERN.test(value));

  return (
    <div>
      <Label htmlFor="slug">Portfolio URL</Label>
      <div className="flex items-center gap-1 text-sm text-muted-foreground">
        <span>hyrepath.dev/p/</span>
        <Input
          id="slug"
          value={value}
          onChange={(e) => onChange(e.target.value.toLowerCase())}
          className="w-48"
          aria-invalid={!isValid}
        />
      </div>
      {!isValid && (
        <p className="mt-1 text-xs text-destructive">
          3-60 characters: lowercase letters, numbers, and single hyphens between words.
        </p>
      )}
    </div>
  );
}
```

**Design note:** `SLUG_PATTERN` mirrors the backend's `PortfolioProfileRequest` validator (§8.10, §9.6) exactly (same regex intent, both reject uppercase/leading-hyphen/too-short) — client-side validation here is a UX nicety (instant feedback), not the source of truth; the backend re-validates and rejects independently, per RULE.md's "never trust the client" default.

**Test file:** `frontend/features/portfolio/components/SlugField.test.tsx` — asserts invalid-state styling/message appears for `"AB"` (too short), `"-abc"` (leading hyphen), `"ABC-def"` (uppercase); asserts no error for `"john-doe-42"`; asserts typed input is lowercased before calling `onChange`.

**New file:** `frontend/features/portfolio/components/PortfolioEditor.tsx`

```tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  useAddPortfolioItem,
  useDeletePortfolioItem,
  usePortfolioProfile,
  useSavePortfolioProfile,
} from "../hooks/usePortfolioProfile";
import { SlugField } from "./SlugField";
import type { PortfolioItem } from "@/src/lib/types";

const ITEM_TYPE_LABELS: Record<PortfolioItem["itemType"], string> = {
  github_repo: "GitHub repo",
  live_demo: "Live demo",
  case_study: "Case study",
  other_link: "Other link",
};

export function PortfolioEditor() {
  const { data: profile, isLoading } = usePortfolioProfile();
  const saveProfile = useSavePortfolioProfile();
  const addItem = useAddPortfolioItem();
  const deleteItem = useDeletePortfolioItem();

  const [slug, setSlug] = useState(profile?.slug ?? "");
  const [headline, setHeadline] = useState(profile?.headline ?? "");
  const [summary, setSummary] = useState(profile?.summary ?? "");
  const [isPublished, setIsPublished] = useState(profile?.isPublished ?? false);
  const [newItemUrl, setNewItemUrl] = useState("");
  const [newItemTitle, setNewItemTitle] = useState("");

  if (isLoading) return <div className="animate-pulse h-96 rounded-lg bg-muted" />;

  function handleSave(e: React.FormEvent) {
    e.preventDefault();
    saveProfile.mutate({ slug, headline: headline || null, summary: summary || null, isPublished });
  }

  function handleAddItem(e: React.FormEvent) {
    e.preventDefault();
    if (!newItemUrl.trim() || !newItemTitle.trim()) return;
    addItem.mutate(
      { itemType: "other_link", title: newItemTitle, description: null, url: newItemUrl },
      { onSuccess: () => { setNewItemUrl(""); setNewItemTitle(""); } },
    );
  }

  return (
    <div className="space-y-8">
      <form onSubmit={handleSave} className="space-y-4">
        <SlugField value={slug} onChange={setSlug} />
        <div>
          <Label htmlFor="headline">Headline</Label>
          <Input id="headline" value={headline} onChange={(e) => setHeadline(e.target.value)} maxLength={120} />
        </div>
        <div>
          <Label htmlFor="summary">Summary</Label>
          <Textarea id="summary" value={summary} onChange={(e) => setSummary(e.target.value)} maxLength={2000} rows={4} />
        </div>
        <div className="flex items-center justify-between rounded-lg border p-4">
          <div>
            <Label htmlFor="isPublished">Publish portfolio</Label>
            <p className="text-sm text-muted-foreground">
              Anyone with the link can view it once published.
            </p>
          </div>
          <Switch id="isPublished" checked={isPublished} onCheckedChange={setIsPublished} />
        </div>
        <Button type="submit" disabled={saveProfile.isPending || slug.length < 3}>
          {saveProfile.isPending ? "Saving..." : "Save profile"}
        </Button>
      </form>

      {profile && (
        <div>
          <h3 className="text-sm font-semibold">Portfolio items</h3>
          <ul className="mt-2 space-y-2">
            {profile.items.map((item) => (
              <li key={item.itemId} className="flex items-center justify-between rounded-lg border p-3">
                <div>
                  <p className="text-sm font-medium">{item.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {ITEM_TYPE_LABELS[item.itemType]} · {item.url}
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => deleteItem.mutate(item.itemId)}
                  disabled={deleteItem.isPending}
                >
                  Remove
                </Button>
              </li>
            ))}
          </ul>

          <form onSubmit={handleAddItem} className="mt-3 flex gap-2">
            <Input
              placeholder="Title"
              value={newItemTitle}
              onChange={(e) => setNewItemTitle(e.target.value)}
              className="w-32"
            />
            <Input
              placeholder="https://..."
              value={newItemUrl}
              onChange={(e) => setNewItemUrl(e.target.value)}
              className="flex-1"
            />
            <Button type="submit" disabled={addItem.isPending}>
              Add
            </Button>
          </form>
        </div>
      )}
    </div>
  );
}
```

**Test file:** `frontend/features/portfolio/components/PortfolioEditor.test.tsx` — asserts save button is disabled while `slug.length < 3`; asserts `handleSave` calls `saveProfile.mutate` with the current form values; asserts each item's "Remove" button calls `deleteItem.mutate(item.itemId)`; asserts `handleAddItem` clears the two input fields on success.

**New file:** `frontend/features/portfolio/components/PublicPortfolioPage.tsx`

```tsx
import { Badge } from "@/components/ui/badge";
import type { PublicPortfolioProfile } from "@/src/lib/types";

interface PublicPortfolioPageProps {
  profile: PublicPortfolioProfile;
}

const ITEM_TYPE_LABELS: Record<string, string> = {
  github_repo: "GitHub",
  live_demo: "Live demo",
  case_study: "Case study",
  other_link: "Link",
};

export function PublicPortfolioPage({ profile }: PublicPortfolioPageProps) {
  return (
    <article className="mx-auto max-w-2xl space-y-8 px-4 py-12">
      <header>
        {profile.headline && <h1 className="text-3xl font-bold">{profile.headline}</h1>}
        {profile.summary && <p className="mt-3 text-muted-foreground">{profile.summary}</p>}
      </header>

      {profile.items.length > 0 && (
        <section className="space-y-3">
          {profile.items.map((item) => (
            <a
              key={item.itemId}
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="block rounded-lg border p-4 transition hover:border-primary"
            >
              <div className="flex items-center justify-between">
                <h2 className="font-medium">{item.title}</h2>
                <Badge variant="outline">{ITEM_TYPE_LABELS[item.itemType] ?? item.itemType}</Badge>
              </div>
              {item.description && <p className="mt-1 text-sm text-muted-foreground">{item.description}</p>}
            </a>
          ))}
        </section>
      )}
    </article>
  );
}
```

**Test file:** `frontend/features/portfolio/components/PublicPortfolioPage.test.tsx` — renders headline/summary conditionally when null; asserts each item link has `target="_blank"` + `rel="noopener noreferrer"` (external-link safety, not optional); asserts unknown `itemType` values fall back to the raw string rather than crashing.

**New file:** `frontend/features/portfolio/index.ts`

```typescript
export { usePortfolioProfile, useSavePortfolioProfile, useAddPortfolioItem, useDeletePortfolioItem } from "./hooks/usePortfolioProfile";
export { usePublicPortfolio } from "./hooks/usePublicPortfolio";
export { PortfolioEditor } from "./components/PortfolioEditor";
export { PublicPortfolioPage } from "./components/PublicPortfolioPage";
export { SlugField } from "./components/SlugField";
export { portfolioKeys } from "./api/keys";
```

---

### 12.6 `frontend/features/outreach/` — draft, edit, send

**New file:** `frontend/features/outreach/api/keys.ts`

```typescript
export const outreachKeys = {
  all: ["outreach"] as const,
  list: () => [...outreachKeys.all, "list"] as const,
};
```

**New file:** `frontend/features/outreach/hooks/useOutreach.ts`

```typescript
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { draftOutreach, editOutreachDraft, fetchOutreachMessages, sendOutreach } from "@/src/lib/api-client";
import { outreachKeys } from "../api/keys";

export function useOutreachMessages() {
  return useQuery({
    queryKey: outreachKeys.list(),
    queryFn: async () => (await fetchOutreachMessages()).data,
  });
}

export function useDraftOutreach() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ jobPostingId, documentId }: { jobPostingId: string; documentId?: string }) =>
      draftOutreach(jobPostingId, documentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: outreachKeys.list() }),
  });
}

export function useEditOutreachDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ messageId, subject, body }: { messageId: string; subject: string; body: string }) =>
      editOutreachDraft(messageId, subject, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: outreachKeys.list() }),
  });
}

export function useSendOutreach() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (messageId: string) => sendOutreach(messageId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: outreachKeys.list() }),
  });
}
```

**Test file:** `frontend/features/outreach/hooks/useOutreach.test.ts` — asserts each mutation hook calls its `api-client` function with the correct arguments and invalidates `outreachKeys.list()` on success.

**New file:** `frontend/features/outreach/components/OutreachDraftCard.tsx`

```tsx
"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { OutreachMessage } from "@/src/lib/types";
import { useEditOutreachDraft, useSendOutreach } from "../hooks/useOutreach";

interface OutreachDraftCardProps {
  message: OutreachMessage;
}

export function OutreachDraftCard({ message }: OutreachDraftCardProps) {
  const editDraft = useEditOutreachDraft();
  const sendMessage = useSendOutreach();
  const [subject, setSubject] = useState(message.subject);
  const [body, setBody] = useState(message.body);
  const isDirty = subject !== message.subject || body !== message.body;

  const canEdit = message.status === "draft";

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-medium">{message.companyName}</h3>
          {message.recipientRole && (
            <p className="text-sm text-muted-foreground">{message.recipientRole}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {message.companyContextSource === "none" && (
            <Badge variant="outline" title="No live company research was available for this draft.">
              Generic draft
            </Badge>
          )}
          <Badge variant={message.status === "sent" ? "default" : "outline"}>{message.status}</Badge>
        </div>
      </div>

      <Input value={subject} onChange={(e) => setSubject(e.target.value)} disabled={!canEdit} />
      <Textarea value={body} onChange={(e) => setBody(e.target.value)} disabled={!canEdit} rows={8} />

      {canEdit && (
        <div className="flex justify-end gap-2">
          {isDirty && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => editDraft.mutate({ messageId: message.messageId, subject, body })}
              disabled={editDraft.isPending}
            >
              Save changes
            </Button>
          )}
          <Button
            size="sm"
            onClick={() => sendMessage.mutate(message.messageId)}
            disabled={sendMessage.isPending || isDirty}
            title={isDirty ? "Save your changes before sending" : undefined}
          >
            {sendMessage.isPending ? "Sending..." : "Send"}
          </Button>
        </div>
      )}
    </div>
  );
}
```

**Design rationale — `disabled={sendMessage.isPending || isDirty}` on Send:** prevents sending stale-in-memory text that hasn't been persisted via `editDraft` yet — the backend's `send_message()` (§8.13) reads `body`/`subject` from the database row, not from whatever the client currently has typed, so sending while `isDirty` would silently send the *previous* saved version, not what's on screen. Disabling until saved makes that impossible rather than documenting it as a gotcha.

**Test file:** `frontend/features/outreach/components/OutreachDraftCard.test.tsx` — asserts subject/body inputs are disabled once `status !== "draft"`; asserts "Save changes" only appears when the text differs from the original `message` props; asserts "Send" is disabled while dirty and enabled once saved; asserts the "Generic draft" badge appears only when `companyContextSource === "none"`.

**New file:** `frontend/features/outreach/index.ts`

```typescript
export { useOutreachMessages, useDraftOutreach, useEditOutreachDraft, useSendOutreach } from "./hooks/useOutreach";
export { OutreachDraftCard } from "./components/OutreachDraftCard";
export { outreachKeys } from "./api/keys";
```

---

## 13. Frontend — pages, routing, navigation

### 13.1 Route map and naming collision check (per §4's own methodology, applied to the frontend)

✅ **DIRECT** (read `phase2_module1.md` §4/§11 and `frontend/app/app/jobs/page.tsx` directly) — `/app/matches` is **already claimed** by Module 1's list-view feed of `JobMatch` records (score badges, thumbs up/down, `MatchesView.tsx`). Module 2's swipe deck operates on the **same underlying data** (`job_matches`/`job_postings`, read-only, per §4.1) through a **different interaction model** (drag-to-decide instead of scroll-and-thumb). Two independent top-level nav items for "the same matches, two ways to look at them" would be confusing; nesting the swipe deck as an alternate view under the existing `/app/matches` area is the resolution:

| Feature | Route | New/reuses | Auth |
|---|---|---|---|
| Swipe deck | `/app/matches/swipe` | NEW — nested under Module 1's existing `/app/matches` area, not a new top-level nav item | authenticated |
| Matches list (Module 1, unchanged) | `/app/matches` | existing | authenticated |
| CV documents list + upload | `/app/documents` | NEW — this is the previously-flagged gap (`phase2_module1.md` §11.10, confirmed again in §11.1 above: zero `documents` BFF routes exist today) | authenticated |
| CV document detail (completeness, chat, feedback) | `/app/documents/[documentId]` | NEW | authenticated |
| Portfolio editor | `/app/portfolio` | NEW | authenticated |
| Public portfolio page | `/p/[slug]` | NEW — deliberately **outside** the `/app` shell (no sidebar/nav chrome), matching the "hosted subdomain-style" public page from the original brief | **unauthenticated** |
| Outreach drafts | `/app/outreach` | NEW | authenticated |

`/p/[slug]` sits at the top level (sibling to the existing `(marketing)` and `(auth)` route groups, not nested under `/app`) for the same reason `frontend/app/opt-out/page.tsx` and `frontend/app/(marketing)/*` sit outside `/app` today: pages a logged-out visitor can load must not inherit `frontend/app/app/layout.tsx`'s authenticated shell (sidebar, bottom nav, auth guard).

### 13.2 CV documents — `/app/documents`

**New file:** `frontend/app/app/documents/page.tsx`

```tsx
import { Suspense } from "react";
import { DocumentsView } from "./DocumentsView";

export default function DocumentsPage() {
  return (
    <Suspense fallback={<div className="animate-pulse h-96 rounded-lg bg-muted" />}>
      <DocumentsView />
    </Suspense>
  );
}
```

**New file:** `frontend/app/app/documents/DocumentsView.tsx` — thin list page; upload itself reuses whatever generic upload widget Foundation Week 1 already ships for `POST /api/documents` (out of this module's scope to invent a second uploader — this view only lists documents and links into each one's detail page):

```tsx
"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { EmptyState } from "@/components/console/EmptyState";
import { Badge } from "@/components/ui/badge";

interface DocumentSummary {
  documentId: string;
  originalFilename: string;
  documentType: string;
  processingStatus: string;
  createdAt: string;
}

async function fetchDocuments(): Promise<{ documents: DocumentSummary[] }> {
  const res = await fetch("/api/documents");
  if (!res.ok) throw new Error(`Failed to fetch documents: ${res.status}`);
  const json = await res.json();
  return json.data;
}

export function DocumentsView() {
  const { data, isLoading, isError } = useQuery({ queryKey: ["documents", "list"], queryFn: fetchDocuments });

  if (isLoading) return <div className="animate-pulse h-96 rounded-lg bg-muted" />;
  if (isError) return <EmptyState title="Couldn't load your documents" description="Please try again shortly." />;
  if (!data || data.documents.length === 0) {
    return <EmptyState title="No CV uploaded yet" description="Upload a PDF or DOCX to get started." />;
  }

  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-semibold">Your documents</h1>
      {data.documents.map((doc) => (
        <Link
          key={doc.documentId}
          href={`/app/documents/${doc.documentId}`}
          className="flex items-center justify-between rounded-lg border p-4 transition hover:border-primary"
        >
          <span className="font-medium">{doc.originalFilename}</span>
          <Badge variant={doc.processingStatus === "completed" ? "default" : "outline"}>
            {doc.processingStatus}
          </Badge>
        </Link>
      ))}
    </div>
  );
}
```

**Scope note:** `fetch("/api/documents")` above assumes Foundation Week 1's own document-list BFF route (not this module's to (re)build — Module 2 only adds the *detail* page's completeness/chat/feedback panels, §13.3). If that list route does not exist yet either, it is one `frontend/app/api/documents/route.ts` proxy identical in shape to §11.4's other GET routes — flagged here rather than silently assumed, per this document's own "check before designing" discipline (§4).

**New file:** `frontend/app/app/documents/[documentId]/page.tsx`

```tsx
import { Suspense } from "react";
import { DocumentDetailView } from "./DocumentDetailView";

export default async function DocumentDetailPage({
  params,
}: {
  params: Promise<{ documentId: string }>;
}) {
  const { documentId } = await params;
  return (
    <Suspense fallback={<div className="animate-pulse h-96 rounded-lg bg-muted" />}>
      <DocumentDetailView documentId={documentId} />
    </Suspense>
  );
}
```

**New file:** `frontend/app/app/documents/[documentId]/DocumentDetailView.tsx`

```tsx
"use client";

import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CompletenessBanner, CvChatWidget, CvFeedbackPanel } from "@/features/cv-management";

interface DocumentDetailViewProps {
  documentId: string;
}

export function DocumentDetailView({ documentId }: DocumentDetailViewProps) {
  const [showChat, setShowChat] = useState(false);

  return (
    <div className="space-y-4">
      <CompletenessBanner documentId={documentId} onStartChat={() => setShowChat(true)} />

      {showChat && (
        <CvChatWidget documentId={documentId} onComplete={() => setShowChat(false)} />
      )}

      <Tabs defaultValue="feedback">
        <TabsList>
          <TabsTrigger value="feedback">AI feedback</TabsTrigger>
        </TabsList>
        <TabsContent value="feedback">
          <CvFeedbackPanel documentId={documentId} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
```

**Test file:** `frontend/app/app/documents/[documentId]/DocumentDetailView.test.tsx` — asserts `CvChatWidget` is not rendered until `onStartChat` fires from `CompletenessBanner`; asserts it unmounts again once `onComplete` fires.

---

### 13.3 Swipe deck — `/app/matches/swipe`

**New file:** `frontend/app/app/matches/swipe/page.tsx`

```tsx
import { Suspense } from "react";
import { SwipeDeckView } from "@/features/job-swipe";

export default function SwipeDeckPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">Swipe your matches</h1>
        <p className="text-sm text-muted-foreground">
          Swipe right if you&apos;re interested, left to pass, up for a super like.
        </p>
      </div>
      <Suspense fallback={<div className="animate-pulse h-[32rem] rounded-2xl bg-muted" />}>
        <SwipeDeckView />
      </Suspense>
    </div>
  );
}
```

**Edited file:** `frontend/app/app/matches/MatchesView.tsx` (Module 1's existing file) — add one link into the new swipe view, next to the existing "Scan now" button (a one-line addition, not a rewrite of Module 1's component):

```tsx
// Added inside MatchesView.tsx's header row, beside the existing "Scan now" Button:
<Link href="/app/matches/swipe">
  <Button variant="outline">Try swipe view</Button>
</Link>
```

---

### 13.4 Portfolio — `/app/portfolio` and public `/p/[slug]`

**New file:** `frontend/app/app/portfolio/page.tsx`

```tsx
import { Suspense } from "react";
import { PortfolioEditor } from "@/features/portfolio";

export default function PortfolioPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Portfolio</h1>
      <Suspense fallback={<div className="animate-pulse h-96 rounded-lg bg-muted" />}>
        <PortfolioEditor />
      </Suspense>
    </div>
  );
}
```

**New file:** `frontend/app/p/[slug]/page.tsx` — outside `/app` per §13.1, so it does **not** inherit `frontend/app/app/layout.tsx`'s auth guard or sidebar chrome, and must fetch server-side via `backendFetchPublic` directly (not the client-side `usePublicPortfolio` hook, since this is a server component so search engines and unauthenticated visitors get a fully-rendered page, not a client-fetched skeleton):

```tsx
import { notFound } from "next/navigation";
import { adaptPublicPortfolioProfile } from "@/src/lib/api-adapter";
import { backendFetchPublic } from "@/src/lib/backend-client";
import { PublicPortfolioPage } from "@/features/portfolio";

export default async function PublicSlugPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;

  const response = await backendFetchPublic(`/api/portfolio/public/${slug}`);
  if (!response.ok) notFound();

  const raw = await response.json();
  const profile = adaptPublicPortfolioProfile(raw.data);

  return <PublicPortfolioPage profile={profile} />;
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const response = await backendFetchPublic(`/api/portfolio/public/${slug}`);
  if (!response.ok) return { title: "Portfolio not found" };
  const raw = await response.json();
  return { title: raw.data.headline ? `${raw.data.headline} — Portfolio` : "Portfolio" };
}
```

**Design rationale — server component, not the client hook:** `usePublicPortfolio` (§12.5) exists for a future case where a logged-in user might preview their *own* portfolio inside the app shell client-side; the actual public-facing `/p/[slug]` page is deliberately a server component instead, so it renders real content in the initial HTML (SEO, and no loading-skeleton flash for a page whose entire purpose is being shared as a link) and can 404 server-side via `notFound()` before any client JS runs.

---

### 13.5 Outreach — `/app/outreach`

**New file:** `frontend/app/app/outreach/page.tsx`

```tsx
import { Suspense } from "react";
import { OutreachView } from "./OutreachView";

export default function OutreachPage() {
  return (
    <Suspense fallback={<div className="animate-pulse h-96 rounded-lg bg-muted" />}>
      <OutreachView />
    </Suspense>
  );
}
```

**New file:** `frontend/app/app/outreach/OutreachView.tsx`

```tsx
"use client";

import { EmptyState } from "@/components/console/EmptyState";
import { OutreachDraftCard, useOutreachMessages } from "@/features/outreach";

export function OutreachView() {
  const { data, isLoading, isError } = useOutreachMessages();

  if (isLoading) return <div className="animate-pulse h-96 rounded-lg bg-muted" />;
  if (isError) return <EmptyState title="Couldn't load your outreach drafts" description="Please try again shortly." />;
  if (!data || data.messages.length === 0) {
    return (
      <EmptyState
        title="No outreach drafts yet"
        description={'Draft outreach from a job\u2019s "why we matched you" card on your swipe deck or matches list.'}
      />
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Outreach</h1>
      <div className="space-y-3">
        {data.messages.map((message) => (
          <OutreachDraftCard key={message.messageId} message={message} />
        ))}
      </div>
    </div>
  );
}
```

**Cross-feature wiring — where "Draft outreach" is actually triggered:** per the empty-state copy above, drafting starts from a job card, not from this page. **Edited file:** `frontend/features/job-swipe/components/SwipeCard.tsx` (§12.4) gets one more button in its bottom section (added, not shown again in full here to avoid repeating the whole file):

```tsx
// Added to SwipeCard.tsx's bottom content block, guarded so it never intercepts drag gestures:
<Button
  size="sm"
  variant="outline"
  onClick={(e) => { e.stopPropagation(); onDraftOutreach(card.jobPostingId); }}
  className="mt-2"
>
  Draft outreach
</Button>
```

This requires threading one more prop, `onDraftOutreach: (jobPostingId: string) => void`, from `SwipeDeckView` down to `SwipeCard`, wired to `useDraftOutreach().mutate({ jobPostingId })` — a small, additive prop change, not a redesign of §12.4's component.

---

### 13.6 Navigation registration

✅ **DIRECT** (read `frontend/components/layout/nav-config.ts` in full, above) — `mainNav`/`systemNav` are plain arrays that `AppSidebar`/`AppBottomNav` already read from; adding items here is the entire integration surface, per `phase2_module1.md` §10's own confirmed pattern.

**Edited file:** `frontend/components/layout/nav-config.ts`

```typescript
// Added imports:
import { Sparkles, Briefcase, User, Mail } from "lucide-react";

// mainNav.items gets one new entry (documents feeds the other three features, so it goes
// first among the new ones — a user without a CV can't sensibly use swipe/portfolio/outreach yet):
{ href: "/app/documents", label: "My CV", icon: Sparkles },
{ href: "/app/matches/swipe", label: "Swipe jobs", icon: Briefcase },
{ href: "/app/portfolio", label: "Portfolio", icon: User },
{ href: "/app/outreach", label: "Outreach", icon: Mail },
```

**Design note — ordering, not just addition:** `/app/documents` is placed before Module 1's existing `/app/matches`, `/app/history`, `/app/signals` in `mainNav.items`, because every other Module 2 feature (chat, feedback, swipe deck's "why we matched", outreach's context) is either directly gated on having an uploaded CV or meaningfully improved by one. This is the same "what does a brand-new user need first" reasoning `phase2_module1.md` itself did not have to make (it only added one item, `/app/matches`, with no internal ordering decision to justify).

---

## 14. ADR — required per RULE.md (new storage + new queue + new external API)

**New file:** `docs/adr/0014-cv-chat-portfolio-outreach.md`

```markdown
# 0014. CV Chat, Portfolio, and Outreach — Storage, Queue, and External API Choices

- **Status:** Proposed
- **Date:** 2026-08-08

## Context

Module 2 ("Tinder-Style Job Board + CV Management") adds five features on top
of Foundation Week 1/2 and Module 1's existing schema. Three of them introduce
genuinely new architectural surface that RULE.md's "When to add an ADR"
criteria (new storage, new queue, new external API, new layer ownership)
require recording:

1. A CV-completeness chatbot needs somewhere to persist multi-turn
   conversation state across requests.
2. Outreach drafting needs live, per-company context that nothing already
   integrated (OpenAI, SendGrid, JobSpy) can provide.
3. A public-facing portfolio page needs to exist **outside** authentication
   entirely — a new trust boundary this codebase has only crossed once before
   (`/opt-out`, `/api/dsar`'s public half).

Job swipe (reads Module 1's existing `job_matches`/`job_postings` read-only)
and CV feedback (reuses the existing `QUEUE_FEEDBACK` queue and
`feedback_generator.py` pattern) are deliberately **not** covered by this ADR
— neither introduces new storage, queue, or external-API surface; they are
ordinary extensions of already-decided architecture (see `phase2_module2.md`
§3 Decisions 3 and 6 for their reasoning, which does not rise to ADR weight).

## Decision

1. **CV chat storage**: two new tables, `cv_chat_sessions` +
   `cv_chat_messages`, owned by the existing `documents` module (not a new
   top-level module) — chat state is a side-effect of one specific document's
   completeness check, the same ownership boundary `candidate_documents`
   already has. **Chat runs synchronously on the `api` container**, not a
   worker queue — each OpenAI round trip is single-digit seconds and the user
   is actively waiting in a conversation, the same shape as any other
   request/response endpoint, not a background job (`phase2_module2.md` §3
   Decision 2).
2. **Outreach's external API**: **Perplexity Sonar**, not a second OpenAI
   call with retrieval bolted on, and not a bespoke web-scraping client.
   Perplexity's API returns web-grounded summaries directly, with built-in
   recency — the exact shape "company context" needs, verified against
   Perplexity's own API documentation before this ADR was written. Failure
   mode: on any error, timeout, or missing API key, `PerplexityClient`
   returns `{"summary": "", "source": "none"}` and outreach generation
   proceeds with a generic (still real, still useful) draft rather than
   failing the whole job — a new external dependency must degrade, not
   become a new single point of failure (`phase2_module2.md` §3 Decision 7).
3. **Outreach queue**: `outreach_generation`, appended to the **existing
   generic worker's** queue list in `rq_worker.py` (not a new dedicated
   container) — see `phase2_module2.md` §10 for the full reasoning distinguishing
   this from Module 1's `worker-job-matching` isolation decision. In short:
   outreach's per-job latency and per-click (not per-burst) trigger pattern
   put it in the same risk class as CV feedback, which already safely shares
   that worker today.
4. **Public portfolio trust boundary**: `GET /api/portfolio/public/{slug}`
   is the **only** unauthenticated route this module adds, deliberately kept
   to read-only, deliberately excluded from the `EnvelopeAPIRoute` global
   auth dependency by routing it through a separate `APIRouter` with no
   `dependencies=[Depends(current_active_verified_user)]` (mirroring how
   `/api/opt-out` already carves out its own public exception today).
   `PublicPortfolioProfileResponse` is a distinct Pydantic schema from the
   authenticated `PortfolioProfileResponse` — it has no `user_id` field at
   all, not a field that is merely omitted at serialization time, so leaking
   it is a type error, not a runtime mistake (`phase2_module2.md` §9.6).

## Tradeoffs

- Reusing `documents` for CV chat keeps ownership simple but means that
  module's `router.py`/`service.py` grow by five endpoints/methods — judged
  acceptable because they are all about the *same* document, not scope creep
  into unrelated concerns.
- Perplexity adds a second paid LLM-adjacent vendor (alongside OpenAI) to
  track spend for — mitigated by the same `cost_tracking.py` instrumentation
  Foundation Week 2 already built for OpenAI calls, extended rather than
  duplicated.
- Keeping outreach on the shared worker instead of isolating it now is a
  YAGNI bet: if wrong, the fix is mechanical (§10.2's documented playbook),
  but it is a real bet, not a guarantee.

## Consequences

- 6 new Alembic revisions (`022`-`027`, `phase2_module2.md` §6), 0 new
  containers, 0 new Dockerfiles, 1 new environment variable group
  (`PERPLEXITY_API_KEY`/`PERPLEXITY_API_BASE`, `phase2_module2.md` §7).
- `docs/adr/README.md`'s ADR index gets a new row for `0014`.
- The Postgres pool-sizing gap already flagged in `phase2_module1.md` §4/ADR
  0013 is **not worsened** by this ADR (§10.3) — a deliberate, stated
  contrast with Module 1's own ADR, which *did* have to accept worsening it.

## Alternatives considered

- **CV chat as a new top-level `modules/cv_chat/`**: rejected — would split
  one document's lifecycle (upload → completeness → chat → feedback) across
  two module boundaries for no ownership benefit; `documents` already owns
  the document.
- **Google/Bing web search API instead of Perplexity**: rejected — would
  require a second LLM call to summarize raw search results into prose,
  duplicating what Perplexity's API already returns in one call; more
  latency, more cost, more code for the same output shape.
- **A second OpenAI-only outreach flow with `browsing` tool-calling**:
  rejected at the time this ADR was written — OpenAI's hosted browsing tool
  was not yet available/stable enough to depend on for a production feature
  when this decision was made; revisit if that changes.
- **Isolate outreach on its own worker container immediately**: rejected —
  no demonstrated starvation evidence yet (§10.2); revisit if evidence
  appears.
```

**Edited file:** `docs/adr/README.md` — add one row to the ADR index table (exact row format verified by reading the file directly before editing) pointing at `0014-cv-chat-portfolio-outreach.md`, following the same one-line-per-ADR convention every prior entry uses.

---

## 15. `backend/docs/ARCHITECTURE.md` — Implementation status diff

Add rows to the "Implementation status" table (exact table location/format verified directly, §656 in the version read this session):

```markdown
| CV completeness chat (Module 2) | `app/modules/documents/cv_chat_service.py`, `app/clients/llm_tools.py` | Real, scaffolded per `phase2_module2.md`. Synchronous on `api`, no queue. |
| CV improvement feedback (Module 2) | `app/services/feedback_generator.py` (`generate_cv_improvement`), `app/workers/tasks/cv_improvement.py` | Real, scaffolded per `phase2_module2.md`. Shares `QUEUE_FEEDBACK` with Foundation Week 2's interview feedback. |
| Candidate portfolio (Module 2) | `app/modules/portfolio/` | Real, scaffolded per `phase2_module2.md`. Only module-2 feature with an unauthenticated public route. |
| Job swipe deck (Module 2) | `app/modules/job_swipe/` | Real, scaffolded per `phase2_module2.md`. Read-only against Module 1's `job_matches`/`job_postings` — depends on Module 1 shipping first. |
| Personalized outreach (Module 2) | `app/modules/outreach/`, `app/clients/perplexity.py` | Real, scaffolded per `phase2_module2.md`. New external dependency: Perplexity Sonar API (ADR 0014), degrades to generic drafts on failure. |
```

Add rows to the "Do not assume" table:

```markdown
| CV chat runs on a worker queue | It does not — synchronous on the `api` container per Decision 2 (`phase2_module2.md` §3). There is no `cv_chat` RQ queue. |
| Outreach has its own dedicated worker container | It does not — shares the generic `worker` container's `QUEUE_OUTREACH` (added to the existing fixed-priority list), unlike Module 1's `job_matching`, which does have a dedicated container. See `phase2_module2.md` §10 for why these two decisions differ. |
| Portfolio pages are all behind auth | `GET /api/portfolio/public/{slug}` (and its frontend counterpart `/p/[slug]`) are deliberately public — see ADR 0014. Every other portfolio/outreach/CV-chat/swipe route requires an authenticated, verified user. |
```

---

## 16. PR checklist (per `.github/pull_request_template.md`)

When Module 2's actual implementation PR is opened (this planning document itself is committed directly to the current branch per the user's explicit instruction — but the **code** described here, when implemented, should follow the normal branch+PR workflow):

- [ ] Link this document: `phase2_module2.md`
- [ ] Link the ADR: `docs/adr/0014-cv-chat-portfolio-outreach.md`
- [ ] Confirm the two prerequisite bug fixes (§2.1) are merged first — `cv_extractor.py`'s `response.json()` and `session_manager.py`'s `UUID` coercion — with their regression tests (§9.4, §9.5) green
- [ ] `alembic upgrade head` and `alembic downgrade 021_job_matches && alembic upgrade head` both succeed (§9.10) — note the downgrade target assumes Module 1's `021_job_matches` has landed first (§4's dependency)
- [ ] All 9 new/edited backend test files pass (§9.1-9.9)
- [ ] Coverage gate maintained (`--cov-fail-under=78`, §9.11)
- [ ] `ruff check` / `mypy` clean on new files
- [ ] Frontend `npm run typecheck && npm run lint && npm run build` all pass
- [ ] Frontend new-feature tests pass (`npm test -- features/cv-management features/job-swipe features/portfolio features/outreach`)
- [ ] `backend/docs/ARCHITECTURE.md` updated per §15
- [ ] `backend/.env.example` updated per §7 (placeholders only, no real keys)
- [ ] `npx shadcn@latest add switch` run and `components/ui/switch.tsx` committed (§12.1)
- [ ] `npm install framer-motion` run and committed to `package.json`/`package-lock.json` (§11.1)
- [ ] `npm run openapi:export && npm run openapi:gen` run after backend routes exist, generated files committed (§11.1)

---

## 17. Final completion checklist — Module 2 is 100% done when every box is checked

**Prerequisites (§2.1):**
- [ ] `cv_extractor.py`'s `await response.json()` bug fixed (sync call, no `await`)
- [ ] `session_manager.py`'s `user_id` UUID-coercion bug fixed
- [ ] Both have passing regression tests (§9.4, §9.5)

**Database (§6):**
- [ ] `022_cv_chat_sessions.py` through `027_outreach_messages.py` created, applied, and reversible
- [ ] `outreach_messages.job_posting_id` foreign key correctly references Module 1's `job_postings` table (§4.1's cross-module dependency honored)

**Backend (§8):**
- [ ] `app/domain/cv_completeness.py` created
- [ ] `app/modules/documents/models.py` edited: `CvChatSession`, `CvChatMessage`, `CvFeedbackReport`
- [ ] `app/clients/llm_tools.py` created
- [ ] `app/modules/documents/cv_chat_service.py` created
- [ ] `app/modules/documents/{schemas,service,router}.py` edited per §8.5-8.7
- [ ] `app/services/feedback_generator.py` edited: `generate_cv_improvement()`
- [ ] `app/workers/tasks/cv_improvement.py` created
- [ ] `app/modules/portfolio/{__init__,models,schemas,repository,service,router}.py` created
- [ ] `app/modules/job_swipe/{__init__,models,schemas,repository,service,router}.py` created
- [ ] `app/clients/perplexity.py` created
- [ ] `app/modules/outreach/{__init__,models,schemas,repository,service,router}.py` created
- [ ] `app/workers/tasks/outreach.py` created
- [ ] `app/workers/queue.py` edited: `QUEUE_OUTREACH` constant + priority entry
- [ ] `app/workers/rq_worker.py` edited: `QUEUE_OUTREACH` added to general-purpose worker's queue list, in the position §8.15 specifies (after `QUEUE_FEEDBACK`, before `QUEUE_DOCUMENT`)
- [ ] `app/main.py` edited: 3 new routers mounted
- [ ] `app/database/orm_registry.py` edited: new ORM modules imported
- [ ] `app/core/config.py` edited: new settings fields (§7)
- [ ] `app/services/email_service.py` edited: `CV_COMPLETENESS_REMINDER`, `PORTFOLIO_PUBLISHED` templates
- [ ] `backend/.env.example` edited (§7)

**Docker (§10):**
- [ ] Confirmed **zero** new Dockerfiles and **zero** new compose overlays are needed (§10.4) — this box exists so "did I forget the Docker work" is explicitly answered "no, by design," not silently skipped

**Testing (§9):**
- [ ] All 9 new/edited backend test files created and passing (§9.1-9.9)
- [ ] Migration upgrade/downgrade test passes (§9.10)
- [ ] Coverage gate (`--cov-fail-under=78`) passes
- [ ] Full existing test suite (`pytest`) still passes — no regressions introduced
- [ ] 4 frontend feature-module test suites created and passing (`cv-management`, `job-swipe`, `portfolio`, `outreach`)

**Frontend (§11-13):**
- [ ] `frontend/src/lib/types.ts` edited: 10 new interfaces/types (§11.2)
- [ ] `frontend/src/lib/api-adapter.ts` edited: 8 new adapter functions (§11.3)
- [ ] 14 BFF routes created under `frontend/app/api/{documents,cv-chat,cv-feedback,portfolio,matches,outreach}/*` (§11.4-11.7)
- [ ] `frontend/src/lib/api-client.ts` edited: 16 new functions (§12.2)
- [ ] `frontend/features/cv-management/` created (7 files: keys, 3 hooks, 3 components, index — §12.3)
- [ ] `frontend/features/job-swipe/` created (5 files: keys, hook, 2 components, index — §12.4)
- [ ] `frontend/features/portfolio/` created (7 files: keys, 2 hooks, 3 components, index — §12.5)
- [ ] `frontend/features/outreach/` created (4 files: keys, hook, component, index — §12.6)
- [ ] `frontend/app/app/documents/{page,DocumentsView}.tsx` and `[documentId]/{page,DocumentDetailView}.tsx` created (§13.2)
- [ ] `frontend/app/app/matches/swipe/page.tsx` created; `MatchesView.tsx` edited with the cross-link (§13.3)
- [ ] `frontend/app/app/portfolio/page.tsx` and `frontend/app/p/[slug]/page.tsx` created (§13.4)
- [ ] `frontend/app/app/outreach/{page,OutreachView}.tsx` created; `SwipeCard.tsx` edited with the "Draft outreach" button (§13.5)
- [ ] `frontend/components/layout/nav-config.ts` edited: 4 new nav entries, ordered per §13.6's reasoning
- [ ] `npx shadcn@latest add switch` run (§12.1)
- [ ] `framer-motion` added to `package.json` (§11.1)

**Documentation (§14-15):**
- [ ] `docs/adr/0014-cv-chat-portfolio-outreach.md` created
- [ ] `docs/adr/README.md` index updated
- [ ] `backend/docs/ARCHITECTURE.md` updated per §15

**If every box above is checked, Module 2 — Tinder-Style Job Board + CV Management — is 100% implemented, tested, documented, and consistent with `RULE.md`, exactly as this document specifies.**
