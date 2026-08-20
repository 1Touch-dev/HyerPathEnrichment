# Backend Architecture

Hyrepath Enrichment backend — architecture reference for the FastAPI service under `backend/`.

**Version:** 0.4 (August 2026)
**Last verified against code:** 2026-08-13
**Repo layout:** `HyerEnrichment/backend/` (split from the Next.js frontend in `frontend/`)

---

## Agent quick reference

**Read this file when:** backend API, pipeline, enricher, opt-out, tier, storage, or Docker work.

**Trust order (highest wins):**

1. Code in `backend/app/`
2. **Implementation status** section below (scaffold vs target)
3. This doc (architecture + routing)
4. `RULE.md` (ownership + import rules)
5. `docs/architecture-plan-azi-10-hyre-enrichment.md` (original plan — may be ahead of code)

### Modular ownership (locked)

| Layer | Path | Role |
|-------|------|------|
| Domain | `app/domain/` | Shared contracts (`Dossier`, `EnrichmentRequest`, enums) |
| Modules | `app/modules/` | HTTP use cases (enrichment, opt_out, dsar, health, signals) |
| Pipeline | `app/enrichers/pipeline.py` | **Only** enrichment execution owner |
| Merge | `app/enrichers/merge.py` | Deterministic dossier assembly |
| Workers | `app/workers/` | RQ adapter; calls Pipeline + JobRepository |
| Compliance | `app/compliance/` | Hashing, suppression impl, purge, audit, DSAR + compliance ORM |
| Clients / integrations | `app/clients/`, `app/integrations/` | External systems |
| Infrastructure | `app/infrastructure/redis.py` | Redis connection factory only |
| Database | `app/database/` | `Base`, session; Alembic stays at `backend/alembic/` |
| HTTP envelopes | `app/core/responses.py`, `errors.py`, `exception_handlers.py`, `api_route.py` | All JSON success/error bodies use shared envelopes (`success`/`data` or `success`/`error` + `meta`) |

**Execution split:** `EnrichmentService` starts/polls jobs; `Pipeline` runs enrichment; workers only provide the async environment. Sync and async both end at `Pipeline.run()`.

### Do not assume (common agent mistakes)

| Assumption | Reality today |
|------------|---------------|
| `POST /enrich` runs inline | Enqueues to **Redis + RQ**; the worker process runs the pipeline. `/enrich/sync` still runs inline. In Docker, API + worker share Postgres so polling works cross-process |
| Enrichers call real tools | They do (subprocess/library/sidecar) behind `app/clients/` and `app/integrations/`, but **degrade to empty fragments** when a tool/sidecar/key is missing. Defaults are fully free/self-hosted; free -> paid is an env flip |
| Database is Postgres everywhere | Local dev default is **SQLite** (`sqlite+aiosqlite:///./hyrepath.db`); **Docker compose uses Postgres** (`postgresql+asyncpg://...@postgres:5432/hyrepath`) shared by API + worker. Schema via **Alembic** (`init_db` → upgrade head); document columns are **JSONB** on Postgres |
| R2 uploads go to Cloudflare | **R2 when `R2_*` creds set** (`aioboto3` PutObject + HeadObject); else local `backend/.asset-cache/` |
| LiteLLM disambiguation is live | Config-selected via `LLM_MODE`; **default is the heuristic stub** (no keys). `ollama`/`litellm` opt-in. Pipeline walks handles below `DISAMBIGUATION_THRESHOLD` via `enrichers/disambiguate.py` → LLM client |
| Authentication is API token only | **Cookie-based auth** with FastAPI-Users (ADR 0009); enrichment and DSAR require **authenticated + verified users**; opt-out remains public |
| Opt-out / DSAR are unauthenticated | **Opt-out is public** (IP rate-limited); **DSAR requires authenticated verified user**; enrich routes require authenticated verified user |
| Email verification is optional | **Required** — unverified users blocked from enrichment and DSAR; only opt-out accessible without verification |
| Logout is stateless | **Token blacklist** (Redis + PostgreSQL dual-write); logged-out tokens trigger security alerts if reused |
| Suppression lives in Redis only | **SQL table** `suppression_list` is the durable record; Redis set `suppression:hashes` is a fast-path cache (dual-write, SQL fallback) in `compliance/suppression.py` |
| Audit logs | **SQL `audit_logs`** for compliance + **SQL `auth_audit_logs`** for auth events — 5-year retention via `purge_audit_logs.py` |
| DSAR flow | **`POST/GET /api/dsar`** — requires authenticated verified user in v1 (per ADR 0009) |
| Data erasure on opt-out | Opt-out service → compliance suppress + purge jobs, photo cache, R2/local assets |
| Sidecars are real services | Compose uses **real images**; free-mode ones default-on, paid/heavy ones behind `profiles:` |
| SMS notification channel | Job-matching preferences accept `"sms"` but no Twilio client exists; selecting it is a UI-disabled no-op. |
| CV chat runs on a worker queue | It does not — synchronous on the `api` container per Decision 2 (`phase2_module2.md` §3). There is no `cv_chat` RQ queue; `documents/cv_chat_service.py` calls OpenAI inline within the request. |
| Outreach has its own dedicated worker container | It does not — shares the generic `worker` container's `QUEUE_OUTREACH` (`outreach_generation`, added to the existing fixed-priority list in `rq_worker.py` right after `QUEUE_FEEDBACK`), unlike Module 1's `job_matching`, which does have a dedicated container. See `phase2_module2.md` §10 and ADR 0014 for why these two decisions differ. |
| Portfolio pages are all behind auth | `GET /api/portfolio/public/{slug}` (and its frontend counterpart `/p/[slug]`) are deliberately public — see ADR 0014. Every other portfolio/outreach/CV-chat/swipe route requires an authenticated, verified user (`Depends(current_verified_user)` at the `app.include_router` call in `main.py`). |
| "Send" on an outreach message actually emails the recipient | It does not, in v1 — `send_message()` in `app/modules/outreach/service.py` appends the mandatory CAN-SPAM disclosure footer and marks the message `sent`, but never transmits over SMTP; the candidate copies/sends the drafted text themselves. Real outbound send-as-the-candidate infrastructure (deliverability, SPF/DKIM) is explicitly out of scope for v1. |
| Module 2 shipped a CV upload widget | It did not — `frontend/app/app/documents/DocumentsView.tsx` only lists and links into existing documents; it explicitly assumes a generic upload widget that, as of this writing, still does not exist anywhere in `frontend/` (same gap `phase2_module1.md` §11.10 already flagged, still open after Module 2). |

