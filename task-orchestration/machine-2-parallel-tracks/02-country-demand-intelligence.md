# Machine 2, Track 2 — Country Demand Intelligence

## Goal

Surface country-level job-demand signal (which countries have the most/fastest-growing postings
for a given role) for placement-agency recruiters deciding where to focus candidate sourcing.
Built on top of the country plumbing already shipped in `backend/app/enrichers/jobspy.py`.

**Launch-relevant, not deferred.** This chunk was previously treated as a nice-to-have,
post-launch analytics add-on; re-prioritized here as launch-relevant. Sourcing strategy (which
countries recruiters spend time on) and resume personalization (see "India/Middle East
resume-personalization consumer" below) both need country-demand signal from day one, not after
an initial launch without it — there is no meaningful "launch, then add demand data later"
milestone for a placement business whose core value proposition is knowing where the jobs
actually are.

## Ground truth (verified 2026-08-22 — note this corrects the original research)

The original research for this effort described a 40+-country mapping table as living in "open
unmerged PR #243." **PR #243 ("JobSpy to JSearch migration: config-gated RapidAPI job-source
provider") has since merged to `master-complete-foundation`** (merge commit `c2c61838`,
2026-08-22). The mapping table is real, shipped code today, not a future dependency:

```12:14:backend/app/enrichers/jobspy.py
JOBSPY_SITES = ("linkedin", "indeed", "glassdoor", "google", "zip_recruiter")
```

```45:86:backend/app/enrichers/jobspy.py
_COUNTRY_NAME_TO_ISO2: dict[str, str] = {
    "usa": "us",
    "united states": "us",
    ...
    "south africa": "za",
}
```

with the resolver function:

```89:107:backend/app/enrichers/jobspy.py
def _country_to_iso2(country: str | None) -> str:
    """Best-effort mapping of a free-text country name to an ISO alpha-2 code for JSearch.

    Falls back to "us" (JSearch's own documented default) for unrecognized input rather
    than forwarding an unusable value that would silently zero out the search.
    """
    ...
```

`request.job_country` (a free-text field on `EnrichmentRequest`) flows through
`_country_to_iso2()` when the JSearch provider path is active (config-gated —
check `backend/app/core/config.py` for the exact flag name added by PR #243, likely something
like `job_source_mode`/`JOB_SOURCE_MODE`, and re-verify its exact name/values before wiring
against it) and through the older `kwargs["country_indeed"] = country.lower()` path
(line ~187-188) when JobSpy's own Indeed/Glassdoor scraping is used instead.

**Before implementing, re-read `backend/app/enrichers/jobspy.py` in full** — this table and
function may have grown since 2026-08-22 (e.g. more countries added), and the exact config flag
gating JobSpy vs. JSearch must be confirmed from `backend/app/core/config.py` directly rather
than assumed from this note.

## Tiered market-research methodology

Recruiter sourcing effort should not be spread evenly across every country this system can
resolve — some markets are worth deep, ongoing attention; others are worth periodic monitoring
for a handful of easy wins. This chunk's `CountryDemandSnapshot` data (see below) is the input to
a three-tier classification recruiters use to decide where to focus:

- **Tier 1 — high-volume, high-competition.** USA, Europe (UK, Germany, Netherlands, and other
  major EU markets), Canada. The largest absolute posting counts for most role buckets, but also
  the most candidate-side and recruiter-side competition. Recruiters treat these as the primary,
  always-on sourcing markets — highest posting volume justifies the highest ongoing attention,
  even though competition depresses the "easy win" rate per candidate placed.
- **Tier 2 — mid-volume, lower-competition.** Markets with meaningfully lower `posting_count`
  than Tier 1 for the same role bucket, but also visibly less recruiter/candidate saturation
  (fewer competing postings per opening, less inbound competition for the same roles) — e.g.
  Australia, Ireland, and other English-primary or high-English-proficiency markets outside the
  Tier 1 set. Worth regular but secondary attention: good return on effort, just at lower absolute
  volume than Tier 1.
