# Admin Module — Validation Guide & Test Plan (for your colleague)

**Purpose of this document:** a self-contained guide so a colleague who did **not** write the Admin Module can (1) understand in plain language what it does, (2) verify every feature is actually present and working across Phase 1 and Modules 1–4, (3) know exactly how to test it (unit, integration, smoke, real-world), and (4) know what's still missing and what to do about it.

**Companion documents this plan updates/extends (do not duplicate — read these for full technical detail):**
- `phase2_admin_module.md` (root of `feat/admin-module`) — the original implementation blueprint the user pasted into this plan. **Status: superseded in parts** — see §1.
- `docs/admin-module-research.md`, `docs/admin-module-phase2-tracking-research.md` — the research trail behind the design decisions.
- `docs/adr/0015-admin-module-rbac-audit-mfa.md`, `docs/adr/0016-phase2-moderation-review-queue.md` — the architectural decisions.

**Important framing before anything else:** as of this writing, the Admin Module lives on `feat/admin-module` (not yet merged into `master-complete-foundation`), and it has **already grown well beyond** the plan the user pasted. The pasted plan describes RBAC + audit + feature flags + MFA + impersonation + queues + system health + analytics only. The real branch **already has all of that, plus** a full Phase-2 moderation/review-queue layer (job postings, documents, portfolio, outreach), plus an extensive automated test suite, a live HTTP smoke script, and Playwright e2e tests. Section 1 below is the accurate, current picture — treat the pasted plan as historical context, not the source of truth for "what exists today."

---

## 1. What actually exists today vs. the pasted plan

| Area | Pasted plan says | Actual `feat/admin-module` branch has |
|---|---|---|
| RBAC (roles/permissions) | To be built | ✅ Built — `roles`, `permissions`, `role_permissions` tables, seeded `support`/`admin` roles, `require_permission()` dependency |
| Audit log | To be built | ✅ Built — `admin_audit_logs` table, `record_admin_action()`, `AdminAuditFallbackMiddleware` safety net |
| Feature flags | To be built | ✅ Built — `feature_flags` table + CRUD + cache |
| MFA (TOTP) | To be built | ✅ Built — enroll/confirm/disable, `pyotp`-based |
| Impersonation | To be built | ✅ Built — scoped JWT `imp` claim, `impersonation_sessions`, MFA-gated start |
| Queue monitor (RQ) | To be built | ✅ Built — read-only queue depth/failed-jobs/retry |
| System health | To be built | ✅ Built — DB/Redis self-checks; Prometheus panel **exists but is wired to metrics that don't exist yet** (see §4.4) |
| Job-match analytics | To be built | ✅ Built — cached aggregate over `job_postings`/`job_matches` |
| **Moderation / review queue** (job postings, documents, portfolio, outreach) | **Not mentioned at all** | ✅ Built — generic `admin_review_queue` table + per-domain moderation columns + per-domain moderation routers (`job_postings_router.py`, `portfolio_router.py`, `outreach_router.py`, `documents_router.py`) + `review_queue_router.py` |
| Module 3 (interview prep) admin coverage | Not mentioned | 🟡 **Stub only** — `questions_router.py` / `practice_audio_router.py` return `501 Not Implemented` on every route, deliberately, until this plan's real wiring lands (§3) |
| Module 4 (application tracker, interview scheduling, manual job entries) admin coverage | Not mentioned | ❌ **Does not exist** — no admin router touches `application_status`, interview scheduling, or manual job entries at all |
| Test suite | Not mentioned | ✅ 20 backend test files, 1 live HTTP smoke script (`scripts/smoke_admin_live.py`), 1 Playwright e2e spec (`frontend/e2e/integration/admin.spec.ts`) — see §6.1 for the full inventory |
| CORS / rate limiting on any admin, Module 3, or Module 4 route | Not mentioned | ❌ **Not wired anywhere** — see §4.3 |
| Traffic monitoring (request-level metrics) | Not mentioned | ❌ **Does not exist anywhere in the backend** — see §4.4 |
| Merged into `master-complete-foundation` | Assumed complete | ❌ **Not merged yet** — `feat/admin-module`, `feat/phase2-module4-application-lifecycle`, and `integration/cors-rate-limit` are still three separate branches |

**Bottom line for your colleague:** most of the *backend logic* for the Admin Module is real, tested, and good. The three genuinely missing pieces are **(a)** wiring it up to Modules 3 and 4, **(b)** CORS/rate-limit coverage on the whole module, and **(c)** real traffic monitoring. Those three are the actual test/validation targets of this document, on top of re-confirming the parts that already exist actually work once everything is merged together.

---

## 2. The Admin Module, explained simply

Think of the Admin Module as the "back office" of the product — a set of screens and APIs that only staff (not candidates) can use, to operate the platform safely. Nine capabilities, explained one at a time:

### 2.1 Roles & permissions (RBAC)
**What it is:** a way to give a staff member *some* admin powers without giving them *all* of them. Example: a support agent can suspend a user account and read audit logs, but cannot assign roles or see other admins' actions.
**Why it matters:** without this, every admin either has zero power or god-mode (`is_superuser`). That's risky — a support agent shouldn't be able to do everything a founder can.
**How it works:** every user can have a `role` (e.g. "support" or "admin"). Each role has a list of permissions like `users:read`, `queues:retry`. A special `is_superuser` flag always overrides everything — it's kept as the ultimate safety net, separate from the role system.

### 2.2 Audit log
**What it is:** a permanent record of "who did what, to whom, when" for every admin action — suspending a user, flipping a feature flag, approving/rejecting a moderation item, starting an impersonation session.
**Why it matters:** if something goes wrong (a user complains "why was my account suspended?"), there must be a record. It's also how you'd investigate misuse by a staff member.
**How it works:** every admin action calls a function that writes one row (actor, action, target, before/after values, IP address, timestamp). As a backup, if a developer forgets to add that call, a background safety-net logs a generic entry anyway — so nothing goes fully unlogged.

### 2.3 Feature flags
**What it is:** on/off switches for behavior, stored in the database, changeable without a code deploy.
**Why it matters:** lets you turn something off instantly (e.g. a broken feature) instead of waiting for a deploy.
**How it works:** a table of `key -> enabled/value`, with a small cache so checking a flag doesn't hit the database on every request.

### 2.4 Multi-factor authentication (MFA)
**What it is:** the standard "6-digit code from your phone app" second login step (TOTP — same tech as Google Authenticator).
**Why it matters:** admin accounts are high-value targets. A stolen password alone shouldn't be enough to act as an admin, especially to impersonate another user.
**How it works:** any user can turn it on for their own account. It is **required** specifically before starting an impersonation session (see 2.5) if the admin has it enabled — that's the one place this plan currently enforces it.

### 2.5 Impersonation ("log in as this user")
**What it is:** lets a support admin see the product exactly as a specific candidate sees it, to debug their problem.
**Why it matters:** "log in as user" is the single most sensitive support tool that exists — done wrong, it's a privacy/security incident waiting to happen.
**How it works:** requires a typed reason, requires MFA if the admin has it enabled, is time-limited (auto-expires), is logged at start and end, and shows a persistent on-screen banner the whole time so nobody forgets they're impersonating.

### 2.6 Queue monitor
**What it is:** a dashboard of the background job queues (the same queues that already process CV parsing, embeddings, job matching, etc.) — how many jobs are waiting, how many failed, and a "retry" button for failed ones.
**Why it matters:** background jobs fail sometimes (a third-party API times out, etc.). Today, without this screen, the only way to see that is reading server logs.
**How it works:** reads the *existing* job queues directly — it does **not** create any new queue.