### Task routing — where to start

| Task | Read first | Edit |
|------|------------|------|
| New enricher | Enricher protocol + tier table | `enrichers/base.py` → new module → `enrichers/registry.py` |
| Change merge/dossier shape | `domain/dossier.py` + frontend types | `enrichers/merge.py`, `domain/dossier.py`, `frontend/src/lib/types.ts` |
| API route / auth | API endpoints section | `modules/*/router.py`, `main.py` |
| Async job queue | Implementation status | `modules/enrichment/`, `workers/`, `docker/docker-compose.yml` |
| Opt-out / suppression | Legal section | `compliance/suppression.py`, `modules/opt_out/`, `compliance/models.py` |
| Photo / Tier 1 | Tier 1 section | `enrichers/linkedin_photo.py`, integrations/clients Multilogin + LinkedIn, `storage/photo_cache.py`, `storage/r2.py` |
| Env / config | Environment variables section | `core/config.py` (shim `config.py`), `.env.example` |
| Tests | Testing strategy | `tests/test_pipeline_shape.py` |
| Frontend integration | Frontend contract below | `frontend/src/lib/api-adapter.ts`, `frontend/src/lib/types.ts`, `frontend/src/lib/generated/` |

### Frontend contract (keep in sync)

Backend wire contract source: FastAPI `/openapi.json` (from Pydantic models in `backend/app/domain/` and module routers). Committed snapshot: `frontend/openapi/openapi.json`. Generated TypeScript: `frontend/src/lib/generated/openapi.ts` via `npm run openapi:gen` (CI enforces drift with `npm run openapi:check`).

UI camelCase mirror: `frontend/src/lib/types.ts`. API adapter: `frontend/src/lib/api-adapter.ts` (imports wire types from `frontend/src/lib/generated/api-schemas.ts`). Field naming differs (`linkedin_url` backend vs `linkedinUrl` frontend) — mapping stays in the adapter, not components.

After changing backend response/request models: `cd frontend && npm run openapi:export && npm run openapi:gen`, then update `types.ts` / adapter if UI shapes change.

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

1. **Modules** (`app/modules/`) — HTTP use cases (routers + services)
2. **Domain** (`app/domain/`) — shared contracts (`Dossier`, `EnrichmentRequest`, enums)
3. **Pipeline** (`app/enrichers/pipeline.py`) — suppression decision, tier dispatch, merge, disambiguation
4. **Enrichers** (`app/enrichers/`) — one module per upstream tool, shared `Enricher` protocol + registry
5. **Workers** (`app/workers/`) — RQ adapter calling Pipeline + JobRepository
6. **Compliance** (`app/compliance/`) — hashing, suppression impl, purge, audit, DSAR
7. **Storage / clients / integrations / infrastructure** — persistence and external systems
8. **Database** (`app/database/`) — SQLAlchemy base + session (Alembic at `backend/alembic/`)

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

**Cross-process caveat:** the async path is only end-to-end when the API and worker share a database. Docker compose wires both containers to the same Postgres (`postgres` service); local dev with SQLite works because API and worker run in the same working directory and share one DB file. Compose runs a one-shot `migrate` service before API/worker start; `/ready` fails until `alembic_version` is at head.

---

## Four enrichment tiers

Each tier maps to enricher modules in `app/enrichers/`. The orchestrator registers them in `PipelineOrchestrator.__init__`.

### Tier 1 — LinkedIn photo (browser-based)

| Module | Upstream | Integration |
|--------|----------|-------------|
| `linkedin_photo.py` | `joeyism/linkedin_scraper` + Playwright | Multilogin X stealth browser over CDP; photo uploaded to R2 |

- One browser session per profile lookup — no bulk scraping
- Multilogin runs on the host; launcher API is hostname-locked to `launcher.mlx.yt:45001` (Docker maps that name via `extra_hosts`). Host-native Windows Tier 1 uses Selenium at `127.0.0.1`; Docker Tier 1 uses `MULTILOGIN_SELENIUM_HOST=http://launcher.mlx.yt`
- **Linux production** (`--with-linux-mlx`): Multilogin runs in a container with `network_mode: host`; the worker container also uses `network_mode: host`. Both share the Linux loopback, so the per-profile Selenium debug port (`127.0.0.1:PORT`) is reachable directly. `MULTILOGIN_SELENIUM_HOST=http://127.0.0.1` (the `config.py` default). See [ADR 0008](../docs/adr/0008-tier1-linux-host-network.md).
- **WSL2 / Windows**: Multilogin's per-profile Selenium debug port is bound to Windows `127.0.0.1`, which is unreachable from any WSL2 container namespace regardless of host-IP routing. Use the Linux production path for real Tier 1 scraping.
- Launcher HTTPS skips TLS verify (self-signed local cert); cloud API (`api.multilogin.com`) does not
- Only the profile picture is captured, not full profile export