- **Tier 3 — low-competition, low-volume ("low-hanging fruit").** Markets with low absolute
  posting counts but disproportionately low competition for those postings — roles that go
  unfilled longer simply because fewer recruiters are looking there. Lower total opportunity per
  market, but a comparatively easy placement once a genuine opening is found. Recruiters treat
  Tier 3 as an opportunistic supplement to Tier 1/2 effort, not a primary sourcing target — worth
  periodic sweeps, not sustained daily attention.

Concretely, this tiering is a **derived view over `get_top_countries_for_role`'s existing output**,
not a new persisted classification: add a third service function,
`async def classify_country_tier(snapshot: CountryDemandSnapshot, all_snapshots_for_role: list[CountryDemandSnapshot]) -> Literal["tier_1", "tier_2", "tier_3"]:`,
that buckets a given country's `posting_count` (and, if available, a simple competition proxy —
e.g. `posting_count` relative to the role bucket's total across all countries, since this chunk
has no separate "competition" signal of its own) relative to the full set of snapshots for that
role query. A simple, documented heuristic (e.g. top-third by `posting_count` → `tier_1`,
middle-third → `tier_2`, bottom-third → `tier_3`, with the fixed Tier-1 country list above always
classified `tier_1` regardless of that particular role's own numbers, since USA/Europe/Canada's
Tier-1 status reflects overall market maturity, not just one role bucket's snapshot) is sufficient
for this chunk's scope — do not build a more sophisticated competition model than the data
actually supports. Surface the tier alongside each row in `TopCountriesResponse` (add a `tier`
field) so the frontend table/panel below can group or badge rows by tier without a second API
call.

## India/Middle East resume-personalization consumer

Country-demand data is not only a recruiter-facing sourcing signal — it also feeds
**resume-tailoring for candidates targeting India and the Middle East**, where demand
characteristics (which skills/keywords are in-demand, which role titles map to which country's
job-market norms) differ meaningfully from the Tier 1 US/Europe/Canada baseline most existing
resume content implicitly assumes. Concretely: a future resume-tailoring chunk (ephemeral,
on-demand, per-company tailoring — tracked as its own chunk in this doc set, not built here) is a
**consumer**, not a producer, of this chunk's `CountryDemandSnapshot` data and this chunk's
`country_to_iso2` normalization — when a candidate's target company/role resolves to an
India/Middle East country code, that consumer looks up this chunk's demand snapshot for the same
`(country_iso2, role_bucket)` pair to inform which skills/keywords get emphasized in the tailored
resume, the same read path (`get_top_countries_for_role`) `07-demand-intelligence-resume-
integration.md` already establishes for outreach-draft prompts. This chunk's own scope is
unchanged by this — it does not build the resume-tailoring consumer itself, it only needs to
ensure India/Middle East country resolution is correct and complete (see the India/Middle East
verification item below) so that future consumer has accurate data to read.

## Files to create

- `backend/app/modules/demand_intelligence/__init__.py`
- `backend/app/modules/demand_intelligence/models.py`
- `backend/app/modules/demand_intelligence/schemas.py`
- `backend/app/modules/demand_intelligence/repository.py`
- `backend/app/modules/demand_intelligence/service.py`
- `backend/app/modules/demand_intelligence/router.py`
- `backend/alembic/versions/047_country_demand_intelligence.py`

(This chunk's migration also uses revision number `047` — if `machine-1-tenancy-core/02` has
already claimed `047_create_organizations_and_user_org_id` by the time this chunk is
implemented, use the next free number instead and set `down_revision` to whichever migration is
actually the current head; **re-run `python -m alembic heads` from `backend/` immediately before
writing this migration** rather than assuming which number is free — these two tracks are
dispatched in parallel and may land in either order.)

## Files to edit

- `backend/app/enrichers/jobspy.py` — export the existing `_country_to_iso2` helper (rename to
  drop the leading underscore, e.g. `country_to_iso2`, or add a thin public wrapper) so
  `demand_intelligence` can reuse the exact same normalization instead of re-implementing it.
  This is the **only** change allowed in this file for this chunk — do not touch any other
  function in `jobspy.py`.
- `backend/app/enrichers/merge.py` — **only if** job-posting persistence needs a
  `country_iso2` value written onto `JobPosting` at ingestion time (see schema below); otherwise
  leave untouched. Check how `merge.py` currently constructs/upserts `JobPosting` rows before
  deciding where the normalization call belongs.

## `backend/app/modules/job_matching/models.py` — one additive column

`JobPosting` (`backend/app/modules/job_matching/models.py` lines 23-58) has no country column
today, only free-text `location: str | None`. Add:

```python
    # Country demand intelligence: derived at ingestion via app.enrichers.jobspy.country_to_iso2()
    # (or JSearch's own returned country field, if already ISO-2). NULL for postings scraped
    # before this column existed or where country could not be determined.
    country_iso2: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
```

Include this column addition in this chunk's migration file (same file as the new
`demand_intelligence` tables, or a preceding migration in the same PR — implementer's choice, but
document which in the PR description).

