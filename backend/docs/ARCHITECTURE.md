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
| `POST /enrich` runs inline | Enqueues to **Redis + RQ**; the worker process runs the orchestrator. `/enrich/sync` still runs inline. In Docker, API + worker share Postgres so polling works cross-process |
| Enrichers call real tools | They do (subprocess/library/sidecar) behind the `app/providers/` layer, but **degrade to empty fragments** when a tool/sidecar/key is missing. Defaults are fully free/self-hosted; free -> paid is an env flip |
| Database is Postgres everywhere | Local dev default is **SQLite** (`sqlite+aiosqlite:///./hyrepath.db`); **Docker compose uses Postgres** (`postgresql+asyncpg://...@postgres:5432/hyrepath`) shared by API + worker |
| R2 uploads go to Cloudflare | **R2 when `R2_*` creds set** (`aioboto3` PutObject + HeadObject); else local `backend/.asset-cache/` |
| LiteLLM disambiguation is live | Config-selected via `LLM_MODE`; **default is the heuristic stub** (no keys). `ollama`/`litellm` opt-in |
| Opt-out is unauthenticated | **Bearer token required** (intentional v1; see `docs/LEGAL.md`) |
| Suppression lives in Redis only | **SQL table** `suppression_list` is the durable record; Redis set `suppression:hashes` is a fast-path cache (dual-write, SQL fallback) |
| Audit logs | **SQL `audit_logs`** — 5-year retention via `purge_audit_logs.py` |
| DSAR flow | **`POST/GET /api/dsar`** — automated access/deletion in v1 |
| Data erasure on opt-out | **`register_opt_out()`** purges jobs, photo cache, R2/local assets |
| Sidecars are real services | Compose uses **real images**; free-mode ones default-on, paid/heavy ones behind `profiles:` |

### Task routing — where to start

| Task | Read first | Edit |
|------|------------|------|
| New enricher | Enricher protocol + tier table | `enrichers/base.py` → new module → `workers/runner.py` tier list |
| Change merge/dossier shape | `models.py` `Dossier` + frontend types | `workers/runner.py` `_merge()`, `models.py`, `frontend/src/lib/types.ts` |
| API route / auth | API endpoints section | `routes/enrich.py`, `routes/opt_out.py`, `main.py` |
| Async job queue | Implementation status | `routes/enrich.py`, `workers/runner.py`, `docker/docker-compose.yml` |
| Opt-out / suppression | Legal section + `_is_suppressed()` | `workers/runner.py`, `routes/opt_out.py`, `models.py` `SuppressionRecord` |
| Photo / Tier 1 | Tier 1 section | `enrichers/linkedin_photo.py`, `providers/multilogin.py`, `providers/profile_pool.py`, `providers/linkedin_browser.py`, `storage/photo_cache.py`, `storage/r2.py` |
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

**Cross-process caveat:** the async path is only end-to-end when the API and worker share a database. Docker compose wires both containers to the same Postgres (`postgres` service); local dev with SQLite works because API and worker run in the same working directory and share one DB file. The worker runs `init_db()` at startup so tables exist regardless of which process boots first.

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

**Current:** backend is config-selected via `LLM_MODE` (`app/providers/llm.py`): `stub` (default, heuristic string match, no network), `ollama` (local model), or `litellm` (proxy + fallback chain). `LiteLLMDisambiguator.compare()` signature is unchanged so the orchestrator and confidence scoring are untouched. Langfuse tracing runs via `providers.llm.trace()` and is a no-op until `LANGFUSE_*` is set.

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

**Docker / production:** PostgreSQL via `DATABASE_URL` (`postgresql+asyncpg://hyrepath:hyrepath@postgres:5432/hyrepath` in compose; API and worker share it).  
**Local dev default:** SQLite (`sqlite+aiosqlite:///./hyrepath.db`).  
Schema is created by `init_db()` (`create_all`) at API lifespan and worker startup — no Alembic migrations yet. Dossier JSON uses the portable `JSON` type (not `JSONB`) for now.

### Object storage (R2)

`app/storage/r2.py` — Cloudflare R2 via S3-compatible API (`aioboto3` in production).