### Tier 2 — Cross-site username hunt (no browser)

Runs in parallel when `tier2` is requested:

| Module | Upstream | Confidence base |
|--------|----------|-----------------|
| `sherlock.py` | `sherlock-project/sherlock` (MIT) | `0.75` (`SHERLOCK_HANDLE_CONFIDENCE`) |
| `maigret.py` | `soxoj/maigret` (MIT) | `0.85` (`MAIGRET_HANDLE_CONFIDENCE`) |
| `social_analyzer.py` | `qeeqbox/social-analyzer` (AGPL) | NLP `rate` via HTTP sidecar |

**Current:** `sherlock-project` + `maigret` ship in `.[enrichers]` and are on PATH in `Dockerfile.worker` / `Dockerfile.api`. Merge dedupes on `(platform, username)` and **keeps the higher confidence**. Handles below **0.7** go to the LLM disambiguator. Full E2E: `bash backend/scripts/e2e_tier2.sh` (free path + litellm Stage B). Free-stack Compose healthchecks include social-analyzer (`GET /get_settings`), email-verifier, and google-maps-scraper (`GET /api/docs`).

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

**Concurrency:** Fully async, no enrichment worker delay.

**Purpose:** Discover job openings matching criteria (JobSpy) and local business information (Google Maps Scraper).

**Input:** `job_search` (or `job_title`/`job_location`/`job_country`) and/or `business`

**LLM Job Query Optimization:**

When `LLM_MODE=litellm`, the system uses an LLM (Gemini 2.5 Flash via LiteLLM proxy) to generate board-specific optimized queries for each job board:

- **LinkedIn**: Contextual location format
- **Indeed**: Correct `country_indeed` parameter + formatted location
- **Glassdoor**: "City, State" or "City, Country" format (strict requirement)
- **Google Jobs**: Natural language query ("Software Engineer jobs in Mumbai, India")
- **ZipRecruiter**: Board-specific keywords

The LLM optimization normalizes locations (e.g., "Bengaluru" → "Bengaluru, Karnataka"), handles ambiguous cities (adds state/country context), and generates board-specific parameters from few-shot examples. Falls back gracefully to manual logic if LLM unavailable.

**Key Implementation:** `backend/app/enrichers/jobspy.py` → `backend/app/clients/llm.py::litellm_optimize_job_query()`

**Cost:** ~$0.001-0.01 per job search (Gemini 2.5 Flash). See [LLM_JOB_OPTIMIZATION.md](../../docs/LLM_JOB_OPTIMIZATION.md) for details.

**JobSpy** scrapes 5 boards concurrently (LinkedIn, Indeed, Glassdoor, Google, ZipRecruiter) via `python-jobspy`. ZipRecruiter often returns 403 (bot detection). Paid proxy (`PROXY_MODE=paid`) helps but doesn't guarantee success. Google Maps Scraper is a containerized sidecar (`docker/Dockerfile.google-maps-scraper`) built from `gosom/google-maps-scraper`.

### LLM post-pass — disambiguation

`app/clients/llm.py` (`LiteLLMDisambiguator`) resolves ambiguous handles:

- Trigger: confidence **&lt; 0.7** (configurable via `DISAMBIGUATION_THRESHOLD`)
- Routed through **LiteLLM** to the cheapest capable model with fallback chain
- Traced in **Langfuse** for cost and quality review
- Only kept if LLM confidence **≥ 0.7**

**Current:** after merge, `Pipeline._disambiguate_handles()` walks each handle below `DISAMBIGUATION_THRESHOLD`, calls `llm.compare(target_identity, handle_evidence)`, boosts and keeps matches (`confidence = max(original, llm)`), and drops the rest. Backend is config-selected via `LLM_MODE` (`app/clients/llm.py`): `stub` (default, heuristic string match, no network), `ollama` (local model), or `litellm` (proxy + `LITELLM_FALLBACKS` chain). Start the proxy with `docker compose --env-file ../.env --profile llm up -d litellm`. The litellm service must **not** inherit Hyrepath’s `DATABASE_URL` (sqlite crash-loops the proxy); vendor keys are passed via compose interpolation and models via `docker/litellm_config.yaml`. api/worker only need `LITELLM_API_BASE` / model list. Langfuse tracing runs via `clients.llm.trace()` and is a no-op until `LANGFUSE_*` is set.

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
| `jobs` | Job id, status, request/dossier JSONB (JSON on SQLite), timestamps |
| `suppression_list` | SHA-256 hashed identifiers + opt-out reason |

**Docker / production:** PostgreSQL via `DATABASE_URL` (`postgresql+asyncpg://hyrepath:hyrepath@postgres:5432/hyrepath` in compose; API and worker share it).
**Local dev default:** SQLite (`sqlite+aiosqlite:///./hyrepath.db`).
Schema is owned by **Alembic** (`backend/alembic/`). Docker Compose applies migrations via the one-shot `migrate` service (`alembic upgrade head`); API and worker do not run DDL on boot. Local dev: `make migrate` before `uvicorn`, or rely on pytest `conftest` / `init_db()` in scripts. `init_db()` still stamps pre-Alembic `create_all` databases at baseline when `jobs` exists and `alembic_version` is missing, then runs `upgrade head`. Document columns use `JsonDoc` (`JSONB` on Postgres, `JSON` on SQLite). Do not use `create_all` for durable schema.

**Ops notes:** Boot applies migrations automatically — no manual `alembic upgrade` required for Compose. Legacy volumes are auto-stamped (do not delete `postgres_data` unless wiping data is intentional). Local SQLite: delete `hyrepath.db` or let auto-stamp run. Postgres migration edge tests: `TEST_DATABASE_URL=postgresql+asyncpg://… pytest -m postgres` (needs `pip install -e ".[dev]"` for psycopg).

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
- *Rate limiting.* Weighted sliding-window counters via `check_rate_limit()` (`app/infrastructure/redis.py`) — an atomic Lua script blends a decaying-weighted estimate of the previous window's count into the current window's check-then-increment, closing the boundary-burst gap a plain fixed-window counter has (full `limit` at the tail of one window + full `limit` at the head of the next). `POST /enrich` enforces `MAX_ASYNC_REQUESTS_PER_MINUTE` and `POST /enrich/sync` enforces `MAX_SYNC_REQUESTS_PER_MINUTE` scoped per API token (`ratelimit:{sync|async}:{token-hash}`). Opt-out and DSAR enforce `MAX_COMPLIANCE_REQUESTS_PER_MINUTE` scoped per client IP (`ratelimit:compliance:{host-hash}`). `POST /auth/register|login|verify-email|resend-verification` share one `MAX_AUTH_REQUESTS_PER_MINUTE` bucket scoped per client IP (`ratelimit:auth:{host-hash}`). `POST /api/documents/upload` (`MAX_DOCUMENTS_UPLOAD_REQUESTS_PER_MINUTE`) and `POST /api/job-matching/scan` (`MAX_JOB_MATCHING_SCAN_REQUESTS_PER_MINUTE`) are scoped per API token; `POST /api/signals/changedetection` (`MAX_SIGNALS_WEBHOOK_REQUESTS_PER_MINUTE`) is scoped per client IP. Dependencies live in `app/dependencies/rate_limit.py`. Over-limit returns `429`. **Fails open** on Redis error — protection, not correctness. Raw tokens and IPs are never logged (hashed to 16 hex chars).
- *Job queue (RQ).* `POST /enrich` enqueues to the `enrichment` queue via `app/workers/queue.py` (synchronous `redis-py` connection — RQ is not async-compatible). The worker (`app/workers/rq_worker.py`) dequeues and calls `run_enrichment_job` (`app/workers/jobs.py`), which bridges to the async orchestrator with `asyncio.run` and a fresh DB session. Because each job gets its own event loop, the job disposes the shared async Redis client and DB engine pool in a `finally` — loop-bound connections leaking into the next job cause "Event loop is closed" failures. Enqueue failure marks the job `failed` and returns `503`.

**Redis roles now wired:** suppression fast path, rate limiting, job queue. Compliance audit trail is in SQL (`audit_logs`).

---

## API endpoints

Enrichment routes require `Authorization: Bearer <API_TOKEN>`. Opt-out and DSAR routes are **unauthenticated** (IP rate-limited) so data subjects can exercise rights without an API key. See `docs/LEGAL.md`.

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/enrich` | Bearer | Create enrichment job (202 Accepted) |
| `GET` | `/enrich` | Bearer | Paginated job list |
| `GET` | `/enrich/{job_id}` | Bearer | Poll job status + dossier |
| `POST` | `/enrich/sync` | Bearer | Synchronous enrichment path |
| `POST` | `/api/opt-out` | Public | Register identifier suppression (LGPD/GDPR/CCPA) |
| `GET` | `/api/opt-out/check?identifier=` | Public | Check if identifier is suppressed |
| `POST` | `/api/dsar` | Public | Create access or deletion request |
| `GET` | `/api/dsar/{id}` | Public | Poll DSAR status and summary |
| `GET` | `/health` | Public | Liveness |
| `GET` | `/ready` | Public | Readiness |
| `GET` | `/metrics` | Public | Prometheus metrics (when `prometheus_client` installed) |

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

**Auth policy:** Enrichment requires Bearer. `POST /api/opt-out`, `GET /api/opt-out/check`, and DSAR routes are unauthenticated with IP-scoped rate limiting (`MAX_COMPLIANCE_REQUESTS_PER_MINUTE`).

---

## Folder structure

```text
HyerEnrichment/
├── frontend/
└── backend/
    ├── app/
    │   ├── main.py
    │   ├── core/                 # config, lifespan
    │   ├── domain/               # Dossier, EnrichmentRequest, enums
    │   ├── modules/              # enrichment, opt_out, dsar, health, signals
    │   ├── enrichers/            # pipeline, merge, disambiguate, registry, tiers
    │   ├── compliance/           # identifiers, suppression, purge, audit, dsar, models
    │   ├── workers/              # queue, tasks, RQ shims
    │   ├── clients/              # thin external clients
    │   ├── integrations/         # linkedin, browser, multilogin
    │   ├── infrastructure/       # redis connection factory
    │   ├── database/             # Base, session
    │   ├── storage/              # r2, photo_cache
    │   └── observability/
    ├── alembic/                  # migrations (repo-level; do not move under app/)
    ├── docker/
    ├── docs/
    ├── scripts/
    ├── tests/
    ├── pyproject.toml
    └── README.md
