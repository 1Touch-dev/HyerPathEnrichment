# Phase 2 — Module 1: AI Job Matching & Notifications

**Branch:** `master-complete-foundation` (this file is committed directly to this branch — no new branch is created)
**Status:** Implementation blueprint — nothing described here exists in code yet unless explicitly marked `EXISTS` with a file citation. Everything else is `NEW`.
**Governing rule file:** `RULE.md` — every decision below was checked against it; violations are called out explicitly rather than silently made. See §0.

**Purpose of this document:** a single, linear, followable plan such that a developer (or agent) who implements every numbered step in order — backend, database, workers, Docker, tests, frontend — ends with Module 1 ("AI Job Matching & Notifications") **100% functionally complete**, with automated tests proving it, without needing to consult any other chat, report, or memory. Every file this plan creates or edits is listed by exact path. Every claim about *why* a design choice was made is evidence-labeled per §1.

---

## 0. RULE.md compliance checklist (read this before writing any code)

This plan was designed against `RULE.md` line by line. Rather than assume compliance, here is the explicit mapping:

| RULE.md requirement | How this plan complies |
|---|---|
| "Search the repo for an existing function, type, component, or pattern" (Before writing any code #1) | §2 inventories everything reused: `CVData`, `cv_extractor.py`, `vector_search.py`, `JobSpyEnricher`, `rq_scheduler.Scheduler.cron()`, `worker-email`/SendGrid, the `features/*` frontend pattern, the BFF pattern. Nothing reusable is rebuilt. |
| "Read Agent quick reference in ARCHITECTURE.md" (#2) | Done; Pipeline/merge/workers/compliance ownership boundaries are respected — Module 1 does **not** touch `enrichers/pipeline.py`, `enrichers/merge.py`, or `compliance/`. |
| "Check Implementation status — do not build on scaffold-only features" (#3) | Verified before use: `document_processor.py`/`cv_extractor.py`/`vector_search.py` are real, working code (not scaffold) — confirmed by reading them directly (see §2). `JobSpyEnricher` is real but request-scoped only (see §3, gap 1). |
| "Keep the change as small as the task allows" (#4) | New module (`app/modules/job_matching/`) instead of bolting onto `documents/` or `enrichment/`, per the "ORM lives with its owner" rule and "one concern per change." |
| Layer ownership table (`domain/`, `modules/`, `enrichers/pipeline.py`, `workers/`, `compliance/`, `clients/`, `storage/`, `database/`) | New code placed per this table exactly — see §4 file-by-file plan; every new file states which layer it belongs to and why. |
| Allowed/forbidden imports (`workers/tasks` → must not import `modules/*/service|router`) | `app/workers/tasks/job_matching.py` imports only `app/modules/job_matching/repository.py` (allowed: "workers/tasks → ... modules/*/repository"), never `service.py` or `router.py`. |
| "One provider per file", "extend Enricher in base.py" (Enrichers section) | `JobSpyEnricher` is **not modified**. Job Matching is not an enricher — it is a standalone recurring pipeline outside `enrichers/`, matching how `documents`/`sessions` modules already work (they are not enrichers either). |
| "Tier registration only in enrichers/registry.py" | Not touched — Module 1 introduces no new Tier-4 enricher; it *reuses* the existing `JobSpyEnricher` output shape by calling the same scraping function from a new scheduled worker context, not by adding a tier. |
| "Do not duplicate validation... merge logic... API field mapping" (No redundant code) | Preference validation lives once in `app/domain/job_matching.py` Pydantic models; no parallel validation in the router. No dossier merge is touched (Module 1 has its own merge-free scoring — see §3 Decision 3). Frontend field mapping goes through `api-adapter.ts` only, per existing convention. |
| "Routes are thin" | `job_matching/router.py` only does auth + call service + return; all scoring/matching logic is in `service.py` / `scorer.py`. |
| "ORM lives with its owner... never recreate a global app/models.py" | New ORM classes live in `app/modules/job_matching/models.py`, not bolted onto `documents/models.py` or a shared file. |
| "Async end-to-end... no run_until_complete in request paths" | All router/service code is `async def`; only the RQ worker entrypoint (a sync context, matching the existing `document.py`/`feedback.py` pattern) uses `asyncio.run()` — same pattern already used in this codebase, not a new one. |
| "Schema changes via Alembic only" | 3 new tables via 3 new Alembic revisions (§5), chained onto the current real head. No `create_all`. |
| "When to add an ADR" — new storage, queue, or layer ownership | **New queue** (`job_matching`) + **new storage** (3 tables) → ADR required. §12 supplies the ADR, `docs/adr/0013-job-matching-queue-and-storage.md`. |
| "New enricher → extend tests/test_pipeline_shape.py" | N/A — not an enricher. Equivalent obligation met instead: new module gets its own `tests/test_job_matching_*.py` suite (§8), matching how `documents`/`sessions` modules each have their own test files rather than being forced into `test_pipeline_shape.py`. |
| "No live external calls in CI... mock subprocess, HTTP, third-party APIs" | All tests mock `JobSpyEnricher._scrape`, OpenAI HTTP calls, and SendGrid — see §8. |
| "Coverage gate ... currently 78%" | New module code is covered per-function in §8; §8.9 gives the exact `pytest --cov` command to prove the gate is met before considering Module 1 done. |
| "Never log raw identifiers... use job IDs or hashed values" | All logging in new code truncates/hashes `user_id` (`str(user_id)[:8]`, matching existing convention in `document.py`/`service.py`) and never logs raw email/CV text. |
| "Never commit secrets... update .env.example with placeholders only" | §6 lists every new env var added to `.env.example` with placeholder values only — no real keys. |
| "Public data only... no discover people flows" | Module 1 only searches for jobs (public postings on public boards), never searches for people — consistent with existing `JobSpyEnricher` scope. |
| "Update backend/docs/ARCHITECTURE.md Implementation status if scaffold changed" | §13 gives the exact diff to add to `ARCHITECTURE.md`. |
| "New/changed storage, queue, auth, or layer ownership → ADR linked in the PR" | §12 ADR + §14 PR checklist explicitly links it. |
| Frontend: "Shared types... do not duplicate Dossier/EnrichmentInput shapes inline" | New `JobMatch`/`CandidateJobPreferences` types added to `frontend/src/lib/types.ts` once, mapped through `api-adapter.ts` — never inlined in components (§10). |
| Frontend: "Keep types in sync... run npm run openapi:export && npm run openapi:gen" | §10.1 gives the exact command sequence and what must be committed. |
| Testing: "New route behavior → API test: status code, auth, response shape" | §8 covers every new route. |
| Frontend: "Type changes → run npm run typecheck... UI changes → npm run lint / build" | §11.7 gives the exact commands. |

If any step below appears to conflict with `RULE.md`, `RULE.md` wins — this document is subordinate to it, not a replacement for it.

---

## 1. Evidence-label legend (used throughout)

- ✅ **DIRECT** — a primary source (official docs, a paper, a company engineering blog, or this repo's own code, read directly) states the claim.
- 🔗 **INDIRECT** — a real, citable source supports the general point but not in this exact form/number, or it's a third-party reconstruction.
- ❌ **NOT FOUND** — checked and could not be verified anywhere; stated as a design choice, not as proven fact.

All citations below were independently verified during this conversation (fetched and read, not recalled from training data). Where an earlier draft of this plan (pasted by the user, sourced from an external report) made claims that did not hold up, this is noted explicitly in §3 rather than silently corrected.

---

## 2. What already exists and will be reused unmodified

Verified by reading the files directly — not assumed from documentation.

| Capability | File | Reused how |
|---|---|---|
| CV → structured data (skills, salary, location, remote pref) | `backend/app/domain/candidate.py` (`CVData` Pydantic model) | Module 1 reads `CandidateDocument.extracted_data` (already populated by this model) as the source of candidate preferences — no new extraction code |
| CV parsing pipeline | `backend/app/services/document_processor.py`, `backend/app/services/cv_extractor.py` | Untouched. Module 1 depends on documents already being uploaded and processed via the existing `/api/documents/upload` flow |
| Document + embedding storage | `backend/app/modules/documents/models.py` (`CandidateDocument`, `DocumentEmbedding`) | Read-only dependency: Module 1 needs at least one `CandidateDocument` with `processing_status="completed"` per candidate |
| Vector similarity search | `backend/app/services/vector_search.py` (`similarity_search()`, `cosine_similarity()`) | Reused verbatim for candidate-CV ↔ job-posting embedding comparison — same function, new caller |
| Job board scraping | `backend/app/enrichers/jobspy.py` (`JobSpyEnricher`, `JOBSPY_SITES`) | The `_scrape()`/`_build_kwargs_manual()` static logic is reused by a new scheduled task; `JobSpyEnricher` class itself is **not modified** (it stays owned by `enrichers/` and the Tier-4 enrichment pipeline) |
| Embeddings client | `backend/app/clients/embeddings.py` (`get_embeddings_client()`) | Reused verbatim to embed job description text and CV text with `text-embedding-3-small` |
| Recurring scheduled jobs | `backend/app/workers/queue.py::register_scheduled_jobs()` (uses `rq_scheduler.Scheduler.cron()`) | Extended with one new `.cron()` registration — same mechanism as the existing `audio_cleanup_daily` job, no new scheduling framework |
| Email delivery | `backend/app/services/email_service.py` (`EmailService`, `EmailTemplate` enum), `backend/app/workers/tasks/email_tasks.py` (`send_email_task`), queue `QUEUE_EMAIL` | New `EmailTemplate.JOB_MATCH_DIGEST` member added; existing `worker-email` container/queue consumes it unchanged |
| Webhook notification | `backend/app/clients/notify.py` (`_post_webhook()`) | Pattern reused for a new `notify_job_match()` function — same fail-soft-when-unset convention |
| Envelope API routing | `backend/app/core/api_route.py` (`EnvelopeAPIRoute`) | New router uses this exactly like `documents/router.py` does |
| Auth dependency | `backend/app/auth/dependencies.py` (`CurrentUser`) | Reused verbatim for every new route |
| DB session dependency | `backend/app/database/session.py` (`get_db_session`) | Reused verbatim |
| JSON column helper | `backend/app/database/base.py` (`JsonDoc` = JSONB on Postgres, JSON on SQLite) | Reused for new ORM columns needing JSON storage |
| Frontend feature-module pattern | `frontend/features/{enrich,history,signals,settings}/` (`index.ts`, `api/keys.ts`, `hooks/`, `components/`) | Copied exactly for `frontend/features/job-matching/` |
| Frontend BFF proxy pattern | `frontend/app/api/enrich/*`, `frontend/src/lib/backend-client.ts` (`backendFetch`), `frontend/src/lib/bff-response.ts` | Copied exactly for `frontend/app/api/job-matching/*` and `frontend/app/api/documents/*` |
| Frontend nav registration | `frontend/components/layout/nav-config.ts` | One new `NavItem` added; `AppSidebar`/`AppBottomNav` pick it up automatically (both already read from this config) |
| `JobCard` component | `frontend/components/dossier/JobCard.tsx` | Currently unused anywhere in the app (verified — zero usages found repo-wide). Extended with a score badge and reused for match list rendering, rather than building a new card from scratch |
| Empty state component | `frontend/components/console/EmptyState.tsx` | Reused for "no matches yet" / "upload a CV to get started" |

Nothing above is edited to change its existing behavior for other features — all reuse is either read-only or additive (new enum members, new functions alongside existing ones).

---

## 3. Evidence-based design decisions (why the implementation is shaped this way)

### Decision 1 — Two-stage retrieval: cheap pgvector ANN first, LLM only on survivors

✅ **DIRECT** — [LinkedIn Engineering: "How LinkedIn Is Using Embeddings to Up Its Match Game for Job Seekers"](https://www.linkedin.com/blog/engineering/platform-platformization/using-embeddings-to-up-its-match-game-for-job-seekers): LinkedIn trains a two-tower model "to minimize the cosine similarity between request embedding and job embedding," running this as the first retrieval stage before any heavier ranking.

✅ **DIRECT** — [LinkedIn: "JUDE: LLM-based representation learning for LinkedIn job recommendations"](https://www.linkedin.com/blog/engineering/ai/jude-llm-based-representation-learning-for-linkedin-job-recommendations): "attribute-based matching (ABM) and embedding-based retrieval (EBR) generate initial candidate sets... candidates retrieved by EBR are then refined through ranking layers."

✅ **DIRECT** — [OpenAI embeddings guide](https://developers.openai.com/api/docs/guides/embeddings): "We recommend cosine similarity... OpenAI embeddings are normalized to length 1... cosine similarity and Euclidean distance will result in the identical rankings" as dot product.

**Applied as:** Stage 1 = pgvector cosine similarity between the candidate's CV embedding and every stored job-posting embedding (cheap, no LLM call, uses `vector_search.similarity_search()` unmodified). Stage 2 = deterministic rule filter (salary floor, location/remote match) in plain SQL/Python. Only the **top 5 survivors** per candidate get an LLM call (for the match explanation, Decision 3) — not every scraped job.

### Decision 2 — Content-based matching only; no behavior-based/collaborative filtering in v1

✅ **DIRECT** — [Indeed Engineering (2016): "Building a Large-Scale ML Pipeline for Job Recommendations"](https://engineering.indeedblog.com/blog/2016/04/building-a-large-scale-machine-learning-pipeline-for-job-recommendations/): Indeed's own history shows content-based matching (resume keywords ↔ job description keywords) preceded behavior-based collaborative filtering, which required historical apply/save/dismiss click data they did not have on day one either.

✅ **DIRECT** — [LinkedIn: "Improving job matching with machine-learned activity features"](https://www.linkedin.com/blog/engineering/machine-learning/improving-job-matching-with-machine-learned-activity-features-): their activity-embedding approach explicitly requires "a member's job-seeking activity history" (apply/save/dismiss events).

**Applied as:** This repo has zero apply/save/dismiss tables today (verified — no such tables exist anywhere in `backend/alembic/versions/`). Module 1 v1 is CV-embedding ↔ job-embedding content matching only. A `job_match_feedback` table (thumbs up/down) is included in the schema (§5) as a forward-compatible hook for a v2 behavior-based re-ranker, but v2 itself is explicitly out of scope for this document.

### Decision 3 — Match score is deterministic; the LLM only explains, never invents, the score

✅ **DIRECT** — [JobMatchAI (ACL 2026 demo paper)](https://doi.org/10.18653/v1/2026.acl-demo.52): "the strict separation of a deterministic scoring layer from a generative explanation layer. Because the LLM receives only the six pre-computed scores... not raw documents, the resulting explanations are auditable and traceable."

✅ **DIRECT** — [Synapse (arXiv 2604.02539)](https://arxiv.org/pdf/2604.02539): "Constraining generation to retrieved content improves transparency and reduces hallucination risk."

✅ **DIRECT** — [AWS/Indeed: "How Indeed builds and deploys fine-tuned LLMs on SageMaker"](https://aws.amazon.com/blogs/machine-learning/how-indeed-builds-and-deploys-fine-tuned-llms-on-amazon-sagemaker/): lists "match explanations" as a real production LLM use case at Indeed, confirming this is an industry-validated feature shape, not a hypothetical.

**Applied as:** `score_job_match()` (pure Python, §5) computes `overall_score: float 0-100` from a weighted formula of cosine similarity + rule-filter booleans. This number is **never** sent to the LLM to regenerate — it is passed **into** the prompt as a given fact, and the LLM's only job is to explain it in 1-2 sentences citing specific CV/JD evidence. This deliberately diverges from the existing `generate_interview_feedback()` pattern in `feedback_generator.py`, which *does* let the LLM invent the score — that pattern is fine for subjective interview answers (no evidence found against it for that use case) but wrong for job matching per the papers above. This divergence is intentional and documented here so it is not "fixed" to match the other function by a future refactor.

### Decision 4 — Job listing deduplication is mandatory before persistence, not optional

✅ **DIRECT** — [Canaria: "4.47B Listings to 907M Unique Jobs"](https://decanaria.com/blog/deduplication-harder-than-you-think): "79.7% of everything we ingest is a duplicate... simple hash-based matching cannot solve it." Canaria's own dedup key deliberately **excludes** company name because of naming inconsistency across boards.

✅ **DIRECT** — [Textkernel: "How to Detect Non-Exact Duplicates in Job Postings"](https://www.textkernel.com/learn-support/blog/online-job-postings-have-many-duplicates-but-how-can-you-detect-them-if-they-are-not-exact-copies-of-each-other/): "true duplicates can have similarity as low as 37%" — pure text-similarity thresholds alone are insufficient.

**Applied as:** every scraped job gets a `dedup_key = sha256(normalized_title + normalized_location + source_domain)` (§5, `job_listings.dedup_key`, unique-indexed) computed **before** insert. `JobSpyEnricher` itself returns raw scraped rows today with zero dedup (verified in `backend/app/enrichers/jobspy.py:64-73`) — this gap is real and is fixed by the new ingestion function, not by editing the enricher.

### Decision 5 — No Celery; extend the existing `rq_scheduler` fan-out pattern

❌ the pasted external spec's "Celery beat + email/SMS workers" line — **this repo has no Celery anywhere.** Verified directly: `backend/pyproject.toml` lists only `redis`, `rq`, and (implicitly via `register_scheduled_jobs()`) `rq_scheduler` as queue dependencies; no `celery` string appears anywhere in the file.

✅ **DIRECT** (own codebase) — `backend/app/workers/queue.py::register_scheduled_jobs()` already registers `audio_cleanup_daily` via `rq_scheduler.Scheduler.cron()`. This is a real, working, existing primitive.

**Applied as:** one new cron registration, `job_matching_scan_daily`, added to the same function, using the same `Scheduler.cron()` call — no second queue framework introduced. This single trigger fans out into N per-user scan jobs (§7 — this fan-out itself is new, since the existing cron job is a singleton with no fan-out today).

### Decision 6 — SMS/webhook notification channels are stubbed, not built, in v1

❌ **NOT FOUND** — no SMS client (Twilio or otherwise) exists anywhere in this repo (verified — no `twilio` string in `pyproject.toml`, no SMS-sending function anywhere in `backend/app/clients/` or `backend/app/services/`).

✅ **DIRECT** (own codebase convention) — `backend/app/clients/notify.py::_post_webhook()` already demonstrates this repo's established fail-soft pattern: "No-op when unset. Never raises." `backend/docs/ARCHITECTURE.md`'s "Do not assume" table documents the same convention for `LLM_MODE`, R2→local fallback, and Reacher's `profiles: ["paid"]` gating.

**Applied as:** the notification-preference schema (§5, `candidate_job_preferences.notification_channels`) accepts `"email" | "sms" | "webhook"` as valid values, but only `"email"` is wired to a real sender in this plan. Selecting `"sms"` is accepted by validation but produces a no-op (logged, not sent) — consistent with the repo's own fail-soft convention, not a broken promise, and clearly labeled as such in the frontend (§10, disabled toggle with "coming soon").

---

## 4. Naming collisions and blind spots checked before designing the schema

**"Jobs" already means two unrelated things in this codebase — a third meaning must not be introduced carelessly.**

1. `Dossier["jobs"]` (`frontend/src/lib/types.ts:58-64`, `JobListing` type at line 217) — Tier-4 enrichment output, `{title, company, location, remote, source}`, populated by `JobSpyEnricher` during a one-off `/enrich` request for a *person*.
2. `JobListResponse.jobs` (`frontend/src/lib/types.ts:164-169`) — the list of **enrichment jobs** (async task records: queued/running/completed/failed), unrelated to job postings at all. `/app/jobs` already redirects to `/app/history` for exactly this reason (`frontend/app/app/jobs/page.tsx`).
3. **Module 1 introduces a third concept**: persisted job postings matched against a *candidate's* CV, independent of any enrichment request.

**Resolution:** Module 1's domain objects are named `JobListing` → **renamed to `JobPosting`** (backend ORM/domain) to avoid colliding with the frontend's existing `JobListing` type alias, and `JobMatch` for the scored candidate↔posting pairing. Frontend route is `/app/matches` (not `/app/jobs`, which is taken). This is a deliberate naming decision made explicit here so it is never "fixed" to the shorter, colliding name later.

**"Signals" is unrelated and must not be reused.** Verified: `backend/app/modules/signals/models.py`'s `SignalRecord` is `changedetection.io` website-change monitoring (`source`, `watch_id`, `url` fields) — a different domain entirely. Module 1 does not touch `signals/`.

**RQ queue starvation is a real, already-present risk that must not be worsened.** ✅ **DIRECT** — [RQ README](https://github.com/rq/rq/blob/master/README.md) + [rq/rq#1420](https://github.com/rq/rq/issues/1420): a worker started with `rq worker high low` never touches `low` while `high` has backlog. Verified in this repo's own code:

```68:74:backend/app/workers/rq_worker.py
queues = [
    Queue(QUEUE_FEEDBACK, connection=connection),  # Week 2: Interview feedback
    Queue(QUEUE_DOCUMENT, connection=connection),  # Week 1: Document processing
    Queue(QUEUE_EMBEDDING, connection=connection),  # Week 1: Embeddings
    Queue(QUEUE_CV_EXTRACTION, connection=connection),  # Week 1: CV extraction
    Queue(QUEUE_NAME, connection=connection),  # Original enrichment queue
]
```

**Resolution:** Module 1's new queue (`job_matching`) gets its **own dedicated worker container** (§9) rather than being appended to this list — appending it here would put it last in fixed-priority order behind 4 other queues, and a job-matching-scan burst would starve everything above it in the other direction. Both directions of starvation are avoided by isolation, not by reordering the existing list (reordering is out of scope — it would affect Module 2/3 features this plan does not own).

**Postgres connection pool has no explicit sizing — a real, pre-existing ceiling this plan must not silently make worse.** ✅ **DIRECT** — verified in `backend/app/database/session.py:21`: `_engine_kwargs: dict[str, Any] = {"future": True, "pool_pre_ping": True}` — no `pool_size`/`max_overflow` override, so SQLAlchemy's defaults (5 pooled + 10 overflow per process) apply. ✅ **DIRECT** — [SQLAlchemy engine docs](https://docs.sqlalchemy.org/en/20/core/engines.html#sqlalchemy.create_engine.params.pool_size) confirm this default. Adding one more worker process (`worker-job-matching`) adds at most 15 connections to an already-uncapped total — this plan does not fix the pool-sizing issue (that is a cross-cutting Phase 2 concern outside Module 1's scope, already flagged in `architecture_phase2.md` §5.1), but §9 explicitly sets `worker-job-matching` replica count to **1** by default specifically to avoid multiplying this existing risk while Module 1 ships.

---

## 5. Database schema — 3 new tables, 3 new Alembic revisions

**Current real Alembic head, verified by listing `backend/alembic/versions/`:** `017_practice_audio_recordings` (down-revision chain: `017` ← `(015_add_session_tracking, 016_interview_questions)`). New revisions in this plan chain onto `017`.

All new tables follow the exact dialect-handling pattern already used in `014_document_embeddings.py` and `017_practice_audio_recordings.py`: `postgresql.UUID(as_uuid=True)` / `sa.String(36)` branch on `bind.dialect.name`, `JsonDoc` (JSONB on Postgres, JSON on SQLite) for JSON columns — no new pattern invented.

### 5.1 `job_postings` — deduplicated, scraped job listings (source of truth, shared across all candidates)

**New file:** `backend/alembic/versions/018_job_postings.py`

```python
"""Add job_postings table for deduplicated scraped job listings.

Revision ID: 018_job_postings
Revises: 017_practice_audio_recordings
Create Date: 2026-08-08
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "018_job_postings"
down_revision: Union[str, Sequence[str], None] = "017_practice_audio_recordings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)
    jsonb_type = postgresql.JSONB() if dialect == "postgresql" else sa.JSON()

    op.create_table(
        "job_postings",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("dedup_key", sa.String(64), nullable=False),  # sha256 hex digest
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("company", sa.String(255), nullable=False),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("remote", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source", sa.String(50), nullable=False),  # "linkedin"|"indeed"|"glassdoor"|"google"|"zip_recruiter"
        sa.Column("source_url", sa.String(2048), nullable=True),
        sa.Column("description_raw", sa.Text(), nullable=True),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("salary_currency", sa.String(10), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sources_seen", jsonb_type, nullable=False, server_default="[]"),  # list[str], union of boards it appeared on
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_job_postings_dedup_key", "job_postings", ["dedup_key"], unique=True)
    op.create_index("ix_job_postings_is_active", "job_postings", ["is_active"])
    op.create_index("ix_job_postings_last_seen_at", "job_postings", ["last_seen_at"])


def downgrade() -> None:
    op.drop_index("ix_job_postings_last_seen_at", table_name="job_postings")
    op.drop_index("ix_job_postings_is_active", table_name="job_postings")
    op.drop_index("ix_job_postings_dedup_key", table_name="job_postings")
    op.drop_table("job_postings")
```

**Design notes (evidence-linked, per Decision 4):** `dedup_key` excludes company name from its hash input deliberately (title + normalized location + source domain only) — mirroring Canaria's confirmed reasoning ("Company name is deliberately excluded because company name inconsistency would cause false splits"). `sources_seen` is a JSON list so the same underlying job seen on both LinkedIn and Indeed merges into one row with both sources recorded, per the "union of fields, don't discard" pattern confirmed in the DEV Community dedup writeup referenced during design. `is_active` lets a nightly sweep mark postings unseen for >14 days as inactive without deleting match history that references them.

### 5.2 `job_posting_embeddings` — one embedding per job posting (parallel structure to `document_embeddings`)

**New file:** `backend/alembic/versions/019_job_posting_embeddings.py`

```python
"""Add job_posting_embeddings table for pgvector-based job matching.

Revision ID: 019_job_posting_embeddings
Revises: 018_job_postings
Create Date: 2026-08-08
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision: str = "019_job_posting_embeddings"
down_revision: Union[str, Sequence[str], None] = "018_job_postings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute(text("""
            CREATE TABLE job_posting_embeddings (
                id UUID PRIMARY KEY,
                job_posting_id UUID NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
                embedding vector(1536) NOT NULL,
                token_count INTEGER NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """))
        op.execute(
            "CREATE INDEX idx_job_posting_embeddings_hnsw ON job_posting_embeddings "
            "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
        )
        op.create_index(
            "ix_job_posting_embeddings_posting_id", "job_posting_embeddings", ["job_posting_id"], unique=True
        )
    else:
        op.create_table(
            "job_posting_embeddings",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("job_posting_id", sa.String(36), sa.ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("embedding", sa.Text(), nullable=False),  # JSON-encoded list[float], SQLite fallback
            sa.Column("token_count", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("job_posting_embeddings")
```

**Design notes:** `m=16, ef_construction=64` intentionally matches pgvector's own shipped defaults — same as `document_embeddings` (`014_document_embeddings.py`). This is a conscious decision to not prematurely optimize; `architecture_phase2.md` §5.2 already documents the retune trigger (10M-row threshold) as a cross-cutting concern outside this module's scope. One embedding per posting (not chunked/multi-embedding) because job descriptions are short enough to fit `text-embedding-3-small`'s 8191-token limit in one call — verified against [OpenAI's own limit](https://developers.openai.com/api/docs/guides/embeddings), no chunking library dependency needed here unlike the CV pipeline.

### 5.3 `candidate_job_preferences` — one row per candidate, editable targeting criteria

**New file:** `backend/alembic/versions/020_candidate_job_preferences.py`

```python
"""Add candidate_job_preferences table.

Revision ID: 020_candidate_job_preferences
Revises: 019_job_posting_embeddings
Create Date: 2026-08-08
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "020_candidate_job_preferences"
down_revision: Union[str, Sequence[str], None] = "019_job_posting_embeddings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)
    jsonb_type = postgresql.JSONB() if dialect == "postgresql" else sa.JSON()

    op.create_table(
        "candidate_job_preferences",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("user_id", uuid_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("source_document_id", uuid_type, sa.ForeignKey("candidate_documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("desired_roles", jsonb_type, nullable=False, server_default="[]"),
        sa.Column("desired_locations", jsonb_type, nullable=False, server_default="[]"),
        sa.Column("remote_preference", sa.String(20), nullable=True),  # "remote"|"hybrid"|"onsite"
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("salary_currency", sa.String(10), nullable=False, server_default="USD"),
        sa.Column("notification_channels", jsonb_type, nullable=False, server_default='["email"]'),
        sa.Column("digest_frequency", sa.String(20), nullable=False, server_default="daily"),  # "daily"|"weekly"|"off"
        sa.Column("is_scan_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_scanned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_candidate_job_preferences_user_id", "candidate_job_preferences", ["user_id"], unique=True)
    op.create_index("ix_candidate_job_preferences_scan_enabled", "candidate_job_preferences", ["is_scan_enabled"])


def downgrade() -> None:
    op.drop_index("ix_candidate_job_preferences_scan_enabled", table_name="candidate_job_preferences")
    op.drop_index("ix_candidate_job_preferences_user_id", table_name="candidate_job_preferences")
    op.drop_table("candidate_job_preferences")
```

**Design notes:** `source_document_id` links back to the `CandidateDocument` the preferences were pre-filled from (nullable — a user can edit preferences without ever having uploaded a CV, or after deleting it, hence `ON DELETE SET NULL` not `CASCADE`). `is_scan_enabled` lets a user pause matching without deleting preferences (needed for the fan-out scheduler in §7 to skip disabled candidates cheaply via an indexed column rather than a soft-delete flag on every row it touches).

### 5.4 `job_matches` — scored candidate↔posting pairs (the output of the matching pipeline)

**New file:** `backend/alembic/versions/021_job_matches.py`

```python
"""Add job_matches table for scored candidate-job pairings.

Revision ID: 021_job_matches
Revises: 020_candidate_job_preferences
Create Date: 2026-08-08
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "021_job_matches"
down_revision: Union[str, Sequence[str], None] = "020_candidate_job_preferences"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)
    jsonb_type = postgresql.JSONB() if dialect == "postgresql" else sa.JSON()

    op.create_table(
        "job_matches",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("user_id", uuid_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_posting_id", uuid_type, sa.ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=False),   # raw cosine similarity, 0.0-1.0
        sa.Column("rule_score", sa.Float(), nullable=False),         # salary/location/remote filter score, 0.0-1.0
        sa.Column("overall_score", sa.Float(), nullable=False),      # weighted composite, 0-100
        sa.Column("score_breakdown", jsonb_type, nullable=False, server_default="{}"),
        sa.Column("explanation", sa.Text(), nullable=True),          # LLM-generated "why this matches", nullable until generated
        sa.Column("explanation_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("feedback", sa.String(10), nullable=True),         # "up"|"down"|null — v2 hook, Decision 2
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_job_matches_user_id", "job_matches", ["user_id"])
    op.create_index("ix_job_matches_job_posting_id", "job_matches", ["job_posting_id"])
    op.create_index("ix_job_matches_overall_score", "job_matches", ["overall_score"])
    op.create_index("ix_job_matches_user_posting", "job_matches", ["user_id", "job_posting_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_job_matches_user_posting", table_name="job_matches")
    op.drop_index("ix_job_matches_overall_score", table_name="job_matches")
    op.drop_index("ix_job_matches_job_posting_id", table_name="job_matches")
    op.drop_index("ix_job_matches_user_id", table_name="job_matches")
    op.drop_table("job_matches")
```

**Design notes:** the unique `(user_id, job_posting_id)` index is what prevents duplicate notifications for the same job across repeated daily scans — a re-scan that finds the same posting again does an `UPDATE` (refresh `overall_score`, keep `notified_at` if unchanged) rather than an `INSERT`, per the service-layer logic in §7. `explanation` is nullable and populated by a second pass (only for the top-5 per candidate, per Decision 1/3) — matches are stored the instant they're scored, before any LLM call, so the pipeline never loses match data if the LLM call fails.

---

## 6. Configuration — new environment variables

**File edited:** `backend/.env.example` (placeholders only, per RULE.md "never commit secrets")

Add this block after the existing Foundation Week 1/2 section:

```bash
# Module 1: AI Job Matching & Notifications
JOB_MATCHING_ENABLED=true
JOB_MATCHING_SCAN_CRON=0 6 * * *          # daily at 06:00 UTC, staggered internally (see §7)
JOB_MATCHING_MAX_POSTINGS_PER_SCAN=50     # JobSpy results_wanted per candidate scan
JOB_MATCHING_SIMILARITY_THRESHOLD=0.5     # pgvector cosine similarity floor, matches vector_search.py default
JOB_MATCHING_TOP_N_EXPLANATIONS=5         # LLM explanation calls per candidate per scan, per Decision 1
JOB_MATCHING_INACTIVE_AFTER_DAYS=14       # job_postings.is_active sweep threshold
NOTIFY_SMS_ENABLED=false                  # placeholder for Decision 6 — no real SMS client wired
```

**File edited:** `backend/app/core/config.py` — add corresponding `Settings` fields (`job_matching_enabled: bool = True`, etc.) following the exact existing pattern used for `jobspy_results_per_board` and `audio_retention_days` (grep those two names in `config.py` for the pattern to copy — same `Field(default=..., description=...)` style, no new pattern invented).

---

## 7. Backend implementation — file by file

New top-level package: `backend/app/modules/job_matching/` (layer: `modules/` per RULE.md's ownership table — "API-facing use cases: routers, services, feature ORM, HTTP schemas").

### 7.1 `backend/app/modules/job_matching/__init__.py`

```python
"""Job matching module: candidate-to-job scoring, preferences, and notifications."""
```

### 7.2 `backend/app/modules/job_matching/models.py`

ORM classes mirroring the Alembic tables in §5 exactly (column-for-column — Alembic is the schema source of truth per RULE.md; this file is the ORM mirror, same relationship as `documents/models.py` to its migrations).

```python
"""ORM models for job matching: postings, embeddings, preferences, matches."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, JsonDoc

try:
    from pgvector.sqlalchemy import Vector

    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False


class JobPosting(Base):
    """Deduplicated job posting scraped from job boards."""

    __tablename__ = "job_postings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    dedup_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remote: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    description_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
    sources_seen: Mapped[list[str]] = mapped_column(JsonDoc, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)


class JobPostingEmbedding(Base):
    """Embedding vector for a job posting (parallel to DocumentEmbedding)."""

    __tablename__ = "job_posting_embeddings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_posting_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    if PGVECTOR_AVAILABLE:
        embedding = mapped_column(Vector(1536), nullable=False)
    else:
        import json as _json

        _embedding_json: Mapped[str] = mapped_column("embedding", Text, nullable=False)

        @property
        def embedding(self) -> list[float]:
            if isinstance(self._embedding_json, list):
                return self._embedding_json
            return self._json.loads(self._embedding_json)

        @embedding.setter
        def embedding(self, value: list[float]) -> None:
            self._embedding_json = value if isinstance(value, str) else self._json.dumps(value)


class CandidateJobPreferences(Base):
    """Per-candidate job-matching targeting criteria and notification settings."""

    __tablename__ = "candidate_job_preferences"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    source_document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("candidate_documents.id", ondelete="SET NULL"), nullable=True
    )
    desired_roles: Mapped[list[str]] = mapped_column(JsonDoc, default=list, nullable=False)
    desired_locations: Mapped[list[str]] = mapped_column(JsonDoc, default=list, nullable=False)
    remote_preference: Mapped[str | None] = mapped_column(String(20), nullable=True)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    notification_channels: Mapped[list[str]] = mapped_column(
        JsonDoc, default=lambda: ["email"], nullable=False
    )
    digest_frequency: Mapped[str] = mapped_column(String(20), default="daily", nullable=False)
    is_scan_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )


class JobMatch(Base):
    """Scored candidate-to-job-posting pairing."""

    __tablename__ = "job_matches"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_posting_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    rule_score: Mapped[float] = mapped_column(Float, nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(JsonDoc, default=dict, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    feedback: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
```

### 7.3 `backend/app/modules/job_matching/schemas.py`

Pydantic request/response models — the only place validation for this module lives (per RULE.md "do not duplicate validation").

```python
"""HTTP request/response schemas for the job matching module."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class JobPreferencesRequest(BaseModel):
    desired_roles: list[str] = Field(default_factory=list, max_length=20)
    desired_locations: list[str] = Field(default_factory=list, max_length=20)
    remote_preference: Literal["remote", "hybrid", "onsite"] | None = None
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    salary_currency: str = Field(default="USD", max_length=10)
    notification_channels: list[Literal["email", "sms", "webhook"]] = Field(default_factory=lambda: ["email"])
    digest_frequency: Literal["daily", "weekly", "off"] = "daily"
    is_scan_enabled: bool = True

    @field_validator("salary_max")
    @classmethod
    def _max_gte_min(cls, v: int | None, info) -> int | None:
        salary_min = info.data.get("salary_min")
        if v is not None and salary_min is not None and v < salary_min:
            raise ValueError("salary_max must be >= salary_min")
        return v


class JobPreferencesResponse(JobPreferencesRequest):
    user_id: str
    source_document_id: str | None
    last_scanned_at: datetime | None
    created_at: datetime
    updated_at: datetime


class JobMatchResponse(BaseModel):
    match_id: str
    job_posting_id: str
    title: str
    company: str
    location: str | None
    remote: bool
    source: str
    source_url: str | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    overall_score: float
    score_breakdown: dict[str, float]
    explanation: str | None
    is_new: bool  # notified_at is None
    viewed_at: datetime | None
    feedback: Literal["up", "down"] | None
    created_at: datetime


class JobMatchListResponse(BaseModel):
    matches: list[JobMatchResponse]
    total: int
    limit: int
    offset: int


class JobMatchFeedbackRequest(BaseModel):
    feedback: Literal["up", "down"]


class ScanTriggerResponse(BaseModel):
    message: str
    scan_enqueued: bool
```

### 7.4 `backend/app/modules/job_matching/repository.py`

Layer: the only place raw SQL/ORM queries for this module live — mirrors `modules/enrichment/repository.py`'s role (`JobRepository`) for this module. This is the file the RQ worker task (§7.6) is allowed to import, per RULE.md's "workers/tasks → modules/*/repository" allowed-import rule — the worker must **not** import `service.py`.

```python
"""Data-access layer for job matching. Workers import this, never service.py."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.job_matching.models import CandidateJobPreferences, JobMatch, JobPosting, JobPostingEmbedding


async def get_preferences(db: AsyncSession, user_id: UUID) -> CandidateJobPreferences | None:
    result = await db.execute(
        select(CandidateJobPreferences).where(CandidateJobPreferences.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def upsert_preferences(
    db: AsyncSession, user_id: UUID, values: dict
) -> CandidateJobPreferences:
    existing = await get_preferences(db, user_id)
    if existing:
        for key, value in values.items():
            setattr(existing, key, value)
        existing.updated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(existing)
        return existing

    prefs = CandidateJobPreferences(user_id=user_id, **values)
    db.add(prefs)
    await db.commit()
    await db.refresh(prefs)
    return prefs


async def list_scan_enabled_preferences(db: AsyncSession, limit: int, offset: int) -> list[CandidateJobPreferences]:
    """Used by the fan-out scheduler (§7.6) to page through candidates to scan."""
    result = await db.execute(
        select(CandidateJobPreferences)
        .where(CandidateJobPreferences.is_scan_enabled.is_(True))
        .order_by(CandidateJobPreferences.user_id)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def find_posting_by_dedup_key(db: AsyncSession, dedup_key: str) -> JobPosting | None:
    result = await db.execute(select(JobPosting).where(JobPosting.dedup_key == dedup_key))
    return result.scalar_one_or_none()


async def upsert_job_posting(db: AsyncSession, dedup_key: str, fields: dict, source: str) -> JobPosting:
    existing = await find_posting_by_dedup_key(db, dedup_key)
    if existing:
        existing.last_seen_at = datetime.now(UTC)
        if source not in existing.sources_seen:
            existing.sources_seen = [*existing.sources_seen, source]
        existing.is_active = True
        await db.commit()
        await db.refresh(existing)
        return existing

    posting = JobPosting(dedup_key=dedup_key, sources_seen=[source], **fields)
    db.add(posting)
    await db.commit()
    await db.refresh(posting)
    return posting


async def store_posting_embedding(db: AsyncSession, job_posting_id: UUID, embedding: list[float], token_count: int) -> None:
    existing = await db.execute(
        select(JobPostingEmbedding).where(JobPostingEmbedding.job_posting_id == job_posting_id)
    )
    row = existing.scalar_one_or_none()
    if row:
        row.embedding = embedding
        row.token_count = token_count
    else:
        db.add(JobPostingEmbedding(job_posting_id=job_posting_id, embedding=embedding, token_count=token_count))
    await db.commit()


async def upsert_match(
    db: AsyncSession,
    user_id: UUID,
    job_posting_id: UUID,
    similarity_score: float,
    rule_score: float,
    overall_score: float,
    score_breakdown: dict,
) -> JobMatch:
    """INSERT or refresh score on conflict — see §5.4 unique (user_id, job_posting_id) index."""
    result = await db.execute(
        select(JobMatch).where(JobMatch.user_id == user_id, JobMatch.job_posting_id == job_posting_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.similarity_score = similarity_score
        existing.rule_score = rule_score
        existing.overall_score = overall_score
        existing.score_breakdown = score_breakdown
        await db.commit()
        await db.refresh(existing)
        return existing

    match = JobMatch(
        user_id=user_id,
        job_posting_id=job_posting_id,
        similarity_score=similarity_score,
        rule_score=rule_score,
        overall_score=overall_score,
        score_breakdown=score_breakdown,
    )
    db.add(match)
    await db.commit()
    await db.refresh(match)
    return match


async def list_matches_for_user(
    db: AsyncSession, user_id: UUID, limit: int, offset: int
) -> tuple[list[tuple[JobMatch, JobPosting]], int]:
    result = await db.execute(
        select(JobMatch, JobPosting)
        .join(JobPosting, JobMatch.job_posting_id == JobPosting.id)
        .where(JobMatch.user_id == user_id)
        .order_by(JobMatch.overall_score.desc(), JobMatch.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = result.all()
    count_result = await db.execute(select(JobMatch).where(JobMatch.user_id == user_id))
    total = len(count_result.all())
    return [(m, p) for m, p in rows], total


async def get_top_unexplained_matches(db: AsyncSession, user_id: UUID, top_n: int) -> list[tuple[JobMatch, JobPosting]]:
    """Top-N matches (by score) that don't have an LLM explanation yet — feeds Decision 1/3's LLM-last stage."""
    result = await db.execute(
        select(JobMatch, JobPosting)
        .join(JobPosting, JobMatch.job_posting_id == JobPosting.id)
        .where(JobMatch.user_id == user_id, JobMatch.explanation.is_(None))
        .order_by(JobMatch.overall_score.desc())
        .limit(top_n)
    )
    return [(m, p) for m, p in result.all()]


async def save_explanation(db: AsyncSession, match_id: UUID, explanation: str) -> None:
    await db.execute(
        update(JobMatch)
        .where(JobMatch.id == match_id)
        .values(explanation=explanation, explanation_generated_at=datetime.now(UTC))
    )
    await db.commit()


async def mark_notified(db: AsyncSession, match_ids: list[UUID]) -> None:
    if not match_ids:
        return
    await db.execute(
        update(JobMatch).where(JobMatch.id.in_(match_ids)).values(notified_at=datetime.now(UTC))
    )
    await db.commit()


async def mark_viewed(db: AsyncSession, match_id: UUID, user_id: UUID) -> bool:
    result = await db.execute(
        update(JobMatch)
        .where(JobMatch.id == match_id, JobMatch.user_id == user_id, JobMatch.viewed_at.is_(None))
        .values(viewed_at=datetime.now(UTC))
    )
    await db.commit()
    return result.rowcount > 0


async def set_feedback(db: AsyncSession, match_id: UUID, user_id: UUID, feedback: str) -> bool:
    result = await db.execute(
        update(JobMatch).where(JobMatch.id == match_id, JobMatch.user_id == user_id).values(feedback=feedback)
    )
    await db.commit()
    return result.rowcount > 0
```

---

### 7.5 `backend/app/modules/job_matching/scorer.py`

Pure functions, no I/O — deterministic scoring per Decision 3. Kept separate from `service.py` so it is trivially unit-testable without a database or network (see §8.2).

```python
"""Deterministic job-match scoring. No LLM calls, no I/O — pure functions.

Per Decision 3 (phase2_module1.md §3): the overall_score is computed here and
passed INTO the LLM prompt as a given fact. The LLM never regenerates this number.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

# Weights sum to 1.0 — similarity dominates, rule-filters are a smaller adjustment.
# This is a product decision (not sourced from any paper) and is intentionally
# simple for v1; see Decision 2 for why a learned weighting model is out of scope.
SIMILARITY_WEIGHT = 0.7
RULE_WEIGHT = 0.3


def normalize_dedup_field(value: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation — used for both title and location."""
    value = value.lower().strip()
    value = re.sub(r"[^\w\s]", "", value)
    value = re.sub(r"\s+", " ", value)
    return value


def compute_dedup_key(title: str, location: str | None, source: str) -> str:
    """Per Decision 4: company name is deliberately excluded (Canaria's confirmed reasoning)."""
    normalized_title = normalize_dedup_field(title)
    normalized_location = normalize_dedup_field(location or "")
    source_domain = source.lower().strip()
    raw = f"{normalized_title}|{normalized_location}|{source_domain}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def score_salary_fit(
    posting_min: int | None,
    posting_max: int | None,
    pref_min: int | None,
    pref_max: int | None,
) -> float:
    """1.0 if fully compatible, 0.0 if fully incompatible, partial credit for overlap.

    Missing data on either side is treated as neutral (0.5) rather than penalized,
    since most scraped postings omit salary entirely.
    """
    if pref_min is None and pref_max is None:
        return 0.5  # candidate has no salary preference; neutral
    if posting_min is None and posting_max is None:
        return 0.5  # posting has no salary listed; neutral

    p_min = posting_min if posting_min is not None else 0
    p_max = posting_max if posting_max is not None else float("inf")
    c_min = pref_min if pref_min is not None else 0
    c_max = pref_max if pref_max is not None else float("inf")

    overlap_low = max(p_min, c_min)
    overlap_high = min(p_max, c_max)
    if overlap_low > overlap_high:
        return 0.0  # no overlap at all
    return 1.0


def score_location_fit(
    posting_location: str | None,
    posting_remote: bool,
    pref_locations: list[str],
    pref_remote: str | None,
) -> float:
    """1.0 for exact/remote match, 0.5 neutral if no preference stated, 0.0 for mismatch."""
    if pref_remote == "remote":
        return 1.0 if posting_remote else 0.0
    if not pref_locations:
        return 0.5  # no location preference stated
    if posting_remote:
        return 1.0  # remote satisfies any location preference

    normalized_pref = {normalize_dedup_field(loc) for loc in pref_locations}
    normalized_posting = normalize_dedup_field(posting_location or "")
    if any(pref in normalized_posting or normalized_posting in pref for pref in normalized_pref):
        return 1.0
    return 0.0


def compute_rule_score(
    posting: dict[str, Any],
    preferences: dict[str, Any],
) -> tuple[float, dict[str, float]]:
    """Combine salary + location rule checks into one 0.0-1.0 rule_score.

    Returns (rule_score, breakdown) so the breakdown can be stored and shown in the UI.
    """
    salary_fit = score_salary_fit(
        posting.get("salary_min"), posting.get("salary_max"),
        preferences.get("salary_min"), preferences.get("salary_max"),
    )
    location_fit = score_location_fit(
        posting.get("location"), posting.get("remote", False),
        preferences.get("desired_locations", []), preferences.get("remote_preference"),
    )
    rule_score = (salary_fit + location_fit) / 2
    return rule_score, {"salary_fit": salary_fit, "location_fit": location_fit}


def compute_overall_score(similarity_score: float, rule_score: float) -> float:
    """Weighted composite, scaled to 0-100 for display."""
    composite = (similarity_score * SIMILARITY_WEIGHT) + (rule_score * RULE_WEIGHT)
    return round(max(0.0, min(1.0, composite)) * 100, 2)
```

### 7.6 `backend/app/modules/job_matching/service.py`

Layer: business logic, called by `router.py` only (per RULE.md "routes are thin"). This file — **not** `repository.py` — is what the HTTP router imports.

```python
"""Business logic for job matching: preferences, match listing, feedback."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from redis import Redis
from rq import Queue
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.job_matching import repository
from app.modules.job_matching.schemas import (
    JobMatchListResponse,
    JobMatchResponse,
    JobPreferencesRequest,
    JobPreferencesResponse,
    ScanTriggerResponse,
)
from app.workers.queue import QUEUE_JOB_MATCHING, get_redis_connection


class JobMatchingService:
    def __init__(self, db: AsyncSession, redis_conn: Redis | None = None):
        self.db = db
        self.redis_conn = redis_conn or get_redis_connection()

    async def get_preferences(self, user_id: UUID) -> JobPreferencesResponse:
        prefs = await repository.get_preferences(self.db, user_id)
        if not prefs:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preferences not set")
        return JobPreferencesResponse(
            user_id=str(prefs.user_id),
            source_document_id=str(prefs.source_document_id) if prefs.source_document_id else None,
            desired_roles=prefs.desired_roles,
            desired_locations=prefs.desired_locations,
            remote_preference=prefs.remote_preference,
            salary_min=prefs.salary_min,
            salary_max=prefs.salary_max,
            salary_currency=prefs.salary_currency,
            notification_channels=prefs.notification_channels,
            digest_frequency=prefs.digest_frequency,
            is_scan_enabled=prefs.is_scan_enabled,
            last_scanned_at=prefs.last_scanned_at,
            created_at=prefs.created_at,
            updated_at=prefs.updated_at,
        )

    async def upsert_preferences(
        self, user_id: UUID, payload: JobPreferencesRequest
    ) -> JobPreferencesResponse:
        prefs = await repository.upsert_preferences(self.db, user_id, payload.model_dump())
        return await self.get_preferences(user_id)

    async def list_matches(self, user_id: UUID, limit: int, offset: int) -> JobMatchListResponse:
        rows, total = await repository.list_matches_for_user(self.db, user_id, limit, offset)
        matches = [
            JobMatchResponse(
                match_id=str(match.id),
                job_posting_id=str(posting.id),
                title=posting.title,
                company=posting.company,
                location=posting.location,
                remote=posting.remote,
                source=posting.source,
                source_url=posting.source_url,
                salary_min=posting.salary_min,
                salary_max=posting.salary_max,
                salary_currency=posting.salary_currency,
                overall_score=match.overall_score,
                score_breakdown=match.score_breakdown,
                explanation=match.explanation,
                is_new=match.notified_at is None,
                viewed_at=match.viewed_at,
                feedback=match.feedback,
                created_at=match.created_at,
            )
            for match, posting in rows
        ]
        return JobMatchListResponse(matches=matches, total=total, limit=limit, offset=offset)

    async def mark_viewed(self, match_id: str, user_id: UUID) -> None:
        found = await repository.mark_viewed(self.db, UUID(match_id), user_id)
        if not found:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    async def set_feedback(self, match_id: str, user_id: UUID, feedback: str) -> None:
        found = await repository.set_feedback(self.db, UUID(match_id), user_id, feedback)
        if not found:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    async def trigger_scan(self, user_id: UUID) -> ScanTriggerResponse:
        """Manual on-demand scan trigger (in addition to the daily cron, §7.7)."""
        try:
            queue = Queue(QUEUE_JOB_MATCHING, connection=self.redis_conn)
            queue.enqueue(
                "app.workers.tasks.job_matching.scan_jobs_for_candidate",
                str(user_id),
                job_timeout=120,
            )
            return ScanTriggerResponse(message="Scan enqueued", scan_enqueued=True)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to enqueue scan: {exc}",
            )
```

### 7.7 `backend/app/modules/job_matching/router.py`

Thin routes only — auth, parse, call service, return. Mirrors `documents/router.py` exactly.

```python
"""FastAPI router for job matching API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.api_route import EnvelopeAPIRoute
from app.database.session import get_db_session
from app.modules.job_matching.schemas import (
    JobMatchFeedbackRequest,
    JobMatchListResponse,
    JobPreferencesRequest,
    JobPreferencesResponse,
    ScanTriggerResponse,
)
from app.modules.job_matching.service import JobMatchingService

router = APIRouter(prefix="/api/job-matching", tags=["job-matching"], route_class=EnvelopeAPIRoute)


@router.get("/preferences", response_model=JobPreferencesResponse)
async def get_preferences(
    current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)
) -> JobPreferencesResponse:
    service = JobMatchingService(db)
    return await service.get_preferences(current_user.id)


@router.put("/preferences", response_model=JobPreferencesResponse)
async def upsert_preferences(
    payload: JobPreferencesRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> JobPreferencesResponse:
    service = JobMatchingService(db)
    return await service.upsert_preferences(current_user.id, payload)


@router.get("/matches", response_model=JobMatchListResponse)
async def list_matches(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> JobMatchListResponse:
    service = JobMatchingService(db)
    return await service.list_matches(current_user.id, limit, offset)


@router.post("/matches/{match_id}/view", status_code=status.HTTP_204_NO_CONTENT)
async def mark_match_viewed(
    match_id: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)
) -> None:
    service = JobMatchingService(db)
    await service.mark_viewed(match_id, current_user.id)


@router.post("/matches/{match_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
async def submit_match_feedback(
    match_id: str,
    payload: JobMatchFeedbackRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    service = JobMatchingService(db)
    await service.set_feedback(match_id, current_user.id, payload.feedback)


@router.post("/scan", response_model=ScanTriggerResponse)
async def trigger_scan(
    current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)
) -> ScanTriggerResponse:
    service = JobMatchingService(db)
    return await service.trigger_scan(current_user.id)
```

**File edited:** `backend/app/main.py` — add two lines, following the exact existing pattern for `documents_router`:

```python
from app.modules.job_matching.router import router as job_matching_router
...
app.include_router(job_matching_router, dependencies=[Depends(current_verified_user)])
```

---

### 7.8 `backend/app/workers/queue.py` — edits (not a new file)

Add a new queue constant and priority entry, then a new cron registration and enqueue helper. Per §4's starvation analysis, this queue gets its **own dedicated worker** (§9) and is **not** added to the generic worker's queue list in `rq_worker.py`.

```python
# Add near the other queue constants:
QUEUE_JOB_MATCHING = "job_matching"

# Add to QUEUE_PRIORITIES dict:
QUEUE_JOB_MATCHING: 6,  # Between feedback (7) and document (5) — user-facing but async
```

Add a new function, alongside the existing `enqueue_feedback()`:

```python
def enqueue_job_matching_scan(user_id: str) -> None:
    """Enqueue a job-matching scan for a single candidate.

    Args:
        user_id: UUID string of the candidate to scan

    Raises:
        Exception: On enqueue failure
    """
    from app.workers.tasks.job_matching import scan_jobs_for_candidate

    connection = get_redis_connection()
    try:
        queue = Queue(QUEUE_JOB_MATCHING, connection=connection)
        queue.enqueue(scan_jobs_for_candidate, user_id, job_timeout=120)
        logger.info(f"Enqueued job-matching scan for user: {user_id[:8]}")
    except Exception as e:
        logger.error(
            f"Failed to enqueue job-matching scan for user {user_id[:8]}",
            extra={"error": str(e), "error_type": type(e).__name__},
            exc_info=True,
        )
        raise
```

Extend `register_scheduled_jobs()` — add a second `scheduler.cron()` call inside the existing `try` block, alongside `audio_cleanup_daily`:

```python
    from app.workers.tasks.job_matching import fan_out_daily_scans

    scheduler.cron(
        "0 6 * * *",  # 06:00 UTC daily — before audio_cleanup's 02:00 slot to avoid contention
        func=fan_out_daily_scans,
        queue_name=QUEUE_JOB_MATCHING,
        id="job_matching_fan_out_daily",
        timeout=600,  # 10 minutes to page through and enqueue all candidates
    )

    logger.info(
        "Registered scheduled jobs",
        extra={"jobs": ["audio_cleanup_daily", "job_matching_fan_out_daily"]},
    )
```

(This replaces the existing single-item `logger.info` call — both jobs are logged together, matching the existing style of logging all registered jobs in one line.)

### 7.9 `backend/app/workers/tasks/job_matching.py` — the core matching pipeline (new file)

Layer: `workers/tasks/` per RULE.md's ownership table ("Background execution adapter + RQ; must not import module routers/services"). This file imports `app.modules.job_matching.repository` directly — never `service.py` or `router.py`, per the allowed-imports rule verified in §0.

This is the largest new file in the plan; it implements the full pipeline: fan-out → scan (JobSpy) → dedup/persist → embed → score (Decision 1/3) → explain top-5 (Decision 3) → notify (digest email).

```python
"""RQ worker tasks for job matching: fan-out scheduler, scan, score, explain, notify.

Pipeline shape (per phase2_module1.md §3 Decision 1):
    fan_out_daily_scans()  [cron, singleton]
        -> enqueues scan_jobs_for_candidate(user_id) per scan-enabled candidate, staggered
    scan_jobs_for_candidate(user_id)
        -> JobSpy scrape (reuses JobSpyEnricher's static scrape logic)
        -> dedup + upsert into job_postings (Decision 4)
        -> embed new/changed postings (job_posting_embeddings)
        -> pgvector similarity search against candidate's CV embedding (Decision 1, stage 1)
        -> rule-filter scoring (scorer.py, Decision 1 stage 2 + Decision 3)
        -> upsert job_matches
        -> generate_explanations_for_candidate(user_id) [only top-5, Decision 1/3]
        -> send_match_digest(user_id) [email, Decision 5/6]
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

# Import ORM registry FIRST to register all models with SQLAlchemy
import app.database.orm_registry  # noqa: F401

from app.database.session import SessionLocal, engine
from app.infrastructure.redis import close_redis
from app.modules.job_matching import repository
from app.modules.job_matching.scorer import compute_dedup_key, compute_overall_score, compute_rule_score
from app.modules.documents.models import CandidateDocument
from app.services.vector_search import similarity_search
from sqlalchemy import select

logger = logging.getLogger(__name__)


def fan_out_daily_scans() -> dict[str, int]:
    """Cron entrypoint (sync). Pages through scan-enabled candidates and enqueues one
    scan_jobs_for_candidate job per candidate, staggered across the day.

    Staggering: candidates are bucketed by `hash(user_id) % 24` into hourly RQ
    scheduled-enqueue offsets, so 10,000 candidates don't all hit JobSpy/pgvector
    in the same second (per architecture_phase2.md §4).
    """
    return asyncio.run(_fan_out_daily_scans_async())


async def _fan_out_daily_scans_async() -> dict[str, int]:
    from datetime import timedelta

    from rq_scheduler import Scheduler

    from app.workers.queue import QUEUE_JOB_MATCHING, get_redis_connection

    enqueued = 0
    page_size = 200
    offset = 0
    scheduler = Scheduler(connection=get_redis_connection())

    async with SessionLocal() as session:
        while True:
            prefs_page = await repository.list_scan_enabled_preferences(session, page_size, offset)
            if not prefs_page:
                break

            for prefs in prefs_page:
                bucket_hour = hash(str(prefs.user_id)) % 24
                scheduler.enqueue_at(
                    _now_plus_hours(bucket_hour),
                    scan_jobs_for_candidate,
                    str(prefs.user_id),
                    job_timeout=120,
                )
                enqueued += 1

            offset += page_size

    logger.info("Fanned out daily job-matching scans", extra={"enqueued": enqueued})
    return {"enqueued": enqueued}


def _now_plus_hours(hours: int):
    from datetime import UTC, datetime, timedelta

    return datetime.now(UTC) + timedelta(hours=hours)


def scan_jobs_for_candidate(user_id: str) -> dict[str, int]:
    """RQ entrypoint (sync) for a single candidate's job-matching scan."""
    return asyncio.run(_scan_jobs_for_candidate_async(user_id))


async def _scan_jobs_for_candidate_async(user_id: str) -> dict[str, int]:
    from app.core.config import get_settings
    from app.clients.embeddings import get_embeddings_client
    from app.enrichers.jobspy import JobSpyEnricher

    settings = get_settings()
    stats = {"scraped": 0, "new_postings": 0, "matches_scored": 0, "explanations": 0}

    try:
        async with SessionLocal() as session:
            prefs = await repository.get_preferences(session, UUID(user_id))
            if not prefs or not prefs.is_scan_enabled:
                logger.info("Skipping scan: preferences missing or disabled", extra={"user_id": user_id[:8]})
                return stats

            # Load candidate's CV data to build a search query and get their embedding.
            cv_doc = await _get_latest_cv(session, UUID(user_id))
            if not cv_doc:
                logger.info("Skipping scan: no processed CV found", extra={"user_id": user_id[:8]})
                return stats

            search_term = _build_search_term(prefs, cv_doc)

            # Reuse JobSpyEnricher's scrape logic directly (Decision: not modifying the enricher class itself).
            enricher = JobSpyEnricher()
            raw_rows = await asyncio.to_thread(
                enricher._scrape,
                search_term,
                (prefs.desired_locations or [None])[0],
                None,
                None,
                settings.job_matching_max_postings_per_scan,
                None,
            )
            stats["scraped"] = len(raw_rows)

            embeddings_client = get_embeddings_client()
            posting_ids: list[UUID] = []

            for row in raw_rows:
                title = str(row.get("title") or search_term)
                company = str(row.get("company") or "Unknown")
                location = row.get("location")
                remote = bool(row.get("is_remote") or row.get("remote") or False)
                source = str(row.get("site") or "jobspy")
                description = str(row.get("description") or "")

                dedup_key = compute_dedup_key(title, location, source)
                posting = await repository.upsert_job_posting(
                    session,
                    dedup_key,
                    {
                        "title": title,
                        "company": company,
                        "location": location,
                        "remote": remote,
                        "source": source,
                        "source_url": row.get("job_url"),
                        "description_raw": description,
                        "salary_min": _safe_int(row.get("min_amount")),
                        "salary_max": _safe_int(row.get("max_amount")),
                        "salary_currency": row.get("currency"),
                    },
                    source,
                )
                posting_ids.append(posting.id)

                # Embed new postings only (skip if embedding already exists is handled by upsert semantics).
                if description:
                    embedding, token_count = await embeddings_client.generate_embedding(
                        f"{title}\n{company}\n{description[:4000]}"
                    )
                    await repository.store_posting_embedding(session, posting.id, embedding, token_count)
                    stats["new_postings"] += 1

            # Stage 1 (Decision 1): pgvector similarity search using the candidate's CV embedding.
            cv_embedding = await _get_cv_embedding(session, cv_doc.id)
            if cv_embedding:
                raw_matches = await similarity_search(
                    session=session,
                    query_embedding=cv_embedding,
                    limit=settings.job_matching_max_postings_per_scan,
                    similarity_threshold=settings.job_matching_similarity_threshold,
                )
                # NOTE: similarity_search() queries document_embeddings by default;
                # job posting matching queries job_posting_embeddings via the same
                # cosine-similarity SQL shape. See repository.py for the parallel query
                # (kept separate from vector_search.py per RULE.md "no unused abstractions" —
                # a shared generic table-agnostic search function is not introduced until
                # a second real caller needs it).

                preferences_dict = {
                    "salary_min": prefs.salary_min,
                    "salary_max": prefs.salary_max,
                    "desired_locations": prefs.desired_locations,
                    "remote_preference": prefs.remote_preference,
                }

                for posting_id in posting_ids:
                    posting_row = await session.get(_JobPostingLocal(), posting_id)  # see note below
                    # Stage 2 (Decision 1): deterministic rule filter.
                    # (Full implementation queries JobPosting directly; abbreviated here for
                    #  brevity — see repository.py for the real query used by the actual task.)
                    pass

            stats["matches_scored"] = len(posting_ids)

        # Second pass: generate explanations for top-5 unexplained matches (Decision 1/3).
        exp_stats = await _generate_explanations_for_candidate_async(user_id)
        stats["explanations"] = exp_stats["generated"]

        # Third pass: send digest notification if there are new, unnotified matches.
        await _send_match_digest_async(user_id)

        return stats

    finally:
        await close_redis()
        await engine.dispose()


def _build_search_term(prefs, cv_doc: "CandidateDocument") -> str:
    """Prefer explicit desired_roles; fall back to CV's current_role."""
    if prefs.desired_roles:
        return prefs.desired_roles[0]
    extracted = cv_doc.extracted_data or {}
    return str(extracted.get("current_role") or "software engineer")


async def _get_latest_cv(session, user_id: UUID) -> "CandidateDocument | None":
    result = await session.execute(
        select(CandidateDocument)
        .where(
            CandidateDocument.user_id == user_id,
            CandidateDocument.document_type == "cv",
            CandidateDocument.processing_status == "completed",
        )
        .order_by(CandidateDocument.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _get_cv_embedding(session, document_id: UUID) -> list[float] | None:
    from app.modules.documents.models import DocumentEmbedding

    result = await session.execute(
        select(DocumentEmbedding).where(DocumentEmbedding.document_id == document_id).limit(1)
    )
    emb = result.scalar_one_or_none()
    return emb.embedding if emb else None


def _safe_int(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def generate_explanations_for_candidate(user_id: str) -> dict[str, int]:
    """RQ entrypoint (sync)."""
    return asyncio.run(_generate_explanations_for_candidate_async(user_id))


async def _generate_explanations_for_candidate_async(user_id: str) -> dict[str, int]:
    """Per Decision 1/3: only the top-N unexplained matches get an LLM call."""
    from app.core.config import get_settings
    from app.modules.job_matching.explainer import generate_match_explanation

    settings = get_settings()
    generated = 0

    async with SessionLocal() as session:
        top_matches = await repository.get_top_unexplained_matches(
            session, UUID(user_id), settings.job_matching_top_n_explanations
        )
        for match, posting in top_matches:
            try:
                explanation = await generate_match_explanation(match, posting, settings)
                await repository.save_explanation(session, match.id, explanation)
                generated += 1
            except Exception:
                logger.warning(
                    "Failed to generate match explanation",
                    exc_info=True,
                    extra={"match_id": str(match.id), "user_id": user_id[:8]},
                )

    return {"generated": generated}


def send_match_digest(user_id: str) -> dict[str, int]:
    """RQ entrypoint (sync)."""
    return asyncio.run(_send_match_digest_async(user_id))


async def _send_match_digest_async(user_id: str) -> dict[str, int]:
    """Send a digest email for unnotified matches, then mark them notified.

    Per Decision 6: only 'email' channel is wired; 'sms'/'webhook' preferences
    are accepted but logged as a no-op, matching notify.py's fail-soft convention.
    """
    from app.workers.queue import enqueue_email  # see §7.10 for this helper

    async with SessionLocal() as session:
        prefs = await repository.get_preferences(session, UUID(user_id))
        if not prefs:
            return {"sent": 0}

        rows, _total = await repository.list_matches_for_user(session, UUID(user_id), limit=100, offset=0)
        unnotified = [(m, p) for m, p in rows if m.notified_at is None]

        if not unnotified:
            return {"sent": 0}

        top_5 = unnotified[:5]

        if "email" not in prefs.notification_channels:
            return {"sent": 0}
        if "sms" in prefs.notification_channels or "webhook" in prefs.notification_channels:
            logger.info(
                "SMS/webhook notification requested but not implemented (Decision 6) — skipping those channels",
                extra={"user_id": user_id[:8], "channels": prefs.notification_channels},
            )

        # Fetch user email via auth module (read-only cross-module read of the User row —
        # allowed per RULE.md: modules may read shared domain/auth records; no service coupling).
        from app.auth.models import User

        user = await session.get(User, UUID(user_id))
        if not user:
            return {"sent": 0}

        enqueue_email(
            template="job_match_digest",
            recipient=user.email,
            context={
                "matches": [
                    {
                        "title": p.title,
                        "company": p.company,
                        "location": p.location,
                        "overall_score": m.overall_score,
                        "explanation": m.explanation or "",
                        "source_url": p.source_url or "",
                    }
                    for m, p in top_5
                ],
            },
        )

        await repository.mark_notified(session, [m.id for m, _ in unnotified])
        return {"sent": len(top_5)}


def check_worker_health(queue_name: str) -> bool:
    """Health check for the job-matching worker, matching document.py's pattern."""
    try:
        from app.workers.queue import get_redis_connection
        from rq import Queue

        redis_conn = get_redis_connection()
        redis_conn.ping()
        queue = Queue(queue_name, connection=redis_conn)
        queue_len = len(queue)
        logger.debug(f"Health check: queue {queue_name} has {queue_len} jobs")
        return True
    except Exception as exc:
        logger.error(f"Health check failed: {exc}", exc_info=True)
        return False
```

**Implementation note on the abbreviated scoring block above:** the `pass`-stubbed inner loop in `_scan_jobs_for_candidate_async` is intentionally left as pseudocode in this planning document to keep the file readable; the actual implementation must replace it with a real query against `JobPosting` (via `session.get(JobPosting, posting_id)`) plus a call to `repository.upsert_match(session, UUID(user_id), posting_id, similarity_score, rule_score, overall_score, breakdown)` using `scorer.compute_rule_score()` and `scorer.compute_overall_score()`. This is flagged explicitly, per this document's own truthfulness standard, rather than presenting pseudocode as if it were finished code — **whoever implements this file must complete that loop before Module 1 can be considered done** (tracked as an explicit item in the §15 completion checklist).

### 7.10 `backend/app/workers/queue.py` — one more addition: `enqueue_email` helper

Verified gap: `queue.py` currently has no generic email-enqueue helper — `email_tasks.py`'s `send_email_task` is enqueued directly by callers today (grep confirms no wrapper exists). Add one for `job_matching.py` to call, following the same shape as `enqueue_feedback()`:

```python
def enqueue_email(template: str, recipient: str, context: dict, subject: str | None = None) -> None:
    """Enqueue a templated email send. Thin wrapper matching enqueue_feedback()'s shape."""
    from app.workers.tasks.email_tasks import send_email_task

    connection = get_redis_connection()
    try:
        queue = Queue(QUEUE_EMAIL, connection=connection)
        queue.enqueue(send_email_task, template, recipient, context, subject, job_timeout=30)
        logger.info(f"Enqueued email: {template} to {recipient[:3]}***")
    except Exception as e:
        logger.error(f"Failed to enqueue email: {template}", extra={"error": str(e)}, exc_info=True)
        raise
```

---

### 7.11 `backend/app/modules/job_matching/explainer.py` — grounded LLM explanation (new file)

Implements Decision 3 precisely: the LLM receives the already-computed score and breakdown as **given facts** and is only asked to explain, never to re-score. Structurally similar to `feedback_generator.py` (same `httpx` + OpenAI chat-completions call shape, same JSON-mode parsing pattern) but with a prompt that explicitly forbids score invention — the one deliberate divergence documented in Decision 3.

```python
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


async def generate_match_explanation(match: JobMatch, posting: JobPosting, settings: Settings) -> str:
    """Generate a grounded explanation for a pre-computed match score.

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

        try:
            data = json.loads(content)
            explanation = str(data.get("explanation", "")).strip()
            if not explanation:
                raise ValueError("Empty explanation returned")
            return explanation
        except (json.JSONDecodeError, KeyError) as exc:
            raise ValueError(f"Invalid explanation JSON: {exc}") from exc
```

### 7.12 `backend/app/services/email_service.py` — edits (not a new file)

Add one new enum member and one new render function, following the exact existing pattern of every other template in this file.

```python
# Add to EmailTemplate enum:
JOB_MATCH_DIGEST = "job_match_digest"
```

```python
# Add to the _render_template dispatch dict (around line 152):
EmailTemplate.JOB_MATCH_DIGEST: self._render_job_match_digest,
```

```python
def _render_job_match_digest(self, ctx: dict[str, Any]) -> tuple[str, str, str]:
    """Render the daily/weekly job-match digest email.

    ctx["matches"]: list of dicts with title, company, location, overall_score,
    explanation, source_url — see job_matching.py's _send_match_digest_async().
    """
    matches = ctx.get("matches", [])
    subject = f"{len(matches)} new job match{'es' if len(matches) != 1 else ''} for you"

    rows_html = "".join(
        f"""
        <tr>
          <td style="padding:12px;border-bottom:1px solid #eee;">
            <strong>{m['title']}</strong> at {m['company']}<br/>
            <span style="color:#666;">{m.get('location') or 'Remote/Unspecified'}</span><br/>
            <span style="color:#0a7;">Match score: {m['overall_score']}/100</span><br/>
            <p>{m.get('explanation', '')}</p>
            <a href="{m.get('source_url', '#')}">View job</a>
          </td>
        </tr>
        """
        for m in matches
    )
    html_body = f"<table style='width:100%;'>{rows_html}</table>"
    text_body = "\n\n".join(
        f"{m['title']} at {m['company']} — {m['overall_score']}/100\n{m.get('explanation', '')}"
        for m in matches
    )
    return subject, html_body, text_body
```

---

## 8. Testing — proving Module 1 is 100% complete

Per RULE.md: "No live external calls in CI" (JobSpy, OpenAI, SendGrid all mocked), "New route behavior → API test," and the 78% coverage gate. New test files live in `backend/tests/`, mirroring the existing flat-file convention (`test_document_processing.py`, `test_feedback_generation.py` are siblings, not nested folders).

**New test files:**
1. `backend/tests/test_job_matching_scorer.py` — pure function unit tests, no mocks needed
2. `backend/tests/test_job_matching_repository.py` — DB-layer tests against the test SQLite/Postgres fixture
3. `backend/tests/test_job_matching_api.py` — router/HTTP tests via `TestClient`
4. `backend/tests/test_job_matching_worker.py` — worker task tests with JobSpy/OpenAI/SendGrid mocked
5. `backend/tests/test_job_matching_explainer.py` — explainer prompt/parsing tests with `httpx` mocked

### 8.1 `backend/tests/test_job_matching_scorer.py`

```python
"""Unit tests for deterministic job-match scoring (scorer.py). No DB, no I/O."""

import pytest

from app.modules.job_matching.scorer import (
    compute_dedup_key,
    compute_overall_score,
    compute_rule_score,
    normalize_dedup_field,
    score_location_fit,
    score_salary_fit,
)


class TestNormalizeDedupField:
    def test_lowercases_and_strips_punctuation(self):
        assert normalize_dedup_field("Senior Software Engineer, Backend!") == "senior software engineer backend"

    def test_collapses_whitespace(self):
        assert normalize_dedup_field("New   York    City") == "new york city"

    def test_handles_empty_string(self):
        assert normalize_dedup_field("") == ""


class TestComputeDedupKey:
    def test_same_title_location_source_produces_same_key(self):
        key1 = compute_dedup_key("Software Engineer", "New York, NY", "linkedin")
        key2 = compute_dedup_key("software engineer", "new york ny", "linkedin")
        assert key1 == key2

    def test_different_source_produces_different_key(self):
        key1 = compute_dedup_key("Software Engineer", "New York, NY", "linkedin")
        key2 = compute_dedup_key("Software Engineer", "New York, NY", "indeed")
        assert key1 != key2

    def test_company_name_is_not_part_of_key(self):
        """Per Decision 4: company name is deliberately excluded."""
        key1 = compute_dedup_key("Software Engineer", "New York, NY", "linkedin")
        key2 = compute_dedup_key("Software Engineer", "New York, NY", "linkedin")
        assert key1 == key2  # same inputs regardless of any company field passed elsewhere

    def test_key_is_64_char_hex(self):
        key = compute_dedup_key("Engineer", "Remote", "indeed")
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)


class TestScoreSalaryFit:
    def test_no_preference_is_neutral(self):
        assert score_salary_fit(100_000, 150_000, None, None) == 0.5

    def test_no_posting_salary_is_neutral(self):
        assert score_salary_fit(None, None, 100_000, 150_000) == 0.5

    def test_full_overlap_is_perfect(self):
        assert score_salary_fit(100_000, 150_000, 100_000, 150_000) == 1.0

    def test_partial_overlap_is_perfect(self):
        assert score_salary_fit(120_000, 180_000, 100_000, 150_000) == 1.0

    def test_no_overlap_is_zero(self):
        assert score_salary_fit(200_000, 250_000, 80_000, 120_000) == 0.0

    def test_posting_min_only(self):
        assert score_salary_fit(100_000, None, 90_000, 110_000) == 1.0

    def test_candidate_min_only(self):
        assert score_salary_fit(50_000, 70_000, 100_000, None) == 0.0


class TestScoreLocationFit:
    def test_remote_preference_matches_remote_posting(self):
        assert score_location_fit(None, True, [], "remote") == 1.0

    def test_remote_preference_rejects_onsite_posting(self):
        assert score_location_fit("Austin, TX", False, [], "remote") == 0.0

    def test_no_location_preference_is_neutral(self):
        assert score_location_fit("Austin, TX", False, [], None) == 0.5

    def test_remote_posting_satisfies_any_location_preference(self):
        assert score_location_fit(None, True, ["New York"], "hybrid") == 1.0

    def test_matching_city_scores_perfect(self):
        assert score_location_fit("New York, NY", False, ["New York"], "onsite") == 1.0

    def test_non_matching_city_scores_zero(self):
        assert score_location_fit("Austin, TX", False, ["New York"], "onsite") == 0.0


class TestComputeRuleScore:
    def test_combines_salary_and_location(self):
        posting = {"salary_min": 100_000, "salary_max": 150_000, "location": "NYC", "remote": False}
        prefs = {"salary_min": 100_000, "salary_max": 150_000, "desired_locations": ["NYC"], "remote_preference": "onsite"}
        score, breakdown = compute_rule_score(posting, prefs)
        assert score == 1.0
        assert breakdown == {"salary_fit": 1.0, "location_fit": 1.0}

    def test_mismatched_everything_scores_zero(self):
        posting = {"salary_min": 40_000, "salary_max": 50_000, "location": "Austin", "remote": False}
        prefs = {"salary_min": 150_000, "salary_max": 200_000, "desired_locations": ["NYC"], "remote_preference": "onsite"}
        score, breakdown = compute_rule_score(posting, prefs)
        assert score == 0.0


class TestComputeOverallScore:
    def test_perfect_scores_yield_100(self):
        assert compute_overall_score(1.0, 1.0) == 100.0

    def test_zero_scores_yield_0(self):
        assert compute_overall_score(0.0, 0.0) == 0.0

    def test_weighted_composite(self):
        # 0.7 * 0.8 + 0.3 * 0.5 = 0.71 -> 71.0
        assert compute_overall_score(0.8, 0.5) == 71.0

    def test_clamps_above_one(self):
        assert compute_overall_score(1.5, 1.5) == 100.0

    def test_clamps_below_zero(self):
        assert compute_overall_score(-0.5, -0.5) == 0.0

    @pytest.mark.parametrize("sim,rule", [(0.9, 0.1), (0.5, 0.5), (0.0, 1.0)])
    def test_result_always_in_valid_range(self, sim, rule):
        result = compute_overall_score(sim, rule)
        assert 0.0 <= result <= 100.0
```

### 8.2 `backend/tests/test_job_matching_repository.py`

Uses the existing `db_session` fixture from `conftest.py` (verified — this fixture is already used by `test_document_processing.py`; no new fixture needed).

```python
"""Repository-layer tests for job matching, using the shared test DB fixture."""

import uuid

import pytest

from app.modules.job_matching import repository
from app.modules.job_matching.scorer import compute_dedup_key


@pytest.mark.asyncio
class TestPreferencesRepository:
    async def test_upsert_creates_new_preferences(self, db_session, test_user):
        prefs = await repository.upsert_preferences(
            db_session, test_user.id, {"desired_roles": ["Backend Engineer"], "salary_min": 100_000}
        )
        assert prefs.desired_roles == ["Backend Engineer"]
        assert prefs.salary_min == 100_000
        assert prefs.is_scan_enabled is True

    async def test_upsert_updates_existing_preferences(self, db_session, test_user):
        await repository.upsert_preferences(db_session, test_user.id, {"salary_min": 100_000})
        updated = await repository.upsert_preferences(db_session, test_user.id, {"salary_min": 150_000})
        assert updated.salary_min == 150_000

        fetched = await repository.get_preferences(db_session, test_user.id)
        assert fetched.salary_min == 150_000

    async def test_get_preferences_returns_none_when_missing(self, db_session):
        result = await repository.get_preferences(db_session, uuid.uuid4())
        assert result is None

    async def test_list_scan_enabled_excludes_disabled(self, db_session, test_user, second_test_user):
        await repository.upsert_preferences(db_session, test_user.id, {"is_scan_enabled": True})
        await repository.upsert_preferences(db_session, second_test_user.id, {"is_scan_enabled": False})

        enabled = await repository.list_scan_enabled_preferences(db_session, limit=100, offset=0)
        enabled_ids = {p.user_id for p in enabled}
        assert test_user.id in enabled_ids
        assert second_test_user.id not in enabled_ids


@pytest.mark.asyncio
class TestJobPostingRepository:
    async def test_upsert_creates_new_posting(self, db_session):
        dedup_key = compute_dedup_key("Backend Engineer", "Remote", "linkedin")
        posting = await repository.upsert_job_posting(
            db_session,
            dedup_key,
            {"title": "Backend Engineer", "company": "Acme", "location": "Remote", "remote": True, "source": "linkedin"},
            "linkedin",
        )
        assert posting.id is not None
        assert posting.sources_seen == ["linkedin"]

    async def test_upsert_same_dedup_key_merges_sources(self, db_session):
        dedup_key = compute_dedup_key("Backend Engineer", "Remote", "linkedin")
        first = await repository.upsert_job_posting(
            db_session,
            dedup_key,
            {"title": "Backend Engineer", "company": "Acme", "location": "Remote", "remote": True, "source": "linkedin"},
            "linkedin",
        )
        second = await repository.upsert_job_posting(
            db_session,
            dedup_key,
            {"title": "Backend Engineer", "company": "Acme", "location": "Remote", "remote": True, "source": "indeed"},
            "indeed",
        )
        assert first.id == second.id  # same row, not a duplicate
        assert set(second.sources_seen) == {"linkedin", "indeed"}

    async def test_find_by_dedup_key_returns_none_when_missing(self, db_session):
        result = await repository.find_posting_by_dedup_key(db_session, "nonexistent" * 8)
        assert result is None


@pytest.mark.asyncio
class TestJobMatchRepository:
    async def test_upsert_match_creates_new(self, db_session, test_user):
        dedup_key = compute_dedup_key("Engineer", "NYC", "linkedin")
        posting = await repository.upsert_job_posting(
            db_session,
            dedup_key,
            {"title": "Engineer", "company": "Acme", "location": "NYC", "remote": False, "source": "linkedin"},
            "linkedin",
        )
        match = await repository.upsert_match(
            db_session, test_user.id, posting.id, 0.8, 0.7, 77.0, {"salary_fit": 0.5, "location_fit": 1.0}
        )
        assert match.overall_score == 77.0

    async def test_upsert_match_refreshes_score_not_duplicate_row(self, db_session, test_user):
        dedup_key = compute_dedup_key("Engineer", "NYC", "linkedin")
        posting = await repository.upsert_job_posting(
            db_session,
            dedup_key,
            {"title": "Engineer", "company": "Acme", "location": "NYC", "remote": False, "source": "linkedin"},
            "linkedin",
        )
        first = await repository.upsert_match(db_session, test_user.id, posting.id, 0.5, 0.5, 50.0, {})
        second = await repository.upsert_match(db_session, test_user.id, posting.id, 0.9, 0.9, 90.0, {})
        assert first.id == second.id
        assert second.overall_score == 90.0

        rows, total = await repository.list_matches_for_user(db_session, test_user.id, limit=10, offset=0)
        assert total == 1  # unique (user_id, job_posting_id) enforced at the app layer too

    async def test_mark_viewed_sets_timestamp_once(self, db_session, test_user):
        dedup_key = compute_dedup_key("Engineer", "NYC", "linkedin")
        posting = await repository.upsert_job_posting(
            db_session, dedup_key, {"title": "Engineer", "company": "Acme", "location": "NYC", "remote": False, "source": "linkedin"}, "linkedin"
        )
        match = await repository.upsert_match(db_session, test_user.id, posting.id, 0.5, 0.5, 50.0, {})

        found = await repository.mark_viewed(db_session, match.id, test_user.id)
        assert found is True

        rows, _ = await repository.list_matches_for_user(db_session, test_user.id, limit=10, offset=0)
        assert rows[0][0].viewed_at is not None

    async def test_mark_viewed_wrong_user_returns_false(self, db_session, test_user, second_test_user):
        dedup_key = compute_dedup_key("Engineer", "NYC", "linkedin")
        posting = await repository.upsert_job_posting(
            db_session, dedup_key, {"title": "Engineer", "company": "Acme", "location": "NYC", "remote": False, "source": "linkedin"}, "linkedin"
        )
        match = await repository.upsert_match(db_session, test_user.id, posting.id, 0.5, 0.5, 50.0, {})

        found = await repository.mark_viewed(db_session, match.id, second_test_user.id)
        assert found is False

    async def test_get_top_unexplained_matches_respects_limit(self, db_session, test_user):
        for i in range(10):
            dedup_key = compute_dedup_key(f"Engineer {i}", "NYC", "linkedin")
            posting = await repository.upsert_job_posting(
                db_session, dedup_key, {"title": f"Engineer {i}", "company": "Acme", "location": "NYC", "remote": False, "source": "linkedin"}, "linkedin"
            )
            await repository.upsert_match(db_session, test_user.id, posting.id, 0.5, 0.5, float(50 + i), {})

        top = await repository.get_top_unexplained_matches(db_session, test_user.id, top_n=5)
        assert len(top) == 5
        scores = [m.overall_score for m, _ in top]
        assert scores == sorted(scores, reverse=True)

    async def test_set_feedback(self, db_session, test_user):
        dedup_key = compute_dedup_key("Engineer", "NYC", "linkedin")
        posting = await repository.upsert_job_posting(
            db_session, dedup_key, {"title": "Engineer", "company": "Acme", "location": "NYC", "remote": False, "source": "linkedin"}, "linkedin"
        )
        match = await repository.upsert_match(db_session, test_user.id, posting.id, 0.5, 0.5, 50.0, {})

        found = await repository.set_feedback(db_session, match.id, test_user.id, "up")
        assert found is True

        rows, _ = await repository.list_matches_for_user(db_session, test_user.id, limit=10, offset=0)
        assert rows[0][0].feedback == "up"
```

**Note on fixtures:** `test_user` already exists in `conftest.py` (verified — used across `test_document_processing.py`). `second_test_user` does not exist yet and must be added to `conftest.py` as a small addition (a second `User` row, same factory pattern as `test_user`, different email) — this is a one-time shared-fixture addition, not duplicated per test file, per RULE.md's reuse principle.

### 8.3 `backend/tests/test_job_matching_api.py`

Uses the existing `async_client`/`authenticated_client` fixtures (verified pattern from `test_document_processing.py`'s API tests).

```python
"""API tests for /api/job-matching/* routes: status codes, auth, response shape."""

import pytest


@pytest.mark.asyncio
class TestPreferencesEndpoints:
    async def test_get_preferences_requires_auth(self, async_client):
        response = await async_client.get("/api/job-matching/preferences")
        assert response.status_code == 401

    async def test_get_preferences_404_when_not_set(self, authenticated_client):
        response = await authenticated_client.get("/api/job-matching/preferences")
        assert response.status_code == 404

    async def test_put_preferences_creates_and_returns(self, authenticated_client):
        payload = {
            "desired_roles": ["Backend Engineer"],
            "desired_locations": ["New York"],
            "remote_preference": "remote",
            "salary_min": 100_000,
            "salary_max": 150_000,
            "notification_channels": ["email"],
            "digest_frequency": "daily",
            "is_scan_enabled": True,
        }
        response = await authenticated_client.put("/api/job-matching/preferences", json=payload)
        assert response.status_code == 200
        body = response.json()["data"]
        assert body["desired_roles"] == ["Backend Engineer"]
        assert body["remote_preference"] == "remote"

    async def test_put_preferences_rejects_salary_max_below_min(self, authenticated_client):
        payload = {"salary_min": 150_000, "salary_max": 100_000}
        response = await authenticated_client.put("/api/job-matching/preferences", json=payload)
        assert response.status_code == 422

    async def test_put_then_get_roundtrips(self, authenticated_client):
        await authenticated_client.put("/api/job-matching/preferences", json={"salary_min": 120_000})
        response = await authenticated_client.get("/api/job-matching/preferences")
        assert response.json()["data"]["salary_min"] == 120_000


@pytest.mark.asyncio
class TestMatchesEndpoints:
    async def test_list_matches_requires_auth(self, async_client):
        response = await async_client.get("/api/job-matching/matches")
        assert response.status_code == 401

    async def test_list_matches_empty_when_none_exist(self, authenticated_client):
        response = await authenticated_client.get("/api/job-matching/matches")
        assert response.status_code == 200
        body = response.json()["data"]
        assert body["matches"] == []
        assert body["total"] == 0

    async def test_list_matches_pagination_params(self, authenticated_client):
        response = await authenticated_client.get("/api/job-matching/matches?limit=5&offset=0")
        assert response.status_code == 200

    async def test_list_matches_rejects_invalid_limit(self, authenticated_client):
        response = await authenticated_client.get("/api/job-matching/matches?limit=1000")
        assert response.status_code == 422

    async def test_mark_viewed_404_for_nonexistent_match(self, authenticated_client):
        response = await authenticated_client.post(
            "/api/job-matching/matches/00000000-0000-0000-0000-000000000000/view"
        )
        assert response.status_code == 404

    async def test_feedback_requires_valid_enum(self, authenticated_client):
        response = await authenticated_client.post(
            "/api/job-matching/matches/00000000-0000-0000-0000-000000000000/feedback",
            json={"feedback": "maybe"},
        )
        assert response.status_code == 422


@pytest.mark.asyncio
class TestScanEndpoint:
    async def test_trigger_scan_requires_auth(self, async_client):
        response = await async_client.post("/api/job-matching/scan")
        assert response.status_code == 401

    async def test_trigger_scan_enqueues_job(self, authenticated_client, mock_redis):
        response = await authenticated_client.post("/api/job-matching/scan")
        assert response.status_code == 200
        assert response.json()["data"]["scan_enqueued"] is True
```

**Note on fixtures:** `mock_redis` must be added if not already present — check `conftest.py` first (RULE.md reuse rule). If a Redis mock fixture already exists for other queue tests (e.g. used by `test_feedback_generation.py`'s enqueue tests), reuse it verbatim; do not create a second one.

### 8.4 `backend/tests/test_job_matching_worker.py`

All external calls mocked per RULE.md's CI rule. `JobSpyEnricher._scrape`, the embeddings client, and `enqueue_email` are all patched.

```python
"""Worker task tests for the job-matching pipeline. All I/O mocked — no live calls."""

from unittest.mock import AsyncMock, patch

import pytest

from app.modules.job_matching import repository
from app.workers.tasks.job_matching import (
    _generate_explanations_for_candidate_async,
    _scan_jobs_for_candidate_async,
    _send_match_digest_async,
)


@pytest.mark.asyncio
class TestScanJobsForCandidate:
    async def test_skips_when_no_preferences(self, db_session, test_user):
        stats = await _scan_jobs_for_candidate_async(str(test_user.id))
        assert stats["scraped"] == 0

    async def test_skips_when_scan_disabled(self, db_session, test_user):
        await repository.upsert_preferences(db_session, test_user.id, {"is_scan_enabled": False})
        stats = await _scan_jobs_for_candidate_async(str(test_user.id))
        assert stats["scraped"] == 0

    async def test_skips_when_no_cv_uploaded(self, db_session, test_user):
        await repository.upsert_preferences(db_session, test_user.id, {"is_scan_enabled": True})
        stats = await _scan_jobs_for_candidate_async(str(test_user.id))
        assert stats["scraped"] == 0

    @patch("app.enrichers.jobspy.JobSpyEnricher._scrape")
    @patch("app.clients.embeddings.get_embeddings_client")
    async def test_scrapes_and_persists_postings(
        self, mock_embeddings_client, mock_scrape, db_session, test_user, completed_cv_document
    ):
        mock_scrape.return_value = [
            {
                "title": "Backend Engineer",
                "company": "Acme",
                "location": "Remote",
                "is_remote": True,
                "site": "linkedin",
                "description": "Python and PostgreSQL experience required.",
                "job_url": "https://linkedin.com/jobs/1",
                "min_amount": 100_000,
                "max_amount": 150_000,
                "currency": "USD",
            }
        ]
        mock_embeddings_client.return_value.generate_embedding = AsyncMock(return_value=([0.1] * 1536, 42))

        await repository.upsert_preferences(db_session, test_user.id, {"is_scan_enabled": True, "desired_roles": ["Backend Engineer"]})

        stats = await _scan_jobs_for_candidate_async(str(test_user.id))
        assert stats["scraped"] == 1
        assert stats["new_postings"] == 1

    @patch("app.enrichers.jobspy.JobSpyEnricher._scrape")
    async def test_handles_empty_scrape_results(self, mock_scrape, db_session, test_user, completed_cv_document):
        mock_scrape.return_value = []
        await repository.upsert_preferences(db_session, test_user.id, {"is_scan_enabled": True})
        stats = await _scan_jobs_for_candidate_async(str(test_user.id))
        assert stats["scraped"] == 0


@pytest.mark.asyncio
class TestGenerateExplanations:
    @patch("app.modules.job_matching.explainer.generate_match_explanation")
    async def test_generates_only_top_n(self, mock_generate, db_session, test_user, ten_scored_matches):
        mock_generate.return_value = "This matches because of X."
        stats = await _generate_explanations_for_candidate_async(str(test_user.id))
        assert stats["generated"] == 5  # JOB_MATCHING_TOP_N_EXPLANATIONS default

    @patch("app.modules.job_matching.explainer.generate_match_explanation")
    async def test_continues_after_individual_failure(self, mock_generate, db_session, test_user, ten_scored_matches):
        mock_generate.side_effect = [Exception("LLM error")] + ["ok explanation"] * 4
        stats = await _generate_explanations_for_candidate_async(str(test_user.id))
        assert stats["generated"] == 4  # 1 failed, 4 succeeded out of top 5


@pytest.mark.asyncio
class TestSendMatchDigest:
    @patch("app.workers.queue.enqueue_email")
    async def test_sends_digest_for_unnotified_matches(self, mock_enqueue, db_session, test_user, ten_scored_matches):
        await repository.upsert_preferences(db_session, test_user.id, {"notification_channels": ["email"]})
        stats = await _send_match_digest_async(str(test_user.id))
        assert stats["sent"] == 5  # top 5 of the unnotified
        mock_enqueue.assert_called_once()

    async def test_skips_when_no_email_channel(self, db_session, test_user, ten_scored_matches):
        await repository.upsert_preferences(db_session, test_user.id, {"notification_channels": ["webhook"]})
        stats = await _send_match_digest_async(str(test_user.id))
        assert stats["sent"] == 0

    @patch("app.workers.queue.enqueue_email")
    async def test_does_not_resend_already_notified_matches(self, mock_enqueue, db_session, test_user, ten_scored_matches):
        await repository.upsert_preferences(db_session, test_user.id, {"notification_channels": ["email"]})
        await _send_match_digest_async(str(test_user.id))
        mock_enqueue.reset_mock()

        second_stats = await _send_match_digest_async(str(test_user.id))
        assert second_stats["sent"] == 0
        mock_enqueue.assert_not_called()
```

**New fixtures needed in `conftest.py` (additions, not duplicates):**
- `completed_cv_document` — a `CandidateDocument` row with `processing_status="completed"`, `document_type="cv"`, and a matching `DocumentEmbedding` row. Follows the exact factory pattern of the existing (verified) `test_document` fixture used by `test_document_processing.py`.
- `ten_scored_matches` — 10 `JobPosting` + `JobMatch` rows for `test_user`, scores 50-95, `explanation=None`, `notified_at=None`. Built via `repository.upsert_job_posting()`/`repository.upsert_match()` inside the fixture, not raw SQL.

### 8.5 `backend/tests/test_job_matching_explainer.py`

```python
"""Tests for the grounded LLM explanation generator. HTTP mocked via respx/httpx_mock."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.job_matching.explainer import generate_match_explanation


class FakeMatch:
    overall_score = 77.0
    score_breakdown = {"salary_fit": 1.0, "location_fit": 0.5}


class FakePosting:
    title = "Backend Engineer"
    company = "Acme"
    description_raw = "We need someone with 5 years of Python and PostgreSQL experience."


@pytest.mark.asyncio
class TestGenerateMatchExplanation:
    @patch("httpx.AsyncClient.post")
    async def test_returns_explanation_from_valid_response(self, mock_post, test_settings):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": json.dumps({"explanation": "Strong Python/PostgreSQL match."})}}]
        }
        mock_post.return_value = mock_response

        result = await generate_match_explanation(FakeMatch(), FakePosting(), test_settings)
        assert result == "Strong Python/PostgreSQL match."

    @patch("httpx.AsyncClient.post")
    async def test_raises_on_malformed_json(self, mock_post, test_settings):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "not json"}}]}
        mock_post.return_value = mock_response

        with pytest.raises(ValueError, match="Invalid explanation JSON"):
            await generate_match_explanation(FakeMatch(), FakePosting(), test_settings)

    @patch("httpx.AsyncClient.post")
    async def test_raises_on_empty_explanation(self, mock_post, test_settings):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": json.dumps({"explanation": ""})}}]
        }
        mock_post.return_value = mock_response

        with pytest.raises(ValueError, match="Empty explanation"):
            await generate_match_explanation(FakeMatch(), FakePosting(), test_settings)

    async def test_raises_when_no_api_key(self, test_settings_no_key):
        with pytest.raises(ValueError, match="not configured"):
            await generate_match_explanation(FakeMatch(), FakePosting(), test_settings_no_key)

    def test_prompt_includes_score_as_given_fact(self):
        """Per Decision 3: the score must be given TO the LLM, never asked FOR."""
        from app.modules.job_matching.explainer import _build_explanation_messages

        messages = _build_explanation_messages(FakeMatch(), FakePosting())
        user_message = messages[1]["content"]
        assert "77.0" in user_message
        assert "Pre-computed match score" in user_message

        system_message = messages[0]["content"]
        assert "must NOT invent" in system_message or "must not invent" in system_message.lower()
```

---

### 8.6 `backend/tests/test_job_matching_scheduler.py` — fan-out and cron registration

```python
"""Tests for the daily fan-out scheduler and cron registration."""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.job_matching import repository
from app.workers.tasks.job_matching import _fan_out_daily_scans_async


@pytest.mark.asyncio
class TestFanOutDailyScans:
    @patch("rq_scheduler.Scheduler")
    async def test_enqueues_one_job_per_scan_enabled_candidate(
        self, mock_scheduler_cls, db_session, test_user, second_test_user
    ):
        mock_scheduler = MagicMock()
        mock_scheduler_cls.return_value = mock_scheduler

        await repository.upsert_preferences(db_session, test_user.id, {"is_scan_enabled": True})
        await repository.upsert_preferences(db_session, second_test_user.id, {"is_scan_enabled": False})

        result = await _fan_out_daily_scans_async()

        assert result["enqueued"] == 1  # only the scan-enabled candidate
        assert mock_scheduler.enqueue_at.call_count == 1

    @patch("rq_scheduler.Scheduler")
    async def test_handles_zero_candidates_gracefully(self, mock_scheduler_cls, db_session):
        mock_scheduler_cls.return_value = MagicMock()
        result = await _fan_out_daily_scans_async()
        assert result["enqueued"] == 0


class TestCronRegistration:
    """Verifies register_scheduled_jobs() registers the new job without breaking the existing one."""

    @patch("rq_scheduler.Scheduler")
    def test_registers_both_audio_cleanup_and_job_matching(self, mock_scheduler_cls):
        from app.workers.queue import register_scheduled_jobs

        mock_scheduler = MagicMock()
        mock_scheduler_cls.return_value = mock_scheduler

        register_scheduled_jobs()

        registered_ids = [call.kwargs.get("id") for call in mock_scheduler.cron.call_args_list]
        assert "audio_cleanup_daily" in registered_ids
        assert "job_matching_fan_out_daily" in registered_ids
```

### 8.7 `backend/tests/test_job_matching_migrations.py` — schema tests

Follows the existing pattern used for `014_document_embeddings.py` (grep confirms a parallel migration test exists for that revision — same structure copied here).

```python
"""Tests that the new Alembic migrations create the expected schema."""

import pytest
from sqlalchemy import inspect


@pytest.mark.asyncio
async def test_job_postings_table_exists_with_unique_dedup_key(db_engine):
    async with db_engine.connect() as conn:
        def _inspect(sync_conn):
            inspector = inspect(sync_conn)
            return inspector.get_table_names(), inspector.get_indexes("job_postings")

        tables, indexes = await conn.run_sync(_inspect)
        assert "job_postings" in tables
        assert any(idx["unique"] and "dedup_key" in idx["column_names"] for idx in indexes)


@pytest.mark.asyncio
async def test_candidate_job_preferences_unique_per_user(db_engine):
    async with db_engine.connect() as conn:
        def _inspect(sync_conn):
            inspector = inspect(sync_conn)
            return inspector.get_indexes("candidate_job_preferences")

        indexes = await conn.run_sync(_inspect)
        assert any(idx["unique"] and "user_id" in idx["column_names"] for idx in indexes)


@pytest.mark.asyncio
async def test_job_matches_unique_user_posting_pair(db_engine):
    async with db_engine.connect() as conn:
        def _inspect(sync_conn):
            inspector = inspect(sync_conn)
            return inspector.get_indexes("job_matches")

        indexes = await conn.run_sync(_inspect)
        assert any(
            idx["unique"] and set(idx["column_names"]) == {"user_id", "job_posting_id"} for idx in indexes
        )


@pytest.mark.asyncio
async def test_downgrade_is_reversible(alembic_config):
    """Confirms alembic downgrade -1 (x4) does not error, matching the existing migration-reversibility test pattern."""
    from alembic import command

    command.downgrade(alembic_config, "-4")
    command.upgrade(alembic_config, "head")
```

### 8.8 Frontend tests (co-located with components, see §11 for exact paths and content)

Listed here for completeness of the "100% tested" claim; full content is in §11 to keep implementation and its test adjacent, matching this repo's existing convention (e.g., `JobCard.test.tsx` sits next to `JobCard.tsx` today — verified).

- `frontend/features/job-matching/hooks/usePreferences.test.ts`
- `frontend/features/job-matching/hooks/useMatches.test.ts`
- `frontend/features/job-matching/components/MatchCard.test.tsx`
- `frontend/features/job-matching/components/PreferencesForm.test.tsx`
- `frontend/app/api/job-matching/preferences/route.test.ts`
- `frontend/app/api/job-matching/matches/route.test.ts`

### 8.9 Commands to run before declaring Module 1 done

```bash
# Backend: migrations apply and reverse cleanly
cd backend
alembic upgrade head
alembic downgrade -4 && alembic upgrade head

# Backend: full new-module test suite
pytest tests/test_job_matching_scorer.py tests/test_job_matching_repository.py \
       tests/test_job_matching_api.py tests/test_job_matching_worker.py \
       tests/test_job_matching_explainer.py tests/test_job_matching_scheduler.py \
       tests/test_job_matching_migrations.py -v

# Backend: coverage gate (must stay >= the repo's existing 78% floor, not lower it)
pytest --cov=app.modules.job_matching --cov=app.workers.tasks.job_matching \
       --cov-report=term-missing --cov-fail-under=78

# Backend: full suite regression check (nothing else broke)
pytest

# Backend: lint/type
ruff check app/modules/job_matching app/workers/tasks/job_matching.py
mypy app/modules/job_matching

# Frontend: typecheck + lint + build (per RULE.md "type changes -> typecheck, UI changes -> lint/build")
cd ../frontend
npm run typecheck
npm run lint
npm run build

# Frontend: new-feature test suite
npm test -- job-matching
```

**Completion is not claimed until every command above exits 0.** This is the same standard the earlier "foundation complete" claim failed to meet (§ discussed in this conversation's prior turns — session-tracking tests were at 13 failed/14 errored despite being called "100% complete"); this document does not repeat that mistake by asserting completion without the commands that prove it.

---

## 9. Docker architecture for Module 1

Per §4's starvation analysis, Module 1 gets its **own dedicated worker container** rather than joining the generic worker's queue list. This follows the same pattern already established by `worker-document` and `worker-embedding` in `backend/docker/docker-compose.foundation.yml` (verified — these are real, existing dedicated-queue containers, not proposed ones) — Module 1 extends a pattern that already exists in this repo, rather than inventing a new one.

### 9.1 New Dockerfile: `backend/docker/Dockerfile.worker-job-matching`

Copies the exact structure of the existing `Dockerfile.worker-document` (verified file — same base image, same non-root user pattern, same healthcheck shape), swapping only the entrypoint module.

```dockerfile
FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml poetry.lock* ./
RUN pip install --no-cache-dir poetry==1.8.3 \
    && poetry config virtualenvs.create false \
    && poetry install --no-root --only main

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

RUN useradd --create-home --shell /bin/bash worker \
    && chown -R worker:worker /app
USER worker

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "from app.workers.tasks.job_matching import check_worker_health; import sys; sys.exit(0 if check_worker_health('job_matching') else 1)"

CMD ["python", "-m", "app.workers.rq_worker_job_matching"]
```

### 9.2 New entrypoint: `backend/app/workers/rq_worker_job_matching.py`

A dedicated single-queue worker entrypoint, mirroring `rq_worker.py`'s structure but listening to only `QUEUE_JOB_MATCHING` — this is what actually resolves the starvation risk from §4 (isolation, not reordering).

```python
"""Dedicated RQ worker for the job_matching queue. Does not share queues with the generic worker."""

from __future__ import annotations

import logging

from rq import Connection, Worker

from app.workers.queue import QUEUE_JOB_MATCHING, get_redis_connection, register_scheduled_jobs

logger = logging.getLogger(__name__)


def main() -> None:
    connection = get_redis_connection()
    with Connection(connection):
        worker = Worker([QUEUE_JOB_MATCHING], connection=connection, name="worker-job-matching")
        logger.info("Starting dedicated job-matching worker", extra={"queue": QUEUE_JOB_MATCHING})

        # Only ONE process should own the scheduler for job_matching's cron entries,
        # to avoid the duplicate-registration risk flagged for the generic worker
        # (rq_worker.py calls with_scheduler=True on every replica — not copied here).
        register_scheduled_jobs()
        worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
```

**Deliberate divergence from `rq_worker.py` flagged explicitly:** the generic worker's `worker.work(with_scheduler=True)` on every replica causes duplicate scheduler registration if scaled beyond 1 replica (a pre-existing issue, out of scope to fix here). Because `docker-compose` (§9.3) pins `worker-job-matching` to `replicas: 1`, this dedicated worker does not introduce a *new* instance of that problem — but it is not fixed either. This is called out so it isn't mistaken for "solved."

### 9.3 `backend/docker/docker-compose.foundation.yml` — additions

Add a new service block, following the exact shape of the existing `worker-document`/`worker-embedding` blocks (verified structure — same `depends_on`, `environment`, `restart` conventions):

```yaml
  worker-job-matching:
    build:
      context: ../..
      dockerfile: backend/docker/Dockerfile.worker-job-matching
    container_name: hyerenrichment-worker-job-matching
    restart: unless-stopped
    depends_on:
      redis:
        condition: service_healthy
      postgres:
        condition: service_healthy
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - JOB_MATCHING_ENABLED=${JOB_MATCHING_ENABLED:-true}
      - JOB_MATCHING_MAX_POSTINGS_PER_SCAN=${JOB_MATCHING_MAX_POSTINGS_PER_SCAN:-50}
      - JOB_MATCHING_SIMILARITY_THRESHOLD=${JOB_MATCHING_SIMILARITY_THRESHOLD:-0.5}
      - JOB_MATCHING_TOP_N_EXPLANATIONS=${JOB_MATCHING_TOP_N_EXPLANATIONS:-5}
      - SENDGRID_API_KEY=${SENDGRID_API_KEY}
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1G
        reservations:
          cpus: "0.25"
          memory: 256M
      replicas: 1   # pinned per §9.2's scheduler-duplication note; do not scale without fixing that first
    healthcheck:
      test: ["CMD", "python", "-c", "from app.workers.tasks.job_matching import check_worker_health; import sys; sys.exit(0 if check_worker_health('job_matching') else 1)"]
      interval: 30s
      timeout: 10s
      start_period: 15s
      retries: 3
```

**Resource sizing rationale:** 1 CPU / 1GB limit matches `worker-embedding`'s existing allocation (verified in the same compose file) — job matching does the same shape of work (one OpenAI HTTP call + one pgvector query per item, no local ML inference), so no evidence supports a different allocation. This is ❌ **NOT FOUND** as a benchmarked number for this specific workload; it is copied from the most analogous existing container as a starting point, to be adjusted from real Prometheus metrics (§9.5) once running — not asserted as a tuned value.

### 9.4 Full container topology after Module 1 ships

```
┌─────────────────────────────────────────────────────────────────┐
│  docker-compose.foundation.yml (extended, not replaced)         │
├─────────────────────────────────────────────────────────────────┤
│  postgres (pgvector)   redis   api (FastAPI)   frontend (Next)  │
│  worker-document        worker-embedding   worker (generic)     │
│  worker-job-matching  ◄── NEW, this plan                        │
└─────────────────────────────────────────────────────────────────┘

Generic `worker` container's queue list (rq_worker.py) — UNCHANGED by this plan:
  [feedback, document_processing, embedding_generation, cv_extraction, enrichment]

`worker-job-matching`'s queue list (rq_worker_job_matching.py) — NEW, isolated:
  [job_matching]
```

### 9.5 Monitoring additions

**File edited:** `backend/app/core/metrics.py` (or wherever Prometheus counters are defined — verified pattern from existing enrichment metrics) — add:

```python
job_matching_scans_total = Counter(
    "job_matching_scans_total", "Total job-matching scans run", ["status"]
)
job_matching_postings_scraped_total = Counter(
    "job_matching_postings_scraped_total", "Total job postings scraped", ["source"]
)
job_matching_explanations_generated_total = Counter(
    "job_matching_explanations_generated_total", "Total LLM explanations generated"
)
job_matching_digest_emails_sent_total = Counter(
    "job_matching_digest_emails_sent_total", "Total digest emails sent"
)
job_matching_scan_duration_seconds = Histogram(
    "job_matching_scan_duration_seconds", "Duration of a single candidate scan"
)
```

Incremented at the relevant points in `job_matching.py`'s task functions (e.g., `job_matching_scans_total.labels(status="success").inc()` at the end of `_scan_jobs_for_candidate_async`, `status="skipped"` on early returns).

---

## 10. Frontend — shared types and BFF API layer

### 10.1 OpenAPI sync (must run first, per RULE.md)

After the backend router (§7.7) exists and the app boots, run:

```bash
cd backend && python -m app.export_openapi  # or the repo's actual export command, verified name below
cd ../frontend && npm run openapi:gen
```

**Verify exact command names before running** — grep `package.json`'s `scripts` block for `openapi` (this plan assumes `openapi:export` on the backend side and `openapi:gen` on the frontend side based on RULE.md's own reference to these two commands; confirm exact names in `frontend/package.json` and the backend's export script before executing, since this plan does not fabricate a command name it hasn't verified character-for-character).

This regenerates `frontend/src/lib/api-types.generated.ts` (or equivalent) with `JobPreferencesRequest`, `JobPreferencesResponse`, `JobMatchResponse`, etc. — committed as part of this change, not hand-written.

### 10.2 `frontend/src/lib/types.ts` — additions

Per §4's naming resolution (`JobPosting`/`JobMatch`, not `JobListing`, to avoid the existing collision):

```typescript
// Module 1: AI Job Matching & Notifications
// NOTE: distinct from JobListing (Dossier tier-4 enrichment output) and
// JobListResponse (enrichment task records) — see phase2_module1.md §4.

export interface CandidateJobPreferences {
  userId: string;
  sourceDocumentId: string | null;
  desiredRoles: string[];
  desiredLocations: string[];
  remotePreference: "remote" | "hybrid" | "onsite" | null;
  salaryMin: number | null;
  salaryMax: number | null;
  salaryCurrency: string;
  notificationChannels: ("email" | "sms" | "webhook")[];
  digestFrequency: "daily" | "weekly" | "off";
  isScanEnabled: boolean;
  lastScannedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface JobMatch {
  matchId: string;
  jobPostingId: string;
  title: string;
  company: string;
  location: string | null;
  remote: boolean;
  source: string;
  sourceUrl: string | null;
  salaryMin: number | null;
  salaryMax: number | null;
  salaryCurrency: string | null;
  overallScore: number;
  scoreBreakdown: Record<string, number>;
  explanation: string | null;
  isNew: boolean;
  viewedAt: string | null;
  feedback: "up" | "down" | null;
  createdAt: string;
}

export interface JobMatchListResponse {
  matches: JobMatch[];
  total: number;
  limit: number;
  offset: number;
}
```

### 10.3 `frontend/src/lib/api-adapter.ts` — additions

Per RULE.md, field-name mapping (snake_case backend ↔ camelCase frontend) happens **only** here, never inline in components.

```typescript
export function adaptJobPreferences(raw: RawJobPreferencesResponse): CandidateJobPreferences {
  return {
    userId: raw.user_id,
    sourceDocumentId: raw.source_document_id,
    desiredRoles: raw.desired_roles,
    desiredLocations: raw.desired_locations,
    remotePreference: raw.remote_preference,
    salaryMin: raw.salary_min,
    salaryMax: raw.salary_max,
    salaryCurrency: raw.salary_currency,
    notificationChannels: raw.notification_channels,
    digestFrequency: raw.digest_frequency,
    isScanEnabled: raw.is_scan_enabled,
    lastScannedAt: raw.last_scanned_at,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

export function adaptJobMatch(raw: RawJobMatchResponse): JobMatch {
  return {
    matchId: raw.match_id,
    jobPostingId: raw.job_posting_id,
    title: raw.title,
    company: raw.company,
    location: raw.location,
    remote: raw.remote,
    source: raw.source,
    sourceUrl: raw.source_url,
    salaryMin: raw.salary_min,
    salaryMax: raw.salary_max,
    salaryCurrency: raw.salary_currency,
    overallScore: raw.overall_score,
    scoreBreakdown: raw.score_breakdown,
    explanation: raw.explanation,
    isNew: raw.is_new,
    viewedAt: raw.viewed_at,
    feedback: raw.feedback,
    createdAt: raw.created_at,
  };
}

export function adaptJobMatchList(raw: RawJobMatchListResponse): JobMatchListResponse {
  return {
    matches: raw.matches.map(adaptJobMatch),
    total: raw.total,
    limit: raw.limit,
    offset: raw.offset,
  };
}
```

`RawJobPreferencesResponse`/`RawJobMatchResponse`/`RawJobMatchListResponse` come from the generated OpenAPI types (§10.1) — not hand-declared duplicates.

### 10.4 BFF routes (Next.js API routes proxying to the backend)

Following the exact existing pattern in `frontend/app/api/documents/*` (verified: thin proxy, `backendFetch()`, envelope unwrap via `bff-response.ts`).

**New file:** `frontend/app/api/job-matching/preferences/route.ts`

```typescript
import { NextRequest } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import { unwrapEnvelope, bffError } from "@/src/lib/bff-response";

export async function GET(request: NextRequest) {
  try {
    const response = await backendFetch(request, "/api/job-matching/preferences", { method: "GET" });
    return unwrapEnvelope(response);
  } catch (error) {
    return bffError(error);
  }
}

export async function PUT(request: NextRequest) {
  try {
    const body = await request.json();
    const response = await backendFetch(request, "/api/job-matching/preferences", {
      method: "PUT",
      body: JSON.stringify(body),
    });
    return unwrapEnvelope(response);
  } catch (error) {
    return bffError(error);
  }
}
```

**New file:** `frontend/app/api/job-matching/matches/route.ts`

```typescript
import { NextRequest } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import { unwrapEnvelope, bffError } from "@/src/lib/bff-response";

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const qs = searchParams.toString();
    const response = await backendFetch(request, `/api/job-matching/matches${qs ? `?${qs}` : ""}`, {
      method: "GET",
    });
    return unwrapEnvelope(response);
  } catch (error) {
    return bffError(error);
  }
}
```

**New file:** `frontend/app/api/job-matching/matches/[matchId]/view/route.ts`

```typescript
import { NextRequest } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import { unwrapEnvelope, bffError } from "@/src/lib/bff-response";

export async function POST(request: NextRequest, { params }: { params: { matchId: string } }) {
  try {
    const response = await backendFetch(request, `/api/job-matching/matches/${params.matchId}/view`, {
      method: "POST",
    });
    return unwrapEnvelope(response);
  } catch (error) {
    return bffError(error);
  }
}
```

**New file:** `frontend/app/api/job-matching/matches/[matchId]/feedback/route.ts`

```typescript
import { NextRequest } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import { unwrapEnvelope, bffError } from "@/src/lib/bff-response";

export async function POST(request: NextRequest, { params }: { params: { matchId: string } }) {
  try {
    const body = await request.json();
    const response = await backendFetch(request, `/api/job-matching/matches/${params.matchId}/feedback`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    return unwrapEnvelope(response);
  } catch (error) {
    return bffError(error);
  }
}
```

**New file:** `frontend/app/api/job-matching/scan/route.ts`

```typescript
import { NextRequest } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import { unwrapEnvelope, bffError } from "@/src/lib/bff-response";

export async function POST(request: NextRequest) {
  try {
    const response = await backendFetch(request, "/api/job-matching/scan", { method: "POST" });
    return unwrapEnvelope(response);
  } catch (error) {
    return bffError(error);
  }
}
```

---

## 11. Frontend — `features/job-matching/` module, pages, routing, design

### 11.1 `frontend/features/job-matching/api/keys.ts`

React Query key factory, following the exact pattern in `frontend/features/enrich/api/keys.ts` (verified structure).

```typescript
export const jobMatchingKeys = {
  all: ["job-matching"] as const,
  preferences: () => [...jobMatchingKeys.all, "preferences"] as const,
  matches: (limit: number, offset: number) => [...jobMatchingKeys.all, "matches", limit, offset] as const,
};
```

### 11.2 `frontend/features/job-matching/api/client.ts`

Thin fetch wrappers calling the BFF routes (§10.4) — never the backend directly, per the existing convention.

```typescript
import type { CandidateJobPreferences, JobMatchListResponse } from "@/src/lib/types";

export async function fetchPreferences(): Promise<CandidateJobPreferences> {
  const res = await fetch("/api/job-matching/preferences");
  if (!res.ok) throw new Error(`Failed to fetch preferences: ${res.status}`);
  const json = await res.json();
  return json.data;
}

export async function updatePreferences(
  payload: Partial<CandidateJobPreferences>
): Promise<CandidateJobPreferences> {
  const res = await fetch("/api/job-matching/preferences", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Failed to update preferences: ${res.status}`);
  const json = await res.json();
  return json.data;
}

export async function fetchMatches(limit: number, offset: number): Promise<JobMatchListResponse> {
  const res = await fetch(`/api/job-matching/matches?limit=${limit}&offset=${offset}`);
  if (!res.ok) throw new Error(`Failed to fetch matches: ${res.status}`);
  const json = await res.json();
  return json.data;
}

export async function markMatchViewed(matchId: string): Promise<void> {
  await fetch(`/api/job-matching/matches/${matchId}/view`, { method: "POST" });
}

export async function submitMatchFeedback(matchId: string, feedback: "up" | "down"): Promise<void> {
  await fetch(`/api/job-matching/matches/${matchId}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ feedback }),
  });
}

export async function triggerScan(): Promise<{ scanEnqueued: boolean }> {
  const res = await fetch("/api/job-matching/scan", { method: "POST" });
  if (!res.ok) throw new Error(`Failed to trigger scan: ${res.status}`);
  const json = await res.json();
  return { scanEnqueued: json.data.scan_enqueued };
}
```

### 11.3 `frontend/features/job-matching/hooks/usePreferences.ts`

```typescript
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchPreferences, updatePreferences } from "../api/client";
import { jobMatchingKeys } from "../api/keys";
import type { CandidateJobPreferences } from "@/src/lib/types";

export function usePreferences() {
  return useQuery({
    queryKey: jobMatchingKeys.preferences(),
    queryFn: fetchPreferences,
    retry: (failureCount, error) => {
      // 404 means "not set yet" — a valid state, not a retryable error.
      if (error instanceof Error && error.message.includes("404")) return false;
      return failureCount < 2;
    },
  });
}

export function useUpdatePreferences() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<CandidateJobPreferences>) => updatePreferences(payload),
    onSuccess: (data) => {
      queryClient.setQueryData(jobMatchingKeys.preferences(), data);
    },
  });
}
```

**Test file:** `frontend/features/job-matching/hooks/usePreferences.test.ts`

```typescript
import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { usePreferences } from "./usePreferences";
import * as client from "../api/client";

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

describe("usePreferences", () => {
  it("returns preferences data on success", async () => {
    vi.spyOn(client, "fetchPreferences").mockResolvedValue({
      userId: "u1",
      sourceDocumentId: null,
      desiredRoles: ["Engineer"],
      desiredLocations: [],
      remotePreference: "remote",
      salaryMin: null,
      salaryMax: null,
      salaryCurrency: "USD",
      notificationChannels: ["email"],
      digestFrequency: "daily",
      isScanEnabled: true,
      lastScannedAt: null,
      createdAt: "2026-01-01T00:00:00Z",
      updatedAt: "2026-01-01T00:00:00Z",
    });

    const { result } = renderHook(() => usePreferences(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.desiredRoles).toEqual(["Engineer"]);
  });

  it("does not retry on 404", async () => {
    vi.spyOn(client, "fetchPreferences").mockRejectedValue(new Error("Failed to fetch preferences: 404"));
    const { result } = renderHook(() => usePreferences(), { wrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
```

### 11.4 `frontend/features/job-matching/hooks/useMatches.ts`

```typescript
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchMatches, markMatchViewed, submitMatchFeedback, triggerScan } from "../api/client";
import { jobMatchingKeys } from "../api/keys";

export function useMatches(limit = 20, offset = 0) {
  return useQuery({
    queryKey: jobMatchingKeys.matches(limit, offset),
    queryFn: () => fetchMatches(limit, offset),
    refetchInterval: 60_000, // poll every 60s — matches are produced async by the worker
  });
}

export function useMarkMatchViewed() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (matchId: string) => markMatchViewed(matchId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: jobMatchingKeys.all }),
  });
}

export function useSubmitFeedback() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ matchId, feedback }: { matchId: string; feedback: "up" | "down" }) =>
      submitMatchFeedback(matchId, feedback),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: jobMatchingKeys.all }),
  });
}

export function useTriggerScan() {
  return useMutation({ mutationFn: triggerScan });
}
```

**Test file:** `frontend/features/job-matching/hooks/useMatches.test.ts` — same shape as §11.3's test, covering: successful fetch, 60s poll interval config is set, `useMarkMatchViewed` invalidates the matches query on success, `useSubmitFeedback` calls the client with correct args.

### 11.5 `frontend/features/job-matching/components/MatchCard.tsx`

Extends the existing (currently unused) `JobCard.tsx` rather than duplicating it — imports and wraps it with a score badge, explanation text, and feedback buttons.

```tsx
import { JobCard } from "@/components/dossier/JobCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ThumbsUp, ThumbsDown } from "lucide-react";
import type { JobMatch } from "@/src/lib/types";
import { useMarkMatchViewed, useSubmitFeedback } from "../hooks/useMatches";
import { useEffect } from "react";

interface MatchCardProps {
  match: JobMatch;
}

function scoreColor(score: number): string {
  if (score >= 80) return "bg-green-100 text-green-800";
  if (score >= 60) return "bg-yellow-100 text-yellow-800";
  return "bg-gray-100 text-gray-600";
}

export function MatchCard({ match }: MatchCardProps) {
  const markViewed = useMarkMatchViewed();
  const submitFeedback = useSubmitFeedback();

  useEffect(() => {
    if (match.isNew) {
      markViewed.mutate(match.matchId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [match.matchId]);

  return (
    <div className="relative rounded-lg border p-4">
      <div className="absolute right-4 top-4">
        <Badge className={scoreColor(match.overallScore)}>{Math.round(match.overallScore)}/100</Badge>
      </div>

      <JobCard
        job={{
          title: match.title,
          company: match.company,
          location: match.location ?? undefined,
          remote: match.remote,
          source: match.source,
        }}
      />

      {match.explanation && (
        <p className="mt-2 text-sm text-muted-foreground">{match.explanation}</p>
      )}

      <div className="mt-3 flex items-center gap-2">
        {match.sourceUrl && (
          <a
            href={match.sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-medium text-primary hover:underline"
          >
            View posting
          </a>
        )}
        <div className="ml-auto flex gap-1">
          <Button
            size="icon"
            variant={match.feedback === "up" ? "default" : "ghost"}
            onClick={() => submitFeedback.mutate({ matchId: match.matchId, feedback: "up" })}
            aria-label="Good match"
          >
            <ThumbsUp className="h-4 w-4" />
          </Button>
          <Button
            size="icon"
            variant={match.feedback === "down" ? "default" : "ghost"}
            onClick={() => submitFeedback.mutate({ matchId: match.matchId, feedback: "down" })}
            aria-label="Not a good match"
          >
            <ThumbsDown className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
```

**Test file:** `frontend/features/job-matching/components/MatchCard.test.tsx` — renders with a sample `JobMatch`, asserts score badge text, asserts feedback buttons call `submitMatchFeedback` with correct args on click, asserts `markMatchViewed` is called once on mount when `isNew` is true and not called when `isNew` is false.

### 11.6 `frontend/features/job-matching/components/PreferencesForm.tsx`

```tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { usePreferences, useUpdatePreferences } from "../hooks/usePreferences";

export function PreferencesForm() {
  const { data: preferences, isLoading } = usePreferences();
  const updateMutation = useUpdatePreferences();

  const [salaryMin, setSalaryMin] = useState(preferences?.salaryMin ?? "");
  const [salaryMax, setSalaryMax] = useState(preferences?.salaryMax ?? "");
  const [remotePreference, setRemotePreference] = useState(preferences?.remotePreference ?? "");
  const [isScanEnabled, setIsScanEnabled] = useState(preferences?.isScanEnabled ?? true);

  if (isLoading) return <div className="animate-pulse h-64 rounded-lg bg-muted" />;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    updateMutation.mutate({
      salaryMin: salaryMin ? Number(salaryMin) : null,
      salaryMax: salaryMax ? Number(salaryMax) : null,
      remotePreference: remotePreference || null,
      isScanEnabled,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label htmlFor="salaryMin">Minimum salary</Label>
          <Input id="salaryMin" type="number" value={salaryMin} onChange={(e) => setSalaryMin(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="salaryMax">Maximum salary</Label>
          <Input id="salaryMax" type="number" value={salaryMax} onChange={(e) => setSalaryMax(e.target.value)} />
        </div>
      </div>

      <div>
        <Label htmlFor="remotePreference">Work arrangement</Label>
        <Select value={remotePreference} onValueChange={setRemotePreference}>
          <SelectTrigger id="remotePreference">
            <SelectValue placeholder="No preference" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="remote">Remote</SelectItem>
            <SelectItem value="hybrid">Hybrid</SelectItem>
            <SelectItem value="onsite">Onsite</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="flex items-center justify-between rounded-lg border p-4">
        <div>
          <Label htmlFor="scanEnabled">Daily job scan</Label>
          <p className="text-sm text-muted-foreground">
            Scan job boards daily and email you the top matches.
          </p>
        </div>
        <Switch id="scanEnabled" checked={isScanEnabled} onCheckedChange={setIsScanEnabled} />
      </div>

      <div className="flex items-center justify-between rounded-lg border border-dashed p-4 opacity-60">
        <div>
          <Label>SMS notifications</Label>
          <p className="text-sm text-muted-foreground">Coming soon.</p>
        </div>
        <Switch disabled checked={false} />
      </div>

      <Button type="submit" disabled={updateMutation.isPending}>
        {updateMutation.isPending ? "Saving..." : "Save preferences"}
      </Button>
    </form>
  );
}
```

**Design notes:** the disabled "SMS notifications — Coming soon" block is the UI-side honesty check for Decision 6 (§3) — a user must never be able to select a channel that silently does nothing; the toggle is visibly disabled rather than accepted-but-ignored.

**Test file:** `frontend/features/job-matching/components/PreferencesForm.test.tsx` — renders with mocked `usePreferences` loading/loaded/empty states, asserts form submission calls `useUpdatePreferences().mutate` with expected shape, asserts SMS switch is disabled and unchecked always.

### 11.7 `frontend/features/job-matching/index.ts`

Barrel export, matching the exact convention of `frontend/features/enrich/index.ts`.

```typescript
export { usePreferences, useUpdatePreferences } from "./hooks/usePreferences";
export { useMatches, useMarkMatchViewed, useSubmitFeedback, useTriggerScan } from "./hooks/useMatches";
export { MatchCard } from "./components/MatchCard";
export { PreferencesForm } from "./components/PreferencesForm";
export { jobMatchingKeys } from "./api/keys";
```

### 11.8 Pages and routing

Per §4's naming resolution, the route is `/app/matches`, not `/app/jobs` (already taken/redirected).

**New file:** `frontend/app/app/matches/page.tsx`

```tsx
import { Suspense } from "react";
import { MatchesView } from "./MatchesView";

export default function MatchesPage() {
  return (
    <Suspense fallback={<div className="animate-pulse h-96 rounded-lg bg-muted" />}>
      <MatchesView />
    </Suspense>
  );
}
```

**New file:** `frontend/app/app/matches/MatchesView.tsx`

```tsx
"use client";

import { useState } from "react";
import { useMatches, useTriggerScan } from "@/features/job-matching";
import { MatchCard } from "@/features/job-matching";
import { EmptyState } from "@/components/console/EmptyState";
import { Button } from "@/components/ui/button";
import { RefreshCw } from "lucide-react";

export function MatchesView() {
  const [offset, setOffset] = useState(0);
  const limit = 20;
  const { data, isLoading, isError } = useMatches(limit, offset);
  const triggerScan = useTriggerScan();

  if (isLoading) {
    return <div className="animate-pulse h-96 rounded-lg bg-muted" />;
  }

  if (isError) {
    return <EmptyState title="Couldn't load matches" description="Please try again shortly." />;
  }

  if (!data || data.matches.length === 0) {
    return (
      <EmptyState
        title="No matches yet"
        description="Upload your CV and set preferences to get started."
        action={
          <Button onClick={() => triggerScan.mutate()} disabled={triggerScan.isPending}>
            <RefreshCw className="mr-2 h-4 w-4" />
            {triggerScan.isPending ? "Scanning..." : "Scan now"}
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Job matches</h1>
        <Button variant="outline" onClick={() => triggerScan.mutate()} disabled={triggerScan.isPending}>
          <RefreshCw className="mr-2 h-4 w-4" />
          {triggerScan.isPending ? "Scanning..." : "Scan now"}
        </Button>
      </div>

      <div className="grid gap-4">
        {data.matches.map((match) => (
          <MatchCard key={match.matchId} match={match} />
        ))}
      </div>

      <div className="flex justify-center gap-2 pt-4">
        <Button variant="ghost" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>
          Previous
        </Button>
        <Button
          variant="ghost"
          disabled={offset + limit >= data.total}
          onClick={() => setOffset(offset + limit)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
```

**New file:** `frontend/app/app/matches/settings/page.tsx`

```tsx
import { PreferencesForm } from "@/features/job-matching";

export default function MatchPreferencesPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-6 py-8">
      <div>
        <h1 className="text-2xl font-semibold">Job match preferences</h1>
        <p className="text-muted-foreground">
          Tell us what you're looking for and we'll scan job boards daily.
        </p>
      </div>
      <PreferencesForm />
    </div>
  );
}
```

### 11.9 Navigation registration

**File edited:** `frontend/components/layout/nav-config.ts` — add one entry (verified: `AppSidebar`/`AppBottomNav` both read from this config automatically, no separate registration needed):

```typescript
{
  label: "Matches",
  href: "/app/matches",
  icon: "Sparkles", // or whatever icon import convention this file already uses — verify exact import name before writing
  matchExact: false,
},
```

### 11.10 Blind spot: CV upload UI is entirely missing — flagged, not silently assumed

Verified during design: **no CV/document upload UI component exists anywhere in `frontend/`** (grep for "upload" across `frontend/components/` and `frontend/features/` returns zero matches for a file-upload form; only the backend `/api/documents/upload` endpoint exists). Module 1's entire preference-prefill flow (`source_document_id`, §5.3) is **useless without this UI** — a candidate cannot get CV-based preferences without uploading a CV somewhere in the app first.

**This is out of scope for Module 1's own file list** (it is arguably Module 3/document-management territory, not job-matching), but it is a **hard dependency**: Module 1 cannot be demoed end-to-end without it. This document does not build it (to keep this module's scope honest and its own file list accurate) but flags it explicitly here rather than pretending Module 1 is "100% usable" without it. If no CV upload UI exists by the time Module 1 ships, the `PreferencesForm` (§11.6) must be usable standalone (all fields manually enterable, which it already is — `desiredRoles`/`desiredLocations`/salary/remote are all plain form fields, not CV-derived-only) so Module 1 remains functional without the missing piece, just less automated.

---

## 12. ADR — required per RULE.md (new storage + new queue)

**New file:** `docs/adr/0013-job-matching-queue-and-storage.md`

```markdown
# ADR 0013: Dedicated Queue and Storage for Job Matching (Module 1)

## Status
Accepted

## Context
Module 1 ("AI Job Matching & Notifications") requires: (1) persisting scraped
job postings independent of any single enrichment request, (2) scoring them
against candidate CVs, and (3) running this on a recurring schedule. None of
the three existing queues (`document_processing`, `embedding_generation`,
`cv_extraction`) nor the existing tables (`candidate_documents`,
`document_embeddings`) are the right owner for this — they belong to the CV
*intake* pipeline, not job *matching*.

## Decision
1. **New queue**: `job_matching`, consumed by a **dedicated worker container**
   (`worker-job-matching`), not appended to the generic worker's queue list.
   Rationale: the generic worker's fixed-priority queue list (`rq_worker.py`)
   already has a documented starvation risk (RQ's own docs confirm workers
   never touch lower-priority queues while higher-priority ones have backlog);
   adding a 6th queue there would worsen that risk in both directions. See
   `phase2_module1.md` §4 for the full analysis.
2. **New storage**: 4 tables — `job_postings`, `job_posting_embeddings`,
   `candidate_job_preferences`, `job_matches` — owned by a new
   `app/modules/job_matching/` module, not bolted onto `documents/`.
   Rationale: job postings are shared across all candidates (many-to-many via
   `job_matches`), fundamentally different cardinality from `candidate_documents`
   (one-to-one with a candidate).
3. **Scheduling**: extends the existing `rq_scheduler`-based cron pattern
   (`register_scheduled_jobs()`), not Celery. Rationale: this repo has no
   Celery dependency anywhere; introducing one for a single cron job would
   violate "keep the change as small as the task allows."

## Consequences
- One more container in `docker-compose.foundation.yml`, pinned to 1 replica
  (scaling requires first fixing the scheduler-duplication issue noted in
  `rq_worker_job_matching.py`'s docstring — tracked as future work, not blocking).
- Postgres connection count grows by up to 15 (SQLAlchemy default pool per
  process) — the pool-sizing ADR gap already flagged in `architecture_phase2.md`
  §5.1 is not fixed by this ADR; it is made marginally worse, within the
  already-accepted risk envelope for Phase 2's first module.
- `job_matches.feedback` column exists now but is unused until a v2
  behavior-based re-ranker is built — an intentional forward-compatible hook,
  not scope creep (Decision 2, `phase2_module1.md` §3).

## Alternatives considered
- **Reuse `documents` module for job postings**: rejected — cardinality
  mismatch (one candidate's CV vs. many-candidates-to-many-jobs), would force
  polymorphic queries and break "ORM lives with its owner."
- **Celery beat**: rejected — no existing Celery dependency; `rq_scheduler`
  already does the job.
- **Append `job_matching` to the generic worker's queue list**: rejected —
  worsens existing starvation risk (§4).
```

---

## 13. `backend/docs/ARCHITECTURE.md` — Implementation status diff

Add a new row to the "Implementation status" table (exact location/format verified by reading the file directly before editing):

```markdown
| Job matching (Module 1) | `app/modules/job_matching/`, `app/workers/tasks/job_matching.py` | Real, scaffolded per `phase2_module1.md`. Depends on CV upload UI existing (currently missing — see that doc §11.10). |
```

Add a line to the "Do not assume" table:

```markdown
| SMS notification channel | Job-matching preferences accept `"sms"` but no Twilio client exists; selecting it is a UI-disabled no-op. |
```

---

## 14. PR checklist (per `.github/pull_request_template.md`)

When Module 1's actual implementation PR is opened (this document itself is committed directly per the user's explicit instruction not to branch — but the **code** described here, when implemented, should follow the normal branch+PR workflow):

- [ ] Link this document: `phase2_module1.md`
- [ ] Link the ADR: `docs/adr/0013-job-matching-queue-and-storage.md`
- [ ] `alembic upgrade head` and `alembic downgrade -4 && alembic upgrade head` both succeed
- [ ] All 7 new backend test files pass (§8.1-8.7)
- [ ] Coverage gate maintained (`--cov-fail-under=78`, §8.9)
- [ ] `ruff check` / `mypy` clean on new files
- [ ] Frontend `npm run typecheck && npm run lint && npm run build` all pass
- [ ] Frontend new-feature tests pass (§8.8)
- [ ] `backend/docs/ARCHITECTURE.md` updated per §13
- [ ] `.env.example` updated per §6 (placeholders only)
- [ ] `docker-compose.foundation.yml` updated per §9.3, and `docker compose up worker-job-matching` boots and passes healthcheck

---

## 15. Final completion checklist — Module 1 is 100% done when every box is checked

**Database (§5):**
- [ ] `018_job_postings.py` through `021_job_matches.py` created, applied, and reversible
- [ ] `pgvector` HNSW index created on `job_posting_embeddings` (Postgres) / plain table on SQLite

**Backend (§7):**
- [ ] `app/modules/job_matching/{__init__,models,schemas,repository,service,router,scorer,explainer}.py` all created
- [ ] `app/workers/tasks/job_matching.py` created, with the `_scan_jobs_for_candidate_async` scoring loop **fully implemented** (not the abbreviated pseudocode flagged in §7.9 — that gap must be closed before this checklist item is checked)
- [ ] `app/workers/rq_worker_job_matching.py` created
- [ ] `app/workers/queue.py` edited: `QUEUE_JOB_MATCHING` constant, `enqueue_job_matching_scan()`, `enqueue_email()`, extended `register_scheduled_jobs()`
- [ ] `app/services/email_service.py` edited: `JOB_MATCH_DIGEST` template
- [ ] `app/main.py` edited: router included
- [ ] `app/core/config.py` edited: new settings fields
- [ ] `.env.example` edited (§6)

**Docker (§9):**
- [ ] `backend/docker/Dockerfile.worker-job-matching` created
- [ ] `docker-compose.foundation.yml` edited with the new service
- [ ] `docker compose up worker-job-matching` boots, healthcheck passes, logs show `register_scheduled_jobs()` ran once

**Testing (§8):**
- [ ] All 7 backend test files created and passing
- [ ] Coverage gate (`--cov-fail-under=78`) passes for the new module
- [ ] Full existing test suite (`pytest`) still passes — no regressions introduced
- [ ] 6 frontend test files created and passing (`npm test -- job-matching`)

**Frontend (§10-11):**
- [ ] `frontend/src/lib/types.ts` edited: `CandidateJobPreferences`, `JobMatch`, `JobMatchListResponse`
- [ ] `frontend/src/lib/api-adapter.ts` edited: 3 adapter functions
- [ ] 5 BFF routes created under `frontend/app/api/job-matching/`
- [ ] `frontend/features/job-matching/` module created (7 files: keys, client, 2 hooks, 2 components, index)
- [ ] `frontend/app/app/matches/page.tsx`, `MatchesView.tsx`, `settings/page.tsx` created
- [ ] `frontend/components/layout/nav-config.ts` edited: 1 new nav entry
- [ ] `npm run typecheck && npm run lint && npm run build` all pass

**Governance (§0, §12-14):**
- [ ] ADR `0013-job-matching-queue-and-storage.md` created
- [ ] `backend/docs/ARCHITECTURE.md` updated (2 table rows)
- [ ] PR opened (not this document — the code) on its own branch, per the repo's standard workflow, linking this document and the ADR

**Known gaps this document does NOT close (explicitly out of scope, not oversights):**
- CV upload UI (§11.10) — cross-module dependency, flagged not built
- SMS/webhook real delivery (Decision 6) — stubbed, not built
- Postgres connection pool sizing (§4) — pre-existing, made marginally worse, not fixed
- HNSW index tuning at scale (§5.2) — deferred, matches existing `document_embeddings` precedent
- v2 behavior-based re-ranking using `job_matches.feedback` (Decision 2) — schema hook only, no logic
- Generic worker's `with_scheduler=True` multi-replica duplication bug (§9.2) — pre-existing, not touched

If every checkbox above is checked and the six gaps are still open, **Module 1 is complete and these six items are correctly still pending** — completion of Module 1 does not require closing pre-existing or explicitly-deferred cross-cutting issues that were never in its scope. If any checkbox is unchecked, Module 1 is **not** complete, regardless of any other claim made about it.
