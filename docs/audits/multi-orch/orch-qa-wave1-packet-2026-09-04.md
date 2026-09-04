# ORCH-QA Wave 1 Packet (2026-09-04)

Status: `READY FOR REVIEW`
Execution state: `PREPARED ONLY`
Live-evidence state: `PARTIAL`
Baseline carried forward: `G0` passed on `R2-BASELINE-2026-09-04`

## Scope for this run

This packet covers the QA-owned Wave 1 preparation slice for:

- `BLK-T4-001`
- `AUTH-SETUP-001`
- `T4-LIVE-001`
- `FINAL-REGRESSION-001`

It does **not** mark any live test as passed. Where execution requires a live API,
database, Redis, or owner decision, the status remains `WAITING FOR ENVIRONMENT`
or `WAITING FOR OWNER DECISION`.

## Baseline context carried forward

- `G0` already passed on baseline `R2-BASELINE-2026-09-04`.
- Current live blocker: `frontend/e2e/integration/auth.setup.ts` and
  `frontend/e2e/integration/product-doors-t4.spec.ts` require a running API/backend path.
- Prior audits blocked on `auth.setup` timing out while polling `GET /health`.
- Mocked desk accessibility evidence exists (`desk-states-a11y`) but is **not** a substitute
  for live T4 evidence.
- Future `D002` and ADR 0021 decisions will expand the regression pack. Those cases are
  prepared here as placeholders and stay `WAITING FOR OWNER DECISION`.

## Readiness summary

| Item | Owner | Current status | Packet status | Notes |
|---|---|---|---|---|
| `DEC-T4-SETUP` | Infra + QA, Security reviewer | `WAITING FOR OWNER DECISION` | `READY FOR REVIEW` | No live execution until an approved non-prod setup path is chosen. |
| `T4-ENV-001` | ORCH-INFRA | `WAITING FOR ENVIRONMENT` | `READY FOR REVIEW` | Needs reachable API, DB, Redis, frontend dev server, env manifest, and cleanup owner. |
| `AUTH-SETUP-001` | ORCH-QA | `WAITING FOR OWNER DECISION` | `PARTIAL` | Matrix and evidence template ready; execution blocked on `DEC-T4-SETUP`. |
| `T4-LIVE-001` | ORCH-QA | `WAITING FOR ENVIRONMENT` | `PARTIAL` | Exact matrix ready; no live pass claimed. |
| `FINAL-REGRESSION-001` | ORCH-QA / ORCH-CERT | `READY AFTER GATE` | `PARTIAL` | Matrix and evidence template ready; execution depends on `G2` live inputs plus decision outcomes. |
| `D002` placeholder cases | ORCH-PRODUCT + ORCH-QA | `WAITING FOR OWNER DECISION` | `READY FOR REVIEW` | Expand after `DEC-D002-PRECEDENCE`. |
| `ADR21` placeholder cases | ORCH-SECURITY + ORCH-QA | `WAITING FOR OWNER DECISION` | `READY FOR REVIEW` | Expand after `DEC-ADR21-SURFACE`. |
| ORCH-QA Wave 1 handoff | ORCH-QA -> ORCH-ROOT / ORCH-INFRA / ORCH-CERT | `READY FOR REVIEW` | `READY FOR REVIEW` | G1 cannot close until env + decisions are approved. |

## `DEC-T4-SETUP` approved-options-needed summary

### Option A — Reuse existing script + live API login

Mechanism:

- Keep the existing `backend/scripts/create_test_user.py` write-direct fixture flow.
- Keep HTTP login in Playwright so the suite still obtains real auth cookies through
  `/api/auth/login`.
- Restrict the mechanism to non-production environments only.

Assessment:

- Recommended for lowest code churn and direct reuse of the current test harness.
- Requires explicit sign-off because the current `auth.setup.ts` path seeds a
  `--is-superuser` fixture user. If owners want least privilege, this option needs either
  an approved exception for a non-prod superuser fixture or a follow-up narrowing of the
  seeded role before `T4-LIVE-001` execution.

### Option B — Compose/test-profile seed command

Mechanism:

- Add a compose-only or test-profile-only seed step that creates the required users before
  Playwright begins.
- Playwright still logs in over HTTP using those seeded credentials.

Assessment:

- Acceptable if Infra already owns the test profile and teardown path.
- Lower risk of ad hoc writes from the frontend runner, but still must stay non-prod only.

### Option C — Internal fixture service

Mechanism:

- Expose a fixture-only endpoint or service inside a test profile that creates the required
  users and states.

Assessment:

- Only acceptable if it is unreachable from production traffic, disabled by default, and
  reviewed by Security.
- Higher implementation complexity than Option A or B.

### Option D — Controlled admin setup operation

Mechanism:

- Use an authenticated admin-only operation to create test actors through the API.

Assessment:

- Only acceptable if it requires existing admin auth, MFA, explicit allowlisting, audit,
  and non-prod hard stops.
- Highest operational overhead; use only if direct script/profile seeding is unavailable.

### Rejected option

- Any unrestricted production-capable setup route, public helper endpoint, or permanent
  auth backdoor is rejected.

### Mandatory security constraints for any approved option

1. Hard-fail when the environment is production or production-like. No override-by-flag.
2. No public unauthenticated setup endpoint.
3. No production-capable auth backdoor, even if hidden behind a query param or secret path.
4. No persistent elevated privileges beyond the test window; teardown owner must be named.
5. No raw passwords, auth cookies, refresh tokens, invite tokens, or seeded secret values in
   committed evidence.
6. Evidence may record fixture labels, exit codes, timestamps, and sanitized role assertions,
   but not cookie-jar contents or credential material.
7. If a superuser fixture is used, the approval packet must state that explicitly and justify
   why lower privilege is insufficient for the covered live cases.
8. Failure to reach `/health`, seed the user, or obtain cookies is `BLOCKED`, never `PASS`.

## Execution prerequisites

### From Infra (`T4-ENV-001`)

1. Reachable backend URL for Playwright, defaulting to `BACKEND_API_URL=http://localhost:8000`,
   with `GET /health` returning `200`.
2. Frontend dev server reachable on the configured `PLAYWRIGHT_PORT`.
3. Database connectivity for the approved setup mechanism so fixture creation can commit a
   verified user row.
4. Redis and database healthy enough for:
   - `/api/auth/login`
   - `/api/admin/mfa/*`
   - `/api/admin/impersonation/*`
   - `/desk/system-health`
5. Python 3 plus backend dependencies installed for:
   - `backend/scripts/create_test_user.py`
   - the MFA TOTP helper invoked by `product-doors-t4.spec.ts`
6. Named non-prod environment owner and cleanup owner.
7. Storage-state files under `frontend/e2e/integration/.auth/` remain untracked and excluded
   from commit scope.
8. If the live stack uses Compose/Postgres, Infra must also provide:
   - `POSTGRES_PASSWORD`
   - `TEST_DATABASE_URL` when Postgres-marked cases are executed
   - the exact API revision / image / compose overlay used for the run
9. Confirm disk headroom before execution because prior audit rounds hit `ENOSPC` during E2E.

### From Product (`DEC-D002-PRECEDENCE`)

1. Final owner-vs-permission precedence decision.
2. Explicit allow/deny expectations for:
   - owner + permission
   - owner - permission
   - non-owner + permission
   - owner + explicit deny
   - no-owner no-permission
   - mid-session revoke/change
   - impersonation mode interactions
3. Final FE nav and route-guard expectations for empty-permission staff users.

### From Security + Product (`DEC-ADR21-SURFACE`)

1. Approved privileged-mutation surface inventory.
2. P0-P4 classification for each in-scope Desk mutation.
3. Confirmation that unclassified operations fail closed.
4. Confirmation that P4 stays unavailable unless ADR guidance changes.
5. Expected negative cases for MFA, impersonation, idempotency, and audit evidence.

## Exact test matrix

All cases below are prepared from current code and plan scope. A case is not executed until its
evidence artifact is populated.

### `AUTH-SETUP-001` matrix