```

Compatibility shims may temporarily remain at `app.workers.jobs` (stable RQ import path). Real logic lives in `modules/`, `domain/`, `clients/`, `integrations/`, `enrichers/`, and `database/`.
---

## Environment variables

Copy `backend/.env.example` → `backend/.env`.

### Required today

| Variable | Purpose |
|----------|---------|
| `API_TOKEN` | Bearer token for enrichment (and other protected) routes |
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
| `MULTILOGIN_WORKSPACE_ID` | Workspace for `/user/refresh_token` after sign-in (needed for multi-workspace accounts) |
| `MULTILOGIN_PROFILE_ID` | Fixed profile id; when set, skips `/profile/search` (local probe / single-profile) |
| `MULTILOGIN_LAUNCHER_URL` | MLX launcher base (`/api/v2` for start, `/api/v1` derived for stop); start/stop skip TLS verify |
| `MULTILOGIN_SELENIUM_HOST` | Selenium Remote host (host-native: `http://127.0.0.1`; Docker Tier 1: `http://launcher.mlx.yt`) |
| `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | R2 credentials |
| `LINKEDIN_BOT_EMAIL`, `LINKEDIN_BOT_PASSWORD` | Dummy LinkedIn account for Selenium login |

**Docker Tier 1:** use `-f docker-compose.tier1.yml`. That override loads secrets from `env_file` (`../.env` or `WORKER_ENV_FILE`) into the **worker only**, forces `MULTILOGIN_SELENIUM_HOST=http://launcher.mlx.yt`, maps `launcher.mlx.yt` and `host.docker.internal` → `host-gateway` (or `MULTILOGIN_HOST_IP` on WSL2 + Docker Engine so traffic reaches Windows), and the worker exits on boot if Multilogin/bot (and staging/production R2) settings are missing (`validate_tier1_settings`). On Windows, prefer a host-native RQ worker with `MULTILOGIN_SELENIUM_HOST=http://127.0.0.1` when ChromeDriver rejects non-localhost Host headers.

### Tier 3 (email) — target

| Variable | Purpose |
|----------|---------|
| `REACHER_URL` | Reacher sidecar endpoint |
| `REACHER_FROM_EMAIL` | SMTP HELO sender mailbox |

### LLM disambiguation — target

| Variable | Purpose |
|----------|---------|
| `LLM_MODE` | `stub` / `ollama` / `litellm` |
| `LITELLM_MODEL` | Primary model |
| `LITELLM_FALLBACKS` | Comma-separated fallback model ids |
| `LITELLM_API_KEY`, `LITELLM_API_BASE` | App → LiteLLM proxy |
| `LITELLM_MASTER_KEY` | Optional proxy auth (match `LITELLM_API_KEY` on app) |
| `OPENAI_API_KEY`, `GEMINI_API_KEY` | Vendor keys on **litellm container only** (`env_file`) |
| `DISAMBIGUATION_THRESHOLD` | Default `0.7` |

### Rate limits (Redis weighted sliding-window counters, atomic Lua script — see `app/infrastructure/redis.py`)

| Variable | Default | Scope |
|----------|---------|-------|
| `MAX_SYNC_REQUESTS_PER_MINUTE` | 10 | Per API token (`/enrich/sync`) |
| `MAX_ASYNC_REQUESTS_PER_MINUTE` | 30 | Per API token (`/enrich`) |
| `MAX_COMPLIANCE_REQUESTS_PER_MINUTE` | 20 | Per client IP (opt-out + DSAR) |
| `MAX_AUTH_REQUESTS_PER_MINUTE` | 5 | Per client IP, one shared bucket across `/auth/register`, `/auth/login`, `/auth/verify-email`, `/auth/resend-verification` |
| `MAX_DOCUMENTS_UPLOAD_REQUESTS_PER_MINUTE` | 10 | Per API token (`POST /api/documents/upload`) |
| `MAX_SIGNALS_WEBHOOK_REQUESTS_PER_MINUTE` | 30 | Per client IP (`POST /api/signals/changedetection`) |
| `MAX_JOB_MATCHING_SCAN_REQUESTS_PER_MINUTE` | 5 | Per API token (`POST /api/job-matching/scan`) |
| `LINKEDIN_PHOTO_TTL_SECONDS` | 86400 | — |
| `USERNAME_LOOKUP_TTL_SECONDS` | 3600 | — |

### CORS

`CORS_ALLOWED_ORIGINS` — comma-separated origin allowlist for `CORSMiddleware` (`app/main.py`); falls back to `FRONTEND_URL`, then `http://localhost:3000`, when unset. `allow_methods` and `allow_headers` are an explicit tightened set (`GET, POST, PUT, PATCH, DELETE, OPTIONS`; `Authorization, Content-Type`), not wildcards, since `allow_credentials=True` forbids a wildcard origin/credentials combination anyway. Preflight responses are cached client-side for 600s (`max_age=600`).

---

## Docker services

`backend/docker/docker-compose.yml` defines the target topology:

| Service | Role |
|---------|------|
| `migrate` | One-shot Alembic `upgrade head` before API/worker |
| `api` | FastAPI on port 8000 |
| `worker` | RQ worker running the orchestrator |
| `postgres` | Job + suppression persistence |
| `redis` | Queue + suppression + rate limits |
| `social-analyzer` | AGPL sidecar (Tier 2) |
| `email-verifier` | AfterShip email verification sidecar (Tier 3 basic mode) |
| `reacher` | SMTP verification sidecar (Tier 3 smtp mode) |
| `google-maps-scraper` | Local business sidecar (Tier 4); built via `Dockerfile.google-maps-scraper` (Playwright driver from npm — not Hub CDN) |
| `litellm` | LLM proxy |
| `langfuse` | LLM observability |
| `glitchtip-web` | Central error tracking (Sentry-compatible UI) |
| `changedetection` | Company change signals via `POST /api/signals/changedetection` → `NOTIFY_WEBHOOK_URL` |

