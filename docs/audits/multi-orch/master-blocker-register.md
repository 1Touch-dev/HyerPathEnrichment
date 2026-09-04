# Multi-Orch Master Blocker Register

- Date: 2026-09-04
- Coordinator: ORCH-ROOT
- Baseline: `R2-BASELINE-2026-09-04`
- Source packets:
  - `docs/audits/multi-orch-product-wave1-dec-d002-precedence-2026-09-04.md`
  - `docs/audits/multi-orch/orch-qa-wave1-packet-2026-09-04.md`
  - `docs/audits/multi-orch/orch-infra-wave1-g1-packet-2026-09-04.md`
  - `docs/audits/multi-orch-adr21-wave1-decision-packet-2026-09-04.md`

## Overall status

Wave 1 packet preparation is complete and the required Wave 2 owner decisions were
approved in-session for this run. The program is no longer blocked on decision intake
for Wave 2 execution, but several technical and live-environment blockers remain open.

## Blocker register

| Blocker ID | Current status | Exact owner(s) | Backing evidence / packet | Pending decision(s) | What this blocker is holding | What it unlocks once resolved |
|---|---|---|---|---|---|---|
| `BLK-PG-001` | `BLOCKED` | `ORCH-INFRA`; Infra human owner for disposable PG credentials and compose password gate | `docs/audits/multi-orch/orch-infra-wave1-g1-packet-2026-09-04.md` | Infra credential authorization for `POSTGRES_PASSWORD`, `DATABASE_URL`, `TEST_DATABASE_URL` | PostgreSQL migration rehearsal and concurrency evidence remain unstartable | `PG-REHEARSAL-001`, `PG-CONCURRENCY-001`, later `FINAL-REG-013` |
| `BLK-PILOT-001` | `BLOCKED` | `ORCH-INFRA`; Product human + Infra human decision owners | `docs/audits/multi-orch/orch-infra-wave1-g1-packet-2026-09-04.md`; `docs/audits/multi-orch-product-wave1-dec-d002-precedence-2026-09-04.md`; `docs/audits/multi-orch/evidence/pilot/PILOT-DEPLOY-001-2026-09-04.md`; `docs/audits/multi-orch/evidence/pilot/ROLLBACK-LIVE-001-2026-09-04.md`; `docs/audits/multi-orch/evidence/pilot/PILOT-DEPLOY-001-local-only-2026-09-04.md`; `docs/audits/multi-orch/evidence/pilot/ROLLBACK-LIVE-001-local-only-2026-09-04.md` | Either a true remote environment, or at minimum a runnable local-only current-RC stack plus a runnable previous-version anchor | Wave 3 now has both a failed real staging attempt and a failed local-only compose rehearsal; the remote path lacked host credentials, while the local path was blocked by Docker `no space left on device` before the RC stack could start | Complete a runnable pilot deploy + rollback rehearsal, then unblock `G3` |
| `BLK-T4-001` | `READY FOR QA RE-REVIEW` | `ORCH-INFRA` + `ORCH-QA`; decision owners Infra human + QA human; Security reviewer | `docs/audits/multi-orch/orch-infra-wave1-g1-packet-2026-09-04.md`; `docs/audits/multi-orch/orch-qa-wave1-packet-2026-09-04.md`; `docs/audits/multi-orch/evidence/AUTH-SETUP-001-2026-09-04.md`; `docs/audits/multi-orch/evidence/T4-LIVE-001-2026-09-04.md` | Independent QA re-review of the corrected evidence package pinned to executed revision `b75883cbdce230b59abc8b59fae587d51db07a96` | Scoped non-production auth setup evidence plus mixed live/hybrid T4 evidence are now captured honestly; closure still depends on fresh independent QA review and this package does not claim standalone live D002 or ADR21 completion | `AUTH-SETUP-001`, scoped `T4-LIVE-001`, later `FINAL-REG-006` through `FINAL-REG-009` |
| `BLK-SEC-001` | `PARTIAL` | `ORCH-SECURITY`; Security human + Product human decision owners | `docs/audits/multi-orch-adr21-wave1-decision-packet-2026-09-04.md` | Remaining privileged-route enforcement, BFF propagation, and independent review sign-off | Catalog + partial route hardening landed, but reviewer-confirmed ADR21 gaps still prevent closure | `ADR21-IMPL-001`, `ADR21-TEST-001` through `ADR21-TEST-008`, later ADR21 live and regression coverage |
| `BLK-PROD-002` | `PARTIAL` | `ORCH-PRODUCT`; Product human decision owner; Security human reviewer | `docs/audits/multi-orch-product-wave1-dec-d002-precedence-2026-09-04.md` | Remaining desk-page/backend permission-boundary alignment | Core FE permission helpers were corrected, but reviewer-confirmed shell/page/API drift still prevents closure | `D002-IMPL-001`, `D002-TEST-001` through `D002-TEST-005`, later D002 live and regression coverage |

