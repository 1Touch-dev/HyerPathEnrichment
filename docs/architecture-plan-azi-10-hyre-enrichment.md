# AZI-10 — Hyrepath Enrichment: Architecture & Implementation Plan

## Scope assessment

The repository is currently a near-empty scaffold (`README.md`, `docs/`, `memory-bank/`) with no application code, infra, or test harness. This phase therefore defines the target production architecture, delivery slices, and concrete file/module plan for the Grunt role to implement.

## Recommended stack

- **Runtime**: Python 3.12+
- **Package/tooling**: `uv`, `pyproject.toml`
- **API**: FastAPI + Pydantic v2
- **Persistence**: PostgreSQL + SQLAlchemy 2 async + Alembic
- **Queue**: Redis + RQ
- **HTTP clients**: `httpx`
- **Object storage**: `aioboto3` for Cloudflare R2
- **Browser automation**: Playwright via provider adapter for LinkedIn photo flow
- **Observability**: structlog or stdlib JSON logging, Prometheus instrumentation, Langfuse, LiteLLM traces
- **Quality**: Ruff, mypy, pytest, pytest-asyncio, coverage, pre-commit
- **Infra**: Docker + Docker Compose + GitHub Actions

## Architectural shape

Use a layered modular monolith with plugin-style enrichers.

### Request flow

1. FastAPI route accepts request
2. Auth dependency validates bearer token/API key
3. Request schema validates one primary identifier + requested tiers
4. Service performs normalization + suppression check
5. Async job record is created
6. Queue service enqueues worker task for async flow, or orchestrator runs inline for sync flow
7. Orchestrator executes tier modules behind common enricher interface
8. Merge engine produces canonical dossier
9. Confidence engine scores entities and whole dossier
10. LLM disambiguator resolves ambiguous identities only below configured threshold
11. Repositories persist pipeline run, results, errors, dossier JSONB, and cached assets metadata
12. API returns job id or synchronous dossier payload

## Proposed repository layout

```text
app/
  __init__.py
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
    opt_out.py
    health.py
    metrics.py
  schemas/
    common.py
    auth.py
    enrich_request.py
    enrich_response.py
    dossier.py
    jobs.py
    opt_out.py
    health.py
  services/
    enrich_service.py
    dossier_service.py
    opt_out_service.py
    health_service.py
    queue_service.py
    asset_service.py
  orchestrators/
    enrichment_orchestrator.py
    pipeline_context.py
  enrichers/
    base.py
    registry.py
    tier1/linkedin_photo.py
    tier2/sherlock.py
    tier2/maigret.py
    tier2/social_analyzer.py
    tier3/gitrecon.py
    tier3/theharvester.py
    tier3/email_sleuth.py
    tier3/reacher.py
    tier3/aftership.py
    tier3/mailchecker.py
    tier3/crosslinked.py
    tier4/jobspy.py
    tier4/google_maps.py
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
  workers/
    rq_worker.py
    jobs.py
  clients/
    base.py
    http_sidecar.py
    linkedin_browser.py
    r2_client.py
    litellm_client.py
    langfuse.py
  storage/
    database.py
    redis.py
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
  utils/
    identifiers.py
    normalization.py
    dedupe.py
    time.py
    pagination.py
    exceptions.py

tests/
  unit/
  integration/
  api/
  workers/
  fixtures/
  mocks/

docker/
  api.Dockerfile
  worker.Dockerfile
  scripts/

docs/
  architecture.md
  api-reference.md
  deployment.md
  env.md
  development.md
  troubleshooting.md
  implementation-plan-azi-10.md

scripts/
  run_api.sh
  run_worker.sh
  migrate.sh
  seed_dev.sh

alembic/
compose.yaml
.env.example
pyproject.toml
pre-commit-config.yaml
```

## Core domain model plan

### Primary tables

- `api_keys`
  - id, key_prefix, key_hash, owner_label, is_active, scopes, rate_limit_profile, created_at, last_used_at
