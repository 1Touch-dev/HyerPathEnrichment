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

Wave 1 packet preparation is complete, Wave 2 is treated as independently accepted
for this run, and Wave 4 now includes the explicit local-only pilot waiver:
`LOCAL_ONLY_PILOT_EVIDENCE: yes`. The five original blockers are therefore
closed for certification purposes within the accepted plan scope.

The two post-certification ORCH-CERT defects have since been remediated on
`origin/product-doors/baseline` at `37e90081c7bd5d6d1a463f791b6bb668bddc0e35`.
The remaining note is external release-signal completion, not another code defect.

## Blocker register

| Blocker ID | Current status | Exact owner(s) | Backing evidence / packet | Pending decision(s) | What this blocker is holding | What it unlocks once resolved |
|---|---|---|---|---|---|---|
| `BLK-PG-001` | `RESOLVED FOR THIS RUN` | `ORCH-INFRA`; Infra human owner for disposable PG credentials and compose password gate | `docs/audits/multi-orch/orch-infra-wave1-g1-packet-2026-09-04.md`; accepted local Postgres rehearsal/concurrency state supplied to ORCH-CERT for this run | None for this run | It no longer blocks `G3`; ORCH-CERT was instructed not to invent new PG evidence paths in Wave 4 | `G3`, `FINAL-AUDIT-001` |
| `BLK-PILOT-001` | `RESOLVED UNDER LOCAL-ONLY SCOPE WAIVER` | `ORCH-INFRA`; Product human + Infra human decision owners | `docs/audits/multi-orch/orch-infra-wave1-g1-packet-2026-09-04.md`; `docs/audits/multi-orch-product-wave1-dec-d002-precedence-2026-09-04.md`; `docs/audits/multi-orch/evidence/pilot/PILOT-DEPLOY-001-2026-09-04.md`; `docs/audits/multi-orch/evidence/pilot/ROLLBACK-LIVE-001-2026-09-04.md`; `docs/audits/multi-orch/evidence/pilot/PILOT-DEPLOY-001-local-only-2026-09-04.md`; `docs/audits/multi-orch/evidence/pilot/ROLLBACK-LIVE-001-local-only-2026-09-04.md` | None after explicit Wave 4 decision `LOCAL_ONLY_PILOT_EVIDENCE: yes` | It no longer blocks `G3` for this plan. The accepted evidence remains explicitly local-only and is **not** remote staging proof. | `G3`, `FINAL-AUDIT-001` |
| `BLK-T4-001` | `RESOLVED FOR THIS RUN` | `ORCH-INFRA` + `ORCH-QA`; decision owners Infra human + QA human; Security reviewer | `docs/audits/multi-orch/orch-infra-wave1-g1-packet-2026-09-04.md`; `docs/audits/multi-orch/orch-qa-wave1-packet-2026-09-04.md`; `docs/audits/multi-orch/evidence/AUTH-SETUP-001-2026-09-04.md`; `docs/audits/multi-orch/evidence/T4-LIVE-001-2026-09-04.md`; accepted T4 state supplied to ORCH-CERT for this run | None for this run | It no longer blocks `G3`; the evidence package is accepted as scoped, mixed live/hybrid proof for this run | `G3`, `FINAL-AUDIT-001` |
| `BLK-SEC-001` | `RESOLVED FOR THIS RUN` | `ORCH-SECURITY`; Security human + Product human decision owners | `docs/audits/multi-orch-adr21-wave1-decision-packet-2026-09-04.md`; `docs/audits/multi-orch/orch-root-wave2-execution-report-2026-09-04.md`; accepted independent re-review state supplied to ORCH-CERT for this run | None for this run | It no longer blocks `G3`; ADR21 remediation is treated as accepted for this certification run | `G3`, `FINAL-AUDIT-001` |
| `BLK-PROD-002` | `RESOLVED FOR THIS RUN` | `ORCH-PRODUCT`; Product human decision owner; Security human reviewer | `docs/audits/multi-orch-product-wave1-dec-d002-precedence-2026-09-04.md`; `docs/audits/multi-orch/orch-root-wave2-execution-report-2026-09-04.md`; accepted independent re-review state supplied to ORCH-CERT for this run | None for this run | It no longer blocks `G3`; D-002 remediation is treated as accepted for this certification run | `G3`, `FINAL-AUDIT-001` |

## Readiness notes by blocker