### Change signals (changedetection.io)

Start the observability profile and set shared secrets in `backend/.env`:

```bash
cd backend/docker
docker compose --env-file ../.env --profile observability up -d api changedetection
```

| Variable | Purpose |
|----------|---------|
| `CHANGEDETECTION_URL` | API base for watch management (`http://changedetection:5000` in compose) |
| `CHANGEDETECTION_API_KEY` | Shared secret for CD REST API and optional `X-Signal-Token` on the webhook |
| `NOTIFY_WEBHOOK_URL` | Outbound JSON webhook (Slack-compatible custom URL); no-op when unset |
| `CHANGEDETECTION_SIGNAL_URL` | Apprise `post://` URL used when creating watches (default `post://api:8000/api/signals/changedetection`) |

Create watches that POST non-PII metadata to the API:

```bash
cd backend
python scripts/setup_changedetection_watches.py create https://acme.example/careers --title "Acme careers"
python scripts/setup_changedetection_watches.py list
```

Flow: changedetection detects a page change → `POST /api/signals/changedetection` → API persists to `signals` table → forwards `{source, watch_id, title, url, timestamp}` to `NOTIFY_WEBHOOK_URL` when configured → frontend displays at `/signals` route.

**Frontend UI:** Authenticated route at `/app/signals` displays signals list with pagination, external links, and empty state. Uses `@tanstack/react-query` for data fetching and auto-refresh. Components: `features/signals/components/SignalsTable.tsx`, `features/signals/hooks/useSignalList.ts`.

### Structured logging

One setup for API + RQ workers (`app/core/logging.py`). Default format is **text** locally and **JSON** when `APP_ENV` is `staging`/`production`; override with `LOG_FORMAT=json|text`. Lines include `timestamp`, `level`, `logger`, `message`, `service`, and optional `request_id` / `job_id`. Configure before Sentry so `LoggingIntegration` stays compatible. See [ADR 0007](../../docs/adr/0007-stdlib-json-logging.md).

| Variable | Purpose |
|----------|---------|
| `LOG_FORMAT` | `json` \| `text` \| empty (auto from `APP_ENV`) |
| `LOG_LEVEL` | Root log level (default `INFO`) |
| `LOG_SERVICE` | Service name field (default `hyrepath-enrichment`) |

### Central error tracking (GlitchTip / Sentry-compatible)

Opt-in crash reporting for unhandled API 500s and RQ worker failures. The SDK is a **no-op** until `SENTRY_DSN` is set (same pattern as Langfuse).

Start GlitchTip under the observability profile:

```bash
cd backend/docker
docker compose --env-file ../.env --profile observability up -d glitchtip-web glitchtip-worker api worker
```

| Variable | Purpose |
|----------|---------|
| `SENTRY_DSN` | Project DSN from GlitchTip (or Sentry SaaS) — empty disables capture |
| `SENTRY_ENVIRONMENT` | Tag events (defaults to `APP_ENV`) |
| `SENTRY_RELEASE` | Optional release/build id (git SHA, image tag) |
| `SENTRY_TRACES_SAMPLE_RATE` | Performance tracing sample rate (default `0`) |
| `SENTRY_SEND_DEFAULT_PII` | Default `false` — do not attach raw identifiers |
| `GLITCHTIP_PUBLIC_URL` | GlitchTip UI URL (compose default `http://localhost:8001`) |
| `GLITCHTIP_SECRET_KEY` | Django secret for self-hosted GlitchTip |
| `ENABLE_ERROR_TRACKING_PROBE` | E2E only — enables `POST /internal/error-tracking-probe` |

**Reported:** unhandled FastAPI exceptions (500), unexpected RQ enrichment task failures (with `job_id` tag).

**Not reported:** expected `AppError` / 4xx, validation errors, enricher soft-fail → empty fragment.

UI: `http://localhost:8001` — create org/project, copy DSN into `SENTRY_DSN`. E2E proof: `bash backend/scripts/e2e_error_tracking.sh`.

