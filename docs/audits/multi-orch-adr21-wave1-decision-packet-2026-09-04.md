# ORCH-SECURITY Wave 1 Packet: `DEC-ADR21-SURFACE`

- Date: 2026-09-04
- Owner: ORCH-SECURITY
- Blocker: `BLK-SEC-001`
- Finding: `FIND-SEC-001`
- Decision task: `ADR21-DECISION-001`
- Resulting implementation task: `ADR21-IMPL-001`
- Baseline carried forward: `G0` passed on `R2-BASELINE-2026-09-04`
- Approval status: `WAITING FOR SECURITY / PRODUCT`

## Purpose

Prepare the Wave 1 decision packet for ADR 0021 surface completeness without
claiming approval and without implementing the resulting enforcement work.

This packet is grounded in the live code under:

- `backend/app/modules/admin/`
- `backend/app/modules/staff_invites/`
- `backend/app/modules/brands/`
- `backend/app/auth/dependencies.py`
- `backend/tests/` security/admin suites

## Scope Boundary

Included in this packet:

- Live privileged or privilege-adjacent Desk/admin mutation routes
- Staff invite issuance
- Brand mutations under admin control
- Self-service MFA routes under the admin prefix because they gate step-up for
  privileged flows
- Current fail-closed admin-unavailable routes that ADR 0021 explicitly calls out
  (`feature_flags`, queue retry)

Explicitly excluded from this packet:

- Read-only admin routes (`GET` list/detail/status surfaces) except as `P0` context
- Public staff invite lookup (`GET /api/staff-invites/{token}`), which is read-only
- Candidate/public DSAR and opt-out routes; they are not part of the Desk privileged
  mutation surface for `BLK-SEC-001`
- Non-Desk business mutations that happen to use RBAC permissions
  (`recruiter_assignments`, `linkedin_sourcing`, `recruiter_actions`)

## Current Code Reality

ADR 0021 is accepted, and the tree already contains important foundations:

- explicit admin audit schema with `request_id` and `outcome`
- impersonation session schema and request-path validation
- staff invite idempotency persistence and replay protection
- fail-closed feature-flag mutations
- fail-closed queue retry

The open gap is still real: there is no single code-owned privileged-operation
catalog that classifies the full live mutation surface and enforces `P1`/`P2`/`P3`
requirements consistently. Controls are split across routers and services, and some
live operations still rely on fallback audit or lack idempotency/typed confirmation.

## 1. Privileged-Surface Inventory

### 1.1 In-scope live mutation families

