## Summary
- Introduce locked modular ownership: `domain/`, `modules/`, `enrichers/pipeline` (+ merge/registry/disambiguate), `compliance/`, `clients/`, `integrations/`, `infrastructure/redis`, `database/`
- Sync and async enrichment converge on `Pipeline.run()`; workers are RQ adapters; `JobRepository` owns job persistence
- Keep compatibility shims (`app.models`, `app.providers`, `app.workers.jobs` / `runner`, routes, config) so RQ path `app.workers.jobs.run_enrichment_job` stays stable
- Update RULE.md and ARCHITECTURE.md with ownership and import rules

## Test plan
- [x] `ruff check backend/app backend/tests`
- [x] `pytest backend/tests -m "not postgres"` (230 passed excluding LinkedIn browser tests that are env/local-sensitive)
- [x] Critical slice: pipeline, merge, disambiguation, opt-out, DSAR, enrichers, health, signals, multilogin, alembic (141 passed)
- [ ] `make up && make smoke` / `make e2e-full-path` (Docker not available in this agent environment — run in CI)