**Current:** compose uses real images/builds. Free-mode sidecars (`social-analyzer`, `google-maps-scraper`, `email-verifier`) start by default; paid/heavy services (`reacher`, `litellm`, `ollama`, `scrapoxy`, `langfuse`, `changedetection`) sit behind compose `profiles:` so a plain `docker compose up` stays free. Default-stack services (`postgres`, `redis`, `api`, `worker`, free sidecars) declare Compose `healthcheck`s; `api`/`worker` wait for `migrate` (`service_completed_successfully`) and `redis` (`service_healthy`). `google-maps-scraper` is built locally (`Dockerfile.google-maps-scraper`) with a pre-assembled Playwright 1.57.0 driver — Hub `:latest` still hits the retired azureedge CDN. Do not volume-mount over `/opt`. Enrichers call real tools (subprocess/library/sidecar) via `app/clients/` and `app/integrations/`, and **degrade to a valid empty fragment** when a tool, sidecar, or key is missing — never a crash. Free -> paid is an env flip via the mode flags in `core/config.py` (`PROXY_MODE`, `BROWSER_MODE`, `LLM_MODE`, `EMAIL_VERIFY_LEVEL`, `ENABLE_TIER1`).

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
| API routes + auth | FastAPI + Bearer | Implemented — JSON responses use shared success/error envelopes (`app/core/`) |
| Cookie-based authentication | Google OAuth + email/password with verification | **Implemented (ADR 0009)** — `app/auth/` with FastAPI-Users, email verification (24h expiry), logged-out token detection (dual Redis+PostgreSQL), bcrypt password hashing (12 rounds), httpOnly cookies, rate limiting, audit logging, unverified user access control; enrichment + DSAR require verified users; opt-out remains public |
| Orchestrator + tier dispatch | `runner.py` | Implemented |
| Enricher modules (11) | Real tool integrations | Real subprocess/library/sidecar calls behind `app/clients/` and `app/integrations/`; degrade to empty fragments when a backend is absent |
| External clients layer | Config-selected free/paid backends | `app/clients/` (proxy, llm, email_verify, sidecar, process) + `app/integrations/` (linkedin, multilogin, browser); mode flags in `core/config.py` |
| Redis client | Queue + suppression + rate limits | Shared async client wired in lifespan; suppression, rate limiting, and queue all use it |
| Async job queue | Redis + RQ, worker process | Implemented — `/enrich` enqueues, `rq_worker` executes; Docker compose shares Postgres for cross-process polling |
| Database | PostgreSQL + JSONB | Postgres in Docker compose (asyncpg, **JSONB** via `JsonDoc`); SQLite local default; **Alembic** via Compose `migrate` job + `make migrate` locally; pytest/scripts may call `init_db()` |
| R2 photo cache | `aioboto3` → Cloudflare R2 | `storage/r2.py` — R2 PutObject + HeadObject when `R2_*` creds set; local `backend/.asset-cache/` fallback (CWD-safe path) |
| LinkedIn photo cache | Redis + Postgres by slug hash | `storage/photo_cache.py` + `PhotoCacheRecord`; slug-keyed TTL; cache-before-browser in `linkedin_photo.py` |
| Multilogin + Selenium | MLX launcher + Selenium Remote | `clients/multilogin.py`, `integrations/multilogin/profile_pool.py`, `integrations/linkedin/`; worker-only `ENABLE_TIER1`; `/enrich/sync` skips tier1 |
| Tier 1 pipeline dispatch | Tier 1 serial, tiers 2–4 parallel | `runner.py` `_dispatch(sync_mode=...)`; see `docs/TESTING_TIER1.md` |
| Tier 1 Docker ops | Worker image + compose override | `Dockerfile.worker` (Chromium + `.[enrichers]`); `docker-compose.tier1.yml` injects secrets via `env_file` (`WORKER_ENV_FILE` or `../.env`), forces `MULTILOGIN_SELENIUM_HOST`, maps `launcher.mlx.yt`/`host.docker.internal` → `host-gateway` or `MULTILOGIN_HOST_IP` (WSL2); `validate_tier1_settings()` fail-fast on worker boot; `tier1_*` Prometheus counters |
| Tier 1 hardening (3.7) | Session reuse, denylist, rate limits | `TIER1_SKIP_LOGIN_IF_SESSION_VALID`; `profile_pool.refund_view()`; `probe_tier1_canary.py`; configurable cooldowns |
| Tier 2 CLIs + scores | Sherlock/Maigret/SA in Docker | `sherlock-project` + `maigret` in `.[enrichers]`; bases 0.75/0.85; merge prefer-max; `e2e_tier2.sh` |
| Tier 3 CLIs + email verify | gitrecon/Harvester/sleuth/CrossLinked + AfterShip | CLIs in worker/api images; `email-verifier` sidecar; two-phase verify in `runner.py`; `EMAIL_VERIFY_LEVEL=basic\|smtp`; `e2e_tier3.sh` |
| LiteLLM disambiguation | Routed LLM calls | `LLM_MODE=stub|ollama|litellm` (default stub) via `clients/llm.py` |
| Langfuse tracing | Per disambiguation call | `clients.llm.trace()`; no-op until `LANGFUSE_*` set |
| Sidecars | 5+ isolated services | Real images; free-mode default-on, paid behind compose `profiles:`; default stack Compose healthchecks (incl. redis/api/worker/GMaps) |
| Compose healthchecks | Infra readiness gates | Default stack probes healthy; api/worker gate on healthy postgres + redis |
| Opt-out / DSAR auth | Opt-out public, DSAR authenticated | **Implemented (ADR 0009)** — Opt-out remains public (IP rate-limited); DSAR requires authenticated verified user; enrichment requires authenticated verified user |
| Audit logs | SQL + 5-year retention script | Implemented — `audit_logs` (compliance) + `auth_audit_logs` (auth events) |
| DSAR flow | `POST/GET /api/dsar` | Implemented — requires authenticated verified user (per ADR 0009) |
| Data erasure | Purge on opt-out/DSAR deletion | Implemented |
| Scrapoxy proxy pool | Rate-limit hardening | `ProxyProvider` (`PROXY_MODE=none|scrapoxy|paid`, default none = direct) |
| Change signals | changedetection.io webhook → notify | `POST /api/signals/changedetection` → `clients/notify.py` (`NOTIFY_WEBHOOK_URL`, optional `X-Signal-Token`) |
| Prometheus metrics | `/metrics` endpoint | Optional dependency |
| Job matching (Module 1) | `app/modules/job_matching/`, `app/workers/tasks/job_matching.py` | Real, scaffolded per `phase2_module1.md`. Depends on CV upload UI existing (currently missing — see that doc §11.10). |
| CV completeness chat (Module 2) | `app/modules/documents/cv_chat_service.py`, `app/clients/llm_tools.py` | Real, implemented per `phase2_module2.md`. Synchronous on `api`, no queue. Function-calling tool (`record_cv_answer`) constrains the model to structured answers, never free-form CV data (ADR 0014). |
| CV improvement feedback (Module 2) | `app/services/feedback_generator.py` (`generate_cv_improvement`), `app/workers/tasks/cv_improvement.py` | Real, implemented per `phase2_module2.md`. Shares `QUEUE_FEEDBACK` with Foundation Week 2's interview feedback. Writes to `cv_feedback_reports`, never overwrites the stored CV — draft-then-explicit-accept, no auto-apply. |
| Candidate portfolio (Module 2) | `app/modules/portfolio/` | Real, implemented per `phase2_module2.md`. Only Module 2 feature with an unauthenticated public route (`GET /api/portfolio/public/{slug}`, ADR 0014) — served by a separate `public_router` with no auth dependency, and a distinct `PublicPortfolioResponse` schema with no `user_id` field. |
| Job swipe deck (Module 2) | `app/modules/job_swipe/` | Real, implemented per `phase2_module2.md`. Read-only against Module 1's `job_matches`/`job_postings` (joined in `repository.py`) — never writes to either table; only writes its own `job_swipe_actions`. Depends on Module 1 shipping first. |
| Personalized outreach (Module 2) | `app/modules/outreach/`, `app/clients/perplexity.py` | Real, implemented per `phase2_module2.md`. New external dependency: Perplexity Sonar API (ADR 0014), degrades to a generic draft on failure. Every message starts `status="draft"`; "send" appends the mandatory CAN-SPAM disclosure footer and marks `sent`, but does not transmit email itself — the candidate copies/sends it externally (v1 scope; see `outreach/service.py`). |

