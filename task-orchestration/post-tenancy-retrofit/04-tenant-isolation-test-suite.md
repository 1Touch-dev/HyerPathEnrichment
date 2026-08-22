# Post-Tenancy Retrofit, Chunk 4 — Tenant Isolation Test Suite (HARD GATE)

## ⚠️ This chunk is a release gate, not a normal feature chunk

Per the root `README.md`: **no `post-tenancy-retrofit` branch, and no `post-tenancy-features`
branch, merges to `master-complete-foundation` until this suite passes green against a real
dockerized Postgres instance.** The reviewer subagent for this chunk must refuse to approve the
PR if the suite runs against SQLite instead of Postgres, if any test is skipped/xfail'd instead
of passing, or if it does not cover all three domains retrofitted in chunks `01`-`03`.

## Depends on

`01-job-matching-and-swipe-tenant-scoping.md`, `02-outreach-documents-portfolio-tenant-scoping.md`,
and `03-admin-tenant-scoping.md` must **all** already be merged — this suite tests their
combined behavior, it does not implement any scoping itself.

## Ground truth: this repo already has real-Postgres test infra

`backend/tests/conftest.py` already detects and switches between SQLite and real Postgres based
on `DATABASE_URL`:

```13:19:backend/tests/conftest.py
_USE_REAL_INFRA = "postgresql" in _EXISTING_DB_URL.lower()
...
USING_POSTGRES = _USE_REAL_INFRA
```

with `USING_POSTGRES` already exported specifically so "tests gated on [SQLite-only bugs] pass
for real [on Postgres]" — i.e. this repo already has precedent for tests that must actually run
(not just theoretically support) against Postgres. This chunk's suite **must** run with
`DATABASE_URL` pointing at `postgresql+asyncpg://...` — start the real service via:

```bash
docker compose -f backend/docker/docker-compose.yml up postgres -d
docker compose -f backend/docker/docker-compose.yml run --rm migrate
```

then export `DATABASE_URL=postgresql+asyncpg://hyrepath:${POSTGRES_PASSWORD}@localhost:5433/hyrepath`
(port `5433`, per `docker-compose.yml`'s `postgres` service port mapping — verify this is still
accurate at implementation time) before running pytest. **Do not write a suite that only works
against SQLite** — per the hard-gate rule, this is disqualifying, not a style nit.

## Files to create

- `backend/tests/test_tenant_isolation.py`
- `backend/tests/conftest_tenant_fixtures.py` (or add fixtures directly to
  `backend/tests/conftest.py` if the existing fixture-organization convention favors one shared
  file — check how other cross-cutting fixtures, e.g. `auth_headers`, are organized before
  deciding; do not create a second fixture file if the convention is one shared conftest)

## Fixtures needed

```python
@pytest.fixture
async def two_orgs(db_session):
    """Two distinct Organizations, each with one recruiter User (org_id set) and
    one seeded row per domain (job preferences, outreach message, document,
    portfolio profile) owned by that org's recruiter."""
    org_a = Organization(id=uuid4(), name="Agency A", slug="agency-a")
    org_b = Organization(id=uuid4(), name="Agency B", slug="agency-b")
    db_session.add_all([org_a, org_b])
    await db_session.flush()

    recruiter_a = _make_user(org_id=org_a.id)
    recruiter_b = _make_user(org_id=org_b.id)
    ...
    return TwoOrgFixture(org_a=org_a, org_b=org_b, recruiter_a=recruiter_a, recruiter_b=recruiter_b, ...)


@pytest.fixture
def direct_candidate(db_session):
    """A user with org_id=None — the pre-tenancy, non-agency direct-candidate case.
    Every isolation test that checks org A vs org B must also check this user isn't
    accidentally broken by the retrofit (org_id IS NULL must mean 'unfiltered', not
    'matches nothing')."""
    ...
```

(Exact fixture helper shape — `_make_user`, seeding helpers per domain — is the implementer's to
design, following whatever existing user/fixture-creation helpers already exist in
`backend/tests/conftest.py`; do not duplicate user-creation logic that conftest.py already
provides.)

## Required test coverage (minimum — one class/module section per domain)

