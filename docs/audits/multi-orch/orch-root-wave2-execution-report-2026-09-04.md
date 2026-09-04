# ORCH-ROOT Wave 2 Execution Report

- Date: 2026-09-04
- Coordinator: ORCH-ROOT
- Baseline: `R2-BASELINE-2026-09-04`
- Branch: `product-doors/baseline`
- Wave 2 implementation commit: `73e6c57`

## Approved decision basis

This run used the main-session approvals supplied directly to ORCH-ROOT for:

- `DEC-COMMIT-AUTH`
- `DEC-D002-PRECEDENCE`
- `DEC-ADR21-SURFACE`
- `DEC-T4-SETUP`
- `DEC-PILOT-ACCEPT`
- `DEC-ROLLBACK-ACCEPT`

Those approvals were treated as authoritative for this Wave 2 execution without
editing the plan file itself.

## Execution summary by task

### `D002-IMPL-001`

- Replaced owner-only Desk gating in shared frontend helpers with permission-based routing.
- Tightened `Roles`, `Feature flags`, and `Queues` Desk layouts to require explicit read permissions.
- Removed role-only write/delete shortcuts from Brands and impersonation affordance checks.
- Added focused frontend unit coverage for the revised permission model.

### `ADR21-IMPL-001`

- Added a central privileged-operation catalog and fail-closed helper module.
- Hardened a subset of privileged `P1` routes with `Idempotency-Key`, atomic audit-plus-mutation commits,
  and explicit unavailable handling for feature-flag and queue mutations.
- Added backend regression coverage for hardened brand and moderation surfaces plus the new setup guard.

### `AUTH-SETUP-001`

- Hardened `create_test_user.py` so it fails in staging/production-like environments.
- Required explicit `ALLOW_E2E_SUPERUSER_BOOTSTRAP=1` for superuser bootstrap usage.
- Updated the admin Playwright setup to opt into that exception explicitly instead of relying on an implicit backdoor.

### `R2-COMMIT-EXEC-001`

- Created the first scoped Wave 2 implementation commit: `73e6c57`.
- Remaining docs/generated-contract commits were left separate to match the planned commit-group shape.

## Regression evidence

- Backend targeted suite:
  `uv run --project backend pytest backend/tests/test_admin_brands_router.py backend/tests/test_brand_deactivation.py backend/tests/test_admin_documents_moderation.py backend/tests/test_admin_job_postings_moderation.py backend/tests/test_admin_outreach_moderation.py backend/tests/test_admin_manual_job_entries_moderation.py backend/tests/test_admin_feature_flags_read_only_d007.py backend/tests/test_admin_queue_hardening.py`
  -> `173 passed`
- Backend setup-guard suite:
  `uv run --project backend pytest backend/tests/test_create_test_user.py`
  -> `4 passed`
- Frontend targeted suite:
  `npm run test:unit -- src/lib/product-doors.test.ts components/auth/AdminGuard.test.tsx app/desk/access-layouts.test.tsx app/desk/page.test.tsx components/layout/nav-config.test.ts features/admin/components/UsersTable.test.tsx app/desk/brands/page.test.tsx`
  -> `64 passed`

## Independent review outcome

Independent reviewer result: `FAIL`

Primary blockers called out by review:

1. Several routes cataloged as `P1` still lack full ADR21 idempotency enforcement.
2. Frontend and BFF layers do not yet propagate `Idempotency-Key` for all newly hardened mutations.
3. Desk/page/API permission boundaries are still incomplete on some staff surfaces.
4. Some unavailable privileged actions are still exposed in the UI.

## Gate outcome

- `G1`: satisfied for Wave 2 execution in this run
- `G2`: `BLOCKED`

`G2` stays blocked because the independent review found real remaining ADR21 and D002 enforcement gaps,
so the current state is not yet implementation-complete enough for honest Wave 2 closure.
