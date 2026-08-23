# Machine 2, Track 2 — Country Demand Intelligence

## Goal

Surface country-level job-demand signal (which countries have the most/fastest-growing postings
for a given role) for placement-agency recruiters deciding where to focus candidate sourcing.
Built on top of the country plumbing already shipped in `backend/app/enrichers/jobspy.py`.

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
# Default False — this is a new, additive analytics feature with its own DB write load;
# opt-in until an agency customer actually needs it.
enable_demand_intelligence: bool = Field(default=False, alias="ENABLE_DEMAND_INTELLIGENCE")
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