- `jobs`
  - id, status, request_type (`sync|async`), requested_tiers, submitted_identifier_type, submitted_identifier_value_hash, created_at, updated_at, started_at, completed_at
- `job_results`
  - id, job_id, dossier_id, status, result_json, error_summary
- `dossiers`
  - id, job_id, subject_key, dossier_jsonb, confidence_jsonb, metadata_jsonb, created_at
- `pipeline_runs`
  - id, job_id, request_id, status, timings_jsonb, tier_summary_jsonb, created_at, finished_at
- `pipeline_errors`
  - id, pipeline_run_id, tier, provider, error_type, message, details_jsonb, created_at
- `cached_assets`
  - id, asset_type, cache_key, source_url, storage_url, checksum, metadata_jsonb, expires_at
- `suppression_list`
  - id, identifier_hash, identifier_type, reason, source, created_at
- `llm_traces`
  - id, pipeline_run_id, prompt_key, request_json, response_json, decision, confidence, created_at
- `audit_logs`
  - id, actor_type, actor_id, action, target_type, target_id, metadata_jsonb, created_at
- optional `users` placeholder for future ownership/auth expansion

### JSONB strategy

Use normalized rows for queryable operations plus JSONB for:
- full dossier payload
- provider raw fragments
- confidence breakdown
- pipeline timings
- error details
- LLM reasoning trace envelopes

## API surface plan

### Endpoints

- `POST /enrich`
  - asynchronous submission
  - returns `202` with `job_id`, status, polling URL
- `GET /enrich/{id}`
  - returns job status and dossier if complete
- `POST /enrich/sync`
  - synchronous run with stricter timeout + reduced tier allowance via config
- `POST /api/opt-out`
  - hashes and stores suppressed identifier
- `GET /api/opt-out/check`
  - checks if identifier is suppressed
- `GET /health`
  - liveness
- `GET /ready`
  - readiness over db/redis/object storage dependencies
- `GET /metrics`
  - Prometheus scrape endpoint

### Route-to-service mapping

- `routes/enrich.py` → `EnrichService`
- `routes/opt_out.py` → `OptOutService`
- `routes/health.py` → `HealthService`
- `routes/metrics.py` → metrics exporter

No route should contain orchestration or persistence logic.

## Schema design plan

### Request schema

Single request object with optional identifier fields but enforce **exactly one** of:
- `email`
- `linkedin_url`
- `username`
- `company`
- `business`
- `job_search`

Additional fields:
- `tiers: list[int]`
- `correlation_id: str | None`
- `priority: str | None`
- tier-specific options:
  - business query params (`location`)
  - job query params (`remote`, `experience`, `location`)

### Response schema

- async submit response
- job status response
- sync dossier response
- canonical dossier schema with:
  - `photo`
  - `handles`
  - `emails`
  - `verified_emails`
  - `github`
  - `coworkers`
  - `jobs`
  - `business`
  - `confidence`
  - `sources`
  - `metadata`

## Enricher plugin plan

### Common contract

Define `BaseEnricher` with methods:
- `initialize()`
- `validate(request)`
- `run(context)`
- `normalize(raw_result)`
- `score(normalized_result)`
- `cleanup()`

### Registration

Use a registry keyed by tier + provider name. The orchestrator requests enrichers from registry based on enabled tiers/config. New provider addition should require:
1. one module
2. one registry entry

### Tier execution model

- Tier 1: serial, only when LinkedIn URL exists
- Tier 2: parallel fan-out across username providers
- Tier 3: parallel fan-out with configurable concurrency caps and per-provider timeouts
- Tier 4: conditional by query type (`job_search` vs `business`)

## Provider/sidecar design

### Client abstractions

- `BaseProviderClient`
- `HttpSidecarClient`
- typed clients per sidecar/provider

This avoids orchestrator changes when adding future HTTP sidecars.

### Provider notes

