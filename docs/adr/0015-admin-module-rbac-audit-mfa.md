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

1. **New storage, additive only**: 6 new tables (`roles`, `permissions`,
   `role_permissions`, `admin_audit_logs`, `feature_flags`,
   `impersonation_sessions`) owned by a new
   `app/modules/admin/` module, plus 4 new nullable columns on `users`
   (`role_id`, `mfa_secret`, `mfa_enabled`, `mfa_enrolled_at`). No existing
   table is dropped, renamed, or has a column removed.
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
4. **Best-effort DB-backed fallback audit capture** via
   `AdminAuditFallbackMiddleware`, in addition to explicit `record_admin_action()`
   calls in every mutating admin endpoint. Rationale: an audit log that
   silently misses writes because a developer forgot to call the helper is
   worse than one with an occasional low-detail `captured_by="fallback"` row.
   This is best-effort, not exactly-once: it runs after the response is
   built and can miss requests that crash before then — accepted as the
   right trade-off for an internal admin trail, not a compliance-grade
   ledger (Decision 2, `phase2_admin_module.md` §4).
5. **Feature flags are DB-backed (Postgres), not env-var or LaunchDarkly.**
   Rationale: this repo already treats Postgres as its source of truth for
   mutable state judged worth auditing (Decision 8), and no external
   flag-vendor dependency exists today; adding one for this PR would violate
   "keep the change as small as the task allows."
6. **Impersonation is JWT-claim-based (`imp` claim), not a separate session
   table read on every request.** The existing cookie-JWT auth path
   (`get_current_user_from_cookie`) decodes the optional `imp` claim once per
   request into `request.state.impersonated_by`; `impersonation_sessions` is
   the audit/expiry record, not the request-time lookup. Rationale: this
   avoids adding a DB round-trip to every authenticated request just to
   support a feature only support staff use.
7. **MFA (TOTP, `pyotp`) gates impersonation-start only when the *admin's own*
   MFA is enabled — it is not force-enabled for all admins in this PR.**
   Rationale: forcing MFA repo-wide is a policy decision this PR does not
   have the authority to make; the module instead makes MFA available
   self-service to any verified user and enforces it conditionally where the
   blast radius (viewing as another user) is highest.
8. **No new Docker service, container, or queue.** Admin endpoints run inside
   the existing `api` container; queue introspection is read-only against
   the existing Redis/RQ queues defined in `app/workers/queue.py`. Rationale:
   this repo's RQ queues already have a documented starvation risk and
   Postgres connection-pool sizing is already a known gap (`phase2_module1.md`
   §4, §12); an admin dashboard is exactly the kind of feature that should
   not add a new failure mode to either.

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
- Best-effort fallback audit capture (Decision 4) accepts occasional
  low-detail `captured_by="fallback"` rows and a small gap on
  requests that crash before the response is built, **traded for** not
  requiring every admin endpoint author to remember an explicit
  `record_admin_action()` call.
- DB-backed feature flags (Decision 5) mean flag reads cost a cached Redis
  round-trip **instead of** a free in-process env-var read, **traded for**
  runtime toggling without a redeploy and an audit trail on every flip.
- JWT-claim-based impersonation (Decision 6) means the access-token JWT
  shape is no longer strictly single-identity **instead of** adding a
  session-table lookup on every authenticated request, **traded for**
  avoiding a DB round-trip on the hot path for a feature only support staff
  use.

## Consequences

- `users` grows 4 nullable columns; existing rows get `role_id=NULL`,
  `mfa_enabled=false` on migration — no backfill required, no behavior change
  for any existing authenticated request until a role is explicitly assigned.
- Two audit-adjacent tables now exist in the schema
  (`compliance.audit_logs` and `admin.admin_audit_logs`) with similar-sounding
  names and deliberately different purposes — flagged here and in
  `phase2_admin_module.md` §5 specifically so a future agent does not merge
  them without reading this ADR first.
- `AdminAuditFallbackMiddleware` adds a small amount of per-request overhead
  (a path-prefix check) to every request through the `api` container, not
  just admin routes — accepted as negligible (§8.7 notes the exact check).
- Impersonation JWTs carry a second identity claim; any future JWT-parsing
  code elsewhere in the codebase that assumes exactly one identity per token
  must be updated to handle `imp` — flagged, not fixed pre-emptively, since no
  such code exists today (verified during this plan's research pass).

## Alternatives considered

- **Replace `is_superuser` with pure RBAC**: rejected — much larger blast
  radius than this module needs; every existing `require_superuser` call site
  would need auditing and possibly rewriting.
- **Reuse `compliance.AuditLog` for admin actions**: rejected — purpose
  collision, compliance-retention risk (§5).
- **LaunchDarkly / external flag vendor**: rejected — new external
  dependency with no existing precedent in this repo, for a feature Postgres
  already handles adequately at this scale.
- **Session-table-backed impersonation, read every request**: rejected —
  unnecessary DB round-trip on the hot path for a rarely-used feature; the
  JWT claim already carries the needed identity, and the session table exists
  for audit/expiry, not per-request lookup.
- **Force MFA on all admin accounts**: rejected — out of this PR's authority;
  left as a natural policy follow-up once self-service MFA has shipped and
  been used for a while.