### `BLK-PG-001`

- ORCH-CERT was instructed to treat local Postgres rehearsal/concurrency evidence
  as already accepted for this run.
- No new Postgres artifact paths are fabricated here. The blocker closes on the
  authoritative accepted state supplied to Wave 4.
- Missing repo-side evidence packaging remains a traceability gap only.

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
- A second, explicitly local-only rehearsal was attempted under compose project
  `wave3pilotlocal` using `docker-compose.yml`,
  `docker-compose.staging.yml`, and the documented
  `docker-compose.tier-workers.yml` overlay plus generated local-only image and
  port overrides.
- Docker cleanup reclaimed approximately `20.10GB` and moved root free space
  from roughly `741M` to roughly `20G`, allowing the fallback local rehearsal
  to proceed.
- The local env file validated, `6da855b` remained an acceptable rollback
  anchor, and both current (`85fa8f5`) and rollback (`6da855b`) image sets were
  built locally.
- The local-only rehearsal then succeeded end to end: current RC `/health` and
  `/ready` passed, `alembic current` stayed at
  `066_privileged_idempotency_records (head)`, verified staff sync and async
  enrich both completed, rollback to `6da855b` completed with the same checks,
  and re-deploy back to `85fa8f5` completed with the same checks.
- Local-only evidence is therefore no longer blocked by machine capacity.
- This blocker is now closed **for this plan** because the explicit Wave 4 user
  decision accepts the local-only pilot/rollback rehearsal as the terminal
  substitute for the missing remote non-production target.
- Remote host provenance is still absent. That remains a release-certification
  concern and is not silently rewritten into "remote staging passed."
- Monitoring-backed expansion evidence remains unavailable unless Infra provides it later.

### `BLK-T4-001`

- QA has a full execution matrix and evidence handling rules.
- Infra has a concrete environment packet.
- The non-production-only setup path has been hardened in code.
- Live non-production backend handoff, separate `AUTH-SETUP-001` setup evidence, and scoped `T4-LIVE-001` execution evidence are now captured in the committed evidence folder.
- The evidence package is pinned to executed revision `b75883cbdce230b59abc8b59fae587d51db07a96`.
- Hybrid `/api/auth/me` and `/api/auth/login` cases are now called out explicitly as regression-only support rather than full live-actor proof.
- D002 / ADR21 bookkeeping rows were restored for traceability and are not over-claimed as separately executed live cases.
- The Wave 4 authoritative state treats the T4 evidence package as accepted for
  this run, so the blocker is no longer open in the blocker register.

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
- The Wave 4 authoritative state treats the independent re-review as accepted for
  this run, so the blocker is no longer open in the blocker register.

### `BLK-PROD-002`

- Product packet recommends a permission-centric precedence model.
- Core FE helper logic now follows that model.
- Follow-up changes completed the remaining reviewed desk-route and backend staff-surface
  permission hardening.
- A second re-review found one stale D-002 artifact: `frontend/e2e/desk-personas.spec.ts`
  still encoded owner-only access. This second follow-up updates it to the approved
  permission-centric matrix.
- The Wave 4 authoritative state treats the independent re-review as accepted for
  this run, so the blocker is no longer open in the blocker register.

## Post-certification refresh notes

The prior two ORCH-CERT release blockers are now closed on the release branch target:

1. `37e9008` commits the compose env passthrough required by the accepted
   local-only pilot topology into `backend/docker/docker-compose.yml`.
2. `37e9008` removes the duplicate `async redirects()` definition from
   `frontend/next.config.js`, restoring `/app/enrich -> /osint` and
   `/app/signals -> /desk/signals`.

Remaining notes after the refresh:

- local checked-out `HEAD` is still `7106dcce0b1c06cbd963ea8478c7fa5b86764d48`,
  which is behind `origin/product-doors/baseline` by 5 commits
- independent re-review [Re-review final blockers](e960981c-a4aa-46c0-9dca-ce3a5b876011)
  returned `PASS-WITH-NOTES` and confirms both prior release blockers are closed
- GitHub commit metadata for `37e9008` still showed combined status `pending`
  and no completed check runs/status contexts at refresh time

## ORCH-ROOT conclusion

The original blocker picture remains closed for this plan, including the explicit
local-only pilot waiver. The post-certification code defects are also closed on
the release branch target. The only remaining release note is the external
GitHub completion signal for `37e9008`.
