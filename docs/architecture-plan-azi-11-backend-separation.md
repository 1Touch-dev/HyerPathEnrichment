# AZI-11 — Backend Separation & Production Backend Plan

## Scope

This repository is currently a **frontend-only Next.js app** that simulates enrichment results with mock data. The requested phase for **The Architect** is to produce a concrete implementation plan for splitting the codebase into:

- `frontend/` — the existing Next.js UI
- `backend/` — a new production-grade Python service

No code implementation is included in this phase.

## Current repo assessment

### Current stack

- Next.js 14
- React 18
- TypeScript 5
- App Router API route at `app/api/enrich/route.ts`
- Mocked enrichment generation in `src/lib/mock-data.ts`

### Current frontend responsibilities found in repo

- `app/page.tsx`
  - page composition and client state ownership
- `components/IntakeForm.tsx`
  - request capture and POST to `/api/enrich`
- `components/PipelineOverview.tsx`
  - displays pipeline stages
- `components/DossierView.tsx`
  - displays merged dossier output
- `src/lib/types.ts`
  - shared UI-facing request/result types
- `src/lib/mock-data.ts`
  - deterministic fake enrichment payloads
- `app/api/enrich/route.ts`
  - temporary mock backend endpoint inside frontend app

### Key architectural gap

The current repo uses a frontend-local API route as a demo backend. For the requested production direction, that route should be removed from frontend ownership and replaced with a separate backend service under `backend/`.

---

## Target repo layout

```text
frontend/
  app/
  components/
  src/
  public/
  package.json
  tsconfig.json
  next.config.js

backend/
  app/
    main.py
    config/
    api/
    routes/
    schemas/
    services/
    workers/
    storage/
    repositories/
    models/
    enrichers/
    orchestrators/
    merge/
    confidence/
    llm/
    security/
    middleware/
    clients/
    utils/
  tests/
  docs/
  docker/
  alembic/
  pyproject.toml
  .env.example
  README.md

docker-compose.yml
README.md
```

## Frontend separation plan

### Move into `frontend/`

The Grunt should relocate the current UI app intact into `frontend/`:

- `app/` → `frontend/app/`
- `components/` → `frontend/components/`
- `src/` → `frontend/src/`
- `package.json` → `frontend/package.json`
- `package-lock.json` → `frontend/package-lock.json`
- `tsconfig.json` → `frontend/tsconfig.json`
- `next.config.js` → `frontend/next.config.js`
- `next-env.d.ts` → `frontend/next-env.d.ts`
- any frontend-only docs can remain repo-root or be mirrored under `frontend/docs/` if desired

### Frontend behavior changes required

1. Replace local fetch target:
   - from `fetch('/api/enrich', ...)`
   - to `fetch(`${NEXT_PUBLIC_API_BASE_URL}/enrich`, ...)`
2. Remove dependency on App Router mock endpoint:
   - delete `frontend/app/api/enrich/route.ts`
3. Keep existing presentation components largely unchanged.
4. Keep `src/lib/types.ts` as frontend DTO/view-model types, but align field names with backend response schema.
5. Optionally keep mock data only for story/demo fallback, not as the primary runtime path.

### Frontend pages/components impact

- `frontend/app/page.tsx`
  - remains the shell page
  - may later support async polling if backend `POST /enrich` returns `202`
- `frontend/components/IntakeForm.tsx`
  - should be the main integration touchpoint
  - needs configurable API base URL and better error/status handling
- `frontend/components/PipelineOverview.tsx`
  - can continue to render pipeline stages from returned job metadata
- `frontend/components/DossierView.tsx`
  - should map directly onto backend dossier schema

---

## Backend architecture plan

### Backend stack

- Python 3.12+
- FastAPI
- Pydantic v2
- SQLAlchemy 2 async
- Alembic
- PostgreSQL
- Redis
- RQ
- httpx
- asyncio
- aioboto3
- LiteLLM
- Langfuse
- Ruff
- mypy
- pytest
- pytest-asyncio
- Docker / Docker Compose
- `uv` package manager

## Backend folder structure

Per the user’s preference, all backend code must live under `backend/`, not repo root.