| Surface | Live routes / code | Current auth/control state | Proposed class | Wave 1 status | Current gap vs ADR 0021 |
|---|---|---|---|---|---|
| Staff invite issuance | `POST /api/staff-invites` in `backend/app/modules/staff_invites/router.py`; persistence in `backend/app/modules/staff_invites/repository.py` | `users:write`, `Idempotency-Key`, typed email confirmation, MFA code, explicit audit, atomic idempotency persistence | `P3` | `PARTIALLY ALIGNED` | Strongest current implementation; still not driven by a central classifier shared with the rest of the privileged surface |
| User deactivation / reactivation | `PATCH /api/admin/users/{user_id}/status` in `backend/app/modules/admin/users_router.py` via `service.update_user_status()` | `users:suspend`, explicit audit in service transaction | `P3` when `is_active=false`; `P1` when `is_active=true` | `INCOMPLETE` | No central classification, no `Idempotency-Key`, no typed confirmation on destructive deactivate path |
| User role assignment | `PUT /api/admin/users/{user_id}/role` in `backend/app/modules/admin/users_router.py` via `service.assign_role()` | strict `is_superuser` only, explicit audit staged before commit | `P3` | `INCOMPLETE` | No central classification, no `Idempotency-Key`, no typed confirmation for privilege grant |
| Role creation | `POST /api/admin/roles` in `backend/app/modules/admin/roles_router.py` via `roles_service.create_role()` | `roles:write`, explicit audit | `P3` | `INCOMPLETE` | Privilege-surface mutation but repository commits before audit, so audit is not guaranteed in the same transaction |
| Role permission attach | `POST /api/admin/roles/{role_id}/permissions` via `roles_service.attach_permission_to_role()` | `roles:write`, explicit audit | `P3` | `INCOMPLETE` | Grants privilege but repository commits before audit; no `Idempotency-Key`; no typed confirmation |
| Role permission detach | `DELETE /api/admin/roles/{role_id}/permissions/{permission_id}` via `roles_service.detach_permission_from_role()` | `roles:write`, explicit audit | `P3` | `INCOMPLETE` | Same atomicity/idempotency gap as attach; destructive authz change without typed confirmation |
| Impersonation start | `POST /api/admin/impersonation/start/{user_id}` in `backend/app/modules/admin/impersonation_router.py` / `impersonation.py` | `impersonation:start`, MFA required, candidate-only target, explicit audit, request-path allowlist enforced in `backend/app/auth/dependencies.py` | `P2` | `PARTIALLY ALIGNED` | No central classifier; no `Idempotency-Key`; separate residual `FIND-SEC-003` remains for unused `revoked_at` writer path |
| Impersonation end | `POST /api/admin/impersonation/end` in `backend/app/modules/admin/impersonation_router.py` / `impersonation.py` | verified user inside active impersonation session, explicit audit, cookie restoration | `P2` | `PARTIALLY ALIGNED` | Controlled but not catalog-driven; no central enforcement of operation class semantics |
| MFA enroll / confirm / disable | `POST /api/admin/mfa/enroll|confirm|disable` in `backend/app/modules/admin/mfa_router.py` / `mfa.py` | verified self only, rate limited, explicit audit; replacement/disable require current MFA code | `P2` | `PARTIALLY ALIGNED` | Sensitive auth-factor management lives under admin prefix but is not represented in a central privileged-operation catalog |
| Brand create | `POST /api/admin/brands` in `backend/app/modules/brands/router.py` | `brands:write`; commit succeeds | `P1` | `INCOMPLETE` | No explicit audit, no idempotency, no central classification |
| Brand update | `PATCH /api/admin/brands/{brand_id}` in `backend/app/modules/brands/router.py` | `brands:write`; commit succeeds | `P1` | `INCOMPLETE` | No explicit audit, no idempotency, no central classification |
| Brand deactivate / reactivate | `POST /api/admin/brands/{brand_id}/deactivate|reactivate` in `backend/app/modules/brands/deactivation_router.py` / `deactivation_service.py` | `brands:delete`, explicit audit, reversible flag flip | `P1` | `PARTIALLY ALIGNED` | No central classifier; no `Idempotency-Key` |
| Content moderation: documents | `POST /api/admin/documents/{document_id}/moderate` | `documents:moderate`, explicit audit | `P1` | `PARTIALLY ALIGNED` | No central classification or idempotency |
| Content moderation: job postings | `POST /api/admin/job-postings/{job_posting_id}/moderate` | `job_postings:moderate`, explicit audit | `P1` | `PARTIALLY ALIGNED` | No central classification or idempotency |
| Content moderation: questions | `POST /api/admin/questions/{question_id}/moderate` | `questions:moderate`, explicit audit | `P1` | `PARTIALLY ALIGNED` | No central classification or idempotency |
| Content moderation: practice audio | `POST /api/admin/practice-audio/{recording_id}/moderate` | `practice_audio:moderate`, explicit audit | `P1` | `PARTIALLY ALIGNED` | No central classification or idempotency |
| Content moderation: outreach | `POST /api/admin/outreach/{message_id}/moderate` | `outreach:moderate`, explicit audit | `P1` | `PARTIALLY ALIGNED` | No central classification or idempotency |
| Content moderation: portfolio | `POST /api/admin/portfolio/{profile_id}/moderate` | `portfolio:moderate`, explicit audit | `P1` | `PARTIALLY ALIGNED` | No central classification or idempotency |
| Content moderation: interview schedules | `POST /api/admin/interview-schedules/{schedule_id}/moderate` | `interview_schedules:moderate`, explicit audit, queue side-effect for cancel | `P1` | `PARTIALLY ALIGNED` | No central classification or idempotency |
| Content moderation: manual job entries | `POST /api/admin/manual-job-entries/{entry_id}/moderate` | `manual_job_entries:moderate`, explicit audit | `P1` | `PARTIALLY ALIGNED` | No central classification or idempotency |
| Review queue decision | `POST /api/admin/review-queue/{item_id}/decide` in `backend/app/modules/admin/review_queue_router.py` | `content_review:decide`, explicit audit, possible notification side effect | `P1` | `PARTIALLY ALIGNED` | No central classification or idempotency |
| Feature-flag create/update/toggle/delete | `PUT|POST|PATCH|DELETE /api/admin/feature-flags...` in `backend/app/modules/admin/flags_router.py` | `feature_flags:write`, always `405`, fail-closed | `UNAVAILABLE` | `ALIGNED AS FAIL-CLOSED` | Disabled by ADR/product constraint; attempted writes rely on fallback audit rather than explicit privileged-op handling |
| Queue retry | `POST /api/admin/queues/{name}/failed/{job_id}/retry` in `backend/app/modules/admin/queues_router.py` / `queues_service.py` | `queues:retry`, always `405`, denied before Redis lookup | `UNAVAILABLE` | `ALIGNED AS FAIL-CLOSED` | Correctly unavailable today; no approved retry-safe catalog or idempotent replay contract yet |

