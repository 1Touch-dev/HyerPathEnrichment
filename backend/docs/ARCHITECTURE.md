# Backend Architecture

Hyrepath Enrichment backend — architecture reference for the FastAPI service under `backend/`.

**Version:** 0.2 (July 2026)  
**Last verified against code:** 2026-07-08  
**Repo layout:** `HyerEnrichment/backend/` (split from the Next.js frontend in `frontend/`)

---

## Agent quick reference

**Read this file when:** backend API, orchestrator, enricher, opt-out, tier, storage, or Docker work.

**Trust order (highest wins):**

1. Code in `backend/app/`
2. **Implementation status** section below (scaffold vs target)
3. This doc (architecture + routing)
4. `docs/architecture-plan-azi-10-hyre-enrichment.md` (original plan — may be ahead of code)
5. `docs/IMPLEMENTATION_NOTES.md` (AZI-11 handoff)

### Do not assume (common agent mistakes)

| Assumption | Reality today |
|------------|---------------|
| `POST /enrich` runs inline | Enqueues to **Redis + RQ**; the worker process runs the orchestrator. `/enrich/sync` still runs inline. Needs a shared DB (Postgres) to poll across processes |
| Enrichers call real tools | Most return **scaffold/mock payloads** |
| Database is Postgres | Default is **SQLite** (`sqlite+aiosqlite:///./hyrepath.db`) |
| R2 uploads go to Cloudflare | Writes to **local** `backend/.asset-cache/` |
| LiteLLM disambiguation is live | **Heuristic stub** in `llm_router.py` |
| Opt-out is unauthenticated | **Bearer token required** (compliance gap vs target) |
| Suppression lives in Redis only | **SQL table** `suppression_list` is the durable record; Redis set `suppression:hashes` is a fast-path cache (dual-write, SQL fallback) |
| Sidecars are real services | Docker compose uses **nginx placeholders** |

### Task routing — where to start

| Task | Read first | Edit |
|------|------------|------|
| New enricher | Enricher protocol + tier table | `enrichers/base.py` → new module → `workers/runner.py` tier list |
| Change merge/dossier shape | `models.py` `Dossier` + frontend types | `workers/runner.py` `_merge()`, `models.py`, `frontend/src/lib/types.ts` |
| API route / auth | API endpoints section | `routes/enrich.py`, `routes/opt_out.py`, `main.py` |
| Async job queue | Implementation status | `routes/enrich.py`, `workers/runner.py`, `docker/docker-compose.yml` |
| Opt-out / suppression | Legal section + `_is_suppressed()` | `workers/runner.py`, `routes/opt_out.py`, `models.py` `SuppressionRecord` |
| Photo / Tier 1 | Tier 1 section | `enrichers/linkedin_photo.py`, `storage/r2.py`, `multilogin.py` |
| Env / config | Environment variables section | `config.py`, `.env.example` |
| Tests | Testing strategy | `tests/test_pipeline_shape.py` |
| Frontend integration | Frontend contract below | `frontend/src/lib/api-adapter.ts`, `frontend/src/lib/types.ts` |

### Frontend contract (keep in sync)

Backend `Dossier` is defined in `backend/app/models.py`. Frontend mirror: `frontend/src/lib/types.ts`. API adapter: `frontend/src/lib/api-adapter.ts`. Field naming differs (`linkedin_url` backend vs `linkedinUrl` frontend) — check adapter, don't guess.

### Agent read order (minimal tokens)

1. This **Agent quick reference** section
2. **Implementation status** table (scroll to it or search `## Implementation status`)
3. Only the sections matching your task (tier table, API, folder structure, etc.)
4. Relevant source files — always verify behavior in code before implementing

---

This document describes the **target production architecture** and calls out where the **current scaffold** differs.

---

## What this service does

Hyrepath Enrichment is a **self-hosted enrichment API**. A client sends one or more identifiers (email, LinkedIn URL, username, company, business query, or job search). The backend returns a unified **dossier**:

- LinkedIn profile photo (cached in Cloudflare R2)
- Cross-site social handles (GitHub, X, Reddit, and thousands more)
- Public commit emails and GitHub metadata
- Guessed and SMTP-verified corporate emails
- Coworkers at the same company
- Open job posts across multiple boards
- Local business info when relevant