## `backend/app/modules/demand_intelligence/models.py`

```python
"""ORM models for country-level job-demand aggregates."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class CountryDemandSnapshot(Base):
    """One day's aggregate posting count for a (country, normalized_role) pair.

    Populated by a periodic worker job (see service.py), not computed on-demand per
    request — recomputing a full country x role aggregate on every API call would be
    an expensive full-table scan of job_postings on every dashboard load.
    """

    __tablename__ = "country_demand_snapshots"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    country_iso2: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    # Lowercased, whitespace-trimmed role title bucket, e.g. "software engineer" —
    # not a foreign key to any existing "role" table (none exists); free-text bucket
    # matching how JobPosting.title itself is free text.
    role_bucket: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    posting_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    remote_posting_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
```

Add a unique constraint on `(snapshot_date, country_iso2, role_bucket)` in the migration (via
`op.create_unique_constraint`) so a re-run of the aggregation job for the same day upserts rather
than duplicates.

## `backend/app/modules/demand_intelligence/service.py`

Two responsibilities:

1. `async def compute_daily_snapshot(db: AsyncSession, target_date: date | None = None) -> int:`
   — aggregate `job_postings` (`is_active = True`) grouped by `country_iso2` and a normalized
   `role_bucket` (derive `role_bucket` from `JobPosting.title` via simple lowercasing/trimming —
   do not build an NLP title-normalization system for this chunk; a naive bucket is acceptable
   and documented as such in the docstring). Upsert one `CountryDemandSnapshot` row per
   `(country_iso2, role_bucket)` pair for `target_date` (default today). Returns the number of
   rows written, for the calling worker job's logging.
2. `async def get_top_countries_for_role(db: AsyncSession, role_query: str, limit: int = 10) -> list[CountryDemandSnapshot]:`
   — read path for the router: most recent `snapshot_date`, `role_bucket` matching (case-
   insensitive substring on `role_query`), ordered by `posting_count` descending.

Wire `compute_daily_snapshot` into the existing cleanup/periodic-worker pattern
(`backend/app/workers/cleanup_worker.py` — read that file to see how it already schedules a
recurring job via `CLEANUP_INTERVAL_SECONDS`, and either add a second scheduled call in that same
worker loop or create a small new scheduled entry point following the identical pattern; do not
introduce a new scheduling library/mechanism (e.g. APScheduler, Celery beat) — this repo's
existing convention is a plain `while True: ... ; await asyncio.sleep(interval)` loop, per
`cleanup_worker.py`).

## `backend/app/modules/demand_intelligence/router.py`