```text
backend/
  app/
    main.py
    bootstrap.py
    config/
      settings.py
      logging.py
      metrics.py
    api/
      dependencies.py
      error_handlers.py
      router.py
    routes/
      enrich.py
      health.py
      opt_out.py
      metrics.py
    schemas/
      enrich_request.py
      enrich_response.py
      dossier.py
      jobs.py
      health.py
      opt_out.py
      common.py
    services/
      enrich_service.py
      dossier_service.py
      opt_out_service.py
      queue_service.py
      health_service.py
      asset_service.py
    workers/
      rq_worker.py
      jobs.py
      runner.py
    storage/
      database.py
      redis.py
      r2.py
    repositories/
      api_keys.py
      jobs.py
      dossiers.py
      audit_logs.py
      suppression.py
      cached_assets.py
      llm_traces.py
      pipeline_runs.py
      pipeline_errors.py
      job_results.py
    models/
      base.py
      api_key.py
      job.py
      dossier.py
      audit_log.py
      suppression_entry.py
      cached_asset.py
      llm_trace.py
      pipeline_run.py
      pipeline_error.py
      job_result.py
    enrichers/
      base.py
      registry.py
      tier1/
        linkedin_photo.py
      tier2/
        sherlock.py
        maigret.py
        social_analyzer.py
      tier3/
        gitrecon.py
        theharvester.py
        email_sleuth.py
        reacher.py
        aftership.py
        mailchecker.py
        crosslinked.py
      tier4/
        jobspy.py
        local_business.py
    orchestrators/
      enrichment_orchestrator.py
      pipeline_context.py
    merge/
      merge_engine.py
      strategies.py
    confidence/
      engine.py
      weights.py
    llm/
      disambiguator.py
      prompts.py
      langfuse_client.py
      llm_router.py
    security/
      auth.py
      rate_limit.py
      hashing.py
      headers.py
    middleware/
      request_id.py
      logging.py
      body_limit.py
      cors.py
    clients/
      base.py
      http_sidecar.py
      multilogin.py
      linkedin_browser.py
      litellm_client.py
      langfuse.py
    utils/
      identifiers.py
      normalization.py
      dedupe.py
      exceptions.py
      time.py
  tests/
    unit/
    integration/
    api/
    workers/
    fixtures/
    mocks/
  docker/
    Dockerfile.api
    Dockerfile.worker
    docker-compose.backend.yml
  docs/
    ARCHITECTURE.md
    API_REFERENCE.md
    DEPLOYMENT.md
    ENVIRONMENT.md
    DEVELOPMENT.md
    TROUBLESHOOTING.md
  alembic/
  scripts/
    create_session.py
    smoke_test.py
  pyproject.toml
  .env.example
  README.md
  DEVELOPER_GUIDE.md
```

---

## Backend API plan

### Endpoints

- `POST /enrich`
  - async submission
  - returns job metadata (`202 Accepted`) with `job_id`
- `GET /enrich/{id}`
  - job status + dossier when ready
- `POST /enrich/sync`
  - bounded synchronous enrichment for interactive use
- `POST /api/opt-out`
  - suppression/GDPR/LGPD/CCPA workflow
- `GET /api/opt-out/check`
  - suppression status lookup
- `GET /health`
  - liveness
- `GET /ready`
  - readiness
- `GET /metrics`
  - Prometheus scrape

### Route ownership

Routes must stay thin:

- route → schema validation / dependency injection
- service → business workflow
- orchestrator → enrichment coordination
- repository → persistence

No business logic in routes.

---

## Data/contracts plan

### Frontend request contract

The current UI sends:

- `email`
- `linkedinUrl`
- `username`
- `company`
- `business`
- `jobSearch`
- `requestedTiers`

### Backend normalization plan

Backend should accept the frontend contract but normalize internally to snake_case domain objects:

- `linkedinUrl` → `linkedin_url`
- `jobSearch` → `job_search`
- `requestedTiers` → `requested_tiers`

To reduce frontend churn, Pydantic aliases should support camelCase input while backend code uses snake_case.

### Final dossier shape

Maintain compatibility with the current UI-facing shape where practical:

- `photo`
- `handles`
- `emails`
- `verifiedEmails` / internally `verified_emails`
- `github`
- `coworkers`
- `jobs`
- `business`
- `confidence`
- `sources`
- `metadata`

Recommendation: backend returns canonical snake_case and a frontend adapter maps to current TS types, or backend uses response aliases to preserve camelCase externally.

---

## Persistence plan

### Required tables

- `users` (future-facing)
- `api_keys`
- `jobs`
- `dossiers`
- `audit_logs`
- `suppression_list`
- `cached_assets`
- `llm_traces`
- `pipeline_runs`
- `pipeline_errors`
- `job_results`

### Storage strategy

- normalized SQL tables for operational querying
- JSONB dossier persistence for complete response bodies
- Redis for queue + cache + rate limiting
- Cloudflare R2 for media assets such as LinkedIn profile photo captures

---

## Pipeline/orchestrator plan

### Ordered flow

