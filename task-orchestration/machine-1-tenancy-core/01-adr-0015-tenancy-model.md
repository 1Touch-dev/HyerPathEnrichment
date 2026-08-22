# Machine 1, Chunk 1 — ADR: Tenancy Model

## Scope

Exactly one file to create:

- `docs/adr/0018-tenancy-model.md`

Exactly one file to edit:

- `docs/adr/README.md` — add one row to the Index table.

## Naming — read this before creating the file

The task brief that generated this planning doc set stated "next number is 0015 since 0001-0014
exist." That was true when that research was done, but **as of 2026-08-22 the repo's actual ADR
index already runs through `0017`** (`0015-admin-module-rbac-audit-mfa.md`,
`0016-phase2-moderation-review-queue.md`,
`0017-interview-practice-question-personalization-and-queue-isolation.md` are all merged to
`master-complete-foundation`). **Before creating this file, re-run:**

```bash
ls docs/adr/*.md | sort
```

and confirm `0018` is genuinely the next free number. If another ADR has landed between this
planning doc being written and this chunk being implemented, use whatever the next free number
actually is instead, and rename the file accordingly — do not silently use a taken number.

## File to create: `docs/adr/0018-tenancy-model.md`

Copy the structure of `docs/adr/template.md` exactly (Status/Date header, Context, Decision,
Tradeoffs, Consequences). Content requirements — the actual prose is the implementer's to write,
but it must cover all of the following decisions and cite the same ground-truth facts this
planning doc set was built from:

### Context section must state

- Today, `backend/app/auth/models.py`'s `User` model (line 18) has **no** `tenant_id`/`org_id`/
  `account_id`/`agency_id` column. The only `account_id`-named column in the schema
  (`OAuthAccount.account_id`, line 86) is Google's OAuth provider account id — a false positive,
  not a tenancy concept.
- The product is pivoting from single-tenant (direct candidates) to multi-tenant (placement
  agencies onboarding their own recruiters, each recruiter working their own pool of candidates/
  jobs/outreach, isolated from other agencies).
- This is squarely an "auth" and "layer-ownership" pattern change per
  `docs/adr/README.md`'s "When to add an ADR" criteria — hence this ADR is mandatory, not
  optional.

### Decision section must choose and justify, explicitly

1. **Column-based tenancy over schema-per-tenant or database-per-tenant.** Decision: add a
   nullable-then-required `org_id` column to shared tables (starting with `users`, later
   retrofitted onto `job_matching`, `outreach`, `documents`, `portfolio`, `admin` tables in
   `post-tenancy-retrofit/`), not separate Postgres schemas or separate databases per agency.
   Justify against: (a) current repo already runs a single shared Postgres instance per
   deployment (ADR 0002 — SQLite local, Postgres Docker/prod) with no per-tenant provisioning
   automation, so schema-per-tenant would require net-new infra this repo has no precedent for;
   (b) column-based tenancy is the smallest change that lets `post-tenancy-retrofit` be "add a
   WHERE clause" rather than "rearchitect the connection layer"; (c) tradeoff: every future
   query against a shared table MUST remember its `WHERE org_id = :org_id` filter — this is a
   real, ongoing footgun (mitigated by `post-tenancy-retrofit/04`'s isolation test suite, but the
   ADR must name this tradeoff explicitly, not hide it).
2. **One org per user (no cross-org membership) in v1.** Decision: `users.org_id` is a single
   nullable FK, not a many-to-many `user_organizations` join table. Justify: the placement-
   agency use case (a recruiter works for exactly one agency) doesn't need multi-org membership
   yet, and a join table can be introduced later without a breaking migration (add the join
   table, backfill from the FK, then deprecate the FK column) — cite this as the reversibility
   argument for why simplicity now doesn't box in the future.
