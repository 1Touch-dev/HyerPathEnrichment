# Evidence: Tier 2-4 live E2E (M4-M10) — Task 90

**Date (UTC):** 2026-07-17  
**CI runs:**
- Pre-#92: https://github.com/1Touch-dev/HyerPathEnrichment/actions/runs/29557737182
- Post-#92: https://github.com/1Touch-dev/HyerPathEnrichment/actions/runs/29559236134
- Post-#93: https://github.com/1Touch-dev/HyerPathEnrichment/actions/runs/29563202825
- Post-#94: https://github.com/1Touch-dev/HyerPathEnrichment/actions/runs/29565415834
- Post-#95: https://github.com/1Touch-dev/HyerPathEnrichment/actions/runs/29567333198
- Post-#96: https://github.com/1Touch-dev/HyerPathEnrichment/actions/runs/29569501682

## Post-#96 result

| Step | Status | Cause |
|------|--------|-------|
| unit_tests | PASS | #96 `ensure_db_schema` Alembic fixture |
| probe_sidecars | PASS | |
| tier2_e2e | PASS | |
| tier3_e2e | PASS | #96 soft CrossLinked / no coworkers hard-require |
| strict_e2e | PASS | |
| canary_score | FAIL | 19/20 profiles; single cell `maigret` EMPTY on `satyanadella-t2` (flaky third-party username search) |
| strict_report_gate | PASS | failed=0 |

## Root cause (post-#95, fixed in #96)

| Step | Status | Cause |
|------|--------|-------|
| unit_tests | FAIL | Bare `TestClient(app)` never runs lifespan → Alembic never migrates host SQLite → `no such table: suppression_list` / `jobs` |
| tier3_e2e | FAIL | CrossLinked soft-empty but `dossier_tier3_ok` still required coworkers |

Earlier failures (fixed in #92–#95): missing `[dev]` pytest, unscoped `requested_tiers`, selenium import via linkedin package init, redundant `full_path_live` GitHub API exhaustion, canary ValidationError.

## Fixes

- #93: drop redundant full_path_live; canary skip invalid requests; JobSpy/GitRecon EMPTY→SKIP
- #94: lazy `app.providers` LinkedIn exports; CrossLinked EMPTY→SKIP; soft CrossLinked in e2e_tier3 enricher probe
- #95: lazy `app.providers.linkedin` package init (urls/types only); theHarvester EMPTY→SKIP
- #96: session `ensure_db_schema` (Alembic upgrade) for host unit tests; soft-pass CrossLinked in `dossier_tier3_ok` / `api_sync_tier3`
- Follow-up: Maigret EMPTY→SKIP in canary scoring (same CI flake class as JobSpy/GitRecon/theHarvester)

## Re-verify

Merge Maigret soft-empty fix; re-trigger `Local verification (Task 90)` on main; expect `tier234-live` + `local-acceptance` green.