**Current:** when `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, and `R2_SECRET_ACCESS_KEY` are set, uploads go to Cloudflare R2 via `aioboto3` (PutObject + HeadObject verify). Otherwise writes to `backend/.asset-cache/` using a path resolved from the package location (CWD-safe). Returns a CDN URL from `R2_PUBLIC_BASE_URL`.

### Redis (target)

- Job queue (RQ)
- Opt-out suppression set (fast lookup)
- Rate limiting
- Audit log hashes (5-year retention per request)

Configured via `REDIS_URL`. Present in docker-compose. A shared async client exists in `app/storage/redis_client.py` (`get_redis` FastAPI dependency, opened/closed in the app lifespan, lazy connection).

**Wired today:**

- *Suppression fast path.* `add_suppression()` writes SQL first (durable record), then `SADD suppression:hashes`. `check_suppression()` tries `SISMEMBER` first; on a miss or Redis error it falls back to the authoritative SQL table and backfills Redis on a hit. Opt-out is never weakened by a Redis outage — no TTL on suppression hashes.
- *Rate limiting.* Fixed-window counters (`ratelimit:{sync|async}:{token-hash}`) via `check_rate_limit()`. `POST /enrich` enforces `MAX_ASYNC_REQUESTS_PER_MINUTE`; `POST /enrich/sync` enforces `MAX_SYNC_REQUESTS_PER_MINUTE`. Dependencies live in `app/routes/rate_limit.py`. Over-limit returns `429`. **Fails open** on Redis error — protection, not correctness. Scope is per API token (SHA-256, first 16 hex chars); raw tokens are never logged.
- *Job queue (RQ).* `POST /enrich` enqueues to the `enrichment` queue via `app/workers/queue.py` (synchronous `redis-py` connection — RQ is not async-compatible). The worker (`app/workers/rq_worker.py`) runs `init_db()` at startup (so tables exist even if the API hasn't booted), then dequeues and calls `run_enrichment_job` (`app/workers/jobs.py`), which bridges to the async orchestrator with `asyncio.run` and a fresh DB session. Because each job gets its own event loop, the job disposes the shared async Redis client and DB engine pool in a `finally` — loop-bound connections leaking into the next job cause "Event loop is closed" failures. Enqueue failure marks the job `failed` and returns `503`.

**Redis roles now wired:** suppression fast path, rate limiting, job queue. Compliance audit trail is in SQL (`audit_logs`).

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
    │   ├── providers/
    │   │   ├── multilogin.py     # Multilogin API client (Tier 1)
    │   │   ├── profile_pool.py   # Profile rotation + daily limits
    │   │   ├── browser.py        # Playwright browser (local dev)
    │   │   └── ...
    │   ├── multilogin.py         # Re-exports providers.multilogin (compat)
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
| `DATABASE_URL` | Async DB URL (SQLite local default; Postgres in Docker/production) |
| `REDIS_URL` | Redis connection (queue + suppression target) |
| `R2_BUCKET` | R2 bucket name |
| `R2_PUBLIC_BASE_URL` | CDN base for cached photos |

### Tier 1 (LinkedIn photo) — target

| Variable | Purpose |
|----------|---------|
| `MULTILOGIN_EMAIL` | Multilogin account |
| `MULTILOGIN_PASSWORD` | Multilogin password (MD5-hashed in code at sign-in) |
| `MULTILOGIN_FOLDER_ID` | Profile pool folder |
| `MULTILOGIN_LAUNCHER_URL` | MLX launcher base (`/api/v2` for start, `/api/v1` derived for stop) |
| `MULTILOGIN_SELENIUM_HOST` | Selenium Remote host (Docker: `http://host.docker.internal`) |
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
| `changedetection` | Company change signals via `POST /api/signals/changedetection` |

