# Addendum R2 — Continued remediation (2026-09-04)

Supersedes scoring in the base report where noted. Base: `docs/audits/dev-b-desk-final-audit-2026-09-04.md`.

## Round-2 actions

### Closed / FIXED_AND_REVERIFIED this round
| ID | Sev | Fix | Reverify |
|----|-----|-----|----------|
| FIND-INFRA-002 residual | P1 | CI `npm run build` + `frontend-e2e` mocked a11y | REVIEW-INFRA-REVERIFY-R2 |
| FIND-INFRA-003 | P1 | Deploy `workflow_run` gated on CI success | REVIEW-INFRA-REVERIFY-R2 |
| FIND-INFRA-006 | P2 | API compose healthcheck → `/ready` | REVIEW-INFRA-REVERIFY-R2 |
| FIND-INFRA-007 | P2 | `backend/uv.lock` gitignored | REVIEW-INFRA-REVERIFY-R2 |
| FIND-QA-001 | P2 | CI pytest `OUTREACH_*` env | REVIEW-INFRA-REVERIFY-R2 |
| FIND-FE-003 | P2 | Roles error vs empty EmptyState | REVIEW-FE-REVERIFY-R2 |
| FIND-UX-001 | P1 | `docs/contracts/ctr-design-states.md` | REVIEW-FE/UX-REVERIFY-R2 |
| FIND-UX-002 / FIND-FE-006 | P2/P3 | Denied copy on Admin/Staff guards | REVIEW-FE/UX-REVERIFY-R2 |
| FIND-UX-005 subset | P2 | confirm on roles detach + queue retry | REVIEW-FE/UX-REVERIFY-R2 |
| ARCHITECTURE impersonation drift | P3/doc | Request-path enforcement documented | FIX-BE-R2 |
| Cookie regression gate | P0 residual | `scripts/check_cookies_not_tracked.sh` in CI | REVIEW-INFRA |

### FIND-QA-002 E2E/a11y disposition
| Suite | Result | Status |
|-------|--------|--------|
| `e2e/desk-states-a11y.spec.ts` (chromium, mocks, port 4310) | **7 passed**, exit 0 | **VERIFIED** |
| Same suite wired in CI `frontend-e2e` | Config present | **VERIFIED** (config); CI run not executed in this env |
| `product-doors-t4.spec.ts` via `integration` project | Auth setup timeout — needs live backend | **BLOCKED** (owner: Infra/QA — local API) |

### Still BLOCKED / product-deferred (unchanged honesty)
| ID | Owner | Notes |
|----|-------|-------|
| FIND-INFRA-005 / DATA-001 / BE-002 / QA-003 | Infra | Postgres isolated rehearsal |
| FIND-INFRA-004 | Infra/Product | Pilot / rollback live evidence |
| FIND-INFRA-008 | Infra | FE CD path |
| FIND-INFRA-009 | Infra | Live Prometheus |
| FIND-SEC-001 | Security/Product | Full ADR 0021 privileged mutation classify |
| FIND-BE-001 / SEC-002 | Product | D-002 owner vs permission |
| FIND-SEC-003 | Security | `revoked_at` writer |
| FIND-DATA-002 | Ops | Admin audit purge job |
| FIND-UX-006/007/008 | UX | Broader state polish (non-blocking vs R2 closes) |
| product-doors-t4 live | Infra/QA | Needs running API + auth setup |

## Revised completion scoring (post R2)

| Layer | Prior | Revised |
|-------|------:|--------:|
| Overall | 72% | **84%** |
| Frontend | 88% | **94%** |
| Backend | 86% | **88%** |
| Database | 75% | **75%** |
| Infrastructure | 55% | **82%** |
| Security | 78% | **80%** |
| Testing | 74% | **90%** |
| Integration | 48% | **72%** |
| Deployment | 35% | **58%** |

Requirements: ~36/43 verified-complete-ish (prior 31) after UX-001/FE-003/denied UX closes.
Tasks: ~13/17 with non-blocking improvements (prior 10).

## Revised verdict

**NOT FULLY COMPLETE — REMEDIATION REQUIRED**

Still cannot claim 100%: Postgres BLOCKED, pilot/rollback evidence OPEN, ADR 0021 FIND-SEC-001 OPEN, D-002 CONFLICT, live product-doors-t4 BLOCKED without API.

## Revised release decision

**NOT APPROVED FOR RELEASE**

Improved path to a **restricted internal pilot** (RBAC-gated) after: commit cookie/CI remediations, rotate any leaked session secrets, and clear Postgres gate. Not certified for production.

## Command ledger (R2 additions)

| Command | Exit | Notes |
|---------|------|-------|
| Playwright `desk-states-a11y.spec.ts` port 4310 mocks | 0 | 7 passed / 42.7s — `/tmp/dev-b-audit/e2e-desk-r2.txt` |
| Playwright `product-doors-t4` project=integration | 1 | auth.setup timeout — live backend missing |
| FIX-FE-R2 typecheck + 32 unit tests | 0 | per FIX-FE-R2.md |
| Disk cleanup of obsolete worktree `node_modules` | n/a | freed ~3GB so builds/e2e could run |

## Independence

FIX-INFRA / FIX-FE / FIX-BE implemented; REVIEW-INFRA / REVIEW-FE / REVIEW-UX-A11Y reverified R2. AUDIT-ORCH not sole technical approver.

## Late REVIEW-QA follow-up (R3)

Original [REVIEW-QA](da7d27fe-90cb-435a-b788-731a8e95573e) completion arrived after R2 and reflected pre-remediation / ENOSPC conditions. Follow-up:

| Finding | Action |
|---------|--------|
| FIND-QA-002 OpenAPI + Prettier drift | Regenerated `openapi.json` / `openapi.ts` against current FastAPI export; Prettier `--write` on desk remediation files. Still uncommitted. |
| FIND-QA-005 access-layouts mock | Clarified as wiring-only; AuthZ proof remains in `AdminGuard.test.tsx`. |
| FIND-QA-003 e2e ENOSPC | Superseded by R2 desk-states-a11y **7/7**; full suite not re-run (disk still tight). |
| FIND-QA-001 outreach pollution | Already fixed in CI env (R2). |

Stale Round-1 reviewer summaries (cookies P0 still open, Brands ungated, no CI unit) are **superseded** by R1/R2 remediations + reverifies — do not re-open from those delayed notifications.