| ID | Role / actor | Polarity | Exact case | Evidence artifacts | Release-blocking | Current status |
|---|---|---|---|---|---|---|
| `T4-AUTH-001` | Infra-provided live stack | Positive | `auth.setup.ts` reaches `GET /health` within timeout and records the backend URL used for the run. | `docs/audits/multi-orch/evidence/AUTH-SETUP-001.template.md`, redacted terminal log, env manifest | Yes | `WAITING FOR ENVIRONMENT` |
| `T4-AUTH-002` | Approved non-prod regular test actor (current source path seeds superuser) | Positive | Approved setup mechanism creates or reuses a verified user fixture without manual DB edits during the run. | setup command record, sanitized fixture metadata, actor-role assertion | Yes | `WAITING FOR OWNER DECISION` |
| `T4-AUTH-003` | Same actor as `T4-AUTH-002` | Positive | Real HTTP login through `/api/auth/login` succeeds and writes storage state for Playwright. | login response metadata, storage-state existence attestation (no cookie contents), timestamped file path | Yes | `WAITING FOR OWNER DECISION` |
| `T4-AUTH-004` | Production or production-like target | Negative | Setup mechanism hard-fails in production and records the deny reason. | denial evidence, environment classification record | Yes | `WAITING FOR OWNER DECISION` |
| `T4-AUTH-005` | Unhealthy backend target | Negative | Setup fails closed when `/health` never returns `200`; run is recorded as `BLOCKED`, not retried into a false pass. | timeout log, blocker note, backend URL | Yes | `WAITING FOR ENVIRONMENT` |
| `T4-AUTH-006` | Same actor as `T4-AUTH-002` | Negative | Login failure, missing cookies, or corrupt storage state is recorded as a setup failure that blocks `T4-LIVE-001`. | redacted login failure log, storage-state validation note | Yes | `WAITING FOR OWNER DECISION` |
| `T4-AUTH-007` | Cleanup owner | Negative / safety | Test identities and local auth state are torn down or explicitly retained with owner approval after the run. | cleanup log or retention waiver, local-only deletion note | Yes | `WAITING FOR ENVIRONMENT` |

### `T4-LIVE-001` matrix

| ID | Role / actor | Polarity | Exact case | Evidence artifacts | Release-blocking | Current status |
|---|---|---|---|---|---|---|
| `T4-DOORS-001` | Anonymous browser request path | Positive | Compatibility redirects preserve path params and query strings for `/app/enrich`, `/app/signals`, `/app/admin`, and `/app/admin/users/:id`. | Playwright report, redirect assertion log | Yes | `WAITING FOR ENVIRONMENT` |
| `T4-DOORS-002` | Direct candidate-route request path | Positive | `/app/jobs`, `/app/history`, `/app/jobs/:id`, `/app/dashboard`, and `/app/health` remain direct pages and do not redirect to Desk or OSINT. | Playwright report, route response capture | Yes | `WAITING FOR ENVIRONMENT` |
| `T4-DOORS-003` | Candidate, recruiter, support, admin, team_owner, superuser, custom_staff | Positive and negative | Role homes and direct-route guards choose the correct door: candidate -> `/app`, recruiter -> `/desk/sourcing-leads`, support -> `/desk/users`, owner/superuser -> `/desk`, custom staff fallback -> `/osint`, recruiter denied `/desk/roles`. | Playwright report, per-role URL assertions | Yes | `WAITING FOR ENVIRONMENT` |
| `T4-DOORS-004` | Recruiter login flow | Positive | Unauthenticated OSINT deep link preserves `tiers` query through login and returns to the original OSINT page after auth. | Playwright trace, redirected URL assertions | Yes | `WAITING FOR ENVIRONMENT` |
| `T4-DOORS-005` | Approved live admin actor | Positive | Every `/desk/*` route listed in `product-doors-t4.spec.ts` renders without `404` or guard leakage, and `/desk/users/:id` resolves from a live API user list. | Playwright report, page screenshots as needed, `/api/admin/users` metadata | Yes | `WAITING FOR ENVIRONMENT` |
| `T4-DOORS-006` | Approved live admin actor + live candidate target | Positive | MFA enroll -> confirm -> status -> impersonation start -> status -> end -> disable completes successfully with the live backend. | Playwright report, sanitized API response metadata, timestamps | Yes | `WAITING FOR ENVIRONMENT` |
| `T4-DOORS-007` | Candidate, recruiter, superuser | Positive | Responsive AppShell product chips show `Candidate`, `Desk`, and `OSINT` at the expected routes and viewports. | screenshot bundle, Playwright report | Supporting only | `WAITING FOR ENVIRONMENT` |
| `T4-DOORS-008` | Unapproved or missing live setup | Negative | If `AUTH-SETUP-001` is incomplete, the suite is blocked and records the exact unmet prerequisite instead of partial-passing around it. | blocker note in `T4-LIVE-001` report, dependency checklist | Yes | `WAITING FOR OWNER DECISION` |
| `T4-D002-001` | Placeholder: roles/permissions from `DEC-D002-PRECEDENCE` | Positive | Execute approved owner + permission allow cases against the live product-door routes and nav once Product decides precedence. | decision addendum, live assertions, screenshots if needed | Yes | `WAITING FOR OWNER DECISION` |
| `T4-D002-002` | Placeholder: roles/permissions from `DEC-D002-PRECEDENCE` | Negative | Execute approved owner-without-permission, non-owner-with-permission, revoke, and impersonation-deny cases once Product decides precedence. | decision addendum, denial assertions, route-guard evidence | Yes | `WAITING FOR OWNER DECISION` |
| `T4-ADR21-001` | Placeholder: classified privileged admin actor | Positive | Execute approved privileged-operation success paths that require MFA, idempotency, and exactly one explicit audit record. | decision addendum, API logs, audit proof | Yes | `WAITING FOR OWNER DECISION` |
| `T4-ADR21-002` | Placeholder: unclassified or under-controlled privileged action | Negative | Unclassified or under-controlled privileged operations fail closed once ADR 0021 scope is approved. | denial evidence, classifier expectation note | Yes | `WAITING FOR OWNER DECISION` |

