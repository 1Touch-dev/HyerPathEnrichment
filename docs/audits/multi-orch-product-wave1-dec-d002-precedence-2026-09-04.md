# ORCH-PRODUCT Wave 1 Packet — `DEC-D002-PRECEDENCE`

- **Date:** 2026-09-04
- **Orchestrator:** ORCH-PRODUCT
- **Blocker:** `BLK-PROD-002`
- **Decision task:** `D002-DECISION-001`
- **Resulting implementation task:** `D002-IMPL-001`
- **Related pilot decision:** `DEC-PILOT-ACCEPT`
- **Baseline:** `R2-BASELINE-2026-09-04`
- **Gate context:** `G0` passed; this packet contributes to `G1` but does **not** satisfy `G1` on its own
- **Status:** `WAITING FOR PRODUCT / SECURITY REVIEW`
- **Approval state:** No Product, Security, or Infra approval is claimed in this document

## 1. Scope and decision boundaries

This packet covers the ORCH-PRODUCT share of Wave 1 only:

1. Prepare the full decision packet for `BLK-PROD-002`
2. Own `D002-DECISION-001`
3. Prepare the Product side of pilot acceptance for `BLK-PILOT-001`
4. Enumerate resulting implementation and test work for `D002-IMPL-001`

This packet does **not**:

- approve any human decision,
- change `docs/adr/0019-tenancy-model.md`,
- override Security review,
- create new backend permission grants,
- treat `Brand`, `signup_brand_id`, or recruiter assignment rows as tenant boundaries or ACLs,
- authorize any implementation work before `DEC-D002-PRECEDENCE` is approved.

## 2. Proposal summary for Product review

**Recommended proposal only, not an approval:** adopt a **permission-centric precedence model** for Desk privileged surfaces.

Decision statement:

1. The authoritative access decision for Desk privileged surfaces is the user's **current effective permission pair** evaluated on the backend, with the existing backend `is_superuser` short-circuit preserved.
2. `role_name` values such as `admin` and `team_owner` are **not independent privileged ACLs**. They may correspond to default permission bundles, but they do not override missing permissions.
3. Frontend visibility and route guards must align to the same permission model as the backend. UI hiding is advisory; API denial remains authoritative.
4. `Brand` remains presentation-only per ADR 0019. No owner shortcut, brand assignment, signup brand, or recruiter assignment may be treated as a tenant boundary or as an authorization override.
5. Impersonation mode must never be accepted as owner access for Desk privileged surfaces.
6. This packet defines **precedence**, not grant policy. Which humans or system roles should receive `roles:*`, `feature_flags:*`, `queues:*`, or `brands:*` remains subject to Product + Security review and the existing migration/permission model.

## 3. Surface inventory in scope

The current `D-002` conflict is not abstract; it affects concrete frontend and backend surfaces:

| Surface | Current frontend behavior | Current backend behavior | Conflict |
|---|---|---|---|
| `/desk/roles` | Nav + layout are owner-only via `isOwnerUser` / `AdminGuard` without a permission prop | `GET /api/admin/roles` requires `roles:read`; create/attach/detach require `roles:write` | FE can deny a permitted non-owner and can admit an owner who then fails API auth |
| `/desk/feature-flags` | Nav + layout are owner-only | `GET` requires `feature_flags:read`; mutations require `feature_flags:write` but still return `405` read-only | Same FE/BE drift; owner semantics are broader than the API for reads and misleading for writes |
| `/desk/queues` | Nav + layout are owner-only | Queue overview and failed jobs require `queues:read`; retry requires `queues:retry` and still returns `405` | Same FE/BE drift |
| `/desk/brands` | Read visibility is permission-based, but create/edit/deactivate/reactivate controls allow `isOwnerUser` shortcut | Read/write/delete are permission-based (`brands:read`, `brands:write`, `brands:delete`) | FE owner shortcut conflicts with BE exact permission checks |
| `/desk` root/home | Owner-only landing behavior via `isOwnerUser` | Backend does not define a matching owner-only concept for the scoped surfaces above | Root routing still reflects the old owner shortcut model |

## 4. Full `DEC-D002-PRECEDENCE` matrix

This is the required explicit owner-vs-permission matrix from the plan. Each line uses an explicit `Allow`, `Deny`, or `Required behavior` decision.

| Matrix ID | Scenario | Decision | Required behavior |
|---|---|---|---|
| D002-M01 | `owner + permission` | **Allow** | If the user is staff and the current effective permission pair allows the surface or action, show the UI affordance, allow the route, and let the API proceed. Successful privileged mutations still need the normal explicit audit behavior required elsewhere. |
| D002-M02 | `owner - permission` | **Deny** | `admin` / `team_owner` naming alone must not unlock the surface. Hide the affordance, deny direct URL entry at the FE guard, and expect backend `403` or route-specific `405` where applicable. |
| D002-M03 | `non-owner + allow` | **Allow** | A non-owner staff user with the exact permission pair must be able to see the affordance, open the page, and call the API. This is the key precedence rule that replaces owner-only FE shortcuts. |
| D002-M04 | `owner + deny` | **Deny** | If the effective permission set says no, the answer is no. Owner semantics may not resurrect access after a permission is removed, withheld, or not granted. |
| D002-M05 | `malformed cross-context ownership` | **Deny** | Ignore ownership claims derived from URL state, frontend props, `Brand`, `signup_brand_id`, recruiter assignment, or any invented org/tenant context. Only authenticated user state plus current backend permission checks may authorize access. |
| D002-M06 | `mid-session ownership change` | **Required behavior** | Backend must evaluate current DB-backed auth on the next request. Frontend must not optimistically elevate access from a stale role label; newly granted access can appear only after identity refresh / reload updates the effective permissions. |
| D002-M07 | `mid-session revoke` | **Required behavior** | Backend denial on the next request is authoritative. Frontend must fail closed after a `403`, remove stale affordances after identity refresh, and redirect away from now-denied pages. |
| D002-M08 | `no owner` | **Deny** | A roleless or candidate user cannot use Desk privileged surfaces. If the user is not staff, the staff door blocks first. If the user is staff but lacks the relevant permission, the permission gate blocks next. |
| D002-M09 | `admin override + audit` | **Required behavior** | Preserve the existing backend `is_superuser` override. Do **not** invent a separate `role_name = admin` override. When a privileged mutation succeeds under superuser or granted permission, the normal explicit audit requirement still applies. This matrix does not approve broader `roles:*` grants outside Security review. |
| D002-M10 | `impersonation mode` | **Deny** | An impersonated candidate context must not satisfy Desk owner or permission checks. Impersonation remains candidate-only / view-only per the frozen contract and cannot be used to operate privileged Desk surfaces. |
| D002-M11 | `ownership transfer` | **Required behavior** | Changing a `Brand` attribution, `signup_brand_id`, or recruiter assignment row must change **zero** Desk authorization outcomes by itself. Access changes only when the user's role/permission state changes through approved admin flows. |
| D002-M12 | `bulk mixed` | **Required behavior** | Bulk requests must evaluate authorization by action, not by owner label. Mixed-authority requests must not silently partially succeed. Future bulk endpoints should either return itemized allow/deny results or reject the whole request atomically. For current global surfaces (`roles`, `feature_flags`, `queues`), fail closed by default. |

## 5. Decision consequences by surface

To avoid vague language, the matrix above resolves into explicit surface rules:

| Surface | View/list page | Mutations / privileged controls | Notes |
|---|---|---|---|
| `roles` | Requires `roles:read` | Requires `roles:write` | Product precedence packet does not itself approve who should hold `roles:write`; Security must still review grant scope |
| `feature_flags` | Requires `feature_flags:read` | Requires `feature_flags:write`, but current backend contract remains `405` read-only | Frontend must not imply operable flag mutations while evaluator/mutation policy is disabled |
| `queues` | Requires `queues:read` | Retry requires `queues:retry`, but current backend contract remains `405` read-only | Page access must not be owner-only |
| `brands` | Requires `brands:read` | Create/edit require `brands:write`; deactivate/reactivate require `brands:delete` | No owner shortcut; no brand-as-tenant interpretation |
| `/desk` root | Must not remain a pure owner shortcut for scoped surfaces | N/A | Root routing must reflect permission-based access or redirect to the highest-priority allowed Desk destination |

## 6. Conflict record: FE vs BE behavior and required acceptance criteria

### 6.1 Current conflict record

1. **Frontend owner shortcut**
   - `product-doors.ts` defines `isOwnerUser()` from `is_superuser` or `role_name` in `{admin, team_owner}`.
   - `AdminGuard` uses `isOwnerUser()` whenever a page/layout does not provide an explicit permission.
   - Desk nav uses `ownerOnly` for `Roles`, `Feature flags`, and `Queues`.
   - `Brands` write/delete controls use `isOwnerUser()` as a fallback allow path.