1. validate request
2. normalize identifiers
3. suppression check
4. create job
5. dispatch requested tiers
6. merge outputs
7. confidence scoring
8. LLM disambiguation
9. persist dossier
10. return job id / response payload

### Tier plan

#### Tier 1
- LinkedIn photo enrichment only
- browser automation isolated behind dedicated client
- upload asset to R2

#### Tier 2
- username discovery
- parallel providers:
  - Sherlock
  - Maigret
  - Social Analyzer

#### Tier 3
- deep OSINT
- modular providers:
  - GitRecon
  - theHarvester
  - Email Sleuth
  - Reacher
  - AfterShip Email Verifier
  - Mailchecker
  - CrossLinked

#### Tier 4
- job intelligence via JobSpy
- business intelligence via Google Maps scraper

---

## Merge/confidence/LLM plan

### Merge engine

Dedicated backend service responsible for:

- identity consolidation
- deduplication
- email merge
- social merge
- organization merge
- jobs merge
- business merge
- final dossier assembly

### Confidence engine

Weighted scoring inputs:

- provider self-confidence
- cross-source agreement
- identifier similarity
- domain match
- username similarity
- email verification
- GitHub match
- LLM confirmation

### LLM disambiguation

- invoked only for ambiguous identities
- LiteLLM wrapper
- Langfuse trace logging
- structured verdict: same person yes/no + confidence + reason

---

## Security and compliance plan

- bearer token auth using API keys
- Redis-backed rate limiting:
  - per API key
  - per IP
  - per endpoint
- request size limits
- strict input validation
- CORS config
- security headers
- audit logging
- suppression check before any outbound enrichment call
- hashed identifiers in suppression store

---

## Infra/devops plan

### Root-level orchestration

Keep a root `docker-compose.yml` that coordinates both apps:

```text
frontend
backend-api
backend-worker
postgres
redis
social-analyzer
reacher
google-maps-scraper
langfuse
litellm
changedetection
```

### Frontend container

- Next.js runtime
- env points to backend service URL

### Backend containers

- API container
- worker container
- shared Python base image strategy

### CI/CD

At minimum:

- frontend: install, typecheck, build
- backend: ruff, mypy, pytest, docker build
- optionally integration smoke on compose profile

---

## Recommended delivery slices for Grunt

### Slice 1 — repository separation

- move current Next.js app into `frontend/`
- make it boot from that subfolder
- update root README to describe monorepo layout
- replace local `/api/enrich` dependency with configurable backend URL

### Slice 2 — backend foundation

- scaffold `backend/` with FastAPI, config, logging, health/readiness, schemas
- add `pyproject.toml`, Dockerfiles, `.env.example`, Alembic bootstrap

### Slice 3 — persistence + auth + queue

- SQLAlchemy models and repositories
- Redis, RQ, API key auth, rate limiting
- job creation/status plumbing

### Slice 4 — orchestrator and providers

- base enricher interface and registry
- provider adapters
- worker-run orchestration

### Slice 5 — merge, confidence, LLM, caching

- merge engine
- confidence engine
- LiteLLM + Langfuse integration
- Redis caches and R2 asset storage

### Slice 6 — frontend integration

- connect form to backend
- support async job polling state
- align dossier rendering with real backend responses

### Slice 7 — hardening

- test coverage
- metrics
- audit logs
- docs
- compose/dev workflow polish

---

## Risks and decisions to preserve

- **Do not keep backend code in root `app/`** — backend belongs under `backend/` only.
- **Do not leave production logic in Next.js route handlers**.
- **Keep the current UI working during separation** by moving first, then swapping the data source.
- **Use adapters for provider integrations** so sidecars/providers can change without rewriting orchestrator logic.
- **Treat the current `src/lib/mock-data.ts` as demo-only** after backend integration lands.

---

## Explicit handoff artifacts for Grunt

### What Grunt should change

- create `frontend/` and relocate all existing frontend code there
- create full `backend/` project scaffold and implementation
- wire frontend to backend over HTTP
- preserve the current UI behavior while replacing the mocked internal backend

### What Grunt should not do in this Architect phase output

- no code has been implemented here
- no PR should be created
- no branch should be pushed by Architect

---

## Terminal log of Architect work

- inspected repo root and confirmed current codebase is frontend-only Next.js
- inspected current API shim at `app/api/enrich/route.ts`
- inspected current request/result types in `src/lib/types.ts`
- inspected current mock enrichment generator in `src/lib/mock-data.ts`
- reviewed existing repo docs to align the new separation plan
- added planning artifact: `docs/architecture-plan-azi-11-backend-separation.md`
- did not modify application source behavior

ARCHITECT_DONE: plan ready for Grunt.