**Current:** compose uses real images. Free-mode sidecars (`social-analyzer`, `google-maps-scraper`) start by default; paid/heavy services (`reacher`, `litellm`, `ollama`, `scrapoxy`, `langfuse`, `changedetection`) sit behind compose `profiles:` so a plain `docker compose up` stays free. Enrichers call real tools (subprocess/library/sidecar) selected by the Phase 0 provider layer (`app/providers/`), and **degrade to a valid empty fragment** when a tool, sidecar, or key is missing — never a crash. Free -> paid is an env flip via the mode flags in `config.py` (`PROXY_MODE`, `BROWSER_MODE`, `LLM_MODE`, `EMAIL_VERIFY_LEVEL`, `ENABLE_TIER1`).

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
| Enricher modules (11) | Real tool integrations | Real subprocess/library/sidecar calls behind `app/providers/`; degrade to empty fragments when a backend is absent |
| Provider layer (Phase 0) | Config-selected free/paid backends | `app/providers/` (proxy, browser, llm, email_verify, sidecar, process); 5 mode flags in `config.py` |
| Redis client | Queue + suppression + rate limits | Shared async client wired in lifespan; suppression, rate limiting, and queue all use it |
| Async job queue | Redis + RQ, worker process | Implemented — `/enrich` enqueues, `rq_worker` executes; Docker compose shares Postgres for cross-process polling |
| Database | PostgreSQL + JSONB | Postgres in Docker compose (asyncpg, `JSON` type); SQLite default for local dev; `create_all`, no Alembic |
| R2 photo cache | `aioboto3` → Cloudflare R2 | `storage/r2.py` — R2 PutObject + HeadObject when `R2_*` creds set; local `backend/.asset-cache/` fallback (CWD-safe path) |
| LinkedIn photo cache | Redis + Postgres by slug hash | `storage/photo_cache.py` + `PhotoCacheRecord`; slug-keyed TTL; cache-before-browser in `linkedin_photo.py` |
| Multilogin + Selenium | MLX launcher + Selenium Remote | `providers/multilogin.py`, `profile_pool.py`, `linkedin_browser.py`; worker-only `ENABLE_TIER1`; `/enrich/sync` skips tier1 |
| Tier 1 pipeline dispatch | Tier 1 serial, tiers 2–4 parallel | `runner.py` `_dispatch(sync_mode=...)`; see `docs/TESTING_TIER1.md` |
| Tier 1 Docker ops | Worker image + compose override | `Dockerfile.worker` (Chromium + `.[enrichers]`); `docker-compose.tier1.yml`; `tier1_*` Prometheus counters |
| Tier 1 hardening (3.7) | Session reuse, denylist, rate limits | `TIER1_SKIP_LOGIN_IF_SESSION_VALID`; `profile_pool.refund_view()`; `probe_tier1_canary.py`; configurable cooldowns |
| LiteLLM disambiguation | Routed LLM calls | `LLM_MODE=stub|ollama|litellm` (default stub) via `providers/llm.py` |
| Langfuse tracing | Per disambiguation call | `providers.llm.trace()`; no-op until `LANGFUSE_*` set |
| Sidecars | 5+ isolated services | Real images; free-mode default-on, paid behind compose `profiles:` |
| Opt-out auth | Authenticated (intentional v1) | Implemented — see `docs/LEGAL.md` |
| Audit logs | SQL + 5-year retention script | Implemented |
| DSAR flow | `POST/GET /api/dsar` | Implemented |
| Data erasure | Purge on opt-out/DSAR deletion | Implemented |
| Scrapoxy proxy pool | Rate-limit hardening | `ProxyProvider` (`PROXY_MODE=none|scrapoxy|paid`, default none = direct) |
| Change signals | changedetection.io webhook | `POST /api/signals/changedetection` consumer (optional shared-secret header) |
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

### Docker Compose E2E (shared Postgres)

Proves the async path end-to-end when API + worker share one Postgres. Requires a Docker daemon (on Windows, Docker Engine inside WSL2 works headlessly).

```bash
bash backend/scripts/e2e_compose_test.sh
```

The script brings up `api`, `worker`, `redis`, `postgres`, then asserts: `/health` 200 → `POST /enrich` 202 `queued` → poll `completed` → opt-out blocks enrichment (suppression row in Postgres) → **worker restart** leaves the old job `completed` (data survives in the `postgres_data` volume). Verified 2026-07-08: all checks pass; `jobs` ends with one `completed` + one `suppressed` row, `suppression_list` with one row.

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

1. ~~Wire Redis/RQ so `/enrich` is truly async~~ (done) — ~~make `/enrich/sync` exclude Tier 1 browser work~~ (done: `runner.py` sync_mode skips tier1)
2. ~~Replace enricher mocks with subprocess/library integrations per upstream repo~~ (done) — remaining: tune upstream CLI/API contracts (gitrecon JSON schema, social-analyzer/GMaps sidecar endpoints) against live deployments
3. Remove Bearer auth from `POST /api/opt-out` for compliance accessibility
4. ~~Promote SQLite → PostgreSQL in default docker-compose wiring~~ (done) — remaining: Alembic migrations and `JSONB` columns when the schema stabilizes
5. ~~Connect LiteLLM + Langfuse in `llm_router.py`~~ (done, opt-in) — remaining: real prompt tuning + cost dashboards once `LLM_MODE=litellm` is exercised
6. ~~Swap nginx sidecar placeholders for real Reacher, social-analyzer, and GMaps images~~ (done) — remaining: verify each real image's health/endpoints in a staging compose run

For tier-specific issues, use `[Tier N]` in issue titles (e.g. `[Tier 3] Reacher fallback fails on catch-all`).