### 1.2 `P0` read-only context

The following live surfaces are relevant to the privileged model but are not part of
`ADR21-IMPL-001` mutation enforcement:

- admin list/detail/status reads under `users`, `roles`, `audit-logs`, `system-health`,
  `feature-flags`, `queues`, `applications`, and admin moderation list/detail routers
- `GET /api/admin/impersonation/status`
- `GET /api/admin/mfa/status`
- public staff invite lookup (`GET /api/staff-invites/{token}`)

These remain `P0`: normal authentication/authorization only, plus the existing
candidate-only impersonation read allowlist where applicable.

### 1.3 Inventory conclusions

1. The live privileged mutation surface is broader than invites, roles, users, flags,
   queues, and impersonation alone; it includes brand mutations and all shipped admin
   moderation / review-decision routes.
2. Staff invite issuance is the only surface already close to the ADR 0021 target
   contract.
3. Brand create/update currently lack explicit audit entirely.
4. Role create/attach/detach currently split mutation commit and audit commit across
   repository/service boundaries, which violates the ADR requirement that the successful
   privileged mutation and its explicit audit record commit together.
5. Many live privileged mutations have explicit audit but still lack centralized class
   mapping and `Idempotency-Key` enforcement.
6. Queue retry and feature-flag mutations must remain unavailable in the recommendation;
   no permissive default is supportable from current code or policy.

## 2. Decision Packet: `DEC-ADR21-SURFACE`

### 2.1 Decision statement

Define one explicit privileged-operation catalog for all live Desk privileged mutations,
map each operation to `P0`/`P1`/`P2`/`P3`/`UNAVAILABLE`, enforce the class server-side,
and make every unmapped or unresolved privileged mutation fail closed.

`P4` remains unavailable everywhere in this wave because there is still no approved
four-eyes workflow, approver ledger, expiry policy, or separation-of-duties model.

### 2.2 Options

| Option | Summary | Security impact | Product impact | Implementation impact | Test impact | Ops impact | Recommendation |
|---|---|---|---|---|---|---|---|
| A | Full code-grounded catalog covering every live privileged mutation family; operation-level mapping may split by payload when needed; unmapped operations fail closed | Strongest. Removes ambiguity, closes hidden route gaps, preserves fail-closed posture | Requires Product to explicitly accept classification outcomes for visible Desk actions; no hidden policy changes | Medium-high. Central catalog + route wiring + transaction fixes + tests | High but bounded and measurable; enables a complete class matrix | Low runtime risk if rolled carefully; no new infra dependency | **Recommended** |
| B | Patch only the known high-risk families (roles, users, invites, impersonation), leave moderation/brands on current route-specific controls | Leaves real live routes outside the catalog; `FIND-SEC-001` remains materially open | Lower immediate Product review burden, but only by ignoring shipped behavior | Medium | Medium | Low | Rejected |
| C | Treat all `/api/admin` mutations as one generic privileged class with ad hoc exceptions | Simpler but too coarse; will either under-protect grants/destructive paths or over-block benign reversible moderation | Product-facing friction becomes arbitrary; hard to explain why some flows require more ceremony | Low-medium initially, expensive later due exceptions | Medium | Medium due repeated exceptions | Rejected |
| D | Document current gaps and time-box exceptions while keeping routes live | Explicitly accepts incomplete enforcement on a release blocker | Lowest near-term product friction | Low | Low | Low | Rejected for certification |

### 2.3 Recommended option details

Recommend **Option A** with these exact rules:

1. Build a server-owned privileged-operation catalog keyed to stable operation IDs,
   not just route prefixes.
2. Permit route-to-operation mapping to branch by payload where the risk changes:
   - `users.status.deactivate` -> `P3`
   - `users.status.reactivate` -> `P1`
3. Treat the following as `P3`:
   - staff invite issuance
   - user role assignment
   - role creation
   - role permission attach
   - role permission detach
4. Treat the following as `P2`:
   - impersonation start
   - impersonation end
   - MFA enroll / confirm / disable
5. Treat the following as `P1`:
   - brand create / update / deactivate / reactivate
   - admin moderation actions
   - review queue decisions
   - user reactivation
6. Keep the following `UNAVAILABLE` until separately approved:
   - all feature-flag mutations
   - queue retry and any broader queue-administration mutations not backed by an
     explicit retry-safe catalog
   - any future operation not added to the catalog
7. For `P1`/`P2`/`P3`, server enforcement must require:
   - explicit operation mapping
   - explicit audit row in the same transaction as the mutation
   - `request_id` and `outcome`
8. Additional per-class rules:
   - `P1`: `Idempotency-Key`
   - `P2`: `Idempotency-Key` plus recent step-up authentication
   - `P3`: `Idempotency-Key` plus recent step-up authentication plus typed confirmation
9. For operations where recent step-up already exists in another form
   (`staff_invites` MFA code, impersonation start MFA code), implementation may reuse
   that proof only if the final classifier documents it as the `P2`/`P3` satisfaction
   mechanism.
10. No route may silently inherit a permissive default from being under `/api/admin`.

### 2.4 Rejected options and why

- **Option B rejected:** it would leave live moderation and brand mutations outside the
  ADR 0021 surface, so `FIND-SEC-001` would still be open in substance even if the most
  obvious paths were patched.
- **Option C rejected:** a single generic class for all admin mutations cannot express the
  difference between a reversible moderation flip and a privilege grant.
- **Option D rejected:** the audit already established this as a release-blocking control
  gap; documenting incompleteness is not equivalent to resolving it.

### 2.5 Threats addressed

- RBAC graph tampering without higher-friction controls on privilege grants
- Replay or double-submit of privileged mutations
- Silent success of privileged mutations without one authoritative explicit audit row
- Inconsistent protection between old and newly added admin routes
- Privileged mutation drift where a new route ships without a class and defaults open
- Queue or feature-flag administrative actions becoming active without an explicit safety
  contract
- Identity-assumption misuse through incomplete impersonation surface governance

### 2.6 Residual risks after the recommended decision

- `FIND-SEC-003` remains separate: request-path enforcement reads `revoked_at`, but the
  main production end path still writes `ended_at`, not revocation.
- `P4` remains unavailable, so any legitimate future four-eyes use case still needs a new
  ADR and implementation slice.
- Some `P1` operations with external side effects (for example review notifications or
  reminder cancellation) will still need careful request-hash design so replay persistence
  does not store sensitive or operationally noisy payloads.
- Product may still decide some operation should move to a stricter class; this packet
  recommends a default classification but does not claim approval.

### 2.7 Required approvers

No approval is claimed here. The packet requires:

- Security human owner: approve or reject the proposed class map and fail-closed rules
- Product human owner: approve or reject the product-visible friction and unavailable
  operations
- Independent Security reviewer after implementation: verify `ADR21-IMPL-001`

### 2.8 Measurable acceptance criteria

`DEC-ADR21-SURFACE` is ready for approval only when reviewers can confirm all of the
following:

1. The privileged-operation inventory covers every currently live Desk/admin mutation route
   in this packet and explicitly labels excluded surfaces.
2. Every in-scope mutation has one explicit target state: `P1`, `P2`, `P3`, or
   `UNAVAILABLE`; none rely on implicit route-prefix defaults.
3. Feature-flag mutations and queue retry remain fail-closed in the approved proposal.
4. The recommended option does not enable any `P4` operation.
5. The resulting implementation backlog is complete enough for `ADR21-IMPL-001` to start
   immediately after approval without reopening policy ambiguity.

## 3. Resulting Backlog: `ADR21-IMPL-001`

Status for the whole implementation workstream: `READY AFTER GATE`

### 3.1 Implementation tasks with owner/tester/reviewer separation

| Task ID | Task | Owner | Tester | Reviewer | Status after this packet |
|---|---|---|---|---|---|
| `ADR21-IMPL-001-A` | Create a central privileged-operation catalog and stable operation IDs for all in-scope routes, including payload-based splits where required | `FIX-BE-SEC` | `TEST-SEC` | `REVIEW-SEC` | `READY AFTER GATE` |
| `ADR21-IMPL-001-B` | Add server enforcement helpers/dependencies for class lookup, fail-closed unmapped operations, `Idempotency-Key`, step-up proof, and typed confirmation requirements | `FIX-BE-SEC` | `TEST-SEC` | `REVIEW-SEC` | `READY AFTER GATE` |
| `ADR21-IMPL-001-C` | Rewire live privileged routes to use the central catalog: users, roles, impersonation, MFA, staff invites, brands, moderation routers, review queue | `FIX-BE-SEC` | `TEST-SEC` | `REVIEW-SEC` | `READY AFTER GATE` |
| `ADR21-IMPL-001-D` | Keep feature-flag mutations and queue retry explicitly unavailable through the same catalog instead of route-local one-offs | `FIX-BE-SEC` | `TEST-SEC` | `REVIEW-SEC` | `READY AFTER GATE` |
| `ADR21-IMPL-001-E` | Fix audit atomicity for role mutations by removing repository-level early commits or otherwise ensuring mutation + explicit audit commit together | `FIX-BE-SEC` | `TEST-SEC` | `REVIEW-SEC` | `READY AFTER GATE` |
| `ADR21-IMPL-001-F` | Add explicit audit coverage for brand create/update so they stop relying on generic fallback behavior | `FIX-BE-SEC` | `TEST-SEC` | `REVIEW-SEC` | `READY AFTER GATE` |
| `ADR21-IMPL-001-G` | Extend request-hash/redaction logic for any new privileged-idempotency usage so stored hashes/responses exclude raw tokens, emails, MFA codes, queue args, and exception payloads | `FIX-BE-SEC` | `TEST-SEC` | `REVIEW-SEC` | `READY AFTER GATE` |
| `ADR21-IMPL-001-H` | Add or update architecture/docs references if the final approved class map changes documented implementation status | `FIX-BE-SEC` | `QA-DOCS` | `REVIEW-SEC` | `READY AFTER GATE` |

### 3.2 Required test tasks