2. **Backend permission enforcement**
   - `roles` routes require `roles:read` or `roles:write`.
   - `feature_flags` routes require `feature_flags:read` or `feature_flags:write`; writes are still denied by a read-only `405` contract.
   - `queues` routes require `queues:read` or `queues:retry`; retry is still denied by a read-only `405` contract.
   - `brands` routes require `brands:read`, `brands:write`, or `brands:delete`.

3. **Observed mismatch classes**
   - A staff user with the right permission but without owner role naming can be wrongly blocked by the frontend.
   - A named owner without the right permission can be shown an affordance or page and then fail at the API.
   - The current FE model can mislead reviewers into reading `Brand` or ownership semantics as an ACL boundary, which ADR 0019 explicitly rejects.

### 6.2 Required acceptance criteria

The `D002-IMPL-001` acceptance criteria that follow from the decision are:

1. **Permission parity**
   - Frontend route access, nav visibility, and in-page action controls for `roles`, `feature_flags`, `queues`, and `brands` must key off the same permission pairs the backend enforces.

2. **No owner fallback**
   - No scoped surface in this packet may remain accessible solely because `isOwnerUser()` returned true.

3. **Allow non-owner + permission**
   - At least one FE and one API contract test must prove a non-owner staff user with the exact permission pair can access the corresponding surface.

4. **Deny owner - permission**
   - At least one FE and one API contract test must prove a named owner without the exact permission pair is denied.

5. **Read-only honesty**
   - `feature_flags` and queue retry UX must not imply mutable controls unless backend policy changes. Exact behavior today is permission-gated visibility plus read-only denial for the mutation path.

6. **Root-route alignment**
   - `/desk` root must stop acting as an owner-only special case for this scope. It must either redirect to the highest-priority allowed Desk surface or show a permission-aligned landing.

7. **ADR 0019 safety**
   - No FE or BE logic introduced under `D002-IMPL-001` may use `Brand`, `signup_brand_id`, recruiter assignment, or any invented `org_id` semantics as an allow/deny filter.

8. **Security review preserved**
   - Any changes touching `roles:*` presentation or grant assumptions must be reviewed against Security's privileged-surface work; this product packet does not supersede that review.

## 7. Product side of pilot acceptance for `BLK-PILOT-001`

This section prepares the Product share of `DEC-PILOT-ACCEPT`. It is a prerequisite packet, not a human approval.

### 7.1 Product prerequisites before acceptance can be considered

Product should not sign pilot acceptance until all of the following are true:

1. `DEC-D002-PRECEDENCE` is approved by Product and reviewed by Security.
2. `D002-IMPL-001` is implemented, tested, and independently reviewed.
3. The pilot is explicitly framed as a **restricted internal pilot**, not a production-general release.
4. Pilot cohort control is RBAC-based unless a separate, later-approved feature-flag evaluator exists. Current feature-flag mutations remain disabled and cannot be used as the pilot-control proof.
5. Product briefing material explicitly states the known v1 constraints relevant to pilot expectations:
   - `Brand` is presentation-only, not a tenant boundary.
   - outbound email send is still a no-op in v1,
   - SMS remains a no-op,
   - queue retry and feature-flag mutation remain read-only,
   - any remaining blocked live-evidence items stay blocked until Infra produces them.

### 7.2 Infra evidence Product will require later

Infra must supply the following evidence before Product can honestly consider pilot acceptance:

| Evidence ID | Infra must provide | Why Product needs it |
|---|---|---|
| PILOT-EVID-001 | Pinned release candidate identity: commit SHA and deployed image digest | Prevents pilot sign-off on an unpinned moving target |
| PILOT-EVID-002 | Named pilot environment/host and deployment record | Distinguishes real pilot evidence from local-only simulation |
| PILOT-EVID-003 | Green `/ready` result from the deployed environment | Confirms live environment health before Product evaluation |
| PILOT-EVID-004 | Role/permission assignment evidence for each pilot actor persona | Confirms the pilot cohort is using the approved D-002 model rather than owner shortcuts |
| PILOT-EVID-005 | Negative authorization proof for `owner - permission`, `non-owner + allow`, and non-staff denial | Confirms the FE/BE conflict is actually closed in the pilot environment |
| PILOT-EVID-006 | Audit evidence for at least one successful privileged mutation in the pilot path | Product must not accept a pilot that masks privileged-surface evidence gaps |
| PILOT-EVID-007 | Rollback procedure + rehearsal evidence compatible with current schema rules | Product cannot accept a pilot if rollback remains theoretical |
| PILOT-EVID-008 | Monitoring evidence or an explicit `INSUFFICIENT EVIDENCE FOR EXPANSION` statement | Product can consider a restricted internal pilot without full expansion metrics, but cannot accept expansion without honest observability evidence |

