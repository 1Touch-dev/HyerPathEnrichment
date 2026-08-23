# Post-Tenancy Retrofit, Chunk 1 — Job Matching + Swipe Tenant Scoping

## Depends on

`machine-1-tenancy-core` fully merged: `Organization` table, `users.org_id` column,
`OrgScopedUser` dependency, `org_id` JWT claim all exist and are in production use.

## Goal

Every query in `job_matching` and `job_swipe` that currently scopes by `user_id` alone must
additionally scope by the querying user's `org_id` **wherever the underlying row is
recruiter/org-owned data** (candidate job preferences, matches, swipe state) — but **not** for
data that is legitimately platform-wide and shared across orgs (`JobPosting` rows themselves are
scraped from public job boards and are not owned by any one org; multiple agencies' recruiters
may match against the same posting). Getting this distinction right is the entire point of this
chunk — over-scoping `JobPosting` would make one org's job-search results miss valid postings
just because a different org's recruiter search first ingested them.

## Files to edit

- `backend/app/modules/job_matching/repository.py`
- `backend/app/modules/job_matching/service.py`
- `backend/app/modules/job_matching/router.py`
- `backend/app/modules/job_swipe/repository.py`
- `backend/app/modules/job_swipe/service.py`
- `backend/app/modules/job_swipe/router.py`
- `backend/alembic/versions/0XX_job_matching_org_scoping.py` (real number TBD at implementation
  time — this wave is sequential and dispatched after `machine-1`, so the head should be stable;
  still re-run `python -m alembic heads` before writing it, since `post-tenancy-retrofit/02` and
  `03` may be implemented in parallel with this chunk and also want a migration)

## What gets an `org_id` filter (owned by a recruiter/org)

- `CandidateJobPreferences` (keyed by `user_id` today) — add `org_id` column, backfill from
  `users.org_id` via the migration's data step, then filter every repository function that takes
  `user_id` to also check `org_id` matches the caller's org **only when the caller has an org**
  (direct candidates with `org_id IS NULL` keep working exactly as today — this retrofit must be
  a no-op for them; see `machine-1`'s ADR Decision §3 on why `NULL` is a real, supported state,
  not a migration debt to clean up).
- `JobMatch` — same treatment: add `org_id`, backfill, filter.
- `PushSubscription` — same treatment.
- `job_swipe`'s own models (read `backend/app/modules/job_swipe/models.py` before assuming exact
  column names, but the same principle applies: anything keyed by `user_id` representing a
  candidate's personal swipe state needs the same `org_id` companion filter).

## What does NOT get an `org_id` filter (shared platform data)

- `JobPosting`, `JobPostingEmbedding` — **no `org_id` column added**. These are the shared,
  deduplicated (`dedup_key`) result of scraping public job boards; every org's recruiters search
  the same pool. Do not add `org_id` here even defensively — it would be actively wrong.
- `ManualJobEntry` (Module F) — **needs `org_id` scoping**, same treatment as `JobMatch`/
  `CandidateJobPreferences`. This is a definitive decision, not a "check this one carefully at
  implementation time" flag: a manually-entered job is created *by* one specific recruiter/
  candidate acting on behalf of one specific org (or no org, for a direct candidate), and no
  *other* org has a legitimate reason to read it — it is not scraped public data like
  `JobPosting`. Read `backend/app/modules/job_matching/models.py`'s `ManualJobEntry` definition
  to confirm its exact current column list before writing the migration, but the scoping decision
  itself does not depend on what's found there.

  **The reusable rule this decision follows** (apply it to any future "does this table need
  `org_id`" question in this doc set, not just this one row): *does exactly one org's action
  create this row, and would a different org ever legitimately need to read it? If yes + no →
  needs `org_id`.* `ManualJobEntry` is yes+no (one recruiter enters it, no other org should ever
  see it) → scoped. Contrast this with `JobPosting`: it is *not* created by any one org's action
  (it's ingested from public job-board scraping, no recruiter "owns" the scrape), and *every* org's
  recruiters legitimately need to read it (shared search pool) — the rule's first half (does one
  org's action create it?) already answers "no," which is exactly why `JobPosting` is correctly
  exempt from `org_id` scoping above, not an inconsistency with `ManualJobEntry`'s treatment.

## Repository retrofit pattern

Every function taking `user_id: UUID` as a filter parameter (e.g. `get_preferences`,
`list_matches_for_user`, `get_owned_match`, `mark_viewed`, `set_feedback`,
`record_apply_click`, `count_unread_matches`, `list_subscriptions_for_user` — read the full
current file, this list from the 2026-08-22 snapshot may not be exhaustive) gets a new optional
parameter `org_id: UUID | None = None` alongside it, and adds `.where(..., <Model>.org_id ==
org_id)` **only when `org_id is not None`** — i.e. the filter degrades to a no-op for
`org_id=None` callers (direct candidates), and becomes a real filter for org-scoped callers.
Do not make `org_id` a required parameter — that would force a breaking signature change on every
call site including ones that legitimately have no org.

Service-layer call sites (`job_matching/service.py`, `job_swipe/service.py`) read the caller's
`org_id` from the authenticated `User` object (now populated by `machine-1`) and pass it through
to every repository call, e.g. `repository.get_preferences(db, user_id, org_id=current_user.org_id)`.

Router-layer call sites stay unchanged in shape (`current_user: CurrentUser` still yields the
full `User` object with `.org_id` on it) — no router file needs a new dependency, just needs to
pass `current_user.org_id` through to the service call it already makes.

## Cross-tenant ownership check — the actual security-relevant change

The single most important correctness property this chunk must guarantee:
**`get_owned_match(db, match_id, user_id)` and equivalent "owned resource" lookups must never
return a row belonging to a different org's recruiter, even if `user_id` is guessed/brute-forced
correctly.** Concretely: if recruiter A (org X) and recruiter B (org Y) are both looking at
matches, a request for `match_id` that happens to belong to org Y must 404 (not just filter out
of a list) when made by a caller from org X — this is exactly what
`post-tenancy-retrofit/04-tenant-isolation-test-suite.md` will test directly against this file's
functions. Add the `org_id` check to the `.where(...)` clause of every single-row "owned lookup"
function, not just the list-returning ones — a common mistake is scoping list endpoints but
leaving single-resource-by-id lookups unscoped.

## Do not touch

- `backend/app/modules/documents/`, `backend/app/modules/portfolio/`,
  `backend/app/modules/outreach/`, `backend/app/modules/admin/` — owned by
  `post-tenancy-retrofit/02` and `03`.
- `backend/app/modules/orgs/`, `backend/app/auth/` — owned by `machine-1` (already merged by the
  time this chunk starts; read-only reference, do not modify).
- `JobPosting`/`JobPostingEmbedding` schema — explicitly no `org_id` column (see above).
- `backend/app/enrichers/`, `backend/app/workers/tasks/` scraping/scoring logic — the *ingestion*
  side (JobSpy/JSearch scraping, embedding generation, match scoring) is unaffected; this chunk
  only retrofits the *read/write access-control* side (repository query filters), not the
  pipeline that produces `JobPosting`/`JobMatch` rows in the first place.

## Verification

- Unit tests per retrofitted repository function: two orgs, two users, assert org A's user
  cannot read/mutate org B's `CandidateJobPreferences`/`JobMatch`/`PushSubscription` rows via any
  retrofitted function, including single-row lookups by id.
- Regression test: a user with `org_id = None` (direct candidate) retains full, unfiltered access
  to their own data exactly as before this chunk — this is the most likely place to introduce an
  accidental regression, since `org_id IS NULL` must mean "skip the filter," not "match nothing."
- Explicitly confirm `JobPosting` search results are identical for two different orgs searching
  the same term/location (no accidental scoping leak in the shared-data path).