Everything is built on **open-source enrichers** behind a common plugin interface. The customer owns the code and the data.

### Audiences and typical tier mixes

| Audience | Main need | Tiers |
|----------|-----------|-------|
| Candidate placement | Job matching across boards | 4 + 2 |
| Recruiters | Identity + GitHub + personal site | 1 + 2 + 3 |
| Sales | Work email, coworkers, social proof | 3 |
| Investors | Founder due diligence | 1 + 2 + 3 + 4 |
| Journalists / bookers | Best contact channel | 2 + 3 |

---

## High-level architecture

```
                            ┌──────────────────────┐
   Client (recruiter,       │  POST /enrich          │
   sales, ATS, frontend)  ──▶  {email|linkedin|...  │  FastAPI + Bearer auth
                            │   requested_tiers}     │
                            └───────────┬──────────┘
                                        │ enqueue (target)
                                        ▼
                             ┌────────────────────┐
                             │  Redis + RQ Queue  │  ← target; inline today
                             └────────┬───────────┘
                                      │ dequeue
                                      ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │              PipelineOrchestrator (workers/runner.py)            │
   │                                                                  │
   │  ┌──────────┐  ┌────────────┐  ┌────────────┐  ┌─────────────┐  │
   │  │ Tier 1   │  │  Tier 2    │  │  Tier 3    │  │  Tier 4     │  │
   │  │ LinkedIn │  │ Sherlock   │  │ gitrecon   │  │ JobSpy      │  │
   │  │ photo    │  │ Maigret    │  │ Harvester  │  │ GMaps       │  │
   │  │          │  │ SocialAnal │  │ email-sleuth│ │ scraper     │  │
   │  │          │  │            │  │ Reacher    │  │             │  │
   │  │          │  │            │  │ CrossLinked│  │             │  │
   │  └────┬─────┘  └─────┬──────┘  └─────┬──────┘  └──────┬──────┘  │
   │       └──────────────┴───────┬───────┴────────────────┘          │
   │                              ▼                                    │
   │                    ┌──────────────────┐                           │
   │                    │ LLM Disambiguator │ LiteLLM → cheapest model │
   │                    │ conf threshold 0.7│                           │
   │                    └────────┬─────────┘                           │
   └───────────────────────────── │ ─────────────────────────────────┘
                                  ▼
              ┌────────────────────────────────────┐
              │  Postgres — jobs + dossier JSONB   │
              │  Cloudflare R2 — photo cache       │
              │  Redis — opt-out set, rate limits  │
              └────────────────────────────────────┘

  Sidecars (isolated Docker services, HTTP calls):
  ┌────────────┐  ┌─────────────┐  ┌────────────┐  ┌──────────┐  ┌──────────────┐
  │ Reacher    │  │ email-verif │  │ social-anl │  │ gmaps    │  │ changedetect │
  │ (AGPL)     │  │ (AfterShip) │  │ (AGPL)     │  │ scraper  │  │ .io          │
  └────────────┘  └─────────────┘  └────────────┘  └──────────┘  └──────────────┘

  ┌────────────┐  ┌─────────────┐
  │ Scrapoxy   │  │  Langfuse   │
  │ (proxies)  │  │ (LLM obs.)  │
  └────────────┘  └─────────────┘
```

### Layered design

The backend is a **modular monolith**:

1. **Routes** (`app/routes/`) — HTTP surface, auth, request/response models
2. **Services** (`app/services.py`) — factory for the orchestrator
3. **Orchestrator** (`app/workers/runner.py`) — suppression check, tier dispatch, merge, confidence
4. **Enrichers** (`app/enrichers/`) — one module per upstream tool, shared `Enricher` protocol
5. **Storage** (`app/storage/`) — async SQLAlchemy sessions, R2 asset client
6. **LLM router** (`app/llm_router.py`) — disambiguation for low-confidence handles

---

## Request flow

