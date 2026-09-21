# `AUTH-SETUP-001` Execution Evidence Template

Status: `EVIDENCE NOT STARTED`
Execution state: `PREPARED ONLY`

## Run metadata

- Date:
- Operator:
- Environment name:
- Environment classification:
- API revision / image / branch:
- Backend URL:
- Frontend URL / port:
- Approved `DEC-T4-SETUP` option:
- Security reviewer sign-off reference:

## Dependency checklist

- [ ] `DEC-T4-SETUP` approved
- [ ] Non-production environment confirmed
- [ ] `GET /health` returned `200`
- [ ] Approved setup mechanism available
- [ ] Cleanup owner named
- [ ] Cookie-jar files remain untracked

## Case ledger

| Case ID | Result | Notes | Evidence |
|---|---|---|---|
| `T4-AUTH-001` | `NOT STARTED` | | |
| `T4-AUTH-002` | `NOT STARTED` | | |
| `T4-AUTH-003` | `NOT STARTED` | | |
| `T4-AUTH-004` | `NOT STARTED` | | |
| `T4-AUTH-005` | `NOT STARTED` | | |
| `T4-AUTH-006` | `NOT STARTED` | | |
| `T4-AUTH-007` | `NOT STARTED` | | |

## Sanitized evidence to attach

- Redacted terminal log for backend health polling
- Redacted setup command log or seed-profile log
- Login response metadata only (status/timestamp, no secrets)
- Storage-state existence attestation only (file present + excluded from VCS)
- Cleanup record or approved retention waiver

## Redaction rules

Do not paste any of the following into this file:

- raw passwords
- auth cookies
- refresh/access tokens
- `.auth/*.json` contents
- raw stdout from `create_test_user.py`

If `create_test_user.py` is used, record only:

- exit code
- actor label/email
- actor privilege level
- timestamp

## Outcome

- Final status:
- Blocking issue, if any:
- Ready to unlock `T4-LIVE-001`:
