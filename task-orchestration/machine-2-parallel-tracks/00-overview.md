# Machine 2 — Parallel Tracks: Overview

## Goal

Seven independent feature tracks that extend the product **without** touching tenant/`org_id`
scoping. None of these tracks depend on `machine-1-tenancy-core` landing first, and none of them
depend on each other **except** the `03 → 05 → 06` sub-chain (outreach strategy dimension →
CAN-SPAM compliance → LinkedIn send), which is internally sequential because `06` imports the
schema `03` defines and the suppression primitives `05` defines, and `07` (demand-intelligence
resume integration), which has a soft, code-import-only dependency on both `02` and `03` (see
that chunk's own file — no schema/migration dependency, just reuse of `02`'s read function and
`03`'s prompt-append convention).

## Tracks

| # | File | Depends on (within this doc set) | Summary |
|---|---|---|---|
| 1 | `01-progressive-profiling-fields.md` | nothing | Add `interests`, `learning_style`, `prep_timeline_weeks` to CV completeness + chat |
| 2 | `02-country-demand-intelligence.md` | nothing | Country-level job-demand signal using JobSpy's country plumbing |
| 3 | `03-outreach-strategy-dimension.md` | nothing | Add an outreach "strategy" dimension (tone/channel/cadence) to existing outreach drafts |
| 4 | `04-rbac-admin-platform.md` | nothing (extends existing RBAC tables) | Agency-facing admin roles/permissions on top of the existing `roles`/`permissions` schema |
| 5 | `05-outreach-cansPAM-send-compliance.md` | `03` (extends the same `OutreachMessage`/service) | CAN-SPAM-compliant send-path hardening: headers, postal address, suppression |
| 6 | `06-linkedin-outreach-send.md` | `03`, `05` | LinkedIn DM/connection-request send layer + intern task-queue UI (**read the legal risk note at the top of that file before implementing anything**) |
| 7 | `07-demand-intelligence-resume-integration.md` | `02` (read function), `03` (prompt-append convention) | Small, additive prompt-context line surfacing country-demand data in outreach drafts — explicitly not a recommendation engine |

Tracks `01`, `02`, `04` may be dispatched to developer subagents in parallel with each other and
with the `03 → 05 → 06` chain, and in parallel with `machine-1-tenancy-core`. The `03 → 05 → 06`
chain is dispatched as three sequential developer-subagent invocations (or one, doing all three
chunks) since each later chunk imports the previous chunk's schema/service additions. `07` is
best dispatched after `02` and `03` (soft ordering preference, not a hard block — see its own
file's "Depends on" section).

## Why these are parallel-safe with `machine-1`

None of these seven tracks add `org_id` filtering to any query, create the `Organization` model,
or touch `backend/app/auth/`, `backend/app/main.py`, or `backend/app/dependencies/rate_limit.py`.
`04-rbac-admin-platform.md` extends the *existing* `roles`/`permissions` tables (ADR 0015,
already shipped) with agency-specific role rows — it does not require `Organization` or
`users.org_id` to exist to insert a `Role` row. It becomes tenant-*aware* only in
`post-tenancy-retrofit/03-admin-tenant-scoping.md`, dispatched after `machine-1` merges.

## Do not touch (applies across all six tracks unless a specific track's file says otherwise)

- `backend/app/auth/models.py`, `backend/app/auth/router.py`, `backend/app/auth/dependencies.py`
  — owned by `machine-1-tenancy-core`.
- `backend/app/main.py`, `backend/app/dependencies/rate_limit.py` — owned by
  `machine-1-tenancy-core/04-cors-and-ratelimit-retrofit.md`.
- `backend/app/modules/orgs/` (does not exist yet at the time these six tracks are dispatched,
  since they run in parallel with `machine-1` — do not create it; if a track finds it genuinely
  needs an org concept, that is a sign it should not be in `machine-2` and should be flagged back
  to the orchestrator instead of proceeding).
- No changes to `backend/alembic/versions/047_*` or any `machine-1`-owned migration file. Each
  track's own migration must pick its own `down_revision` — see each track's file for the
  specific value to use, and re-verify the actual current head with `python -m alembic heads`
  immediately before writing the migration, since these tracks may be dispatched and merged in
  any order relative to each other.

## Subagent dispatch notes

See the root `README.md`'s "Subagent role assignment" table for the full breakdown. In short:
tracks `01`, `02`, `04` each get their own developer/reviewer/tester subagent trio dispatched in
parallel; the `03 → 05 → 06` chain gets one developer subagent per chunk, dispatched
sequentially, each gated by its own reviewer subagent before the next chunk's developer subagent
starts; `07` gets its own trio, dispatched after `02` and `03` (soft ordering preference).