### 7.3 Monitoring expectations for restricted pilot vs expansion

For a **restricted internal pilot**, Product can review a deployment even if full rollout-expansion monitoring is not yet available, but only if the evidence is labeled honestly.

For any **expansion beyond a restricted internal pilot**, Infra must later provide the thresholds already defined in the baseline pilot checklist:

- HTTP 5xx/error rate evidence,
- latency evidence,
- queue depth / stalled job evidence,
- auth anomaly evidence where applicable.

If those metrics are unavailable because the monitoring stack is not configured, the correct status is not pass; it is **insufficient evidence for expansion**.

## 8. Resulting `D002-IMPL-001` implementation and test backlog

These tasks are enumerated only. None are approved or implemented by this packet.

| Task ID | Type | Scope | Owner orchestrator | Execution owner | Tester | Reviewer | Status after this packet | Depends on |
|---|---|---|---|---|---|---|---|---|
| D002-IMPL-001A | Implementation | Replace owner-only nav metadata for `roles`, `feature_flags`, and `queues` with explicit permission-based visibility rules in the Desk navigation / door helpers | ORCH-PRODUCT | FIX-FE-DOORS | TEST-FE-DOORS | REVIEW-FE | `READY AFTER DECISION APPROVED` | `DEC-D002-PRECEDENCE` |
| D002-IMPL-001B | Implementation | Update `AdminGuard` and Desk route/layout wiring so `roles`, `feature_flags`, and `queues` use explicit permission props instead of owner fallback | ORCH-PRODUCT | FIX-FE-GUARDS | TEST-FE-GUARDS | REVIEW-FE | `READY AFTER DECISION APPROVED` | `DEC-D002-PRECEDENCE` |
| D002-IMPL-001C | Implementation | Align `/desk` root routing with permission-centric precedence instead of owner-only landing behavior | ORCH-PRODUCT | FIX-FE-ROOT | TEST-FE-ROOT | REVIEW-FE | `READY AFTER DECISION APPROVED` | `DEC-D002-PRECEDENCE` |
| D002-IMPL-001D | Implementation | Remove `isOwnerUser()` shortcut from Brands action controls; gate create/edit/deactivate/reactivate only by `brands:write` / `brands:delete` | ORCH-PRODUCT | FIX-FE-BRANDS | TEST-FE-BRANDS | REVIEW-FE | `READY AFTER DECISION APPROVED` | `DEC-D002-PRECEDENCE` |
| D002-TEST-001 | Test | Update `product-doors` and `AdminGuard` unit tests to cover `owner + permission`, `owner - permission`, and `non-owner + allow` outcomes explicitly | ORCH-PRODUCT | TEST-FE-UNIT | REVIEW-FE-UNIT | REVIEW-FE | `READY AFTER DECISION APPROVED` | `D002-IMPL-001A`, `D002-IMPL-001B` |
| D002-TEST-002 | Test | Update layout/page wiring tests so `roles`, `feature_flags`, and `queues` prove explicit permission-based guarding instead of owner-only wrapping | ORCH-PRODUCT | TEST-FE-LAYOUTS | REVIEW-FE-LAYOUTS | REVIEW-FE | `READY AFTER DECISION APPROVED` | `D002-IMPL-001B` |
| D002-TEST-003 | Test | Update Brands page tests for exact `brands:write` / `brands:delete` control visibility and denial states, with no owner shortcut | ORCH-PRODUCT | TEST-FE-BRANDS | REVIEW-FE-BRANDS | REVIEW-FE | `READY AFTER DECISION APPROVED` | `D002-IMPL-001D` |
| D002-TEST-004 | Contract test | Add or refresh API contract tests proving the matrix remains backend-authoritative for `roles`, `feature_flags`, `queues`, and `brands` | ORCH-QA | TEST-API-D002 | REVIEW-BE-D002 | ORCH-SECURITY | `READY AFTER DECISION APPROVED` | `DEC-D002-PRECEDENCE` |
| D002-TEST-005 | Live integration | Extend live `product-doors-t4` coverage for D-002 negative/positive cases once environment exists | ORCH-QA | QA-RUNNER-D002 | QA-EVIDENCE-REVIEW | ORCH-CERT | `WAITING FOR ENVIRONMENT + DECISION` | `DEC-D002-PRECEDENCE`, `T4-ENV-001`, `AUTH-SETUP-001`, `G2` |