- **Tier 1 LinkedIn photo**: encapsulate Playwright/CDP/Multilogin concerns in `clients/linkedin_browser.py`; enricher returns only photo asset metadata and avoids profile field scraping.
- **Social Analyzer / Reacher / Google Maps / Changedetection**: treat as HTTP sidecars behind configurable base URLs.
- **GitRecon / theHarvester / Mailchecker / CrossLinked / Sherlock / Maigret**: support either subprocess wrapper or sidecar/client abstraction; prefer adapters so implementation details stay provider-local.

## Orchestrator plan

### Responsibilities

- normalize input
- run suppression check before any provider call
- create pipeline context with request/job/request-id
- choose tiers/providers
- execute providers with timeout/retry policy
- collect raw results
- hand off to merge engine
- hand off to confidence engine
- invoke LLM disambiguation for ambiguous entity pairs only
- persist outputs and state transitions

### Execution concerns

- use `asyncio.TaskGroup` or `asyncio.gather` for parallel enrichers
- isolate provider failures so one provider degrades but does not collapse the whole dossier
- record per-tier latency and provider error stats
- allow config-driven feature flags per provider

## Merge engine plan

Create a dedicated merge module with focused merge functions:
- `merge_photos`
- `merge_handles`
- `merge_emails`
- `merge_verified_emails`
- `merge_organizations`
- `merge_coworkers`
- `merge_jobs`
- `merge_business`
- `merge_sources`

Deduping heuristics:
- normalized email equality
- username similarity by platform + normalized handle
- organization name/domain similarity
- business entity dedupe by phone + website + normalized address
- source precedence rules for canonical values

## Confidence engine plan

### Inputs

- provider self-reported confidence
- cross-provider agreement count
- similarity signals
- domain/email alignment
- GitHub/public identity matches
- LLM confirmation result

### Output

- entity-level confidence scores
- dossier-level aggregate confidence
- explanation metadata for audit/debugging

### Configuration

Expose weighted knobs in settings:
- provider weight
- cross-source agreement bonus
- domain match bonus
- llm boost
- disposable email penalty
- SMTP verification bonus

## LLM disambiguation plan

### Triggering

Only evaluate candidate identity pairs below merge certainty threshold and above ambiguity threshold.

### Flow

1. build compact comparison prompt
2. call LiteLLM through wrapper
3. require structured response: `same_person: bool`, `confidence: float`, `reason: str`
4. reject malformed/low-confidence responses
5. log prompt/response to Langfuse and local `llm_traces`

## Storage/repository plan

Repositories should hide SQLAlchemy details from services/orchestrator.

Key repos:
- `ApiKeyRepository`
- `JobRepository`
- `DossierRepository`
- `PipelineRunRepository`
- `PipelineErrorRepository`
- `SuppressionRepository`
- `CachedAssetRepository`
- `AuditLogRepository`
- `LlmTraceRepository`

## Queue/worker plan

### Queue topology

- `enrichment` queue for primary jobs
- optional `dead_letter` queue for manual inspection

### Worker flow

- fetch job payload
- mark job started
- run orchestrator
- persist result/error
- mark job done/failed/blocked

### Retry policy

- provider timeouts/retriable network failures: bounded retries with backoff
- suppression/auth/validation errors: no retry
- dead-letter after max retries

## Security plan

- bearer auth via API key table and secure hash compare
- per-key + per-IP rate limiting via Redis
- request body max size middleware
- strict CORS allowlist from config
- security headers middleware
- no secrets in logs
- suppression identifiers hashed using stable salted hash
- audit log for enrich, opt-out, auth failures

## Observability plan

### Logging

Structured JSON with:
- request_id
- job_id
- pipeline_run_id
- tier
- provider
- latency_ms
- outcome

### Metrics

- request count/status
- enrichment job count by status
- queue depth
- tier/provider latency histograms
- provider failure counters
- dossier generation duration

### Health

- liveness: process ok
- readiness: db + redis + optional R2 check

## Caching plan