Use this table when reviewing PRs, running `GRILLME.md` sessions, or planning the next delivery slice.

---

## Testing strategy

| Layer | What | Where |
|-------|------|-------|
| Shape tests | Every enricher returns valid dossier fragments | `tests/test_pipeline_shape.py` |
| Integration | Fake sidecars in CI via compose override | Implemented — `docker-compose.fake-sidecars.yml` + `scripts/e2e_fake_sidecars.sh` |
| Full-path E2E | CI compose + fake sidecars; optional live tier chain | `scripts/e2e_full_path.sh` + `scripts/e2e_full_path_runner.py` → `.e2e-results/full-path-report.json` |
| Load / performance | k6 concurrent traffic (health/ready + enrich); elevated rate limits + fake sidecars | `load/k6/main.js` + `scripts/run_load_test.py` → `.e2e-results/load-report.json` — see [`LOAD_TESTING.md`](LOAD_TESTING.md) |
| Manual QA | 20-profile canary run/score (`run_canary_score.py`, `tier*_canary_set.example.json`) | Implemented — Tier 2–4 uses in-repo public identifiers; Tier 1 needs local Multilogin + gitignored `tier1_canary_set.json` |

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

### Full-path E2E runner

Chains existing scripts for CI and/or live validation; writes `backend/.e2e-results/full-path-report.json`.

```bash
bash backend/scripts/e2e_full_path.sh              # --ci: compose test + fake sidecars
bash backend/scripts/e2e_full_path.sh --live       # probe + tier2/3 + strict
python backend/scripts/e2e_full_path_runner.py     # Windows-friendly wrapper
```

Set `E2E_SKIP_COMPOSE=1` to skip `e2e_compose_test.sh` when the stack is already running. See `docs/TESTING_TIER234.md` for stage details.

### Rate limits to respect (production)

Upstream caps (LinkedIn, GitHub, SMTP) and Hyrepath ingress limits are documented in one operator matrix: **[Upstream source limits](LEGAL.md#appendix-upstream-source-limits)** in `docs/LEGAL.md`. Summary:

- **LinkedIn:** ~20–25 profile views/day per Multilogin profile (`MULTILOGIN_DAILY_VIEW_LIMIT`)
- **GitHub API:** 5,000 req/hour authenticated — operator monitors beyond gitrecon throttles
- **SMTP verification:** ~10/min per Reacher instance (`EMAIL_VERIFY_SMTP_DELAY_SECONDS`)
- **API ingress:** 10 sync / 30 async / 20 compliance req/min (`MAX_*_REQUESTS_PER_MINUTE`)

---

## Related documentation

- `backend/README.md` — run and test commands
- `README.md` — monorepo overview (frontend + backend split)
- `docs/architecture-plan-azi-10-hyre-enrichment.md` — full production plan
- `docs/IMPLEMENTATION_NOTES.md` — AZI-11 delivery handoff
- `GRILLME.md` — challenge-mode readiness checks
- `CHANGELOG.md` — ticket-level release notes
- [`docs/adr/README.md`](../../docs/adr/README.md) — formal architecture decision records (why X over Y)

---

## Open questions and next slices

Resolved architecture decisions are recorded in [`docs/adr/README.md`](../../docs/adr/README.md) (e.g. [0001 async Redis/RQ](../../docs/adr/0001-async-redis-rq.md), [0002 SQLite vs Postgres](../../docs/adr/0002-sqlite-local-postgres-docker.md), [0003 pipeline model](../../docs/adr/0003-pipeline-enricher-model.md)).

**Remaining work (not yet ADR-worthy or still in flight):**

- GMaps sidecar validation against live deployments beyond free-stack smoke
- LiteLLM prompt tuning and cost dashboards once `LLM_MODE=litellm` is exercised in staging/prod

For new architectural choices or reversals, add ADR 0007+ (copy [`docs/adr/template.md`](../../docs/adr/template.md)) or open a GitHub issue with `[ADR]` prefix. For tier-specific bugs, use `[Tier N]` in issue titles (e.g. `[Tier 3] Reacher fallback fails on catch-all`).
