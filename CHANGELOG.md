# Changelog

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
- preserved frontend application at repo root

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