Redis-backed cache service with namespaced keys:
- linkedin photo by normalized LinkedIn URL
- username lookups by provider + handle
- GitHub/OSINT fragments by identifier hash
- jobs/business queries by normalized query signature

Add TTLs in config per provider/class.

## Error model plan

Create domain exceptions:
- `TierUnavailableError`
- `RateLimitedError`
- `ProviderTimeoutError`
- `ProviderFailureError`
- `SuppressedIdentifierError`
- `AuthenticationFailureError`
- `ValidationFailureError`
- `NotFoundError`

Map these centrally to consistent API error responses.

## Infra plan

### Docker Compose services

- api
- worker
- redis
- postgres
- social-analyzer
- reacher
- google-maps-scraper
- langfuse
- litellm
- changedetection

Optional later:
- pgadmin/adminer for local-only profile
- Prometheus/Grafana for richer local observability

### Dockerfiles

Separate API and worker Dockerfiles sharing a base image/layer strategy.

## CI/CD plan

GitHub Actions pipeline should run:
- Ruff
- mypy
- pytest + coverage
- docker build for api and worker
- optional Alembic migration sanity check

## Documentation plan

Deliver docs as separate files:
- `README.md` quickstart
- `docs/architecture.md`
- `docs/api-reference.md`
- `docs/deployment.md`
- `docs/env.md`
- `docs/development.md`
- `docs/troubleshooting.md`

## Delivery slices for Grunt

### Slice 1 — foundation
- scaffold Python project with `uv`, FastAPI app, config, logging, error handling
- add Docker, Compose, lint/test tooling, pre-commit
- add base models, DB session, Redis session, Alembic init

### Slice 2 — domain/core pipeline
- request/response schemas
- repositories for jobs/dossiers/pipeline runs/suppression/api keys
- auth dependency + rate limiting + middleware
- queue service + worker bootstrap
- orchestrator skeleton + enricher registry + base interfaces

### Slice 3 — tier implementations
- implement Tier 2 and Tier 4 first behind adapters/mocks
- implement Tier 3 providers incrementally with feature flags
- implement Tier 1 LinkedIn photo flow with asset upload abstraction

### Slice 4 — merge/confidence/LLM
- merge engine
- confidence engine
- LiteLLM + Langfuse integration
- final dossier persistence and GET polling response

### Slice 5 — hardening
- metrics, health/readiness, audit logs, cache TTLs, dead-letter handling
- comprehensive tests aiming toward 90% coverage
- final docs polish

## Key risks / engineering decisions

- **Provider instability**: isolate each provider with timeouts, retries, and feature flags.
- **Async + RQ mismatch**: RQ is sync-worker-oriented; Grunt should wrap async orchestration with `asyncio.run()` in worker jobs or consider a disciplined async bridge rather than leaking event-loop logic everywhere.
- **Tier 1 browser complexity**: keep browser/CDP provider fully encapsulated in client module to avoid contaminating pipeline logic.
- **Legal/compliance sensitivity**: suppression checks must happen before any outbound provider call.
- **Coverage target realism**: external providers should be mocked behind adapters so unit/integration tests remain deterministic.

## Explicit handoff to Grunt

Build from the above structure in this order:
1. repo scaffold and tooling
2. app bootstrap and config
3. models/repos/migrations
4. auth + middleware + routes
5. queue + worker + orchestrator
6. enricher registry + provider adapters
7. merge/confidence/LLM
8. docker/compose/CI/docs/tests

Do **not** collapse layers into route files. Keep provider logic isolated and testable.

## Terminal change log

- Inspected repository root and confirmed it is effectively empty aside from scaffold files.
- Reviewed local Paperclip agent role notes in `.paperclip/AGENTS.md`.
- Added planning artifact: `docs/architecture-plan-azi-10-hyre-enrichment.md`.
- Did **not** modify application code, infra code, or Git remote state.

ARCHITECT_DONE: plan ready for Grunt.