```
1. Input                    2. Enrichment                 3. Output
────────                    ─────────────                 ──────────

email ─────────────┐                                      ┌── photo CDN URL
linkedin_url ──────┤         ┌──────────────┐            ├── handles[]
username ──────────┼────────▶│  Pipeline    │───────────▶├── github / emails
company ───────────┤         │  (tiers +    │            ├── coworkers[]
job_search ────────┤         │   LLM pass)  │            ├── jobs[]
business ──────────┘         └──────┬───────┘            └── business profile
                                    │
                             Opt-out check
                          (SHA-256 identifier)
                                    │
                           [suppressed?] ──▶ empty dossier, status suppressed
                                    │
                                  [ok]
                                    ▼
                              Run requested tiers
                              (parallel per enricher)
                                    ▼
                              Merge → confidence → persist
```

### Step-by-step (current code path)

1. `POST /enrich` or `POST /enrich/sync` hits `app/routes/enrich.py`
2. `verify_token` dependency checks `Authorization: Bearer <API_TOKEN>`
3. Per-route rate-limit dependency enforces the sync/async limit (Redis counter, `429` over-limit)
4. `EnrichmentRequest` validates at least one identifier and optional `requested_tiers`
5. **`POST /enrich` (async):** `create_queued_job()` persists a `JobRecord` with status `queued`, then `enqueue_enrichment(job.id)` pushes it to the RQ `enrichment` queue; returns `202`. If Redis is unreachable the job is marked `failed` and the API returns `503`.
6. **`POST /enrich/sync` (inline):** `PipelineOrchestrator.run()` executes the pipeline in the API process and returns the completed dossier.
7. The pipeline body (`_execute()`, shared by both paths and the worker):
   - checks suppression via `_is_suppressed()` (Redis set, SQL fallback)
   - if suppressed → returns dossier with `metadata.suppressed = true`
   - else dispatches enrichers for requested tiers in parallel (`asyncio.gather`)
   - merges payloads into a canonical `Dossier`
   - runs confidence scoring + LLM disambiguation pass
   - persists dossier JSON and marks job `completed` (or `failed` on error)
8. The **worker** (`app/workers/rq_worker.py`) dequeues, opens its own DB session, and calls `execute_job(job_id)` → `_execute()`
9. `GET /enrich/{job_id}` polls the stored job (`queued` → `running` → `completed`/`failed`/`suppressed`)