```python
router = APIRouter(prefix="/api/demand-intelligence", tags=["demand-intelligence"])

@router.get("/top-countries", response_model=TopCountriesResponse)
async def get_top_countries(
    role: str,
    limit: int = 10,
    user: VerifiedUser,
    db: AsyncSession = Depends(get_db_session),
) -> TopCountriesResponse: ...
```

Register this router in `backend/app/main.py` following the exact existing pattern used for
every other module router (find the block of `app.include_router(...)` calls and add one more,
matching the existing style — do not reorder or restructure the existing include-router block).

## Config flag

Add to `backend/app/core/config.py`, following the existing bool-flag convention:

```python
# Demand intelligence: enable the daily country/role posting-count aggregation job.
# Default True — launch-relevant: recruiter market-research prioritization (see the
# tiered Tier 1/2/3 methodology below) and resume-tailoring's country-specific
# personalization both depend on this data being live at launch, not bolted on later.
enable_demand_intelligence: bool = Field(default=True, alias="ENABLE_DEMAND_INTELLIGENCE")
```

Gate `compute_daily_snapshot`'s scheduled invocation on this flag (mirrors `enable_tier1`'s
gating pattern in `backend/app/integrations/multilogin/profile_pool.py` and elsewhere — check
`no-op when disabled` docstring conventions used for other flags and match them).

## Do not touch

- `backend/app/enrichers/jobspy.py` — only the public-rename/export change described above.
- `backend/app/modules/job_matching/service.py`, `repository.py`, `scorer.py`, `explainer.py`,
  `push.py`, `events.py` — untouched; this chunk reads `job_postings` for aggregation, it does
  not change job-matching scoring or push-notification behavior.
