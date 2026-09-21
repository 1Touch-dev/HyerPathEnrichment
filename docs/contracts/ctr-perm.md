# CTR-PERM — Desk permission precedence (D-002)

Approved permission-centric access contract for Desk privileged surfaces.
Implementation SoT: [`frontend/src/lib/product-doors.ts`](../../frontend/src/lib/product-doors.ts)
(`hasPermission` + `is_superuser`) and backend `require_permission` /
`require_superuser_strict`. `role_name` is never an ACL.

See ADR 0015, ADR 0019, and the D-002 matrix
(`docs/audits/multi-orch-product-wave1-dec-d002-precedence-2026-09-04.md`).

## Precedence

1. Authenticated, verified user.
2. Staff door where the route is staff-mounted (`is_superuser` or `role_id`).
3. Current effective permission pair on the backend, with `is_superuser` override.
4. UI guards and nav must use the same permission pairs. Hiding is advisory; API denial is authoritative.

`admin` / `team_owner` labels do **not** unlock a surface. `Brand`,
`signup_brand_id`, and recruiter assignments are presentation / ownership
markers, not tenant or ACL overrides (ADR 0019).

## D002 matrix

| ID | Scenario | Decision | Required behavior |
|----|----------|----------|-------------------|
| D002-M01 | owner + permission | Allow | Staff with the current permission pair may see the UI, enter the route, and call the API. Privileged mutations still need CTR-PRIV audit/idempotency. |
| D002-M02 | owner − permission | Deny | `admin` / `team_owner` naming alone must not unlock. Hide affordance, deny URL at FE guard, expect API `403` or route `405`. |
| D002-M03 | non-owner + allow | Allow | Non-owner staff with the exact pair may see, open, and call. |
| D002-M04 | owner + deny | Deny | Missing permission is deny. Owner semantics must not resurrect access. |
| D002-M05 | malformed cross-context ownership | Deny | Ignore URL props, Brand, signup brand, recruiter assignment, invented org/tenant context. |
| D002-M06 | mid-session grant | Required | Backend re-evaluates DB auth on the next request. FE must not elevate from a stale role label. |
| D002-M07 | mid-session revoke | Required | Backend denial on the next request is authoritative. FE fail-closed after `403`. |
| D002-M08 | no owner / candidate | Deny | Roleless users cannot use Desk privileged surfaces. Staff door first, then permission. |
| D002-M09 | admin override + audit | Required | Preserve backend `is_superuser` override. Do not invent `role_name = admin` override. |
| D002-M10 | impersonation mode | Deny | Impersonated candidate context cannot satisfy Desk permission checks. Candidate-only / view-only. |
| D002-M11 | ownership transfer | Required | Changing Brand attribution or assignment rows changes zero Desk authz outcomes. |
| D002-M12 | bulk mixed | Required | Authorize by action, not owner label. Current global surfaces fail closed by default. |

## Route permission pairs (read)

| Path | Permission |
|------|------------|
| `/desk` home | `system_health:read` |
| `/desk/roles` | `roles:read` |
| `/desk/feature-flags` | `feature_flags:read` |
| `/desk/queues` | `queues:read` |
| `/desk/brands` | `brands:read` (write/delete are separate pairs) |
| `/desk/users` | `users:read` |
| `/desk/staff-invites` | `users:write` |

Unauthenticated users go to `/login?redirect=`. Non-staff go to `/app/matches`.
Staff without a matching home permission fall through to `/osint`.

## Must / must-not

- **Must** evaluate `{resource, action}` pairs (or `is_superuser`).
- **Must not** treat `role_name` as sufficient for privileged Desk surfaces.
- **Must not** add `org_id` / tenant isolation filters.
