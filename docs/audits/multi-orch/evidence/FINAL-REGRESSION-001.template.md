# `FINAL-REGRESSION-001` Execution Evidence Template

Status: `EVIDENCE NOT STARTED`
Execution state: `PREPARED ONLY`

## Run metadata

- Date:
- Operator:
- Release candidate revision / image:
- Environment(s):
- Related evidence:
  - `AUTH-SETUP-001`:
  - `T4-LIVE-001`:
  - `PG-REHEARSAL-001`:
  - `PG-CONCURRENCY-001`:

## Gate checklist

- [ ] `G2` reached
- [ ] Release candidate pinned
- [ ] `AUTH-SETUP-001` completed
- [ ] `T4-LIVE-001` completed
- [ ] Postgres evidence attached
- [ ] Product and Security decision addenda attached or marked `WAITING FOR OWNER DECISION`

## Case ledger

| Case ID | Result | Notes | Evidence |
|---|---|---|---|
| `FINAL-REG-001` | `NOT STARTED` | | |
| `FINAL-REG-002` | `NOT STARTED` | | |
| `FINAL-REG-003` | `NOT STARTED` | | |
| `FINAL-REG-004` | `NOT STARTED` | | |
| `FINAL-REG-005` | `NOT STARTED` | Supporting evidence only; not a live-T4 substitute | |
| `FINAL-REG-006` | `NOT STARTED` | | |
| `FINAL-REG-007` | `NOT STARTED` | | |
| `FINAL-REG-008` | `NOT STARTED` | | |
| `FINAL-REG-009` | `NOT STARTED` | | |
| `FINAL-REG-010` | `NOT STARTED` | | |
| `FINAL-REG-011` | `NOT STARTED` | | |
| `FINAL-REG-012` | `NOT STARTED` | | |
| `FINAL-REG-013` | `NOT STARTED` | Depends on ORCH-INFRA evidence | |
| `FINAL-REG-014` | `NOT STARTED` | | |
| `FINAL-REG-015` | `NOT STARTED` | | |
| `FINAL-REG-016` | `WAITING FOR OWNER DECISION` | Placeholder until `DEC-D002-PRECEDENCE` | |
| `FINAL-REG-017` | `WAITING FOR OWNER DECISION` | Placeholder until `DEC-ADR21-SURFACE` | |
| `FINAL-REG-018` | `NOT STARTED` | | |

## Evidence to attach

- Command logs for frontend checks and backend pytest
- Playwright reports for connectivity, T4 live, and admin live
- Cookie safety script output
- ADR verification output
- Decision addenda for D002 and ADR 0021 when available
- Postgres rehearsal/concurrency reports

## Failure policy

- Any release-blocking failure keeps the final result below release approval.
- Missing live-environment evidence is `WAITING FOR ENVIRONMENT` or
  `CANNOT CERTIFY`, not `PASS`.
- Missing Product/Security decision outcomes keep placeholder cases
  `WAITING FOR OWNER DECISION`.

## Outcome

- Final regression status:
- Blocking issues:
- Ready for `FINAL-AUDIT-001`:
