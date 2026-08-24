# Machine 1 — Tenancy Core: Overview

## Goal

Introduce the concept of a **Brand** into HyrePath's schema and presentation layer, without
introducing any data-isolation boundary. The product is one internal operator with **one shared
pool** of candidates and recruiters — `Brand` is a marketing/storefront concept, nothing more:
which storefront a candidate signed up through, which custom domain/CORS origin a request came
in on, which chatbot config and landing-page tier to render for a given visitor. A `Brand` has a
name, a slug, an optional custom domain, a chatbot config, and landing-page-tier-related config.

`Brand` is explicitly **not** a tenant boundary:

- No query anywhere is ever filtered by brand. There is no `brand_id`/`org_id` WHERE clause on
  `job_matching`, `outreach`, `documents`, `portfolio`, or `admin` tables, and none should ever be
  added — that would silently reintroduce the isolated-tenant model this track deliberately
  rejects.
- No JWT claim scopes data access by brand. Auth stays exactly as it is today (`sub`, `email`,
  `jti`, `exp`, `iat`) — this track adds no new claim.
- Any recruiter can search, view, and act on any candidate in the shared pool, regardless of
  which brand storefront that candidate signed up through. `candidates.signup_brand_id` (added by
  chunk `02`) and `recruiter_candidate_assignments` (also added by chunk `02`) both record
  *presentation*/*ownership* facts for reporting and "my assigned candidates" views — neither is
  ever used as a query filter that restricts what a recruiter can reach.

This track produces the schema (`Brand` table, `candidates.signup_brand_id`,
`recruiter_candidate_assignments`) and the presentation-layer wiring (per-brand-domain CORS,
generic staff onboarding) that the rest of the product needs to render multiple branded
storefronts over one shared backend. It deliberately does **not** touch
`job_matching`/`outreach`/`documents`/`portfolio`/`admin` business-logic queries at all — there is
no follow-up "add a WHERE clause" wave for this track to hand off to, because there is no
isolation boundary for those queries to enforce.

## Chunks, in required order

| # | File | Depends on | Produces |
|---|---|---|---|
| 1 | `01-adr-0015-tenancy-model.md` | nothing | ADR document (decision + tradeoffs, no code) |
| 2 | `02-schema-and-migration.md` | ADR decision | `Brand` model, Alembic migration, `candidates.signup_brand_id` column, `recruiter_candidate_assignments` table |
| 3 | `03-auth-org-id-claim.md` | — | Superseded stub only — no code. Kept as a file (not deleted) because other tracks reference it by name; see that file for why no `org_id`/access-scoping claim is needed. |
| 4 | `05-org-invite-flow.md` | `02`'s `Brand` model (optional storefront association on a staff invite) | Generic `StaffInvite` model, invite-creation/acceptance endpoints for recruiters/interns — no seat enforcement, no org membership |
| 5 | `04-cors-and-ratelimit-retrofit.md` | `02`'s `Brand` table (for custom-domain CORS lookup) | Per-brand-domain CORS allow-list. Rate limiting stays per-caller only — no brand-wide/org-wide ceiling, since brand never gates or dimensions access. |

Each chunk's file is written so a developer with zero context on the others could implement it,
given the previous chunk has already landed. Chunk `01` produces no code, only the ADR file
itself — it is chunk `02`'s job to actually create the `Brand` table the ADR describes.

Chunk `03` no longer sits on the critical path — it is a stub, not a functional dependency of
`04`/`05`. The implementation order that matters is **`01 → 02 → 05 → 04`**.

## Naming note (confirmed against current repo, 2026-08-22)

`docs/adr/README.md`'s index currently runs through **ADR 0017** (`0015` is RBAC/audit/MFA,
`0016` is Phase 2 moderation, `0017` is interview-practice personalization) — all *already
merged* to `master-complete-foundation`. The filename `01-adr-0015-tenancy-model.md` in this
planning tree is kept exactly as specified for this planning doc set, but its content instructs
the implementer to create the real ADR file as **`docs/adr/0018-tenancy-model.md`** (next free
number) and to re-check `docs/adr/README.md`'s index immediately before implementing, in case
another ADR has landed in the meantime. See that chunk's "Naming" note for detail.

## Do not touch (applies to all five chunks in this track)

- `backend/app/modules/job_matching/`, `backend/app/modules/outreach/`,
  `backend/app/modules/documents/`, `backend/app/modules/portfolio/`,
  `backend/app/modules/admin/` — no query changes in any of these, ever. `machine-1` adds the
  `Brand` table and the presentation-only `candidates.signup_brand_id` /
  `recruiter_candidate_assignments` records; it does not add any access-scoping column to any
  table, and no other module's queries change.
- `backend/app/enrichers/`, `backend/app/integrations/`, `backend/app/compliance/`,
  `backend/app/workers/` — untouched by this track.
- Anything under `machine-2-parallel-tracks/` scope (see those files) — no overlap expected, but
  if a conflict is discovered, `machine-1` wins (it is the blocking track).
- Frontend: this track is backend-only. No changes under `frontend/` in any of these five
  chunks.

## Cross-track coordination

There is no downstream "tenant isolation" retrofit wave for this track to hand off to — Brand
never gates data access, so there is nothing for a later wave to scope by brand. Any recruiter,
candidate, job, or outreach query written elsewhere in the codebase is correct as long as it
never adds a brand/org filter; this track's own files are the source of truth for that rule.
