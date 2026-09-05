# Machine 1, Chunk 3 — Auth: `org_id` JWT Claim (SUPERSEDED)

## Status: superseded, no longer needed

This chunk is **not implemented**. It is kept as a file, not deleted, because other files in this
planning doc set reference it by name (`00-overview.md`'s chunk table,
`04-cors-and-ratelimit-retrofit.md`'s original "Depends on" section,
`05-org-invite-flow.md`'s original "Depends on" section, and the root `README.md`'s dependency
graph/merge order) — deleting it outright would leave those cross-references dangling for
whichever agent stitches the final `README.md`. If a later cleanup pass removes every reference to
this filename elsewhere in the doc set, this stub can be deleted at that point.

## Why it's superseded

The original plan for this chunk was to add an `org_id` claim to the JWT payload and a
`require_org_member`/`OrgScopedUser` dependency, so requests could be scoped to an isolated
agency tenant. That premise no longer holds: per `docs/adr/0018-tenancy-model.md`, `Brand` is a
presentation-only concept, not a data-isolation boundary, and there is **one shared pool** of
candidates and recruiters. There is no access decision left for a JWT claim to gate:

- No query anywhere is filtered by brand/org, so there is nothing for a claim to scope.
- `users.signup_brand_id` (added in `02-schema-and-migration.md`) and
  `recruiter_candidate_assignments` are both presentation/ownership markers, read by UI and
  reporting code, never by an authorization check — so neither needs a corresponding JWT claim
  either.
- Auth stays exactly as it is today: `create_access_token`'s payload (`sub`, `email`, `jti`,
  `exp`, `iat`) is unchanged, and `backend/app/auth/dependencies.py` gets no new
  `require_org_member`-style dependency.

## What replaced the gap this chunk would have left

- Generic staff (recruiter/intern) onboarding is now `05-org-invite-flow.md`'s job, using plain
  role assignment (existing `Role`/`RolePermission` machinery from
  `machine-2-parallel-tracks/04-rbac-admin-platform.md`) instead of org membership.
- Per-brand-domain CORS resolution (`04-cors-and-ratelimit-retrofit.md`) now looks up
  `Brand.custom_domain` directly at startup — it never needed a JWT claim, since it operates at
  the CORS-preflight layer, not per-authenticated-request.
- Rate limiting stays per-caller only, dimensioned by the same `_client_id()`/`_host_client_id()`
  keys that already exist today — no brand/org dimension was added, so there was never a need
  for a claim to carry one.

## Do not touch

- Do not add any `org_id`/`brand_id`/`tenant_id` claim to `create_access_token`'s payload.
- Do not add a `require_org_member`/`OrgScopedUser`-style dependency to
  `backend/app/auth/dependencies.py`.
- Do not implement anything from this file's original scope — it is intentionally a no-op.
