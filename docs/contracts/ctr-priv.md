# CTR-PRIV — Privileged-operation catalog freeze

Approved contract for Desk / admin privileged mutations. Source of truth for
classification is [`PRIVILEGED_OPERATION_CATALOG`](../../backend/app/modules/admin/privileged_operations.py)
and the route map `EXPECTED_PRIVILEGED_ROUTE_OPERATIONS`. This file freezes
that table for consumers; do not enable `UNAVAILABLE` ops in this residual.

See ADR 0021. Unmapped operations fail closed with `405 PRIVILEGED_OPERATION_UNCLASSIFIED`.
P4 four-eyes remains unavailable. Feature-flag writes and queue retry stay `405`.

## Classification

| Level | Meaning |
|-------|---------|
| P1 | Bounded reversible mutation. AuthZ + explicit audit + `Idempotency-Key`. |
| P2 | Sensitive data or identity assumption. P1 plus recent step-up (MFA where already required). |
| P3 | Destructive or privilege grant. P2 plus typed confirmation. |
| UNAVAILABLE | Must not execute. Return `405` with the catalog code/reason. |
| P4 | Dual control. Not implemented; do not approximate. |

## Catalog

| Operation ID | Level | Route(s) | Notes |
|--------------|-------|----------|-------|
| `staff_invite.issued` | P3 | `POST /api/staff-invites` | Recruiter-only; MFA + typed email + key (existing invite path). |
| `user.status.deactivate` | UNAVAILABLE | `PATCH /api/admin/users/{user_id}/status` when `is_active=false` | Typed confirm + step-up not implemented. |
| `user.status.reactivate` | P1 | `PATCH /api/admin/users/{user_id}/status` when `is_active=true` | |
| `user.role.assign` | UNAVAILABLE | `PUT /api/admin/users/{user_id}/role` | |
| `role.create` | UNAVAILABLE | `POST /api/admin/roles` | |
| `role.attach_permission` | UNAVAILABLE | `POST /api/admin/roles/{role_id}/permissions` | |
| `role.detach_permission` | UNAVAILABLE | `DELETE /api/admin/roles/{role_id}/permissions/{permission_id}` | |
| `impersonation.started` | P2 | `POST /api/admin/impersonation/start/{user_id}` | Candidate-only, `view_only`, MFA. |
| `impersonation.ended` | P2 | `POST /api/admin/impersonation/end` | |
| `mfa.enrollment_started` | P2 | `POST /api/admin/mfa/enroll` | |
| `mfa.enrollment_confirmed` | P2 | `POST /api/admin/mfa/confirm` | |
| `mfa.disabled` | P2 | `POST /api/admin/mfa/disable` | |
| `brand.create` | P1 | `POST /api/admin/brands` | |
| `brand.update` | P1 | `PATCH /api/admin/brands/{brand_id}` | |
| `brand.deactivate` | P1 | `POST /api/admin/brands/{brand_id}/deactivate` | |
| `brand.reactivate` | P1 | `POST /api/admin/brands/{brand_id}/reactivate` | |
| `documents.moderate` | P1 | `POST /api/admin/documents/{document_id}/moderate` | |
| `job_postings.moderate` | P1 | `POST /api/admin/job-postings/{job_posting_id}/moderate` | |
| `questions.moderate` | P1 | `POST /api/admin/questions/{question_id}/moderate` | |
| `practice_audio.moderate` | P1 | `POST /api/admin/practice-audio/{recording_id}/moderate` | |
| `outreach.moderate` | P1 | `POST /api/admin/outreach/{message_id}/moderate` | |
| `portfolio.moderate` | P1 | `POST /api/admin/portfolio/{profile_id}/moderate` | |
| `interview_schedules.moderate` | P1 | `POST /api/admin/interview-schedules/{schedule_id}/moderate` | |
| `manual_job_entries.moderate` | P1 | `POST /api/admin/manual-job-entries/{entry_id}/moderate` | |
| `review_queue.decide` | P1 | `POST /api/admin/review-queue/{item_id}/decide` | |
| `feature_flags.mutate` | UNAVAILABLE | `PUT/POST/PATCH/DELETE /api/admin/feature-flags…` | `FEATURE_FLAGS_READ_ONLY` — no consumer. |
| `queues.retry_failed_job` | UNAVAILABLE | `POST /api/admin/queues/{name}/failed/{job_id}/retry` | `QUEUE_ADMIN_READ_ONLY`. |

## Must / must-not

- **Must** classify every live privileged mutation before it executes.
- **Must** require a caller-supplied `Idempotency-Key` for P1/P2/P3.
- **Must** fail closed (`405`) for unclassified and `UNAVAILABLE` operations.
- **Must not** enable `UNAVAILABLE` operations without a new contract revision and Security review.
- **Must not** invent `/api/desk` or an `org_id` tenancy filter (ADR 0019).