### `FINAL-REGRESSION-001` matrix

| ID | Role / actor | Polarity | Exact case | Evidence artifacts | Release-blocking | Current status |
|---|---|---|---|---|---|---|
| `FINAL-REG-001` | Frontend toolchain | Positive | `npm run openapi:check` passes with no generated-contract drift. | command log, diff status | Yes | `READY AFTER GATE` |
| `FINAL-REG-002` | Frontend toolchain | Positive | `npm run format:check` and `npm run typecheck` pass. | command log | Yes | `READY AFTER GATE` |
| `FINAL-REG-003` | Frontend toolchain | Positive | `npm run test:unit` passes, including `AdminGuard`, `nav-config`, and `product-doors` coverage. | test report | Yes | `READY AFTER GATE` |
| `FINAL-REG-004` | Frontend toolchain | Positive | `npm run build` passes on the release candidate. | build log | Yes | `READY AFTER GATE` |
| `FINAL-REG-005` | Mocked frontend E2E | Positive | `desk-states-a11y` mocked suite remains green; use only as regression support, not live-T4 substitution. | Playwright report for mocked suite | Yes | `READY AFTER GATE` |
| `FINAL-REG-006` | Live backend + frontend | Positive | `connectivity.spec.ts` passes against the same live stack used for T4 evidence. | Playwright report, env manifest | Yes | `WAITING FOR ENVIRONMENT` |
| `FINAL-REG-007` | Live setup path | Positive | `AUTH-SETUP-001` is approved and executed with sanitized evidence. | completed `AUTH-SETUP-001` report | Yes | `WAITING FOR OWNER DECISION` |
| `FINAL-REG-008` | Live product-door actors | Positive | `T4-LIVE-001` passes on the pinned release candidate and references the executed auth-setup artifact. | completed `T4-LIVE-001` report | Yes | `WAITING FOR ENVIRONMENT` |
| `FINAL-REG-009` | Live admin actor | Positive | `frontend/e2e/integration/admin.spec.ts` passes on the same live stack. | Playwright report, env manifest | Yes | `WAITING FOR ENVIRONMENT` |
| `FINAL-REG-010` | Backend toolchain | Positive | `make test` or equivalent `pytest -m "not postgres"` backend regression passes with coverage gate intact. | pytest log, coverage summary | Yes | `READY AFTER GATE` |
| `FINAL-REG-011` | Backend security contracts | Positive | Focused privileged-security regression passes (`backend/tests/test_admin_privileged_security_contracts.py`). | pytest log | Yes | `READY AFTER GATE` |
| `FINAL-REG-012` | Backend staff-invite hardening | Positive | Focused staff-invite regression passes (`backend/tests/test_admin_be_003_staff_invite_hardening.py`). | pytest log | Yes | `READY AFTER GATE` |
| `FINAL-REG-013` | Postgres environment | Positive | Postgres-marked migration and concurrency evidence is attached from ORCH-INFRA before final certification. | `PG-REHEARSAL-001` and `PG-CONCURRENCY-001` reports | Yes | `WAITING FOR ENVIRONMENT` |
| `FINAL-REG-014` | CI safety gate | Positive | `scripts/check_cookies_not_tracked.sh` passes; no cookie jars or auth state files enter commit scope. | script log, tracked-file check | Yes | `READY AFTER GATE` |
| `FINAL-REG-015` | ADR verification | Positive | `python backend/scripts/verify_adrs.py --json` passes. | script output | Yes | `READY AFTER GATE` |
| `FINAL-REG-016` | Placeholder: Product-approved D002 actors | Positive and negative | Execute the approved D002 matrix in FE and API regression once Product finalizes the precedence decision. | D002 addendum, live/unit/api reports | Yes | `WAITING FOR OWNER DECISION` |
| `FINAL-REG-017` | Placeholder: Security/Product-approved ADR21 actors | Positive and negative | Execute the approved ADR 0021 privileged-operation matrix once the surface inventory and controls are approved. | ADR21 addendum, backend/live reports | Yes | `WAITING FOR OWNER DECISION` |
| `FINAL-REG-018` | Deploy workflow validation | Positive | Validate deploy workflow via `actionlint .github/workflows/deploy.yml` or approved dry-run proof path. | actionlint output or dry-run record | Yes | `READY AFTER GATE` |

