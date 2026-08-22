# Machine 1 — Tenancy Core: Overview

## Goal

Introduce the concept of a **tenant** ("Organization" / "agency") into HyrePath's schema, auth,
CORS, and rate-limiting layers, without breaking the existing single-tenant deployment (direct
candidates using the product today, with no org at all).

This track produces the *capability* to be multi-tenant. It deliberately does **not** touch
`job_matching`, `outreach`, `documents`, `portfolio`, or `admin` business-logic queries — adding
`org_id` filters to those domains' queries is `post-tenancy-retrofit/01-03`'s job, dispatched only
after this track merges. Keeping that split is what lets `post-tenancy-retrofit` be reviewed as a
narrow, mechanical "add a WHERE clause" change instead of being tangled up with "what even is an
org" design work.

## Chunks, in required order

| # | File | Depends on | Produces |
|---|---|---|---|
| 1 | `01-adr-0015-tenancy-model.md` | nothing | ADR document (decision + tradeoffs, no code) |
| 2 | `02-schema-and-migration.md` | ADR decision | `Organization` model, Alembic migration, `users.org_id` column |
| 3 | `03-auth-org-id-claim.md` | `02`'s `users.org_id` column existing | `org_id` in JWT payload, `OrgScopedUser` dependency, org bootstrap on signup |
| 4 | `04-cors-and-ratelimit-retrofit.md` | `02`'s `Organization` table (for custom-domain lookup) and `03`'s `org_id` claim (for rate-limit dimension) | Per-org CORS allow-list, `org_id`-dimensioned rate-limit scopes |

Each chunk's file is written so a developer with zero context on the others could implement it,
given the previous chunk has already landed. Chunk `01` produces no code, only the ADR file
itself — it is chunk `02`'s job to actually create the `Organization` table the ADR describes.

## Naming note (confirmed against current repo, 2026-08-22)

`docs/adr/README.md`'s index currently runs through **ADR 0017** (`0015` is RBAC/audit/MFA,
`0016` is Phase 2 moderation, `0017` is interview-practice personalization) — all *already
merged* to `master-complete-foundation`. The filename `01-adr-0015-tenancy-model.md` in this
planning tree is kept exactly as specified for this planning doc set, but its content instructs
the implementer to create the real ADR file as **`docs/adr/0018-tenancy-model.md`** (next free
number) and to re-check `docs/adr/README.md`'s index immediately before implementing, in case
another ADR has landed in the meantime. See that chunk's "Naming" note for detail.

## Do not touch (applies to all four chunks in this track)

- `backend/app/modules/job_matching/`, `backend/app/modules/outreach/`,
  `backend/app/modules/documents/`, `backend/app/modules/portfolio/`,
  `backend/app/modules/admin/` — no query changes in any of these. `machine-1` only adds the
  `org_id` column to `users` and creates the new `Organization` table; it does not add `org_id`
  to any other table.
- `backend/app/enrichers/`, `backend/app/integrations/`, `backend/app/compliance/`,
  `backend/app/workers/` — untouched by this track.
- Anything under `machine-2-parallel-tracks/` scope (see those files) — no overlap expected, but
  if a conflict is discovered, `machine-1` wins (it is the blocking track).
- Frontend: this track is backend-only. No changes under `frontend/` in any of these four
  chunks (the org-aware login/signup UI, if needed, is out of scope for this planning doc set —
  flag it as a follow-up if the implementer finds the JWT change requires a frontend change to
  keep existing sessions valid; see chunk `03`'s migration-safety notes on this).

## Cross-track coordination

`post-tenancy-retrofit/03-admin-tenant-scoping.md` will later read `users.org_id` and the
`Organization` table this track creates — but it is dispatched only after this track's PR(s) are
merged, so there is no live coordination needed during implementation, only a hard merge-order
dependency (see the root `README.md`'s dependency graph).