### Job matching + swipe (chunk `01`)

- `test_job_match_isolated_by_org` — org A's recruiter cannot list, get-by-id, mark-viewed, or
  set-feedback on org B's `JobMatch` rows.
- `test_candidate_job_preferences_isolated_by_org` — same shape for `CandidateJobPreferences`.
- `test_job_posting_shared_across_orgs` — **inverse** assertion: both orgs' recruiters see the
  *same* `JobPosting` search results for identical query params (proves the shared-data
  exemption from `01`'s file wasn't accidentally over-scoped).
- `test_direct_candidate_unaffected` — a `direct_candidate` (org_id=None) retains full access to
  their own `JobMatch`/`CandidateJobPreferences` rows post-retrofit.

### Outreach, documents, portfolio (chunk `02`)

- `test_outreach_message_isolated_by_org` — including direct `message_id` lookup (the "owned
  lookup" pitfall named in `01`'s file — re-verify it here for outreach specifically), and the
  `send` endpoint (org A cannot send/edit org B's draft).
- `test_candidate_document_and_cv_chat_isolated_by_org`.
- `test_portfolio_management_isolated_by_org` — private/management views.
- `test_portfolio_public_slug_still_public` — **inverse** assertion: a portfolio's public slug
  page is reachable by an unauthenticated request or a different org's recruiter, unfiltered
  (proves `get_profile_by_slug`'s exemption from `02`'s file wasn't accidentally scoped).
- `test_direct_candidate_unaffected` (documents/portfolio/outreach versions).

### Admin (chunk `03`)

- `test_admin_review_queue_isolated_by_org` — org A's `agency_owner` only sees org A's flagged
  items.
- `test_admin_user_management_isolated_by_org` — org A's admin cannot `update_user_status`/
  `assign_role` on an org B user; asserts **404**, not 403 (existence-leak check, per `03`'s
  file).
- `test_superuser_sees_all_orgs_unfiltered` — a superuser (`is_superuser=True`) retrieves data
  across both org A and org B through every retrofitted admin endpoint, unfiltered. This is
  explicitly called out in `03`'s file as the regression most likely to slip through — treat it
  as equally important as the isolation tests themselves, not a lesser afterthought.

### Cross-cutting

- `test_no_query_missing_org_filter` (best-effort, not exhaustive): for each retrofitted
  repository module, assert that calling its "owned lookup" functions with org A's `user_id`/
  `resource_id` combination but org B's `org_id` argument returns `None`/empty, not the row —
  i.e. explicitly exercise the *mismatched* combination, not just "org A's own recruiter can't
  see org B's data through org A's own token" (which is the more common thing to accidentally
  test only via the router/auth layer, potentially masking a raw repository-level gap).

## Do not touch

- Chunks `01`, `02`, `03`'s implementation files — this chunk is test-only. If a test in this
  suite fails, the fix belongs in the relevant chunk's files (possibly requiring that chunk's PR
  to be reopened/amended), not patched around inside this test file.
- Any other existing test file — do not modify existing tests to make this suite pass; if an
  existing test's fixtures need extending (e.g. `conftest.py`'s user-creation helper needs an
  `org_id` parameter), that is an additive, backward-compatible signature change (default
  `org_id=None`), not a rewrite of the existing helper's behavior for existing callers.

## CI wiring

Add (or extend an existing) CI job that runs this suite specifically against real Postgres — not
folded into whatever job already runs the SQLite-based suite. Check `.github/workflows/` for the
existing test workflow structure before adding a new job; follow its existing conventions for
starting Postgres as a service container / via `docker compose` in CI, matching how (if at all)
`test_jsearch_provider.py` or other Postgres-aware tests are already wired into CI (if none are
wired in yet, this chunk is also responsible for adding that CI wiring, not just the test file
itself — the hard-gate rule is meaningless if the suite only runs manually).

## Verification

Running `pytest backend/tests/test_tenant_isolation.py` with `DATABASE_URL` pointed at a real
Postgres instance must produce 100% passing tests, with zero skips/xfails, before this chunk's PR
can be marked ready for the reviewer subagent's approval. Paste the full pytest output (not a
truncated summary) into the PR description as evidence.
