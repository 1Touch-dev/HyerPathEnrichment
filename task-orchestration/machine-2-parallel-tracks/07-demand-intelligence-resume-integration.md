# Machine 2, Track 7 — Demand-Intelligence Resume Integration

## Depends on

`02-country-demand-intelligence.md` (needs `get_top_countries_for_role()` — this chunk's read
path) and `03-outreach-strategy-dimension.md` / the existing outreach-drafting pipeline (needs
the established LLM prompt-construction append-pattern this chunk reuses, specifically
`_STRATEGY_INSTRUCTIONS`'s composition style in `backend/app/workers/tasks/outreach.py`). Both
`02` and `03` must already exist (their files/functions, not necessarily merged to
`master-complete-foundation` — this track can be developed against a local checkout of both, same
as `05`/`06` already do against `03`) before this chunk's code can import from them.

## Goal — explicitly scoped small, not a recommendation engine

Country-level job-demand data (`02`'s `CountryDemandSnapshot`) currently has no consumer outside
its own `/api/demand-intelligence/top-countries` endpoint — it does not feed into anything a
candidate actually sees. This chunk closes that gap with a **small, additive prompt-context
injection** into the existing outreach-drafting LLM call: when a candidate has `desired_roles`
populated on their CV, look up demand data for those roles and inject one short, factual line
into the drafting prompt so the LLM can optionally reference market demand when discussing
relocation/remote flexibility.

**This is explicitly not a new recommendation engine.** A full embedding-based
recommendation/matching system — the kind of architecture LinkedIn's own **JUDE** (their
production job-recommendation embedding pipeline) represents — would be disproportionate
engineering effort at this repo's current scale: one additive context line into an existing
prompt, backed by an aggregate table that already exists (`02`'s `CountryDemandSnapshot`), solves
the actual stated need (surface demand signal to a candidate) without building new embedding
infrastructure, an offline training pipeline, or a new serving layer this repo has no precedent
for. Do not expand this chunk's scope toward that direction — if a genuine "recommend the best
country/role to pursue" feature is wanted later, that is a distinct, much larger effort deserving
its own ADR (per `docs/adr/README.md`'s "storage/layer-ownership" criteria), not an extension of
this chunk.

**Cross-reference: `10-resume-tailoring.md` now closes the "future consumer" promise.**
`02-country-demand-intelligence.md`'s "India/Middle East resume-personalization consumer" section
names `10-resume-tailoring.md` as a future consumer of this same `get_top_countries_for_role` read
path. That promise was dangling (named but not built) until `10`'s own "Demand-intelligence
context injection" section was added, which mirrors this chunk's `_demand_context_line` shape and
contract exactly — same flag-gated, additive, byte-identical-when-disabled design, applied to the
resume-tailoring prompt instead of this chunk's outreach-drafting prompt, under its own sibling
flag `enable_demand_intelligence_in_resume_tailoring`. This chunk's own scope is unchanged by that
addition — it does not import from or depend on `10`, the two chunks' `_demand_context_line*`
helpers are independent, this note exists only so a reader following `02`'s promise through to
its actual resolution lands here rather than at a dead end.

## Ground truth: where `desired_roles` actually lives (verified 2026-08-22)

The task brief that generated this chunk referenced `machine-2-parallel-tracks/01-progressive-
profiling-fields.md`'s file for a `desired_roles`-bearing `CVData`. **`desired_roles` already
exists today**, independent of whether `01` has landed — it is a base field on `CVData`, not one
of `01`'s three new progressive-profiling additions (`interests`, `learning_style`,
`prep_timeline_weeks`):

```44:45:backend/app/domain/candidate.py
    desired_roles: list[str] = Field(default_factory=list)
    desired_locations: list[str] = Field(default_factory=list)
```

This means this chunk has **no dependency on `01` landing first** — `desired_roles` is
unconditionally available on any `CVData` instance, whether or not progressive profiling has
shipped. Re-read `backend/app/domain/candidate.py` before implementing in case this field has
moved or been renamed since 2026-08-22, but do not block this chunk on `01`'s merge status.

## Files to edit

- `backend/app/workers/tasks/outreach.py`
- `backend/app/core/config.py`

## Files to create

- None. This chunk is a pure prompt-context addition to an existing LLM call site; no new table,
  no new migration, no new module.

## `backend/app/core/config.py` — config flag

Following the exact existing bool-flag convention (`enable_tier1`, `outreach_enabled`,
`enable_demand_intelligence` from `02`):

```python
# Demand intelligence -> outreach integration (machine-2/07): inject a short,
# factual country-demand context line into outreach-draft prompts when the
# candidate has desired_roles populated and demand data exists for one of them.
# Default False — additive, low-risk, but off until validated against real drafts;
# also has no effect unless enable_demand_intelligence (02's flag) is also True,
# since there is no snapshot data to inject without it.
enable_demand_intelligence_in_outreach: bool = Field(
    default=False, alias="ENABLE_DEMAND_INTELLIGENCE_IN_OUTREACH"
)
```

## `backend/app/workers/tasks/outreach.py` — wiring

Import the read path from `02`'s service module:

```python
from app.modules.demand_intelligence.service import get_top_countries_for_role
```

In `_draft_with_llm` (the function `03-outreach-strategy-dimension.md` already extends with
`_STRATEGY_INSTRUCTIONS`), add the demand-intelligence line using the **exact same append-pattern
`03` already established** for `_STRATEGY_INSTRUCTIONS` — appended to `user_content` after the
strategy-instruction line and before the `custom_instruction`/`referral_context` appends (so this
chunk's line composes with `03`'s regardless of which strategy is selected, since strategy and
demand-context are orthogonal dimensions, same reasoning `03` used to justify strategy being
orthogonal to `message_type`):

```python
async def _demand_context_line(
    cv_data: CVData, settings: Settings, db: AsyncSession
) -> str | None:
    """One short, factual line about job-market demand for the candidate's first
    desired role with actual snapshot data, or None if the flag is off, no
    desired_roles are set, or no snapshot data exists for any of them. Checks only
    the first desired_roles entry with data (not all of them) to keep the prompt
    addition genuinely short, per this chunk's "small, additive" scope."""
    if not settings.enable_demand_intelligence_in_outreach or not cv_data.desired_roles:
        return None
    for role in cv_data.desired_roles:
        snapshots = await get_top_countries_for_role(db, role, limit=3)
        if snapshots:
            countries = ", ".join(s.country_iso2.upper() for s in snapshots)
            return (
                f"Note: recent job-market data shows the highest current demand for "
                f"{role} is in {countries}; consider this when discussing relocation/"
                f"remote flexibility, if relevant."
            )
    return None
```

Threading `db: AsyncSession` into `_draft_with_llm` is a signature change — `_draft_with_llm` is
currently called from `_generate_outreach_draft_job`, which already holds an open `session`
(`async with SessionLocal() as session:`, per the existing file) — pass that same session through
rather than opening a second one. Append the returned line to `user_content` when not `None`:

```python
    demand_line = await _demand_context_line(cv_data, settings, session)
    if demand_line:
        user_content = f"{user_content}\n{demand_line}"
```

placed after the existing company-context line and `03`'s strategy-instruction append, before the
`custom_instruction`/`referral_context` appends — matching the ordering convention `03` already
established (strategy/context lines before candidate-specific free-text instructions, so a
candidate's own explicit instruction always has the "last word" positionally in the prompt).

**Regression safety requirement:** when `enable_demand_intelligence_in_outreach` is `False` (the
default), `_demand_context_line` must return `None` unconditionally — do not let it perform the
`get_top_countries_for_role` query at all in that branch (the early return in the function above
already guarantees this), so disabled behavior costs zero extra DB round-trips, not just zero
prompt-text bytes.

## Do not touch

- `backend/app/modules/demand_intelligence/` (created by `02`) — read-only import of
  `get_top_countries_for_role`; no changes to that module's models/service/router/schemas.
- `backend/app/modules/outreach/models.py`, `schemas.py`, `service.py` — this chunk only touches
  the worker task file (`workers/tasks/outreach.py`) and config; it does not add a new column, a
  new request field, or a new response field anywhere in the `outreach` module itself. The
  demand-context line is prompt-only — it is never persisted on the `OutreachMessage` row, and a
  recruiter/candidate reviewing a draft afterward sees only the resulting `subject`/`body` text,
  not a separate "demand context was used" flag.
- `_STRATEGY_INSTRUCTIONS`, `_SYSTEM_PROMPTS_BY_TYPE`, and every other existing dict/constant in
  `outreach.py` — read/reference only, not modified. This chunk adds one new async helper
  function and one new call site inside `_draft_with_llm`; it does not restructure any existing
  prompt-construction logic.
- Do not build any embedding, ranking, or "best country to target" scoring logic — see the "Goal"
  section's explicit JUDE-architecture scope cut above.

## Verification

- Test: with the flag on and a candidate whose `desired_roles` includes a role that has
  `CountryDemandSnapshot` data, assert the prompt (`user_content`) sent to the mocked LLM call
  includes the demand-intelligence context line, formatted with the correct top-country codes.
- Test: with the flag on but no `CountryDemandSnapshot` rows matching any of the candidate's
  `desired_roles`, assert the prompt is unaffected (no stray "Note: ..." line, no exception).
- Test: with the flag on but `cv_data.desired_roles` empty, assert the prompt is unaffected.
- **Regression test (required, byte-identical check):** with the flag off (default), assert the
  constructed `user_content` for a given `cv_data`/`company_name`/`role_title`/context/job-
  description/message-type/strategy combination is byte-identical to the `user_content` that
  would have been constructed before this chunk shipped — i.e. this chunk must be a strict no-op
  for every existing caller/test that doesn't explicitly opt in via the new flag.
- Test: assert `_demand_context_line` does not call `get_top_countries_for_role` at all when the
  flag is off (mock/spy on the import and assert zero calls) — enforces the "zero extra DB
  round-trips when disabled" requirement above, not just "zero prompt text."