### 2.7 System health
**What it is:** one screen: "is the database up? is Redis up? how fast are they responding?" Optionally, if Prometheus is configured, a "four golden signals" panel (traffic, latency, errors, saturation).
**Why it matters:** the fastest way to answer "is something broken right now?" without digging through logs.
**⚠️ Known issue:** the golden-signals panel currently queries metric names (`http_requests_total`, `http_request_duration_seconds_bucket`) that **don't exist anywhere in this codebase yet** — see §4.4. Until that's fixed, this panel will always show empty/blank values even with Prometheus configured.

### 2.8 Analytics (job-match aggregate stats)
**What it is:** simple counts and averages over the existing job postings/matches data — total postings, postings by source, top companies, average salary range, average match score.
**Why it matters:** a quick operational pulse-check ("is job scraping actually bringing in postings?"), not a full BI dashboard.

### 2.9 Moderation & review queue
**What it is:** a generic "flagged content" inbox. Job postings, uploaded documents, portfolio pages, and outreach messages can be automatically flagged (by keyword rules or an LLM check) or reported, and an admin reviews each flagged item and decides "approve" or "reject." Rejecting hides/blocks the item (e.g. sets `admin_hidden`/`admin_blocked`/`deleted_at` on the underlying row).
**Why it matters:** any platform with user-generated content (job postings from scraping, candidate documents, portfolio pages, outreach messages) needs a way to catch and act on bad content — spam, scams, policy violations — before it causes harm.
**How it works:** one shared `admin_review_queue` table for all four content types (`resource_type` + `resource_id`), so the UI and API are the same regardless of which kind of content is flagged.

---

## 3. Feature-to-Phase/Module map (what a colleague should expect to see, and where)

| Phase/Module | What it built | What the Admin Module gives visibility/control over it | Current status |
|---|---|---|---|
| **Phase 1 (Foundation)** — users, auth, cookie-JWT sessions | `app/auth/` | Users list/suspend, role assignment, MFA self-service, impersonation, audit trail of every admin action taken against a user | ✅ Done |
| **Module 1** — job matching (`job_postings`, `job_matches`, scraping) | `app/modules/job_matching/` | Job-match analytics (§2.8); job-postings moderation — hide a bad scraped posting (§2.9) | ✅ Done |
| **Module 2** — documents (CV upload/parse), portfolio, outreach | `app/modules/documents/`, `app/modules/portfolio/`, `app/modules/outreach/` | Documents moderation (soft-delete via `deleted_at`), portfolio moderation (`admin_hidden`), outreach moderation (`admin_blocked`) | ✅ Built, but see §4.2 — one enforcement gap |
| **Module 3** — interview question bank, practice audio/sessions | `app/modules/interview_prep/` (or equivalent — verify exact path at implementation time) | Admin should be able to read/moderate interview questions and practice-audio content | 🟡 **Stub only — `501 Not Implemented` on every route.** Real wiring is this plan's job (§4.1) |
| **Module 4** — application tracker (`application_status`, `applied_at`), interview scheduling, manual job entries | `app/auth/models.py` (`application_status` etc.), `app/modules/job_matching/models.py` (`is_manual`, `manual_job_entry_id`), interview scheduling module | Admin should be able to see/moderate applications, interview schedules, and manually-entered jobs | ❌ **Does not exist.** New routers needed (§4.1) |
| **CORS + rate limiting** (`integration/cors-rate-limit`) | Multi-origin CORS allowlist, sliding-window Redis rate limiter, per-scope limits (auth, sync, async, documents, compliance, signals webhook, job-matching scan) | Every admin, Module 3, and Module 4 route should sit behind the same CORS policy and an appropriate rate-limit scope | ❌ **Not wired to admin, Module 3, or Module 4 routes at all today** (§4.3) |
| **Traffic monitoring** | — | System Health's "golden signals" panel should show real request volume/latency/error-rate | ❌ **Metrics referenced don't exist anywhere in the codebase** (§4.4) |

---

## 4. Addendum to the original plan — Module 3/4 wiring, CORS/rate-limit, and traffic monitoring

This section is the actual "update" the user asked for: extending `phase2_admin_module.md` to cover what it didn't.

### 4.1 Module 3 and Module 4 admin wiring