**Cross-process caveat:** the async path is only end-to-end when the API and worker share a database. The default SQLite is per-container, so promote both to Postgres (open question #4) for a real deployment.

---

## Four enrichment tiers

Each tier maps to enricher modules in `app/enrichers/`. The orchestrator registers them in `PipelineOrchestrator.__init__`.

### Tier 1 — LinkedIn photo (browser-based)

| Module | Upstream | Integration |
|--------|----------|-------------|
| `linkedin_photo.py` | `joeyism/linkedin_scraper` + Playwright | Multilogin X stealth browser over CDP; photo uploaded to R2 |

- One browser session per profile lookup — no bulk scraping
- Multilogin runs on the host; worker reaches it at `host.docker.internal:45001`
- Only the profile picture is captured, not full profile export

### Tier 2 — Cross-site username hunt (no browser)

Runs in parallel when `tier2` is requested:

| Module | Upstream | Confidence base |
|--------|----------|-----------------|
| `sherlock.py` | `sherlock-project/sherlock` (MIT) | ~0.75 |
| `maigret.py` | `soxoj/maigret` (MIT) | ~0.85 |
| `social_analyzer.py` | `qeeqbox/social-analyzer` (AGPL) | NLP scoring via HTTP sidecar |

Results are merged, deduplicated, and scored. Handles below **0.7** go to the LLM disambiguator.

### Tier 3 — Deep OSINT (GitHub + email + company)

| Module | Upstream | Role |
|--------|----------|------|
| `gitrecon.py` | `GONZOsint/gitrecon` | Commit emails, names, orgs from GitHub |
| `theharvester.py` | `laramies/theHarvester` | Company-wide email harvest |
| `email_discover.py` | `buyukakyuz/email-sleuth` | Pattern-guess corporate emails |
| `email_verify.py` | Reacher + AfterShip + mailchecker | SMTP verify, catch-all detection, disposable blocklist |
| `crosslinked.py` | `m8sec/CrossLinked` | Coworker enumeration without LinkedIn login |

### Tier 4 — Job match + local business

| Module | Upstream | Role |
|--------|----------|------|
| `jobspy.py` | `speedyapply/JobSpy` | Multi-board job pull (LinkedIn, Indeed, Glassdoor, Google Jobs, ZipRecruiter) |
| `local_business.py` | `gosom/google-maps-scraper` | Address, phone, website, rating via sidecar |

### LLM post-pass — disambiguation

`app/llm_router.py` (`LiteLLMDisambiguator`) resolves ambiguous handles:

- Trigger: confidence **&lt; 0.7** (configurable via `DISAMBIGUATION_THRESHOLD`)
- Routed through **LiteLLM** to the cheapest capable model with fallback chain
- Traced in **Langfuse** for cost and quality review
- Only kept if LLM confidence **≥ 0.7**

**Current:** heuristic string-match stub with a placeholder reason. **Target:** real LiteLLM + Langfuse integration per `docs/architecture-plan-azi-10-hyre-enrichment.md`.

---

## Enricher protocol

All enrichers implement `app/enrichers/base.py`:

```python
class Enricher(ABC):
    source_name: str

    async def initialize(self) -> None: ...
    async def cleanup(self) -> None: ...
    async def validate(self, request: EnrichmentRequest) -> bool: ...
    async def run(self, request: EnrichmentRequest) -> dict[str, Any]: ...
    async def normalize(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    async def score(self, payload: dict[str, Any]) -> dict[str, Any]: ...
```

Lifecycle per enricher in `_dispatch()`:

1. `validate()` — skip if required identifier missing
2. `initialize()` → `run()` → `normalize()` → `score()`
3. `cleanup()` in a `finally` block

Each enricher returns a partial dict (`photo`, `handles`, `emails`, `verified_emails`, `github`, `coworkers`, `jobs`, `business`, `sources`). The orchestrator merges them into one `Dossier`.

---

## Storage

### Database (SQLAlchemy 2 async)

| Table | Purpose |
|-------|---------|
| `jobs` | Job id, status, request JSON, dossier JSONB, timestamps |
| `suppression_list` | SHA-256 hashed identifiers + opt-out reason |

**Target:** PostgreSQL via `DATABASE_URL`.  
**Current default:** SQLite (`sqlite+aiosqlite:///./hyrepath.db`) for local development.

### Object storage (R2)

`app/storage/r2.py` — Cloudflare R2 via S3-compatible API (`aioboto3` in production).

**Current:** writes to `backend/.asset-cache/` and returns a CDN URL from `R2_PUBLIC_BASE_URL`. Interface matches production.

### Redis (target)

- Job queue (RQ)
- Opt-out suppression set (fast lookup)
- Rate limiting
- Audit log hashes (5-year retention per request)

Configured via `REDIS_URL`. Present in docker-compose. A shared async client exists in `app/storage/redis_client.py` (`get_redis` FastAPI dependency, opened/closed in the app lifespan, lazy connection).

**Wired today:**

- *Suppression fast path.* `add_suppression()` writes SQL first (durable record), then `SADD suppression:hashes`. `check_suppression()` tries `SISMEMBER` first; on a miss or Redis error it falls back to the authoritative SQL table and backfills Redis on a hit. Opt-out is never weakened by a Redis outage — no TTL on suppression hashes.
- *Rate limiting.* Fixed-window counters (`ratelimit:{sync|async}:{token-hash}`) via `check_rate_limit()`. `POST /enrich` enforces `MAX_ASYNC_REQUESTS_PER_MINUTE`; `POST /enrich/sync` enforces `MAX_SYNC_REQUESTS_PER_MINUTE`. Dependencies live in `app/routes/rate_limit.py`. Over-limit returns `429`. **Fails open** on Redis error — protection, not correctness. Scope is per API token (SHA-256, first 16 hex chars); raw tokens are never logged.
- *Job queue (RQ).* `POST /enrich` enqueues to the `enrichment` queue via `app/workers/queue.py` (synchronous `redis-py` connection — RQ is not async-compatible). The worker (`app/workers/rq_worker.py`) dequeues and calls `run_enrichment_job` (`app/workers/jobs.py`), which bridges to the async orchestrator with `asyncio.run` and a fresh DB session. Enqueue failure marks the job `failed` and returns `503`.

**Redis roles now wired:** suppression fast path, rate limiting, job queue. Audit-log hashes remain target-only.

---

## API endpoints

All enrichment and opt-out routes require `Authorization: Bearer <API_TOKEN>` in the **current** implementation.

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/enrich` | Create enrichment job (202 Accepted) |
| `GET` | `/enrich/{job_id}` | Poll job status + dossier |
| `POST` | `/enrich/sync` | Synchronous enrichment path |
| `POST` | `/api/opt-out` | Register identifier suppression (LGPD/GDPR/CCPA) |
| `GET` | `/api/opt-out/check?identifier=` | Check if identifier is suppressed |
| `GET` | `/health` | Liveness |
| `GET` | `/ready` | Readiness |
| `GET` | `/metrics` | Prometheus metrics (when `prometheus_client` installed) |

### Example request

```json
POST /enrich
Authorization: Bearer <API_TOKEN>

{
  "username": "jane-doe",
  "linkedin_url": "https://www.linkedin.com/in/jane-doe",
  "company": "Acme",
  "job_search": "senior backend engineer remote",
  "business": "Acme Coffee Curitiba",
  "requested_tiers": ["tier1", "tier2", "tier3", "tier4"]
}
```

### Example response shape

```json
{
  "id": "job_abc123",
  "status": "completed",
  "dossier": {
    "photo": { "source": "linkedin-photo", "asset_url": "...", "confidence": 0.84 },
    "handles": [{ "platform": "X", "username": "jane-doe", "confidence": 0.75 }],
    "emails": ["jane@acme.com"],
    "verified_emails": [{ "value": "jane.doe@acme.com", "status": "verified", "confidence": 0.89 }],
    "github": { "profile": "...", "organizations": [], "public_commits": 0 },
    "coworkers": ["bob@acme.com"],
    "jobs": [{ "title": "Senior Backend Engineer", "company": "Acme", "remote": true }],
    "business": { "name": "Acme Coffee", "address": "...", "rating": 4.5 },
    "confidence": [{ "label": "identity-match", "score": 0.91, "evidence": [] }],
    "sources": ["Sherlock", "gitrecon"],
    "metadata": { "requested_tiers": ["tier1", "tier2"], "identifier_summary": "..." }
  }
}
```

**Target policy:** `POST /api/opt-out` should be **unauthenticated** so data subjects can opt out without an API key. Track this as a compliance gap in the current scaffold.

---

## Folder structure

```text
HyerEnrichment/
├── frontend/                     # Next.js UI (intake, pipeline, dossier)
└── backend/
    ├── app/
    │   ├── main.py               # FastAPI entrypoint, auth, route registration
    │   ├── config.py             # Env-driven settings
    │   ├── models.py             # Pydantic schemas + SQLAlchemy models
    │   ├── services.py           # Orchestrator factory
    │   ├── multilogin.py         # Multilogin API client (Tier 1)
    │   ├── llm_router.py         # LiteLLM disambiguation
    │   ├── enrichers/
    │   │   ├── base.py           # Enricher protocol
    │   │   ├── linkedin_photo.py # Tier 1
    │   │   ├── sherlock.py       # Tier 2
    │   │   ├── maigret.py        # Tier 2
    │   │   ├── social_analyzer.py# Tier 2 (HTTP sidecar)
    │   │   ├── gitrecon.py       # Tier 3
    │   │   ├── theharvester.py   # Tier 3
    │   │   ├── email_discover.py # Tier 3 (email-sleuth)
    │   │   ├── email_verify.py   # Tier 3 (Reacher + AfterShip)
    │   │   ├── crosslinked.py    # Tier 3 (coworkers)
    │   │   ├── jobspy.py         # Tier 4
    │   │   └── local_business.py # Tier 4 (GMaps sidecar)
    │   ├── routes/
    │   │   ├── enrich.py         # /enrich, /enrich/sync, /enrich/{id}
    │   │   ├── health.py         # /health, /ready, /metrics
    │   │   └── opt_out.py        # /api/opt-out, /api/opt-out/check
    │   ├── storage/
    │   │   ├── db.py             # Async SQLAlchemy session
    │   │   └── r2.py             # R2 asset client
    │   └── workers/
    │       └── runner.py         # PipelineOrchestrator
    ├── docker/
    │   ├── Dockerfile.api
    │   ├── Dockerfile.worker
    │   └── docker-compose.yml    # api, worker, pg, redis, sidecar placeholders
    ├── docs/
    │   └── ARCHITECTURE.md       # this file
    ├── scripts/
    │   └── smoke_test.py
    ├── tests/
    │   └── test_pipeline_shape.py
    ├── .env.example
    ├── pyproject.toml
    └── README.md
```

---

## Environment variables

Copy `backend/.env.example` → `backend/.env`.

### Required today

| Variable | Purpose |
|----------|---------|
| `API_TOKEN` | Bearer token for protected routes |
| `DATABASE_URL` | Async DB URL (SQLite default; Postgres in production) |
| `REDIS_URL` | Redis connection (queue + suppression target) |
| `R2_BUCKET` | R2 bucket name |
| `R2_PUBLIC_BASE_URL` | CDN base for cached photos |

### Tier 1 (LinkedIn photo) — target

| Variable | Purpose |
|----------|---------|
| `MULTILOGIN_EMAIL` | Multilogin account |
| `MULTILOGIN_PASSWORD_MD5` | Multilogin auth |
| `MULTILOGIN_FOLDER_ID` | Profile pool folder |
| `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | R2 credentials |

### Tier 3 (email) — target

| Variable | Purpose |
|----------|---------|
| `REACHER_URL` | Reacher sidecar endpoint |
| `REACHER_FROM_EMAIL` | SMTP HELO sender mailbox |

### LLM disambiguation — target

| Variable | Purpose |
|----------|---------|
| `LITELLM_MODEL` | Primary model |
| `LITELLM_FALLBACKS` | Fallback chain |
| `LITELLM_API_KEY`, `LITELLM_API_BASE` | LiteLLM proxy config |
| `DISAMBIGUATION_THRESHOLD` | Default `0.7` |

### Rate limits (enforced per API token via Redis fixed-window counters)

| Variable | Default |
|----------|---------|
| `MAX_SYNC_REQUESTS_PER_MINUTE` | 10 |
| `MAX_ASYNC_REQUESTS_PER_MINUTE` | 30 |
| `LINKEDIN_PHOTO_TTL_SECONDS` | 86400 |
| `USERNAME_LOOKUP_TTL_SECONDS` | 3600 |

---

## Docker services

`backend/docker/docker-compose.yml` defines the target topology:

| Service | Role |
|---------|------|
| `api` | FastAPI on port 8000 |
| `worker` | RQ worker running the orchestrator |
| `postgres` | Job + suppression persistence |
| `redis` | Queue + suppression + rate limits |
| `social-analyzer` | AGPL sidecar (Tier 2) |
| `reacher` | SMTP verification sidecar (Tier 3) |
| `google-maps-scraper` | Local business sidecar (Tier 4) |
| `litellm` | LLM proxy |
| `langfuse` | LLM observability |
| `changedetection` | Company change signals (future webhooks) |

**Current:** sidecar images are placeholders (`nginx:alpine`). Enrichers return scaffold payloads until real integrations land.

### AGPL isolation

AGPL tools (`social-analyzer`, Reacher) run as **isolated sidecars** called over HTTP. Application code stays MIT-compatible; AGPL code never links into the main package.

---

## Legal, compliance, and product boundaries

### Legal posture

- **Public data only** — public profiles, commits, search results
- **Customer-supplied identifiers only** — no unsolicited people-finding
- **LGPD / GDPR / CCPA** — opt-out honored globally
- **DSAR** — data subject requests answered within 30 days

### Enforcement in code

1. `POST /api/opt-out` writes SHA-256(identifier) to `suppression_list`
2. `PipelineOrchestrator._is_suppressed()` runs **before** any tier dispatch
3. Suppressed requests return an empty dossier with `status: suppressed`

### Hard product boundaries (policy, not technical limits)

1. **No face recognition** — photos are for display only
2. **No bulk scraping** — one profile per session
3. **No private data** — public sources only
4. **No enrichment without a customer-supplied identifier**
5. **Opt-out is permanent** — blocked across all tiers once registered

---

## Implementation status

> **Agents:** Treat this table as the source of truth for what exists today vs what is planned. Update **Last verified against code** at the top when this table changes.

| Area | Target (v0.2 guide) | Current scaffold |
|------|---------------------|------------------|
| API routes + auth | FastAPI + Bearer | Implemented |
| Orchestrator + tier dispatch | `runner.py` | Implemented |
| Enricher modules (11) | Real tool integrations | Scaffold payloads / mocks |
| Redis client | Queue + suppression + rate limits | Shared async client wired in lifespan; suppression, rate limiting, and queue all use it |
| Async job queue | Redis + RQ, worker process | Implemented — `/enrich` enqueues, `rq_worker` executes; needs shared Postgres for cross-process polling |
| Database | PostgreSQL + JSONB | SQLite default |
| R2 photo cache | `aioboto3` → Cloudflare R2 | Local `.asset-cache/` fallback |
| Multilogin + Playwright | CDP browser session | Client stub; mock photo bytes |
| LiteLLM disambiguation | Routed LLM calls | Heuristic string match |
| Langfuse tracing | Per disambiguation call | Not wired |
| Sidecars | 5+ isolated services | Placeholder containers |
| Opt-out auth | Unauthenticated POST | Bearer required (gap) |
| Scrapoxy proxy pool | Rate-limit hardening | Not integrated |
| Prometheus metrics | `/metrics` endpoint | Optional dependency |

Use this table when reviewing PRs, running `GRILLME.md` sessions, or planning the next delivery slice.

---

## Testing strategy

| Layer | What | Where |
|-------|------|-------|
| Shape tests | Every enricher returns valid dossier fragments | `tests/test_pipeline_shape.py` |
| Integration | Fake sidecars in CI via compose override | Target |
| Manual QA | 20-profile canary set (technical + non-technical + private) | Target |

Run backend tests:

```bash
cd backend
pytest tests
```

### Local Redis E2E (Option A)

Requires Redis on `REDIS_URL` (see `.env`), plus API and worker in separate terminals:

```bash
# Terminal 1 — API
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 2 — RQ worker
cd backend
python -m app.workers.rq_worker
```

Automated check (API + worker must already be running):

```bash
cd backend
python scripts/e2e_redis_test.py
```

**Windows:** RQ's default `Worker` uses `os.fork` and `SIGALRM` (unavailable on Windows). `rq_worker.py` automatically uses `SimpleWorker` + a no-op death penalty locally; Linux/Docker production keeps the default fork-based worker.

### Rate limits to respect (production)

- **LinkedIn:** ~20–25 profile views/day per Multilogin profile
- **GitHub API:** 5,000 req/hour authenticated
- **SMTP verification:** throttle to ~10/min per Reacher instance

---

## Related documentation

- `backend/README.md` — run and test commands
- `README.md` — monorepo overview (frontend + backend split)
- `docs/architecture-plan-azi-10-hyre-enrichment.md` — full production plan
- `docs/IMPLEMENTATION_NOTES.md` — AZI-11 delivery handoff
- `GRILLME.md` — challenge-mode readiness checks
- `CHANGELOG.md` — ticket-level release notes

---

## Open questions and next slices

Track these as architecture decisions mature:

1. ~~Wire Redis/RQ so `/enrich` is truly async~~ (done) — remaining: make `/enrich/sync` exclude Tier 1 browser work, and promote to Postgres (#4) so API + worker share job state
2. Replace enricher mocks with subprocess/library integrations per upstream repo
3. Remove Bearer auth from `POST /api/opt-out` for compliance accessibility
4. Promote SQLite → PostgreSQL in default docker-compose wiring
5. Connect LiteLLM + Langfuse in `llm_router.py`
6. Swap nginx sidecar placeholders for real Reacher, social-analyzer, and GMaps images

For tier-specific issues, use `[Tier N]` in issue titles (e.g. `[Tier 3] Reacher fallback fails on catch-all`).
