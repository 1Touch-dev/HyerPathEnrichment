# Phase 2, Module 4 — Job Application Lifecycle, Outreach, and JD-Aware Interview Prep

**Status:** Draft implementation plan (not yet built). Read-only investigation completed against `master-complete-foundation` and `origin/feat/phase2-module3-interview-prep`. No code changed by this document.

**Scope:** 100% of backend (models, migrations, services, routers, workers, config), 100% of frontend (pages, components, hooks, API clients, types), and 100% of the Docker/infra changes needed to ship Modules A–G below, in dependency order, on top of `phase2-module3-interview-prep`.

**Out of scope for this document:** actually writing the code. This is the plan an implementer (human or agent) should be able to execute chunk-by-chunk without needing to re-derive any of the design decisions below.

---

## 0. How to read this document

- **Label legend** (carried over from the research that grounded this plan):
  - **[Direct]** — an external source explicitly states this.
  - **[Indirect]** — a source supports the general principle, not this exact case.
  - **[NotFound]** — no external source; grounded in direct codebase reads or engineering judgment, stated as such.
- Every new backend file is shown with its **full intended contents outline** (function/class signatures, not full bodies) so an implementer isn't guessing at shape. Full bodies are only written out where the logic is non-obvious (e.g., the fallback-relaxation query, the open-redirect guard).
- Every new frontend file is shown with its props/hook signatures and the BFF route it talks to.
- All new tables/columns are shown as complete Alembic migration bodies (these **are** written in full, since getting the SQLite/Postgres dual-dialect batch pattern right is exactly the kind of thing that's expensive to get wrong twice).
- File paths are relative to the repo root (`g:\ThunderMarketingCorp\HyerEnrichment`).

---

## 1. Corrections carried over from the investigation (do not re-litigate these)

1. **`phase2-module3-interview-prep` does not do JD-aware interviewing today.** It ships `backend/app/modules/questions/` (question bank + on-demand personalized generation, keyed by `job_role`/`category`/`difficulty`, personalized only via the candidate's résumé) and `backend/app/modules/practice_audio/` (upload → R2 → Whisper transcription → heuristic analysis). Confirmed by reading `questions/service.py`, `questions/schemas.py`, `services/question_generator.py`, and `practice_audio/service.py` directly off `origin/feat/phase2-module3-interview-prep`. There is no code path that takes a job description and a résumé and produces JD-tailored questions. **Module E below builds this as new work**, extending the existing `CandidateContext` personalization pattern rather than replacing it.
2. **Migration lineage collision is real and confirmed.** `master-complete-foundation`'s current single head is `032_portfolio_item_image_url`. `phase2-module3-interview-prep` independently created `033_question_attempt_fk_and_personalization.py` (`down_revision = "032_portfolio_item_image_url"`) → `034_question_recency_index.py` → `035_practice_audio_recordings_voice_tone.py`, confirmed by reading all three files directly off that branch. If both branches land as-is with their current revision IDs, Alembic will see two different migrations both claiming `down_revision = 032`, i.e. two heads. **Step 0 below is the mandatory first commit of this entire plan.**

---

## 2. Step 0 (blocking) — Migration lineage reconciliation

### 2.1 Why renumbering, not a merge migration

Alembic has two standard fixes for divergent heads:

1. **Merge migration** — keep both original revision IDs, add a new migration whose `down_revision` is a tuple of both heads (`("032_portfolio_item_image_url", "033_question_attempt_fk_and_personalization")` — but this only applies if *both* `033`s already exist as committed, deployed history in a shared environment. That is not the case here: `phase2-module3-interview-prep`'s `033`–`035` have not been merged to any shared trunk yet.
2. **Renumber** — since nothing outside `phase2-module3-interview-prep`'s own branch has ever run these three migrations against a real database, it is safe and strictly simpler to renumber them to slot in after `032` with no fork at all. This produces a clean linear chain and avoids a permanent no-op "merge" migration cluttering the history forever.

**Decision: renumber.** If, by the time this lands, `033`–`035` have already been applied to a shared staging/production database under their original names, switch to the merge-migration strategy instead (Alembic supports downgrading+re-upgrading under new names, but that is destructive to any data those migrations wrote — check `alembic_version` in every shared environment before running Step 0).

### 2.2 Exact renumbering

| Old file | Old revision id | New file | New revision id | New `down_revision` |
|---|---|---|---|---|
| `033_question_attempt_fk_and_personalization.py` | `033_question_attempt_fk_and_personalization` | `036_question_attempt_fk_and_personalization.py` | `036_question_attempt_fk_and_personalization` | `032_portfolio_item_image_url` |
| `034_question_recency_index.py` | `034_question_recency_index` | `037_question_recency_index.py` | `037_question_recency_index` | `036_question_attempt_fk_and_personalization` |
| `035_practice_audio_recordings_voice_tone.py` | `035_practice_audio_recordings_voice_tone` | `038_practice_audio_recordings_voice_tone.py` | `038_practice_audio_recordings_voice_tone` | `037_question_recency_index` |

Every new migration this plan adds for Modules A–G (§4 onward) is numbered `039` and up, chained after `038`. This keeps one single linear head throughout.

### 2.3 Mechanical steps

1. `git mv backend/alembic/versions/033_question_attempt_fk_and_personalization.py backend/alembic/versions/036_question_attempt_fk_and_personalization.py` (repeat for `034`→`037`, `035`→`038`).
2. In each renamed file, edit the module docstring's `Revision ID:` comment, the `revision: str = "..."` literal, and the `down_revision: str | Sequence[str] | None = "..."` literal to the new IDs from the table above. No other line changes — the migration bodies (the actual `op.*` calls) are unaffected by renumbering.
3. Search the rest of the branch for any other reference to the old IDs (there should be none outside the three files themselves and this history, but check `git grep -n "033_question_attempt_fk_and_personalization\|034_question_recency_index\|035_practice_audio_recordings_voice_tone"` after the rename to confirm zero remaining hits).
4. Run `alembic heads` (from `backend/`) after rebasing/merging — must print exactly one head. Run `alembic history` and eyeball the chain `... 032 → 036 → 037 → 038 → 039 → ...` is linear with no branch points.
5. Add a one-line regression test alongside the existing `backend/tests/test_alembic_migrations.py` (already present on `phase2-module3-interview-prep`, confirmed via the branch diff) asserting `len(alembic_script.get_heads()) == 1` — this is cheap insurance against this exact class of bug recurring as more branches land in parallel.

### 2.4 Sequencing relative to everything else

Step 0 must be its own commit/PR, merged into the base branch (`phase2-module3-interview-prep`, per your instruction to build everything on top of it) **before** any of Modules A–G add their own migrations, since every module below assumes a single head to chain onto (`039`, `040`, ... in module order — see §4's consolidated table for the exact assignment).

---

## 3. Cross-cutting backend conventions (recap — every module below follows these exactly)

These are not new inventions; they are the patterns already used by `job_matching/`, `job_swipe/`, `outreach/`, and `questions/`/`practice_audio/` today, restated here so each module section below can just say "follows convention" instead of re-deriving it.

- **Layering** (`RULE.md`): `router.py` is thin (auth dep, parse, call service, return) → `service.py` holds business logic, calls `repository.py` for DB access and `clients/`/`services/` for external calls → `repository.py` is the only place that touches the ORM session for cross-cutting reads. Workers (`app/workers/tasks/*.py`) import `repository.py` directly, never `service.py` (per the existing `job_matching/repository.py` docstring: *"Workers import this, never service.py"*).
- **Route registration**: every router uses `route_class=EnvelopeAPIRoute` so every response is wrapped in the standard `{ "data": ..., "meta": ... }` / `{ "error": ... }` envelope (confirms with `frontend/src/lib/api-envelope.ts` on the frontend side, which every BFF route already unwraps via `handleBackendJson`).
- **Auth deps**: `CurrentUser` (any authenticated user) or `VerifiedUser` (email-verified) from `app.auth.dependencies`, injected as a typed parameter, never manually decoded in a router.
- **Cross-module reads**: modules read each other's ORM models directly for simple joins (e.g., `job_swipe/repository.py` reads `job_matching`'s `JobMatch`/`JobPosting` "read-only, never redefined"; `workers/tasks/outreach.py` reads `JobMatch`/`JobPosting` the same way). New modules below (C, D, F, G) do the same — they read `job_matching.models.JobMatch`/`JobPosting` read-only and never duplicate those tables.
- **JSON columns**: `app.database.base.JsonDoc` (JSONB on Postgres, JSON on SQLite) for any `dict`/`list` column, exactly as `JobPosting.sources_seen`, `JobMatch.score_breakdown`, `OutreachMessage.company_context_used` already do.
- **Migrations**: every `ALTER TABLE ... ADD COLUMN` or new FK/index goes through `op.batch_alter_table(...)` (required for SQLite compatibility, already the pattern in `036`/`037`/`038` after Step 0's renumbering, and in `033`'s original body). Every new UUID column that needs cross-dialect typing uses the `postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)` pattern already used in the renamed `036_question_attempt_fk_and_personalization.py`.
- **Settings**: every new config value is a new `Field(default=..., alias="ENV_VAR_NAME")` on `app.core.config.Settings`, never read from `os.environ` directly anywhere else in the codebase.
- **Queues**: every new background job gets a `QUEUE_<NAME>` constant in `app.workers.queue`, a priority slot in `QUEUE_PRIORITIES`, and an `enqueue_<name>(...)` wrapper function there — never a bare `Queue(...).enqueue(...)` call scattered in a service file (the one exception already in the codebase is `outreach/service.py`, which enqueues directly with an inline `Queue(QUEUE_OUTREACH, ...)` — new modules below follow the more consistent `queue.py`-wrapper pattern used by `enqueue_job_matching_scan`/`enqueue_feedback`/`enqueue_question_generation` instead).
- **Metrics**: every module gets its own `app/observability/<module>_metrics.py` following the exact `Counter`/`Histogram` + no-op-fallback-if-`prometheus_client`-missing pattern in `job_matching_metrics.py`.
- **Frontend feature folders**: `frontend/features/<feature>/{api/{client.ts,keys.ts},hooks/*.ts,components/*.tsx,index.ts}`, consumed by a page under `frontend/app/app/<route>/page.tsx` (+ a `*View.tsx` client component, mirroring `MatchesView.tsx`).
- **Frontend BFF routes**: every backend endpoint gets a matching Next.js route handler under `frontend/app/api/<path>/route.ts` that calls `backendFetch(...)` and either passes the envelope through or maps it via a new `mapBackend...ToFrontend`/`adapt...` function added to `frontend/src/lib/api-adapter.ts`, following the exact snake_case→camelCase boundary-mapping convention already used for every existing feature there (see `mapBackendJobMatchItem`, `adaptSwipeDeck`, `adaptOutreachMessage`).
- **Types**: every new response shape gets a hand-written type in `frontend/src/lib/types.ts` (the file already documents that real OpenAPI-generated types don't exist yet for `job_swipe`/`outreach`/`portfolio`, so these are consciously hand-maintained placeholders, same as `RawSwipeDeckResponse` etc. in `api-adapter.ts` today).

---

## 4. Consolidated settings additions (`backend/app/core/config.py`)

All of these are added to the existing `Settings` class in one PR (Step 0 companion, or its own tiny first PR) so every module below can assume they exist without re-touching `config.py` seven times. Grouped by module, in the exact `Field(default=..., alias=...)` style already used throughout the file.

```python
# Module A — job matching fallback relaxation
job_matching_min_results: int = Field(default=10, alias="JOB_MATCHING_MIN_RESULTS")

# Module B — apply-click tracking / redirect
apply_redirect_base_url: str = Field(default="", alias="APPLY_REDIRECT_BASE_URL")
# empty => derive from app_public_base_url; see Module B §5.3

# Module C — application tracker (no new settings; reuses existing pagination/limit conventions)

# Module D — interview scheduling, calendar, notifications
interview_reminder_hours_before: int = Field(default=24, alias="INTERVIEW_REMINDER_HOURS_BEFORE")
interview_ics_organizer_email: str = Field(
    default="", alias="INTERVIEW_ICS_ORGANIZER_EMAIL"
)  # falls back to sendgrid_from_email if empty

# Module E — JD-aware interview practice
jd_question_generation_daily_limit_per_user: int = Field(
    default=10, alias="JD_QUESTION_GENERATION_DAILY_LIMIT_PER_USER"
)  # separate budget from question_generation_daily_limit_per_user (Module 3) since
   # JD-tailored generation always bypasses the shared bank (§9.3) and is therefore
   # more expensive per request; kept as an independent knob rather than reusing
   # question_generation_daily_limit_per_user so ops can tune them independently.

# Module F — manual job entry (no new settings)

# Module G — multi-channel outreach messages
outreach_linkedin_inmail_body_max_chars: int = Field(
    default=1900, alias="OUTREACH_LINKEDIN_INMAIL_BODY_MAX_CHARS"
)
outreach_linkedin_inmail_subject_max_chars: int = Field(
    default=200, alias="OUTREACH_LINKEDIN_INMAIL_SUBJECT_MAX_CHARS"
)
outreach_linkedin_connection_note_max_chars: int = Field(
    default=300, alias="OUTREACH_LINKEDIN_CONNECTION_NOTE_MAX_CHARS"
)
```

All defaults above are chosen so every feature is **on** by default in dev (matching the repo's existing "defaults = fully free / self-hosted, safe to run with nothing configured" philosophy) except where a feature has zero safe default (e.g., there is no safe default `INTERVIEW_ICS_ORGANIZER_EMAIL` if left blank other than falling back to `sendgrid_from_email`, which is itself blank by default — this is documented per-module below, not silently assumed).

---

## 5. Module A — Minimum 10 matches per scan (progressive relaxation fallback)

### 5.1 Problem (confirmed by direct read)

`find_similar_postings` (`backend/app/modules/job_matching/repository.py:292-412`) applies `similarity >= similarity_threshold` as a hard filter in both the pgvector SQL path and the SQLite Python fallback path, with **no fallback** — if only 2 postings clear `JOB_MATCHING_SIMILARITY_THRESHOLD` (default `0.5`), only 2 ever come back, forever, for that candidate.

### 5.2 Design

Progressive relaxation, staged:

1. Try the strict query exactly as today: `similarity >= threshold`, `LIMIT max_postings_per_scan`.
2. If the strict result count `< JOB_MATCHING_MIN_RESULTS` (new setting, default `10`, §4), re-run the **same** query shape but with the threshold filter removed, ordered by `similarity DESC`, `LIMIT JOB_MATCHING_MIN_RESULTS`.
3. Merge: keep every strict-pass result (already above threshold — never dropped), then top up with the highest-similarity results from the relaxed pass that weren't already included, until either `JOB_MATCHING_MIN_RESULTS` is reached or the relaxed pool is exhausted. Never truncate the strict-pass set to make room for relaxed-pass results — a candidate with 15 genuinely good matches should see 15, not be capped at 10.
4. Every result gets a new `passed_threshold: bool` flag (in-memory only at the repository layer, not persisted) so the caller (`workers/tasks/job_matching.py::_scan_jobs_for_candidate_async`) can score/label relaxed-pass matches differently downstream (§5.4).

### 5.3 `backend/app/modules/job_matching/repository.py` changes

`find_similar_postings` signature changes from returning `list[tuple[UUID, float]]` to `list[tuple[UUID, float, bool]]` (adds `passed_threshold`). Every existing caller (just `workers/tasks/job_matching.py`) is updated in the same PR — this is not a public HTTP-facing signature, so no versioning concern.

```python
async def find_similar_postings(
    db: AsyncSession,
    query_embedding: list[float],
    limit: int = 20,
    similarity_threshold: float = 0.5,
    posting_ids: list[UUID] | None = None,
    min_results: int | None = None,
) -> list[tuple[UUID, float, bool]]:
    """Return (job_posting_id, similarity_score, passed_threshold) triples.

    Stage 1: strict threshold-filtered query (unchanged behavior/SQL from today).
    Stage 2 (only runs if stage 1 returned fewer than `min_results`): the same
    query shape with the WHERE similarity >= threshold clause dropped, ordered
    by similarity DESC, LIMIT min_results. Stage-2-only rows are flagged
    passed_threshold=False so callers can rank/label them as lower-confidence
    without silently presenting a 0.1-similarity job as an equally strong match
    (Module A design note re: candidate trust).

    min_results defaults to settings.job_matching_min_results (10) when None —
    accepting it as a parameter (rather than reading get_settings() inside this
    function unconditionally) keeps this function testable with an explicit
    value, matching every other threshold/limit parameter here already being
    caller-supplied rather than read from settings internally.
    """
    settings = get_settings()
    effective_min_results = min_results if min_results is not None else settings.job_matching_min_results

    strict_results = await _find_similar_postings_pass(
        db, query_embedding, limit, similarity_threshold, posting_ids, apply_threshold=True
    )
    strict_triples = [(pid, sim, True) for pid, sim in strict_results]

    if len(strict_triples) >= effective_min_results:
        return strict_triples

    logger.info(
        "Job-matching similarity fallback fired: strict pass returned fewer than "
        "min_results, relaxing threshold",
        extra={
            "strict_count": len(strict_triples),
            "min_results": effective_min_results,
            "threshold": similarity_threshold,
        },
    )
    job_matching_similarity_fallback_fired_total.inc()

    relaxed_results = await _find_similar_postings_pass(
        db, query_embedding, effective_min_results, 0.0, posting_ids, apply_threshold=False
    )
    strict_ids = {pid for pid, _ in strict_results}
    relaxed_triples = [(pid, sim, False) for pid, sim in relaxed_results if pid not in strict_ids]

    return strict_triples + relaxed_triples[: max(0, effective_min_results - len(strict_triples))]
```

- `_find_similar_postings_pass(...)` is today's `find_similar_postings` body, extracted verbatim into a private helper with an added `apply_threshold: bool` switch that either includes or omits the `AND similarity >= :similarity_threshold` clause in the pgvector `text()` query (and the equivalent `if similarity >= similarity_threshold:` guard in the SQLite Python fallback loop). This is a mechanical extraction — the pgvector SQL, the SQLite fallback, and the existing error handling/logging inside today's function are preserved exactly, just parameterized on whether the threshold clause is applied.
- New Prometheus counter `job_matching_similarity_fallback_fired_total` in `app/observability/job_matching_metrics.py` (plain `Counter`, no labels needed — this is a rare/diagnostic signal, not a per-request-labeled one), incremented exactly once per scan where the fallback fires. This directly satisfies the "log intent and path for analytics, so the threshold itself can be tuned later" design goal from the fallback-search-logic reference material.

### 5.4 `backend/app/workers/tasks/job_matching.py` changes

In `_scan_jobs_for_candidate_async`, the loop over `similar_postings` becomes a loop over the new triples, and `compute_overall_score` gets a new optional signal:

```python
for matched_posting_id, similarity_score, passed_threshold in similar_postings:
    posting = await job_matching_repository.get_posting_by_id(db, matched_posting_id)
    if posting is None:
        continue  # posting deactivated/deleted between the similarity query and here — skip, not an error
    posting_dict = posting_to_scoring_dict(posting)  # existing helper, unchanged
    rule_score, breakdown = compute_rule_score(posting_dict, preferences_dict)
    overall_score = compute_overall_score(similarity_score, rule_score)
    if not passed_threshold:
        breakdown["below_similarity_threshold"] = True  # surfaces in score_breakdown JSON, no schema change needed
    await repository.upsert_match(
        db, user_id=candidate.user_id, job_posting_id=matched_posting_id,
        similarity_score=similarity_score, rule_score=rule_score,
        overall_score=overall_score, score_breakdown=breakdown,
    )
```

`score_breakdown` is already a `JsonDoc` free-form dict (`JobMatch.score_breakdown`), so this needs **zero migration** — the flag rides inside the existing column. `JobMatchResponse.score_breakdown: dict[str, float]` (schemas.py) has to widen to `dict[str, float | bool]` to type this correctly; this is a backend-only Pydantic type change, no frontend break since JSON serializes bools fine and the frontend's `scoreBreakdown: Record<string, number>` type (`src/lib/types.ts`) should widen to `Record<string, number | boolean>` in the same PR for correctness (cosmetic, not blocking — TypeScript's structural typing means this is a low-risk, non-urgent follow-up if deferred).

### 5.5 Frontend changes (small, cosmetic-but-important trust signal)

Per the design note in the original research ("must be careful that fallback results are still visually/semantically distinguishable... so candidates aren't misled"):

- `frontend/features/job-matching/components/MatchCard.tsx`: read `match.scoreBreakdown.below_similarity_threshold` (new optional field); if `true`, render a small muted `Badge` reading **"Broader match"** next to the score badge instead of the normal green/yellow/gray score-color badge, so a low-similarity fallback result is never visually indistinguishable from a strong match.
- `frontend/features/job-swipe/components/SwipeCard.tsx`: same treatment — `SwipeableMatchResponse`/`SwipeCard` type doesn't currently expose `score_breakdown` at all (confirmed: `job_swipe/schemas.py`'s `SwipeableMatchResponse` intentionally omits it, per the existing comment in `api-adapter.ts`). Module A adds a single new boolean field `below_similarity_threshold: bool` directly to `SwipeableMatchResponse` (not the whole breakdown dict) to keep that schema's minimalism intact while still surfacing this one signal.
- `frontend/src/lib/types.ts`: `SwipeCard` interface gets `belowSimilarityThreshold: boolean`; `JobMatch` interface's `scoreBreakdown: Record<string, number>` widens to `Record<string, number | boolean>`.
- `frontend/src/lib/api-adapter.ts`: `adaptSwipeDeck`'s per-card mapping adds `belowSimilarityThreshold: c.below_similarity_threshold`.

### 5.6 Tests

- `backend/tests/test_job_matching_repository.py` (new, or extend existing coverage if a repository-level test file already exists — check `test_job_matching_worker.py` first): strict-pass-plenty case unchanged (asserts fallback never fires when ≥10 strict results exist); strict-pass-fewer-than-10 case exercises the fallback and asserts (a) all strict results are present untouched, (b) relaxed results fill up to exactly `min_results` total, (c) relaxed results are flagged `passed_threshold=False`, (d) the Prometheus counter increments exactly once.
- `backend/tests/test_job_matching_worker.py`: extend to assert `score_breakdown["below_similarity_threshold"]` is set correctly end-to-end through `_scan_jobs_for_candidate_async`.
- `frontend/features/job-matching/components/MatchCard.test.tsx`: new case rendering a match with `scoreBreakdown.below_similarity_threshold: true` and asserting the "Broader match" badge appears instead of the score-color badge.
- `frontend/features/job-swipe/components/SwipeCard.test.tsx`: equivalent case for `belowSimilarityThreshold`.

### 5.7 Docker / infra impact

None beyond the settings addition already listed in §4 — `JOB_MATCHING_MIN_RESULTS` needs to be threaded into `backend/docker/docker-compose.yml`'s `worker` service environment block (alongside the existing `JOB_MATCHING_SIMILARITY_THRESHOLD`-adjacent job-matching env vars — note: today's `docker-compose.yml` doesn't actually pass `JOB_MATCHING_SIMILARITY_THRESHOLD` either, since it currently has a safe code default and no compose-level override; follow that same pattern — add `JOB_MATCHING_MIN_RESULTS: ${JOB_MATCHING_MIN_RESULTS:-10}` to the `worker` service block only if ops wants a non-default value in a given environment; it is **not required** to add it at all, since the `Settings` field default already covers the common case). No new services, no new Dockerfiles, no new queues.

**Effort:** Small–medium. **Risk:** Low.

---

## 6. Module B — Apply button on every card, click tracking, mark-applied

### 6.1 Design

Two independent signals, per the LinkedIn-grounded research: a **click** (server-recorded, low-friction, happens on every "Apply" press) and a **mark-applied** (explicit candidate confirmation, the only thing that actually advances Module C's tracker). A click is never treated as a completed application.

### 6.2 Migration `039_job_match_apply_tracking.py`

`down_revision = "038_practice_audio_recordings_voice_tone"` (first migration after Step 0's renumbered chain).

```python
"""Add apply_clicked_at and applied_at to job_matches (Module 4, Module B).

Revision ID: 039_job_match_apply_tracking
Revises: 038_practice_audio_recordings_voice_tone
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "039_job_match_apply_tracking"
down_revision: str | Sequence[str] | None = "038_practice_audio_recordings_voice_tone"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("job_matches") as batch_op:
        batch_op.add_column(sa.Column("apply_clicked_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("job_matches") as batch_op:
        batch_op.drop_column("applied_at")
        batch_op.drop_column("apply_clicked_at")
```

### 6.3 `backend/app/modules/job_matching/models.py` changes

`JobMatch` gains:

```python
apply_clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

### 6.4 `backend/app/modules/job_matching/repository.py` additions

```python
async def record_apply_click(db: AsyncSession, match_id: UUID) -> JobMatch | None:
    """Idempotent: only sets apply_clicked_at the first time (never overwrites a later
    click with an earlier one via repeated calls — CURRENT_TIMESTAMP semantics aren't
    needed here since we want the FIRST click time for funnel analysis, not the latest).
    """
    result = await db.execute(select(JobMatch).where(JobMatch.id == match_id))
    match = result.scalar_one_or_none()
    if match is None:
        return None
    if match.apply_clicked_at is None:
        match.apply_clicked_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(match)
    return match


async def set_applied(db: AsyncSession, match_id: UUID, user_id: UUID, applied: bool) -> bool:
    """Toggle applied_at on/off (unmarking is allowed — candidates make mistakes)."""
    result = await db.execute(
        update(JobMatch)
        .where(JobMatch.id == match_id, JobMatch.user_id == user_id)
        .values(applied_at=datetime.now(UTC) if applied else None)
    )
    await db.commit()
    return bool(result.rowcount > 0)  # type: ignore[attr-defined]
```

### 6.5 Open-redirect-safe apply endpoint

This is the one piece of this module with a real security requirement, so it's spelled out in full. New router file section (added to the existing `backend/app/modules/job_matching/router.py`, since this is Module 1's own `job_matches` table and stays in that module rather than spawning a new one — consistent with how `job_swipe` nests under Module 1's `/api/matches` prefix instead of introducing a parallel resource):

```python
from starlette.responses import RedirectResponse

@router.get("/matches/{match_id}/apply-redirect")
async def apply_redirect(
    match_id: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db_session)
) -> RedirectResponse:
    """Records the click server-side, then 302s to the posting's own source_url.

    Open-redirect guard (hard requirement): the ONLY URL ever redirected to is
    `source_url` already stored on the JobPosting row joined through this exact
    match_id + current_user.id pair — there is no query parameter or request body
    input that influences the redirect target. A match_id belonging to a different
    user 404s (never leaks another candidate's saved posting), and a posting with
    no source_url (should not normally happen — JobSpy/JSearch rows always populate
    it, but defensive) 404s rather than redirecting to a blank/relative URL.
    """
    service = JobMatchingService(db)
    target_url = await service.record_apply_click_and_get_redirect_url(match_id, current_user.id)
    return RedirectResponse(url=target_url, status_code=status.HTTP_302_FOUND)


@router.post("/matches/{match_id}/mark-applied", status_code=status.HTTP_204_NO_CONTENT)
async def mark_applied(
    match_id: str,
    payload: MarkAppliedRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    service = JobMatchingService(db)
    await service.set_applied(match_id, current_user.id, payload.applied)
```

`JobMatchingService.record_apply_click_and_get_redirect_url` (new method in `service.py`):

```python
async def record_apply_click_and_get_redirect_url(self, match_id: str, user_id: UUID) -> str:
    owned = await repository.get_owned_match(self.db, UUID(match_id), user_id)
    if owned is None:
        raise NotFoundError("Match not found")
    match, posting = owned
    if posting is None or not posting.source_url:
        raise NotFoundError("This posting has no external application link")
    _validate_redirect_scheme(posting.source_url)
    await repository.record_apply_click(self.db, match.id)
    job_matching_apply_clicks_total.inc()
    return posting.source_url


def _validate_redirect_scheme(url: str) -> None:
    """Security edge case: source_url is scraped from third-party job boards
    (JobSpy/JSearch) — this codebase does not control or sanitize that upstream
    data. A malformed or malicious scrape (e.g. `javascript:...`, `data:...`, or
    a bare relative path) must never reach RedirectResponse, since a browser
    following a non-http(s) "redirect" from an authenticated same-origin request
    is a real, if narrow, injection surface. Only `http`/`https` schemes are
    allowed through; anything else 404s exactly like a missing source_url would,
    so a malformed row fails closed rather than exposing scheme-specific behavior
    to a client probing for it.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise NotFoundError("This posting has no external application link")
```

`repository.get_owned_match(db, match_id, user_id) -> tuple[JobMatch, JobPosting | None] | None` is a **new** single-row, filtered `SELECT ... WHERE id = :match_id AND user_id = :user_id` function added here in Module B (not an O(n) list-and-filter over `list_matches_for_user(limit=1000)`, which would silently truncate at 1000 rows and do a full table scan for what should be a single indexed lookup). Outer-joined against `JobPosting` from day one for the same Module-F forward-compat reason given in §7 — `posting` is `None` for a manual entry, hence the `posting is None or not posting.source_url` check above (a manual entry never has an external apply link to redirect to). **Module C (§7) and Module E (§9) both reuse this exact function** rather than reintroducing it — see §7.4's `repository.py` and §9.4's `service.py`, both of which import it from `job_matching.repository` instead of duplicating the query.

`MarkAppliedRequest` schema addition to `job_matching/schemas.py`:

```python
class MarkAppliedRequest(BaseModel):
    applied: bool
```

New metric in `job_matching_metrics.py`: `job_matching_apply_clicks_total = Counter("job_matching_apply_clicks_total", "Total Apply-button clicks recorded")`.

### 6.6 `JobMatchResponse` / `SwipeableMatchResponse` schema changes

- `JobMatchResponse` (`job_matching/schemas.py`) gains `apply_clicked_at: datetime | None` and `applied_at: datetime | None`. `source_url` already exists on this schema (confirmed — line 56 of `job_matching/schemas.py`), so no change needed there for the list view.
- `SwipeableMatchResponse` (`job_swipe/schemas.py`) is **missing `source_url` today** (confirmed by direct read — the swipe deck currently has no way to link out to the actual posting at all, a pre-existing gap this module also fixes since it's required for the Apply button to work in the swipe view). Add `source_url: str | None` and `applied_at: datetime | None` to `SwipeableMatchResponse`. `job_swipe/service.py`'s `get_deck` mapping (wherever it builds `SwipeableMatchResponse` instances from `JobMatch`/`JobPosting` pairs) adds `source_url=posting.source_url, applied_at=match.applied_at`.

### 6.7 Frontend

- **`frontend/src/lib/types.ts`**: `JobMatch` gains `applyClickedAt: string | null`, `appliedAt: string | null`. `SwipeCard` gains `sourceUrl: string | null`, `appliedAt: string | null`.
- **`frontend/src/lib/api-adapter.ts`**: `mapBackendJobMatchItem` adds the two new fields. `adaptSwipeDeck`'s card mapping adds `sourceUrl: c.source_url, appliedAt: c.applied_at`.
- **New BFF routes**:
  - `frontend/app/api/matches/[matchId]/mark-applied/route.ts` — `POST`, proxies to `POST /api/job-matching/matches/{matchId}/mark-applied`.
  - No BFF route is added for the redirect endpoint itself — the "Apply" button's `href` points **directly** at the backend's `apply-redirect` URL (through the existing `NEXT_PUBLIC_API_BASE_URL`-style backend origin already used for direct-navigation cases, or, if the backend is not directly browser-reachable in a given deployment, a thin pass-through BFF redirect route `frontend/app/api/matches/[matchId]/apply-redirect/route.ts` that itself issues a 302 to the backend's own redirect endpoint — pick whichever matches how `backendFetch`'s base URL is actually configured per environment; check `frontend/src/lib/backend-client.ts` for whether the browser can reach the backend origin directly before deciding). This is called out explicitly as an environment-dependent decision rather than guessed at, since getting a same-origin vs. cross-origin redirect wrong here is a real, environment-specific correctness question, not a design preference.
- **`frontend/features/job-matching/api/client.ts`**: add `markApplied(matchId: string, applied: boolean): Promise<void>` and a helper `getApplyRedirectUrl(matchId: string): string` (pure string builder, not a fetch — this is used as an `<a href>`/`<Button asChild>` target, not called programmatically).
- **`frontend/features/job-matching/hooks/useMatches.ts`**: add `useMarkApplied()` mutation hook (mirrors the existing `useMarkMatchViewed`/`useSubmitFeedback` shape exactly — `useMutation` + query-cache invalidation of the matches list query key).
- **`frontend/features/job-matching/components/MatchCard.tsx`**: replace the current "View posting" plain link with:
  - An **"Apply"** `Button` (`asChild`) wrapping an `<a href={getApplyRedirectUrl(match.matchId)} target="_blank" rel="noopener noreferrer">` — satisfies the Lighthouse `external-anchors-use-rel-noopener` requirement explicitly (the existing "View posting" link already does this correctly today, confirmed at `MatchCard.tsx:56-64` — Module B's new Apply button/link must preserve the same `rel="noopener noreferrer"` attribute).
  - A **"Mark as applied"** `Checkbox`/toggle next to it, wired to `useMarkApplied()`, reflecting `match.appliedAt !== null`.
- **`frontend/features/job-swipe/components/SwipeCard.tsx`**: today this card has **no apply/link affordance at all** (confirmed — only "Draft outreach" and the swipe gestures exist). Add the same Apply button + Mark-as-applied toggle, positioned in the bottom action row alongside the existing "Draft outreach" button, visible only `isTop` (matching the existing pattern where secondary actions only render on the top card).

### 6.8 Tests

- Backend: `test_job_matching_router.py` (or wherever matches router tests live) — apply-redirect 404s for another user's match_id; 404s for a match whose posting has no `source_url`; 302s to the exact stored `source_url` on success; `apply_clicked_at` is set on first click and unchanged on a second click (idempotency assertion). `mark-applied` toggles `applied_at` on and off correctly, 404s for another user's match.
- Frontend: `MatchCard.test.tsx` / `SwipeCard.test.tsx` — Apply link has `rel="noopener noreferrer"` and `target="_blank"` and the correct `href`; Mark-as-applied checkbox reflects `appliedAt` and calls the mutation on toggle.

### 6.9 Docker / infra impact

None — no new settings beyond what's already listed, no new services, no schema outside the one migration above.

**Effort:** Small–medium. **Risk:** Low, contingent on the open-redirect guard in §6.5 being implemented exactly as specified (never accept a redirect target from any request input).

---

## 7. Module C — Job application tracking board

### 7.1 Design

Named-pipeline-stage model (Greenhouse/Lever-inspired, candidate-facing mirror image): `new → applied → replied → interview → offer → rejected`, manually transitioned (never auto-detected), filterable + sortable list first, drag-and-drop Kanban explicitly deferred to avoid scope creep into a much larger UI investment for the MVP.

### 7.2 Migration `040_job_match_application_status.py`

`down_revision = "039_job_match_apply_tracking"`.

```python
"""Add application_status enum column + status_updated_at to job_matches (Module 4, Module C).

Revision ID: 040_job_match_application_status
Revises: 039_job_match_apply_tracking
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "040_job_match_application_status"
down_revision: str | Sequence[str] | None = "039_job_match_apply_tracking"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Enforced at the app layer (Pydantic Literal), NOT a DB-level CHECK/ENUM type —
# matches the existing convention already used for JobMatch.explanation_status
# and JobMatch.feedback (both plain String columns with app-layer validation
# only, per job_matching/models.py's own inline comments). A native Postgres
# ENUM type would also complicate the SQLite dev/test path, which this repo
# consistently avoids (see JsonDoc's JSONB-vs-JSON dialect branching for the
# same underlying reason).
_STATUS_DEFAULT = "new"


def upgrade() -> None:
    with op.batch_alter_table("job_matches") as batch_op:
        batch_op.add_column(
            sa.Column(
                "application_status", sa.String(20), nullable=False, server_default=_STATUS_DEFAULT
            )
        )
        batch_op.add_column(
            sa.Column("status_updated_at", sa.DateTime(timezone=True), nullable=True)
        )
    op.create_index(
        "ix_job_matches_user_application_status",
        "job_matches",
        ["user_id", "application_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_job_matches_user_application_status", table_name="job_matches")
    with op.batch_alter_table("job_matches") as batch_op:
        batch_op.drop_column("status_updated_at")
        batch_op.drop_column("application_status")
```

### 7.3 `backend/app/modules/job_matching/models.py` changes

```python
# "new"|"applied"|"replied"|"interview"|"offer"|"rejected" — enforced at app layer,
# same convention as explanation_status/feedback above.
application_status: Mapped[str] = mapped_column(String(20), default="new", nullable=False, index=True)
status_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

Also add the reverse relationship anchor comment: the new `interview_schedules` table (Module D, §8) FKs to `job_matches.id`; no relationship object is required on `JobMatch` itself (this codebase doesn't use SQLAlchemy `relationship()` on these lightweight cross-module models — confirmed, `JobMatch`/`JobPosting` have zero `relationship()` declarations today, only plain FK columns; new tables follow the same style rather than introducing ORM relationships inconsistently).

### 7.4 Where this module's code lives

**New module `backend/app/modules/application_tracker/`** rather than piling further onto `job_matching/`. Rationale: `job_matching/` already owns scan/scoring/notification concerns; the tracker is a distinct read/filter/status-mutate surface over the same `JobMatch` table, exactly parallel to how `job_swipe/` is its own module that reads `job_matching`'s tables read-only rather than being folded into it. This keeps `job_matching/router.py` from growing an unrelated fourth concern.

```
backend/app/modules/application_tracker/
    __init__.py
    models.py       # (empty/placeholder — this module owns no tables of its own;
                     #  application_status/status_updated_at live on job_matching's
                     #  JobMatch, per RULE.md "do not duplicate", same convention
                     #  job_swipe/models.py already documents for JobMatch/JobPosting)
    schemas.py
    repository.py
    service.py
    router.py
```

**`schemas.py`:**

```python
from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel

ApplicationStatus = Literal["new", "applied", "replied", "interview", "offer", "rejected"]
_ALL_STATUSES: tuple[ApplicationStatus, ...] = (
    "new", "applied", "replied", "interview", "offer", "rejected",
)

class TrackedMatchResponse(BaseModel):
    match_id: str
    job_posting_id: str
    title: str
    company: str
    location: str | None
    remote: bool
    source_url: str | None
    overall_score: float | None  # None for manual entries (Module F) — the
                                    # 0.0 sentinel stored on the row is never
                                    # surfaced to the frontend as a literal score
    application_status: ApplicationStatus
    apply_clicked_at: datetime | None
    applied_at: datetime | None
    status_updated_at: datetime | None
    created_at: datetime
    # Module D forward-reference: null until Module D lands; present in the
    # response shape from day one so the frontend tracker card doesn't need a
    # second schema version once interview scheduling ships.
    next_interview_at: datetime | None = None

class TrackedMatchListResponse(BaseModel):
    matches: list[TrackedMatchResponse]
    total: int
    limit: int
    offset: int
    counts_by_status: dict[ApplicationStatus, int]  # for tab/column badges

class UpdateApplicationStatusRequest(BaseModel):
    application_status: ApplicationStatus
```

**`repository.py`:**

```python
from app.modules.job_matching.repository import get_owned_match  # re-exported for
    # this module's service.py — Module C never redefines the owned-single-match
    # lookup; it imports Module B's get_owned_match (job_matching/repository.py,
    # §6.5) directly, same read-only cross-module convention as everywhere else.

_SORT_COLUMNS: dict[str, Any] = {
    "newest": JobMatch.created_at.desc(),
    "oldest": JobMatch.created_at.asc(),
    # Manual entries (Module F) sentinel overall_score=0.0 must never be conflated
    # with a real low score in "score" sort — ORDER BY expression puts NULL/manual
    # rows last regardless of dialect (Postgres sorts NULL last on DESC by default;
    # SQLite does NOT — SQLite sorts NULL first always, so the explicit
    # `.is_(None)` tie-break below is REQUIRED for cross-dialect correctness, not
    # just a Postgres nicety).
    "score": (JobMatch.overall_score.is_(None), JobMatch.overall_score.desc()),
    "recently_updated": (
        JobMatch.status_updated_at.is_(None),
        JobMatch.status_updated_at.desc(),
        JobMatch.created_at.desc(),  # tie-break for rows never manually updated
    ),
}


async def list_tracked_matches(
    db: AsyncSession,
    user_id: UUID,
    *,
    status: ApplicationStatus | None,
    sort: Literal["newest", "oldest", "score", "recently_updated"],
    limit: int,
    offset: int,
) -> tuple[list[tuple[JobMatch, JobPosting | None]], int]:
    """Extends job_matching's list_matches_for_user with status filter + sort options.
    Deliberately NOT added to job_matching/repository.py itself (see §7.4 rationale).

    Uses outerjoin (not join) from day one — Module F (§10) later widens
    JobMatch.job_posting_id to nullable for manual entries; building this query
    with an inner join now would mean silently dropping every manual-entry row
    the moment Module F ships, with no error surfaced anywhere. Cheaper to write
    the correct join shape once than to remember to revisit this file later.
    """
    order_by = _SORT_COLUMNS[sort]
    order_clauses = order_by if isinstance(order_by, tuple) else (order_by,)

    stmt = (
        select(JobMatch, JobPosting)
        .outerjoin(JobPosting, JobMatch.job_posting_id == JobPosting.id)
        .where(JobMatch.user_id == user_id)
    )
    if status is not None:
        stmt = stmt.where(JobMatch.application_status == status)
    stmt = stmt.order_by(*order_clauses).limit(limit).offset(offset)

    result = await db.execute(stmt)
    rows = [(m, p) for m, p in result.all()]

    count_stmt = select(func.count()).select_from(JobMatch).where(JobMatch.user_id == user_id)
    if status is not None:
        count_stmt = count_stmt.where(JobMatch.application_status == status)
    total = (await db.execute(count_stmt)).scalar_one()

    return rows, total


async def update_status(
    db: AsyncSession, match_id: UUID, user_id: UUID, new_status: ApplicationStatus
) -> JobMatch | None:
    """Single-flight UPDATE (not read-then-write) so two concurrent PATCHes from
    the same candidate (e.g. a double-click before the button disables, or two
    browser tabs) can never race into an inconsistent read-modify-write — the
    UPDATE...WHERE is atomic at the database level regardless of how many
    concurrent requests hit it, and RETURNING gives us the fresh row in the same
    round-trip.
    """
    result = await db.execute(
        update(JobMatch)
        .where(JobMatch.id == match_id, JobMatch.user_id == user_id)
        .values(application_status=new_status, status_updated_at=datetime.now(UTC))
        .returning(JobMatch)
    )
    row = result.first()
    if row is None:
        return None
    await db.commit()
    return row[0]


async def count_by_status(db: AsyncSession, user_id: UUID) -> dict[str, int]:
    """One GROUP BY query for the tab/column badge counts — avoids 6 separate
    COUNT(*) round-trips from the frontend rendering 6 status tabs. Zero-fills
    every status not present in the result (a candidate with no rejected
    applications yet must see rejected: 0, not a missing key the frontend has
    to guard against with `?? 0` at every call site).
    """
    result = await db.execute(
        select(JobMatch.application_status, func.count())
        .where(JobMatch.user_id == user_id)
        .group_by(JobMatch.application_status)
    )
    counts = {status: 0 for status in _ALL_STATUSES}
    counts.update({row[0]: row[1] for row in result.all()})
    return counts
```

**`service.py`:**

```python
def _to_tracked_response(match: JobMatch, posting: JobPosting | None) -> TrackedMatchResponse:
    return TrackedMatchResponse(
        match_id=str(match.id),
        job_posting_id=str(match.job_posting_id) if match.job_posting_id else "",
        title=posting.title if posting else "",
        company=posting.company if posting else "",
        location=posting.location if posting else None,
        remote=posting.remote if posting else False,
        source_url=posting.source_url if posting else None,
        overall_score=match.overall_score if posting is not None else None,  # sentinel-hiding
        application_status=match.application_status,
        apply_clicked_at=match.apply_clicked_at,
        applied_at=match.applied_at,
        status_updated_at=match.status_updated_at,
        created_at=match.created_at,
        next_interview_at=None,  # populated by a follow-up outerjoin against
                                   # InterviewSchedule once Module D lands; None until then
    )


async def list_tracked(
    db: AsyncSession, user_id: UUID, *, status: ApplicationStatus | None,
    sort: Literal["newest", "oldest", "score", "recently_updated"], limit: int, offset: int,
) -> TrackedMatchListResponse:
    rows, total = await repository.list_tracked_matches(
        db, user_id, status=status, sort=sort, limit=limit, offset=offset
    )
    counts = await repository.count_by_status(db, user_id)
    return TrackedMatchListResponse(
        matches=[_to_tracked_response(m, p) for m, p in rows],
        total=total, limit=limit, offset=offset, counts_by_status=counts,
    )


async def update_status(
    db: AsyncSession, user_id: UUID, match_id: UUID, new_status: ApplicationStatus
) -> TrackedMatchResponse:
    match = await repository.update_status(db, match_id, user_id, new_status)
    if match is None:
        raise NotFoundError("Match not found")
    owned = await get_owned_match(db, match_id, user_id)
    _, posting = owned  # match row is guaranteed present here since update_status just returned it
    return _to_tracked_response(match, posting)
```

**`router.py`:**

```python
router = APIRouter(prefix="/api/application-tracker", tags=["application-tracker"], route_class=EnvelopeAPIRoute)


@router.get("/matches", response_model=TrackedMatchListResponse)
async def list_tracked_matches_endpoint(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
    status: ApplicationStatus | None = Query(default=None),
    sort: Literal["newest", "oldest", "score", "recently_updated"] = Query(default="newest"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> TrackedMatchListResponse:
    return await service.list_tracked(
        db, current_user.id, status=status, sort=sort, limit=limit, offset=offset
    )


@router.patch("/matches/{match_id}/status", response_model=TrackedMatchResponse)
async def update_application_status(
    match_id: str,
    payload: UpdateApplicationStatusRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> TrackedMatchResponse:
    return await service.update_status(db, current_user.id, UUID(match_id), payload.application_status)
```

Registered in `backend/app/main.py` alongside every other module router (find the existing `app.include_router(job_matching_router)` / `app.include_router(job_swipe_router)` block and add `app.include_router(application_tracker_router)` next to it).

### 7.5 Interaction with Module B

`applied_at` being set via Module B's `mark-applied` endpoint should **also** auto-advance `application_status` from `new` to `applied` if it's still `new` (never downgrade a status the candidate already manually advanced past, e.g. don't reset `interview` back to `applied` if they un-check "mark as applied" by mistake — only forward-fill from `new`). This one cross-module behavior lives in `job_matching/service.py::set_applied` (Module B's method), which after Module C lands should call `application_tracker.repository.update_status(db, match_id, user_id, "applied")` **only if current status == "new"**. This is the one specific place Module B and Module C's code touch, called out explicitly rather than left as an implicit assumption.

### 7.6 Frontend

**New feature folder** `frontend/features/application-tracker/`:

```
frontend/features/application-tracker/
    api/
        client.ts     # fetchTrackedMatches(status?, sort, limit, offset), updateApplicationStatus(matchId, status)
        keys.ts        # query key factory, mirrors job-matching/api/keys.ts
    hooks/
        useTrackedMatches.ts       # useQuery wrapper
        useUpdateApplicationStatus.ts  # useMutation, invalidates useTrackedMatches' query key
    components/
        TrackerFilterBar.tsx   # status dropdown + sort dropdown, controlled via URL search params
                                # (?status=interview&sort=score) so the view is linkable/shareable/back-button-safe
        TrackedMatchRow.tsx     # one row: title/company/location, score column (overall_score, "—" for
                                # Module F manual entries later), status <select>, "next interview" chip
                                # (null until Module D), Apply + Mark-as-applied (reuses Module B's controls)
        StatusBadge.tsx         # colored badge per ApplicationStatus (new=gray, applied=blue, replied=purple,
                                # interview=amber, offer=green, rejected=red) — small enough to be its own file
                                # since Module D's calendar view and Module E's practice-link card also need it
    index.ts
```

**New route** `frontend/app/app/tracker/page.tsx` → `frontend/app/app/tracker/TrackerView.tsx` (client component, mirrors `MatchesView.tsx`'s shape: loading/error/empty states, then a list of `TrackedMatchRow`s, then pagination controls). MVP is the **filterable list**, not a drag-and-drop board — per the effort/risk note in the original research, explicit column-per-stage Kanban is deferred; the status `<select>` on each row is the "move stage" affordance for v1.

**New BFF routes:**
- `frontend/app/api/application-tracker/matches/route.ts` — `GET`, forwards `status`/`sort`/`limit`/`offset` query params to `GET /api/application-tracker/matches`.
- `frontend/app/api/application-tracker/matches/[matchId]/status/route.ts` — `PATCH`, forwards to `PATCH /api/application-tracker/matches/{matchId}/status`.

**`frontend/src/lib/types.ts` additions:**

```typescript
export type ApplicationStatus = "new" | "applied" | "replied" | "interview" | "offer" | "rejected";

export type TrackedMatch = {
  matchId: string;
  jobPostingId: string;
  title: string;
  company: string;
  location: string | null;
  remote: boolean;
  sourceUrl: string | null;
  overallScore: number | null; // null for Module F manual entries (§10)
  applicationStatus: ApplicationStatus;
  applyClickedAt: string | null;
  appliedAt: string | null;
  statusUpdatedAt: string | null;
  createdAt: string;
  nextInterviewAt: string | null; // Module D
};

export type TrackedMatchListResponse = {
  matches: TrackedMatch[];
  total: number;
  limit: number;
  offset: number;
  countsByStatus: Record<ApplicationStatus, number>;
};
```

**`frontend/src/lib/api-adapter.ts` additions:** `mapBackendTrackedMatchItem`, `mapBackendTrackedMatchListToFrontend` (snake→camel, same shape as `mapBackendJobMatchItem`).

**Navigation:** `frontend/components/layout/nav-config.ts` — add `{ href: "/app/tracker", label: "Applications", icon: ClipboardList }` to `mainNav.items`, positioned after `"/app/matches/swipe"` and before `"/app/portfolio"` (keeps the job-related items grouped together in the existing order).

### 7.7 Tests

- Backend: `test_application_tracker_repository.py` — status filter, each of the 4 sort orders, `count_by_status` correctness, ownership scoping (another user's match never returned). `test_application_tracker_router.py` — full endpoint round-trip, 404 on foreign match_id for the PATCH endpoint, Module B integration case (mark-applied auto-advances `new`→`applied`, does not downgrade `interview`→`applied`).
- Frontend: `TrackedMatchRow.test.tsx` (status badge colors, score "—" fallback), `TrackerFilterBar.test.tsx` (URL search param sync), `useTrackedMatches.test.tsx`/`useUpdateApplicationStatus.test.tsx` (mirror the existing `useMatches.test.tsx` mocking pattern).

### 7.8 Docker / infra impact

None beyond the one migration and the new router registration (no new env vars, no new services/queues).

**Effort:** Medium–large (new module, new migration, new frontend route). **Risk:** Low technically; the explicitly named risk is scope creep into full drag-and-drop — the filterable-list MVP above is the committed v1 scope.

---

## 8. Module D — Interview scheduling, calendar, and notifications

### 8.1 Design summary

Ship the `.ics`/prefilled-calendar-link tier first (no OAuth, near-zero integration cost); defer full Google Calendar OAuth sync to v2. Reuse existing notification rails (`EmailService`, `push.py`) entirely — no new infra, only a new template and new call sites.

### 8.2 Migration `041_interview_schedules.py`

`down_revision = "040_job_match_application_status"`.

```python
"""Create interview_schedules table (Module 4, Module D).

Revision ID: 041_interview_schedules
Revises: 040_job_match_application_status
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "041_interview_schedules"
down_revision: str | Sequence[str] | None = "040_job_match_application_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)

    op.create_table(
        "interview_schedules",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "job_match_id",
            uuid_type,
            sa.ForeignKey("job_matches.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("reminder_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_interview_schedules_user_scheduled_at", "interview_schedules", ["user_id", "scheduled_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_interview_schedules_user_scheduled_at", table_name="interview_schedules")
    op.drop_table("interview_schedules")
```

### 8.3 New module `backend/app/modules/interview_scheduling/`

```
backend/app/modules/interview_scheduling/
    __init__.py
    models.py        # InterviewSchedule ORM model
    schemas.py
    repository.py
    service.py
    router.py
    ics_builder.py    # .ics file generation (no external dependency needed — RFC 5545
                       # VEVENT is simple enough to hand-build; avoids adding a new
                       # third-party package for one small text template, consistent
                       # with this repo's general "free/self-hosted, minimal deps"
                       # philosophy already stated for every other provider mode)
```

**`models.py`:**

```python
class InterviewSchedule(Base):
    """One row per JobMatch, enforced by a UNIQUE constraint on job_match_id — v1
    is deliberately single-schedule-per-match ("when is *the* interview for this
    application"), not a multi-round interview tracker (phone screen → onsite →
    offer as separate rows). Rescheduling reuses the same row (schedule_interview
    is an upsert, §8.3's router). Multi-round support is a real future need (most
    real interview loops have 2-4 rounds) but is explicitly out of scope for this
    plan — the UNIQUE constraint below is the honest reflection of that scope cut,
    not an oversight. Revisiting this later means dropping the constraint and
    adding a `round_number`/`round_label` column; not done now to avoid building
    UI (a whole "rounds" list view) nobody asked for yet.
    """

    __tablename__ = "interview_schedules"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_match_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_matches.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=lambda: datetime.now(UTC))
```

**`repository.py`:**

```python
async def upsert_schedule(
    db: AsyncSession, *, job_match_id: UUID, user_id: UUID,
    scheduled_at: datetime, duration_minutes: int, notes: str | None,
) -> InterviewSchedule:
    """INSERT-or-UPDATE keyed on the job_match_id UNIQUE constraint — this is the
    rescheduling path: a candidate who re-opens the dialog and picks a new time
    updates the existing row (and re-fires §8.5/§8.6's notification+reminder for
    the new time) rather than erroring on the UNIQUE violation or creating a
    second row. Read-then-write, not a raw SQL upsert, since SQLite's
    ON CONFLICT syntax and Postgres's differ enough that a portable two-step
    (SELECT, then INSERT or UPDATE) is clearer than dialect-branching upsert SQL
    for a low-frequency, single-row-per-user operation like this.
    """
    existing = await get_schedule_for_match(db, job_match_id, user_id)
    if existing is not None:
        existing.scheduled_at = scheduled_at
        existing.duration_minutes = duration_minutes
        existing.notes = notes
        existing.reminder_sent_at = None  # rescheduled — the old reminder timer is stale
        await db.flush()
        await db.commit()
        return existing

    schedule = InterviewSchedule(
        job_match_id=job_match_id, user_id=user_id, scheduled_at=scheduled_at,
        duration_minutes=duration_minutes, notes=notes,
    )
    db.add(schedule)
    await db.flush()
    await db.commit()
    return schedule


async def get_schedule_for_match(
    db: AsyncSession, job_match_id: UUID, user_id: UUID
) -> InterviewSchedule | None:
    result = await db.execute(
        select(InterviewSchedule).where(
            InterviewSchedule.job_match_id == job_match_id,
            InterviewSchedule.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def delete_schedule(db: AsyncSession, schedule_id: UUID) -> None:
    await db.execute(delete(InterviewSchedule).where(InterviewSchedule.id == schedule_id))
    await db.commit()


async def mark_reminder_sent(db: AsyncSession, schedule_id: UUID) -> None:
    """Idempotency guard for the reminder worker task (§8.6) — sets
    reminder_sent_at so a worker retry (RQ retries on transient failure) or a
    duplicate enqueue can never double-send the reminder email/push.
    """
    await db.execute(
        update(InterviewSchedule)
        .where(InterviewSchedule.id == schedule_id, InterviewSchedule.reminder_sent_at.is_(None))
        .values(reminder_sent_at=datetime.now(UTC))
    )
    await db.commit()
```

**`service.py` helpers used by the router above:**

```python
def _to_response(schedule: InterviewSchedule) -> InterviewScheduleResponse:
    return InterviewScheduleResponse(
        id=str(schedule.id),
        job_match_id=str(schedule.job_match_id),
        scheduled_at=schedule.scheduled_at,
        duration_minutes=schedule.duration_minutes,
        notes=schedule.notes,
        ics_download_url=f"/api/interviews/matches/{schedule.job_match_id}/schedule.ics",
        google_calendar_link=build_google_calendar_link(
            summary="Interview",  # router builds the title/company-specific version for the .ics;
            description=schedule.notes or "",  # this response-level link is a generic fallback shown
            location=None,  # inline in the UI before a page navigation, refined client-side if needed
            start=schedule.scheduled_at,
            duration_minutes=schedule.duration_minutes,
        ),
        created_at=schedule.created_at,
    )


async def _send_scheduled_notification(
    db: AsyncSession, user: User, match: JobMatch, posting: JobPosting | None, schedule: InterviewSchedule,
) -> None:
    title = posting.title if posting else "your role"
    company = posting.company if posting else "the company"
    await email_service.send_email(
        db, user, EmailTemplate.INTERVIEW_SCHEDULED,
        context={
            "title": title, "company": company,
            "scheduled_at": schedule.scheduled_at.isoformat(),
            "ics_download_url": f"/api/interviews/matches/{match.id}/schedule.ics",
            "google_calendar_link": build_google_calendar_link(
                summary=f"Interview: {title} at {company}", description=schedule.notes or "",
                location=None, start=schedule.scheduled_at, duration_minutes=schedule.duration_minutes,
            ),
        },
    )
    subs = await push.get_subscriptions_for_user(db, user.id)
    for sub in subs:
        await push.send_push_notification(
            sub,
            {
                "event": "interview_scheduled", "title": title, "company": company,
                "scheduled_at": schedule.scheduled_at.isoformat(),
            },
        )
```

`job_matching/service.py` gains one small shared helper reused by both Module B (§6) and Module D here — a single forward-fill-only status-advance function, so the "never downgrade a further-along status" rule lives in exactly one place instead of being reimplemented per module:

```python
_STATUS_ORDER: dict[str, int] = {
    "new": 0, "applied": 1, "replied": 2,
    "interview": 3, "offer": 4, "rejected": 4,
}


async def advance_application_status_if_earlier(
    db: AsyncSession, match: JobMatch, *, target: str
) -> None:
    if _STATUS_ORDER[target] > _STATUS_ORDER[match.application_status]:
        match.application_status = target
        match.status_updated_at = datetime.now(UTC)
        await db.flush()
        await db.commit()
```

New `app/workers/queue.py` additions used above: `cancel_interview_reminder(schedule_id: str) -> None` wraps `rq_scheduler.Scheduler(...).cancel(job_id)` inside a `try/except` that logs-and-swallows `rq.exceptions.NoSuchJobError` (the job already fired, or never existed — both are fine, cancellation is best-effort).

**Timezone handling (edge case):** `scheduled_at` is stored tz-aware in UTC (standard for this codebase — every other `DateTime(timezone=True)` column follows the same rule). The candidate always *enters* and *sees* the time in their own browser's local timezone — the datetime `<input>` in `ScheduleInterviewDialog` (§8.7) is a native `<input type="datetime-local">`, which has no timezone concept of its own; the frontend converts the picked local wall-clock time to a UTC ISO string via `new Date(localValue).toISOString()` before the POST, and converts back via `new Date(iso).toLocaleString(undefined, { dateStyle: "full", timeStyle: "short" })` (passing `undefined` locale/timezone means "use the browser's own", so a candidate who schedules from Karachi and later opens the same match from London sees the *same instant*, correctly converted — never a raw UTC string, which is the actual edge case this note prevents someone from shipping). The `.ics` file and Google Calendar link are also built from the UTC value (`ics_builder.py` emits `Z`-suffixed `DTSTART`/`DTEND`), so the calendar app the candidate imports into does its own correct local-timezone rendering too — no timezone field needs to be stored on the row at all.

**`ics_builder.py`:**

```python
def build_ics(
    *, uid: str, summary: str, description: str, location: str | None,
    start: datetime, duration_minutes: int, organizer_email: str,
) -> str:
    """Hand-built RFC 5545 VEVENT — minimal, no recurrence (RRULE not needed for a
    one-off interview), no attendee RSVP tracking (this is a personal reminder file
    for the candidate, not a real invite the interviewer receives — the candidate's
    own calendar app is the only consumer). DTSTART/DTEND in UTC (Z suffix) so the
    file is timezone-unambiguous regardless of which calendar app opens it.
    """
    start_utc = start.astimezone(UTC)
    end_utc = start_utc + timedelta(minutes=duration_minutes)
    now_utc = datetime.now(UTC)

    def _fmt(dt: datetime) -> str:
        return dt.strftime("%Y%m%dT%H%M%SZ")

    def _escape(text: str) -> str:
        # RFC 5545 §3.3.11: backslash, comma, semicolon must be escaped; literal
        # newlines become the two-char sequence \n.
        return (
            text.replace("\\", "\\\\")
            .replace(",", "\\,")
            .replace(";", "\\;")
            .replace("\n", "\\n")
        )

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//HyerEnrichment//Interview Scheduling//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{_fmt(now_utc)}",
        f"DTSTART:{_fmt(start_utc)}",
        f"DTEND:{_fmt(end_utc)}",
        f"SUMMARY:{_escape(summary)}",
        f"DESCRIPTION:{_escape(description)}",
        f"ORGANIZER:mailto:{organizer_email}",
    ]
    if location:
        lines.append(f"LOCATION:{_escape(location)}")
    lines += ["STATUS:CONFIRMED", "END:VEVENT", "END:VCALENDAR"]
    # RFC 5545 §3.1 requires CRLF line endings, not bare \n.
    return "\r\n".join(lines) + "\r\n"


def build_google_calendar_link(
    *, summary: str, description: str, location: str | None, start: datetime, duration_minutes: int,
) -> str:
    """https://calendar.google.com/calendar/render?action=TEMPLATE&text=...&dates=...
    prefilled-link pattern — zero OAuth, opens Google Calendar's own "add event" UI
    with fields prefilled; the candidate still clicks "Save" themselves. This is the
    well-known Eventbrite/Calendly pattern flagged as [NotFound] (no specific citation
    pulled) but standard practice — used here as the low-friction alternative to the
    .ics download for candidates who prefer not to download a file.
    """
    start_utc = start.astimezone(UTC)
    end_utc = start_utc + timedelta(minutes=duration_minutes)
    dates = f"{start_utc.strftime('%Y%m%dT%H%M%SZ')}/{end_utc.strftime('%Y%m%dT%H%M%SZ')}"
    params = {"action": "TEMPLATE", "text": summary, "dates": dates, "details": description}
    if location:
        params["location"] = location
    return f"https://calendar.google.com/calendar/render?{urlencode(params)}"
```

**`schemas.py`:**

```python
class ScheduleInterviewRequest(BaseModel):
    scheduled_at: datetime
    duration_minutes: int = Field(default=60, ge=15, le=480)
    notes: str | None = Field(default=None, max_length=2000)

class InterviewScheduleResponse(BaseModel):
    id: str
    job_match_id: str
    scheduled_at: datetime
    duration_minutes: int
    notes: str | None
    ics_download_url: str
    google_calendar_link: str
    created_at: datetime
```

**`router.py`:**

```python
router = APIRouter(prefix="/api/interviews", tags=["interview-scheduling"], route_class=EnvelopeAPIRoute)


@router.post("/matches/{match_id}/schedule", response_model=InterviewScheduleResponse)
async def schedule_interview(
    match_id: str, payload: ScheduleInterviewRequest, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> InterviewScheduleResponse:
    """Creates/updates the InterviewSchedule row, advances the JobMatch's
    application_status to "interview" (Module C integration — same forward-fill-only
    rule as Module B's mark-applied: only auto-advance if current status isn't
    already past "interview" e.g. don't downgrade "offer" back to "interview"),
    and enqueues both the confirmation notification (email+push, §8.5) and the
    reminder job (§8.6).
    """
    if payload.scheduled_at <= datetime.now(UTC):
        raise HTTPException(status_code=422, detail="scheduled_at must be in the future")

    owned = await job_matching_repository.get_owned_match(db, UUID(match_id), current_user.id)
    if owned is None:
        raise HTTPException(status_code=404, detail="Match not found")
    match, posting = owned

    schedule = await repository.upsert_schedule(
        db,
        job_match_id=match.id,
        user_id=current_user.id,
        scheduled_at=payload.scheduled_at,
        duration_minutes=payload.duration_minutes,
        notes=payload.notes,
    )

    await job_matching_service.advance_application_status_if_earlier(
        db, match, target="interview"
    )

    await _send_scheduled_notification(db, current_user, match, posting, schedule)

    send_at = payload.scheduled_at - timedelta(hours=get_settings().interview_reminder_hours_before)
    queue.enqueue_interview_reminder(str(schedule.id), send_at)

    return _to_response(schedule)


@router.get("/matches/{match_id}/schedule", response_model=InterviewScheduleResponse | None)
async def get_interview_schedule(
    match_id: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db_session),
) -> InterviewScheduleResponse | None:
    schedule = await repository.get_schedule_for_match(db, UUID(match_id), current_user.id)
    return _to_response(schedule) if schedule else None


@router.delete("/matches/{match_id}/schedule", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_interview(
    match_id: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db_session),
) -> None:
    """Deletes the InterviewSchedule row. Does NOT auto-revert application_status —
    a candidate who cancels a scheduling row after actually attending (rescheduling
    flow) shouldn't have their status silently reset; status stays a manual field
    (Module C's core design tenet), this endpoint only removes the calendar artifact.
    Also cancels the pending reminder job via RQ's cancel_job (no-op, logged at
    warning level, if the job already fired or already ran — same idempotent-cancel
    pattern as job_matching's existing scan-cancellation path).
    """
    schedule = await repository.get_schedule_for_match(db, UUID(match_id), current_user.id)
    if schedule is None:
        return
    queue.cancel_interview_reminder(str(schedule.id))
    await repository.delete_schedule(db, schedule.id)


@router.get("/matches/{match_id}/schedule.ics")
async def download_ics(
    match_id: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db_session),
) -> Response:
    """Returns the .ics file with Content-Type: text/calendar; charset=utf-8 and
    Content-Disposition: attachment so the browser downloads/opens-in-calendar-app
    rather than rendering the raw ICS text.
    """
    owned = await job_matching_repository.get_owned_match(db, UUID(match_id), current_user.id)
    if owned is None:
        raise HTTPException(status_code=404, detail="Match not found")
    match, posting = owned
    schedule = await repository.get_schedule_for_match(db, match.id, current_user.id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="No interview scheduled for this match")

    title = posting.title if posting else "your role"
    company = posting.company if posting else "the company"
    ics_body = build_ics(
        uid=f"interview-{schedule.id}@hyerenrichment",
        summary=f"Interview: {title} at {company}",
        description=schedule.notes or f"Interview for {title} at {company}",
        location=None,
        start=schedule.scheduled_at,
        duration_minutes=schedule.duration_minutes,
        organizer_email=get_settings().interview_ics_organizer_email,
    )
    return Response(
        content=ics_body,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="interview-{schedule.id}.ics"'},
    )
```

Registered in `main.py` alongside the other module routers.

### 8.4 `EmailTemplate` additions

`backend/app/services/email_service.py`'s `EmailTemplate` enum gains:

```python
INTERVIEW_SCHEDULED = "interview_scheduled"
INTERVIEW_REMINDER = "interview_reminder"
```

Two new `_render_interview_scheduled(ctx)` / `_render_interview_reminder(ctx)` methods, following the exact HTML/text-string-template shape every other `_render_*` method in this file already uses (see `_render_job_match_digest` for the closest structural analog — a templated list of one job's details plus a CTA link). `_render_interview_scheduled`'s CTA links to both the `.ics` download URL and the Google Calendar prefilled link. Both renderer functions registered in the `_render_template`'s `templates` dict.

### 8.5 Confirmation notification (reuses existing rails, no new infra)

Inside `schedule_interview`'s service method, after the `InterviewSchedule` row is committed:

```python
await email_service.send_email(
    db, user, EmailTemplate.INTERVIEW_SCHEDULED,
    context={
        "title": posting.title, "company": posting.company,
        "scheduled_at": schedule.scheduled_at.isoformat(),
        "ics_download_url": f"/api/interviews/matches/{match.id}/schedule.ics",
        "google_calendar_link": build_google_calendar_link(
            summary=f"Interview: {posting.title} at {posting.company}", description=schedule.notes or "",
            location=None, start=schedule.scheduled_at, duration_minutes=schedule.duration_minutes,
        ),
    },
)
# Push: reuses app.modules.job_matching.push.send_push_notification directly —
# this is the "new call site outside the job-matching-digest context" flagged in
# the original research as the one piece of push wiring that's actually new.
subscriptions = await job_matching_repository.list_subscriptions_for_user(db, user_id)
for sub in subscriptions:
    await push.send_push_notification(
        sub,
        {
            "event": "interview_scheduled", "title": posting.title, "company": posting.company,
            "scheduled_at": schedule.scheduled_at.isoformat(),
        },
    )
```

Note the cross-module import: `interview_scheduling/service.py` imports `app.modules.job_matching.push` and `app.modules.job_matching.repository.list_subscriptions_for_user` directly — same read-only cross-module convention already established (§3), since Module D has no reason to duplicate push-subscription storage or the Web Push send helper.

### 8.6 Reminder job

New queue `QUEUE_INTERVIEW_REMINDERS = "interview_reminders"` in `app/workers/queue.py`, priority slot `7` (same tier as `QUEUE_FEEDBACK` — user-facing, time-sensitive). New `enqueue_interview_reminder(interview_schedule_id: str, send_at: datetime) -> None` wrapper using `rq_scheduler.Scheduler.enqueue_at(...)`, mirroring `fan_out_daily_scans`'s existing use of `Scheduler.enqueue_at` for staggered per-candidate jobs. Called once, at schedule-creation time, with `send_at = scheduled_at - timedelta(hours=settings.interview_reminder_hours_before)` (default 24h, §4). If `send_at` is already in the past (interview scheduled with less than 24h notice), the reminder enqueues immediately instead of being skipped — a same-day interview still deserves a reminder, just sent right away rather than not at all.

New worker task `backend/app/workers/tasks/interview_reminders.py::send_interview_reminder_job(interview_schedule_id: str) -> None` — loads the `InterviewSchedule` + joined `JobMatch`/`JobPosting`, re-checks `reminder_sent_at is None` (guards against a double-send if the job somehow runs twice) and that `scheduled_at` hasn't since been changed/cancelled (re-fetch, don't trust the enqueue-time snapshot), sends via the same email+push pattern as §8.5 but with the `INTERVIEW_REMINDER` template, then sets `reminder_sent_at`.

### 8.7 "Practice for this interview" link (forward reference to Module E)

`InterviewScheduleResponse` (and the tracker row, §7.6) exposes enough to build a link: `frontend/features/interview-scheduling/components/InterviewScheduleCard.tsx` renders a **"Practice for this interview"** button that navigates to `/app/practice?jobMatchId={matchId}` (Module E's practice entry point, §9.6). No new field needed on the response for this — the frontend already has `match_id` from context.

### 8.8 Frontend

**New feature folder** `frontend/features/interview-scheduling/`:

```
frontend/features/interview-scheduling/
    api/{client.ts, keys.ts}
    hooks/
        useInterviewSchedule.ts     # useQuery(matchId)
        useScheduleInterview.ts     # useMutation
        useCancelInterview.ts       # useMutation
    components/
        ScheduleInterviewDialog.tsx  # date/time picker (reuse existing shadcn Dialog +
                                      # form primitives already in components/ui/), duration,
                                      # notes textarea
        InterviewScheduleCard.tsx    # shown on a TrackedMatchRow when application_status
                                      # == "interview": date/time, "Add to Calendar"
                                      # (.ics download + Google Calendar link, both as
                                      # plain <a> tags — no client-side calendar library
                                      # needed), "Practice for this interview", "Cancel"
    index.ts
```

**Integration point:** `TrackedMatchRow.tsx` (Module C) renders `<InterviewScheduleCard>` inline when `applicationStatus === "interview"`, and a "Schedule interview" button (opens `ScheduleInterviewDialog`) when transitioning a row's status dropdown to `"interview"` for the first time (i.e., the status change and the scheduling dialog are two separate, sequential actions — changing the dropdown to "interview" doesn't force scheduling, but immediately offers it).

**New BFF routes:**
- `frontend/app/api/interviews/matches/[matchId]/schedule/route.ts` — `POST`/`GET`/`DELETE`, proxies to the three respective backend endpoints.
- `.ics` download is a **direct link to the backend**, not proxied through a BFF route (same reasoning as Module B's apply-redirect — a file-download response doesn't benefit from a Next.js round-trip and the existing codebase has no precedent for proxying binary/file responses through the BFF layer; confirm `backend-client.ts`'s base-URL reachability assumption before finalizing, same caveat as §6.7).

**Types (`types.ts`):** `InterviewSchedule { id, jobMatchId, scheduledAt, durationMinutes, notes, icsDownloadUrl, googleCalendarLink, createdAt }`.

### 8.9 Tests

- Backend: `test_interview_scheduling_router.py` — schedule/get/cancel round-trip, ownership scoping, status auto-advance-to-"interview" (and non-downgrade of a later stage), `.ics` file has correct `Content-Type`/`Content-Disposition` and parses as valid RFC 5545 (a minimal hand-rolled parser assertion — check for `BEGIN:VEVENT`/`DTSTART`/`DTEND`/`END:VEVENT` markers is sufficient, no need for a full ICS-parsing dependency in tests either). `test_interview_reminders_worker.py` — reminder fires once, respects `reminder_sent_at` idempotency guard, re-fetches current `scheduled_at` rather than trusting a stale snapshot.
- Frontend: `ScheduleInterviewDialog.test.tsx`, `InterviewScheduleCard.test.tsx` (renders both calendar-add affordances, "Practice for this interview" link has the correct `?jobMatchId=` query param).

### 8.10 Docker / infra impact

- New queue `interview_reminders` — needs a listening worker. **Decision: no new dedicated worker container.** The mechanism is now confirmed by direct inspection (not left as an open question): `backend/docker/Dockerfile.worker`'s `CMD` is just `["python", "-m", "app.workers.rq_worker"]` — the actual queue list lives in Python, inside `app/workers/rq_worker.py::main()`, not in the Dockerfile or `docker-compose.yml` at all. That function branches on `settings.worker_queue_mode`: in `"per_tier"` mode it listens to exactly one queue named by `WORKER_TARGET_QUEUE` (used by the dedicated `worker-tier1`/`worker-tier234` containers); in the default general-purpose mode it builds an explicit Python list — `[Queue(QUEUE_FEEDBACK, ...), Queue(QUEUE_OUTREACH, ...), Queue(QUEUE_DOCUMENT, ...), Queue(QUEUE_EMBEDDING, ...), Queue(QUEUE_CV_EXTRACTION, ...), Queue(QUEUE_NAME, ...)]` — and this is exactly where `QUEUE_OUTREACH` was added when outreach shipped, confirming this is the established pattern for "lightweight, not tier-scoped" background work. `QUEUE_JOB_MATCHING` is deliberately **not** in this list — job matching gets its own dedicated `worker-job-matching` container (`Dockerfile.worker-job-matching`, wired up in `docker-compose.foundation.yml`) because JobSpy scraping is heavy; interview reminders are a single lightweight email+push send per schedule, so they belong in the general-purpose list alongside outreach, not on a new dedicated container. **Concrete change:** add `Queue(QUEUE_INTERVIEW_REMINDERS, connection=connection)` to that list in `app/workers/rq_worker.py::main()`, with a one-line comment (`# NEW — Module D`) matching the existing `# NEW — Module 2` style already there for `QUEUE_OUTREACH`.
- `rq-scheduler`'s `register_scheduled_jobs()` doesn't need a new cron entry (interview reminders are one-off `enqueue_at` calls triggered per-schedule, not a recurring cron job, unlike `fan_out_daily_scans`).
- New settings `INTERVIEW_REMINDER_HOURS_BEFORE`, `INTERVIEW_ICS_ORGANIZER_EMAIL` (§4) added to the `worker`/`api` service environment blocks in `docker-compose.yml` only if a non-default value is needed per environment (same "code default is enough for dev, override in `.env.production` only if ops wants a different value" pattern as Module A's setting).

**Effort:** Medium. **Risk:** Low — fully additive, reuses 100% of existing notification infrastructure per the original research's own finding.

---

## 9. Module E — JD-aware interview practice

### 9.1 What actually exists today (restated precisely, per §1.1)

On `origin/feat/phase2-module3-interview-prep`:
- `backend/app/services/question_generator.py::generate_questions(job_role, category, difficulty, settings, count, candidate_context: CandidateContext | None)` — `CandidateContext` is `{skills, target_role, years_experience, recent_job_titles}`, all résumé-derived. No job-description field exists anywhere in this file.
- `backend/app/modules/questions/service.py::get_questions(db, user_id, request: QuestionRequest, settings)` — orchestrates `select_questions` (shared bank) first, falls back to `generate_questions` only on a shortfall, optionally personalizing via `_load_candidate_context` when `request.personalize=True`. `QuestionRequest` has no JD field.
- `backend/app/modules/practice_audio/` — audio upload → Whisper transcription → heuristic analysis, keyed to a `practice_session_id`, entirely JD-agnostic (it doesn't care what questions were asked, just transcribes+analyzes the answer audio).
- `backend/app/modules/sessions/models.py::PracticeSession`/`QuestionAttempt` — session/attempt tracking, `session_type: str` free-text field (no enum), `session_metadata: JsonDoc` free-form dict — **this is the extension point Module E uses**, since a "JD-tailored practice session" is a new `session_type` value with JD context stashed in `session_metadata`, not a new table.

### 9.2 Design

Add a **new, parallel generation path** rather than overloading `get_questions`/`generate_questions`'s existing role/category/difficulty-keyed shape: a JD-tailored question is not selectable from the shared bank (bank questions are role/category/difficulty-keyed, never JD-specific — sharing them across users of different companies/JDs would be actively wrong), so **bank-first selection must be bypassed entirely** when a JD is supplied, per the original research's own correct call. This is cleanest as a sibling function, not a branch deep inside `get_questions`.

### 9.3 `backend/app/services/question_generator.py` changes

Add a new dataclass and a new prompt-building/generation function, **additive only** — every existing call site (`questions/service.py::get_questions`) is untouched, since `candidate_context`'s existing shape and `generate_questions`'s existing signature don't change at all:

```python
@dataclass(slots=True)
class JobContext:
    """JD-tailored personalization input (Module 4, Module E). Distinct from
    CandidateContext (résumé-derived) — a JobContext always accompanies a
    CandidateContext when generating (both the JD and the résumé ground the
    question), but is never used alone.
    """
    job_description: str  # JobPosting.description_raw, truncated (see _MAX_JD_CHARS below)
    job_title: str
    company: str


_MAX_JD_CHARS = 3000  # generous excerpt — long enough for a full JD, short enough to
                       # keep prompt cost bounded; matches the existing precedent of
                       # workers/tasks/outreach.py's _get_job_description() truncating
                       # to description_raw[:1500] for the same cost-control reason,
                       # sized up here since question generation needs more of the JD's
                       # actual responsibilities/requirements text than an outreach
                       # email's brief "job description excerpt" context line does.


def _build_jd_generation_messages(
    category: QuestionCategory,
    difficulty: QuestionDifficulty,
    job_context: JobContext,
    candidate_context: CandidateContext | None,
    count: int = 1,
) -> list[dict[str, str]]:
    """Builds the JD-tailored prompt. Reuses GENERATION_SYSTEM_PROMPT verbatim (the
    interviewer-persona instructions don't change), only the user-turn content differs:
    grounds the question in the JD's actual text first, then layers candidate résumé
    context on top exactly the way _build_generation_messages already does for the
    non-JD path — this keeps the two prompts structurally parallel rather than
    diverging into two unrelated prompt-engineering styles.
    """
    category_hints = _CATEGORY_HINTS  # extracted to a module-level constant shared by both
    difficulty_hints = _DIFFICULTY_HINTS  # builder functions (see below) — these are pure
                               # lookup tables with no role-specific logic, so
                               # _build_generation_messages's private inline dicts are
                               # hoisted out to module level here and that function is
                               # updated to reference the same constants, rather than
                               # this new function duplicating the lookup tables.

    jd_excerpt = job_context.job_description[:_MAX_JD_CHARS]
    user_content = f"""
Generate {count} unique interview question{"s" if count > 1 else ""} tailored SPECIFICALLY
to this job posting — not a generic question for the role in general.

Job title: {job_context.job_title}
Company: {job_context.company}
Job description: {jd_excerpt}

Category: {category} ({category_hints[category]})
Difficulty: {difficulty} ({difficulty_hints[difficulty]})

Ground the question in specific responsibilities, requirements, or technologies
actually mentioned in the job description above. Do not ask something that could
apply to any {job_context.job_title} role anywhere — it must be recognizably
about THIS posting.
{"Return a JSON array with " + str(count) + " question objects." if count > 1 else "Return a single JSON object."}
""".strip()

    if candidate_context is not None:
        # identical personalization-details block to _build_generation_messages —
        # extract to a shared _append_candidate_context_details(user_content, ctx) -> str
        # helper so both builders stay in sync rather than copy-pasting this block twice.
        user_content = _append_candidate_context_details(user_content, candidate_context)

    return [
        {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


async def generate_jd_tailored_questions(
    job_context: JobContext,
    category: QuestionCategory,
    difficulty: QuestionDifficulty,
    settings: Settings,
    count: int = 1,
    candidate_context: CandidateContext | None = None,
) -> tuple[list[QuestionData], dict[str, int]]:
    """JD-tailored sibling of generate_questions(). Same HTTP call shape, retry
    policy (with_transient_retry), response parsing (_parse_generation_response
    is reused as-is — the response JSON shape is identical), and token-usage
    return contract — only the prompt-building step differs, via
    _build_jd_generation_messages instead of _build_generation_messages.
    """
    if count < 1 or count > 5:
        raise ValueError("count must be between 1 and 5")
    api_key = settings.openai_api_key.strip()
    if not api_key:
        raise ValueError("OpenAI API key not configured")

    messages = _build_jd_generation_messages(category, difficulty, job_context, candidate_context, count)
    return await _call_and_parse(messages, count, job_role_for_logging=job_context.job_title)
```

`generate_questions()` above must be refactored in the same PR to extract its own tail — the `httpx` POST via `with_transient_retry`, followed by `_parse_generation_response` and the `(list[QuestionData], dict[str, int])` return — into that same shared `_call_and_parse(messages, count, job_role_for_logging)` private helper, then call it instead of inlining the ~40-line retry/parse/log block a second time. This is a refactor of existing, working code: the extraction must not change `generate_questions()`'s observable behavior (same retries, same error types, same logging), verified by the existing `test_question_generator.py` suite passing unmodified.

### 9.4 New module `backend/app/modules/jd_practice/`

A new module (not folded into `questions/`) because its request/response shape, bank-bypass behavior, and cost-budget (`jd_question_generation_daily_limit_per_user`, §4) are genuinely different from `questions/`'s bank-first orchestration — mirrors the same "distinct concern, own module, reads sibling tables read-only" pattern used throughout this plan (Module C vs. `job_matching`, Module D vs. `job_matching`).

```
backend/app/modules/jd_practice/
    __init__.py
    schemas.py
    service.py
    router.py
```

**`schemas.py`:**

```python
class JdPracticeRequest(BaseModel):
    job_match_id: str  # required — this endpoint only exists for a JD the candidate
                        # is actually tracking (Module C), never an arbitrary pasted JD;
                        # keeps scope bounded to "practice for THIS interview" per the
                        # original feature request, not a general-purpose JD-paste tool
    category: QuestionCategory | None = None
    difficulty: QuestionDifficulty | None = None
    count: int = Field(default=5, ge=1, le=10)

class JdPracticeQuestionItem(BaseModel):
    id: UUID
    question_text: str
    category: QuestionCategory
    difficulty: QuestionDifficulty
    sample_answer: str  # exposed here (unlike questions/schemas.py's QuestionItem,
                          # which omits sample_answer from the list response) since
                          # this is consumed by a single "prep for my interview" flow
                          # where showing the model answer after attempting is part of
                          # the UX (§9.6) — check whether questions/schemas.py's
                          # omission was deliberate (likely: don't spoil the bank
                          # question's answer before the candidate attempts it) and
                          # apply the same non-spoiler ordering here: this field is
                          # returned but the frontend must not render it until after
                          # the candidate submits an attempt (UI-layer discipline,
                          # not a schema-layer omission, since JD-tailored questions
                          # aren't reused across users the way bank questions are —
                          # there's no "spoiling the bank" concern, but there IS a
                          # "don't let the candidate read the answer before trying"
                          # UX concern, which belongs in the frontend, not the API).

class JdPracticeResponse(BaseModel):
    questions: list[JdPracticeQuestionItem]
    job_match_id: str
    practice_session_id: UUID  # a new PracticeSession row created with
                                 # session_type="jd_tailored" and session_metadata=
                                 # {"job_match_id": ..., "job_title": ..., "company": ...}
```

**`service.py`:**

```python
async def get_jd_tailored_questions(
    db: AsyncSession, user_id: UUID, request: JdPracticeRequest, settings: Settings,
) -> JdPracticeResponse:
    """Always bypasses the shared bank (§9.2) — every call generates fresh via
    generate_jd_tailored_questions. Daily-limit-guarded the same way
    questions/service.py guards personalized (résumé-only) generation, but against
    the SEPARATE jd_question_generation_daily_limit_per_user budget (§4), since this
    path is strictly more expensive per request (always generates, never serves from
    the bank) and deserves its own independently-tunable cap rather than competing
    with Module 3's résumé-personalization budget for the same limit.
    """
    match_row = await job_matching_repository.get_owned_match(db, UUID(request.job_match_id), user_id)
    # (job_matching_repository here refers to the efficient single-row lookup
    # introduced in Module C §7.4 — get_owned_match; if Module E ships before
    # Module C, add the minimal single-row fetch inline here instead and let
    # Module C's later PR replace it with the shared repository function.)
    if match_row is None:
        raise NotFoundError("Tracked job not found")
    match, posting = match_row
    if posting is None:
        # Module F forward-compat: a manual job entry (job_posting_id is NULL) has
        # no scraped description at all — there is nothing to tailor a question
        # against, so this path is explicitly rejected with a clear, actionable
        # message rather than crashing on `posting.description_raw` (which would
        # be an AttributeError on None) or silently falling back to generic
        # (non-JD-tailored) questions the candidate didn't ask for.
        raise ValidationAppError(
            "JD-tailored practice isn't available for manually-added jobs "
            "(no job description on file) — try résumé-personalized practice instead"
        )
    if not posting.description_raw:
        raise ValidationAppError("This job posting has no description to practice against")

    generated_today = await _jd_generation_count_today(db, user_id)  # mirrors
        # questions/service.py's _personalized_generation_count_today shape, but
        # counts PracticeSession rows with session_type="jd_tailored" created in
        # the last 24h, since JD-tailored questions aren't persisted to
        # interview_questions with a personalized_for_user_id flag the way Module
        # 3's bank-reuse-eligible generated questions are (§9.2 — JD questions are
        # NOT written back to the shared interview_questions bank at all, since
        # they're inherently non-reusable across users/JDs; they live only in
        # session_metadata / are returned directly to the caller, never persisted
        # as InterviewQuestion rows).
    if generated_today >= settings.jd_question_generation_daily_limit_per_user:
        raise RateLimitError("Daily JD-tailored practice question limit reached")

    candidate_context = await _load_candidate_context(db, user_id)  # reuse
        # questions/service.py's existing _load_candidate_context helper verbatim
        # (import it, don't reimplement) — the résumé-loading logic is identical
        # regardless of whether the questions are JD-tailored or not.

    job_context = JobContext(
        job_description=posting.description_raw, job_title=posting.title, company=posting.company,
    )
    generated, token_usage = await generate_jd_tailored_questions(
        job_context, request.category or "technical", request.difficulty or "medium",
        settings, count=request.count, candidate_context=candidate_context,
    )
    await track_llm_cost(
        model="gpt-4o-mini",
        input_tokens=token_usage["input_tokens"],
        output_tokens=token_usage["output_tokens"],
        operation="jd_question_generation",
    )

    session = PracticeSession(
        user_id=user_id, session_type="jd_tailored", status="in_progress",
        session_metadata={"job_match_id": str(match.id), "job_title": posting.title, "company": posting.company},
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return JdPracticeResponse(
        questions=[JdPracticeQuestionItem(id=uuid4(), question_text=q["question_text"], category=q["category"], difficulty=q["difficulty"], sample_answer=q["sample_answer"]) for q in generated],
        job_match_id=request.job_match_id,
        practice_session_id=session.id,
    )
```

Note the explicit design decision, stated so it isn't silently assumed: **JD-tailored questions get a fresh random `uuid4()` for their `id` field and are never written to `interview_questions`.** This is deliberate — writing them to the shared bank (as Module 3's résumé-personalized-but-still-generic questions already do, via `_persist_generated_questions`) would pollute the shared pool with a question that's only meaningful for one specific job posting at one specific company, and the existing `question_attempts.question_id` FK (added in the renumbered `036_question_attempt_fk_and_personalization.py`, §2.2) is nullable specifically to support this — a `QuestionAttempt` row for a JD-tailored question sets `question_id = NULL` and instead relies on `attempt_metadata` (already a `JsonDoc` free-form column on `QuestionAttempt`) to carry the actual `question_text`/`category`/`difficulty` it was answering, since there's no bank row to join back to.

**`router.py`:**

```python
router = APIRouter(prefix="/api/jd-practice", tags=["jd-practice"], route_class=EnvelopeAPIRoute)

@router.post("/questions", response_model=JdPracticeResponse)
async def get_jd_practice_questions(
    request: JdPracticeRequest, user: VerifiedUser, db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> JdPracticeResponse:
    return await get_jd_tailored_questions(db, user.id, request, settings)
```

Registered in `main.py`.

### 9.5 Attempt submission and audio practice integration

No new endpoints needed for **submitting** an attempt against a JD-tailored question — the existing `sessions/` module's attempt-recording path (wherever `QuestionAttempt` rows get created today on `phase2-module3-interview-prep` — check `sessions/router.py`/`sessions/service.py`, which the branch diff shows exist but weren't read in full during this investigation; the implementer must confirm the exact existing endpoint shape before wiring this) already accepts a `question_id: UUID | None` per the nullable FK from §9.4. The frontend (§9.6) passes `question_id: null` plus the question text in `attempt_metadata` for JD-tailored attempts, using whatever the existing attempt-submission contract already is.

Similarly, `practice_audio`'s upload endpoint (`POST /api/practice/audio`, takes `practice_session_id`) needs **zero backend changes** — a JD-tailored `PracticeSession` (created in §9.4) is a valid `practice_session_id` for that endpoint exactly like any other session type, since `practice_audio/service.py::upload_and_process_audio` only checks `PracticeSession.user_id` ownership, never branches on `session_type`.

### 9.6 Frontend

**New feature folder** `frontend/features/jd-practice/`:

```
frontend/features/jd-practice/
    api/{client.ts, keys.ts}   # requestJdPracticeQuestions(jobMatchId, category?, difficulty?, count)
    hooks/useJdPracticeQuestions.ts   # useMutation (this is a generation request, not a
                                        # cacheable GET — mirrors useTriggerScan's mutation
                                        # shape more than useMatches' query shape)
    components/
        JdPracticeEntryCard.tsx   # shown from InterviewScheduleCard (Module D, §8.7) and
                                    # from a TrackedMatchRow generally (not gated to only
                                    # "interview" status — a candidate may want to practice
                                    # right after applying, before an interview is even
                                    # scheduled) — "Practice for this job" button
        JdPracticeSessionView.tsx  # the actual practice flow: shows one question at a time,
                                    # text or audio answer (reuses the EXISTING audio-recording
                                    # component from Module 3's practice UI if one exists on
                                    # phase2-module3-interview-prep's frontend side — the branch
                                    # diff shows only backend changes under frontend/ for that
                                    # branch's own practice_audio feature were not enumerated in
                                    # this investigation; implementer must check
                                    # frontend/features/ on that branch for an existing
                                    # practice/audio-recorder component before building a new one),
                                    # sample answer revealed only after submission (§9.4's UX note)
    index.ts
```

**New route** `frontend/app/app/practice/page.tsx` — reads `?jobMatchId=` from the query string (linked from Module D's `InterviewScheduleCard` and Module C's `TrackedMatchRow`), calls `useJdPracticeQuestions` on mount, renders `JdPracticeSessionView`.

**New BFF route** `frontend/app/api/jd-practice/questions/route.ts` — `POST`, proxies to `POST /api/jd-practice/questions`.

**Types:** `JdPracticeQuestion { id, questionText, category, difficulty, sampleAnswer }`, `JdPracticeResponse { questions: JdPracticeQuestion[], jobMatchId, practiceSessionId }`.

### 9.7 Tests

- Backend: `test_jd_practice_service.py` — bank is never queried (assert `select_questions` is not called — this is the one behavioral invariant that most needs a regression test, since accidentally falling back to the shared bank would silently reintroduce generic questions for a JD-tailored request); daily limit enforcement (separate counter from Module 3's own limit — test that hitting Module 3's `question_generation_daily_limit_per_user` does NOT block this endpoint and vice versa); 404 for a `job_match_id` not owned by the caller; 400/`ValidationAppError` for a posting with no `description_raw`; generated questions are never persisted to `interview_questions`.
- Backend: `test_question_generator_jd.py` — `_build_jd_generation_messages` includes the JD excerpt verbatim (truncated at `_MAX_JD_CHARS`), includes candidate context details when provided, omits them when not — parallel to whatever existing tests cover `_build_generation_messages`'s personalization branch on `phase2-module3-interview-prep`.
- Frontend: `JdPracticeSessionView.test.tsx` — sample answer hidden until after submission; `JdPracticeEntryCard.test.tsx` — link navigates with the correct `jobMatchId` query param.

### 9.8 Docker / infra impact

No new services/queues (this is a synchronous request-path LLM call, same as Module 3's existing on-demand generation — no background job needed since `count` is capped at 10 and a single OpenAI call already handles the existing non-JD path synchronously within an HTTP request). New setting `JD_QUESTION_GENERATION_DAILY_LIMIT_PER_USER` (§4) needs no compose changes beyond the code default unless ops wants a non-default value.

**Effort:** Medium (new module, prompt-engineering iteration needed for quality, but no new infrastructure). **Risk:** Low technically; the real risk (flagged honestly, matching the original research's own labeling) is prompt-output quality requiring iteration/eval rather than being a one-shot correct implementation — budget review cycles for this, not just the initial build.

---

## 10. Module F — Manual job entry ("add jobs from your own network")

### 10.1 Design decision (restated from the research, confirmed against the schema)

`JobPosting` is a shared, dedup'd, global table (`dedup_key` unique index, `sources_seen` array shared across whichever candidates happened to scan into the same posting). A manually-added job is inherently private to one candidate and must never be dedup'd against, or shown to, anyone else. **Decision: separate table `manual_job_entries`**, not a nullable `added_by_user_id` column bolted onto `JobPosting` — keeps the shared table's dedup invariant ("every row here is a real external listing, potentially seen by multiple candidates") intact rather than special-casing it for private rows.

### 10.2 How a manual entry flows into the tracker (Module C)

`JobMatch.job_posting_id` is a required FK to `job_postings.id` today (confirmed: `job_matching/models.py:127`, `nullable=False`). A manual entry has no `JobPosting` row, so it cannot produce a real `JobMatch` row without a schema change to that FK. **Decision: widen `JobMatch.job_posting_id` to nullable, add a sibling nullable `manual_job_entry_id` FK, and add a CHECK constraint enforcing exactly one of the two is set.** This is the discriminator pattern flagged as the recommended option in the original research, made concrete:

```
job_matches.job_posting_id      nullable, FK -> job_postings.id
job_matches.manual_job_entry_id  nullable, FK -> manual_job_entries.id
CHECK ( (job_posting_id IS NOT NULL) != (manual_job_entry_id IS NOT NULL) )  -- exactly one
```

This means **every reader of `JobMatch` joined to `JobPosting`** (there are several: `job_matching/repository.py::list_matches_for_user`/`get_top_unexplained_matches`, `job_swipe/repository.py`, `application_tracker/repository.py` from Module C, `workers/tasks/outreach.py::_get_job_description`) must be updated to `LEFT JOIN` instead of an inner join, and branch on which side is populated. This is the single largest cross-cutting change in this plan and is why Module F is sequenced **last** among the tracker-dependent modules (§13) — it touches code Modules A/B/C/D already shipped and stabilized.

### 10.3 Migration `042_manual_job_entries.py`

`down_revision = "041_interview_schedules"`.

```python
"""Create manual_job_entries table; widen job_matches.job_posting_id to nullable
and add manual_job_entry_id + a CHECK enforcing exactly one source (Module 4, Module F).

Revision ID: 042_manual_job_entries
Revises: 041_interview_schedules
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "042_manual_job_entries"
down_revision: str | Sequence[str] | None = "041_interview_schedules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)

    op.create_table(
        "manual_job_entries",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("user_id", uuid_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("company", sa.String(255), nullable=False),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("source_label", sa.String(255), nullable=True),
        sa.Column("source_url", sa.String(2048), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    with op.batch_alter_table("job_matches") as batch_op:
        batch_op.alter_column("job_posting_id", existing_type=uuid_type, nullable=True)
        batch_op.add_column(
            sa.Column(
                "manual_job_entry_id", uuid_type,
                sa.ForeignKey("manual_job_entries.id", ondelete="CASCADE"), nullable=True,
            )
        )
        # SQLite has no native CHECK-constraint alteration via batch mode the same way
        # Postgres does, but op.create_check_constraint works under batch_alter_table
        # for both dialects here since this is an ADD, not a modification of column
        # nullability under a constraint — consistent with how 033 (renumbered 036)
        # already used batch mode for a mixed add-column + add-constraint operation.
        batch_op.create_check_constraint(
            "ck_job_matches_exactly_one_source",
            "(job_posting_id IS NOT NULL AND manual_job_entry_id IS NULL) OR "
            "(job_posting_id IS NULL AND manual_job_entry_id IS NOT NULL)",
        )


def downgrade() -> None:
    with op.batch_alter_table("job_matches") as batch_op:
        batch_op.drop_constraint("ck_job_matches_exactly_one_source")
        batch_op.drop_column("manual_job_entry_id")
        batch_op.alter_column("job_posting_id", existing_type=uuid_type, nullable=False)
    op.drop_table("manual_job_entries")
```

**Data-safety note for the implementer:** the `downgrade()`'s `alter_column(..., nullable=False)` will fail on any environment that has real manual-entry `JobMatch` rows (their `job_posting_id` is legitimately NULL) — this is expected and correct; a downgrade after real manual entries exist requires deleting those rows first, which is a deliberate, manual, ops-reviewed decision, not something the migration should silently paper over.

### 10.4 `backend/app/modules/job_matching/models.py` changes

```python
job_posting_id: Mapped[UUID | None] = mapped_column(  # was non-nullable
    ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=True, index=True
)
manual_job_entry_id: Mapped[UUID | None] = mapped_column(
    ForeignKey("manual_job_entries.id", ondelete="CASCADE"), nullable=True, index=True
)
```

The `CheckConstraint` from §10.3 is also declared in `__table_args__` for consistency with how the SQLAlchemy model should mirror the DB (matching the pattern `sessions/models.py::PracticeSession.__table_args__` already uses for its own `CheckConstraint`s):

```python
__table_args__ = (
    CheckConstraint(
        "(job_posting_id IS NOT NULL AND manual_job_entry_id IS NULL) OR "
        "(job_posting_id IS NULL AND manual_job_entry_id IS NOT NULL)",
        name="ck_job_matches_exactly_one_source",
    ),
)
```

### 10.5 New `ManualJobEntry` model — lives in the new module, not `job_matching/models.py`

Per RULE.md's layer-ownership convention (mirrors why `job_swipe` doesn't redefine `JobMatch`), `ManualJobEntry` is owned by a new `backend/app/modules/manual_jobs/` module, even though `job_matching/models.py` has to *reference* its table name in the new FK column above (a bare `ForeignKey("manual_job_entries.id", ...)` string reference needs no import of the model class itself, so this doesn't create a circular import — same pattern already used for `ForeignKey("users.id", ...)` throughout the codebase without importing `auth.models.User` into every module that FKs to it).

```
backend/app/modules/manual_jobs/
    __init__.py
    models.py     # ManualJobEntry
    schemas.py
    repository.py
    service.py
    router.py
```

**`models.py`:**

```python
class ManualJobEntry(Base):
    __tablename__ = "manual_job_entries"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
```

**`schemas.py`:**

```python
class CreateManualJobEntryRequest(BaseModel):
    title: str = Field(max_length=255)
    company: str = Field(max_length=255)
    location: str | None = Field(default=None, max_length=255)
    source_label: str | None = Field(default=None, max_length=255)
    source_url: str | None = Field(default=None, max_length=2048)
    notes: str | None = Field(default=None, max_length=2000)

class ManualJobEntryResponse(BaseModel):
    id: str
    title: str
    company: str
    location: str | None
    source_label: str | None
    source_url: str | None
    notes: str | None
    job_match_id: str  # the auto-created tracker row's id — returned so the
                         # frontend can navigate straight to the tracker entry
    created_at: datetime
```

**`service.py`:**

```python
async def create_manual_entry(
    db: AsyncSession, user_id: UUID, request: CreateManualJobEntryRequest
) -> ManualJobEntryResponse:
    """Creates the ManualJobEntry row, then a companion JobMatch row with
    manual_job_entry_id=entry.id, job_posting_id=None, similarity_score=0.0,
    rule_score=0.0, overall_score=0.0, score_breakdown={}, application_status="new"
    (the "no overall_score/similarity for manual entries — nothing to embed
    against" design point from the original research; 0.0 here is a sentinel, not
    a real score — §10.6 covers how the frontend must render it, since 0.0
    displayed literally would misleadingly look like a real terrible-match score
    rather than "not applicable"). Both inserts happen in one transaction — if the
    JobMatch insert fails (e.g. a future constraint violation), the ManualJobEntry
    insert rolls back too, so there's never an orphaned entry with no tracker row.
    """
    entry = ManualJobEntry(
        user_id=user_id,
        title=request.title,
        company=request.company,
        location=request.location,
        source_label=request.source_label,
        source_url=request.source_url,
        notes=request.notes,
    )
    db.add(entry)
    await db.flush()  # populate entry.id for the FK below, without committing yet

    match = JobMatch(
        user_id=user_id,
        job_posting_id=None,
        manual_job_entry_id=entry.id,
        similarity_score=0.0,
        rule_score=0.0,
        overall_score=0.0,
        score_breakdown={},  # deliberately empty, not {"below_similarity_threshold": True} —
                               # that flag (Module A, §5.3) means something specific ("a real
                               # similarity search ran and fell back"), which never applies to
                               # a manual entry; an empty dict correctly signals "not applicable"
                               # rather than overloading the flag with a second meaning
        application_status="new",
    )
    db.add(match)
    await db.flush()
    await db.commit()

    return ManualJobEntryResponse(
        id=str(entry.id), title=entry.title, company=entry.company, location=entry.location,
        source_label=entry.source_label, source_url=entry.source_url, notes=entry.notes,
        job_match_id=str(match.id), created_at=entry.created_at,
    )
```

**`router.py`:**

```python
router = APIRouter(prefix="/api/manual-jobs", tags=["manual-jobs"], route_class=EnvelopeAPIRoute)


@router.post("", response_model=ManualJobEntryResponse)
async def create_manual_job_entry(
    request: CreateManualJobEntryRequest, current_user: CurrentUser, db: AsyncSession = Depends(get_db_session),
) -> ManualJobEntryResponse:
    return await service.create_manual_entry(db, current_user.id, request)
```

Registered in `main.py`.

### 10.6 Fallout: every existing `JobMatch` ⋈ `JobPosting` join site must handle the manual-entry case

This is the change that most needs a careful implementer, not a rubber-stamp of the sketch below — enumerate every join site and fix each one explicitly rather than trusting a single shared helper to cover all of them silently:

- **`job_matching/repository.py::list_matches_for_user`**: change the inner `.join(JobPosting, ...)` to `.outerjoin(JobPosting, ...)`, add `.outerjoin(ManualJobEntry, JobMatch.manual_job_entry_id == ManualJobEntry.id)` (cross-module read import, same convention as everywhere else in this plan), and the row-mapping code that builds `JobMatchResponse` must branch: `title = posting.title if posting else manual_entry.title` (same for `company`, `location`; `remote`/`source`/`salary_*` are `False`/`"manual"`/`None` for manual rows since `ManualJobEntry` has no such fields).
- **`job_matching/repository.py::get_top_unexplained_matches`**: manual entries should **never** be selected here at all — there's no JD-embedding to explain a similarity match against, so add `.where(JobMatch.job_posting_id.is_not(None))` to this query specifically (explanations are a `job_posting_id`-only concept).
- **`job_swipe/`**: manual entries **never appear in the swipe deck** — swiping is specifically for scanner-discovered matches the candidate hasn't reacted to yet; a manually-added job the candidate typed in themselves has no "discovery" moment to swipe on. `job_swipe/repository.py`'s deck query adds `.where(JobMatch.job_posting_id.is_not(None))` (same filter as above, different query).
- **`application_tracker/repository.py`** (Module C): this is the **one place manual entries are supposed to show up** — its join becomes the outer-join-both-sides pattern above, and `TrackedMatchResponse`'s mapping sets `overall_score: float | None = None` for manual rows (schema change: widen `overall_score` from `float` to `float | None` — the frontend's existing "score column shows '—' for manual entries" requirement, confirmed already anticipated in Module C §7.6's `TrackedMatch.overallScore: number | null` type).
- **`workers/tasks/outreach.py::_get_job_description`**: manual entries have no `description_raw` to draft outreach from — this function already returns `None` gracefully when `posting.description_raw` is falsy (confirmed at `outreach.py:143`), so extending it to also return `None` early when `match.job_posting_id is None` (before even attempting the `JobPosting` lookup) is a small, safe addition, not a structural change.
- **`jd_practice/service.py::get_jd_tailored_questions`** (Module E, §9.4): must explicitly reject manual entries with a clear `ValidationAppError("Manual job entries have no job description to practice against — this feature requires a scanned posting")`, since `posting.description_raw` doesn't exist to check when `job_posting_id is None` at all — this must be checked **before** attempting the `description_raw` lookup, or it 500s on a `None.description_raw` attribute access instead of returning a clean 400. Call this out as a required defensive check in Module E's own PR if Module F ships after Module E (sequencing dependency noted again in §13).

### 10.7 Frontend

**New feature folder** `frontend/features/manual-jobs/`:

```
frontend/features/manual-jobs/
    api/{client.ts, keys.ts}
    hooks/useCreateManualJobEntry.ts
    components/AddManualJobDialog.tsx  # title, company, location, source label,
                                         # optional URL, notes — simple form, per the
                                         # original research's own "Simple form UI" scope
    index.ts
```

**Integration point:** a **"+ Add a job"** button on the tracker view (`TrackerView.tsx`, Module C), opening `AddManualJobDialog`; on success, navigates to (or refreshes and highlights) the new tracker row via the returned `jobMatchId`.

**`TrackedMatchRow.tsx` (Module C) update:** score column renders `"—"` (with a `title="Manually added — no match score"` tooltip) when `overallScore === null`; `source`-dependent UI (the "Apply" link, remote badge) is conditionally hidden/adapted — a manual entry's "Apply" affordance becomes a plain link to `sourceUrl` if the candidate provided one, with no server-side click-tracking redirect (Module B's `apply-redirect` endpoint is `job_posting_id`-keyed today and would need the same nullable-join treatment to support manual entries; **out of scope for Module F's initial cut** — manual-entry rows get a plain `<a>` tag if `sourceUrl` is set, and no Apply button at all if it's blank, rather than extending Module B's redirect-tracking machinery to a second source type in the same PR).

**New BFF route** `frontend/app/api/manual-jobs/route.ts` — `POST`, proxies to `POST /api/manual-jobs`.

**Types:** `ManualJobEntry { id, title, company, location, sourceLabel, sourceUrl, notes, jobMatchId, createdAt }`. `TrackedMatch.overallScore` type already anticipated as `number | null` in §7.6.

### 10.8 Tests

- Backend: `test_manual_jobs_router.py` — create round-trip, returned `job_match_id` resolves to a real `JobMatch` with `manual_job_entry_id` set and `job_posting_id` NULL. `test_application_tracker_repository.py` (Module C, extended) — manual entries appear in tracker listing with `overall_score=None`, mixed pagination with real scanned matches sorts correctly (manual entries' `0.0` sentinel never leaks into a `sort=score` ordering ahead of real low-scoring matches — this needs an explicit `ORDER BY` tie-break test, e.g. `ORDER BY overall_score IS NULL, overall_score DESC` or equivalent, called out explicitly since naive `ORDER BY overall_score DESC` would put `0.0` sentinel rows in the middle of real scores instead of consistently last/first). `test_job_swipe_repository.py` (extended) — manual entries never appear in `get_deck()`. `test_job_matching_repository.py` (extended) — manual entries never appear in `get_top_unexplained_matches()`. `test_outreach_worker.py` (extended) — `_get_job_description` returns `None` cleanly for a manual-entry `job_match_id`, no exception.
- Frontend: `AddManualJobDialog.test.tsx`, `TrackedMatchRow.test.tsx` (score "—" fallback, Apply affordance degrades gracefully for manual rows).

### 10.9 Docker / infra impact

None beyond the one migration and new router registration.

**Effort:** Medium (new table + a real, non-trivial join-widening change touching four existing repository files). **Risk:** Medium — explicitly flagged higher than every other module in this plan, because the nullable-FK-plus-outer-join change is the one place a mistake (e.g. forgetting one of the five join sites in §10.6) causes a 500 or a silent data-leak-shaped bug (a manual entry's `None` posting causing an `AttributeError` deep in a response mapper) rather than a cleanly-caught validation error. **Recommend Module F be reviewed with extra scrutiny and a dedicated test pass over §10.6's five call sites specifically**, not just the new code Module F itself adds.

---

## 11. Module G — Multi-channel AI message generation

### 11.1 Design

`OutreachMessage` is hard-coded to one email-shaped `{subject, body}` pair today (confirmed: `outreach/models.py` has no `message_type`/`channel` column). Add a `message_type` discriminator with per-type system prompts and per-type constraints (LinkedIn's real character limits), and make explicit — to the user, in the UI, not just in this document — that non-email channels are **copy-paste-only**, never automated sends, since LinkedIn has no public send-as-the-candidate API and this repo's own `send_message()` already only marks-as-sent rather than transmitting anywhere (confirmed: `outreach/service.py::send_message`'s own docstring, quoted in §11.5 below).

### 11.2 Migration `043_outreach_message_type.py`

`down_revision = "042_manual_job_entries"`.

```python
"""Add message_type + custom_instruction to outreach_messages (Module 4, Module G).

Revision ID: 043_outreach_message_type
Revises: 042_manual_job_entries
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "043_outreach_message_type"
down_revision: str | Sequence[str] | None = "042_manual_job_entries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("outreach_messages") as batch_op:
        batch_op.add_column(
            sa.Column("message_type", sa.String(20), nullable=False, server_default="email")
        )
        batch_op.add_column(sa.Column("custom_instruction", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("outreach_messages") as batch_op:
        batch_op.drop_column("custom_instruction")
        batch_op.drop_column("message_type")
```

`server_default="email"` means every existing `OutreachMessage` row (all created before this migration, necessarily email-shaped since that was the only type) backfills correctly with zero data migration script needed — this is the reason the default is baked into the column definition rather than a separate `UPDATE` statement.

### 11.3 `backend/app/modules/outreach/models.py` changes

```python
message_type: Mapped[str] = mapped_column(String(20), default="email", nullable=False, index=True)
custom_instruction: Mapped[str | None] = mapped_column(Text, nullable=True)
```

### 11.4 `backend/app/modules/outreach/schemas.py` changes

```python
OutreachMessageType = Literal["email", "linkedin", "generic", "custom"]

class OutreachDraftRequest(BaseModel):
    # existing fields (document_id, company_name, recipient_role_title, job_match_id) unchanged
    message_type: OutreachMessageType = "email"
    custom_instruction: str | None = Field(
        default=None, max_length=1000,
        description="Required when message_type='custom'; validated in the service layer "
        "(not a Pydantic model_validator) since the requirement is conditional on another "
        "field's value — same pattern already used by JobPreferencesRequest's salary_max "
        "cross-field validator elsewhere in this codebase for the shape of the check, "
        "though this one is easier expressed as a plain service-layer guard.",
    )

# OutreachMessageResponse gains: message_type: OutreachMessageType
```

### 11.5 `backend/app/workers/tasks/outreach.py` changes — per-type system prompts

The existing `_OUTREACH_SYSTEM_PROMPT` module constant is renamed `_EMAIL_SYSTEM_PROMPT` (unchanged content) and three siblings are added:

```python
_LINKEDIN_SYSTEM_PROMPT = """
You are helping a job candidate write a short LinkedIn message to a hiring manager or
recruiter. LinkedIn InMail messages are capped at 200 characters for the subject line and
1,900 characters for the body — write well within these limits (aim for under 150 words in
the body; LinkedIn's own guidance is that shorter InMails perform better). Do not include an
email-style signature block or a formal letter salutation ("Dear ..."); LinkedIn messages
read as brief, direct, professional notes. Reference at least one real detail from the job
description or company context if provided. End with a clear, low-friction call to action
(e.g., suggesting a short call). Return JSON: {"subject": <string, <=200 chars>, "body":
<string, <=1900 chars>}.
""".strip()

_GENERIC_SYSTEM_PROMPT = """
You are helping a job candidate write a short, informal outreach message (e.g., a text
message or DM to a personal contact/referral, not a formal email to a stranger). Keep it
brief (under 100 words), warm, and direct — this is going to someone the candidate likely
already knows or has a warm introduction to, not a cold outreach. No email-style subject
line is needed; return JSON: {"subject": <string, can be empty>, "body": <string>}.
""".strip()

_CUSTOM_INSTRUCTION_PREFIX = """
Additional instructions from the candidate for this specific message (follow these in
addition to, not instead of, the grounding in the candidate's real background, the job
description, and company context provided below):
""".strip()
```

`_draft_with_llm` gains a `message_type: str` and `custom_instruction: str | None` parameter; selects the system prompt via a `{"email": _EMAIL_SYSTEM_PROMPT, "linkedin": _LINKEDIN_SYSTEM_PROMPT, "generic": _GENERIC_SYSTEM_PROMPT, "custom": _EMAIL_SYSTEM_PROMPT}` lookup (custom mode reuses the email system prompt as its base persona/grounding-discipline instructions, but appends `_CUSTOM_INSTRUCTION_PREFIX + custom_instruction` to the **user** message content, layering the candidate's free-text directive on top of the same JD+résumé+company-context inputs already gathered — exactly the design already specified in the original research). After generation, a hard length-enforcement pass runs for `message_type == "linkedin"` specifically:

```python
if message_type == "linkedin":
    settings = get_settings()
    if len(subject) > settings.outreach_linkedin_inmail_subject_max_chars:
        subject = subject[: settings.outreach_linkedin_inmail_subject_max_chars - 1].rstrip() + "…"
    if len(body) > settings.outreach_linkedin_inmail_body_max_chars:
        body = body[: settings.outreach_linkedin_inmail_body_max_chars - 1].rstrip() + "…"
    # Truncation is a defensive backstop, not the primary control — the system
    # prompt above already instructs the model to stay within limits; this catches
    # the cases where it doesn't, since LinkedIn will itself reject/truncate an
    # over-limit InMail and a candidate should never be surprised by that after
    # already copying the text out of this app.
```

`generate_outreach_draft_job`'s signature grows `message_type: str = "email"` and `custom_instruction: str | None = None` params, passed through from `OutreachService.request_draft`'s RQ `queue.enqueue(...)` call (which already passes every other draft parameter positionally — add these two to the same call).

### 11.6 `backend/app/modules/outreach/service.py` changes

`request_draft` validates `body.message_type == "custom"` requires `body.custom_instruction` non-empty (`raise HTTPException(400, "custom_instruction is required when message_type='custom'")` — the conditional-requirement check flagged as service-layer, not schema-layer, in §11.4). The Redis lock key gains `message_type` so a candidate can request, e.g., both an email draft and a LinkedIn draft for the same company concurrently without the second being rejected as a duplicate-in-progress: `f"outreach-draft-lock:{user_id}:{company}:{job_match_id}:{message_type}"`.

`send_message`'s existing docstring (quoted verbatim below, since Module G's UI must communicate this exact constraint to the user, not soften it) is preserved unchanged and its behavior is **extended**, not altered: the CAN-SPAM unsubscribe footer (`_UNSUBSCRIBE_FOOTER_TEMPLATE`) is appended **only when `message.message_type == "email"`** — never for `linkedin`/`generic`/`custom`, since CAN-SPAM's own statutory definition is scoped to "electronic mail message" and a physical-address/opt-out footer makes no sense pasted into a LinkedIn message or a text to a personal contact.

> *(Existing docstring, reproduced for traceability — this constraint predates Module G and Module G must not weaken it):* "This method does NOT actually transmit an email over SMTP in v1 — no email-sending infra targeting arbitrary third-party recipients exists in this repo today... Marking as 'sent' here records the candidate's own action of copying/sending it externally themselves."

**Edge case — manual edits via the existing `PATCH /api/outreach/{message_id}` endpoint:** `outreach/router.py:38`'s `edit_draft` (backed by `OutreachEditRequest`) already lets a candidate hand-edit a draft's subject/body after generation, for every message type, not just email — this endpoint is untouched by §11.5's LLM-side truncation backstop entirely, since that backstop only runs at generation time. Without a fix, a candidate could paste in a 3,000-character LinkedIn message via this existing edit endpoint and it would save successfully, only to be rejected or silently truncated by LinkedIn itself later — the app would have told them nothing. `OutreachService.edit_draft` gains one guard, applied only when `message.message_type == "linkedin"`: re-validate the *incoming edited* `subject`/`body` against `outreach_linkedin_inmail_subject_max_chars`/`outreach_linkedin_inmail_body_max_chars` and raise `HTTPException(422, "LinkedIn messages are limited to {N} characters; please shorten before saving")` if either is exceeded — a hard rejection here, not a silent truncation, since silently cutting off a candidate's *own hand-typed* edit (as opposed to an LLM's over-generation) would delete content they explicitly chose to keep. The frontend's live character counter (§11.7) exists precisely so the candidate sees this coming before they hit save, not after.

### 11.7 Frontend

**`frontend/features/outreach/components/OutreachDraftCard.tsx` changes:**
- The "send" button's label/copy changes based on `message.messageType`: for `email`, keep existing "Send" copy (still just marks-as-sent per the existing, unmodified backend behavior — no actual transmission happens today for email either, this is a pre-existing constraint Module G does not change). For `linkedin`/`generic`/`custom`, the button is relabeled **"Copy & mark as sent"** with an explicit inline note ("LinkedIn/DMs can't be sent from here — copy this and paste it into LinkedIn/your messaging app yourself") and a **"Copy to clipboard"** icon-button next to the body text, using the browser `navigator.clipboard.writeText(...)` API — this is the concrete UI expression of §11.6's constraint, not left as an assumption the user has to infer.
- For `linkedin` drafts specifically, render a live character counter under both the subject and body fields while editing (`{body.length} / 1900`), turning amber past 1500 and red past 1900 — mirrors the "color-changing character counter" UX pattern LinkedIn's own composer uses, called out directly in the original research citation.

**New "draft type" selector** on whatever component currently triggers `POST /api/outreach/drafts` (check `frontend/features/outreach/` and `frontend/app/app/outreach/page.tsx` for the exact existing trigger UI — likely a "Draft outreach" button surfaced from `SwipeCard.tsx`/`MatchCard.tsx`, per `SwipeCard.tsx`'s existing `onDraftOutreach` prop confirmed at line 12): a small segmented control / `Select` with four options (Email, LinkedIn message, Generic message, Custom), and — only when "Custom" is selected — a `Textarea` for the free-text instruction, exactly matching the original research's "text box that only appears for custom" spec.

**Types (`types.ts`):** `OutreachMessage` gains `messageType: "email" | "linkedin" | "generic" | "custom"`. New request-side type `RequestOutreachDraftInput` gains `messageType` and optional `customInstruction`.

**`api-adapter.ts`:** `adaptOutreachMessage` adds `messageType: raw.message_type`. A new `toBackendOutreachDraftRequest(input)` helper (or extend whatever the existing draft-request BFF body-building code does today) adds `message_type`/`custom_instruction` to the outgoing JSON.

**BFF route** `frontend/app/api/outreach/drafts/route.ts` (existing — check if this file already exists on `master-complete-foundation`; the outreach `POST /drafts` backend endpoint already exists per §∅ investigation, confirmed at `outreach/router.py:24`, so its BFF counterpart almost certainly already exists too) — just needs its request-body pass-through to include the two new fields, no structural change.

### 11.8 Tests

- Backend: `test_outreach_worker.py` (extended) — one test per `message_type` asserting the correct system prompt is selected; LinkedIn truncation backstop fires correctly at both the subject and body limits (test with a deliberately-oversized fake LLM response, not by hoping the real model complies); `custom` mode's user-content includes the `_CUSTOM_INSTRUCTION_PREFIX` + the candidate's instruction verbatim; CAN-SPAM footer is appended for `email` and never for the other three types (`send_message` test matrix, all four types).
- Backend: `test_outreach_router.py` (extended) — 400 when `message_type="custom"` and `custom_instruction` is missing/empty; concurrent-draft-request lock is scoped per `message_type` (two simultaneous requests for the same company but different `message_type`s both succeed; two for the same company AND same `message_type` — the second is rejected, exactly like today).
- Frontend: `OutreachDraftCard.test.tsx` — "Copy & mark as sent" copy/behavior for non-email types, character counter color thresholds for `linkedin`, custom-instruction textarea only renders when "Custom" is selected.

### 11.9 Docker / infra impact

None beyond the migration and the three new settings already listed in §4 (`OUTREACH_LINKEDIN_INMAIL_BODY_MAX_CHARS`, `OUTREACH_LINKEDIN_INMAIL_SUBJECT_MAX_CHARS`, `OUTREACH_LINKEDIN_CONNECTION_NOTE_MAX_CHARS` — note the connection-note limit is defined in settings for completeness/future use but **not yet wired to any code path in this initial cut**, since the LinkedIn message type modeled here is the InMail/general-message shape, not the connection-request-note shape; if a future iteration needs a distinct "connection note" `message_type`, this setting is already in place for it — flagged here so it isn't mistaken for dead code, it's forward-provisioned, not wired to the fifth `message_type` this plan doesn't build).

**Effort:** Medium (schema + prompt branching + moderate UI work). **Risk:** Low, contingent on the UI being explicit (per §11.7) that non-email channels are copy-paste-only — the single biggest risk in this module is a user believing "Send" actually transmits a LinkedIn message when it does not.

---

## 12. Full Docker/infra architecture impact (consolidated)

This section pulls together every infra-touching decision from Modules A–G into one place, since the user's request was for **100% of Docker architecture**, not just the incremental deltas scattered through each module above.

### 12.1 What does NOT change

- No new Docker **images**/Dockerfiles. Every module above reuses the existing `Dockerfile.api` (FastAPI app) and `Dockerfile.worker` (RQ worker) build targets — nothing in Modules A–G needs a new runtime, new system dependency, or new sidecar container. This is a deliberate design constraint honored throughout (§8.10 explicitly rejects a new dedicated worker container for interview reminders; §9.8 explicitly notes JD-practice generation is synchronous, no new queue/worker).
- No new external services in `docker-compose.yml` (no new database, no new cache, no new third-party sidecar). Module D's `.ics`/calendar-link generation is pure Python, zero dependencies; Module E's JD-tailored generation reuses the existing OpenAI client path `question_generator.py` already uses.
- `docker-compose.prod.yml`, `docker-compose.tier1.yml`, `docker-compose.tier-workers.yml`, `docker-compose.staging.yml`, `docker-compose.loadtest.yml`, `docker-compose.multilogin.yml`, `docker-compose.fake-sidecars.yml`, `docker-compose.foundation.yml` — **none of these files need structural changes** (no new `services:` blocks, no new `profiles:`, no new `volumes:`). They only need the environment-variable additions in §12.2 below, and only in the environments where a non-default value is actually wanted.

### 12.2 Environment variable additions, by compose file and service

All new settings from §4, with their defaults, need **zero** compose changes to work correctly in dev (the `Settings` field defaults already cover it) — env vars only need to be added to a compose file's `environment:` block in an environment where ops wants to **override** the default. The table below is the complete reference for where each one *would* go if overridden:

| Setting | Default | Compose file(s) / service(s) if overridden |
|---|---|---|
| `JOB_MATCHING_MIN_RESULTS` | `10` | `docker-compose.yml` → `worker` (job-matching scans run on the worker) |
| `APPLY_REDIRECT_BASE_URL` | `""` | `docker-compose.yml` → `api` (redirect endpoint is API-served) |
| `INTERVIEW_REMINDER_HOURS_BEFORE` | `24` | `docker-compose.yml` → `worker` (reminder scheduling happens worker-side) |
| `INTERVIEW_ICS_ORGANIZER_EMAIL` | `""` (falls back to `SENDGRID_FROM_EMAIL`) | `docker-compose.yml` → `api` + `worker` (both build `.ics` files — API for the download endpoint, worker for the email attachment) |
| `JD_QUESTION_GENERATION_DAILY_LIMIT_PER_USER` | `10` | `docker-compose.yml` → `api` (synchronous request path, no worker involvement per §9.8) |
| `OUTREACH_LINKEDIN_INMAIL_BODY_MAX_CHARS` | `1900` | `docker-compose.yml` → `worker` (draft generation is a worker task) |
| `OUTREACH_LINKEDIN_INMAIL_SUBJECT_MAX_CHARS` | `200` | `docker-compose.yml` → `worker` |
| `OUTREACH_LINKEDIN_CONNECTION_NOTE_MAX_CHARS` | `300` | `docker-compose.yml` → `worker` (forward-provisioned, unused today per §11.9) |

`docker-compose.prod.yml`'s `api`/`worker` blocks already `env_file: - ${API_ENV_FILE:-../.env.production}` / `${WORKER_ENV_FILE:-../.env.production}` (confirmed, lines 25/38), so any of the above that need a production-specific override are set in `backend/.env.production` directly (the file already open in this session's editor context) — **not** hardcoded into the compose YAML itself, consistent with every other production secret/override in this repo.

### 12.3 Queue/worker routing — the one real infra decision this plan makes

Every new background task introduced by Modules A–G is enumerated here with its assigned queue and which physical worker process consumes it, since this is the one area where a wrong default silently drops jobs on the floor (a job enqueued to a queue no running worker listens to just sits in Redis forever with no error surfaced):

| Module | New queue | Priority slot | Consumed by |
|---|---|---|---|
| A | *(none — synchronous, part of the existing scan pipeline)* | — | existing `worker`/`worker-job-matching` |
| B | *(none — synchronous HTTP request/redirect)* | — | `api` |
| C | *(none — synchronous HTTP request)* | — | `api` |
| D | `interview_reminders` (new) | `7` (between `QUEUE_FEEDBACK`'s `7` and `QUEUE_JOB_MATCHING`'s `6` — tie with feedback is fine, both are "user-facing, not urgent-urgent") | **existing** general-purpose `worker` service — per §8.10, explicitly NOT a new dedicated container; add `Queue(QUEUE_INTERVIEW_REMINDERS, connection=connection)` to the explicit Python queue list inside `app/workers/rq_worker.py::main()`'s non-`per_tier` branch, alongside `QUEUE_OUTREACH` |
| E | *(none — synchronous HTTP request, per §9.8)* | — | `api` |
| F | *(none — synchronous HTTP request)* | — | `api` |
| G | *(none — reuses the existing `outreach_generation` queue, just with new parameters)* | unchanged (`6`) | existing `worker`/whichever worker listens to `QUEUE_OUTREACH` today |

**Concrete change for Module D:** add one line to the general-purpose branch of `app/workers/rq_worker.py::main()` — `Queue(QUEUE_INTERVIEW_REMINDERS, connection=connection),  # NEW — Module D` — in the same list that already holds `Queue(QUEUE_OUTREACH, connection=connection)  # NEW — Module 2`, and add `QUEUE_INTERVIEW_REMINDERS` to that function's existing `from app.workers.queue import (...)` import line. No Dockerfile, `docker-compose.yml`, or entrypoint-script change is needed — the queue list lives entirely in this one Python function, confirmed by direct inspection of `Dockerfile.worker` (`CMD ["python", "-m", "app.workers.rq_worker"]`, no queue names baked into the image or compose file at all).

### 12.4 Migration/deploy sequencing in Docker terms

`docker-compose.yml`'s `migrate` service (confirmed at lines 2-13: builds `Dockerfile.api`, runs `run-migrations.sh`, `restart: "no"`, and every other service `depends_on: migrate: condition: service_completed_successfully`) already enforces "migrations run to completion before `api`/`worker` start" — this means **every migration in this plan (`039` through `043`, plus the renumbered `036`-`038`) runs automatically, in order, with zero additional compose wiring**, as long as Step 0 (§2) is merged first so the chain has a single linear head for `run-migrations.sh`'s `alembic upgrade head` to walk. This is worth stating explicitly since it's the reason Step 0 is a hard blocker and not just a nice-to-have cleanup — a divergent-heads database would make `alembic upgrade head` itself fail (ambiguous target), taking down `migrate` and therefore every dependent service on the very first `docker compose up` after these branches merge.

### 12.5 No changes needed to networking, healthchecks, or volumes

- **Networking** (`backend/docker/NETWORKING.md`'s documented tier1-host-network vs. tier2-4-bridge-network split): unaffected. Every new endpoint in this plan is either `api`-served (bridge network, same as every existing API route) or `worker`-consumed via the `interview_reminders` queue (bridge network, same as `QUEUE_JOB_MATCHING`/`QUEUE_OUTREACH` today — no tier1/Multilogin/host-network involvement anywhere in Modules A–G).
- **Healthchecks**: no new services means no new healthcheck blocks needed. The existing `api` and `worker` healthchecks (`curl .../health` and the Redis-ping Python one-liner, respectively) already cover the processes that gain new code paths.
- **Volumes**: no new persistent volumes — every new table lives in the existing `postgres_data` volume (same Postgres instance, no new database), and Module D's `.ics` generation is stateless (built on-the-fly per request, never written to disk).

---

## 13. Consolidated migration chain and build/sequencing order

### 13.1 Full migration chain after this plan lands

```
... -> 032_portfolio_item_image_url
     -> 036_question_attempt_fk_and_personalization   (renumbered from 033, Step 0)
     -> 037_question_recency_index                     (renumbered from 034, Step 0)
     -> 038_practice_audio_recordings_voice_tone        (renumbered from 035, Step 0)
     -> 039_job_match_apply_tracking                    (Module B)
     -> 040_job_match_application_status                (Module C)
     -> 041_interview_schedules                         (Module D)
     -> 042_manual_job_entries                          (Module F)
     -> 043_outreach_message_type                       (Module G)
```

Module A and Module E add **zero** migrations (A only touches `score_breakdown`'s free-form JSON contents and a repository query shape; E persists nothing new to the schema by design, per §9.4). This is why they don't appear in the chain above.

### 13.2 Build/PR sequencing (restates and finalizes §"Sequencing, branch strategy" from the original research, now with this plan's exact module contents)

1. **Step 0** (§2) — migration renumbering. Blocking, first, alone in its own PR.
2. **Settings consolidation** (§4) — can ride along with Step 0's PR (both are pure additions with no behavior change) or be its own tiny PR immediately after. Either is fine; doing them together minimizes PR count for near-zero-risk changes.
3. **Module A** (§5) — smallest, no dependency on anything else in this plan. Do first among the "real feature" modules.
4. **Module B** (§6) — small, no dependency on C. Do second.
5. **Module C** (§7) — depends on B's `applied_at` field existing (§7.5's auto-advance integration). Do third.
6. **Module D** (§8) — depends on C's `application_status` enum (specifically the `"interview"` value) for its auto-advance behavior (§8.3's router docstring). Do fourth.
7. **Module G** (§11) — independent of C/D/F; can run in parallel with D once B is in (G has no hard dependency on B either, actually — G only touches `outreach_messages`, entirely orthogonal to `job_matches`). Reorder note versus the original research's sequencing: G can move earlier than F since it has zero dependency on F's schema changes, whereas F's join-widening work (§10.6) is safer to land after the tracker (C) has stabilized in production, so that any join-site regression F might introduce is caught against a smaller, already-tested set of tracker behaviors rather than compounding with a still-fresh Module C.
8. **Module E** (§9) — depends on C existing (needs a tracked job + its JD to link "practice for this interview" from, per §9.4's `job_match_id` requirement) and touches `question_generator.py` from the base `phase2-module3-interview-prep` branch directly. Should land after C, can be parallel with D/G.
9. **Module F** (§10) — **last**, deliberately. Its join-widening change (§10.6) touches code from A (none, actually — A doesn't join `JobPosting` by identity, just filters), B (no join changes needed there), C (does need updating — the tracker's join is exactly what F extends), D (no join changes needed — `interview_schedules` FKs to `job_matches.id` directly, doesn't care whether that match is manual or scanned), and E (needs the explicit manual-entry rejection check from §10.6's last bullet). Landing F last, after every other module's join sites are stable and well-tested, minimizes the blast radius of the one change in this whole plan explicitly flagged as medium-risk (§10.9).

### 13.3 One-time cross-module integration checklist (do not lose track of these — they are easy to forget since each lives in a different module's PR)

- [ ] Module B's `mark-applied` auto-advances `application_status` `new → applied` only (§7.5) — **implemented in Module C's PR** if B ships first (the hook has to be added to B's already-merged `set_applied` method), or in B's own PR if C's schema already exists by the time B is written. Whichever PR lands second between B and C must include this hook — track it explicitly rather than assuming the other module's author remembers.
- [ ] Module D's `schedule_interview` auto-advances `application_status` to `"interview"` (forward-fill-only, §8.3) — implemented in Module D's PR, requires Module C's `application_status` column to already exist (hard dependency, already sequenced correctly above).
- [ ] Module E's `get_jd_tailored_questions` must reject manual-entry `job_match_id`s explicitly (§10.6, last bullet) — this is a Module F concern that has to be retrofitted into Module E's already-merged code, since Module E ships before Module F per §13.2's ordering. **Track this as a required follow-up task the moment Module F's PR opens, do not let it be forgotten because it's a one-line guard in someone else's already-closed module.**
- [ ] Module G's `edit_draft` LinkedIn-length re-validation (§11.6's edge-case note) must be added even though it touches the pre-existing `outreach/router.py:38`/`OutreachService.edit_draft` code path that predates this entire plan — easy to miss because the natural instinct is "Module G only touches generation," but the manual-edit endpoint is an equally real way to end up with an over-length LinkedIn message.
- [ ] Module F's join-widening (§10.6) touches: `job_matching/repository.py` (2 functions), `job_swipe/repository.py` (1 query), `application_tracker/repository.py` (1 query, Module C), `workers/tasks/outreach.py` (1 function). **All four files must be touched in Module F's single PR** — do not split this across multiple PRs, since a partially-applied nullable-FK migration with only some join sites updated is a state where the other, un-updated sites will throw `AttributeError`s on the first manually-added job any user creates.

---

## 14. What this plan deliberately does not build (explicit non-goals, stated so they aren't silently assumed later)

- **Full Google Calendar OAuth two-way sync** (Module D) — v2, only if users ask for it after the `.ics`/link tier ships (§8.1).
- **Drag-and-drop Kanban board** (Module C) — v2; the filterable list is the committed MVP (§7.6).
- **Automated LinkedIn/DM sending** (Module G) — not just deferred, actually impossible via any public API; the UI must say so explicitly (§11.7), not imply it's coming later.
- **SMS notifications** (pre-existing gap, not introduced by this plan) — `notify_sms_enabled` and `"sms" in notification_channels` are already accepted-but-no-op today (confirmed: `workers/tasks/job_matching.py::_send_match_digest_async`'s existing log-and-skip behavior); nothing in Modules A–G changes this, and Module D's interview reminders follow the same email+push-only pattern, not SMS.
- **Real outbound email-sending-as-the-candidate infrastructure** (Module G, and pre-existing for Module 2's original outreach feature) — explicitly out of scope, per `outreach/service.py::send_message`'s own existing docstring (quoted in §11.6), which this plan does not change.
- **A general-purpose "paste any JD" practice tool** (Module E) — deliberately scoped to `job_match_id`-linked JDs only (§9.4's schema note), not an arbitrary-JD-paste feature, to keep the practice flow anchored to a job the candidate is actually tracking.
- **Editing or deleting a manual job entry** (Module F) — v1 only supports *creating* one (§10's schemas only define `CreateManualJobEntryRequest`); a typo in a manually-typed title/company has no fix-it path other than the tracker's existing status controls (the row itself can't be edited or removed). This mirrors the pre-existing product today, where a scanned `JobMatch` also has no delete endpoint anywhere in the codebase — Module F is consistent with that existing constraint rather than introducing a new asymmetry, but it's called out explicitly here since "add a job" without "fix a typo in the job I just added" is a real, likely-to-be-hit rough edge a candidate will notice immediately. Flagged as the first candidate for a v1.1 follow-up (`PATCH`/`DELETE /api/manual-jobs/{id}`), not built now to keep this plan's scope matched to what was actually asked for.
- **Multi-round interview tracking** (Module D) — v1 is one `InterviewSchedule` row per `JobMatch` (enforced by a UNIQUE constraint, §8.2), representing "the interview," not a sequence of phone-screen/onsite/offer rounds. Rescheduling reuses the same row; a second, distinct round is out of scope. Noted as a real, common need (most interview loops have 2+ rounds) but deliberately deferred rather than building a "rounds" data model and UI nobody asked for in this plan.
- **Account-level GDPR/DSAR export or deletion covering Phase 2's candidate-account data** (all of Modules A–G, plus everything already in `job_matching`/`outreach`/`sessions`/`practice_audio` today) — this is a **pre-existing gap that predates this plan, not one introduced by it**: `backend/app/compliance/dsar.py`/`purge.py` are scoped entirely to *identifier*-based enrichment lookups (`JobRecord`/`PhotoCacheRecord`, the original Module 1 product surface — "purge everything associated with this email/LinkedIn handle"), not to *account*-based candidate data (job matches, tracked applications, interview schedules, outreach drafts, practice sessions). None of Modules A–G make this gap worse (the 5 new/changed tables in this plan — `job_matches`' new columns, `interview_schedules`, `manual_job_entries`, `outreach_messages`' new columns — are exactly as uncovered by account-level DSAR as every pre-existing Phase 2 table already is), but they also don't fix it. If/when account-level "export or delete all my data" is built for the candidate-facing product, this plan's new tables need to be added to that future work's scope — recorded here so it isn't lost.

---

## 15. Self-review addendum — concurrency, security, accessibility, and UI-state coverage

This section closes gaps found in a deliberate critical pass over §§1–14 above, done in response to a direct question about edge-case, placeholder, and UI completeness. Each item below is either a fix already applied inline above (cross-referenced) or a decision recorded here because it didn't have a natural home in any single module's section.

### 15.1 Concurrency / idempotency, module by module

- **Module A:** the strict pass and the relaxed pass are two separate DB round-trips per scan; under concurrent scans for the same user (shouldn't normally happen — scans are per-candidate and the existing fan-out staggers them — but not physically prevented), both could run `upsert_match` for overlapping postings. `upsert_match` is already an upsert (confirmed pre-existing behavior, not changed by Module A), so this is safe by construction — called out here only because the fallback pass doubles the number of round-trips where this matters, not because it introduces a new race.
- **Module B:** `record_apply_click` (increments a click count/timestamp) and `set_applied` are both single-row `UPDATE`s, not read-modify-write in application code — a double-click on "Apply" before the UI disables the button results in two clean, idempotent `UPDATE`s, not a lost update.
- **Module C:** `update_status` (§7.4) is a single `UPDATE ... WHERE ... RETURNING`, not read-then-write — already covers the double-submit race explicitly (see the docstring added at §7.4).
- **Module D:** `upsert_schedule` (§8.2) is read-then-write, not atomic — a genuine (if narrow) TOCTOU window exists between the `get_schedule_for_match` read and the `INSERT`/`UPDATE` if the exact same candidate double-submits the schedule dialog from two tabs simultaneously. Accepted risk, not fixed with a DB-level `ON CONFLICT` upsert: the two-step form is portable across SQLite/Postgres and the failure mode of losing this narrow race is "the second submission's time wins, exactly like a real double-submit would resolve on any form with a debounced submit button" — not data corruption, just last-write-wins, which is the correct outcome for "what time did you actually decide on" anyway.
- **Module E:** the daily-generation-count guard (`_jd_generation_count_today`, §9.4) is read-then-compare, not atomic — a candidate opening two practice tabs and submitting simultaneously could exceed the daily limit by one request. Accepted: this is a cost-control soft limit, not a security boundary, and the existing Module 3 personalized-generation limit (which this mirrors) has the same property.
- **Module F:** `create_manual_entry` (§10's `service.py`) wraps both inserts (the `ManualJobEntry` and its companion `JobMatch`) in one transaction/flush-then-commit, so a mid-request failure can never leave an orphaned entry with no tracker row (already documented inline, restated here for the audit trail).
- **Module G:** the Redis lock key now includes `message_type` (§11.6) specifically so two different-type draft requests for the same company don't get its own new race — the pre-existing per-company lock behavior for same-type requests is unchanged.

### 15.2 Security hardening added in this pass

- **Open-redirect / scheme validation on Module B's apply-redirect** (§6.5's `_validate_redirect_scheme`) — the single most important addition from this review pass. `source_url` is scraped, third-party, unsanitized data; redirecting a browser to it without a scheme allowlist was the one real injection-adjacent gap in the original draft.
- **LinkedIn character-limit re-validation on manual edits** (§11.6's edge-case note) — closes the gap where the LLM-generation-time truncation backstop (§11.5) had no equivalent for the pre-existing hand-edit endpoint.
- Every new endpoint across Modules B–G reuses `CurrentUser`/`VerifiedUser` + ownership-scoped queries (`user_id ==` filters baked into every repository function introduced above) — no new endpoint in this plan trusts a client-supplied `user_id`; ownership is always derived from the authenticated session and enforced in the `WHERE` clause, not checked after the fact in application code. This is a restatement of the existing convention (§3), confirmed to hold for every new query added in this document during this review pass.
- Rate limiting: no new endpoint in this plan needs a *bespoke* rate limit beyond what's already noted per-module (Module E's daily JD-generation cap, §4; Module A/B/C/D/F/G's endpoints are all low-cost CRUD/redirect operations already covered by whatever global per-user rate limiting the API gateway/middleware layer applies today — this plan does not change or need to change that global policy).

### 15.3 Observability parity across modules (gap found and closed)

§3's cross-cutting convention states "every module gets its own metrics file," but the original draft of this plan only added Prometheus metrics for Modules A and B (§5.3, §6.5). Closed here — one counter per module, following the exact `Counter`/no-op-fallback-if-`prometheus_client`-missing pattern already used in `job_matching_metrics.py`:

| Module | New metric | File |
|---|---|---|
| C | `application_tracker_status_updates_total` (plain `Counter`, incremented once per successful `PATCH .../status`) | `app/observability/application_tracker_metrics.py` (new file) |
| D | `interview_schedules_created_total`, `interview_reminders_sent_total` | `app/observability/interview_scheduling_metrics.py` (new file) |
| E | `jd_practice_questions_generated_total`, `jd_practice_daily_limit_hit_total` (the latter incremented when the §9.4 rate-limit guard actually rejects a request — the same "log intent so the limit can be tuned later" rationale as Module A's fallback counter) | `app/observability/jd_practice_metrics.py` (new file) |
| F | `manual_job_entries_created_total` | `app/observability/manual_jobs_metrics.py` (new file) |
| G | `outreach_drafts_by_type_total` (labeled `Counter` with a `message_type` label — the one metric in this table that needs a label, since "how many LinkedIn vs. email drafts" is the actual product question this metric answers) | added to the existing `app/observability/outreach_metrics.py` if that file already exists on `phase2-module3-interview-prep`/`master-complete-foundation`, else created new |

### 15.4 Accessibility checklist (applies to every new interactive element across Modules A–G)

- Every icon-only button introduced by this plan (Module B's inline "mark as applied" checkbox icon, Module G's "Copy to clipboard" button, Module D's calendar-add icons) gets an explicit `aria-label` — following the exact pattern already used by `MatchCard.tsx`'s existing icon buttons (confirmed convention, not a new one invented for this plan).
- `ScheduleInterviewDialog`, `AddManualJobDialog` (both net-new modal dialogs) use the existing shadcn `Dialog` primitive, which already provides focus-trap, `Escape`-to-close, and `aria-modal` semantics for free — no bespoke accessibility work needed as long as neither dialog is rebuilt from a bare `<div>` instead of the shared primitive.
- `TrackerFilterBar`'s status filter and sort `Select` controls need visible focus rings and keyboard operability — inherited for free from the shared shadcn `Select` primitive, called out only to confirm no custom-styled override in this plan's components suppresses the default focus ring (a real, easy-to-introduce regression when adding custom Tailwind classes to a shadcn primitive).
- `TrackedMatchRow`'s status `Select`/dropdown must announce the status change to screen readers (shadcn's `Select` already does this via its underlying Radix primitive's `aria-live` behavior) — no additional work needed, confirmed here rather than left unverified.

### 15.5 Loading / error / empty state matrix for every new frontend view

Every new `useQuery`-backed view below must render all three states explicitly — listed here as a single checklist so none is silently skipped during implementation, mirroring the existing `MatchesView.tsx`'s already-established loading/error/empty pattern (skeleton rows / inline error banner with retry / centered empty-state illustration+CTA, respectively):

| View | Loading | Error | Empty |
|---|---|---|---|
| `TrackerView` (Module C) | Skeleton rows (reuse `MatchCard`'s existing skeleton, if any, or a generic row skeleton) | Inline error banner + "Retry" button (re-triggers `useTrackedMatches`) | "No applications tracked yet — swipe or browse matches to start tracking" + CTA linking to `/app/matches` |
| `TrackerView` filtered to one status with zero results | N/A (this is a distinct empty state from "no data at all") | N/A | "No applications with status '{status}' yet" — distinct copy from the all-statuses empty state above, since an empty *filtered* view reads very differently to a user than a genuinely empty tracker |
| `InterviewScheduleCard` (Module D) | Skeleton while `useInterviewSchedule` loads | Inline error, no retry needed (low-stakes GET, page refresh is an adequate fallback) | Renders the "Schedule interview" CTA button instead of the card itself when `useInterviewSchedule` resolves to `null` (this is the expected common case, not an error) |
| `JdPracticeSessionView` (Module E) | Loading spinner while questions generate (this is a synchronous request, §9.8 — no polling needed, but the wait is a few seconds of real LLM latency and must show a spinner/skeleton, not a blank screen) | Distinct error copy for the rate-limit case (`429`/`RateLimitError` — "You've hit today's practice question limit, try again tomorrow") vs. a generic failure (network/LLM error — "Couldn't generate questions, please try again") | N/A (a successful response always has ≥1 question; the daily-limit-exhausted case is the error state above, not an empty state) |
| `AddManualJobDialog` (Module F) | Submit button shows a spinner + disables while the mutation is in flight (prevents the double-submit case noted in §15.1) | Inline form-level error (e.g. "Title and company are required") | N/A (a dialog, not a list view) |
| `OutreachDraftCard` message-type selector (Module G) | N/A (selector itself has no async state) | Draft-generation failure shows the existing outreach error pattern, unchanged by Module G | N/A |

### 15.6 Mobile navigation (verified, no change needed)

Module C's `nav-config.ts` addition (§7.6) is automatically picked up by both `AppSidebar` (desktop) and `AppBottomNav` (mobile, confirmed by direct inspection of `frontend/components/layout/AppBottomNav.tsx`) — the mobile bottom nav imports `mainNav`/`systemNav` from the exact same `nav-config.ts` module the desktop sidebar does, so a single edit to that one file covers both surfaces. No separate mobile-specific navigation change is needed anywhere in this plan, confirmed rather than assumed.