**Module 3 (interview prep) — replace the stubs, don't rebuild them.**
`backend/app/modules/admin/questions_router.py` and `practice_audio_router.py` already exist as intentional placeholders (verified: every route returns `501`, and `backend/tests/test_admin_module3_placeholder_routes.py` asserts exactly that today, mounting them on a throwaway `FastAPI()` app since they're deliberately **not** wired into `app/modules/admin/__init__.py` yet). The task here is:
1. Read the real Module 3 domain module (question bank, practice sessions/audio — confirm exact file paths under `app/modules/interview_prep/` or wherever Module 3 landed) to find its real models/service functions.
2. Replace each `501` handler in `questions_router.py`/`practice_audio_router.py` with a real implementation that calls into that service layer (list/read questions, moderate a question, list/read practice audio, flag/moderate practice audio) — following the exact same shape as `job_postings_router.py`/`portfolio_router.py` (`require_permission(...)`, call repository/service, `record_admin_action(...)`).
3. Wire both routers into `app/modules/admin/__init__.py`'s aggregator (they are the **only** two sub-routers not yet aggregated — every other admin sub-router already is, per the `__init__.py` reuse shown in §2 research).
4. Delete or repurpose `test_admin_module3_placeholder_routes.py`'s "verify these return 501" assertions — once real, a `501` response is a regression, not the expected behavior. Replace with the same request/response/RBAC/audit test shape used in `test_admin_job_postings_moderation.py`.

**Module 4 (application tracker, interview scheduling, manual job entries) — new admin routers, following the existing per-domain moderation pattern.**
None of this exists yet. Add, one per Module 4 feature, in the same shape as `job_postings_router.py`:
- `app/modules/admin/applications_router.py` — `GET /api/admin/applications` (cursor-paginated list, filterable by `application_status`), `GET /api/admin/applications/{user_id}` (one candidate's full application history) — read/moderate permission: `require_permission("applications", "read"|"moderate")`.
- `app/modules/admin/interview_schedules_router.py` — `GET /api/admin/interview-schedules` (list, filterable by date range/status), moderate action if the domain model supports cancelling/flagging a scheduled interview — `require_permission("interview_schedules", "read"|"moderate")`.
- `app/modules/admin/manual_job_entries_router.py` — `GET /api/admin/manual-job-entries` (list `JobPosting` rows where `is_manual=True`), `PATCH /api/admin/manual-job-entries/{id}/moderate` (approve/reject a user-submitted manual job entry before it's visible in matching) — `require_permission("manual_job_entries", "read"|"moderate")`.

Each new router: read-only list + one moderate/decide action, `EnvelopeAPIRoute`, `record_admin_action()` on every mutation, wired into `app/modules/admin/__init__.py`'s aggregator alongside everything else, new `Permission` rows added to the seed migration (`("applications","read")`, `("applications","moderate")`, `("interview_schedules","read")`, `("interview_schedules","moderate")`, `("manual_job_entries","read")`, `("manual_job_entries","moderate")`), each granted to the `admin` role (not `support`, unless product decides otherwise — these are Module 4 domain-moderation actions, a step up from the `support` role's existing read-only + suspend scope).

Frontend: one new BFF route + hook + panel component per feature, following the exact `frontend/features/admin/` layout convention already used by every other panel (`ApplicationsPanel.tsx`, `InterviewSchedulesPanel.tsx`, `ManualJobEntriesPanel.tsx`), plus three new items in `adminNav`.

### 4.2 One existing enforcement gap to close while wiring this up

`outreach_messages.admin_blocked` is set by the moderation "reject" action, but verify at implementation time whether the actual outreach-sending code path (`app/modules/outreach/service.py` or wherever messages are actually dispatched) checks `admin_blocked` before sending. If it doesn't, a blocked message could still go out — the column exists and the audit trail records the block, but the block itself may not be enforced at the point that matters. This is a one-line `if message.admin_blocked: raise/skip` check, but it must be verified directly against the code, not assumed present just because the column exists (the same caution `docs/admin-module-phase2-tracking-research.md` §"Ground truth already mapped" already applies to the portfolio `admin_hidden` check).

### 4.3 CORS and rate limiting — wire into every admin, Module 3, and Module 4 route

**Current state (verified directly):** `integration/cors-rate-limit`'s rate-limit dependencies (`backend/app/dependencies/rate_limit.py`) define seven scopes — `sync`, `async`, `compliance`, `auth`, `documents`, `signals`, `job_matching` — applied only to their own modules' routes. **None of the Admin Module's ~40 routes, and none of Module 3/4's routes, have any rate-limit dependency applied.** CORS itself (the `CORSMiddleware` origin/method/header allowlist in `app/main.py`) is global, so every route — including admin — already gets CORS treatment; the gap is specifically rate limiting, plus confirming CORS's `allow_methods`/`allow_headers` tightening doesn't accidentally block an admin-only verb (e.g. `PATCH`/`PUT`, both used heavily by admin routes).

**What to add:**
1. A new rate-limit scope, `admin`, in `rate_limit.py`: `enforce_admin_rate_limit()`, keyed per-admin-user (reuse `_client_id`), with a new setting `max_admin_requests_per_minute` (suggested default: higher than `sync`'s candidate-facing limit, since a small number of trusted staff should not be throttled during normal use — e.g. 120/min — but still bounded so a runaway frontend polling bug or a compromised admin token can't hammer the DB unbounded).
2. Apply `Depends(enforce_admin_rate_limit)` at the `app.include_router(admin_router, dependencies=[...])` call in `main.py` (one dependency, covers all ~40+ admin routes including the new Module 3/4 ones — matches how `current_verified_user` is already applied there today) rather than repeating it on every individual router.
3. For the two highest-blast-radius admin actions specifically, add a **second, tighter** scope on top of the blanket `admin` one: `enforce_admin_impersonation_rate_limit` (e.g. 5/min) on `POST /api/admin/impersonation/start/{user_id}`, and `enforce_admin_mutation_rate_limit` (e.g. 30/min) on role-assignment/user-suspend — both layered the same way `job_matching_router.py` already layers `enforce_job_matching_scan_rate_limit` on top of the blanket auth dependency (this repo already has precedent for "one global rate limit + one tighter route-specific one" — verify the exact existing example directly before copying it, per `RULE.md`).
4. `.env.example` gets `MAX_ADMIN_REQUESTS_PER_MINUTE=120` (placeholder, matching every other `MAX_*_REQUESTS_PER_MINUTE` var's existing style).
5. CORS: confirm `allow_methods` includes `PATCH`/`PUT`/`DELETE` (needed by user-status, role-assignment, feature-flag, and every new Module 3/4 moderate endpoint) and `allow_headers` includes whatever the frontend BFF actually sends (`Content-Type`, `X-Request-ID` if used) — a 5-minute direct read of the current `CORSMiddleware(...)` call in `main.py`, not a guess.

### 4.4 Traffic monitoring — the gap the user specifically asked about

**Answer: no, this codebase does not have general HTTP traffic monitoring today.** Verified directly (not inferred):
- `backend/app/observability/` has `tier_metrics.py`, `tier1_metrics.py`, `job_matching_metrics.py`, `session_metrics.py`, `cost_tracking.py`, `budget_alerts.py`, `error_tracking.py`, `health_alerts.py` — all **feature-specific** counters (enrichment tiers, job matching, sessions, cost). None of them track generic per-request volume, latency, or status code across the whole API.
- `backend/app/core/logging.py`'s `RequestContextMiddleware` only assigns a correlation `request_id` for log lines — it does not record any Prometheus metric.
- `GET /metrics` (in `app/modules/health/router.py`) is real and does export whatever Prometheus counters/histograms are registered process-wide — but since no generic request counter/histogram is registered anywhere, `/metrics` never emits `http_requests_total` or `http_request_duration_seconds_bucket`.
- The Admin Module's own `app/modules/admin/health.py::_query_golden_signals()` queries exactly those two metric names (`http_requests_total`, `http_request_duration_seconds_bucket`) against Prometheus. **This means the golden-signals panel is wired to a Prometheus query that will always return empty results, even in a fully deployed, correctly-configured production environment**, because nothing ever populates those series. This is a real bug to fix, not a hypothetical.
- The rate limiter (`rate_limit.py`) has no counter either — a burst of `429`s today produces log lines (`logger.warning` only on Redis failure, not on every rejection) and a `RateLimitError` response, but no metric a dashboard could alert on.

**What to add (small, standard, no new infrastructure):**
1. Add `prometheus-fastapi-instrumentator` (a small, widely-used, actively maintained library — MIT license, zero new services) to `backend/pyproject.toml`. In `app/main.py`, `Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)` — replacing the current hand-written `/metrics` handler in `health/router.py`, or calling `Instrumentator` and letting the existing route continue to call `generate_latest()` (either works, since both read from the same global Prometheus registry; pick whichever requires fewer changes once you've read the exact current `/metrics` route implementation). This one call is what actually produces `http_requests_total{method,handler,status}` and `http_request_duration_seconds_bucket{method,handler}` — the exact two series `admin/health.py` already expects.
2. Add one small `Counter` for rate-limit rejections specifically, e.g. `rate_limit_rejections_total{scope}`, incremented in `rate_limit.py`'s `_enforce()` right where `RateLimitError` is raised — this is the one traffic signal generic HTTP instrumentation won't give you for free (a 429 still shows up in `http_requests_total{status="429"}`, but a scope-labeled counter makes "which limiter is tripping" immediately answerable without cross-referencing logs).
3. No new Docker service, no new container — `prometheus-fastapi-instrumentator` runs inside the existing `api` container, exactly like every other admin-module capability (Decision 9 in the original plan already established this precedent; this follows the same rule).
4. Once (1) is done, `admin/health.py`'s golden-signals panel starts returning real numbers for the first time — re-run `test_admin_system_health.py`'s "Prometheus configured" test case against a real local Prometheus scrape to confirm the panel actually populates, not just that the HTTP call doesn't error.
5. Add `backend/tests/test_admin_traffic_metrics.py` (new): asserts `GET /metrics` response body contains `http_requests_total` after making a handful of requests through the test client, and asserts the rate-limit-rejection counter increments when a scope's limit is deliberately exceeded in a test.

---

## 5. Validation checklist — what your colleague should check, and how

**Prerequisite:** this checklist assumes `feat/admin-module`, `feat/phase2-module4-application-lifecycle`, and `integration/cors-rate-limit` have been merged into `master-complete-foundation`, §4's Module 3/4/CORS/rate-limit/traffic-monitoring additions have been implemented, and the stack is running locally (`docker compose up`, migrations applied). Each row: what to check, how, and what "pass" looks like. A colleague with no prior context on this module should be able to follow this top to bottom.

### 5.1 RBAC
| Check | How | Pass looks like |
|---|---|---|
| Non-admin user gets 401/403 on every `/api/admin/*` route | `curl` each admin GET endpoint with no cookie, then with a regular (non-admin) user's cookie | `401` unauthenticated, `403` authenticated-but-not-admin |
| `is_superuser` still works exactly as before this module existed | Log in as the existing seeded superuser, hit `/api/admin/costs/daily` (the pre-existing endpoint) | Same response shape as before any Admin Module work started — zero regression |
| A `support`-role user can read users/audit logs but cannot assign roles | Assign the seeded `support` role to a test user, hit `GET /api/admin/users` (expect 200) then `PUT /api/admin/users/{id}/role` (expect 403) | Read succeeds, role-assignment is blocked for anyone but `is_superuser` |

### 5.2 Audit log
| Check | How | Pass looks like |
|---|---|---|
| Every admin mutation produces an audit row | Suspend a test user via the UI or API, then `GET /api/admin/audit-logs?action=user.status_changed` | A new row with the right `before`/`after`, actor, timestamp |
| Fallback middleware catches an un-audited mutation | (Engineering-only check) temporarily comment out one `record_admin_action()` call, hit that route, confirm a `captured_by="fallback"` row still appears | A row exists either way — nothing is silently unlogged |

### 5.3 Feature flags
| Check | How | Pass looks like |
|---|---|---|
| Create/toggle a flag, confirm audit entry | `PUT /api/admin/feature-flags/test_flag` with `enabled: true` | Flag shows enabled in `GET /api/admin/feature-flags`; audit log has a `feature_flag.flipped` entry |
| Cache doesn't serve stale data after a flip | Toggle a flag twice quickly, `GET` immediately after each | Second `GET` reflects the second value, not a stale cached first value |

### 5.4 MFA
| Check | How | Pass looks like |
|---|---|---|
| Enroll → confirm → enabled | `POST /api/admin/mfa/enroll`, generate a TOTP code from the returned secret, `POST /api/admin/mfa/confirm` | `GET /api/admin/mfa/status` now shows `mfa_enabled: true` |
| Wrong code rejected | `POST /api/admin/mfa/confirm` with `000000` | `400`, `mfa_enabled` stays `false` |
| Disable works | `POST /api/admin/mfa/disable` | `mfa_enabled` back to `false`, secret cleared |

### 5.5 Impersonation
| Check | How | Pass looks like |
|---|---|---|
| MFA-enabled admin cannot start impersonation without a code | Enable MFA on the admin account, then `POST /api/admin/impersonation/start/{user_id}` with no `mfa_code` | `403` |
| Successful start shows the banner and logs both identities | Start impersonation via the UI, check the persistent top banner shows both admin + target email | Banner visible on every page while impersonating; `impersonation.started` audit row has both `actor_user_id` and correct target |
| End revokes the session | `POST /api/admin/impersonation/end` | Cookie cleared, subsequent requests with the old token fail, `impersonation.ended` audit row exists |
| Cannot impersonate self | `POST /api/admin/impersonation/start/{own_id}` | `400` |

### 5.6 Queue monitor
| Check | How | Pass looks like |
|---|---|---|
| Queue depths match reality | Enqueue a few background jobs (e.g. trigger a CV parse), check `GET /api/admin/queues` before/after | Queued count increases, then drops as workers process |
| Retry actually re-runs a failed job | Force a job to fail (bad input), find it under `GET /api/admin/queues/{name}/failed`, hit the retry endpoint | Job disappears from failed list, reappears as processed (success or a new, different failure) |

### 5.7 System health
| Check | How | Pass looks like |
|---|---|---|
| DB/Redis self-checks reflect reality | Stop Redis temporarily, hit `GET /api/admin/system-health` | `redis_ok: false`, page shows a clear "Redis down" state, page does **not** 500 |
| Golden-signals panel populates (after §4.4 fix) | Set `PROMETHEUS_QUERY_URL`, generate some traffic, hit the system-health page | Latency/traffic/error-rate/saturation show real non-null numbers — **if this still shows blank, §4.4 wasn't actually fixed** |

### 5.8 Analytics
| Check | How | Pass looks like |
|---|---|---|
| Numbers match a manual DB query | `GET /api/admin/analytics/job-matches`, cross-check `total_postings` against `SELECT COUNT(*) FROM job_postings` | Numbers match |
| Cache hit/refresh works | Call twice, then call with `?refresh=1` | Second call shows `cache_hit: true`, refreshed call shows `cache_hit: false` |

### 5.9 Moderation / review queue (all four domains)
| Check | How | Pass looks like |
|---|---|---|
| A flagged job posting appears in the queue | Trigger the flagging path (or manually insert a review-queue row in a test env), `GET /api/admin/review-queue` | Item appears with `resource_type: job_posting` |
| Rejecting hides the posting from candidates | Reject the item, then check the posting no longer appears in candidate-facing job matching | Posting is hidden/excluded post-rejection |
| Same flow works for documents, portfolio, outreach | Repeat for each domain | Each domain's own "hidden" column (`deleted_at`/`admin_hidden`/`admin_blocked`) flips correctly |
| **Outreach block is actually enforced at send time** (§4.2) | Block an outreach message via moderation, then attempt to trigger its send path directly | Send is refused/skipped — **if it still sends, §4.2's gap is not actually closed** |

### 5.10 Module 3 (interview prep) — the newly-wired part
| Check | How | Pass looks like |
|---|---|---|
| No more `501`s | `GET /api/admin/questions`, `GET /api/admin/practice-audio` | Real `200` responses with real data, not `501` |
| RBAC applied | Non-admin hits the same routes | `401`/`403`, same pattern as every other admin route |
| Moderation action works and is audited | Moderate a question or a practice-audio item | Audit log entry appears; underlying content's visibility changes accordingly |

### 5.11 Module 4 (application tracker, interview scheduling, manual job entries) — the newly-built part
| Check | How | Pass looks like |
|---|---|---|
| Applications list matches real data | `GET /api/admin/applications`, cross-check against `application_status`/`applied_at` columns in `users`/`job_matches` | List reflects real application state |
| Interview-schedule list matches real data | `GET /api/admin/interview-schedules` | List reflects real scheduled interviews |
| Manual job entries list + moderate | `GET /api/admin/manual-job-entries`, then moderate one | List shows `is_manual=True` postings; moderation flips the right column and is audited |

### 5.12 CORS
| Check | How | Pass looks like |
|---|---|---|
| Admin frontend origin is allowed | Load the admin UI from the actual configured frontend origin, watch network tab | No CORS errors on any admin API call |
| A non-allowlisted origin is rejected | `curl -H "Origin: https://evil.example.com"` against an admin endpoint | No `Access-Control-Allow-Origin` echoing that origin back |
| `PATCH`/`PUT`/`DELETE` all work from the browser | Trigger a user-suspend (`PATCH`), a role-assignment (`PUT`), and any admin `DELETE` from the actual UI | No CORS preflight failures |

### 5.13 Rate limiting
| Check | How | Pass looks like |
|---|---|---|
| Blanket admin rate limit trips | Script ~150 rapid requests to any admin `GET` endpoint within a minute (above the configured `MAX_ADMIN_REQUESTS_PER_MINUTE`) | `429` responses kick in once the limit is exceeded |
| Impersonation-start has a tighter limit | Attempt to start impersonation 6+ times in a minute | `429` well before the blanket admin limit would trigger |
| Redis outage fails open, not closed | Stop Redis, retry an admin request | Request still succeeds (rate limiting is "protection, not correctness" — see `_enforce()`'s fail-open design) — admin access must not go down just because Redis did |

### 5.14 Traffic monitoring
| Check | How | Pass looks like |
|---|---|---|
| `/metrics` exposes real traffic data | Make a handful of requests, then `curl /metrics` | Response body contains `http_requests_total` and `http_request_duration_seconds_bucket` lines with non-zero counts |
| Rate-limit rejections are counted | Trigger a `429` deliberately, then check `/metrics` | `rate_limit_rejections_total{scope=...}` incremented |

---

## 6. Test plan: unit, integration, smoke, and real-world

### 6.1 Existing test inventory (already on `feat/admin-module` — verified directly, do not rebuild these)

| File | Covers |
|---|---|
| `backend/tests/test_admin_migrations.py` | Schema exists after migration, seed roles/permissions created |
| `backend/tests/test_admin_audit.py` | `record_admin_action()`, fallback middleware |
| `backend/tests/test_admin_pagination.py` | Cursor encode/decode round-trip |
| `backend/tests/test_admin_users_api.py` | User list/suspend/role-assignment API |
| `backend/tests/test_admin_rbac.py` | Permission checks, superuser bypass |
| `backend/tests/test_admin_feature_flags.py` | Feature flag CRUD + audit |
| `backend/tests/test_admin_analytics.py` | Job-match analytics + cache |
| `backend/tests/test_admin_queues.py` | RQ introspection (mocked) |
| `backend/tests/test_admin_system_health.py` | DB/Redis self-checks, Prometheus fail-soft |
| `backend/tests/test_admin_mfa.py` | TOTP enroll/verify/disable |
| `backend/tests/test_admin_impersonation.py` | Start/end, MFA gate, dual-identity audit |
| `backend/tests/test_admin_costs.py` | Pre-existing cost endpoints — regression guard |
| `backend/tests/test_admin_documents_moderation.py` | Document soft-delete moderation |
| `backend/tests/test_admin_job_postings_moderation.py` | Job posting moderation |
| `backend/tests/test_admin_job_swipe_visibility.py` | Moderated postings excluded from candidate-facing swipe/matching |
| `backend/tests/test_admin_moderation_flagging.py` | Automated flagging (keyword/LLM-judge) into the review queue |
| `backend/tests/test_admin_module3_placeholder_routes.py` | **Currently asserts `501`s — must be rewritten once §4.1 lands, not just deleted** |
| `backend/tests/test_admin_outreach_moderation.py` | Outreach message moderation |
| `backend/tests/test_admin_portfolio_moderation.py` | Portfolio moderation |
| `backend/tests/test_admin_review_queue.py` | Generic review-queue list/detail/decide |
| `backend/scripts/smoke_admin_live.py` | **Live HTTP smoke test** against a real running stack — see §6.4 |
| `frontend/e2e/integration/admin.spec.ts` | **Playwright e2e** against a real running stack — see §6.5 |
| `frontend/features/admin/components/*.test.tsx` | One React component test per admin panel |

### 6.2 New unit tests needed (fast, no DB/Redis/HTTP — pure logic)

- `backend/tests/test_admin_rate_limit_scopes.py` (NEW): `enforce_admin_rate_limit`/`enforce_admin_impersonation_rate_limit` call `check_rate_limit` with the right scope string and limit value (mock `check_rate_limit`, assert call args) — mirrors the existing pattern for `enforce_job_matching_scan_rate_limit`.
- Extend `test_admin_rbac.py` with cases for the three new Module 4 permission pairs (`applications:*`, `interview_schedules:*`, `manual_job_entries:*`) — superuser bypass, role-grant, role-deny, same shape as existing cases.

### 6.3 New integration tests needed (real test DB + test client, no live external calls)

- `backend/tests/test_admin_questions_practice_audio.py` (NEW, replaces the `501`-asserting parts of `test_admin_module3_placeholder_routes.py`): real `200` list/read/moderate flows, RBAC-gated, audited — same shape as `test_admin_job_postings_moderation.py`.
- `backend/tests/test_admin_applications.py` (NEW): `GET /api/admin/applications` list + filter by `application_status`, cursor pagination, RBAC.
- `backend/tests/test_admin_interview_schedules.py` (NEW): list + filter, RBAC.
- `backend/tests/test_admin_manual_job_entries.py` (NEW): list `is_manual=True` postings, moderate action flips visibility + audits.
- `backend/tests/test_admin_outreach_send_enforcement.py` (NEW, closes §4.2's gap): seed a message with `admin_blocked=True`, call the actual send/dispatch function directly, assert it raises/skips rather than sending.
- `backend/tests/test_admin_cors_rate_limit.py` (NEW): hits several admin endpoints with `Depends(enforce_admin_rate_limit)` overridden to a tiny limit (e.g. 2/min) in the test, asserts the 3rd request in the same minute gets `429`; separately asserts a `CORSMiddleware`-added `Access-Control-Allow-Origin` header is present for an allowlisted `Origin` and absent for a non-allowlisted one.
- `backend/tests/test_admin_traffic_metrics.py` (NEW, per §4.4): `GET /metrics` after a few requests contains `http_requests_total`; a deliberately-exceeded rate limit increments `rate_limit_rejections_total`.

### 6.4 Smoke test — extend `scripts/smoke_admin_live.py`

This script already exists and already drives login, user list/suspend, feature flags, MFA, impersonation, queues, system health, and a review-queue flag→decide→audit pass over real HTTP against a running stack (Postgres + Redis + API container), printing PASS/FAIL per step. **Extend it, don't replace it**, with new steps in the same `_record(name, passed, detail)` style:
1. `questions_admin_read` / `practice_audio_admin_read` — confirm no more `501`s.
2. `applications_admin_list`, `interview_schedules_admin_list`, `manual_job_entries_admin_list_and_moderate`.
3. `admin_rate_limit_enforced` — fire enough rapid requests to trip the new `admin` scope, confirm a `429` shows up.
4. `metrics_endpoint_has_traffic_data` — `GET /metrics`, confirm `http_requests_total` is present in the body.

Run it locally against the docker-compose stack: `python backend/scripts/smoke_admin_live.py --base-url http://127.0.0.1:8010` (or whatever port `docker-compose.yml` maps `api` to) — every line should print `PASS`; a non-zero exit code means something in this module is broken against a real, live system, not just against mocks.

### 6.5 Real-world / E2E test — extend `frontend/e2e/integration/admin.spec.ts`

This Playwright spec already polls the live backend's `/health`, then walks `/app/admin/system-health`, `/app/admin/analytics`, `/app/admin/audit-logs`, `/app/admin/feature-flags`, and more, checking the real rendered UI against a real running backend (not mocked). **Extend it** with:
1. New test cases for `/app/admin/questions`... (or wherever Module 3's admin pages land) — heading renders, no error state, no more "not implemented" messaging.
2. New test cases for `/app/admin/applications`, `/app/admin/interview-schedules`, `/app/admin/manual-job-entries` — heading renders, table/list populates.
3. A full impersonation click-through: log in as superuser → Users table → "Log in as" → dialog with reason (+ MFA code if enabled) → confirm banner appears → click "Exit impersonation" → banner disappears.
4. A full moderation click-through for at least one domain (e.g. job postings): navigate to the moderation panel, reject an item, confirm it disappears from the queue and the audit log shows the action.

Run it against the real dev stack: `npx playwright test e2e/integration/admin.spec.ts` (backend + frontend both running, per the spec's own `pollBackendHealth()` prerequisite).

### 6.6 Commands to run everything

```bash
# Backend — full admin suite + regression guard
cd backend && pytest tests/test_admin_migrations.py tests/test_admin_audit.py \
  tests/test_admin_pagination.py tests/test_admin_users_api.py tests/test_admin_rbac.py \
  tests/test_admin_feature_flags.py tests/test_admin_analytics.py tests/test_admin_queues.py \
  tests/test_admin_system_health.py tests/test_admin_mfa.py tests/test_admin_impersonation.py \
  tests/test_admin_costs.py tests/test_admin_documents_moderation.py \
  tests/test_admin_job_postings_moderation.py tests/test_admin_job_swipe_visibility.py \
  tests/test_admin_moderation_flagging.py tests/test_admin_outreach_moderation.py \
  tests/test_admin_portfolio_moderation.py tests/test_admin_review_queue.py \
  tests/test_admin_questions_practice_audio.py tests/test_admin_applications.py \
  tests/test_admin_interview_schedules.py tests/test_admin_manual_job_entries.py \
  tests/test_admin_outreach_send_enforcement.py tests/test_admin_cors_rate_limit.py \
  tests/test_admin_traffic_metrics.py tests/test_admin_rate_limit_scopes.py -v

# Backend — full suite regression check (nothing else broke)
cd backend && pytest tests -m "not postgres" -q

# Backend — coverage gate
cd backend && pytest tests -m "not postgres" -q --cov=app --cov-report=term-missing

# Smoke test — live stack required
docker compose -f backend/docker/docker-compose.yml up -d
python backend/scripts/smoke_admin_live.py --base-url http://127.0.0.1:8010

# Frontend — typecheck/lint/build + unit tests
cd frontend && npm run typecheck && npm run lint && npm run build && npm run test:unit -- features/admin

# Frontend — real-world e2e (live stack required)
cd frontend && npx playwright test e2e/integration/admin.spec.ts
```

---

## 7. How to improve the Admin Module further (prioritized)

1. **Fix the traffic-monitoring gap (§4.4)** — highest priority, because the System Health page silently shows nothing useful today even when "fully configured." A colleague testing this without reading this document would incorrectly conclude the feature works (no error, just empty data).
2. **Close the Module 3/4 gaps (§4.1)** — the module is genuinely incomplete without these; Module 3 actively returns `501`s today.
3. **Wire CORS/rate-limit coverage (§4.3)** — right now, a compromised admin token or a buggy frontend polling loop has no throttle on `/api/admin/*` at all.
4. **Verify and close the outreach-send enforcement gap (§4.2)** — a one-line check, but currently unverified.
5. **Merge the three branches into `master-complete-foundation`** — nothing above can be truly "validated end-to-end" until this happens; today it's three separate, unmerged branches.
6. **Longer-term, already-flagged-as-deferred (from the ADR, not new findings):** full RBAC replacing `is_superuser` (deliberately not done), exactly-once audit guarantee (best-effort fallback only, by design), SSO for admin login, real-time (websocket) dashboards instead of polling, force-enabled MFA for all admins, hash-chained tamper-proof audit logs, a self-serve in-app appeals flow for moderation decisions (currently just an email notification). None of these are bugs — they're scoped-out, documented future work.

---

## 8. Final "is it done" checklist

- [ ] §4.1 Module 3 stubs replaced with real implementations; placeholder-`501` tests replaced with real tests
- [ ] §4.1 Module 4 admin routers (`applications`, `interview_schedules`, `manual_job_entries`) built, wired, tested
- [ ] §4.2 Outreach `admin_blocked` enforcement verified (or fixed) at the actual send path
- [ ] §4.3 `admin` rate-limit scope added and applied to the admin router; tighter scope on impersonation-start
- [ ] §4.3 CORS `allow_methods`/`allow_headers` confirmed to cover every verb the admin UI actually uses
- [ ] §4.4 `prometheus-fastapi-instrumentator` (or equivalent) added; `http_requests_total`/`http_request_duration_seconds_bucket` confirmed present in `/metrics`; golden-signals panel confirmed to show real, non-null data
- [ ] §4.4 `rate_limit_rejections_total{scope}` counter added and confirmed incrementing
- [ ] All items in §5's validation checklist pass
- [ ] All new tests in §6.2–6.3 written and passing; existing §6.1 suite still passing (zero regressions)
- [ ] §6.4 smoke script extended and passing against a live stack
- [ ] §6.5 e2e spec extended and passing against a live stack
- [ ] `feat/admin-module`, `feat/phase2-module4-application-lifecycle`, and `integration/cors-rate-limit` merged into `master-complete-foundation`
- [ ] `backend/docs/ARCHITECTURE.md` updated to reflect Module 3/4 admin coverage and traffic-monitoring instrumentation
- [ ] This document's own §7 improvement list reviewed with the team — decide which "longer-term" items (if any) get promoted to actual scope

---

## 9. IMPORTANT — a merge is already happening in the background

While writing this section, we found a branch called `merge/admin-module3-4-cors-ratelimit` that already exists locally, 9 commits ahead of `origin/master-complete-foundation`, not yet pushed. Its commit history (`fix(cors): support multi-origin allowlist...`, `fix(rate-limit): replace fixed-window counter with atomic sliding-window algorithm`, `fix(rate-limit): add tiered limits for documents upload, signals webhook, job-matching scan`, `fix(auth): add rate limiting to register/login/verify/resend-verification`, `docs(admin): add full-stack implementation plan for Admin Module`) shows someone (the user, or another agent session) is actively working through exactly this merge, in real time, outside this document. **As of this check, that branch has merged CORS + rate-limiting work, but Module 3 and Module 4's own code (`questions`, `practice_audio`, `application_tracker`, `interview_scheduling`, `manual_jobs`, `jd_practice`) is not yet merged into it** — those still only exist on `feat/phase2-module4-application-lifecycle` (verified directly). **Before doing any validation work below, check the current state of `merge/admin-module3-4-cors-ratelimit` again — it may have moved further along by the time you read this.**

---

## 10. Module 3 (Interview Prep) — is it actually implemented?

**In simple language: Module 3 is "practice interviews with AI."** A candidate gets asked interview questions (some generic, some personalized to their résumé), answers by typing or recording their voice, and gets AI-generated feedback on their answer.

### 10.1 What's actually built (verified directly against `feat/phase2-module4-application-lifecycle`, which already includes Module 3's code)

- **Question bank + personalized questions** (`backend/app/modules/questions/`) — picks interview questions for a candidate, can generate personalized ones based on their résumé (topic is personalized, the scoring rubric is not — a deliberate safety choice so personalization can't be used to make scoring unfair).
- **Practice audio** (`backend/app/modules/practice_audio/`) — upload a voice recording of a practice answer, it gets transcribed (OpenAI Whisper) and analyzed for basic coaching feedback (pace, filler words, etc.). An optional, paid, **off-by-default** add-on (Hume AI) can add "voice tone" coaching insights — never a hire/no-hire signal, explicitly framed as coaching only.
- **AI feedback generation** (`feedback_generator.py`) — turns a candidate's answer into written feedback, with retry/backoff added so a flaky OpenAI call doesn't just fail outright.
- **JD-aware practice** (`backend/app/modules/jd_practice/`) — practice questions tailored to a specific job description, not just generic ones.
- **Its own background-job lane** — feedback generation and question pre-generation run on their own worker queue, kept separate from other background work so a backlog in one doesn't starve the other.
- **A real, dedicated smoke test already exists:** `backend/scripts/smoke_test_module3.py` (+ a `.sh` wrapper) — talks to a real running server over real HTTP with real cookie-based login and a real Redis-backed worker, not mocks. This is a strong sign Module 3 was seriously tested by whoever built it.
- **A real pytest suite already exists:** `test_question_bank.py`, `test_questions_router.py`, `test_practice_audio_router.py`, `test_practice_audio_model.py`, `test_question_generator_jd.py`, `test_feedback_question_text_lookup.py`.

### 10.2 What to double-check is actually fixed (the plan doc `phase2_module3.md` itself lists these as bugs it set out to fix — verify each one, don't assume it's done just because the plan says so)

<table fit-page-width="true" header-row="true">
<tr><td>Thing to check</td><td>Why it matters</td><td>How to check</td></tr>
<tr><td>`question_id` has a real foreign-key constraint</td><td>The plan's own §4.2 found this missing in two tables — a missing FK means a deleted question could leave orphaned/broken references</td><td>Open a DB client, run `\d question_attempts` (or the Postgres equivalent) and confirm a `FOREIGN KEY` on `question_id` actually exists, not just a plain column</td></tr>
<tr><td>`practice_audio_recordings` has a real ORM model class</td><td>The plan's §4.3 found the table existed in the DB but no Python class represented it — meaning code could silently write to the wrong shape</td><td>Confirm `test_practice_audio_model.py` passes and actually imports a real model class (not just raw SQL)</td></tr>
<tr><td>Feedback worker reads the real question text, not `None`</td><td>The plan's §4.4 found the feedback worker was silently reading `None` for the question text on every single attempt — feedback would then be generated against no question at all</td><td>Run `test_feedback_question_text_lookup.py`; also manually trigger one practice-answer feedback and read the generated feedback text — does it actually reference the specific question asked?</td></tr>
<tr><td>No HTTP route is dead code</td><td>The plan's §4.5 found `question_selector.py`/`question_generator.py`/audio upload were built but nothing in the API actually called them</td><td>Hit each relevant endpoint (`GET` a personalized question, `POST` a practice-audio upload) and confirm a real response, not a 404/dead path</td></tr>
</table>

### 10.3 What's genuinely still missing (not a "maybe," verified absent)

- **No admin visibility into Module 3 at all today.** On the separate `feat/admin-module` branch, the two admin routers for this (`questions_router.py`, `practice_audio_router.py`) exist but return `501 Not Implemented` on every route, on purpose, until wired (see §4.1 above).
- **No rate limiting on any Module 3 endpoint.** Verified: `rate_limit.py` on the module-3/4 code branch only has `sync`, `async`, and `compliance` scopes, applied only to `opt_out`/`dsar`. Every `questions`/`practice_audio`/`jd_practice` route sits behind `current_verified_user` only — nothing stops one user from hammering the personalized-question-generation endpoint (which calls a paid OpenAI API per call) as fast as their browser allows.
- **CORS is wide open, not hardened.** `allow_methods=["*"]`, `allow_headers=["*"]`, single origin from `FRONTEND_URL`. It works, but it's the "before" state, not the tightened multi-origin allowlist described in §4.3.

### 10.4 How to test Module 3 — unit, integration, smoke, live

- **Unit:** the personalization/FK/recency-index logic in `question_selector.py` — pure-logic tests already exist in `test_question_bank.py`; add a case per §10.2 bug if not already covered (recency exclusion actually excludes recently-seen questions, personalization never changes the scoring rubric).
- **Integration:** `test_questions_router.py` / `test_practice_audio_router.py` (real test DB + test client) — already exist; extend with a case for each §10.2 row if missing.
- **Smoke:** `python backend/scripts/smoke_test_module3.py` against a real running stack (`BASE_URL=http://127.0.0.1:8010 ... python scripts/smoke_test_module3.py`) — every PASS/FAIL line should say PASS.
- **Live/real-world:** the smoke script above already **is** the real-world test for Module 3 (real HTTP, real worker, real Whisper/OpenAI calls if keys are configured) — there is no separate Playwright/e2e spec for Module 3 yet; adding one (`frontend/e2e/integration/module3.spec.ts`, mirroring `admin.spec.ts`'s shape) is a reasonable next step, not something that already exists.

---

## 11. Module 4 (Application Lifecycle) — is it actually implemented?

**In simple language: Module 4 is "everything that happens after a candidate finds a job they like."** It tracks whether they applied, lets them schedule and get reminded about interviews, lets them add jobs they found on their own (not from scraping), and helps them write outreach messages to recruiters/companies.

### 11.1 What's actually built (verified directly against `feat/phase2-module4-application-lifecycle`)

<table fit-page-width="true" header-row="true">
<tr><td>Sub-feature (as named in `phase2_module4_application_lifecycle_and_interview_prep.md`)</td><td>What it does, simply</td><td>Where the code lives</td><td>Status</td></tr>
<tr><td>Module A — minimum-10-matches fallback</td><td>If strict matching finds too few jobs, progressively relax the filters so the candidate still sees a reasonable number of matches</td><td>`app/modules/job_matching/repository.py`, `workers/tasks/job_matching.py`</td><td>✅ Built</td></tr>
<tr><td>Module B — Apply button + click tracking</td><td>An "Apply" button on every job card that safely redirects to the real posting and records that the candidate clicked apply</td><td>`app/modules/job_matching/` (apply-redirect endpoint, migration `039`)</td><td>✅ Built</td></tr>
<tr><td>Module C — Application tracking board</td><td>A board showing every job the candidate applied to and its status (applied/replied/interview/offer/rejected)</td><td>`app/modules/application_tracker/`</td><td>✅ Built</td></tr>
<tr><td>Module D — Interview scheduling + calendar + notifications</td><td>Schedule an interview, get a calendar invite (.ics) and email/push reminders</td><td>`app/modules/interview_scheduling/`</td><td>✅ Built</td></tr>
<tr><td>Module E — JD-aware interview practice</td><td>Practice questions generated from the actual job description you're interviewing for, not generic ones</td><td>`app/modules/jd_practice/`</td><td>✅ Built</td></tr>
<tr><td>Module F — Manual job entry</td><td>Add a job you found yourself (not from scraping) so it shows up in your tracker too</td><td>`app/modules/manual_jobs/`</td><td>✅ Built</td></tr>
<tr><td>Module G — Multi-channel outreach messages</td><td>AI-drafted messages to recruiters/companies, with a `message_type` so different message styles get different prompts</td><td>`app/modules/outreach/` (`message_type` column verified present)</td><td>✅ Built</td></tr>
</table>

Every one of these has its own migration, model, repository, service, router, and a pytest file already (`test_application_tracker_repository.py`, `test_application_tracker_router.py`, `test_interview_scheduling_router.py`, `test_manual_jobs_migrations.py`, `test_manual_jobs_router.py`, plus job-matching's existing test files for Modules A/B).

### 11.2 What's genuinely still missing

- **No live smoke test or real-world e2e test exists for any of Module 4** — unlike Module 3 (`smoke_test_module3.py`) and the Admin Module (`smoke_admin_live.py` + `admin.spec.ts`), there is **no equivalent script** covering application tracking, interview scheduling, manual job entries, or the new outreach message types end-to-end against a real running stack. This is the single biggest testing gap in Module 4 today.
- **No admin visibility into Module 4 at all.** Confirmed: the Admin Module (on its own branch) has zero routers touching `application_status`, interview schedules, or manual job entries — see §4.1 above for the plan to add them.
- **No rate limiting on any Module 4 endpoint** — same gap as Module 3, verified the same way (only `sync`/`async`/`compliance` scopes exist, none applied to `application_tracker`/`interview_scheduling`/`manual_jobs`/`jd_practice`/`outreach`).
- **CORS still wide-open, not hardened** — same as Module 3.
- **Migration ordering:** the plan doc's §2 calls out a "Step 0 (blocking) — migration lineage reconciliation" because Module 3 and Module 4 forked their Alembic revisions from the same point. Confirm this renumbering was actually applied by running `alembic upgrade head` cleanly from a fresh database and checking there is exactly one linear history, not two competing heads.

### 11.3 How to test Module 4 — unit, integration, smoke, live

- **Unit:** pure logic like the apply-redirect open-redirect-safety check (Module B) and the manual-entry-to-tracker join logic (Module F) — extend the existing test files with edge cases (e.g. an apply-redirect URL pointing somewhere off-platform must be rejected, not followed).
- **Integration:** the existing router test files already exercise the real test DB + test client path — run them and confirm all pass: `pytest backend/tests/test_application_tracker_repository.py backend/tests/test_application_tracker_router.py backend/tests/test_interview_scheduling_router.py backend/tests/test_manual_jobs_migrations.py backend/tests/test_manual_jobs_router.py -v`.
- **Smoke (needs to be built — doesn't exist yet):** create `backend/scripts/smoke_test_module4.py`, following the exact shape of `smoke_test_module3.py` (real HTTP, real cookie login, real worker) — steps: create an application via apply-redirect, move it through tracker statuses, schedule an interview and confirm the .ics/notification fires, add a manual job entry, generate an outreach message of each `message_type`. Print PASS/FAIL per step, non-zero exit on any failure.
- **Live/real-world (needs to be built — doesn't exist yet):** a Playwright spec (`frontend/e2e/integration/module4.spec.ts`), mirroring `admin.spec.ts`'s shape — click through the actual application tracker board, schedule an interview through the real UI, add a manual job entry through the real UI, generate an outreach message through the real UI, against a real running backend.

---

## 12. Checking Admin Module + CORS + Rate-limit wiring for Module 3 and 4 — simple step-by-step

This is the part the user specifically asked about: **is the Admin Module properly connected to Module 3 and Module 4, and is CORS/rate-limiting properly applied to them?** Here's exactly how to check, in plain steps, and what to do if the answer is "no."

### 12.1 Is the Admin Module wired to Module 3 and 4?

**How to check (takes 2 minutes):**
1. Log in to the app as a superuser/admin.
2. Try to open an admin screen for interview questions, practice audio, applications, interview schedules, or manual job entries (or, if no UI exists yet, `curl` the equivalent API: `GET /api/admin/questions`, `GET /api/admin/applications`, etc.).
3. Look at the response.

**What "properly wired" looks like:** a normal `200 OK` with real data (or a normal `403` if you're not allowed — but the endpoint itself exists and does something).

**What "NOT properly wired" looks like:** a `501 Not Implemented` (Module 3's current state) or a `404 Not Found` because the route doesn't exist at all (Module 4's current state — there is no such route yet).

**If it's not properly wired, what to do:** follow §4.1 above — for Module 3, replace the two `501` stub routers with real implementations and wire them into the admin router aggregator; for Module 4, build the three new admin routers from scratch (applications, interview schedules, manual job entries) the same way every other admin moderation router was built.

### 12.2 Is CORS properly wired to Module 3 and 4?

**How to check (takes 2 minutes):**
1. Open the actual frontend app in a browser, log in, and use any Module 3 (practice) or Module 4 (applications/scheduling/manual jobs/outreach) screen.
2. Open the browser's developer tools → Network tab. Look for any red/failed request, or a console error mentioning "CORS."

**What "properly wired" looks like:** no CORS errors at all; every request succeeds or fails with a normal application error (like a 400), never a browser-blocked CORS error.

**What "NOT properly wired" looks like:** a browser console error like `has been blocked by CORS policy`, or a request that never even reaches the server.

**Current reality on Module 3/4's own branch:** CORS is technically present (so today's basic screens do work) but is the wide-open, single-origin, `allow_methods=["*"]`/`allow_headers=["*"]` version — not broken, but not the hardened multi-origin allowlist from `integration/cors-rate-limit` either. **If you're testing against a build that already merged in `integration/cors-rate-limit`,** re-check specifically that Module 3/4's own verbs (`PATCH` for status updates, `POST` for scheduling/manual entries) aren't accidentally excluded by a newly-tightened `allow_methods` list — that's the one way "hardening" CORS can silently break something that worked before.

**If it's not properly wired, what to do:** find the `CORSMiddleware(...)` call in `backend/app/main.py`, confirm the frontend's real origin(s) are in `allow_origins`, and confirm `allow_methods` includes every verb Module 3/4 actually uses (`GET`, `POST`, `PATCH`, `DELETE`).

### 12.3 Is rate limiting properly wired to Module 3 and 4?

**How to check (takes 5 minutes):**
1. Pick any Module 3 or Module 4 endpoint (e.g. the personalized-question-generation endpoint, or the outreach-message-generation endpoint — both call a paid AI API per request).
2. Script ~50-100 rapid repeated requests to it within a minute (a simple `for` loop with `curl`, or a short Python script with `httpx`).
3. Watch the responses.

**What "properly wired" looks like:** at some point, the responses switch to `429 Too Many Requests`, well before you've made an unreasonable number of calls.

**What "NOT properly wired" looks like:** every single request succeeds, no matter how many you send. **This is the current, verified state of Module 3 and Module 4 today** — there is no rate limit on any of their endpoints.

**If it's not properly wired, what to do:** follow §4.3 above — add rate-limit scopes for the expensive/sensitive Module 3/4 endpoints (question generation, feedback generation, outreach message generation, apply-click tracking) the same way `enforce_job_matching_scan_rate_limit` was added for Module 1's scan endpoint, and apply them with `Depends(...)` on the specific routes that call a paid external API per request — those are the ones worth protecting first, even before a blanket per-module limit.

### 12.4 Quick reference — current wiring status (as of this check)

<table fit-page-width="true" header-row="true">
<tr><td>Module 3/4 endpoint group</td><td>Admin visibility</td><td>Rate limiting</td><td>CORS</td></tr>
<tr><td>Questions / practice audio (Module 3)</td><td>❌ `501` stubs on the admin branch</td><td>❌ None</td><td>🟡 Present, not hardened</td></tr>
<tr><td>Application tracker (Module 4.C)</td><td>❌ No admin route exists</td><td>❌ None</td><td>🟡 Present, not hardened</td></tr>
<tr><td>Interview scheduling (Module 4.D)</td><td>❌ No admin route exists</td><td>❌ None</td><td>🟡 Present, not hardened</td></tr>
<tr><td>JD-aware practice (Module 4.E)</td><td>❌ No admin route exists</td><td>❌ None</td><td>🟡 Present, not hardened</td></tr>
<tr><td>Manual job entries (Module 4.F)</td><td>❌ No admin route exists</td><td>❌ None</td><td>🟡 Present, not hardened</td></tr>
<tr><td>Outreach messages (Module 4.G)</td><td>🟡 Only pre-existing outreach moderation on the Admin branch — does not yet know about `message_type`</td><td>❌ None</td><td>🟡 Present, not hardened</td></tr>
</table>

---

## 13. Module 3/4-specific improvement list and final checklist

### 13.1 How to improve Module 3 and Module 4 further (prioritized)

1. **Build the missing Module 4 smoke script and e2e spec (§11.2/§11.3)** — right now Module 4 has zero end-to-end proof it works against a real running system; Module 3 already has this, Module 4 doesn't.
2. **Add rate limiting to every expensive/sensitive Module 3 and Module 4 endpoint (§12.3)** — question generation, feedback generation, outreach message generation, and apply-click tracking all currently have zero throttle, and at least three of those call a paid third-party API per request.
3. **Wire the Admin Module to Module 3 (fix the stubs) and Module 4 (build new routers) (§4.1, §12.1)** — staff currently have zero visibility into applications, interview schedules, manual job entries, or interview-prep content moderation.
4. **Re-verify every bug `phase2_module3.md` itself called out as fixed (§10.2)** — don't take the plan document's word for it; each one is independently checkable in under a minute.
5. **Confirm the Alembic migration renumbering (§11.2) was actually applied** — a fresh `alembic upgrade head` run is the fastest way to know for sure.
6. **Harden CORS for real (§12.2)** — the current wide-open `allow_methods=["*"]`/`allow_headers=["*"]` works today but is not the target end-state; once `integration/cors-rate-limit`'s hardening lands, re-test every Module 3/4 verb specifically (not just "does the page load").
7. **Give outreach moderation (on the Admin branch) awareness of `message_type` (§12.4)** — today's admin outreach moderation predates Module 4's `message_type` column; the review-queue UI should show which type of message was flagged.

### 13.2 Final checklist — Module 3 and Module 4 are done when every box is checked

- [ ] Every bug listed in `phase2_module3.md` §4 (FK, ORM model, feedback worker, dead routes) independently re-verified fixed, not just assumed from the plan doc (§10.2)
- [ ] `backend/scripts/smoke_test_module4.py` created, covering apply-tracking → application board → interview scheduling → manual job entry → outreach message generation, and passing against a live stack (§11.3)
- [ ] `frontend/e2e/integration/module4.spec.ts` created and passing against a live stack (§11.3)
- [ ] Rate limiting added to question generation, feedback generation, outreach message generation, and apply-click tracking, with a passing test proving a 429 eventually fires (§12.3)
- [ ] Admin Module's `questions_router.py`/`practice_audio_router.py` no longer return 501; real Module 4 admin routers (`applications`, `interview_schedules`, `manual_job_entries`) exist and are wired (§12.1)
- [ ] CORS allowlist confirmed to include every origin and every verb Module 3/4 actually use, checked by hand in a real browser, not just assumed (§12.2)
- [ ] Alembic migration history confirmed linear (one head, not two) after a fresh `alembic upgrade head` (§11.2)
- [ ] Outreach moderation UI/API updated to show `message_type` on flagged items (§12.4)
- [ ] `merge/admin-module3-4-cors-ratelimit` (or whatever branch ends up carrying this work) re-checked one more time immediately before merging to `master-complete-foundation`, since it was actively moving while this document was written (§9)