## Readiness notes by blocker

### `BLK-PG-001`

- Infra has defined exact deferred commands and evidence folders.
- Infra has not yet supplied or approved disposable PostgreSQL credentials.
- This blocker affects Wave 3 evidence, not Wave 2 policy implementation directly.

### `BLK-PILOT-001`

- Product and Infra decisions are approved for later use.
- The RC is now pinned and pushed at `85fa8f5654ef6393a90c65dfb1905c1c5859dde1`
  on `origin/product-doors/baseline`.
- Wave 3 attempted the repo's real staging deploy workflow:
  <https://github.com/1Touch-dev/HyerPathEnrichment/actions/runs/33858619483>
- `await-ci` and `build-and-push` succeeded; `deploy-staging` failed before host
  contact with `error: missing server host`.
- The failed job env dump also showed blank `GHCR_USER` and `GHCR_TOKEN`, so the
  required staging deploy secrets were not available to the run.
- No live base URL, `/ready`, smoke, or rollback rehearsal evidence could be
  produced honestly from this attempt.
- A second, explicitly local-only rehearsal was then attempted using
  `docker-compose.yml` + `docker-compose.staging.yml` + local image overrides
  under compose project `wave3pilotlocal`.
- The local env file validated, and `6da855b` was accepted as a plausible
  previous-version rollback anchor because no `backend/alembic/` changes exist
  between that revision and the RC.
- The local-only rehearsal still failed before the RC stack could start because
  Docker hit `no space left on device` during image export/extraction and again
  during `docker compose up`.
- Therefore this blocker remains open on two honest grounds: there is still no
  true remote environment, and the current machine could not complete the
  fallback local-only RC rehearsal either.
- Monitoring-backed expansion evidence remains unavailable unless Infra provides it later.

### `BLK-T4-001`

- QA has a full execution matrix and evidence handling rules.
- Infra has a concrete environment packet.
- The non-production-only setup path has been hardened in code.
- Live non-production backend handoff, separate `AUTH-SETUP-001` setup evidence, and scoped `T4-LIVE-001` execution evidence are now captured in the committed evidence folder.
- The evidence package is pinned to executed revision `b75883cbdce230b59abc8b59fae587d51db07a96`.
- Hybrid `/api/auth/me` and `/api/auth/login` cases are now called out explicitly as regression-only support rather than full live-actor proof.
- D002 / ADR21 bookkeeping rows were restored for traceability and are not over-claimed as separately executed live cases.
- The blocker is ready for independent QA re-review; it is not fully closed until that review happens.

### `BLK-SEC-001`

- Security packet recommended a full code-grounded privileged-operation catalog with
  fail-closed treatment for unmapped operations and continued unavailability for `P4`,
  queue retry, and feature-flag mutations.
- The catalog and all reviewed Wave 2 `P1` routes are now implemented with focused
  follow-up idempotency enforcement.
- Frontend and BFF `Idempotency-Key` propagation gaps identified by the first review
  were fixed in a follow-up pass.
- A second re-review found one remaining ADR21-related UI exposure: reachable
  `user.role.assign` despite ADR21 unavailability. This second follow-up removes that path.
- Remaining closure item: fresh independent re-review sign-off.

### `BLK-PROD-002`

- Product packet recommends a permission-centric precedence model.
- Core FE helper logic now follows that model.
- Follow-up changes completed the remaining reviewed desk-route and backend staff-surface
  permission hardening.
- A second re-review found one stale D-002 artifact: `frontend/e2e/desk-personas.spec.ts`
  still encoded owner-only access. This second follow-up updates it to the approved
  permission-centric matrix.
- Remaining closure item: fresh independent re-review sign-off.

## ORCH-ROOT conclusion

Wave 1 packet prep is complete and the required Wave 2 approvals are now on record for
this run. The blocker picture has shifted from decision intake to implementation
completion and live-environment evidence.
