# `T4-LIVE-001` Execution Evidence Template

Status: `EVIDENCE NOT STARTED`
Execution state: `PREPARED ONLY`

## Run metadata

- Date:
- Operator:
- Environment name:
- API revision / image / branch:
- Frontend revision / branch:
- Backend URL:
- Frontend URL / port:
- `AUTH-SETUP-001` evidence reference:
- Playwright command:

## Dependency checklist

- [ ] `AUTH-SETUP-001` completed
- [ ] Live API/backend path confirmed
- [ ] DB + Redis healthy for login, MFA, impersonation, and Desk pages
- [ ] Playwright report output path recorded
- [ ] No cookie/auth secrets included in committed evidence
- [ ] D002 / ADR21 placeholders either executed from approved addenda or still recorded as `WAITING FOR OWNER DECISION`

## Case ledger

| Case ID | Result | Notes | Evidence |
|---|---|---|---|
| `T4-DOORS-001` | `NOT STARTED` | | |
| `T4-DOORS-002` | `NOT STARTED` | | |
| `T4-DOORS-003` | `NOT STARTED` | | |
| `T4-DOORS-004` | `NOT STARTED` | | |
| `T4-DOORS-005` | `NOT STARTED` | | |
| `T4-DOORS-006` | `NOT STARTED` | | |
| `T4-DOORS-007` | `NOT STARTED` | | |
| `T4-DOORS-008` | `NOT STARTED` | | |
| `T4-D002-001` | `WAITING FOR OWNER DECISION` | Placeholder until `DEC-D002-PRECEDENCE` | |
| `T4-D002-002` | `WAITING FOR OWNER DECISION` | Placeholder until `DEC-D002-PRECEDENCE` | |
| `T4-ADR21-001` | `WAITING FOR OWNER DECISION` | Placeholder until `DEC-ADR21-SURFACE` | |
| `T4-ADR21-002` | `WAITING FOR OWNER DECISION` | Placeholder until `DEC-ADR21-SURFACE` | |

## Evidence to attach

- Playwright HTML or line reporter output
- Per-case URL/assertion summary
- Screenshots for `T4-DOORS-007`
- Sanitized API metadata for MFA/impersonation lifecycle
- Blocker note if any prerequisite prevented execution

## Blocker handling

If setup or environment readiness fails:

- mark the affected case `BLOCKED`
- record the unmet dependency precisely
- do not convert the run into a partial pass

## Outcome

- Final status:
- Blocking issue, if any:
- Ready for ORCH-CERT review:
