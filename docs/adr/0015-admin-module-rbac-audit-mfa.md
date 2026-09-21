# 0015. RBAC, Audit Log, Feature Flags, and Support Impersonation (Admin Module)

- **Status:** Accepted
- **Date:** 2026-08-19

## Context
The Admin Module (`docs/admin-module-research.md`) needs: (1) a way to grant
narrower-than-superuser admin capabilities, (2) a tamper-evident record of
admin-initiated changes, (3) runtime config toggles without a redeploy, and
(4) a safe way for support staff to view the product as a specific user. None
of these map onto existing tables — `User.is_superuser` is a binary override,
`compliance.models.AuditLog` is a *candidate*-facing compliance trail (GDPR/DSAR
lineage), not an admin-write log, and there is no existing config-flag or
delegated-session table anywhere in the schema (§5 of `phase2_admin_module.md`).

## Decision
In each case below we chose the option that reuses or extends this repo's
existing primitives — `is_superuser`, the existing JWT/cookie auth path,
Postgres, Redis — **over** introducing a new, parallel mechanism:

1. **New storage, additive only**: the original 6 tables (`roles`, `permissions`,
   `role_permissions`, `admin_audit_logs`, `feature_flags`,
   `impersonation_sessions`) owned by a new
   `app/modules/admin/` module, plus 4 new nullable columns on `users`
   (`role_id`, `mfa_secret`, `mfa_enabled`, `mfa_enrolled_at`). No existing
   table is dropped, renamed, or has a column removed. The 2026-09-03
   hardening adds `privileged_idempotency_records` and additive audit,
   impersonation-session, and staff-invite fields through sequential
   revisions 063–066. Revision 065 requires a stop-the-world API maintenance
   window: every old API instance must stop serving invite creation, lookup,
   and redemption before revisions 065–066 are applied. Only digest-first
   code may start afterward. The migration backfills digests and retains safe
   active historical plaintext solely for restored-schema recovery by a
   hardened compatibility artifact; it is never permission to run a
   pre-hardening binary. Successful redemption, expiry cleanup, or
   acknowledged post-drain cleanup removes it. Cleanup is deliberately not an
   automatically applied migration.
   **Rollback contract:** a pre-hardening/old API binary must never serve
   staff-invite creation, lookup, or redemption against revision 065 or a
   restored schema. Rollback first stops and drains API/invite traffic. Traffic
   may resume only with a prebuilt artifact verified to preserve the current
   digest-first, recruiter-only, email-bound, revocation-aware implementation
   on the target schema and to pass invite-security smoke. If that artifact is
   unavailable, API/invite traffic stays stopped and operators roll forward.
   Artifact construction, traffic drain, and evidence are mandatory
   `INT-RELEASE` gates outside this repository.
2. **`is_superuser` is kept, not replaced.** `Role`-based permissions are
   additive grants checked only when `is_superuser` is false. Rationale:
   collapsing the two into one system on this PR would be a much larger,
   riskier change than the Admin Module needs, and every existing
   `require_superuser` call site keeps working unmodified (Decision 1,
   `phase2_admin_module.md` §4).
3. **A new `admin_audit_logs` table, not reuse of `compliance.AuditLog`.**
   Rationale: the compliance log's rows are legally-retained
   candidate-consent/erasure records; mixing admin-write events into it would
   both violate that table's single, well-defined purpose and risk
   accidentally subjecting admin logs to compliance retention/erasure rules
   meant for candidate data (§5 naming-collision check).
4. **Transactional explicit audit capture is the release guarantee.** Every
   successful privileged mutation and its one explicit `admin_audit_logs` row
   must commit in the same database transaction. New records require
   `request_id` and `outcome`; impersonated actions also retain the real actor,
   effective target, and impersonation-session ID. The existing fallback
   middleware remains anomaly detection only and never satisfies audit
   coverage. Audit rows default to 1,825-day retention and are append-only to
   application roles. Actor/session foreign keys restrict physical deletion
   rather than erasing attribution.
5. **Feature flags are DB-backed (Postgres), not env-var or LaunchDarkly.**
   Rationale: this repo already treats Postgres as its source of truth for
   mutable state judged worth auditing (Decision 8), and no external
   flag-vendor dependency exists today; adding one for this PR would violate
   "keep the change as small as the task allows." There is currently no
   business consumer, so flag mutations remain disabled until a real
   evaluation path and rollback owner exist.
6. **Impersonation uses a JWT claim plus a database session validated on every
   impersonated request.** The token retains `sub`, `jti`, and `imp`, but an
   impersonated request is accepted only while the matching
   `impersonation_sessions` row is active, unexpired, and unrevoked, the real
   actor remains active and still has `impersonation:start`, and the target is
   a roleless, non-superuser candidate. Scope is always `view_only`; mutations
   are denied except ending the session. Ending or revoking the session
   invalidates its JTI immediately. Normal sessions do not pay this extra
   lookup.
7. **MFA is required for every impersonation start.** An actor without an
   enrolled and verified TOTP cannot start impersonation. This records the
   behavior already enforced by `app/modules/admin/impersonation.py` and
   supersedes the earlier conditional-MFA wording.
