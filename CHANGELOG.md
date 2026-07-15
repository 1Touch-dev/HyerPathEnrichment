# Changelog

## [Infra] - 2026-07-15

### Added

- Compose healthchecks for the default stack: `redis`, `api`, `worker`, and `google-maps-scraper` (postgres / social-analyzer / email-verifier already had them)
- `curl` in `Dockerfile.google-maps-scraper` for the `/api/docs` readiness probe

### Changed

- `api` and `worker` wait for Redis with `condition: service_healthy` (same gate pattern as Postgres)

## [Enrichers] - 2026-07-08

### Added

- Phase 0 provider layer (`backend/app/providers/`): `ProxyProvider`, `BrowserProvider`, config-selected LLM disambiguation (`llm.py`), `EmailVerifier` chain, `SidecarClient`, and a shared `run_command` subprocess helper
- Five free/paid mode flags in `config.py` + `.env.example` (`PROXY_MODE`, `BROWSER_MODE`, `LLM_MODE`, `EMAIL_VERIFY_LEVEL`, `ENABLE_TIER1`) plus per-tier optional settings
- `POST /api/signals/changedetection` webhook consumer (optional shared-secret header)
- `tests/test_enrichers.py` per-enricher unit tests (mocked subprocess/HTTP); `enrichers` optional-dependency group in `pyproject.toml`

### Changed

- All 11 enrichers now call real backends (subprocess/library/sidecar) selected by the provider layer and degrade to a valid empty fragment when a tool/sidecar/key is missing; the `Enricher.run` template wraps a new `_fetch` seam
- Tier 1 LinkedIn photo gated behind `ENABLE_TIER1` and routed through `BrowserProvider`
- `docker-compose.yml`: real sidecar images; free-mode ones default-on, paid/heavy ones behind `profiles:`
- `llm_router.LiteLLMDisambiguator` is mode-aware (same `compare()` signature) with a Langfuse trace no-op hook

### Notes

- No orchestrator, `Enricher` protocol, or `Dossier` shape changes: free -> paid is an env flip only
- Upstream CLI/sidecar contracts (gitrecon JSON, social-analyzer/GMaps endpoints) are best-effort and need tuning against live deployments

## [AZI-11] - 2026-07-07

### Added

- top-level documentation for the split frontend/backend repository layout
- release handoff notes describing the backend placement under `backend/`
- backend delivery summary covering routes, orchestrator, enrichers, Docker assets, and tests
- updated README instructions for frontend and backend setup/run flows

### Delivered in code

- dedicated `backend/` folder containing the Python/FastAPI backend
- backend API entrypoint, auth guard, enrichment routes, opt-out routes, and health route
- modular enrichment worker/orchestrator and provider modules
- backend Dockerfiles, compose configuration, environment template, and tests
- moved frontend application into `frontend/`

### Notes

- This ticket documents and finalizes the repo split so frontend and backend are clearly separated.
- Documentation has been aligned to the implemented AZI-11 structure for automated PR completion.

## [AZI-10] - 2026-07-07

### Added

- documentation for the shipped HyerEnrichment Next.js demo experience
- README coverage for setup, run flow, scripts, and current scope
- implementation notes for deployment and PR handoff
- ticket-level changelog entry for automated PR review

### Delivered in code

- intake form for enrichment identifiers and tier selection
- pipeline trace UI for the 10-stage enrichment flow
- merged dossier view with mocked identity, email, GitHub, jobs, business, and confidence data
- deterministic sample data model to support local review and demos

### Notes

- This repository currently contains a frontend/demo implementation, not the full backend platform described in the original long-form product brief.
- Documentation has been aligned to the code that actually exists in this branch so deployment and PR review are accurate.
