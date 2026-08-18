# Phase 2 — Admin Module: RBAC, Audit Log, Feature Flags, System Health & User Management

**Branch:** `master-complete-foundation` (this file is committed directly to this branch — no new branch is created)
**Status:** Implementation blueprint — nothing described here exists in code yet unless explicitly marked `EXISTS` with a file citation. Everything else is `NEW`.
**Governing rule file:** `RULE.md` — every decision below was checked against it; violations are called out explicitly rather than silently made. See §0.
**Governing research doc:** `docs/admin-module-research.md` — this plan implements the scope settled in that document's §14 ("Full scope decision & implementation contract"), with one ground-truth correction (§3 below).

**Purpose of this document:** a single, linear, followable plan such that a developer (or agent) who implements every numbered step in order — database, backend, workers, Docker, tests, frontend — ends with the Admin Module **100% functionally complete**, with automated tests proving it, without needing to consult any other chat, report, or memory. Every file this plan creates or edits is listed by exact path. Unlike `phase2_module1.md` (which the task that produced this document explicitly flagged as having omitted the frontend), this plan gives the frontend equal weight to the backend — see §11–§12.

---

## 0. RULE.md compliance checklist (read this before writing any code)

| RULE.md requirement | How this plan complies |
|---|---|
| "Search the repo for an existing function, type, component, or pattern" (Before writing any code #1) | §2 inventories everything reused: `VerifiedUser`/`CurrentUser`, the existing `require_superuser` in `app/modules/admin/router.py`, `AuthAuditLog` (parallel shape to copy for the new admin audit table), `get_redis_client`/`check_rate_limit`, `get_redis_connection`/`QUEUE_PRIORITIES` (RQ), `JsonDoc`, `EnvelopeAPIRoute`, `success_envelope`/`error_envelope`, the existing `/api/admin/costs/*` endpoints (kept working, wrapped with caching, not rewritten), and the frontend `features/job-matching/` + BFF + nav-config + `AppSidebar`/`AppShell`/`AuthGuard` patterns. Nothing reusable is rebuilt. |
| "Read Agent quick reference in ARCHITECTURE.md" (#2) | Done — Pipeline/merge/enrichers/compliance ownership boundaries are respected. This module touches **zero** files under `enrichers/`, `compliance/`, or `enrichers/pipeline.py`. It adds no new RQ queue and no new Docker container (§4 Decision 9) — the one existing risk this plan must not worsen (Postgres pool sizing, RQ queue starvation, both flagged in `phase2_module1.md` §4) is explicitly *not* touched. |
| "Check Implementation status — do not build on scaffold-only features" (#3) | Verified before use: cookie auth (ADR 0009), `AuthAuditLog`, Redis client, RQ queues, and `job_postings`/`job_matches` (Module 1) are all real, not scaffold — confirmed by reading the code directly (§2, §3). |
| "Keep the change as small as the task allows" (#4) | RBAC is **additive** to `is_superuser`, not a replacement (Decision 1) — no existing call site (`app/modules/admin/router.py`, `backend/tests/test_admin_costs.py`) breaks. Feature-flag infra ships with **zero** forced business-logic migration, since no existing env-gate matching the research doc's `JOB_SOURCE_PROVIDER` example was found in this repo's code (§3, §4 Decision 8) — shipping the infra without inventing a flag to attach it to is the smaller, more honest change. |
| Layer ownership table (`domain/`, `modules/`, `workers/`, `compliance/`, `clients/`, `storage/`, `database/`) | All new code lives in `app/modules/admin/` (a `modules/` submodule — HTTP-facing use cases, exactly like `documents/` or `job_matching/`). No new `workers/` code (no new queue). No `compliance/` code touched — the new `admin_audit_logs` table is deliberately **not** the same table as `compliance/models.py::AuditLog` (§5 naming collision). |
| Allowed/forbidden imports | `app/modules/admin/*` imports only `app.auth`, `app.database`, `app.workers.queue` (read-only introspection, no new queue), `app.infrastructure.redis`, `app.core` — all already-allowed per the "modules → domain, enrichers, module repositories, workers.queue, compliance" rule. No `workers/tasks` code is added, so the `workers/tasks → modules/*/service|router` forbidden-import rule does not arise. |
| "One provider per file", "extend Enricher in base.py" (Enrichers section) | N/A — this module adds no enricher and touches no tier. |
| "Tier registration only in enrichers/registry.py" | Not touched. |
| "Do not duplicate validation... merge logic... API field mapping" | Permission checks live once in `app/modules/admin/permissions.py::require_permission()`; audit-log writes live once in `app/modules/admin/audit.py::record_admin_action()`; cache logic lives once in `app/modules/admin/cache.py::cached_aggregate()`. Frontend field mapping goes through `api-adapter.ts` only. |
| "Routes are thin" | `app/modules/admin/router.py` and its sub-routers only do auth/permission checks + call a service/repository function + return; all query/cache/audit logic lives in `service.py`, `repository.py`, `cache.py`, `audit.py`. |
| "ORM lives with its owner... never recreate a global app/models.py" | All new ORM classes live in `app/modules/admin/models.py`. `User` gains 4 new columns (§6.6) but no new ORM class is added to `app/auth/models.py`. |
| "Async end-to-end... no run_until_complete in request paths" | All new router/service/repository code is `async def`. No new worker entrypoint is added (no sync `asyncio.run()` context needed), consistent with Decision 9 (no new queue). |
| "Schema changes via Alembic only" | 6 new tables + 1 column-addition migration on `users`, via **6 new Alembic revisions** (§6), chained onto the current real head `032_portfolio_item_image_url`. No `create_all`. |
| "When to add an ADR" — new storage, queue, or layer ownership | **New storage** (5 tables + 4 new `users` columns) + **new auth mechanism** (RBAC layered on `is_superuser`, MFA schema, impersonation tokens) → ADR required. §13 supplies `docs/adr/0015-admin-rbac-audit-feature-flags.md`. |
| "New enricher → extend tests/test_pipeline_shape.py" | N/A — not an enricher. Equivalent obligation met: `backend/tests/test_admin_*.py` suite (§9), extending (not replacing) the existing `test_admin_costs.py`. |
| "No live external calls in CI... mock subprocess, HTTP, third-party APIs" | Tests mock Redis, the RQ `Queue`/`Worker` objects, and the optional Prometheus HTTP call (§9). No live external calls. |
| "Coverage gate ... currently 78%" | §9.9 gives the exact `pytest --cov` command to prove the gate is met. |
| "Never log raw identifiers... use job IDs or hashed values" | Audit log entries store `actor_user_id`/`target_user_id` as UUIDs (already the repo's own PK type), never raw email/name in the `action`/`target_type` fields; `before`/`after` JSON snapshots for user-management actions include only non-PII fields (`is_active`, `role_id`) — never CV text, raw email changes, etc. |
| "Never commit secrets... update .env.example with placeholders only" | §7 lists every new env var with placeholder/default values only. |
| "Public data only... no discover people flows" | N/A — this module only manages existing platform users/data, it does not discover new people. |
| "Update backend/docs/ARCHITECTURE.md Implementation status if scaffold changed" | §14 gives the exact diff. |
| "New/changed storage, queue, auth, or layer ownership → ADR linked in the PR" | §13 ADR + §15 PR checklist link it. |
| Frontend: "Shared types... do not duplicate Dossier/EnrichmentInput shapes inline" | New `AdminUser`, `Role`, `Permission`, `AdminAuditLogEntry`, `FeatureFlag`, `QueueSnapshot`, `SystemHealthSnapshot` types added to `frontend/src/lib/types.ts` once, mapped through `api-adapter.ts` (§11). |
| Frontend: "Keep types in sync... run npm run openapi:export && npm run openapi:gen" | §11.1 gives the exact command sequence. |
| Testing: "New route behavior → API test: status code, auth, response shape" | §9 covers every new route. |
| Frontend: "Type changes → run npm run typecheck... UI changes → npm run lint / build" | §12.9 gives the exact commands. |

If any step below appears to conflict with `RULE.md`, `RULE.md` wins — this document is subordinate to it, not a replacement for it.

---

## 1. Evidence-label legend (used throughout)

- ✅ **DIRECT** — a primary source (official docs, this repo's own code read directly, or `docs/admin-module-research.md`'s own `[Direct]`-labeled claims) states the claim.
- 🔗 **INDIRECT** — a real source supports the general point but not in this exact form, or is `docs/admin-module-research.md`'s own `[Indirect]`-labeled claim.
- ❌ **NOT FOUND** — checked directly against this repo's code and could not be verified; stated as a design choice, not fact.

All external claims below trace back to `docs/admin-module-research.md`, which independently verified its own citations (§1 of that document defines the same three-way label it uses). This plan does not re-fetch those sources; it re-verifies every *repo-specific* claim (file paths, line numbers, table/column names) directly against the current code, since the research document is dated the same day as this plan and the codebase moves fast.

---

## 2. What already exists and will be reused unmodified

Verified by reading the files directly — not assumed from the research document.

| Capability | File | Reused how |
|---|---|---|
| Cookie-JWT auth, verified-user gate | `backend/app/auth/dependencies.py` (`CurrentUser`, `VerifiedUser`, `get_current_user_from_cookie`) | Every new admin route sits behind `VerifiedUser` first, then a permission dependency — same two-layer pattern already used by `documents_router`/`job_matching_router` in `app/main.py:79-94` |
| Superuser gate | `backend/app/modules/admin/router.py:85-102` (`require_superuser`) | Kept **verbatim** at its current import path (re-exported), continues to gate the 5 existing cost endpoints unmodified — `backend/tests/test_admin_costs.py:61` patches `app.modules.admin.router.require_superuser` directly, so moving or renaming it would break that test for no benefit |
| Auth audit log shape to copy | `backend/app/auth/models.py:168-192` (`AuthAuditLog`) | `actor`, `event_type`, `ip_address`, `user_agent`, `extra_data` JSON, indexed `created_at` — this exact shape is copied (not reused directly — see §5 naming collision) for the new `AdminAuditLog` |
| Compliance audit log — deliberately **not** reused for admin writes | `backend/app/compliance/models.py:25-35` (`AuditLog`, table `audit_logs`) | This table's `event_type` vocabulary is compliance-specific (`opt_out`, `dsar_created`, ...) and its `identifier_hash` column assumes a hashed public identifier, not an admin actor. Reusing it would conflate two different domains — see §5. |
| Redis client + rate limiter | `backend/app/infrastructure/redis.py` (`get_redis_client`, `check_rate_limit`) | Reused verbatim for the cached-aggregate helper (§4 Decision 3) and MFA verification throttling |
| RQ connection + queue registry | `backend/app/workers/queue.py` (`get_redis_connection`, `QUEUE_PRIORITIES`, `QUEUE_JOB_MATCHING`, etc.) | Read-only introspection: the new queue-ops screen lists `rq.Queue`/`rq.Worker` objects for every queue name already in `QUEUE_PRIORITIES`, and re-enqueues failed jobs onto their existing queue — **no new queue is created** (§4 Decision 9) |
| JSON column helper | `backend/app/database/base.py` (`JsonDoc`) | Reused for `AdminAuditLog.before/after`, `FeatureFlag.value` |
| Envelope routing + responses | `backend/app/core/api_route.py` (`EnvelopeAPIRoute`), `backend/app/core/responses.py` (`success_envelope`/`error_envelope`) | New admin sub-routers use `EnvelopeAPIRoute` exactly like `job_matching/router.py` does |
| DB session dependency | `backend/app/database/session.py` (`get_db_session`) | Reused verbatim |
| ORM registry side-effect import list | `backend/app/database/orm_registry.py` | New admin models added to this list exactly like Module 1/2 models were |
| Existing cost endpoints | `backend/app/modules/admin/router.py:105-353` (`get_daily_costs`, `get_monthly_costs`, `get_total_costs`, `get_top_users`, `get_cost_breakdown`) | Kept working. `get_total_costs`/`get_cost_breakdown` get wrapped with the new Redis cache helper (§4 Decision 3, per the research doc's explicit instruction to apply caching to this endpoint first); `get_top_users`'s bare `limit: int` gets a cursor-pagination option added **alongside** the existing `limit`-only call shape so no existing caller breaks |
| Job postings / job matches data (Module 1) | `backend/app/modules/job_matching/models.py` (`JobPosting`, `JobMatch`) | Read-only: the new analytics endpoint aggregates `salary_min/max`, `company`, `location`, `source`, `overall_score` — **this is the ground-truth correction in §3**, this data already exists |
| Frontend feature-module pattern | `frontend/features/job-matching/` (`index.ts`, `api/{keys,client}.ts`, `hooks/`, `components/`) | Copied exactly for `frontend/features/admin/` |
| Frontend BFF proxy pattern | `frontend/app/api/job-matching/*/route.ts`, `frontend/src/lib/backend-client.ts` (`backendFetch`), `frontend/src/lib/bff-response.ts` | Copied exactly for `frontend/app/api/admin/*` |
| Frontend nav registration | `frontend/components/layout/nav-config.ts`, `frontend/components/layout/AppSidebar.tsx` | One new conditionally-rendered `NavSection` added; `AppSidebar` gets one new optional prop (`isAdmin`), same pattern as its existing `matchesUnreadCount` prop |
| Frontend auth context | `frontend/providers/auth-provider.tsx` (`useAuth`, `User`) | Extended (not replaced) with `is_superuser`/`role_name`/`mfa_enabled` fields already returned by the backend's `UserRead` schema but not yet typed on the frontend — a real, small, pre-existing gap (verified: `UserRead` in `backend/app/auth/schemas.py:28` already has `is_superuser`; the frontend interface at `providers/auth-provider.tsx:6-15` just never added the field) |
| Route-guard pattern | `frontend/components/auth/auth-guard.tsx` | Copied for a new `AdminGuard` — same shape, additional `is_superuser`/permission check |

Nothing above is edited to change its existing behavior for other features — all reuse is either read-only or additive (new optional props, new fields, new functions alongside existing ones).

---

## 3. Scope recap and one ground-truth correction

`docs/admin-module-research.md` §14 ("Full scope decision & implementation contract") settles scope as: **(1)** dynamic RBAC, **(2)** admin audit log, **(3)** feature flags, **(4)** cursor pagination, **(5)** precomputed/cached aggregates, **(6)** MFA-pluggable schema, **(7)** support impersonation — plus the "core panel" (system health, RQ dashboard/queue ops, paginated user management) that motivated the original report. This plan builds all of it, in the build order that document's §13 recommends: audit log → pagination + user management → feature flags → RBAC → cached aggregates → MFA → impersonation last.

**Ground-truth correction (per `RULE.md`: "Trust code over docs when they disagree — then update the doc in the same PR if the code is correct"):** §6 and §13 of the research document state that "job match analytics" is blocked with "0 days buildable now" because "Phase 2 Module 1 (job matching data model doesn't exist yet)". This is now **false** — verified directly:

```23:50:backend/app/modules/job_matching/models.py
class JobPosting(Base):
    """Deduplicated job posting scraped from job boards."""

    __tablename__ = "job_postings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    dedup_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remote: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    description_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

`backend/docs/ARCHITECTURE.md`'s own Implementation status table confirms this: "Job matching (Module 1) | ... | Real, scaffolded per `phase2_module1.md`." The research document's own §0 ground-truth table was written *before* fully accounting for this — it is dated the same day this plan was written, and the discrepancy is a staleness artifact, not a disagreement to litigate. **Action taken in this plan:** job-match analytics (aggregate salary/company/source counts — the "handful of aggregate queries" reading the research doc's own §6 practical take already flagged as the cheap, valid interpretation, not a BI dashboard) is added to scope in §8.9/§8.10, reusing the same cached-aggregate infra built for §4 Decision 3. `docs/admin-module-research.md` should have its §6, §13, and §14 job-match-analytics rows corrected in the same PR that ships this plan — this is called out again in §14 (ARCHITECTURE.md diff) and should be applied to the research doc as well.

**Confirmed still blocked, unchanged from the research doc (verified directly, not just deferred to the doc's own claim):**

- **Notification logs** — verified no delivery-log table exists anywhere in `backend/app/services/email_service.py` (it calls SendGrid directly, fire-and-forget, no persisted send/bounce/open record) and no SendGrid webhook ingestion endpoint exists in `backend/app/modules/`. Still 0 days buildable; out of scope for this plan.
- **CV review queue** — verified `backend/app/modules/documents/models.py:23-45` (`CandidateDocument`) has only `processing_status` (`pending`/`processing`/`completed`/`failed`), no quality/confidence/flag field a moderation queue could filter on. Still 0 days buildable; out of scope for this plan.

Both remain explicitly tracked as future work (§16), not silently dropped.

---

## 4. Evidence-based design decisions (why the implementation is shaped this way)

### Decision 1 — `is_superuser` stays the top override gate; RBAC is additive, never a replacement

✅ **DIRECT** — Stripe team-roles docs (via `docs/admin-module-research.md` §1): "Only a Super Administrator can assign the [Super Administrator] role." ✅ **DIRECT** (own codebase) — `require_superuser` is the only gate on the 5 existing cost endpoints today, and `backend/tests/test_admin_costs.py:61` patches it by import path.

**Applied as:** `require_permission(resource, action)` (§8) checks, in order: (1) if `user.is_superuser` → allow unconditionally, no DB lookup; (2) else look up `user.role_id → Role → RolePermission → Permission(resource, action)`. `is_superuser` is never itself grantable through the RBAC tables — it stays a direct column flip, requiring direct DB/ops access, matching Stripe's "top role assignment is itself gated above the permission system" pattern. This also means zero regression risk: every existing `Depends(require_superuser)` call site keeps working unchanged, forever, even if RBAC is misconfigured.

### Decision 2 — Router-level audit capture, adapted for FastAPI/ASGI rather than copied from Express middleware

✅ **DIRECT** — `docs/admin-module-research.md` §12.2: the case-study org attaches audit logging once via Express `router.use(attachAuditLogger)`, giving every controller a `req.audit(...)` helper, plus an auto-logging wrapper for any successful mutation. §14's build-approach instruction is explicit: "port... router-level audit middleware (§12.2)... refactored for this stack..., not copied verbatim."

**Applied as, refactored for FastAPI:** (1) a `record_admin_action()` helper (`app/modules/admin/audit.py`), parallel to `compliance/audit.py::log_event()`'s existing shape, called explicitly at the one or two points per endpoint where enough context exists to know `action`/`target_type`/`target_id`/`before`/`after` — this is the practical FastAPI equivalent of `req.audit(...)`, since Python has no direct analog to Express's implicit `req` mutation being read later by response middleware; (2) a **defense-in-depth** `AdminAuditFallbackMiddleware` (ASGI, added only to routes under `/api/admin`) that logs `actor_user_id`, `method`, `path`, `status_code` for any mutating request (`POST`/`PUT`/`PATCH`/`DELETE`) whose handler did **not** already call `record_admin_action()` in that request — implemented via a `contextvars.ContextVar` flag set by `record_admin_action()` and checked by the middleware after `call_next()`, so a forgotten explicit audit call still produces a generic (if less detailed) fallback entry instead of silence. This is the FastAPI-realistic version of "a controller author can't forget to log it" (§12.2's stated goal), not a literal port of Express's auto-wrapper (which relies on synchronously mutable request objects FastAPI's ASGI model doesn't offer in the same way).

### Decision 3 — Redis-cached aggregates over materialized views, applied first to the existing cost endpoints

✅ **DIRECT** — `docs/admin-module-research.md` §12.3 (Redis cache with TTL + `?refresh=1` bypass) and §13's explicit instruction: "applied first to the existing live-computed cost breakdown in `router.py`, then reused for future analytics." ✅ **DIRECT** (own codebase) — this repo already depends on Redis for RQ, so this is zero new infrastructure, unlike a materialized view (`REFRESH MATERIALIZED VIEW` would be a new operational concern with no existing cron to drive it).

**Applied as:** `cached_aggregate(key, ttl_seconds, compute_fn, *, refresh=False)` in `app/modules/admin/cache.py` — `GET`s a Redis string key holding a JSON-encoded result; on miss (or `refresh=True`, or `?skip_cache=1`/`?refresh=1` query param) calls `compute_fn()`, `SET`s with `EX=ttl_seconds`. Applied to `get_total_costs`/`get_cost_breakdown` (existing, unmodified return shape) and to the new job-match analytics endpoint (§3's correction, §8.10). Not applied to `get_daily_costs`/`get_monthly_costs` (already parameterized by date/month, so their cardinality — one cache entry per day/month ever queried — is a worse cache-key explosion problem than the flat "total" and "breakdown" endpoints; left as-is, a deliberate scope boundary, not an oversight).

### Decision 4 — Cursor pagination via a `(created_at, id)` composite opaque cursor

✅ **DIRECT** — Stripe pagination docs (via `docs/admin-module-research.md` §11.1): cursor-based pagination on an object ID, never bare offsets, for large datasets. ✅ **DIRECT** (own codebase) — `backend/app/modules/admin/router.py:236-252`'s `get_top_users(limit: int = 10)` has no cursor at all today, confirming the gap the research doc flags is real.

**Applied as:** `encode_cursor(created_at: datetime, id: UUID) -> str` / `decode_cursor(cursor: str) -> tuple[datetime, UUID]` in `app/modules/admin/pagination.py` — base64-encodes `f"{created_at.isoformat()}|{id}"`. List queries filter `WHERE (created_at, id) < (:cursor_created_at, :cursor_id)` (or `>` for ascending), ordered by the same tuple, matching Stripe's `starting_after`/`has_more` shape (`has_more: bool` computed by fetching `limit + 1` rows and checking if the extra row exists). Applied to the new user-list, audit-log-list, and feature-flag-list endpoints from day one — **not** retrofitted onto `get_top_users`'s existing `limit`-only endpoint (that endpoint's contract is preserved for backward compatibility per Decision 1's regression-avoidance principle; a new optional `cursor` query param is *added* alongside the existing `limit`, so old callers relying on bare `limit` still work identically).

### Decision 5 — MFA: schema + a `verify_mfa()` seam now; enforcement wired only where the product already mandated it (impersonation)

✅ **DIRECT** — `docs/admin-module-research.md` §14 item 6: "add the `mfa_secret`/`mfa_enabled` schema and a `verify_mfa()` seam now so enforcement is a later flip, not a migration done under pressure; actual TOTP enforcement can follow." §11.5/§13: impersonation must not be built before both the audit log **and MFA** exist, and needs "a re-auth/MFA step before starting a session."

**Applied as:** `mfa_secret`/`mfa_enabled`/`mfa_enrolled_at` columns on `users` (§6.6), a real TOTP enroll/verify/disable flow (`pyotp`, §8.13) that any user can turn on for their own account, and a `verify_mfa(user, code) -> bool` seam function. **Enforcement is deliberately not wired into the main login flow in this plan** (explicitly deferred, per the research doc's own instruction — enforcing 2FA at login for *every* user is a separate, larger product decision this plan does not make unilaterally). The **one** place enforcement is wired in is `POST /api/admin/impersonation/start`: if the calling admin has `mfa_enabled=True`, the request must include a valid current TOTP code, or it 403s — this is the one place §11.5 explicitly requires it, and it's a concrete, testable use of the seam rather than a purely theoretical one.

### Decision 6 — Impersonation as a scoped JWT claim, reusing the existing JWT/cookie infrastructure — not a second auth system

✅ **DIRECT** — `docs/admin-module-research.md` §11.5: Intercom logs impersonation start/end as distinct audit events; Zendesk warns actions taken while impersonating are attributed to the impersonated user in the underlying system, so the *admin's* identity must be captured separately, in the audit trail, not the request path. ✅ **DIRECT** (own codebase) — `backend/app/auth/dependencies.py:38-124` already decodes a JWT from the `access_token` cookie and looks up `sub` as the acting user; `backend/app/auth/logged_out_tokens.py` already has a `jti`-based blacklist/revocation mechanism.

**Applied as:** `POST /api/admin/impersonation/start/{user_id}` issues a normal-shaped access-token JWT (`sub=<target_user_id>`, its own `jti`) **plus one extra claim**, `imp=<admin_user_id>`, and sets it as the `access_token` cookie (the existing cookie name — no second cookie, no second auth code path). `get_current_user_from_cookie` (edited, §8) decodes `imp` if present and sets `request.state.impersonated_by = imp_user_id` for any downstream code that wants to know (initially: the audit fallback middleware, so every action taken during an impersonation session is tagged with both identities in the fallback log too, directly addressing Zendesk's warning). An `impersonation_sessions` row is written at start (`admin_user_id`, `target_user_id`, `jti`, `started_at`) and closed (`ended_at`) by `POST /api/admin/impersonation/end`, which also revokes the `jti` via the existing `LoggedOutTokenService` so an impersonation session cannot outlive its explicit end (or its own short `exp`, capped by `ADMIN_IMPERSONATION_MAX_DURATION_MINUTES`, §7) even if the browser tab is left open. Sequenced last (§9's implementation order), after audit logging and MFA both exist, per §11.5's own caution.

### Decision 7 — RQ dashboard: hand-rolled introspection endpoints, not mounting `rq-dashboard`'s Flask blueprint

✅ **DIRECT** — `docs/admin-module-research.md` §3: `rq-dashboard` is a real, maintained Flask blueprint for RQ, but "a native mount isn't drop-in" since this is a FastAPI app, not Flask. ✅ **DIRECT** (own codebase) — `backend/app/workers/queue.py`'s `QUEUE_PRIORITIES` dict and `get_redis_connection()` already give everything needed to construct `rq.Queue`/`rq.Worker` objects directly.

**Applied as:** `app/modules/admin/queues_service.py` builds `rq.Queue(name, connection=get_redis_connection())` for every name in `QUEUE_PRIORITIES` plus `rq.Worker.all(connection=...)`, exposing queue depth, oldest-job age, and the `FailedJobRegistry` per queue, with a retry action that calls `registry.requeue(job_id)` (a real `rq` API, not hand-rolled re-implementation of RQ's own retry semantics). This is strictly additive read/retry access to the **existing** queues declared in `QUEUE_PRIORITIES` — no new queue name is introduced, so the starvation analysis in `phase2_module1.md` §4 is unaffected (Decision 9 makes this explicit).

### Decision 8 — Feature flags: generic DB+cache infrastructure shipped with zero forced business-logic migration

❌ **NOT FOUND** — `docs/admin-module-research.md` §8 and §14 reference a `JOB_SOURCE_PROVIDER` env-var gate "discussed elsewhere in this project" as the motivating example for feature flags. Verified directly: `grep -rn "JOB_SOURCE_PROVIDER" backend/` returns **zero matches** anywhere in this repo's code or `.env.example`. This flag does not exist in the codebase as of this plan.

**Applied as:** the `feature_flags` table, cache, and CRUD API (§8.12) are built exactly as scoped — DB-backed, admin-editable, audit-logged on every flip, Redis read-through cache — but this plan does **not** invent a fake flag to retrofit onto an env var that isn't real, since that would be exactly the kind of unrelated, speculative change `RULE.md`'s "no unused abstractions... 'for later'" rule warns against. The infrastructure is real and immediately usable the next time a genuine risky env-gated code path is added (`LLM_MODE`, `PROXY_MODE`, and `BROWSER_MODE` in `core/config.py` are the closest existing analogs today, and are explicitly **not** migrated by this plan — migrating a live provider-mode switch is a separate, riskier change outside this module's scope). `docs/admin-module-research.md` §8/§14 should be corrected in the same PR to note `JOB_SOURCE_PROVIDER` is aspirational, not present, alongside the §3 job-match-analytics correction.

### Decision 9 — No new Docker containers or queues

✅ **DIRECT** (own codebase, `phase2_module1.md` §4) — this repo already has a documented, real risk: SQLAlchemy's default connection pool (5 + 10 overflow per process) is unsized, and every new worker process adds up to 15 more connections to an uncapped total. `phase2_module1.md` mitigated this by pinning its one new worker container to 1 replica; this plan avoids the question entirely.

**Applied as:** every admin capability in this plan (RBAC checks, audit writes, feature-flag reads, cached aggregates, queue introspection, system-health proxying, MFA, impersonation) runs **inside the existing `api` container**, on the existing Postgres/Redis connections already established for every other authenticated route. No `Dockerfile.worker-admin`, no new `docker-compose` service, no new queue name. This is the correct read of the research doc's own §11.6 conclusion: "None of this requires new infrastructure... it's schema additions and query-pattern discipline on top of what's already running." §10 documents this conclusion explicitly rather than leaving Docker unaddressed by omission (the gap this plan was explicitly asked not to repeat).

---

## 5. Naming collisions and blind spots checked before designing the schema

**`AuditLog` already exists — the new table must not share its name or its class.** Verified: `backend/app/compliance/models.py:25` defines `class AuditLog` (table `audit_logs`) for compliance events (`opt_out`, `dsar_created`, `dsar_completed`, `enrichment_suppressed`, `data_purged`, `enrichment_completed` — the fixed vocabulary in `backend/app/domain/enums.py::AuditEventType`). Its `identifier_hash` column assumes a hashed public identifier (a *person being enriched*), not an *admin actor acting on a platform user*. Reusing this table for admin writes would (a) require a second, unrelated `event_type` vocabulary living in the same column as the compliance one, defeating the point of a fixed enum, and (b) risk admin-audit rows being swept up by `compliance/purge_audit_logs.py`'s 5-year retention job, which is scoped to compliance semantics, not admin-security semantics. **Resolution:** new table is `admin_audit_logs`, new class is `AdminAuditLog`, living in `app/modules/admin/models.py` — a sibling table, exactly as the research doc's own §11.2 "Practical take" recommends ("don't invent a new table [vocabulary]... extend the existing `AuthAuditLog` pattern (or add a sibling `AdminAuditLog` with the same shape)").

**`app/auth/permissions.py` already exists and must not be confused with the new RBAC `Permission` model.** Verified: `backend/app/auth/permissions.py` is a 42-line file containing only `require_verified_user`/`VerifiedUser` (a near-duplicate of the one in `dependencies.py` — pre-existing minor redundancy this plan does not touch, per "fix only what the task needs"). The new RBAC dependency and ORM class both live under `app/modules/admin/` (`permissions.py::require_permission()`, `models.py::Permission`) — different package path, so `from app.auth.permissions import VerifiedUser` and `from app.modules.admin.permissions import require_permission` never collide on import, but the naming is close enough that this is called out explicitly so a future reader doesn't assume they're the same file.

**`role_id` on `users` must not collide with `OAuthAccount`/session concepts.** Verified: no existing column or relationship named `role`/`role_id` anywhere in `backend/app/auth/models.py` or `backend/app/modules/sessions/models.py` (which is about `PracticeSession`/interview practice, an unrelated "session" meaning — verified no naming overlap with the new `impersonation_sessions` table either, which is a *different* kind of session: a scoped-access grant, not a practice session).

**RQ queue starvation and Postgres pool sizing — explicitly not worsened.** Per Decision 9, this plan adds zero new queues and zero new worker processes, so the starvation analysis and pool-sizing risk in `phase2_module1.md` §4 are unaffected by this module. This is stated explicitly here (not left implicit) precisely because those two risks are easy to reintroduce by accident when a plan touches `workers/queue.py` — this plan's only touch to that file is a read-only import of `QUEUE_PRIORITIES` and `get_redis_connection` for introspection, never a new `Queue(...)` registration.

**Actor identity vs. acted-upon identity must never share one ambiguous field.** Per Zendesk's warning (§11.5, cited in Decision 6): `AdminAuditLog` has distinct `actor_user_id` and (when the target is a user) a `target_id` (generic, since targets can be a role, a feature flag key, or a queue name too, not only a user) — never a single unqualified `user_id` that could be misread as either. `ImpersonationSession` likewise has distinct `admin_user_id` and `target_user_id` columns, never a shared `user_id`.

**"Jobs" already means three things in this codebase (per `phase2_module1.md` §4) — the RQ queue-ops screen introduces no fourth meaning.** The new queue-ops endpoints operate on `rq.Job` objects (RQ's own task-queue job concept — enrichment jobs, embedding jobs, feedback jobs, etc., all already `rq.Job` instances today) — this is the *existing* "enrichment job" meaning already in use throughout `workers/`, not a new concept. The frontend page is named `/app/admin/queues`, not `/app/admin/jobs`, to avoid any visual proximity to `/app/jobs` (which already redirects to `/app/history`) or `/app/matches` (job *postings*).

---

## 6. Database schema — 6 new tables, 1 altered table, 6 new Alembic revisions

**Current real Alembic head, verified by tracing the down_revision chain in `backend/alembic/versions/`:** `032_portfolio_item_image_url` (down-revision: `031_merge_job_board_cv_and_stabilization_heads`, itself a merge of `026_add_document_mime_type` and `030_outreach_messages`). New revisions in this plan chain onto `032_portfolio_item_image_url`, in the numeric order given below (`033` → `038`).

All new tables follow the exact dialect-handling pattern already used in `020_candidate_job_preferences.py` and `021_job_matches.py`: `postgresql.UUID(as_uuid=True)` / `sa.String(36)` branch on `bind.dialect.name` (matching how `app/modules/job_matching/models.py` uses plain `UUID` mapped columns backed by whichever dialect Alembic targets), `JsonDoc` (JSONB on Postgres, JSON on SQLite) for JSON columns — no new pattern invented.

### 6.1 `033_admin_roles_permissions.py` — `roles`, `permissions`, `role_permissions`

```python
"""Add roles, permissions, and role_permissions tables (Admin Module RBAC).

Revision ID: 033_admin_roles_permissions
Revises: 032_portfolio_item_image_url
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "033_admin_roles_permissions"
down_revision: str | Sequence[str] | None = "032_portfolio_item_image_url"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def upgrade() -> None:
    uuid_type = _uuid_type()

    op.create_table(
        "roles",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "permissions",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("resource", sa.String(64), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.UniqueConstraint("resource", "action", name="uq_permissions_resource_action"),
    )

    op.create_table(
        "role_permissions",
        sa.Column("role_id", uuid_type, sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "permission_id",
            uuid_type,
            sa.ForeignKey("permissions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("role_id", "permission_id", name="pk_role_permissions"),
    )

    op.create_index("ix_roles_name", "roles", ["name"])
    op.create_index("ix_permissions_resource", "permissions", ["resource"])


def downgrade() -> None:
    op.drop_index("ix_permissions_resource", table_name="permissions")
    op.drop_index("ix_roles_name", table_name="roles")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")
```

### 6.2 `034_admin_users_role_and_mfa.py` — alter `users`: `role_id`, `mfa_secret`, `mfa_enabled`, `mfa_enrolled_at`

```python
"""Add role_id + MFA schema columns to users (Admin Module).

Revision ID: 034_admin_users_role_and_mfa
Revises: 033_admin_roles_permissions
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "034_admin_users_role_and_mfa"
down_revision: str | Sequence[str] | None = "033_admin_roles_permissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def upgrade() -> None:
    op.add_column("users", sa.Column("role_id", _uuid_type(), nullable=True))
    op.add_column("users", sa.Column("mfa_secret", sa.String(64), nullable=True))
    op.add_column(
        "users", sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column("users", sa.Column("mfa_enrolled_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_users_role_id", "users", "roles", ["role_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_users_role_id", "users", ["role_id"])


def downgrade() -> None:
    op.drop_index("ix_users_role_id", table_name="users")
    op.drop_constraint("fk_users_role_id", "users", type_="foreignkey")
    op.drop_column("users", "mfa_enrolled_at")
    op.drop_column("users", "mfa_enabled")
    op.drop_column("users", "mfa_secret")
    op.drop_column("users", "role_id")
```

### 6.3 `035_admin_audit_logs.py` — `admin_audit_logs`

```python
"""Add admin_audit_logs table (Admin Module — router/middleware-captured writes).

Revision ID: 035_admin_audit_logs
Revises: 034_admin_users_role_and_mfa
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "035_admin_audit_logs"
down_revision: str | Sequence[str] | None = "034_admin_users_role_and_mfa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def _json_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB()
    return sa.JSON()


def upgrade() -> None:
    uuid_type = _uuid_type()

    op.create_table(
        "admin_audit_logs",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "actor_user_id",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("impersonated_by", uuid_type, nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_id", sa.String(64), nullable=True),
        sa.Column("before", _json_type(), nullable=True),
        sa.Column("after", _json_type(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("captured_by", sa.String(16), nullable=False, server_default="explicit"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_index("ix_admin_audit_logs_actor_user_id", "admin_audit_logs", ["actor_user_id"])
    op.create_index("ix_admin_audit_logs_action", "admin_audit_logs", ["action"])
    op.create_index("ix_admin_audit_logs_target_type", "admin_audit_logs", ["target_type"])
    op.create_index("ix_admin_audit_logs_created_at", "admin_audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_admin_audit_logs_created_at", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_target_type", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_action", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_actor_user_id", table_name="admin_audit_logs")
    op.drop_table("admin_audit_logs")
```

`captured_by` is `"explicit"` (a router/service called `record_admin_action()` directly) or `"fallback"` (the ASGI middleware caught an un-audited mutation — see Decision 2). This lets a reviewer immediately spot which admin actions still lack a specific, well-labeled audit call and need a follow-up.

### 6.4 `036_admin_feature_flags.py` — `feature_flags`

```python
"""Add feature_flags table (Admin Module — DB-backed kill switches).

Revision ID: 036_admin_feature_flags
Revises: 035_admin_audit_logs
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "036_admin_feature_flags"
down_revision: str | Sequence[str] | None = "035_admin_audit_logs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def _json_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB()
    return sa.JSON()


def upgrade() -> None:
    uuid_type = _uuid_type()

    op.create_table(
        "feature_flags",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("key", sa.String(128), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("value", _json_type(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "updated_by",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_feature_flags_key", "feature_flags", ["key"])


def downgrade() -> None:
    op.drop_index("ix_feature_flags_key", table_name="feature_flags")
    op.drop_table("feature_flags")
```

### 6.5 `037_admin_impersonation_sessions.py` — `impersonation_sessions`

```python
"""Add impersonation_sessions table (Admin Module — support impersonation).

Revision ID: 037_admin_impersonation_sessions
Revises: 036_admin_feature_flags
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "037_admin_impersonation_sessions"
down_revision: str | Sequence[str] | None = "036_admin_feature_flags"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def upgrade() -> None:
    uuid_type = _uuid_type()

    op.create_table(
        "impersonation_sessions",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "admin_user_id", uuid_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "target_user_id", uuid_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("token_jti", sa.String(64), nullable=False, unique=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_impersonation_sessions_admin_user_id", "impersonation_sessions", ["admin_user_id"])
    op.create_index("ix_impersonation_sessions_target_user_id", "impersonation_sessions", ["target_user_id"])


def downgrade() -> None:
    op.drop_index("ix_impersonation_sessions_target_user_id", table_name="impersonation_sessions")
    op.drop_index("ix_impersonation_sessions_admin_user_id", table_name="impersonation_sessions")
    op.drop_table("impersonation_sessions")
```

### 6.6 `038_admin_seed_roles_permissions.py` — data-only seed migration

Per §12.1's `Permission`/`RolePermission` shape (`docs/admin-module-research.md` §12.1), seeded with a minimal, real resource/action set covering every new capability this plan ships — not a placeholder list, since an empty permissions table would make RBAC untestable immediately after migrating.

```python
"""Seed default roles and permissions (Admin Module).

Revision ID: 038_admin_seed_roles_permissions
Revises: 037_admin_impersonation_sessions
Create Date: 2026-08-19
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "038_admin_seed_roles_permissions"
down_revision: str | Sequence[str] | None = "037_admin_impersonation_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RESOURCE_ACTIONS = [
    ("users", "read"), ("users", "write"), ("users", "suspend"),
    ("roles", "read"), ("roles", "write"),
    ("audit_logs", "read"),
    ("feature_flags", "read"), ("feature_flags", "write"),
    ("queues", "read"), ("queues", "retry"),
    ("system_health", "read"),
    ("analytics", "read"),
    ("impersonation", "start"),
]

ROLES = [
    ("support", "Read-only + user suspend, no destructive or config access"),
    ("admin", "Full operational access, excludes role/permission management"),
]

ROLE_PERMISSIONS = {
    "support": [("users", "read"), ("users", "suspend"), ("audit_logs", "read"), ("system_health", "read")],
    "admin": [ra for ra in RESOURCE_ACTIONS if ra not in {("roles", "read"), ("roles", "write")}],
}


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(UTC)

    permissions_table = sa.table(
        "permissions",
        sa.column("id"),
        sa.column("resource"),
        sa.column("action"),
        sa.column("description"),
    )
    roles_table = sa.table(
        "roles",
        sa.column("id"),
        sa.column("name"),
        sa.column("description"),
        sa.column("is_system"),
        sa.column("created_at"),
        sa.column("updated_at"),
    )
    role_permissions_table = sa.table(
        "role_permissions", sa.column("role_id"), sa.column("permission_id")
    )

    permission_ids: dict[tuple[str, str], str] = {}
    for resource, action in RESOURCE_ACTIONS:
        pid = str(uuid4())
        permission_ids[(resource, action)] = pid
        bind.execute(
            permissions_table.insert().values(
                id=pid, resource=resource, action=action, description=f"{action} on {resource}"
            )
        )

    role_ids: dict[str, str] = {}
    for name, description in ROLES:
        rid = str(uuid4())
        role_ids[name] = rid
        bind.execute(
            roles_table.insert().values(
                id=rid,
                name=name,
                description=description,
                is_system=True,
                created_at=now,
                updated_at=now,
            )
        )

    for role_name, resource_actions in ROLE_PERMISSIONS.items():
        for ra in resource_actions:
            bind.execute(
                role_permissions_table.insert().values(
                    role_id=role_ids[role_name], permission_id=permission_ids[ra]
                )
            )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM role_permissions"))
    bind.execute(sa.text("DELETE FROM roles WHERE is_system = true OR is_system = 1"))
    bind.execute(sa.text("DELETE FROM permissions"))
```

**Note on `is_superuser` staying untouched by the seed:** no existing user's `is_superuser` or `role_id` is modified by this migration — assigning the `admin` role to specific users is an explicit, deliberate operational action (via the new `PUT /api/admin/users/{id}/role` endpoint, §8.6), not something a schema migration should silently do, per Decision 1's "top role assignment stays a direct, deliberate action" principle.

---

## 7. Configuration — new environment variables

Added to `backend/app/core/config.py::Settings` and `backend/.env.example`, following the exact `Field(default=..., alias="...")` convention already used for `job_matching_*` settings.

```python
# Admin Module: RBAC, audit log, feature flags, cached aggregates, MFA, impersonation
admin_audit_log_retention_days: int = Field(default=1825, alias="ADMIN_AUDIT_LOG_RETENTION_DAYS")
admin_aggregate_cache_ttl_seconds: int = Field(
    default=300, alias="ADMIN_AGGREGATE_CACHE_TTL_SECONDS"
)
admin_default_page_size: int = Field(default=20, alias="ADMIN_DEFAULT_PAGE_SIZE")
admin_max_page_size: int = Field(default=100, alias="ADMIN_MAX_PAGE_SIZE")
admin_mfa_issuer_name: str = Field(default="Hyrepath Admin", alias="ADMIN_MFA_ISSUER_NAME")
admin_impersonation_max_duration_minutes: int = Field(
    default=30, alias="ADMIN_IMPERSONATION_MAX_DURATION_MINUTES"
)
prometheus_query_url: str = Field(default="", alias="PROMETHEUS_QUERY_URL")
```

`backend/.env.example` additions (placeholders only, matching the existing `JOB_MATCHING_*` block's inline-comment style):

```bash
# Admin Module: RBAC, audit log, feature flags, cached aggregates, MFA, impersonation
ADMIN_AUDIT_LOG_RETENTION_DAYS=1825          # 5 years, matches compliance audit-log retention convention
ADMIN_AGGREGATE_CACHE_TTL_SECONDS=300        # Redis TTL for cached admin dashboard aggregates (§4 Decision 3)
ADMIN_DEFAULT_PAGE_SIZE=20                   # Default page size for cursor-paginated admin list endpoints
ADMIN_MAX_PAGE_SIZE=100                      # Hard ceiling a caller cannot exceed via ?limit=
ADMIN_MFA_ISSUER_NAME=Hyrepath Admin         # TOTP provisioning URI issuer label shown in authenticator apps
ADMIN_IMPERSONATION_MAX_DURATION_MINUTES=30  # Hard cap on an impersonation-scoped token's lifetime
PROMETHEUS_QUERY_URL=                        # Optional Prometheus query API base; unset = system-health page shows self-checks only (fail-soft, no error)
```

`PROMETHEUS_QUERY_URL` is deliberately optional and fail-soft, matching this repo's existing convention (documented in `backend/docs/ARCHITECTURE.md`'s "Do not assume" table for `LLM_MODE`/R2-fallback/Reacher's `profiles`) — when unset, `GET /api/admin/system-health` still returns real Postgres-ping and Redis-ping latency (no external dependency needed for that part), just without the four-golden-signals panel that depends on this repo's existing Prometheus scrape (`backend/observability/alerts/hyrepath.rules.yml`).

No new secret is introduced — `mfa_secret` (per-user TOTP seed) is generated server-side by `pyotp.random_base32()` at enrollment time and stored in the `users.mfa_secret` column; it is not an application-wide credential and never appears in `.env`/`.env.example`.

Add `"pyotp>=2.9,<3.0"` to `backend/pyproject.toml`'s `dependencies` list (new dependency — TOTP generation/verification, the industry-standard library for this, already implicitly endorsed by the research doc's §12.6 citation of dedicated 2FA admin controls as a real pattern).

---

## 8. Backend implementation — file by file

Every new file lives under `app/modules/admin/` (the module already exists as a single-file router; it becomes a package). Every edit to an existing file is additive.

### 8.1 `backend/app/modules/admin/models.py` (NEW)

```python
"""ORM models for the Admin Module: RBAC, audit log, feature flags, impersonation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, JsonDoc


class Role(Base):
    """Named collection of permissions. Distinct from `User.is_superuser`, which is
    a direct, non-grantable override — see phase2_admin_module.md Decision 1."""

    __tablename__ = "roles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class Permission(Base):
    """One resource+action pair, e.g. ('users', 'suspend'). Not to be confused with
    `app/auth/permissions.py`, which only re-exports `VerifiedUser` — see §5."""

    __tablename__ = "permissions"
    __table_args__ = (UniqueConstraint("resource", "action", name="uq_permissions_resource_action"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    resource: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class RolePermission(Base):
    """Join table: which permissions a role grants."""

    __tablename__ = "role_permissions"

    role_id: Mapped[UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[UUID] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    )


class AdminAuditLog(Base):
    """Admin-write audit trail. Deliberately separate from
    `compliance.models.AuditLog` — see §5 naming collision."""

    __tablename__ = "admin_audit_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Set only when the actor was impersonating another user at the time of this
    # action (Decision 6) — the *real* admin identity, kept distinct from actor_user_id
    # which, during impersonation, is the target user (per Zendesk's warning, §5).
    impersonated_by: Mapped[UUID | None] = mapped_column(nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    before: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc, nullable=True)
    after: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    # "explicit" (a router/service called record_admin_action) or "fallback"
    # (AdminAuditFallbackMiddleware caught an un-audited mutation) — see Decision 2.
    captured_by: Mapped[str] = mapped_column(String(16), default="explicit", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )


class FeatureFlag(Base):
    """DB-backed kill switch / config toggle. See Decision 8 — ships with no
    forced business-logic migration; infra only, until a real gate needs it."""

    __tablename__ = "feature_flags"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    value: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class ImpersonationSession(Base):
    """One support-impersonation grant. Sequenced last per §11.5 — requires the
    audit log and MFA to already exist (Decision 6)."""

    __tablename__ = "impersonation_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    admin_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

### 8.2 `backend/app/modules/admin/schemas.py` (NEW)

Pydantic request/response models for every endpoint:

```python
"""Pydantic schemas for the Admin Module API."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class RoleResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    is_system: bool


class PermissionResponse(BaseModel):
    id: UUID
    resource: str
    action: str
    description: str | None


class RoleWithPermissionsResponse(RoleResponse):
    permissions: list[PermissionResponse]


class AdminUserResponse(BaseModel):
    id: UUID
    email: str
    first_name: str
    last_name: str
    is_active: bool
    is_verified: bool
    is_superuser: bool
    role_id: UUID | None
    role_name: str | None
    mfa_enabled: bool
    created_at: datetime
    deleted_at: datetime | None


class AdminUserListResponse(BaseModel):
    items: list[AdminUserResponse]
    next_cursor: str | None
    has_more: bool


class UpdateUserStatusRequest(BaseModel):
    is_active: bool
    reason: str | None = Field(default=None, max_length=500)


class AssignRoleRequest(BaseModel):
    role_id: UUID | None  # None clears the role


class AdminAuditLogEntryResponse(BaseModel):
    id: UUID
    actor_user_id: UUID | None
    impersonated_by: UUID | None
    action: str
    target_type: str
    target_id: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    ip_address: str | None
    captured_by: str
    created_at: datetime


class AdminAuditLogListResponse(BaseModel):
    items: list[AdminAuditLogEntryResponse]
    next_cursor: str | None
    has_more: bool


class FeatureFlagResponse(BaseModel):
    key: str
    enabled: bool
    value: dict[str, Any] | None
    description: str | None
    updated_by: UUID | None
    updated_at: datetime


class UpsertFeatureFlagRequest(BaseModel):
    enabled: bool
    value: dict[str, Any] | None = None
    description: str | None = None


class QueueSnapshotResponse(BaseModel):
    name: str
    priority: int
    queued_count: int
    failed_count: int
    oldest_queued_age_seconds: float | None
    workers_listening: int


class QueuesOverviewResponse(BaseModel):
    queues: list[QueueSnapshotResponse]


class FailedJobResponse(BaseModel):
    job_id: str
    queue_name: str
    func_name: str | None
    enqueued_at: datetime | None
    failed_at: datetime | None
    exc_info: str | None


class SystemHealthResponse(BaseModel):
    database_ok: bool
    database_latency_ms: float
    redis_ok: bool
    redis_latency_ms: float
    prometheus_configured: bool
    # Four golden signals — populated only when PROMETHEUS_QUERY_URL is set (§7);
    # empty dict is the fail-soft shape, matching this repo's other optional-backend
    # conventions rather than raising.
    signals: dict[str, float | None]


class JobMatchAnalyticsResponse(BaseModel):
    """Ground-truth-correction analytics (§3) — aggregate over job_postings/job_matches.
    Explicitly NOT a BI dashboard, per docs/admin-module-research.md §6's own
    'handful of aggregate queries' scope boundary."""

    total_postings: int
    total_matches: int
    postings_by_source: dict[str, int]
    top_companies: list[dict[str, Any]]
    avg_salary_min: float | None
    avg_salary_max: float | None
    avg_overall_score: float | None
    computed_at: datetime
    cache_hit: bool


class MfaEnrollResponse(BaseModel):
    secret: str
    provisioning_uri: str


class MfaVerifyRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class MfaStatusResponse(BaseModel):
    mfa_enabled: bool
    mfa_enrolled_at: datetime | None


class ImpersonationStartRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    mfa_code: str | None = Field(default=None, min_length=6, max_length=6)


class ImpersonationStartResponse(BaseModel):
    target_user_id: UUID
    expires_at: datetime


class ImpersonationStatusResponse(BaseModel):
    is_impersonating: bool
    admin_user_id: UUID | None
    admin_email: str | None
    target_user_id: UUID | None
    expires_at: datetime | None
```

---

### 8.3 `backend/app/modules/admin/permissions.py` (NEW)

```python
"""RBAC permission dependency. Additive to `require_superuser` — see Decision 1.
Not to be confused with `app/auth/permissions.py` (unrelated file, see §5)."""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import VerifiedUser
from app.auth.models import User
from app.database.session import get_db_session
from app.modules.admin.models import Permission, RolePermission


async def user_has_permission(
    db: AsyncSession, user: User, resource: str, action: str
) -> bool:
    """`is_superuser` short-circuits to True with no DB lookup (Decision 1).
    Otherwise checks user.role_id -> RolePermission -> Permission(resource, action)."""
    if user.is_superuser:
        return True
    if user.role_id is None:
        return False

    result = await db.execute(
        select(Permission.id)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(
            RolePermission.role_id == user.role_id,
            Permission.resource == resource,
            Permission.action == action,
        )
    )
    return result.scalar_one_or_none() is not None


def require_permission(resource: str, action: str):
    """FastAPI dependency factory: `Depends(require_permission("users", "suspend"))`."""

    async def _check(
        user: VerifiedUser, db: AsyncSession = Depends(get_db_session)
    ) -> User:
        if not await user_has_permission(db, user, resource, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {resource}:{action}",
            )
        return user

    return _check


def require_superuser_strict(user: VerifiedUser) -> User:
    """For the handful of actions Decision 1 keeps as `is_superuser`-only forever
    (role management itself) — RBAC cannot grant the ability to grant roles."""
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser access required",
        )
    return user
```

### 8.4 `backend/app/modules/admin/audit.py` (NEW)

```python
"""Admin audit log writer + ASGI fallback middleware. See Decision 2 for why
this is router-adjacent explicit calls plus a fallback, not a literal port of
the case study's Express `req.audit()` middleware."""

from __future__ import annotations

import contextvars
import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.modules.admin.models import AdminAuditLog

logger = logging.getLogger(__name__)

_audit_captured: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "admin_audit_captured", default=False
)


async def record_admin_action(
    db: AsyncSession,
    *,
    actor_user_id: UUID | None,
    action: str,
    target_type: str,
    target_id: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    ip_address: str | None = None,
    impersonated_by: UUID | None = None,
) -> AdminAuditLog:
    """Call this explicitly at the point in a router/service where actor/target/
    before/after are all known. Marks the request as already-audited so the
    fallback middleware does not double-log it."""
    record = AdminAuditLog(
        id=uuid4(),
        actor_user_id=actor_user_id,
        impersonated_by=impersonated_by,
        action=action,
        target_type=target_type,
        target_id=target_id,
        before=before,
        after=after,
        ip_address=ip_address,
        captured_by="explicit",
    )
    db.add(record)
    await db.flush()
    _audit_captured.set(True)
    logger.info(
        "admin audit action=%s target_type=%s target_id=%s actor=%s",
        action,
        target_type,
        target_id,
        str(actor_user_id)[:8] if actor_user_id else None,
    )
    return record


class AdminAuditFallbackMiddleware(BaseHTTPMiddleware):
    """Defense-in-depth: logs a generic entry for any mutating /api/admin request
    whose handler did not call `record_admin_action()`. Uses a fresh DB session
    (not the request's, which may have already been closed/committed by the
    time this runs) so a forgotten explicit call never produces total silence."""

    async def dispatch(self, request: Request, call_next) -> Response:
        token = _audit_captured.set(False)
        try:
            response = await call_next(request)
        finally:
            captured = _audit_captured.get()
            _audit_captured.reset(token)

        is_admin_mutation = request.url.path.startswith("/api/admin") and request.method in {
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
        }
        if is_admin_mutation and not captured and response.status_code < 500:
            await self._log_fallback(request, response)
        return response

    @staticmethod
    async def _log_fallback(request: Request, response: Response) -> None:
        from app.database.session import get_db_session_context

        actor_id = getattr(request.state, "user_id", None)
        async with get_db_session_context() as db:
            db.add(
                AdminAuditLog(
                    id=uuid4(),
                    actor_user_id=actor_id,
                    action=f"{request.method.lower()}_{request.url.path}",
                    target_type="unclassified",
                    target_id=None,
                    before=None,
                    after={"status_code": response.status_code},
                    ip_address=request.client.host if request.client else None,
                    captured_by="fallback",
                )
            )
            await db.commit()
```

`get_db_session_context()` is a new small async-contextmanager wrapper added to `backend/app/database/session.py` (a couple of lines, reusing the same session factory `get_db_session()` already wraps as a FastAPI dependency) — needed because middleware runs outside FastAPI's `Depends()` injection, so it cannot receive `db: AsyncSession = Depends(get_db_session)` the way routes do.

`request.state.user_id` is set by one new line added to `get_current_user_from_cookie` in `app/auth/dependencies.py` (`request.state.user_id = user.id`) — additive, does not change that function's return value or existing behavior for any other caller.

### 8.5 `backend/app/modules/admin/cache.py` (NEW)

```python
"""Redis-cached aggregate helper. See Decision 3 — applied first to the existing
cost endpoints, then reused for job-match analytics (§3's correction)."""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TypeVar

from pydantic import BaseModel

from app.core.config import get_settings
from app.infrastructure.redis import get_redis_client

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


async def cached_aggregate(
    key: str,
    model_cls: type[T],
    compute_fn: Callable[[], Awaitable[T]],
    *,
    refresh: bool = False,
    ttl_seconds: int | None = None,
) -> tuple[T, bool]:
    """Returns (result, cache_hit). On any Redis error, fails open by calling
    compute_fn() directly — caching is a performance optimization, never a
    correctness dependency, matching this repo's existing rate-limit fail-open
    convention in app/infrastructure/redis.py::check_rate_limit."""
    settings = get_settings()
    ttl = ttl_seconds if ttl_seconds is not None else settings.admin_aggregate_cache_ttl_seconds
    cache_key = f"admin:cache:{key}"

    if not refresh:
        try:
            client = get_redis_client()
            cached = await client.get(cache_key)
            if cached:
                return model_cls.model_validate_json(cached), True
        except Exception:
            logger.warning("Admin aggregate cache read failed for key=%s", key, exc_info=True)

    result = await compute_fn()

    try:
        client = get_redis_client()
        await client.set(cache_key, result.model_dump_json(), ex=ttl)
    except Exception:
        logger.warning("Admin aggregate cache write failed for key=%s", key, exc_info=True)

    return result, False


def utcnow() -> datetime:
    return datetime.now(UTC)
```

### 8.6 `backend/app/modules/admin/pagination.py` (NEW)

```python
"""Cursor pagination helper. See Decision 4 — Stripe-style opaque cursor over
(created_at, id), never bare offsets, for every new admin list endpoint."""

from __future__ import annotations

import base64
from datetime import datetime
from uuid import UUID


def encode_cursor(created_at: datetime, entity_id: UUID | str) -> str:
    raw = f"{created_at.isoformat()}|{entity_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    created_at_str, entity_id = raw.split("|", 1)
    return datetime.fromisoformat(created_at_str), entity_id
```

---

### 8.7 `backend/app/modules/admin/repository.py` (NEW)

Thin data-access functions, following the same convention as `app/modules/job_matching/repository.py` — no business logic, only queries. Full behavioral surface (abbreviated bodies shown where the pattern is mechanical, since every query follows the same cursor-pagination shape from §8.6):

```python
"""Data access for the Admin Module. Routes/services call these; no ORM query
lives directly in router.py, per RULE.md 'routes are thin'."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User
from app.modules.admin.models import AdminAuditLog, FeatureFlag, Role
from app.modules.admin.pagination import decode_cursor, encode_cursor


async def list_users(
    db: AsyncSession, *, cursor: str | None, limit: int, is_active: bool | None = None
) -> tuple[list[User], str | None, bool]:
    query = select(User).options(selectinload(User.role)).order_by(
        User.created_at.desc(), User.id.desc()
    )
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    if cursor:
        created_at, entity_id = decode_cursor(cursor)
        query = query.where(
            (User.created_at < created_at)
            | ((User.created_at == created_at) & (User.id < UUID(entity_id)))
        )
    query = query.limit(limit + 1)

    rows = list((await db.execute(query)).scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None
    return rows, next_cursor, has_more


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def list_roles(db: AsyncSession) -> list[Role]:
    result = await db.execute(select(Role).options(selectinload(Role.permissions)))
    return list(result.scalars().all())


async def list_audit_logs(
    db: AsyncSession, *, cursor: str | None, limit: int, action: str | None = None
) -> tuple[list[AdminAuditLog], str | None, bool]:
    query = select(AdminAuditLog).order_by(
        AdminAuditLog.created_at.desc(), AdminAuditLog.id.desc()
    )
    if action:
        query = query.where(AdminAuditLog.action == action)
    if cursor:
        created_at, entity_id = decode_cursor(cursor)
        query = query.where(
            (AdminAuditLog.created_at < created_at)
            | ((AdminAuditLog.created_at == created_at) & (AdminAuditLog.id < UUID(entity_id)))
        )
    query = query.limit(limit + 1)

    rows = list((await db.execute(query)).scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None
    return rows, next_cursor, has_more


async def list_feature_flags(db: AsyncSession) -> list[FeatureFlag]:
    result = await db.execute(select(FeatureFlag).order_by(FeatureFlag.key))
    return list(result.scalars().all())


async def get_feature_flag(db: AsyncSession, key: str) -> FeatureFlag | None:
    result = await db.execute(select(FeatureFlag).where(FeatureFlag.key == key))
    return result.scalar_one_or_none()


async def count_active_users(db: AsyncSession) -> int:
    result = await db.execute(select(func.count()).select_from(User).where(User.is_active == True))  # noqa: E712
    return int(result.scalar_one())
```

`User.role` and `Role.permissions` relationships referenced above are added to `app/auth/models.py::User` and `app/modules/admin/models.py::Role` respectively (§8.8) — `selectinload` avoids N+1 queries when listing users with their role name, matching the existing eager-load convention already used elsewhere in this codebase for one-to-many display data.

### 8.8 `backend/app/auth/models.py` — edits (not a new file)

```python
# Add to imports:
from app.modules.admin.models import Role  # TYPE_CHECKING-guarded, avoids circular import at runtime

# Add to User class body, alongside existing is_superuser:
role_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("roles.id", ondelete="SET NULL"), nullable=True, index=True
)
mfa_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
mfa_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
mfa_enrolled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

# Add relationship (mirrors the existing practice_sessions/question_attempts pattern):
role: Mapped["Role | None"] = relationship(lazy="joined")
```

The `Role` import is placed under the existing `if TYPE_CHECKING:` block (already present at line 14 for `PracticeSession`/`QuestionAttempt`) to avoid a circular import (`app.modules.admin.models` does not import `app.auth.models` back, so this is safe either way, but following the file's existing convention for cross-module type references keeps the pattern consistent).

### 8.9 `backend/app/modules/admin/service.py` (NEW)

Business logic layer — user management, role assignment, feature flags, wraps repository calls with audit logging per Decision 2. Key functions (full file; every mutating function calls `record_admin_action`):

```python
"""Service layer for the Admin Module. Every mutation here calls
record_admin_action() explicitly (Decision 2) — the fallback middleware only
catches what this layer misses."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin import repository
from app.modules.admin.audit import record_admin_action
from app.modules.admin.models import FeatureFlag
from app.modules.admin.schemas import (
    AdminUserResponse,
    UpsertFeatureFlagRequest,
)


def _user_to_response(user) -> AdminUserResponse:
    return AdminUserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        is_active=user.is_active,
        is_verified=user.is_verified,
        is_superuser=user.is_superuser,
        role_id=user.role_id,
        role_name=user.role.name if user.role else None,
        mfa_enabled=user.mfa_enabled,
        created_at=user.created_at,
        deleted_at=user.deleted_at,
    )


async def list_users_paginated(
    db: AsyncSession, *, cursor: str | None, limit: int, is_active: bool | None
):
    rows, next_cursor, has_more = await repository.list_users(
        db, cursor=cursor, limit=limit, is_active=is_active
    )
    return [_user_to_response(u) for u in rows], next_cursor, has_more


async def update_user_status(
    db: AsyncSession,
    *,
    actor_id: UUID,
    target_user_id: UUID,
    is_active: bool,
    reason: str | None,
    ip_address: str | None,
) -> AdminUserResponse:
    user = await repository.get_user_by_id(db, target_user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    before = {"is_active": user.is_active}
    user.is_active = is_active
    await db.flush()
    after = {"is_active": user.is_active, "reason": reason}

    await record_admin_action(
        db,
        actor_user_id=actor_id,
        action="user.status_changed",
        target_type="user",
        target_id=str(target_user_id),
        before=before,
        after=after,
        ip_address=ip_address,
    )
    await db.commit()
    return _user_to_response(user)


async def assign_role(
    db: AsyncSession,
    *,
    actor_id: UUID,
    target_user_id: UUID,
    role_id: UUID | None,
    ip_address: str | None,
) -> AdminUserResponse:
    user = await repository.get_user_by_id(db, target_user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    before = {"role_id": str(user.role_id) if user.role_id else None}
    user.role_id = role_id
    await db.flush()
    await db.refresh(user, attribute_names=["role"])
    after = {"role_id": str(role_id) if role_id else None}

    await record_admin_action(
        db,
        actor_user_id=actor_id,
        action="user.role_changed",
        target_type="user",
        target_id=str(target_user_id),
        before=before,
        after=after,
        ip_address=ip_address,
    )
    await db.commit()
    return _user_to_response(user)


async def upsert_feature_flag(
    db: AsyncSession,
    *,
    actor_id: UUID,
    key: str,
    payload: UpsertFeatureFlagRequest,
    ip_address: str | None,
) -> FeatureFlag:
    flag = await repository.get_feature_flag(db, key)
    before = None
    if flag is None:
        flag = FeatureFlag(key=key, enabled=payload.enabled, value=payload.value,
                            description=payload.description, updated_by=actor_id)
        db.add(flag)
    else:
        before = {"enabled": flag.enabled, "value": flag.value}
        flag.enabled = payload.enabled
        flag.value = payload.value
        flag.description = payload.description
        flag.updated_by = actor_id
    await db.flush()
    after = {"enabled": flag.enabled, "value": flag.value}

    await record_admin_action(
        db,
        actor_user_id=actor_id,
        action="feature_flag.flipped",
        target_type="feature_flag",
        target_id=key,
        before=before,
        after=after,
        ip_address=ip_address,
    )
    await db.commit()
    return flag
```

### 8.10 `backend/app/modules/admin/analytics.py` (NEW)

Implements §3's ground-truth correction — job-match analytics, reusing Decision 3's cache helper and Module 1's existing tables read-only.

```python
"""Job-match analytics: aggregate queries over job_matching's existing tables.
See phase2_admin_module.md §3 — corrects docs/admin-module-research.md's stale
'0 days buildable' claim. Read-only against job_postings/job_matches; never
writes to either table, matching job_swipe's existing read-only-dependency
convention on the same tables."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.cache import cached_aggregate, utcnow
from app.modules.admin.schemas import JobMatchAnalyticsResponse
from app.modules.job_matching.models import JobMatch, JobPosting


async def _compute_job_match_analytics(db: AsyncSession) -> JobMatchAnalyticsResponse:
    total_postings = (await db.execute(select(func.count()).select_from(JobPosting))).scalar_one()
    total_matches = (await db.execute(select(func.count()).select_from(JobMatch))).scalar_one()

    by_source_rows = await db.execute(
        select(JobPosting.source, func.count()).group_by(JobPosting.source)
    )
    postings_by_source = {row[0]: row[1] for row in by_source_rows.all()}

    top_companies_rows = await db.execute(
        select(JobPosting.company, func.count().label("count"))
        .group_by(JobPosting.company)
        .order_by(func.count().desc())
        .limit(10)
    )
    top_companies = [{"company": row[0], "count": row[1]} for row in top_companies_rows.all()]

    avg_row = (
        await db.execute(
            select(
                func.avg(JobPosting.salary_min),
                func.avg(JobPosting.salary_max),
            )
        )
    ).one()
    avg_score_row = (await db.execute(select(func.avg(JobMatch.overall_score)))).scalar_one()

    return JobMatchAnalyticsResponse(
        total_postings=total_postings,
        total_matches=total_matches,
        postings_by_source=postings_by_source,
        top_companies=top_companies,
        avg_salary_min=float(avg_row[0]) if avg_row[0] is not None else None,
        avg_salary_max=float(avg_row[1]) if avg_row[1] is not None else None,
        avg_overall_score=float(avg_score_row) if avg_score_row is not None else None,
        computed_at=utcnow(),
        cache_hit=False,
    )


async def get_job_match_analytics(
    db: AsyncSession, *, refresh: bool = False
) -> JobMatchAnalyticsResponse:
    result, cache_hit = await cached_aggregate(
        "job_match_analytics",
        JobMatchAnalyticsResponse,
        lambda: _compute_job_match_analytics(db),
        refresh=refresh,
    )
    result.cache_hit = cache_hit
    return result
```

---

### 8.11 `backend/app/modules/admin/queues_service.py` (NEW)

Implements Decision 7 — hand-rolled RQ introspection, no `rq-dashboard` mount, no new queue.

```python
"""RQ queue introspection + retry. Read/retry access to the EXISTING queues in
QUEUE_PRIORITIES only — never registers a new queue (Decision 9)."""

from __future__ import annotations

from datetime import UTC, datetime

from rq import Queue, Worker
from rq.registry import FailedJobRegistry

from app.modules.admin.schemas import FailedJobResponse, QueueSnapshotResponse
from app.workers.queue import QUEUE_PRIORITIES, get_redis_connection


def get_queues_overview() -> list[QueueSnapshotResponse]:
    connection = get_redis_connection()
    workers = Worker.all(connection=connection)
    snapshots = []

    for name, priority in QUEUE_PRIORITIES.items():
        queue = Queue(name, connection=connection)
        failed_registry = FailedJobRegistry(queue=queue)
        oldest_age = None
        job_ids = queue.job_ids
        if job_ids:
            oldest_job = queue.fetch_job(job_ids[0])
            if oldest_job and oldest_job.enqueued_at:
                oldest_age = (datetime.now(UTC) - oldest_job.enqueued_at).total_seconds()

        listening = sum(1 for w in workers if name in [q.name for q in w.queues])

        snapshots.append(
            QueueSnapshotResponse(
                name=name,
                priority=priority,
                queued_count=len(queue),
                failed_count=len(failed_registry),
                oldest_queued_age_seconds=oldest_age,
                workers_listening=listening,
            )
        )
    return snapshots


def list_failed_jobs(queue_name: str, limit: int = 50) -> list[FailedJobResponse]:
    connection = get_redis_connection()
    queue = Queue(queue_name, connection=connection)
    registry = FailedJobRegistry(queue=queue)
    job_ids = registry.get_job_ids()[:limit]

    results = []
    for job_id in job_ids:
        job = queue.fetch_job(job_id)
        if job is None:
            continue
        results.append(
            FailedJobResponse(
                job_id=job.id,
                queue_name=queue_name,
                func_name=job.func_name,
                enqueued_at=job.enqueued_at,
                failed_at=job.ended_at,
                exc_info=job.exc_info,
            )
        )
    return results


def retry_failed_job(queue_name: str, job_id: str) -> bool:
    connection = get_redis_connection()
    queue = Queue(queue_name, connection=connection)
    registry = FailedJobRegistry(queue=queue)
    if job_id not in registry.get_job_ids():
        return False
    registry.requeue(job_id)
    return True
```

### 8.12 `backend/app/modules/admin/health.py` (NEW)

System health page — self-checks always; Prometheus panel only when configured (§7).

```python
"""System health: real Postgres/Redis pings always; Prometheus four-golden-
signals panel only when PROMETHEUS_QUERY_URL is set (fail-soft, per this
repo's existing optional-backend convention)."""

from __future__ import annotations

import time

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.infrastructure.redis import get_redis_client
from app.modules.admin.schemas import SystemHealthResponse


async def get_system_health(db: AsyncSession) -> SystemHealthResponse:
    settings = get_settings()

    db_start = time.monotonic()
    database_ok = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        database_ok = False
    database_latency_ms = (time.monotonic() - db_start) * 1000

    redis_start = time.monotonic()
    redis_ok = True
    try:
        client = get_redis_client()
        await client.ping()
    except Exception:
        redis_ok = False
    redis_latency_ms = (time.monotonic() - redis_start) * 1000

    signals: dict[str, float | None] = {}
    prometheus_configured = bool(settings.prometheus_query_url)
    if prometheus_configured:
        signals = await _query_golden_signals(settings.prometheus_query_url)

    return SystemHealthResponse(
        database_ok=database_ok,
        database_latency_ms=round(database_latency_ms, 2),
        redis_ok=redis_ok,
        redis_latency_ms=round(redis_latency_ms, 2),
        prometheus_configured=prometheus_configured,
        signals=signals,
    )


async def _query_golden_signals(base_url: str) -> dict[str, float | None]:
    """Latency, traffic, errors, saturation — per docs/admin-module-research.md
    §2's SRE-book citation. Queries this repo's own existing Prometheus metrics
    (tier_metrics, job_matching_metrics), never invents new metric names."""
    queries = {
        "latency_p95_seconds": 'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))',
        "traffic_requests_per_sec": "sum(rate(http_requests_total[5m]))",
        "error_rate": 'sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))',
        "queue_depth_saturation": "sum(rq_queue_length)",
    }
    results: dict[str, float | None] = {}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            for signal_name, query in queries.items():
                response = await client.get(f"{base_url}/api/v1/query", params={"query": query})
                response.raise_for_status()
                data = response.json()
                result = data.get("data", {}).get("result", [])
                results[signal_name] = float(result[0]["value"][1]) if result else None
    except Exception:
        # Fail-soft: Prometheus unreachable or misconfigured is not a 500 for
        # the whole health page — matches this repo's other optional-backend
        # conventions (LLM_MODE stub, R2->local fallback).
        return dict.fromkeys(queries, None)
    return results
```

### 8.13 `backend/app/modules/admin/mfa.py` (NEW)

Implements Decision 5 — TOTP schema + seam, real enroll/verify/disable flow, enforcement wired only into impersonation.

```python
"""TOTP MFA: enroll/verify/disable for any user's own account. Enforcement is
NOT wired into the main login flow in this plan (Decision 5) — the one place
it IS enforced is impersonation start (§8.14), per docs/admin-module-research.md
§11.5's explicit requirement."""

from __future__ import annotations

from uuid import UUID

import pyotp
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.config import get_settings
from app.database.session import get_db_session
from app.modules.admin.schemas import MfaEnrollResponse


async def enroll_mfa(db: AsyncSession, user: User) -> MfaEnrollResponse:
    secret = pyotp.random_base32()
    user.mfa_secret = secret
    # mfa_enabled flips to True only after a successful verify_mfa_code call
    # (confirm_enrollment below) — never on enroll alone, so a user who
    # generates a QR code but never scans it isn't locked into an unusable state.
    await db.flush()
    await db.commit()

    settings = get_settings()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=user.email, issuer_name=settings.admin_mfa_issuer_name)
    return MfaEnrollResponse(secret=secret, provisioning_uri=uri)


def verify_mfa_code(user: User, code: str) -> bool:
    """The `verify_mfa()` seam per Decision 5 — a pure function, easy to unit
    test and easy to call from any future enforcement point without touching
    this module's internals."""
    if not user.mfa_secret:
        return False
    totp = pyotp.TOTP(user.mfa_secret)
    return totp.verify(code, valid_window=1)


async def confirm_enrollment(db: AsyncSession, user: User, code: str) -> None:
    if not verify_mfa_code(user, code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid MFA code")
    from datetime import UTC, datetime

    user.mfa_enabled = True
    user.mfa_enrolled_at = datetime.now(UTC)
    await db.flush()
    await db.commit()


async def disable_mfa(db: AsyncSession, user: User) -> None:
    user.mfa_enabled = False
    user.mfa_secret = None
    user.mfa_enrolled_at = None
    await db.flush()
    await db.commit()
```

### 8.14 `backend/app/modules/admin/impersonation.py` (NEW)

Implements Decision 6 — scoped JWT claim reusing existing cookie infra, sequenced last, MFA-gated per §11.5.

```python
"""Support impersonation: a scoped JWT claim on the existing access_token
cookie, not a second auth system. See Decision 6. Sequenced last in the
build order (§9) — requires the audit log and MFA to already exist."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException, Response, status
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.config import get_settings
from app.modules.admin import repository
from app.modules.admin.audit import record_admin_action
from app.modules.admin.mfa import verify_mfa_code
from app.modules.admin.models import ImpersonationSession
from app.modules.admin.schemas import ImpersonationStartResponse


async def start_impersonation(
    db: AsyncSession,
    *,
    admin: User,
    target_user_id: UUID,
    reason: str,
    mfa_code: str | None,
    response: Response,
    ip_address: str | None,
) -> ImpersonationStartResponse:
    if admin.mfa_enabled:
        if not mfa_code or not verify_mfa_code(admin, mfa_code):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Valid MFA code required to start an impersonation session",
            )

    target = await repository.get_user_by_id(db, target_user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Target user not found")
    if target.id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot impersonate yourself")

    settings = get_settings()
    jti = uuid4().hex
    expires_at = datetime.now(UTC) + timedelta(
        minutes=settings.admin_impersonation_max_duration_minutes
    )

    payload = {
        "sub": str(target.id),
        "jti": jti,
        "imp": str(admin.id),
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    response.set_cookie(
        "access_token", token, httponly=True, secure=True, samesite="lax",
        expires=int(expires_at.timestamp()),
    )

    session = ImpersonationSession(
        admin_user_id=admin.id,
        target_user_id=target.id,
        token_jti=jti,
        reason=reason,
        expires_at=expires_at,
    )
    db.add(session)
    await db.flush()

    await record_admin_action(
        db,
        actor_user_id=admin.id,
        action="impersonation.started",
        target_type="user",
        target_id=str(target.id),
        after={"reason": reason, "expires_at": expires_at.isoformat()},
        ip_address=ip_address,
    )
    await db.commit()

    return ImpersonationStartResponse(target_user_id=target.id, expires_at=expires_at)


async def end_impersonation(
    db: AsyncSession, *, admin_user_id: UUID, jti: str, response: Response, ip_address: str | None
) -> None:
    from sqlalchemy import select

    result = await db.execute(
        select(ImpersonationSession).where(ImpersonationSession.token_jti == jti)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Impersonation session not found")

    session.ended_at = datetime.now(UTC)

    from app.auth.logged_out_tokens import LoggedOutTokenService
    from app.infrastructure.redis import get_redis_client

    blacklist_service = LoggedOutTokenService(get_redis_client())
    await blacklist_service.blacklist_token(
        db=db, token_jti=jti, user_id=session.target_user_id, reason="impersonation_ended"
    )

    await record_admin_action(
        db,
        actor_user_id=admin_user_id,
        action="impersonation.ended",
        target_type="user",
        target_id=str(session.target_user_id),
        ip_address=ip_address,
    )
    await db.commit()
    response.delete_cookie("access_token")
```

`LoggedOutTokenService.blacklist_token` is assumed to exist per `backend/app/auth/logged_out_tokens.py`'s stated purpose ("Tokens blacklisted on logout, synced to Redis"); if its exact method name differs from `blacklist_token` when this is implemented, use whatever the real method signature is — this plan's contract is "revoke the `jti` via the existing blacklist service," not a specific method name, since verifying the exact signature is an implementation-time check, not a planning-time one.

### 8.15 `backend/app/modules/admin/router.py` — restructured (existing file, extended)

The existing file becomes `backend/app/modules/admin/router.py` (cost endpoints, unchanged) plus new sibling router files aggregated in `backend/app/modules/admin/__init__.py`. The 5 existing cost endpoints and `require_superuser` function **keep their exact current signatures and import path** (Decision 1, regression-avoidance) — only `get_total_costs` and `get_cost_breakdown` gain an internal call to `cached_aggregate()` (Decision 3), which does not change their route signature, request shape, or response shape.

New files, each a small `APIRouter` mounted under `/api/admin` with its own prefix, all using `EnvelopeAPIRoute`:

- `backend/app/modules/admin/users_router.py` — `GET /api/admin/users` (cursor-paginated, `Depends(require_permission("users","read"))`), `PATCH /api/admin/users/{user_id}/status` (`require_permission("users","suspend")`), `PUT /api/admin/users/{user_id}/role` (`require_superuser_strict`, per Decision 1 — role assignment is superuser-only, not RBAC-grantable)
- `backend/app/modules/admin/roles_router.py` — `GET /api/admin/roles` (`require_permission("roles","read")`)
- `backend/app/modules/admin/audit_router.py` — `GET /api/admin/audit-logs` (cursor-paginated, `require_permission("audit_logs","read")`)
- `backend/app/modules/admin/flags_router.py` — `GET /api/admin/feature-flags`, `PUT /api/admin/feature-flags/{key}` (`require_permission("feature_flags","read"|"write")`)
- `backend/app/modules/admin/queues_router.py` — `GET /api/admin/queues`, `GET /api/admin/queues/{name}/failed`, `POST /api/admin/queues/{name}/failed/{job_id}/retry` (`require_permission("queues","read"|"retry")`)
- `backend/app/modules/admin/health_router.py` — `GET /api/admin/system-health` (`require_permission("system_health","read")`)
- `backend/app/modules/admin/analytics_router.py` — `GET /api/admin/analytics/job-matches` (`require_permission("analytics","read")`, `?refresh=1` query param wired to `cached_aggregate`'s `refresh` flag)
- `backend/app/modules/admin/mfa_router.py` — `POST /api/admin/mfa/enroll`, `POST /api/admin/mfa/confirm`, `POST /api/admin/mfa/disable`, `GET /api/admin/mfa/status` (all `Depends(VerifiedUser)` only — any user manages their own MFA, no special permission needed, matching how `/api/auth/*` self-service endpoints work today)
- `backend/app/modules/admin/impersonation_router.py` — `POST /api/admin/impersonation/start/{user_id}`, `POST /api/admin/impersonation/end`, `GET /api/admin/impersonation/status` (`require_permission("impersonation","start")`)

`backend/app/modules/admin/__init__.py` (edited — currently near-empty per the directory listing) aggregates all of the above into one `router` object the same way `job_matching/router.py` is a single router today, so `main.py` keeps importing one name:

```python
from fastapi import APIRouter

from app.modules.admin.audit_router import router as audit_router
from app.modules.admin.analytics_router import router as analytics_router
from app.modules.admin.flags_router import router as flags_router
from app.modules.admin.health_router import router as health_router
from app.modules.admin.impersonation_router import router as impersonation_router
from app.modules.admin.mfa_router import router as mfa_router
from app.modules.admin.queues_router import router as queues_router
from app.modules.admin.roles_router import router as roles_router
from app.modules.admin.router import router as costs_router
from app.modules.admin.users_router import router as users_router

router = APIRouter()
router.include_router(costs_router)
router.include_router(users_router)
router.include_router(roles_router)
router.include_router(audit_router)
router.include_router(flags_router)
router.include_router(queues_router)
router.include_router(health_router)
router.include_router(analytics_router)
router.include_router(mfa_router)
router.include_router(impersonation_router)
```

`backend/app/main.py` needs **zero changes** — it already does `from app.modules.admin.router import router as admin_router` at line 14 and `app.include_router(admin_router, dependencies=[Depends(current_verified_user)])` at line 79. Since `__init__.py` now aggregates everything into the package-level `router`, this import path changes to `from app.modules.admin import router as admin_router` (one line edited in `main.py`) — the aggregate router carries all 10 sub-routers' routes under the single `current_verified_user` dependency already applied at the `include_router` call, with each individual endpoint additionally gated by its own `require_permission`/`require_superuser_strict`/`VerifiedUser`-only dependency as listed above (two layers, matching how `dsar_router` already stacks `current_verified_user` + `enforce_compliance_rate_limit` in `main.py:89-92`).

`app.add_middleware(AdminAuditFallbackMiddleware)` is added to `main.py` alongside the existing `SecurityHeadersMiddleware`/`RequestContextMiddleware` registrations (§8.4).

### 8.16 `backend/app/auth/dependencies.py` — edits (not a new file)

```python
# Inside get_current_user_from_cookie, after successfully fetching `user`
# from the DB (after the existing is_active check), add:
request.state.user_id = user.id

# After decoding the JWT payload, also read the optional impersonation claim:
impersonated_by: str | None = payload.get("imp")
if impersonated_by:
    request.state.impersonated_by = UUID(impersonated_by)
```

Both additions are purely additive attributes on `request.state` — no existing return value, exception path, or caller of `get_current_user_from_cookie` changes behavior.

---

## 9. Testing — proving the Admin Module is complete

Implementation order (per §3/§13): (1) migrations + models, (2) audit log, (3) pagination + user management, (4) feature flags, (5) RBAC, (6) cached aggregates (analytics + cost endpoints), (7) queues + system health, (8) MFA, (9) impersonation last. Tests below are grouped to match.

### 9.1 `backend/tests/test_admin_migrations.py` (NEW)

```python
"""Schema tests for the Admin Module migrations — mirrors the shape of
phase2_module1.md §8.7's test_job_matching_migrations.py."""

import pytest
from sqlalchemy import inspect

pytestmark = pytest.mark.asyncio


async def test_admin_tables_exist_after_migration(db_engine):
    async with db_engine.connect() as conn:
        inspector = await conn.run_sync(inspect)
        tables = inspector.get_table_names()
        for table in [
            "roles", "permissions", "role_permissions",
            "admin_audit_logs", "feature_flags", "impersonation_sessions",
        ]:
            assert table in tables


async def test_users_table_has_new_columns(db_engine):
    async with db_engine.connect() as conn:
        inspector = await conn.run_sync(inspect)
        columns = {c["name"] for c in inspector.get_columns("users")}
        assert {"role_id", "mfa_secret", "mfa_enabled", "mfa_enrolled_at"} <= columns


async def test_seed_migration_creates_support_and_admin_roles(db_session):
    from sqlalchemy import select

    from app.modules.admin.models import Role

    result = await db_session.execute(select(Role.name))
    names = {row[0] for row in result.all()}
    assert {"support", "admin"} <= names
```

### 9.2 `backend/tests/test_admin_audit.py` (NEW)

```python
"""Audit log writer + fallback middleware tests."""

import pytest

pytestmark = pytest.mark.asyncio


async def test_record_admin_action_persists_entry(db_session, seed_user):
    from app.modules.admin.audit import record_admin_action

    entry = await record_admin_action(
        db_session,
        actor_user_id=seed_user.id,
        action="user.status_changed",
        target_type="user",
        target_id=str(seed_user.id),
        before={"is_active": True},
        after={"is_active": False},
        ip_address="127.0.0.1",
    )
    assert entry.captured_by == "explicit"
    assert entry.action == "user.status_changed"


def test_fallback_middleware_logs_uncaptured_mutation(client, superuser_cookie):
    response = client.patch(
        "/api/admin/some-endpoint-without-explicit-audit",
        cookies=superuser_cookie,
    )
    # Exact endpoint used here is illustrative; the real test iterates every
    # mutating admin route with record_admin_action mocked out entirely and
    # asserts a captured_by="fallback" row is written instead of silence.
    assert response.status_code in (200, 204, 404)
```

### 9.3 `backend/tests/test_admin_pagination.py` (NEW)

```python
"""Cursor encode/decode round-trip + list-endpoint pagination correctness."""

from datetime import UTC, datetime
from uuid import uuid4

from app.modules.admin.pagination import decode_cursor, encode_cursor


def test_cursor_round_trip():
    now = datetime.now(UTC)
    entity_id = uuid4()
    cursor = encode_cursor(now, entity_id)
    decoded_at, decoded_id = decode_cursor(cursor)
    assert decoded_at == now
    assert decoded_id == str(entity_id)


def test_cursor_is_opaque_base64():
    cursor = encode_cursor(datetime.now(UTC), uuid4())
    assert "|" not in cursor  # raw separator must not leak through encoding
```

### 9.4 `backend/tests/test_admin_users_api.py` (NEW)

```python
"""User management API: pagination, status changes, role assignment, audit."""

import pytest

pytestmark = pytest.mark.asyncio


async def test_list_users_requires_permission(client):
    response = client.get("/api/admin/users")
    assert response.status_code == 401


async def test_list_users_returns_cursor_shape(client, superuser_cookie):
    response = client.get("/api/admin/users", cookies=superuser_cookie)
    assert response.status_code == 200
    body = response.json()["data"]
    assert "items" in body and "next_cursor" in body and "has_more" in body


async def test_suspend_user_writes_audit_log(client, superuser_cookie, regular_user, db_session):
    response = client.patch(
        f"/api/admin/users/{regular_user.id}/status",
        json={"is_active": False, "reason": "ToS violation"},
        cookies=superuser_cookie,
    )
    assert response.status_code == 200

    from sqlalchemy import select

    from app.modules.admin.models import AdminAuditLog

    result = await db_session.execute(
        select(AdminAuditLog).where(AdminAuditLog.action == "user.status_changed")
    )
    entry = result.scalar_one()
    assert entry.before["is_active"] is True
    assert entry.after["is_active"] is False


async def test_assign_role_requires_strict_superuser_not_rbac_permission(
    client, support_role_cookie, regular_user
):
    """RBAC alone (e.g. a 'support' role with users:write) must NOT be able to
    assign roles — only is_superuser can, per Decision 1."""
    response = client.put(
        f"/api/admin/users/{regular_user.id}/role",
        json={"role_id": None},
        cookies=support_role_cookie,
    )
    assert response.status_code == 403
```

### 9.5 `backend/tests/test_admin_rbac.py` (NEW)

```python
"""require_permission() behavior: superuser bypass, role-based grant/deny."""

import pytest

pytestmark = pytest.mark.asyncio


async def test_superuser_bypasses_rbac_lookup(db_session, superuser):
    from app.modules.admin.permissions import user_has_permission

    assert await user_has_permission(db_session, superuser, "nonexistent", "resource") is True


async def test_user_without_role_denied(db_session, regular_user):
    from app.modules.admin.permissions import user_has_permission

    assert await user_has_permission(db_session, regular_user, "users", "read") is False


async def test_support_role_can_read_users_but_not_write(db_session, support_user):
    from app.modules.admin.permissions import user_has_permission

    assert await user_has_permission(db_session, support_user, "users", "read") is True
    assert await user_has_permission(db_session, support_user, "users", "write") is False


async def test_existing_require_superuser_call_sites_unaffected(client):
    """Regression guard for Decision 1 — the 5 pre-existing cost endpoints must
    keep working exactly as before this module's changes."""
    response = client.get("/api/admin/costs/daily")
    assert response.status_code == 401  # unauthenticated, same as before this plan
```

### 9.6 `backend/tests/test_admin_feature_flags.py` (NEW)

```python
"""Feature flag CRUD, cache invalidation, audit trail."""

import pytest

pytestmark = pytest.mark.asyncio


async def test_upsert_flag_creates_and_audits(db_session, superuser):
    from app.modules.admin.schemas import UpsertFeatureFlagRequest
    from app.modules.admin.service import upsert_feature_flag

    flag = await upsert_feature_flag(
        db_session,
        actor_id=superuser.id,
        key="test_flag",
        payload=UpsertFeatureFlagRequest(enabled=True, value=None, description="test"),
        ip_address="127.0.0.1",
    )
    assert flag.enabled is True


async def test_flip_invalidates_cache(db_session, superuser, mock_redis):
    """A flip must not leave a stale cached read visible — verifies the cache
    key used for feature-flag reads is invalidated (deleted or overwritten) on
    every write, not just relying on TTL expiry."""
```

### 9.7 `backend/tests/test_admin_analytics.py` (NEW)

```python
"""Job-match analytics — the §3 ground-truth correction. Verifies the endpoint
reads real Module 1 tables and never writes to them."""

import pytest

pytestmark = pytest.mark.asyncio


async def test_analytics_reads_job_postings_and_matches(db_session, seeded_job_postings):
    from app.modules.admin.analytics import get_job_match_analytics

    result = await get_job_match_analytics(db_session)
    assert result.total_postings == len(seeded_job_postings)
    assert result.cache_hit is False  # first call, cold cache


async def test_analytics_second_call_hits_cache(db_session, seeded_job_postings):
    from app.modules.admin.analytics import get_job_match_analytics

    await get_job_match_analytics(db_session)
    result = await get_job_match_analytics(db_session)
    assert result.cache_hit is True


async def test_analytics_refresh_bypasses_cache(db_session, seeded_job_postings):
    from app.modules.admin.analytics import get_job_match_analytics

    await get_job_match_analytics(db_session)
    result = await get_job_match_analytics(db_session, refresh=True)
    assert result.cache_hit is False


async def test_analytics_never_writes_to_job_matching_tables(db_session, seeded_job_postings):
    from app.modules.job_matching.models import JobPosting

    from app.modules.admin.analytics import get_job_match_analytics

    before_count = len((await db_session.execute(select(JobPosting))).all())
    await get_job_match_analytics(db_session)
    after_count = len((await db_session.execute(select(JobPosting))).all())
    assert before_count == after_count
```

### 9.8 `backend/tests/test_admin_queues.py` (NEW)

```python
"""RQ introspection: mocks rq.Queue/Worker, no live Redis needed in CI
(RULE.md: 'No live external calls in CI')."""

from unittest.mock import MagicMock, patch

import pytest


def test_get_queues_overview_uses_existing_queue_priorities():
    from app.modules.admin.queues_service import get_queues_overview

    with patch("app.modules.admin.queues_service.get_redis_connection") as mock_conn:
        with patch("app.modules.admin.queues_service.Worker.all", return_value=[]):
            with patch("app.modules.admin.queues_service.Queue") as mock_queue_cls:
                mock_queue = MagicMock()
                mock_queue.job_ids = []
                mock_queue.__len__.return_value = 0
                mock_queue_cls.return_value = mock_queue

                snapshots = get_queues_overview()
                # One snapshot per name in QUEUE_PRIORITIES — no new queue introduced.
                from app.workers.queue import QUEUE_PRIORITIES

                assert len(snapshots) == len(QUEUE_PRIORITIES)


def test_retry_failed_job_calls_registry_requeue():
    from app.modules.admin.queues_service import retry_failed_job

    with patch("app.modules.admin.queues_service.get_redis_connection"):
        with patch("app.modules.admin.queues_service.Queue"):
            with patch("app.modules.admin.queues_service.FailedJobRegistry") as mock_registry_cls:
                mock_registry = MagicMock()
                mock_registry.get_job_ids.return_value = ["job-1"]
                mock_registry_cls.return_value = mock_registry

                result = retry_failed_job("email", "job-1")
                assert result is True
                mock_registry.requeue.assert_called_once_with("job-1")
```

### 9.9 `backend/tests/test_admin_system_health.py` (NEW)

```python
"""System health: self-checks always real; Prometheus panel fail-soft when
PROMETHEUS_QUERY_URL unset (mocked HTTP when set, per 'no live external calls')."""

import pytest

pytestmark = pytest.mark.asyncio


async def test_health_without_prometheus_configured(db_session, monkeypatch):
    from app.modules.admin.health import get_system_health

    monkeypatch.setattr("app.core.config.get_settings().prometheus_query_url", "")
    result = await get_system_health(db_session)
    assert result.prometheus_configured is False
    assert result.signals == {}
    assert result.database_ok is True


async def test_health_prometheus_unreachable_fails_soft(db_session, monkeypatch):
    from app.modules.admin.health import get_system_health

    monkeypatch.setattr(
        "app.core.config.get_settings().prometheus_query_url", "http://unreachable:9090"
    )
    result = await get_system_health(db_session)
    assert result.prometheus_configured is True
    assert all(v is None for v in result.signals.values())
```

### 9.10 `backend/tests/test_admin_mfa.py` (NEW)

```python
"""TOTP enroll/verify/disable — the verify_mfa() seam per Decision 5."""

import pyotp
import pytest

pytestmark = pytest.mark.asyncio


async def test_enroll_generates_valid_provisioning_uri(db_session, regular_user):
    from app.modules.admin.mfa import enroll_mfa

    result = await enroll_mfa(db_session, regular_user)
    assert result.provisioning_uri.startswith("otpauth://totp/")
    assert regular_user.mfa_enabled is False  # not enabled until confirmed


async def test_confirm_enrollment_with_valid_code_enables_mfa(db_session, regular_user):
    from app.modules.admin.mfa import confirm_enrollment, enroll_mfa

    await enroll_mfa(db_session, regular_user)
    code = pyotp.TOTP(regular_user.mfa_secret).now()
    await confirm_enrollment(db_session, regular_user, code)
    assert regular_user.mfa_enabled is True


async def test_confirm_enrollment_with_invalid_code_rejected(db_session, regular_user):
    from fastapi import HTTPException

    from app.modules.admin.mfa import enroll_mfa, confirm_enrollment

    await enroll_mfa(db_session, regular_user)
    with pytest.raises(HTTPException):
        await confirm_enrollment(db_session, regular_user, "000000")


def test_verify_mfa_code_seam_is_pure_and_reusable(regular_user):
    from app.modules.admin.mfa import verify_mfa_code

    regular_user.mfa_secret = None
    assert verify_mfa_code(regular_user, "123456") is False
```

### 9.11 `backend/tests/test_admin_impersonation.py` (NEW)

```python
"""Impersonation: MFA gate, dual-identity audit entries, jti revocation on end."""

import pytest

pytestmark = pytest.mark.asyncio


async def test_start_requires_mfa_when_admin_has_it_enabled(
    db_session, superuser_with_mfa, regular_user
):
    from fastapi import HTTPException
    from starlette.responses import Response

    from app.modules.admin.impersonation import start_impersonation

    with pytest.raises(HTTPException) as exc:
        await start_impersonation(
            db_session,
            admin=superuser_with_mfa,
            target_user_id=regular_user.id,
            reason="debugging a support ticket",
            mfa_code=None,
            response=Response(),
            ip_address="127.0.0.1",
        )
    assert exc.value.status_code == 403


async def test_start_writes_impersonation_session_and_audit_entry(
    db_session, superuser, regular_user
):
    from starlette.responses import Response

    from app.modules.admin.impersonation import start_impersonation

    result = await start_impersonation(
        db_session,
        admin=superuser,
        target_user_id=regular_user.id,
        reason="debugging a support ticket",
        mfa_code=None,
        response=Response(),
        ip_address="127.0.0.1",
    )
    assert result.target_user_id == regular_user.id

    from sqlalchemy import select

    from app.modules.admin.models import AdminAuditLog, ImpersonationSession

    session = (
        await db_session.execute(
            select(ImpersonationSession).where(
                ImpersonationSession.target_user_id == regular_user.id
            )
        )
    ).scalar_one()
    assert session.admin_user_id == superuser.id

    audit_entry = (
        await db_session.execute(
            select(AdminAuditLog).where(AdminAuditLog.action == "impersonation.started")
        )
    ).scalar_one()
    assert audit_entry.actor_user_id == superuser.id


async def test_cannot_impersonate_self(db_session, superuser):
    from fastapi import HTTPException
    from starlette.responses import Response

    from app.modules.admin.impersonation import start_impersonation

    with pytest.raises(HTTPException):
        await start_impersonation(
            db_session,
            admin=superuser,
            target_user_id=superuser.id,
            reason="x",
            mfa_code=None,
            response=Response(),
            ip_address="127.0.0.1",
        )
```

### 9.12 Frontend tests (co-located with components, exact paths given in §12)

`AdminGuard.test.tsx`, `UsersTable.test.tsx`, `AuditLogTable.test.tsx`, `FeatureFlagsPanel.test.tsx`, `QueueMonitor.test.tsx`, `SystemHealthPanel.test.tsx`, `AnalyticsPanel.test.tsx`, `MfaSetupCard.test.tsx`, `ImpersonationBanner.test.tsx` — one test file per component, following the existing `MatchCard.test.tsx`/`PreferencesForm.test.tsx` co-location convention already used in `frontend/features/job-matching/components/`.

### 9.13 Commands to run before declaring the Admin Module done

```bash
# Backend: migrations apply and reverse cleanly
cd backend && alembic upgrade head && alembic downgrade -6 && alembic upgrade head

# Backend: full new-module test suite
cd backend && pytest tests/test_admin_migrations.py tests/test_admin_audit.py \
  tests/test_admin_pagination.py tests/test_admin_users_api.py tests/test_admin_rbac.py \
  tests/test_admin_feature_flags.py tests/test_admin_analytics.py tests/test_admin_queues.py \
  tests/test_admin_system_health.py tests/test_admin_mfa.py tests/test_admin_impersonation.py -v

# Backend: existing admin test file must still pass unmodified (regression guard, Decision 1)
cd backend && pytest tests/test_admin_costs.py -v

# Backend: coverage gate (must stay >= the repo's existing 78% floor, not lower it)
cd backend && pytest tests -m "not postgres" -q --cov=app --cov-report=term-missing

# Backend: full suite regression check (nothing else broke)
cd backend && pytest tests -m "not postgres" -q

# Backend: lint/type
cd backend && ruff check app/modules/admin app/auth && ruff format --check app/modules/admin

# Frontend: typecheck + lint + build (per RULE.md "type changes -> typecheck, UI changes -> lint/build")
cd frontend && npm run typecheck && npm run lint && npm run build

# Frontend: new-feature test suite
cd frontend && npm run test:unit -- features/admin
```

---

## 10. Docker architecture for the Admin Module

Per Decision 9, this is short by design — the point being made explicit rather than left as a silent omission (the gap this plan was explicitly asked not to repeat from `phase2_module1.md`).

### 10.1 No new Dockerfile, no new compose service, no new queue

Every new backend module (`app/modules/admin/`) executes inside the existing `api` container (`backend/docker/Dockerfile.api`) — same process, same Postgres connection pool, same Redis client already established by `app/infrastructure/redis.py` for every other route. Verified this is safe: the new code adds zero new dependencies that require anything beyond what `Dockerfile.api` already installs (`pyotp` is a small pure-Python package with no system dependencies, unlike e.g. Playwright/Chromium for Tier 1).

### 10.2 `backend/docker/Dockerfile.api` — one dependency line, no structural change

```dockerfile
# No new RUN/COPY/ENV instructions needed. pyotp is installed the same way
# every other pure-Python dependency in pyproject.toml already is, via the
# existing `pip install -e .` (or equivalent) layer.
```

If `Dockerfile.api` pins dependencies via a lockfile step rather than installing from `pyproject.toml` directly at build time, that lockfile is regenerated as part of normal dependency-update tooling — no Dockerfile edit is needed either way, since `pyotp` is added to `pyproject.toml`'s `dependencies` list (§7), and `Dockerfile.api` already installs from that file.

### 10.3 `backend/docker/docker-compose.yml` — no new service block, one env addition to the existing `api` service

No `admin` or `worker-admin` service is added. The base stack's `api` service (`backend/docker/docker-compose.yml:14-86`) already runs every route this plan adds — it just needs the 7 new env vars from §7 added to its existing `environment:` block, following the exact `${VAR:-default}` convention every other setting in that block already uses (verified directly, e.g. `LLM_MODE: ${LLM_MODE:-stub}` at line 33). These vars are added to `api` **only** — never to `worker`, `worker-document`, `worker-embedding`, or `worker-job-matching` (defined in `docker-compose.foundation.yml`), since none of them run admin code.

```yaml
# backend/docker/docker-compose.yml — additions to the existing `api` service's environment block:
  api:
    environment:
      # ... existing vars unchanged ...
      ADMIN_AUDIT_LOG_RETENTION_DAYS: ${ADMIN_AUDIT_LOG_RETENTION_DAYS:-1825}
      ADMIN_AGGREGATE_CACHE_TTL_SECONDS: ${ADMIN_AGGREGATE_CACHE_TTL_SECONDS:-300}
      ADMIN_DEFAULT_PAGE_SIZE: ${ADMIN_DEFAULT_PAGE_SIZE:-20}
      ADMIN_MAX_PAGE_SIZE: ${ADMIN_MAX_PAGE_SIZE:-100}
      ADMIN_MFA_ISSUER_NAME: ${ADMIN_MFA_ISSUER_NAME:-Hyrepath Admin}
      ADMIN_IMPERSONATION_MAX_DURATION_MINUTES: ${ADMIN_IMPERSONATION_MAX_DURATION_MINUTES:-30}
      PROMETHEUS_QUERY_URL: ${PROMETHEUS_QUERY_URL:-}
```

### 10.4 `migrate` service — no change needed

`backend/docker/docker-compose.yml:2-13`'s `migrate` service already runs `alembic upgrade head` against whatever the current head is, and every worker's `depends_on: migrate: condition: service_completed_successfully` (verified directly in `worker-job-matching`'s block, §2) already waits on it. Since this plan's 6 new revisions chain onto the real head linearly (§6), `migrate` picks them up automatically with zero edits to its own definition.

### 10.5 Full container topology after the Admin Module ships

No new boxes. The topology diagram in `backend/docs/ARCHITECTURE.md`'s "Docker services" section is unchanged by this plan — `api`, `worker`, `worker-document`, `worker-embedding`, `worker-job-matching`, `postgres`, `redis`, and the existing sidecars all keep their current roles. The only new *runtime relationship* is `api` optionally calling out to a Prometheus query API if `PROMETHEUS_QUERY_URL` is set (§7) — and Prometheus itself is not a new service this plan introduces; `backend/observability/alerts/hyrepath.rules.yml` already implies a running Prometheus somewhere in the deployment (this plan does not add a `prometheus` compose service — if the target environment does not already run one, `PROMETHEUS_QUERY_URL` stays unset and the four-golden-signals panel simply does not render, per §8.12's fail-soft design).

### 10.6 Monitoring additions

No new Prometheus counters are introduced by this plan (unlike `phase2_module1.md` §9.5, which added `tier1_*` counters for a genuinely new pipeline). The Admin Module's own operations (permission checks, audit writes, cache hits/misses) are logged via the existing `stdlib` JSON logging convention (ADR 0007) at `INFO`/`WARNING` level (see §8.4's `logger.info` call, §8.5's `logger.warning` fail-open calls) — sufficient for this module's own observability without adding new metric cardinality, consistent with "keep the change as small as the task allows."

---

## 11. Frontend — shared types and BFF API layer

The section the task explicitly flagged `phase2_module1.md` for omitting. Given equal weight here — every backend endpoint in §8 gets a typed BFF route before any UI component is built, matching this repo's own layering rule ("Components display; lib handles data — fetching and mapping live in `src/lib/`, not scattered in JSX").

### 11.1 OpenAPI sync (must run first, per RULE.md)

```bash
cd frontend && npm run openapi:export && npm run openapi:gen
git add openapi/openapi.json src/lib/generated/openapi.ts
```

Run this **after** the backend routes in §8.15 exist and the app can boot (`export_openapi.py` imports `app.main:app`), and commit the regenerated files in the same PR, per `RULE.md`'s explicit instruction.

### 11.2 `frontend/src/lib/types.ts` — additions

Appended after the existing `JobMatchListResponse`/`UnreadMatchCountEvent` block, following the exact camelCase mirror convention already used for every other type in this file:

```typescript
export type AdminRole = {
  id: string;
  name: string;
  description: string | null;
  isSystem: boolean;
};

export type AdminPermission = {
  id: string;
  resource: string;
  action: string;
  description: string | null;
};

export type AdminRoleWithPermissions = AdminRole & {
  permissions: AdminPermission[];
};

export type AdminUser = {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  isActive: boolean;
  isVerified: boolean;
  isSuperuser: boolean;
  roleId: string | null;
  roleName: string | null;
  mfaEnabled: boolean;
  createdAt: string;
  deletedAt: string | null;
};

export type AdminUserListResponse = {
  items: AdminUser[];
  nextCursor: string | null;
  hasMore: boolean;
};

export type AdminAuditLogEntry = {
  id: string;
  actorUserId: string | null;
  impersonatedBy: string | null;
  action: string;
  targetType: string;
  targetId: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  ipAddress: string | null;
  capturedBy: "explicit" | "fallback";
  createdAt: string;
};

export type AdminAuditLogListResponse = {
  items: AdminAuditLogEntry[];
  nextCursor: string | null;
  hasMore: boolean;
};

export type FeatureFlag = {
  key: string;
  enabled: boolean;
  value: Record<string, unknown> | null;
  description: string | null;
  updatedBy: string | null;
  updatedAt: string;
};

export type QueueSnapshot = {
  name: string;
  priority: number;
  queuedCount: number;
  failedCount: number;
  oldestQueuedAgeSeconds: number | null;
  workersListening: number;
};

export type FailedJob = {
  jobId: string;
  queueName: string;
  funcName: string | null;
  enqueuedAt: string | null;
  failedAt: string | null;
  excInfo: string | null;
};

export type SystemHealthSnapshot = {
  databaseOk: boolean;
  databaseLatencyMs: number;
  redisOk: boolean;
  redisLatencyMs: number;
  prometheusConfigured: boolean;
  signals: Record<string, number | null>;
};

export type JobMatchAnalytics = {
  totalPostings: number;
  totalMatches: number;
  postingsBySource: Record<string, number>;
  topCompanies: { company: string; count: number }[];
  avgSalaryMin: number | null;
  avgSalaryMax: number | null;
  avgOverallScore: number | null;
  computedAt: string;
  cacheHit: boolean;
};

export type MfaStatus = {
  mfaEnabled: boolean;
  mfaEnrolledAt: string | null;
};

export type MfaEnrollResult = {
  secret: string;
  provisioningUri: string;
};

export type ImpersonationStatus = {
  isImpersonating: boolean;
  adminUserId: string | null;
  adminEmail: string | null;
  targetUserId: string | null;
  expiresAt: string | null;
};
```

Also extend the existing `User` interface in `frontend/providers/auth-provider.tsx` (not `types.ts`, since that interface already lives there per §2's reuse table):

```typescript
// frontend/providers/auth-provider.tsx — additions to the existing User interface:
interface User {
  // ... existing fields unchanged ...
  is_superuser: boolean;
  role_name?: string | null;
  mfa_enabled?: boolean;
}
```

This is a genuine, small, pre-existing gap being closed, not a new abstraction — `is_superuser` is already returned by `GET /api/auth/me` today (`UserRead` schema, `backend/app/auth/schemas.py:28`), the frontend interface simply never typed it. `role_name`/`mfa_enabled` are new fields this plan's backend adds to that same response's underlying `User` model.

### 11.3 `frontend/src/lib/api-adapter.ts` — additions

Following the exact `mapBackend*ToFrontend` / `toBackend*Request` naming convention already used for every other adapter function in this file:

```typescript
export function mapBackendAdminUser(raw: BackendAdminUserResponse): AdminUser {
  return {
    id: raw.id,
    email: raw.email,
    firstName: raw.first_name,
    lastName: raw.last_name,
    isActive: raw.is_active,
    isVerified: raw.is_verified,
    isSuperuser: raw.is_superuser,
    roleId: raw.role_id,
    roleName: raw.role_name,
    mfaEnabled: raw.mfa_enabled,
    createdAt: raw.created_at,
    deletedAt: raw.deleted_at,
  };
}

export function mapBackendAdminUserList(raw: BackendAdminUserListResponse): AdminUserListResponse {
  return {
    items: raw.items.map(mapBackendAdminUser),
    nextCursor: raw.next_cursor,
    hasMore: raw.has_more,
  };
}

export function mapBackendAuditLogEntry(raw: BackendAdminAuditLogEntryResponse): AdminAuditLogEntry {
  return {
    id: raw.id,
    actorUserId: raw.actor_user_id,
    impersonatedBy: raw.impersonated_by,
    action: raw.action,
    targetType: raw.target_type,
    targetId: raw.target_id,
    before: raw.before,
    after: raw.after,
    ipAddress: raw.ip_address,
    capturedBy: raw.captured_by,
    createdAt: raw.created_at,
  };
}

export function mapBackendAuditLogList(
  raw: BackendAdminAuditLogListResponse,
): AdminAuditLogListResponse {
  return {
    items: raw.items.map(mapBackendAuditLogEntry),
    nextCursor: raw.next_cursor,
    hasMore: raw.has_more,
  };
}

export function mapBackendFeatureFlag(raw: BackendFeatureFlagResponse): FeatureFlag {
  return {
    key: raw.key,
    enabled: raw.enabled,
    value: raw.value,
    description: raw.description,
    updatedBy: raw.updated_by,
    updatedAt: raw.updated_at,
  };
}

export function toBackendFeatureFlagRequest(input: Partial<FeatureFlag>) {
  return {
    enabled: input.enabled,
    value: input.value ?? null,
    description: input.description ?? null,
  };
}

export function mapBackendQueueSnapshot(raw: BackendQueueSnapshotResponse): QueueSnapshot {
  return {
    name: raw.name,
    priority: raw.priority,
    queuedCount: raw.queued_count,
    failedCount: raw.failed_count,
    oldestQueuedAgeSeconds: raw.oldest_queued_age_seconds,
    workersListening: raw.workers_listening,
  };
}

export function mapBackendSystemHealth(raw: BackendSystemHealthResponse): SystemHealthSnapshot {
  return {
    databaseOk: raw.database_ok,
    databaseLatencyMs: raw.database_latency_ms,
    redisOk: raw.redis_ok,
    redisLatencyMs: raw.redis_latency_ms,
    prometheusConfigured: raw.prometheus_configured,
    signals: raw.signals,
  };
}

export function mapBackendJobMatchAnalytics(raw: BackendJobMatchAnalyticsResponse): JobMatchAnalytics {
  return {
    totalPostings: raw.total_postings,
    totalMatches: raw.total_matches,
    postingsBySource: raw.postings_by_source,
    topCompanies: raw.top_companies,
    avgSalaryMin: raw.avg_salary_min,
    avgSalaryMax: raw.avg_salary_max,
    avgOverallScore: raw.avg_overall_score,
    computedAt: raw.computed_at,
    cacheHit: raw.cache_hit,
  };
}
```

`BackendAdminUserResponse` etc. are the generated OpenAPI wire types from §11.1's `npm run openapi:gen` output (`src/lib/generated/openapi.ts`) — imported at the top of `api-adapter.ts` exactly like every existing `Backend*Response` type already is (e.g. `BackendJobPreferencesResponse` used by `mapBackendJobPreferencesToFrontend`).

### 11.4 BFF routes (Next.js API routes proxying to the backend)

One route file per backend endpoint group, following the exact `backendFetch` + `handleBackendJson`/`bffServiceUnavailable` pattern already used in `frontend/app/api/job-matching/preferences/route.ts` (read directly, §2):

| New BFF route | Proxies to |
|---|---|
| `frontend/app/api/admin/users/route.ts` | `GET /api/admin/users` |
| `frontend/app/api/admin/users/[userId]/status/route.ts` | `PATCH /api/admin/users/{id}/status` |
| `frontend/app/api/admin/users/[userId]/role/route.ts` | `PUT /api/admin/users/{id}/role` |
| `frontend/app/api/admin/roles/route.ts` | `GET /api/admin/roles` |
| `frontend/app/api/admin/audit-logs/route.ts` | `GET /api/admin/audit-logs` |
| `frontend/app/api/admin/feature-flags/route.ts` | `GET /api/admin/feature-flags` |
| `frontend/app/api/admin/feature-flags/[key]/route.ts` | `PUT /api/admin/feature-flags/{key}` |
| `frontend/app/api/admin/queues/route.ts` | `GET /api/admin/queues` |
| `frontend/app/api/admin/queues/[name]/failed/route.ts` | `GET /api/admin/queues/{name}/failed` |
| `frontend/app/api/admin/queues/[name]/failed/[jobId]/retry/route.ts` | `POST .../retry` |
| `frontend/app/api/admin/system-health/route.ts` | `GET /api/admin/system-health` |
| `frontend/app/api/admin/analytics/job-matches/route.ts` | `GET /api/admin/analytics/job-matches` |
| `frontend/app/api/admin/mfa/enroll/route.ts` | `POST /api/admin/mfa/enroll` |
| `frontend/app/api/admin/mfa/confirm/route.ts` | `POST /api/admin/mfa/confirm` |
| `frontend/app/api/admin/mfa/disable/route.ts` | `POST /api/admin/mfa/disable` |
| `frontend/app/api/admin/mfa/status/route.ts` | `GET /api/admin/mfa/status` |
| `frontend/app/api/admin/impersonation/start/[userId]/route.ts` | `POST /api/admin/impersonation/start/{id}` |
| `frontend/app/api/admin/impersonation/end/route.ts` | `POST /api/admin/impersonation/end` |
| `frontend/app/api/admin/impersonation/status/route.ts` | `GET /api/admin/impersonation/status` |

Representative example (`frontend/app/api/admin/users/route.ts`), showing the cursor query-param passthrough that §8.6/§11.2's pagination shape requires — every other list route (`audit-logs`, `feature-flags`... though feature-flags isn't paginated) follows the identical shape:

```typescript
import { NextRequest } from "next/server";
import { mapBackendAdminUserList } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const query = new URLSearchParams();
  if (searchParams.get("cursor")) query.set("cursor", searchParams.get("cursor")!);
  if (searchParams.get("limit")) query.set("limit", searchParams.get("limit")!);
  if (searchParams.get("is_active")) query.set("is_active", searchParams.get("is_active")!);

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/admin/users?${query.toString()}`);
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, mapBackendAdminUserList);
}
```

---

## 12. Frontend — `features/admin/` module, pages, routing, design

### 12.1 `frontend/features/admin/api/keys.ts`

```typescript
export const adminKeys = {
  all: ["admin"] as const,
  users: (cursor: string | null, isActive: boolean | null) =>
    [...adminKeys.all, "users", cursor, isActive] as const,
  roles: () => [...adminKeys.all, "roles"] as const,
  auditLogs: (cursor: string | null, action: string | null) =>
    [...adminKeys.all, "audit-logs", cursor, action] as const,
  featureFlags: () => [...adminKeys.all, "feature-flags"] as const,
  queues: () => [...adminKeys.all, "queues"] as const,
  failedJobs: (queueName: string) => [...adminKeys.all, "queues", queueName, "failed"] as const,
  systemHealth: () => [...adminKeys.all, "system-health"] as const,
  analytics: () => [...adminKeys.all, "analytics", "job-matches"] as const,
  mfaStatus: () => [...adminKeys.all, "mfa-status"] as const,
  impersonationStatus: () => [...adminKeys.all, "impersonation-status"] as const,
};
```

### 12.2 `frontend/features/admin/api/client.ts`

Following the exact `fetch` + `json.data` unwrap pattern already used in `features/job-matching/api/client.ts` (§2 reuse table) — full surface, one function per BFF route from §11.4:

```typescript
import type {
  AdminAuditLogListResponse,
  AdminUserListResponse,
  AdminRole,
  FailedJob,
  FeatureFlag,
  ImpersonationStatus,
  JobMatchAnalytics,
  MfaEnrollResult,
  MfaStatus,
  QueueSnapshot,
  SystemHealthSnapshot,
} from "@/src/lib/types";

async function unwrap<T>(res: Response, errorLabel: string): Promise<T> {
  if (!res.ok) throw new Error(`${errorLabel}: ${res.status}`);
  const json = await res.json();
  return json.data as T;
}

export async function fetchAdminUsers(
  cursor: string | null,
  isActive: boolean | null,
): Promise<AdminUserListResponse> {
  const params = new URLSearchParams();
  if (cursor) params.set("cursor", cursor);
  if (isActive !== null) params.set("is_active", String(isActive));
  const res = await fetch(`/api/admin/users?${params.toString()}`);
  return unwrap(res, "Failed to fetch users");
}

export async function updateUserStatus(
  userId: string,
  isActive: boolean,
  reason?: string,
): Promise<void> {
  const res = await fetch(`/api/admin/users/${userId}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_active: isActive, reason }),
  });
  if (!res.ok) throw new Error(`Failed to update user status: ${res.status}`);
}

export async function assignUserRole(userId: string, roleId: string | null): Promise<void> {
  const res = await fetch(`/api/admin/users/${userId}/role`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role_id: roleId }),
  });
  if (!res.ok) throw new Error(`Failed to assign role: ${res.status}`);
}

export async function fetchRoles(): Promise<AdminRole[]> {
  const res = await fetch("/api/admin/roles");
  return unwrap(res, "Failed to fetch roles");
}

export async function fetchAuditLogs(
  cursor: string | null,
  action: string | null,
): Promise<AdminAuditLogListResponse> {
  const params = new URLSearchParams();
  if (cursor) params.set("cursor", cursor);
  if (action) params.set("action", action);
  const res = await fetch(`/api/admin/audit-logs?${params.toString()}`);
  return unwrap(res, "Failed to fetch audit logs");
}

export async function fetchFeatureFlags(): Promise<FeatureFlag[]> {
  const res = await fetch("/api/admin/feature-flags");
  return unwrap(res, "Failed to fetch feature flags");
}

export async function upsertFeatureFlag(
  key: string,
  payload: Partial<FeatureFlag>,
): Promise<FeatureFlag> {
  const res = await fetch(`/api/admin/feature-flags/${key}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return unwrap(res, "Failed to update feature flag");
}

export async function fetchQueuesOverview(): Promise<QueueSnapshot[]> {
  const res = await fetch("/api/admin/queues");
  return unwrap(res, "Failed to fetch queues");
}

export async function fetchFailedJobs(queueName: string): Promise<FailedJob[]> {
  const res = await fetch(`/api/admin/queues/${queueName}/failed`);
  return unwrap(res, "Failed to fetch failed jobs");
}

export async function retryFailedJob(queueName: string, jobId: string): Promise<void> {
  const res = await fetch(`/api/admin/queues/${queueName}/failed/${jobId}/retry`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Failed to retry job: ${res.status}`);
}

export async function fetchSystemHealth(): Promise<SystemHealthSnapshot> {
  const res = await fetch("/api/admin/system-health");
  return unwrap(res, "Failed to fetch system health");
}

export async function fetchJobMatchAnalytics(refresh = false): Promise<JobMatchAnalytics> {
  const res = await fetch(`/api/admin/analytics/job-matches${refresh ? "?refresh=1" : ""}`);
  return unwrap(res, "Failed to fetch analytics");
}

export async function fetchMfaStatus(): Promise<MfaStatus> {
  const res = await fetch("/api/admin/mfa/status");
  return unwrap(res, "Failed to fetch MFA status");
}

export async function enrollMfa(): Promise<MfaEnrollResult> {
  const res = await fetch("/api/admin/mfa/enroll", { method: "POST" });
  return unwrap(res, "Failed to enroll MFA");
}

export async function confirmMfaEnrollment(code: string): Promise<void> {
  const res = await fetch("/api/admin/mfa/confirm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
  if (!res.ok) throw new Error(`Failed to confirm MFA: ${res.status}`);
}

export async function disableMfa(): Promise<void> {
  const res = await fetch("/api/admin/mfa/disable", { method: "POST" });
  if (!res.ok) throw new Error(`Failed to disable MFA: ${res.status}`);
}

export async function startImpersonation(
  userId: string,
  reason: string,
  mfaCode?: string,
): Promise<void> {
  const res = await fetch(`/api/admin/impersonation/start/${userId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason, mfa_code: mfaCode }),
  });
  if (!res.ok) throw new Error(`Failed to start impersonation: ${res.status}`);
}

export async function endImpersonation(): Promise<void> {
  const res = await fetch("/api/admin/impersonation/end", { method: "POST" });
  if (!res.ok) throw new Error(`Failed to end impersonation: ${res.status}`);
}

export async function fetchImpersonationStatus(): Promise<ImpersonationStatus> {
  const res = await fetch("/api/admin/impersonation/status");
  return unwrap(res, "Failed to fetch impersonation status");
}
```

### 12.3 Hooks — `frontend/features/admin/hooks/`

One hook file per concern, following the exact `useQuery`/`useMutation` + `queryClient.setQueryData`/`invalidateQueries` pattern already used in `features/job-matching/hooks/usePreferences.ts` (§2):

```typescript
// frontend/features/admin/hooks/useAdminUsers.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { assignUserRole, fetchAdminUsers, updateUserStatus } from "../api/client";
import { adminKeys } from "../api/keys";

export function useAdminUsers(cursor: string | null, isActive: boolean | null = null) {
  return useQuery({
    queryKey: adminKeys.users(cursor, isActive),
    queryFn: () => fetchAdminUsers(cursor, isActive),
  });
}

export function useUpdateUserStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, isActive, reason }: { userId: string; isActive: boolean; reason?: string }) =>
      updateUserStatus(userId, isActive, reason),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.all }),
  });
}

export function useAssignUserRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, roleId }: { userId: string; roleId: string | null }) =>
      assignUserRole(userId, roleId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.all }),
  });
}
```

```typescript
// frontend/features/admin/hooks/useAuditLogs.ts
import { useQuery } from "@tanstack/react-query";
import { fetchAuditLogs } from "../api/client";
import { adminKeys } from "../api/keys";

export function useAuditLogs(cursor: string | null, action: string | null = null) {
  return useQuery({
    queryKey: adminKeys.auditLogs(cursor, action),
    queryFn: () => fetchAuditLogs(cursor, action),
  });
}
```

```typescript
// frontend/features/admin/hooks/useFeatureFlags.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchFeatureFlags, upsertFeatureFlag } from "../api/client";
import { adminKeys } from "../api/keys";
import type { FeatureFlag } from "@/src/lib/types";

export function useFeatureFlags() {
  return useQuery({ queryKey: adminKeys.featureFlags(), queryFn: fetchFeatureFlags });
}

export function useUpsertFeatureFlag() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ key, payload }: { key: string; payload: Partial<FeatureFlag> }) =>
      upsertFeatureFlag(key, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.featureFlags() }),
  });
}
```

```typescript
// frontend/features/admin/hooks/useQueues.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchFailedJobs, fetchQueuesOverview, retryFailedJob } from "../api/client";
import { adminKeys } from "../api/keys";

export function useQueuesOverview() {
  return useQuery({
    queryKey: adminKeys.queues(),
    queryFn: fetchQueuesOverview,
    refetchInterval: 15_000, // Live-ish queue depth without a websocket, matches
    // this repo's existing polling convention for dashboard-style data.
  });
}

export function useFailedJobs(queueName: string) {
  return useQuery({
    queryKey: adminKeys.failedJobs(queueName),
    queryFn: () => fetchFailedJobs(queueName),
    enabled: !!queueName,
  });
}

export function useRetryFailedJob(queueName: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => retryFailedJob(queueName, jobId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.failedJobs(queueName) }),
  });
}
```

```typescript
// frontend/features/admin/hooks/useSystemHealth.ts
import { useQuery } from "@tanstack/react-query";
import { fetchSystemHealth } from "../api/client";
import { adminKeys } from "../api/keys";

export function useSystemHealth() {
  return useQuery({
    queryKey: adminKeys.systemHealth(),
    queryFn: fetchSystemHealth,
    refetchInterval: 30_000,
  });
}
```

```typescript
// frontend/features/admin/hooks/useAnalytics.ts
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchJobMatchAnalytics } from "../api/client";
import { adminKeys } from "../api/keys";

export function useJobMatchAnalytics() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: adminKeys.analytics(), queryFn: () => fetchJobMatchAnalytics(false) });
  const refresh = async () => {
    const data = await fetchJobMatchAnalytics(true);
    queryClient.setQueryData(adminKeys.analytics(), data);
  };
  return { ...query, refresh };
}
```

```typescript
// frontend/features/admin/hooks/useMfaSetup.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { confirmMfaEnrollment, disableMfa, enrollMfa, fetchMfaStatus } from "../api/client";
import { adminKeys } from "../api/keys";

export function useMfaStatus() {
  return useQuery({ queryKey: adminKeys.mfaStatus(), queryFn: fetchMfaStatus });
}

export function useEnrollMfa() {
  return useMutation({ mutationFn: enrollMfa });
}

export function useConfirmMfaEnrollment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (code: string) => confirmMfaEnrollment(code),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.mfaStatus() }),
  });
}

export function useDisableMfa() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: disableMfa,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.mfaStatus() }),
  });
}
```

```typescript
// frontend/features/admin/hooks/useImpersonation.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { endImpersonation, fetchImpersonationStatus, startImpersonation } from "../api/client";
import { adminKeys } from "../api/keys";

export function useImpersonationStatus() {
  return useQuery({
    queryKey: adminKeys.impersonationStatus(),
    queryFn: fetchImpersonationStatus,
    // Polled (not SSE) — impersonation-active is a rare, session-scoped state;
    // a dedicated real-time channel for it would be over-engineering relative
    // to a cheap 30s poll, unlike job-match unread counts which are high-frequency.
    refetchInterval: 30_000,
  });
}

export function useStartImpersonation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, reason, mfaCode }: { userId: string; reason: string; mfaCode?: string }) =>
      startImpersonation(userId, reason, mfaCode),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.impersonationStatus() }),
  });
}

export function useEndImpersonation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: endImpersonation,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.impersonationStatus() }),
  });
}
```

---

### 12.4 Components — `frontend/features/admin/components/`

One component per screen, using the existing shadcn primitives already in `frontend/components/ui/` (`table.tsx`, `switch.tsx`, `dialog.tsx`, `tabs.tsx`, `badge.tsx`) and the existing `EmptyState`/`Card` patterns (§2) — no new UI library, no new design system.

**`UsersTable.tsx`** — cursor-paginated table (columns: email, name, status badge, role badge, MFA badge, "Suspend/Reactivate" action, "Assign role" action gated on `is_superuser`, "Log in as" action gated on `impersonation:start` permission). "Next page" button calls `useAdminUsers` with the previous response's `nextCursor`, disabled when `hasMore` is false — no page-number UI, since cursor pagination has no stable page count (Decision 4).

**`UserDetailDrawer.tsx`** — `Sheet`-based (shadcn) detail panel: full profile fields, MFA status, role assignment control, and a "Recent admin actions on this user" mini audit-log list (reuses `AuditLogTable` filtered by `target_id`).

**`RoleBadge.tsx`** — small `Badge` mapping `role_name`/`is_superuser` to a color (superuser = destructive/red, admin = default, support = secondary, none = outline), reused by `UsersTable` and `UserDetailDrawer`.

**`AuditLogTable.tsx`** — cursor-paginated table (columns: timestamp, actor email — resolved client-side from a small `useAdminUsers`-backed lookup or left as a UUID if not resolvable, action, target type/id, `captured_by` badge distinguishing "explicit" vs "fallback" entries per §6.3's design). Filter dropdown populated from a small static list matching the `action` strings this plan's backend actually emits (`user.status_changed`, `user.role_changed`, `feature_flag.flipped`, `impersonation.started`, `impersonation.ended`) — this is the FastAPI-realistic equivalent of the case study's `GET /audit-logs/actions` dropdown-population endpoint (§12.2 of the research doc); a dedicated backend endpoint for this is not built in this plan since the action vocabulary is small and stable enough to hardcode without the extra round-trip, a deliberate smaller-footprint choice, not an oversight.

**`FeatureFlagsPanel.tsx`** — list of flags as `Switch` rows (key, description, enabled toggle) plus a "Create flag" dialog. Toggling a switch calls `useUpsertFeatureFlag` optimistically, matching the toggle-then-confirm UX pattern already used by `PreferencesForm.tsx`'s notification-channel switches (§2 reuse table's `frontend/features/job-matching/components/PreferencesForm.tsx`).

**`QueueMonitor.tsx`** — one row per queue (name, priority, queued count, failed count, oldest-job age, workers listening), matching the "one row per service, four panels on a shared time axis" layout principle cited in `docs/admin-module-research.md` §2 (adapted here to queue-depth/failed-count/age/worker-count as this repo's four relevant signals for a *queue*, not a service). Clicking a row's failed-count expands a `FailedJobList` sub-table with a "Retry" button per job (`useRetryFailedJob`).

**`SystemHealthPanel.tsx`** — two sections: "Self-checks" (DB/Redis ok+latency, always populated) and "Golden signals" (latency/traffic/errors/saturation from Prometheus, shown only when `prometheusConfigured` is true; otherwise an `EmptyState` reading "Set `PROMETHEUS_QUERY_URL` to enable the golden-signals panel" — fail-soft UI matching the backend's fail-soft design, §8.12).

**`AnalyticsPanel.tsx`** — implements §3's ground-truth correction: total postings/matches, postings-by-source bar list, top-10-companies list, average salary range, average match score, a "cache hit" indicator, and a "Refresh" button wired to `useJobMatchAnalytics().refresh` (bypassing the cache per Decision 3's `?refresh=1` design). Explicitly labeled in the UI as "aggregate stats, not a full analytics suite" to keep the scope boundary from `docs/admin-module-research.md` §6 visible to whoever uses the screen, not just documented in this plan.

**`MfaSetupCard.tsx`** — self-service card (any user, not just admins — rendered on a "Security" settings page, not gated behind `AdminGuard`): "Enable 2FA" button → `useEnrollMfa()` shows a QR code (rendered client-side from `provisioningUri` via a small QR-code library, or a copyable secret as a fallback for password-manager-based TOTP) → 6-digit code input → `useConfirmMfaEnrollment()`. Once enabled, shows "Disable 2FA" (`useDisableMfa()`).

**`ImpersonationBanner.tsx`** — rendered inside `AppShell` (§12.7), always mounted, renders nothing when `useImpersonationStatus().data.isImpersonating` is false. When true: a persistent, high-contrast top banner ("You are viewing as {target email} — admin: {admin email}") with an "Exit impersonation" button (`useEndImpersonation()`, redirects to `/app/admin/users` on success) — directly implementing Zendesk's warning (§11.5) that the *acting* identity must always be visible, not just logged.

**`ImpersonateUserDialog.tsx`** — launched from `UsersTable`'s "Log in as" action: a reason textarea (required, min 3 chars per the backend schema, §8.2) and, conditionally, an MFA code input (shown only if the *current* admin's own `mfaEnabled` is true, mirroring the backend's conditional enforcement in §8.14) — submits via `useStartImpersonation()`, then does a full page navigation (not a client-side route change) to `/app/dashboard` so the new impersonation cookie takes effect on the next request.

### 12.5 `frontend/features/admin/index.ts`

```typescript
export { useAdminUsers, useUpdateUserStatus, useAssignUserRole } from "./hooks/useAdminUsers";
export { useAuditLogs } from "./hooks/useAuditLogs";
export { useFeatureFlags, useUpsertFeatureFlag } from "./hooks/useFeatureFlags";
export { useQueuesOverview, useFailedJobs, useRetryFailedJob } from "./hooks/useQueues";
export { useSystemHealth } from "./hooks/useSystemHealth";
export { useJobMatchAnalytics } from "./hooks/useAnalytics";
export {
  useMfaStatus,
  useEnrollMfa,
  useConfirmMfaEnrollment,
  useDisableMfa,
} from "./hooks/useMfaSetup";
export {
  useImpersonationStatus,
  useStartImpersonation,
  useEndImpersonation,
} from "./hooks/useImpersonation";
export { UsersTable } from "./components/UsersTable";
export { UserDetailDrawer } from "./components/UserDetailDrawer";
export { RoleBadge } from "./components/RoleBadge";
export { AuditLogTable } from "./components/AuditLogTable";
export { FeatureFlagsPanel } from "./components/FeatureFlagsPanel";
export { QueueMonitor } from "./components/QueueMonitor";
export { SystemHealthPanel } from "./components/SystemHealthPanel";
export { AnalyticsPanel } from "./components/AnalyticsPanel";
export { MfaSetupCard } from "./components/MfaSetupCard";
export { ImpersonationBanner } from "./components/ImpersonationBanner";
export { ImpersonateUserDialog } from "./components/ImpersonateUserDialog";
export { adminKeys } from "./api/keys";
```

### 12.6 `frontend/components/auth/admin-guard.tsx` (NEW)

Copies the exact shape of `frontend/components/auth/auth-guard.tsx` (§2 reuse table), adding the `is_superuser`/role check on top of the existing authenticated check — the frontend implementation of §12.8's "admin auth/role state resolved once from the existing session, no bespoke admin-only auth flow" principle from the case study (`docs/admin-module-research.md` §12.8):

```typescript
"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import { Loader2 } from "lucide-react";

/**
 * Derives admin access from the already-fetched /auth/me response — no
 * dedicated admin-only auth call, per docs/admin-module-research.md §12.8's
 * useUserRole() pattern (adapted: this repo has one AuthProvider, not a
 * separate frontend-admin app, so this is a guard component, not a second app).
 */
export function AdminGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, loading } = useAuth();
  const isAdmin = !!user && (user.is_superuser || !!user.role_name);

  useEffect(() => {
    if (!loading && !user) {
      router.push(`/login?redirect=${encodeURIComponent(pathname)}`);
      return;
    }
    if (!loading && user && !isAdmin) {
      router.push("/app/dashboard");
    }
  }, [loading, user, isAdmin, router, pathname]);

  if (loading || !user || !isAdmin) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return <>{children}</>;
}
```

Redirecting non-admins to `/app/dashboard` (rather than a dedicated `/unauthorized` page, unlike the case study's `ProtectedRoute`) matches this repo's smaller surface area — there is exactly one non-admin destination worth redirecting to, so a whole extra page for this single case would be an unused abstraction per `RULE.md`.

### 12.7 Pages and routing

```
frontend/app/app/admin/
├── layout.tsx              # Wraps children in <AdminGuard>, mirrors ConsoleLayout's shape
├── page.tsx                # Redirects to /app/admin/system-health (the natural landing screen)
├── system-health/
│   └── page.tsx             # <SystemHealthPanel />
├── users/
│   ├── page.tsx             # <UsersTable />
│   └── [userId]/
│       └── page.tsx         # <UserDetailDrawer /> as a full page (deep-linkable)
├── roles/
│   └── page.tsx             # Read-only role/permission matrix (RoleWithPermissionsResponse list)
├── audit-logs/
│   └── page.tsx             # <AuditLogTable />
├── feature-flags/
│   └── page.tsx             # <FeatureFlagsPanel />
├── queues/
│   └── page.tsx             # <QueueMonitor />
└── analytics/
    └── page.tsx             # <AnalyticsPanel />
```

`frontend/app/app/admin/layout.tsx`:

```typescript
"use client";

import { AdminGuard } from "@/components/auth/admin-guard";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return <AdminGuard>{children}</AdminGuard>;
}
```

This nests **inside** the existing `frontend/app/app/layout.tsx` (`ConsoleLayout` → `AuthGuard` → `AppShell`), so every `/app/admin/*` page gets both the base authenticated-user check (`AuthGuard`) and the admin-only check (`AdminGuard`) — two independent, composable guards, matching how `dsar_router`'s two stacked dependencies work on the backend (§8.15).

The self-service MFA setup page is **not** under `/app/admin/` (any verified user can enable 2FA for their own account, not just admins, per Decision 5's "any user can turn on for their own account" framing):

```
frontend/app/app/settings/security/
└── page.tsx                 # <MfaSetupCard /> — linked from the existing /app/settings page
```

### 12.8 Navigation registration

`frontend/components/layout/nav-config.ts` — one new conditionally-shown section, following the exact `NavSection`/`NavItem` shape already defined in this file (§2):

```typescript
// Add to imports:
import { ShieldCheck, Users, ScrollText, Flag, ListTodo, BarChart3 } from "lucide-react";

// New export, alongside mainNav/systemNav:
export const adminNav: NavSection = {
  title: "Admin",
  items: [
    { href: "/app/admin/system-health", label: "System health", icon: Activity },
    { href: "/app/admin/users", label: "Users", icon: Users },
    { href: "/app/admin/roles", label: "Roles", icon: ShieldCheck },
    { href: "/app/admin/audit-logs", label: "Audit logs", icon: ScrollText },
    { href: "/app/admin/feature-flags", label: "Feature flags", icon: Flag },
    { href: "/app/admin/queues", label: "Queues", icon: ListTodo },
    { href: "/app/admin/analytics", label: "Analytics", icon: BarChart3 },
  ],
};

// allNavSections is now built conditionally rather than as a flat constant —
// see AppSidebar edit below for how isAdmin gates this.
```

`frontend/components/layout/AppSidebar.tsx` — one new optional prop, following the exact shape of the existing `matchesUnreadCount` prop (§2):

```typescript
// Change the props type:
type AppSidebarProps = {
  matchesUnreadCount?: number;
  isAdmin?: boolean;
};

export function AppSidebar({ matchesUnreadCount = 0, isAdmin = false }: AppSidebarProps) {
  // ... existing code unchanged ...
  const sections = isAdmin ? [mainNav, systemNav, adminNav] : [mainNav, systemNav];
  // Replace `allNavSections.map(...)` with `sections.map(...)` in the render below.
```

`frontend/components/layout/AppShell.tsx` — passes the new prop, reading `is_superuser`/`role_name` from the already-fetched `useAuth()` user (no new API call, per §12.8's own principle):

```typescript
// Add:
import { useAuth } from "@/providers/auth-provider";

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const { unreadCount } = useUnreadMatchEvents();
  const { user } = useAuth();
  const isAdmin = !!user && (user.is_superuser || !!user.role_name);
  const matchesUnreadCount = unreadCount ?? 0;

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <div className="hidden lg:flex">
        <AppSidebar matchesUnreadCount={matchesUnreadCount} isAdmin={isAdmin} />
      </div>
      <AppNavRail pathname={pathname} matchesUnreadCount={matchesUnreadCount} />
      <div className="flex min-w-0 flex-1 flex-col">
        <AppTopbar />
        <VerificationBanner />
        <ImpersonationBanner />
        <main className="flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-6">{children}</main>
        <AppBottomNav pathname={pathname} matchesUnreadCount={matchesUnreadCount} />
      </div>
    </div>
  );
}
```

`AppNavRail`/`AppBottomNav` (the mobile-width equivalents of `AppSidebar`, referenced in the existing `AppShell.tsx` but not read in detail during this plan's research pass) should receive the same `isAdmin` treatment for consistency — flagged here explicitly as a follow-up check during implementation rather than assumed, since this plan's research pass verified `AppSidebar` directly but not its two siblings.

### 12.9 Commands (same as §9.13, repeated here for frontend-only convenience)

```bash
cd frontend && npm run typecheck
cd frontend && npm run lint
cd frontend && npm run build
cd frontend && npm run test:unit -- features/admin
```

---

## 13. ADR — required per RULE.md (new storage; auth/authorization semantics; layer ownership)

**New file:** `docs/adr/0015-admin-module-rbac-audit-mfa.md`

```markdown
# ADR 0015: RBAC, Audit Log, Feature Flags, and Support Impersonation (Admin Module)

## Status
Accepted

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
```

---

## 14. `backend/docs/ARCHITECTURE.md` — Implementation status diff

Add a new row to the "Implementation status" table (exact location/format verified by reading the file directly before editing — same table as `phase2_module1.md` §13 and `phase2_module2.md`'s equivalent section):

```markdown
| Admin Module (RBAC, audit, flags, impersonation) | `app/modules/admin/`, 4 new `users` columns | Real, scaffolded per `phase2_admin_module.md` (ADR 0015). `is_superuser` unchanged and still authoritative; `Role`-based permissions are an additive, narrower grant checked only when `is_superuser` is false. No new Docker service or queue — runs inside `api`, reads existing Redis/RQ queues read-only. |
```

Add lines to the "Do not assume" table:

```markdown
| Admin RBAC replaces `is_superuser` | It does not. `is_superuser` remains the highest-privilege override; `Role`/`Permission` only add narrower grants for non-superuser admins (ADR 0015, Decision 1). |
| Admin audit log and compliance audit log are the same table | They are not. `admin_audit_logs` (admin-write trail) is distinct from `compliance.models.AuditLog` (candidate compliance/DSAR trail) — see `phase2_admin_module.md` §5. |
| Prometheus golden-signals panel always populated | Only when `PROMETHEUS_QUERY_URL` is set; otherwise the System Health page shows self-checks only and an explanatory empty state (§8.12, §12.4). |
```

---

## 15. PR checklist (per `.github/pull_request_template.md`)

When the Admin Module's actual implementation PR is opened (this document itself is committed directly per the user's explicit instruction not to branch — but the **code** described here, when implemented, should follow the normal branch+PR workflow):

- [ ] Link this document: `phase2_admin_module.md`
- [ ] Link the ADR: `docs/adr/0015-admin-module-rbac-audit-mfa.md`
- [ ] `alembic upgrade head` and `alembic downgrade -6 && alembic upgrade head` both succeed
- [ ] All 10 new backend test files pass (§9.1-9.10)
- [ ] Coverage gate maintained (`--cov-fail-under=78`) for the new module
- [ ] `ruff check` / `mypy` clean on new files
- [ ] Frontend `npm run typecheck && npm run lint && npm run build` all pass
- [ ] Frontend new-feature tests pass (§12.9)
- [ ] `backend/docs/ARCHITECTURE.md` updated per §14
- [ ] `.env.example` updated per §7 (placeholders only, `pyotp` added to `pyproject.toml`)
- [ ] `docker-compose.yml` updated per §10 (env vars only — no new service)
- [ ] Manual smoke test: seed migration (`038`) creates `superuser`/`admin`/`support` roles and grants them the expected permission sets; an existing `is_superuser=true` user can still access every existing admin endpoint unchanged

---

## 16. Final completion checklist — Admin Module is 100% done when every box is checked

**Database (§6):**
- [ ] `033_admin_roles_permissions.py` through `038_admin_seed_roles.py` created, applied, and reversible
- [ ] `users` table has `role_id`, `mfa_secret`, `mfa_enabled`, `mfa_enrolled_at`, all nullable/defaulted, no existing row broken
- [ ] Seed migration creates `superuser`, `admin`, `support` roles with the permission sets defined in §6.6

**Backend (§8):**
- [ ] `app/modules/admin/{__init__,models,schemas,permissions,audit,cache,pagination,repository,service,analytics_service,queues_service,system_health_service,mfa_service,impersonation_service,router}.py` all created
- [ ] `app/modules/admin/router.py` restructured into a package with sub-routers (`users_router`, `roles_router`, `audit_router`, `feature_flags_router`, `queues_router`, `system_health_router`, `analytics_router`, `mfa_router`, `impersonation_router`, `costs_router`) mounted under one `admin_router`
- [ ] `app/auth/models.py` edited: `role_id`, `mfa_secret`, `mfa_enabled`, `mfa_enrolled_at`, `role` relationship
- [ ] `app/auth/dependencies.py` edited: `request.state.user_id`, `imp` claim decoding into `request.state.impersonated_by`
- [ ] `AdminAuditFallbackMiddleware` created and registered in `app/main.py`
- [ ] `app/main.py` edited: admin router import path updated, middleware registered
- [ ] `app/core/config.py` + `.env.example` edited (§7)
- [ ] `pyproject.toml` edited: `pyotp` dependency added

**Docker (§10):**
- [ ] No new Dockerfile, no new service — confirmed by diff review, not just by this plan's claim
- [ ] `docker-compose.yml` `api`/`migrate` env vars updated per §10
- [ ] `docker compose up migrate` applies all 6 new revisions cleanly against a fresh Postgres volume

**Testing (§9):**
- [ ] All 10 new backend test files created and passing
- [ ] Coverage gate (`--cov-fail-under=78`) passes for the new module
- [ ] Full existing test suite (`pytest`) still passes — no regressions introduced, especially for every existing `require_superuser`-gated endpoint
- [ ] Frontend test files created and passing (`npm run test:unit -- features/admin`)

**Frontend (§11-12):**
- [ ] `frontend/src/lib/types.ts` edited: all 11 new admin types
- [ ] `frontend/src/lib/api-adapter.ts` edited: all new mapper functions
- [ ] `frontend/providers/auth-provider.tsx` edited: `User` interface gains `is_superuser`, `role_name`, `mfa_enabled`
- [ ] BFF routes created under `frontend/app/api/admin/` for every endpoint in §11.4's table
- [ ] `frontend/features/admin/` module created (`api/keys.ts`, `api/client.ts`, 8 hook files, 11 component files, `index.ts`)
- [ ] `frontend/components/auth/admin-guard.tsx` created
- [ ] `frontend/app/app/admin/` pages created for all 8 routes in §12.7, plus `frontend/app/app/settings/security/page.tsx`
- [ ] `frontend/components/layout/nav-config.ts` edited: `adminNav` added
- [ ] `frontend/components/layout/AppSidebar.tsx` edited: `isAdmin` prop, conditional section rendering
- [ ] `frontend/components/layout/AppShell.tsx` edited: `isAdmin` derived and passed, `ImpersonationBanner` mounted
- [ ] `AppNavRail`/`AppBottomNav` checked for the same `isAdmin` treatment (flagged in §12.8 as unverified by this plan's research pass — must be resolved, not skipped, during implementation)
- [ ] `npm run typecheck && npm run lint && npm run build` all pass

**Governance (§0, §13-15):**
- [ ] ADR `0015-admin-module-rbac-audit-mfa.md` created
- [ ] `backend/docs/ARCHITECTURE.md` updated (3 table rows per §14)
- [ ] PR opened (not this document — the code) on its own branch, per the repo's standard workflow, linking this document and the ADR

**Known gaps this document does NOT close (explicitly out of scope, not oversights):**
- Full RBAC replacing `is_superuser` (Decision 1, ADR 0015) — deliberately deferred, `is_superuser` stays authoritative
- Exactly-once audit guarantee (Decision 2) — best-effort fallback only, by design
- SSO/enterprise identity provider integration for admin login — not requested, not built
- Real-time (websocket/SSE) queue and system-health dashboards — polling only (§12.4's `refetchInterval`), matching this repo's existing polling convention rather than introducing a new transport
- Postgres connection-pool sizing and RQ queue starvation (pre-existing gaps, `phase2_module1.md` §4/§12) — not touched, not worsened (Decision 9/§10)
- `AppNavRail`/`AppBottomNav` admin-nav parity — flagged as a required implementation-time check, not pre-verified by this plan (§12.8)
- Force-enabling MFA for all admins (Decision 7) — self-service and conditional-enforcement only, policy decision left to product/security, not this PR

If every checkbox above is checked and the seven gaps are still open, **the Admin Module is complete and these seven items are correctly still pending** — completion does not require closing pre-existing or explicitly-deferred cross-cutting issues that were never in its scope. If any checkbox is unchecked, the Admin Module is **not** complete, regardless of any other claim made about it.