- `backend/app/modules/orgs/` — does not exist yet at the time this track is dispatched (parallel
  to `machine-1`); country-demand snapshots are **not** org-scoped in this chunk (they aggregate
  platform-wide postings, which are not tenant-specific data — a country's job-market demand
  isn't owned by any one agency). If a future need for org-specific demand views arises, that is
  a follow-up, not part of this chunk.

## Verification

- Unit test `compute_daily_snapshot` against a small seeded set of `JobPosting` rows with known
  `country_iso2`/`title` values; assert exact aggregate counts.
- Unit test `_country_to_iso2`/`country_to_iso2` is unchanged in behavior after the rename/export
  (existing tests for `jobspy.py`'s country handling, if any — check
  `backend/tests/test_jsearch_provider.py`, added by PR #243 — must still pass unmodified).
- Integration test hitting `/api/demand-intelligence/top-countries` end-to-end against a seeded
  DB.
- **India/Middle East resolution coverage (verified against `backend/app/enrichers/jobspy.py`'s
  current `_COUNTRY_NAME_TO_ISO2` table, 2026-08-22):** add a unit test asserting
  `country_to_iso2()`/`_country_to_iso2()` correctly resolves `"India"` → `"in"` and
  `"UAE"`/`"United Arab Emirates"` → `"ae"` — both already present in today's mapping table, so
  this is a regression-lock test, not new mapping work. **Also add `"Saudi Arabia"` → `"sa"` and
  2-3 other Middle East country names (e.g. `"Qatar"` → `"qa"`, `"Israel"` → `"il"`, `"Egypt"` →
  `"eg"`) to `_COUNTRY_NAME_TO_ISO2` itself** — these are genuinely missing from the table as of
  the 2026-08-22 snapshot (only `"united arab emirates"`/`"uae"` exist among Middle East entries
  today), so this is real mapping work, not only a test. Unrecognized-input entries still fall
  back to `"us"` per the function's existing documented behavior — do not change that fallback.
  This coverage is a hard requirement for this chunk's own launch-relevance claim above and for
  the India/Middle East resume-personalization consumer described above — neither can produce
  correct output if India/Middle East countries silently fall back to `"us"`.
- Unit test `classify_country_tier`: assert USA/a major-Europe country/Canada always classify
  `tier_1` regardless of the role query's own snapshot numbers; assert the top/middle/bottom-third
  heuristic buckets a synthetic set of snapshots into `tier_1`/`tier_2`/`tier_3` as expected.
- **JSearch `language` parameter check (integration-level, not just unit):** the JSearch call site
  (`_scrape_jsearch`, `backend/app/enrichers/jobspy.py` lines ~280-285) currently builds `params`
  with `query`, `num_pages`, `country`, and `date_posted` — **no `language` parameter at all**,
  meaning every request implicitly defaults to JSearch's English-language behavior regardless of
  which country is targeted. Add an integration-level test/assertion that the JSearch call site
  passes a correct, non-empty `language` parameter for non-English-primary markets (e.g. India,
  UAE, Saudi Arabia) rather than leaving it blank/defaulted to English. **Cite the specific risk
  this closes:** JSearch's own documentation warns that omitting or mis-setting `language` for a
  non-English market causes silently fewer-or-zero results, not an HTTP error — a materially more
  dangerous failure mode than an exception, because it looks like "this country just has no job
  postings" (a plausible, easy-to-believe false negative) rather than "something is broken."
  Implementing the actual per-country `language` parameter (mapping `country_iso2` to a sensible
  default language code, e.g. `"in"` → `"en"` since India's JSearch-indexed postings are
  predominantly English-language despite the country not being English-primary generally — verify
  this assumption against JSearch's own documented supported-language list before hardcoding any
  mapping) is in scope for this chunk's fix, not deferred to a follow-up, since the missing
  parameter is a real, currently-shipped-with gap in the exact file this chunk already edits.

## Frontend

A simple admin/recruiter-facing page, following the existing `admin/{feature}/page.tsx`
convention (verified against the real current tree — `frontend/app/app/admin/` today has
`outreach/`, `roles/`, `documents/`, `portfolio/`, `job-postings/`, `users/`, `review-queue/`,
`audit-logs/`, `analytics/`, `feature-flags/`, `queues/`, `system-health/` — all sibling
`page.tsx` files under a shared `frontend/app/app/admin/layout.tsx`, the exact same convention
`machine-2-parallel-tracks/06-linkedin-outreach-send.md` already cites for its own new
`admin/linkedin-tasks/page.tsx`):

- **New file:** `frontend/app/app/admin/demand-intelligence/page.tsx` — sits under the existing
  shared `frontend/app/app/admin/layout.tsx`, not a parallel layout.
- **New file:** `frontend/features/demand-intelligence/components/DemandIntelligencePanel.tsx` —
  following the componentization pattern already established by
  `frontend/features/admin/components/DocumentsModerationPanel.tsx` (a feature-scoped component
  imported into a thin page file, rather than inlining the table/chart markup directly into
  `page.tsx`).
- Calls the existing `GET /api/demand-intelligence/top-countries` endpoint (this chunk's own
  router, above) with a role-search input and renders the results as a table (country, posting
  count, remote posting count, avg salary range, tier badge — `tier_1`/`tier_2`/`tier_3` per the
  tiered market-research methodology above) — a simple table is sufficient for this chunk's
  minimum scope; a chart or tier-grouped sections are an acceptable enhancement but not required.
- New file: `frontend/features/demand-intelligence/hooks/useDemandIntelligence.ts` — a
  `useQuery`-based hook following the exact pattern of
  `frontend/features/outreach/hooks/useOutreach.ts`'s `useOutreachMessages` (React Query, a
  query-key factory module, no manual `useEffect`/`fetch` boilerplate in the component itself).
- Gating: this page's data has no candidate PII on it (aggregate country/role counts only), so it
  does not need a new permission — reuse whatever gate already protects other admin pages in this
  same directory (check `layout.tsx`'s existing auth/permission check and follow it, rather than
  adding a bespoke check for this one page).