3. **`org_id` nullable, not `NOT NULL`, at the schema level.** Decision: existing users (direct
   candidates predating this feature) get `org_id = NULL`, meaning "no org / legacy direct
   user," not backfilled into a synthetic default org. Justify: a synthetic "default org" would
   silently lump all pre-tenancy users into one fake tenant with no real isolation boundary,
   which is worse than explicitly modeling "no org" as a valid state. Application code (the
   `OrgScopedUser` dependency in chunk `03`) must treat `org_id IS NULL` as "not a tenant
   member" — direct-candidate flows keep working unscoped, agency flows require `org_id IS NOT
   NULL`.
4. **`org_id` claim added to the JWT payload, not looked up per-request from the DB.** Justify
   against the existing token shape in `backend/app/auth/router.py`'s `create_access_token()`
   (`sub`, `email`, `jti`, `exp`, `iat`) — adding `org_id` as one more claim costs nothing extra
   per-request (no additional DB round-trip to resolve tenant on every call) and mirrors how the
   existing impersonation feature already added an additive `imp` claim
   (`backend/app/auth/dependencies.py` lines 82-87) without breaking old tokens that lack it.
   Tradeoff to name: if a user's `org_id` changes after a token is issued (e.g. admin moves them
   between orgs), the stale token keeps the old `org_id` until it expires or is refreshed — name
   `ACCESS_TOKEN_EXPIRE_MINUTES`'s existing value (read it from `backend/app/core/config.py` and
   quote it in the ADR) as the bound on how stale that claim can get.
5. **Per-org CORS origins and rate-limit dimension retrofit, not a new proxy/gateway layer.**
   Justify against `backend/docker/docker-compose.yml` having "no reverse proxy container" today
   — introducing one (e.g. Traefik/Nginx for per-tenant routing) is out of scope for this ADR;
   the existing single FastAPI `CORSMiddleware` and Redis-backed `check_rate_limit()` are
   extended in-place (chunk `04`) instead.

### Tradeoffs section must include (at minimum)

- Shared-table + `WHERE org_id` isolation is only as strong as every single query remembering
  the filter — one missed filter is a cross-tenant data leak. This is why
  `post-tenancy-retrofit/04-tenant-isolation-test-suite.md` is a hard merge gate, not a nice-to-
  have.
- Single-org-per-user is simpler now but will need a breaking-free migration path (join table)
  if multi-org membership is ever needed — name this explicitly so a future reader doesn't
  assume it was never considered.
- JWT-embedded `org_id` trades a small staleness window for zero added per-request DB cost.

### Consequences section must link

- `backend/app/auth/models.py` (User model gets `org_id`)
- `backend/app/auth/router.py` (`create_access_token` gets an `org_id` parameter)
- `backend/app/auth/dependencies.py` (new `OrgScopedUser` dependency)
- `backend/app/main.py` (CORS middleware retrofit)
- `backend/app/dependencies/rate_limit.py` (rate-limit scope key retrofit)
- Forward-reference `post-tenancy-retrofit/` as the wave that depends on this decision.

## File to edit: `docs/adr/README.md`

Add exactly one row to the **Index** table (after the existing `0017` row), following the exact
existing row format:

```markdown
| [0018](0018-tenancy-model.md) | Column-based multi-tenancy for the placement-agency platform | Accepted | 2026-08-22 |
```

(Adjust the ADR number/filename/date if step "Naming" above found a different next-free number
at implementation time. Status starts as `Accepted` per this planning doc set's intent — this
is a settled decision for the effort, not a still-open discussion — but the implementer/reviewer
may downgrade it to `Proposed` if genuinely still under debate at implementation time.)

## Verification

Run `python backend/scripts/verify_adrs.py` after both edits — per `docs/adr/README.md`'s own
documented verification step. It checks ADR structure, the Accepted set, cross-links, and PR
template presence. This must pass before this chunk is considered done.

## Do not touch

- No code changes in this chunk — documentation only (the ADR file itself, plus the one README
  index row). Do not create `Organization` model or migration here — that is chunk `02`.
- Do not edit any other row in `docs/adr/README.md`'s Index table.
- Do not touch `.github/pull_request_template.md` in this chunk.