Backlog guardrails:

- The same agent/person must not implement, test, and approve the same task.
- No backlog item here authorizes new permission grants by itself.
- If Security's privileged-surface packet constrains any scoped surface more tightly, Security wins until Product re-approves the combined result.

## 9. Status labels and `G1` handoff

### 9.1 ORCH-PRODUCT status labels

- `BLK-PROD-002`: `OPEN CONFLICT`
- `D002-DECISION-001`: `PACKET PREPARED`
- `DEC-D002-PRECEDENCE`: `WAITING FOR PRODUCT / SECURITY REVIEW`
- Product side of `DEC-PILOT-ACCEPT`: `PREREQUISITES PREPARED; APPROVAL PENDING`
- `D002-IMPL-001`: `READY AFTER DECISION APPROVED`

### 9.2 ORCH-ROOT handoff

**Handoff label:** `PACKET READY; OWNER DECISION PENDING`

ORCH-ROOT should record:

1. The ORCH-PRODUCT Wave 1 packet is complete for review.
2. `G1` is **not** satisfied by the Product track yet because Product approval and Security review are still pending.
3. `BLK-PROD-002` remains open until `DEC-D002-PRECEDENCE` is human-approved and the resulting implementation/tests pass.
4. No `D002-IMPL-001` execution should start from this packet alone.

### 9.3 ORCH-SECURITY handoff

**Handoff label:** `SECURITY REVIEW REQUIRED`

ORCH-SECURITY should review and either confirm or reject:

1. the proposed permission-centric precedence,
2. preservation of the existing `is_superuser` override only,
3. denial of impersonation as a Desk privilege path,
4. denial of any owner/brand/assignment-based tenant interpretation,
5. the boundary that this packet defines precedence only and does not self-approve grant expansion.

### 9.4 ORCH-QA handoff

**Handoff label:** `TEST DESIGN READY AFTER APPROVAL`

ORCH-QA should:

1. derive FE unit, layout, API contract, and live T4 cases directly from the `D002-M01` through `D002-M12` matrix,
2. keep any live execution in `WAITING FOR ENVIRONMENT` until the existing T4 prerequisites are satisfied,
3. reject any attempt to count mocked FE coverage as a substitute for live D-002 validation in the final certification path.

## 10. Final status for this Wave 1 packet

This packet is complete as a **decision-and-handoff artifact**. It is intentionally not an approval artifact.

Current recommended status:

- `DEC-D002-PRECEDENCE`: `WAITING FOR PRODUCT / SECURITY REVIEW`
- `BLK-PROD-002`: `OPEN CONFLICT`
- `D002-IMPL-001`: `READY AFTER DECISION APPROVED`
- Product share of `DEC-PILOT-ACCEPT`: `PREREQUISITES PREPARED; WAITING FOR INFRA EVIDENCE AND HUMAN SIGN-OFF`

## 11. Source traceability

Primary evidence for this packet was drawn from:

- `frontend/src/lib/product-doors.ts`
- `frontend/components/auth/admin-guard.tsx`
- `frontend/components/layout/nav-config.ts`
- `frontend/app/desk/page.tsx`
- `frontend/app/desk/roles/layout.tsx`
- `frontend/app/desk/feature-flags/layout.tsx`
- `frontend/app/desk/queues/layout.tsx`
- `frontend/app/desk/brands/page.tsx`
- `frontend/components/auth/AdminGuard.test.tsx`
- `frontend/app/desk/access-layouts.test.tsx`
- `backend/app/modules/admin/permissions.py`
- `backend/app/modules/admin/roles_router.py`
- `backend/app/modules/admin/flags_router.py`
- `backend/app/modules/admin/queues_router.py`
- `backend/app/modules/brands/router.py`
- `backend/app/modules/brands/deactivation_router.py`
- `backend/tests/test_product_doors.py`
- `backend/tests/test_admin_brands_router.py`
- `backend/tests/test_admin_feature_flags_read_only_d007.py`
- `backend/tests/test_brand_deactivation.py`
- `backend/alembic/versions/038_admin_seed_roles_permissions.py`
- `backend/alembic/versions/047_seed_system_roles.py`
- `backend/alembic/versions/056_seed_brands_permissions.py`
- `backend/alembic/versions/057_seed_brands_delete_permission.py`
- `docs/adr/0019-tenancy-model.md`
- `docs/audits/dev-b-desk-final-audit-2026-09-04.md`
- `docs/audits/dev-b-desk-final-audit-2026-09-04-addendum-r2.md`
