# Post-Tenancy Retrofit, Chunk 2 — Outreach, Documents, Portfolio Tenant Scoping

## Depends on

`machine-1-tenancy-core` fully merged. Parallel-safe with `01` and `03` (disjoint modules).

## Goal

Same retrofit pattern as `01-job-matching-and-swipe-tenant-scoping.md` (optional `org_id`
parameter, no-op for `org_id=None`, real filter otherwise), applied to:

- `backend/app/modules/outreach/` — `OutreachMessage` rows.
- `backend/app/modules/documents/` — `CandidateDocument`, `DocumentJob`, `CvChatSession`,
  `CvChatMessage`, `CvFeedbackReport` rows.
- `backend/app/modules/portfolio/` — `PortfolioProfile`, `PortfolioItem` rows.

Read `01`'s file first if implementing both — it defines the shared retrofit pattern in more
detail; this file only calls out what's specific to these three modules.

## Files to edit

- `backend/app/modules/outreach/models.py`, `repository.py`, `service.py`, `router.py`
- `backend/app/modules/documents/models.py`, and whichever repository/service files exist for
  documents (check current file list — `cv_chat_service.py` was read earlier in this effort;
  there may be a separate `documents_service.py`/`repository.py` — verify before assuming a
  single service file covers all of `CandidateDocument`/`DocumentJob`/CV chat)
- `backend/app/modules/portfolio/models.py`, `repository.py`, `service.py`, `router.py`
- New migration adding `org_id` to: `outreach_messages`, `candidate_documents`, `document_jobs`,
  `cv_chat_sessions`, `cv_feedback_reports`, `portfolio_profiles`, `portfolio_items`.

## Portfolio-specific note: public slugs must stay public

`backend/app/modules/portfolio/repository.py`'s `get_profile_by_slug(db, slug)`
(lines 18-20) backs the **public**, unauthenticated portfolio page (candidate-facing public URL,
also the basis for `frontend/src/lib/subdomain.ts`'s subdomain rewrite). **Do not add an
`org_id` filter to `get_profile_by_slug`** — a portfolio's public page must remain visible to
anyone with the link/subdomain regardless of which org (if any) owns the underlying candidate;
tenant scoping is about *recruiters managing candidate data*, not about *gatekeeping a
candidate's own public-facing portfolio page*. Only `get_profile_by_user_id` (line 13-15) and any
recruiter-facing management/list endpoints get the `org_id` filter.

## Outreach-specific note: interaction with `05`/`06`'s new columns

If `machine-2-parallel-tracks/03,05,06` have already merged by the time this chunk starts (check
`backend/app/modules/outreach/models.py`'s actual current columns before writing the migration),
`OutreachMessage` will already have `strategy`, `referral_context`, `recipient_email`,
`suppression_checked_at`, and possibly `recipient_linkedin_url` columns from those tracks. This
chunk only adds `org_id` — it does not touch, rename, or reinterpret any of those columns.
`LinkedInSendTask` (from `06`, if merged) is keyed by `outreach_message_id`, not directly by
`user_id` — decide whether it needs its own `org_id` column or can be scoped transitively via a
join to its parent `OutreachMessage.org_id`; a join-based transitive scope is preferred over a
duplicate column if the query pattern allows it cleanly, to avoid two columns that could drift
out of sync.

## Documents-specific note: CV chat cascades

`CvChatSession`/`CvChatMessage` are keyed by `user_id` (`CvChatSession`) and `session_id`
(`CvChatMessage`, transitively by `user_id`). Scope `CvChatSession` directly with `org_id`;
`CvChatMessage` does not need its own `org_id` column — access control is enforced at the
session level (`_get_owned_session` in `cv_chat_service.py`, lines 273-284) and messages are only
ever reached through an already-org-checked session, so a redundant column there would be dead
weight, not a security improvement.

## Do not touch

- `backend/app/modules/job_matching/`, `backend/app/modules/job_swipe/`,
  `backend/app/modules/admin/` — owned by `01` and `03`.
- `backend/app/clients/perplexity.py`, `backend/app/workers/tasks/outreach.py`'s LLM-drafting
  logic — unaffected; this chunk only retrofits access-control filters, not drafting behavior.
  (If `org_id` needs to be threaded through the RQ job so the created `OutreachMessage` row gets
  the right `org_id` at creation time, that plumbing change to
  `request_draft`'s enqueue args and the job function's signature is in scope — but nothing else
  in that file is.)
- `backend/app/modules/documents/cv_chat_service.py`'s LLM tool-calling logic
  (`_call_llm_with_tool`) — unaffected.

## Verification

Same two-org isolation test shape as `01`:

- Two orgs' recruiters cannot read/edit/send each other's `OutreachMessage` rows, including via
  direct `message_id` lookup.
- Two orgs' recruiters cannot read each other's `CandidateDocument`/CV-chat data.
- Two orgs' recruiters cannot see each other's private portfolio-management views, but a
  portfolio's public slug page (`get_profile_by_slug`) remains reachable by anyone regardless of
  org — add an explicit test asserting this stays true (a "portfolio not found because wrong
  org" regression here would be a real product bug, not a security fix).
- Regression: `org_id = None` callers keep unfiltered access to their own data across all three
  modules.
