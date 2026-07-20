# 0003. Pipeline + registry enricher execution model

- **Status:** Accepted
- **Date:** 2026-07-20

## Context

The backend wraps many open-source enrichers (Sherlock, gitrecon, Reacher, etc.) behind one dossier API. Without a single execution owner, merge logic, suppression checks, and tier dispatch would duplicate across routes, services, and workers.

## Decision

We chose **Pipeline + registry + thin adapters** over **enricher logic in routes** and a **monolithic orchestrator** because one `Pipeline` in `enrichers/pipeline.py` owns suppression, dispatch, merge, and disambiguation; enrichers register in `enrichers/registry.py` and return partial dicts; routes and workers only start or poll jobs. Putting enricher dispatch in routes was rejected — it breaks layer ownership and makes workers re-implement orchestration.

## Tradeoffs

- Every new enricher must follow `Enricher` in `base.py` and register in the registry — no ad-hoc subprocess calls from modules.
- Real tools run behind `clients/` and `integrations/`; missing sidecars degrade to empty fragments rather than failing the whole job.
- Workers must not import module routers or services (see `RULE.md` import rules).

## Consequences

- `EnrichmentService` starts/polls jobs; `Pipeline.run()` is the only enrichment execution path for sync and async.
- Merge lives exclusively in `enrichers/merge.py`; LLM policy in `enrichers/disambiguate.py`.
- Tier-specific E2E harnesses (`e2e_tier2.sh`, `e2e_tier3.sh`) validate real adapter integrations.
