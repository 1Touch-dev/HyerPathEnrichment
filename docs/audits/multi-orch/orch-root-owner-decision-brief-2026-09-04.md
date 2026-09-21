# ORCH-ROOT Owner Decision Brief

- Date: 2026-09-04
- Purpose: concise receiving brief for the human decision owner(s)
- Important: no approval is recorded in this document

## What needs an explicit owner response now

The program is not waiting on more packet writing. It is waiting on explicit owner
decisions. If you are acting in one or more of the roles below, these are the exact
questions now in front of you.

## Decision checklist

### `DEC-COMMIT-AUTH`

- Owner: human release owner
- Review first:
  - `docs/audits/multi-orch/orch-root-wave1-g1-readiness-brief-2026-09-04.md`
  - `/home/axiz/.cursor/plans/multi-orch_blocker_resolution_e17125d7.plan.md`
- Recommended option: authorize the already-planned atomic Round 2 commit groups only;
  do not expand scope.
- If approved, this unlocks: `R2-COMMIT-EXEC-001`
- If deferred, this stays blocked: immutable RC creation and all later live-evidence work

### `DEC-D002-PRECEDENCE`

- Owner: Product human
- Required reviewer: Security human
- Review first:
  - `docs/audits/multi-orch-product-wave1-dec-d002-precedence-2026-09-04.md`
- Recommended option: permission-centric precedence; role name alone is never enough;
  FE visibility must align to backend permissions; Brand is not an ACL or tenant boundary.
- If approved, this unlocks: `D002-IMPL-001`, `D002-TEST-001` through `D002-TEST-005`
- If deferred, this stays blocked: FE/BE authz alignment work and closure of `BLK-PROD-002`

### `DEC-ADR21-SURFACE`

- Owners: Security human + Product human
- Review first:
  - `docs/audits/multi-orch-adr21-wave1-decision-packet-2026-09-04.md`
- Recommended option: approve the full privileged-operation catalog with fail-closed
  treatment for unmapped operations; keep `P4`, queue retry, and feature-flag mutations
  unavailable in this wave.
- If approved, this unlocks: `ADR21-IMPL-001`, `ADR21-TEST-001` through `ADR21-TEST-008`
- If deferred, this stays blocked: closure of `BLK-SEC-001` and all privileged-surface implementation

### `DEC-T4-SETUP`

- Owners: Infra human + QA human
- Required reviewer: Security human
- Review first:
  - `docs/audits/multi-orch/orch-infra-wave1-g1-packet-2026-09-04.md`
  - `docs/audits/multi-orch/orch-qa-wave1-packet-2026-09-04.md`
- Recommended option: non-production-only reuse of the existing setup script plus real
  HTTP login, with hard fail-closed production checks and explicit handling if a
  superuser fixture is needed.
- If approved, this unlocks: `AUTH-SETUP-001`, `T4-LIVE-001`
- If deferred, this stays blocked: all live T4 evidence and the QA share of Wave 3

### `DEC-PILOT-ACCEPT`

- Owners: Product human + Infra human
- Review first:
  - `docs/audits/multi-orch-product-wave1-dec-d002-precedence-2026-09-04.md`
  - `docs/audits/multi-orch/orch-infra-wave1-g1-packet-2026-09-04.md`
- Recommended option: restricted internal pilot only, RBAC-based cohort control, with
  known v1 limitations and observability status stated honestly.
- If approved, this unlocks: `PILOT-DEPLOY-001`
- If deferred, this stays blocked: live pilot evidence for `BLK-PILOT-001`

### `DEC-ROLLBACK-ACCEPT`

- Owners: Infra human + Product human
- Review first:
  - `docs/audits/multi-orch/orch-infra-wave1-g1-packet-2026-09-04.md`
  - `/home/axiz/.cursor/plans/multi-orch_blocker_resolution_e17125d7.plan.md`
- Recommended option: approve rollback only under ADR 0021 schema guardrails; never
  run a pre-hardening API against schema `065+`; use restore/roll-forward if incompatible.
- If approved, this unlocks: `ROLLBACK-LIVE-001`
- If deferred, this stays blocked: live rollback evidence for `BLK-PILOT-001`

## Short ruling for the decision owner

Nothing in `wave2-impl` should start yet. The next useful action is not more analysis;
it is explicit approval, rejection, or requested edits on the six decisions above.

## Suggested reply format

Use exact status language if helpful:

```text
DEC-COMMIT-AUTH: APPROVE | REJECT | NEEDS EDITS
DEC-D002-PRECEDENCE: APPROVE | REJECT | NEEDS EDITS
DEC-ADR21-SURFACE: APPROVE | REJECT | NEEDS EDITS
DEC-T4-SETUP: APPROVE | REJECT | NEEDS EDITS
DEC-PILOT-ACCEPT: APPROVE | REJECT | NEEDS EDITS
DEC-ROLLBACK-ACCEPT: APPROVE | REJECT | NEEDS EDITS
```