## Evidence handling rules

1. Use the templates under `docs/audits/multi-orch/evidence/`.
2. Keep any raw auth state, cookie jars, passwords, invite tokens, or local `.auth/*.json` files
   out of version control and out of committed evidence.
3. Redact command output from `create_test_user.py` because its stdout includes the fixture
   password by design.
4. Distinguish:
   - `PREPARED ONLY`: matrix/template exists, not executed
   - `PARTIAL`: some non-secret supporting evidence exists, but no blocker-close evidence yet
   - `READY FOR REVIEW`: packet content is complete enough for owner/reviewer decision
   - `WAITING FOR ENVIRONMENT`: live stack missing
   - `WAITING FOR OWNER DECISION`: blocked on Product/Infra/Security sign-off

## G1 handoff

### Handoff to ORCH-ROOT

- ORCH-QA Wave 1 packet is `READY FOR REVIEW`.
- G1 is **not** satisfied from QA alone.
- Remaining G1 blockers outside this packet:
  - `DEC-T4-SETUP` approval
  - `T4-ENV-001` environment readiness from Infra
  - `DEC-D002-PRECEDENCE`
  - `DEC-ADR21-SURFACE`

### Handoff to ORCH-INFRA

- Provide the named non-prod environment, API revision, compose/env manifest, and cleanup owner.
- Confirm whether the approved T4 setup path is Option A, B, C, or D.
- If Option A reuses the current source path, explicitly confirm whether a non-prod superuser
  fixture is acceptable or whether privilege must be narrowed before execution.
- Return `T4-ENV-001` with enough detail for ORCH-QA to execute without improvising.

### Handoff to ORCH-CERT

- Do not certify from this packet alone.
- Treat all live T4 and auth-setup evidence as unexecuted until the execution templates are
  filled and attached to the pinned release candidate.
- Use `FINAL-REGRESSION-001` as the final QA evidence checklist once `G2` exists.
