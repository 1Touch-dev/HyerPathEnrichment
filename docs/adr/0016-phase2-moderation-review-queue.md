# 0016. Generic Review Queue + Per-Domain Moderation Columns (Phase 2 Moderation)

- **Status:** Accepted
- **Date:** 2026-08-20

## Context
Phase 2's moderation layer needs to flag and let admins act on problematic
content across four different domains — job postings, candidate documents,
portfolio profiles, and outreach messages — plus (per the plan) two more
Module 3 resource types (`question`, `practice_audio`) once that module
lands. None of these domains had any moderation surface before this batch
(`docs/admin-module-phase2-tracking-research.md`'s Ground truth section):
no moderation columns, no admin escape hatch, and in documents' and
portfolio's case, the existing read/delete paths (`delete_document()`,
`get_public_profile()`) had no concept of a moderation state to check at
all. The design question is where the *triage/queue* concern lives versus
where the *per-request moderation-state check* concern lives — putting both
in the same place doesn't scale cleanly across five-plus resource types.

## Decision
We chose a **hybrid**: one generic, polymorphic review-queue table for
triage, plus small, domain-owned moderation columns for state — over either
a single fully-generic system with no domain columns, or fully bespoke
per-domain moderation tables with no shared queue.

1. **Generic `admin_review_queue` table** (`alembic/versions/039_admin_review_queue.py`,
   `AdminReviewQueueItem` in `backend/app/modules/admin/models.py`) is the
   single triage surface: one row per flagged item, keyed by a polymorphic
   `resource_type`/`resource_id` pair, with `status`/`flag_reason`/
   `flag_source`/`reviewed_by`/`reviewed_at`/`review_notes`. This is what
   gives the admin UI one unified list/detail/decide flow
   (`review_queue_router.py`) across every resource type, rather than a
   separate queue screen per domain — the same Stripe-Radar-style shape
   already validated in `docs/admin-module-research.md` §4, generalized
   from CVs to all five-plus resource types
   (`docs/admin-module-phase2-tracking-research.md` §2).
2. **Per-domain moderation columns own domain state**: `job_postings` gets
   `moderation_status`/`moderated_by`/`moderated_at`; `candidate_documents`
   gets `deleted_at`; `portfolio_profiles` gets `admin_hidden`;
   `outreach_messages` gets `admin_blocked` (all added in
   `alembic/versions/040_phase2_moderation_columns.py`). Each domain's own
   read paths check their own column with a plain column read/filter —
   `PortfolioProfile.admin_hidden` is checked directly inside
   `get_public_profile()` (`backend/app/modules/portfolio/service.py:107-111`,
   `if not profile or not profile.is_published or profile.admin_hidden: raise
   HTTPException(...)`), and `JobPosting.moderation_status` is filterable
   directly in the admin job-postings list (`job_postings_router.py`'s
   `list_job_postings`), with no join or lookup into `admin_review_queue`
   required on either path. This is the deliberate reason the columns exist
   on the domain tables at all, rather than the review queue being the only
   source of moderation truth: the portfolio public route and a future
   candidate-facing document list are both hot, frequently-hit read paths
   where a join out to a separate generic table on every request would be
   the wrong tradeoff for a state check that's true for the overwhelming
   majority of rows (not moderated) and cheap to represent as one boolean or
   enum column.
3. **The review queue and the domain columns are reconciled at decide-time,
   not at read-time.** `review_queue_router.py`'s `decide_review_queue_item()`
   is the only place that writes to both: on `rejected`, it flips the
   corresponding domain column via `_flip_domain_column()` (raw `sa.table()`
   updates, not the domain ORM models — see Decision 4) in the same
   transaction as the queue row's own `status`/`reviewed_by`/`reviewed_at`
   update. Reads never need to consult both tables at once; only the single
   decide action does.
4. **Domain updates use raw `sa.table()` constructs, not the domain ORM
   models**, because `review_queue_router.py` was built concurrently with
   sibling in-flight chunks editing `job_matching/documents/portfolio/
   outreach` `models.py` in separate worktrees and could not safely import
   those models without a merge-order dependency. `_RESOURCE_TABLES` (for
   read-side resource resolution) and the `_flip_domain_column()` branches
   (for the write-side decision flip) are both hand-maintained maps from
   `resource_type` to table/column names, deliberately decoupled from the
   ORM. This is the same "table object, not ORM model" pattern this repo's
   own migrations already use (`alembic/versions/038_admin_seed_roles_permissions.py`),
   so it required no new pattern, just applying an existing one to
   application code instead of a migration.
5. **Automated flagging is fail-open by construction, never blocking the
   underlying user action.** `moderation_flagging.py`'s `flag_if_needed()`
   only ever *adds a row* to `admin_review_queue`; it never returns an error
   that could fail a caller's own create/update, and both the heuristic
   check and the LLM-judge call (`run_llm_judge()`) are wrapped so that any
   failure — missing API key, network/timeout, non-2xx, malformed JSON —
   degrades to "not flagged" rather than raising. This is a deliberate
   architectural choice, not an oversight: per the cascade-moderation
   research in `docs/admin-module-phase2-tracking-research.md` §3, a
   moderation classifier that can block the action it's supposed to be
   screening turns a content-safety feature into an availability
   dependency for the entire write path it's attached to. Because this plan
   only builds *flagging into a queue*, never *automated removal or
   blocking*, the fail-open choice has no safety downside symmetric to the
   one those sources describe for automated *enforcement* pipelines — the
   worst case of a fully-degraded flagging cascade is that nothing gets
   flagged, which is the same as never having built it, not a new harm.

