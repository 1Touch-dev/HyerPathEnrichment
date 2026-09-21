# 0021. Privileged-operation controls and replay safety

- **Status:** Accepted
- **Date:** 2026-09-03

## Context

Desk mutations can change access, assume another identity, retry work, or
alter runtime configuration. RBAC answers who may request an operation, but
does not provide recent authentication, deliberate confirmation, dual
control, atomic audit, or safe retry semantics. No approved four-eyes
workflow or feature-flag consumer currently exists.

## Decision

We chose **one server-enforced operation classification and idempotency
contract** over route-specific UI conventions:

1. `P0` is read-only and requires normal authentication and authorization.
2. `P1` is a bounded, reversible mutation. It requires authorization,
   transactional explicit audit, and an `Idempotency-Key`.
3. `P2` exposes sensitive data or assumes identity. It adds recent step-up
   authentication; impersonation start uses a verified TOTP challenge and
   creates a candidate-only, `view_only` session.
4. `P3` is destructive or grants privilege. It adds typed confirmation to
   P2. Staff invitations are recruiter-only by default; inviting an admin,
   team owner, support user, or arbitrary role is unavailable.
5. `P4` requires independent approval/four-eyes control. Because no approved
   workflow, approver policy, or durable approval ledger exists, every P4
   operation is unavailable. We do not approximate it with a checkbox or a
   second confirmation.

Feature-flag mutations remain disabled until a real consumer and rollback
owner exist. Queue names and operations will be allowlisted; queue-wide purge
and other unclassified destructive actions remain unavailable.

Every privileged mutation uses a caller-supplied `Idempotency-Key`.
Persistence is atomic with the operation and is unique on
`(caller_user_id, operation, idempotency_key)`. A canonical request hash
distinguishes an equivalent replay from key reuse: an equivalent replay
returns the stored status/body, while a changed payload returns
`409 IDEMPOTENCY_KEY_REUSED`. In-progress duplicates do not execute a second
mutation. Records retain the request ID, response, creation/completion times,
and expiry. Expiry permits key reuse only after the retention policy removes
the old record; records are never silently overwritten.

Every successful privileged mutation and exactly one explicit audit record
commit in the same database transaction. New audit records require
`request_id` and `outcome`. The fallback middleware is anomaly detection,
not evidence of a successful operation. The default admin-audit retention is
1,825 days.

## Tradeoffs

- Per-request database checks for impersonation and atomic idempotency writes
  add latency, traded for immediate revocation and replay safety.
- P3 typed confirmation creates interaction friction, traded for deliberate
  destructive or privilege-granting actions.
- Keeping P4 unavailable blocks useful operations, traded for not claiming
  dual control before an independently authorized workflow exists.
- Persisting replay responses consumes storage and requires redaction,
  traded for deterministic retries without repeating side effects.

## Consequences

- Revisions `063` through `066` add the audit, impersonation, invite, and
  idempotency schema foundation on both SQLite and PostgreSQL.
- Revisions 065–066 require an API maintenance window. Operators stop and
  verify the drain of every old API instance before migration, then start only
  digest-first/new-redemption code and pass health/security smoke before
  acknowledged plaintext cleanup. Mixed API versions are unsupported.
- Rollback never authorizes a pre-hardening/old API binary to serve invite
  creation, lookup, or redemption against revision 065 or a restored schema.
  API/invite traffic remains drained unless `INT-RELEASE` has a prebuilt,
  target-schema-compatible artifact that retains the hardened digest-first,
  recruiter-only, email-bound, revocation-aware behavior and passes the same
  security smoke. Without that artifact, roll forward while traffic remains
  stopped. The repository cannot verify deployed artifacts or load-balancer
  state; both are mandatory release evidence, not claimed code enforcement.
- Endpoint/service enforcement lands separately and must fail closed until
  its operation class is implemented.
- Stored request hashes and responses must exclude raw invite tokens, email,
  TOTP values, LinkedIn URLs, raw queue arguments, and exception payloads.
- A future P4 workflow requires a new ADR defining approvers, separation of
  duties, expiry, cancellation, and audit behavior before enabling any P4
  operation.