8. **No new Docker service, container, or queue.** Admin endpoints run inside
   the existing `api` container; queue introspection is read-only against
   the existing Redis/RQ queues defined in `app/workers/queue.py`. Rationale:
   this repo's RQ queues already have a documented starvation risk and
   Postgres connection-pool sizing is already a known gap (`phase2_module1.md`
   §4, §12); an admin dashboard is exactly the kind of feature that should
   not add a new failure mode to either.
9. **Staff access is a coarse product door, followed by endpoint RBAC.**
   A user is staff when `is_superuser` is true or `role_id` is non-null.
   Staff-only route groups reject roleless candidates before their existing
   permission dependencies run; narrower `resource:action` checks remain in
   place and still fail closed. MFA remains available to verified candidates,
   and impersonation status/end remain outside the staff aggregator so an
   impersonated candidate can end the session; impersonation start retains
   its existing `impersonation:start` permission. Rationale: product access
   and operation authorization answer different questions and should remain
   composable rather than replacing one another.
10. **`team_owner` receives every existing Desk permission explicitly, not a
    wildcard or superuser equivalence.** The Product Doors migration lists all
    45 permission pairs present at its verified parent revision, requires
    those rows and the role to exist, and inserts only missing associations.
    It creates no new permission slug and does not change strict-superuser
    role assignment or costs policy. Migration bookkeeping records only the
    associations actually inserted, allowing downgrade to remove exactly
    those grants while preserving roles, permission rows, legacy owner
    grants, and any association that predated the migration. Rationale:
    explicit grants keep the owner role auditable as the Desk permission
    universe evolves without silently broadening RBAC into `is_superuser`.

## Tradeoffs

- Keeping `is_superuser` alongside RBAC (Decision 2) means the codebase now
  carries two overlapping authorization concepts instead of one unified
  model, **traded for** zero regression risk on every existing
  `require_superuser` call site and a much smaller PR than a full RBAC
  migration would be.
- A dedicated `admin_audit_logs` table (Decision 3) duplicates some shape
  with `compliance.AuditLog` **instead of** reusing it, **traded for**
  keeping the compliance log's legally-retained candidate-consent/erasure
  purpose uncontaminated by unrelated admin-write events.
- Transactional explicit audit capture (Decision 4) requires mutation services
  to share a transaction with the audit writer, **traded for** fail-closed,
  attributable evidence. Fallback rows remain useful anomaly signals but are
  not successful-operation evidence.
- DB-backed feature flags (Decision 5) mean flag reads cost a cached Redis
  round-trip **instead of** a free in-process env-var read, **traded for**
  runtime toggling without a redeploy and an audit trail on every flip.
- Session-validated impersonation (Decision 6) adds one database lookup to each
  impersonated request, **traded for** immediate expiry, revocation, and
  permission-change enforcement without slowing ordinary sessions.
- A coarse staff door adds one authorization layer before endpoint RBAC,
  **traded for** keeping roleless candidates out of operational products
  without weakening any permission-specific denial.
- Explicitly enumerating 45 owner grants requires a migration whenever the
  intended Desk permission universe grows, **traded for** reviewable least
  privilege and no wildcard semantics. The revision-specific bookkeeping
  table adds one small internal schema object while the revision is applied,
  **traded for** a downgrade that can distinguish newly inserted grants from
  pre-existing associations.

## Consequences

- `users` grows 4 nullable columns; existing rows get `role_id=NULL`,
  `mfa_enabled=false` on migration — no backfill required, no behavior change
  for any existing authenticated request until a role is explicitly assigned.
- Two audit-adjacent tables now exist in the schema
  (`compliance.audit_logs` and `admin.admin_audit_logs`) with similar-sounding
  names and deliberately different purposes — flagged here and in
  `phase2_admin_module.md` §5 specifically so a future agent does not merge
  them without reading this ADR first.
- `AdminAuditFallbackMiddleware` is retained only as an anomaly detector.
  Release evidence counts exactly one transactional explicit row for each
  successful privileged mutation.
- Impersonation JWTs carry a second identity claim and require a live session
  lookup. Candidate-only, view-only scope prevents privilege acquisition from
  the target identity.
- Product-level staff checks do not authorize an operation by themselves:
  non-superuser staff must still hold each endpoint's explicit permission.
  Roleless candidates retain verified-user flows such as MFA but cannot enter
  the Desk or OSINT operational surfaces.
- `team_owner` has the complete existing Desk permission inventory, including
  moderation, applications/interviews/manual jobs, AI supervision, LinkedIn
  sourcing/tasks, recruiter actions, brands, recruiter assignments, and the
  existing documents/portfolio/outreach/job-posting owner grants. Costs and
  strict-superuser role assignment remain superuser-only.

## Alternatives considered

- **Replace `is_superuser` with pure RBAC**: rejected — much larger blast
  radius than this module needs; every existing `require_superuser` call site
  would need auditing and possibly rewriting.
- **Reuse `compliance.AuditLog` for admin actions**: rejected — purpose
  collision, compliance-retention risk (§5).
- **LaunchDarkly / external flag vendor**: rejected — new external
  dependency with no existing precedent in this repo, for a feature Postgres
  already handles adequately at this scale.
- **Trust the impersonation JWT without a session lookup**: rejected — it
  cannot enforce immediate revocation, real-actor deactivation, or permission
  changes. Only impersonated requests incur the lookup.
- **Force MFA on all admin accounts**: rejected — out of this PR's authority;
  left as a natural policy follow-up once self-service MFA has shipped and
  been used for a while.