## Tradeoffs

- The hybrid (Decisions 1-2) means moderation state is not queryable from
  one single table — an admin dashboard wanting "everything currently
  hidden or removed across all domains" must query the review queue for
  history/attribution and each domain table for current state, **traded
  for** every domain's own hot read path staying a plain column check with
  no join, and one shared UI for triage instead of five bespoke ones.
- Raw `sa.table()` domain writes (Decision 4) mean the review-queue router's
  column-name maps (`_RESOURCE_TABLES`, `_flip_domain_column`'s branches)
  are not type-checked against the real ORM models and must be
  hand-updated if a domain's schema changes, **traded for** not having a
  merge-order dependency on four concurrently-edited sibling worktrees'
  `models.py` files landing first.
- Fail-open flagging (Decision 5) means a degraded or misconfigured LLM
  judge silently produces fewer flags rather than surfacing an error,
  **traded for** guaranteeing the moderation layer can never be the reason
  a legitimate job-posting scrape, document upload, portfolio edit, or
  outreach send fails.

## Consequences

- **Easy:** the admin UI gets one unified review-queue list/detail/decide
  screen across every current and future moderated resource type; adding a
  sixth or seventh moderated domain later is "add one `resource_type`
  string, one domain column (or reuse an existing boolean/enum shape), and
  one `_flip_domain_column()` branch" — not a new table, migration set, or
  UI screen.
- **Watch:** the review-queue router's `_RESOURCE_TABLES` map and
  `_flip_domain_column()`'s branches are the one place in this plan that
  duplicates schema knowledge outside the ORM — any future migration that
  renames or removes one of these domain columns (`moderation_status`,
  `deleted_at`, `admin_hidden`, `admin_blocked`) must update this file too,
  or the review queue will silently stop flipping the right column (it logs
  a warning for unrecognized `resource_type`s, but not for a stale column
  name inside a recognized one).
- **Watch:** `question` and `practice_audio` (`_MODULE_3_PLACEHOLDER_TYPES`)
  already exist as valid `resource_type` values in this schema and code
  before any real Module 3 table backs them on this branch — resolution and
  the decide-time flip are both deliberate no-ops for these two today. A
  future Module 3 implementation must add both a real domain column and a
  real `_flip_domain_column()`/`_RESOURCE_TABLES` branch for them, or
  flagged Module 3 content will sit in the queue with rejections that never
  actually take effect on the underlying resource.
- No new Docker service, container, or queue was added — flagging runs
  inside existing worker task paths and the review queue is plain
  request/response against Postgres, consistent with `docs/adr/0015`
  Decision 8's "don't add a new failure mode to the queue/DB layer for an
  admin feature" principle.

## Alternatives considered

- **Single fully-generic moderation system, no domain columns** (e.g. every
  domain's read path joins out to `admin_review_queue`, or checks a
  polymorphic `moderation_state` table keyed by `resource_type`/
  `resource_id`): rejected — turns every hot read path (portfolio's public
  route, a future candidate document list) into a join or an extra query
  for a state that's false for the overwhelming majority of rows; also
  couples an unrelated domain's request-time behavior to the schema and
  query plan of a shared cross-domain table.
- **Fully bespoke per-domain moderation tables, no shared queue** (e.g. a
  `job_posting_moderation_queue`, `document_moderation_queue`, etc., each
  with its own list/detail/decide endpoints): rejected — duplicates the
  same list/filter/cursor-pagination/decide logic five times over, and
  gives the admin UI five separate screens to build and maintain instead of
  one, for a triage workflow that is structurally identical across domains
  (per the Stripe Radar precedent, `docs/admin-module-phase2-tracking-research.md`
  §2).
- **Hash-chained/append-only audit ledger for moderation decisions**:
  rejected as premature for current scale — `docs/admin-module-phase2-tracking-research.md`
  §5 found this pattern is consistently framed around SOC 2/HIPAA
  compliance evidence and multi-tenant or hostile-insider threat models
  this repo does not currently have; the existing single `AdminAuditLog`
  table (`docs/adr/0015`) already captures actor/action/before/after for
  every review-queue decision and is proportionate to this repo's actual
  bar (an internal, attributable admin trail), not a third-party-auditable
  one.
- **Synchronous/blocking moderation checks** (flagging call must succeed,
  or block, before the triggering create/update completes): rejected per
  the fail-open principle (Decision 5) — would make the moderation layer's
  own availability a hard dependency of the job-scrape, document-upload,
  portfolio-edit, and outreach-send paths it's meant to be screening, for a
  feature whose entire job in this plan is flagging into a queue, not
  gating the action itself.