| Task ID | Test task | Owner | Tester | Reviewer | Status after this packet |
|---|---|---|---|---|---|
| `ADR21-TEST-001` | Add unit/API tests proving every mapped `P1` operation rejects missing `Idempotency-Key` and replays equivalent requests safely | `TEST-SEC` | `TEST-SEC` | `REVIEW-SEC` | `READY AFTER GATE` |
| `ADR21-TEST-002` | Add unit/API tests proving every mapped `P2` operation rejects missing/expired/invalid step-up proof and stays fail-closed on stale impersonation state | `TEST-SEC` | `TEST-SEC` | `REVIEW-SEC` | `READY AFTER GATE` |
| `ADR21-TEST-003` | Add unit/API tests proving every mapped `P3` operation rejects missing typed confirmation and does not mutate state on denial | `TEST-SEC` | `TEST-SEC` | `REVIEW-SEC` | `READY AFTER GATE` |
| `ADR21-TEST-004` | Add regression tests for role mutation atomicity: mutation must not persist if explicit audit persistence fails | `TEST-SEC` | `TEST-SEC` | `REVIEW-SEC` | `READY AFTER GATE` |
| `ADR21-TEST-005` | Add regression tests for brand create/update explicit audit with `request_id` and `outcome` | `TEST-SEC` | `TEST-SEC` | `REVIEW-SEC` | `READY AFTER GATE` |
| `ADR21-TEST-006` | Add completeness tests asserting all live privileged routes are present in the catalog and any new unmapped route fails closed | `TEST-SEC` | `TEST-SEC` | `REVIEW-SEC` | `READY AFTER GATE` |
| `ADR21-TEST-007` | Keep queue retry and feature-flag mutation tests proving deny-before-side-effect and `405` stability | `TEST-SEC` | `TEST-SEC` | `REVIEW-SEC` | `READY AFTER GATE` |
| `ADR21-TEST-008` | Add Postgres-backed transaction tests for privileged audit and idempotency behavior where SQLite can mask ordering/constraint issues | `QA-PG-TEST` | `QA-PG-TEST` | `INFRA-REVIEW` + `REVIEW-SEC` | `WAITING FOR ENVIRONMENT` |

## 4. Status Labels for Security-Owned Tasks

| Item | Owner | Status label | Evidence expectation |
|---|---|---|---|
| `BLK-SEC-001` | ORCH-SECURITY + Product review | `OPEN` | Cannot close until approved decision plus verified implementation/test evidence |
| `FIND-SEC-001` | Security/Product | `OPEN` | This packet only prepares the decision; it does not resolve the finding |
| `ADR21-DECISION-001` | ORCH-SECURITY | `READY FOR OWNER REVIEW` | This document, explicit approver disposition, and any requested edits |
| `DEC-ADR21-SURFACE` | Security + Product humans | `WAITING FOR OWNER DECISION` | Signed or otherwise durable approval/rejection record referencing the final packet |
| `ADR21-IMPL-001` | FIX-BE-SEC | `READY AFTER GATE` | Approved decision packet plus implementation/test task kickoff |
| `EVID-ADR21-SURFACE` | ORCH-SECURITY | `PARTIAL` | Inventory + packet exist; approval evidence does not yet exist |
| `G1` security track | ORCH-ROOT with Security/Product approvers | `BLOCKED ON OWNER DECISION` | Security and Product approval for `DEC-ADR21-SURFACE`; implementation backlog accepted as actionable |

## 5. G1 Evidence Expectations for the Security Track

To satisfy the security slice of `G1`, the evidence bundle must contain:

1. This code-grounded inventory packet.
2. A durable owner approval record for `DEC-ADR21-SURFACE` from:
   - Security human
   - Product human
3. An implementation backlog reference that clearly starts `ADR21-IMPL-001` without
   reopening classification ambiguity.
4. A derived test matrix tying `P1`/`P2`/`P3`/`UNAVAILABLE` outcomes to concrete
   backend tests.
5. An explicit statement that:
   - unclassified privileged mutations remain unavailable
   - feature-flag mutations remain unavailable
   - queue retry remains unavailable
   - `P4` remains unavailable

Absent those approval records, the correct state remains
`WAITING FOR OWNER DECISION`, not `APPROVED`.

## 6. Recommended next handoff

Send this packet to the Security and Product human owners for `DEC-ADR21-SURFACE`.
If they approve with edits, freeze the approved class map and start `ADR21-IMPL-001`
with the owner/tester/reviewer split above. If they reject or request reclassification,
update this packet first; do not start implementation from an ambiguous class model.
