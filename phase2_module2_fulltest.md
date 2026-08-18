# Module 2 — Full Test Plan: Tinder-Style Job Board + CV Management

**Status of this document:** executable test plan / runbook, written against the actual code on branch `feat/phase2-module2-job-board-cv` as of 2026-08-14. It is a companion to [`phase2_module2.md`](phase2_module2.md) (the original 17-section implementation blueprint) — read that document for design rationale ("Decision 1" through "Decision 7", the RULE.md compliance checklist, etc.). This document does not re-derive that rationale; it verifies the *result*.

Every claim below was checked against the real files in this repo during this session (code reads, `grep`, and — where noted — actually running the backend test suite, the frontend test suite, and `next build`/`next lint`). Where a number is cited (test counts, coverage %), it was captured from a real run on this branch, not estimated.

---

## 1. Overview

Module 2 adds four candidate-facing features on top of Module 1 (AI Job Matching) and the Foundation Week 1/2 document/interview infrastructure:

1. **CV completeness chat** — a turn-based (non-streamed) chatbot that asks the candidate about whichever `CVData` fields `app/domain/cv_completeness.py` says are missing, and writes validated answers back onto `CandidateDocument.extracted_data` via an OpenAI strict-mode function-calling tool (`record_cv_answer`).
2. **CV improvement / feedback** — an async (RQ-worker) GPT-4o-mini call that reviews the candidate's raw CV text and returns an ATS score, strengths/improvements, and a small set of rewritten bullets, gated by an explicit "accept" action per bullet (nothing auto-applies to the stored CV).
3. **Candidate portfolio pages** — a per-candidate public page (`/p/{slug}`) listing projects/links (`portfolio_items`), backed by `portfolio_profiles`/`portfolio_items` tables and a slug validated against the RFC 1035 label charset.
4. **Tinder-style job swipe deck + personalized outreach** — a swipe UI over Module 1's `job_matches` (right/left/up, with undo), and an AI-drafted (Perplexity company research + OpenAI drafting), CAN-SPAM-disclosure-appended outreach message workflow gated by a per-company Redis idempotency lock.

This document exists so that a human or an agent can, top-to-bottom, **concretely verify Module 2 is complete and working end-to-end** — smoke tests first (is anything obviously broken), then unit tests (is each piece of logic proven in isolation, including the two post-build hardening/gap-closure rounds this branch went through), then integration tests (do the real cross-layer flows work against a running stack), then the full-suite + coverage gate, then a final honest acceptance checklist.

**What this document is not:** it does not re-litigate `phase2_module2.md`'s design decisions, and it does not cover Module 1 (AI Job Matching) except where Module 2 reads Module 1's tables read-only (job swipe, outreach).

---

## 2. Prerequisites

### 2.1 Environment variables

Module 2's env vars, confirmed against the actual `backend/.env.example` (search for "Module 2: Tinder-Style Job Board + CV Management", near the end of the file) and `backend/app/core/config.py`:

| Variable | Example / default | Used by |
|---|---|---|
| `PORTFOLIO_PUBLIC_BASE_URL` | `https://app.hyrepath.example/p` | `portfolio/service.py` — builds each profile's `public_url` |
| `CV_CHAT_MAX_TURNS` | `12` (default `12` in code even if unset) | `cv_chat_service.py` — hard cap on chatbot turns per session |
| `CV_FEEDBACK_MODEL` | `gpt-4o-mini` (default `gpt-4o-mini` in code) | `feedback_generator.generate_cv_improvement()` |
| `PERPLEXITY_API_KEY` | `pplx-...` | `clients/perplexity.py` — empty string disables Perplexity, feature fails soft |
| `PERPLEXITY_API_BASE` | `https://api.perplexity.ai` (default in code) | `clients/perplexity.py` |
| `OUTREACH_ENABLED` | `true` (default `True` in code) | `outreach/service.py.request_draft()` — 403 if `false` |
| `APP_PUBLIC_BASE_URL` | `https://app.hyrepath.example` | `outreach/service.py._privacy_policy_url()` — absolute link in the disclosure footer |

Also required (pre-existing, not Module-2-specific, but needed for the LLM-backed pieces to do more than fail-soft): `OPENAI_API_KEY`. Without it, `cv_chat_service.py._call_llm_with_tool()` returns `None` (chat re-prompts instead of recording an answer) and `generate_cv_improvement()` raises `ValueError` (caught by the worker task, which marks the job `failed`) — both are legitimate, testable degrade paths, not bugs.

**Known gap:** the original plan (`phase2_module2.md` §7) also lists `OUTREACH_SENDER_EMAIL` as a new env var. The real `.env.example` and `config.py` do not define it — `outreach/router.py`'s `send_message` call uses `current_user.email` as the sender address instead. This is a deliberate deviation, not a missing env var; do not add `OUTREACH_SENDER_EMAIL` expecting it to do anything.

### 2.2 Backend: migrations, API, worker

```bash
cd backend

# 1. Apply migrations. Module 2's tables live in 025_cv_chat_sessions through
#    030_outreach_messages, plus 032_portfolio_item_image_url (the image_url
#    column added during the hardening round). Confirmed single head:
alembic upgrade head
alembic heads   # expect exactly one line: "032_portfolio_item_image_url (head)"

# 2. Start the API (dev)
uvicorn app.main:app --reload --port 8000

# 3. Start a worker that can service QUEUE_OUTREACH and QUEUE_FEEDBACK
#    (both already included in the generic worker's fixed-priority queue list —
#    see app/workers/rq_worker.py; no new worker container needed, §10 of the plan):
python -m app.workers.rq_worker
```

Requires Redis reachable at `REDIS_URL` (RQ queues) and a database reachable at `DATABASE_URL` (SQLite for local dev is fine; Postgres for anything exercising the pgvector-based similarity-boost path in job-swipe — see §5.3 below).

### 2.3 Frontend

```bash
cd frontend
npm install     # if not already done
npm run dev      # http://localhost:3000
```

The frontend talks to the backend through Next.js BFF routes under `frontend/app/api/*` (e.g. `app/api/matches/swipe-deck/route.ts`, `app/api/outreach/drafts/route.ts`) which forward to the FastAPI backend — point `BACKEND_API_URL` (or whatever the repo's existing BFF convention env var is) at the running backend from §2.2.

---

## 3. Smoke tests

Fastest possible "is anything obviously broken" pass. Expected total time: a few minutes.

### 3.1 Backend smoke tests

```bash
cd backend

# Migration applies cleanly, single head
alembic upgrade head
alembic heads                      # exactly one head line

# Backend imports/starts without error
python -c "from app.main import app; print('OK', len(app.routes), 'routes')"

# Each of the 4 feature routers is mounted and returns non-500 on an
# unauthenticated request to its base route (expect 401/403, not 500).
# current_verified_user raises 401 with no session cookie at all (confirmed
# in app/auth/dependencies.py); 403 only applies to an authenticated-but-
# unverified user, which these curl calls (no cookie) will never hit.
uvicorn app.main:app --port 8000 &
sleep 2
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/documents/00000000-0000-0000-0000-000000000000/completeness   # expect 401
curl -s -o /dev/null -w "%{http_code}\n" -X PUT http://localhost:8000/api/portfolio/profile -d '{}' -H 'Content-Type: application/json'  # expect 401
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/matches/swipe-deck   # expect 401
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/api/outreach/drafts -d '{}' -H 'Content-Type: application/json'  # expect 401 (422 also acceptable — body validation may run before auth depending on FastAPI dependency order; anything in {401,403,422} is fine, 500 is not)
# The one deliberately-unauthenticated route should return 200 or 404, never 401/500:
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/portfolio/public/does-not-exist   # expect 404
kill %1
```

This was verified directly in this session: `app.main` mounts `portfolio_router`, `job_swipe_router`, and `outreach_router` with `dependencies=[Depends(current_verified_user)]`, and `portfolio_public_router` with no auth dependency at all (`backend/app/main.py`, lines mounting the four routers). `current_verified_user` raises `401` when there is no session, so all four authenticated smoke checks above should return `401`, not `500`.

### 3.2 Frontend smoke tests

```bash
cd frontend
npm run build     # must succeed — this also statically renders /app/documents,
                   # /app/matches/swipe, /app/outreach, /app/portfolio, and the
                   # dynamic /p/[slug] route as part of the Next.js build
npm run lint       # non-interactive; must exit 0 (may print warnings, must not error)
```

Verified in this session: `npm run build` completes with all 47 routes generated, including `/app/documents` (○ static), `/app/matches/swipe` (○ static, 43.1 kB), `/app/outreach` (○ static), `/app/portfolio` (○ static), and `/p/[slug]` (ƒ dynamic, server-rendered per-request as expected for a per-slug public page). `npm run lint` completes with exit code `0`; the only warnings printed are in files outside Module 2's scope (e.g. `verify-email/page.tsx`, `DossierView.tsx`, `NetworkGraph.tsx`) — none of the Module 2 feature files (`features/cv-management/`, `features/job-swipe/`, `features/portfolio/`, `features/outreach/`) produce a single lint warning.

Manual/browser check of the 5 key pages rendering without throwing (`/app/documents`, `/app/matches/swipe`, `/app/outreach`, `/app/portfolio`, `/p/[slug]`): the build's static/dynamic page generation above is a strong proxy for "renders without throwing" (Next.js fails the build if a page throws during prerender), but for `/app/documents`, `/app/matches/swipe`, `/app/outreach`, and `/app/portfolio` — all client-rendered behind auth — do a manual click-through in a logged-in browser session as the final confirmation; the build step alone does not execute their client-side data-fetching hooks.

---

## 4. Unit tests

All backend Module 2 tests were actually run in this session. Summary: **179 passed, 0 failed** across the 11 files below (`test_cv_completeness.py`, `test_cv_chat.py`, `test_cv_improvement.py`, `test_cv_improvement_worker.py`, `test_portfolio.py`, `test_job_swipe.py`, `test_outreach.py`, `test_outreach_worker.py`, `test_module2_api.py`, `test_cv_extraction.py`, `test_session_tracking.py`, plus the always-relevant `test_retry.py`). All 14 frontend Module 2 feature test files were also actually run: **70 passed, 0 failed**, plus 2 more in `DocumentDetailView.test.tsx`.

Two extra backend test files exist beyond what `phase2_module2.md` §9 originally specified — `test_cv_improvement_worker.py` and `test_outreach_worker.py` (worker-entrypoint tests, i.e. testing `app/workers/tasks/{cv_improvement,outreach}.py` directly rather than only the services they call) — plus `backend/tests/test_module2_migrations.py`, which supersedes the plan's placeholder §9.10 filename. All three are real, present, and passing; treat them as part of this module's test suite even though they weren't in the original blueprint.

### 4.1 CV completeness (`app/domain/cv_completeness.py`)

```bash
cd backend
pytest tests/test_cv_completeness.py -v
```

11 tests, pure functions, no DB/mocks. Covers:
- `compute_missing_fields()`: all-missing on empty CV, none-missing on full CV, partial CV, and a regression case (`test_compute_missing_fields_zero_years_experience_is_not_missing` — proves `0.0` years of experience is a valid answer, not "missing", which matters because a naive falsy check would wrongly flag a fresh graduate's `0` as unanswered) plus `test_compute_missing_fields_unchanged_regression` (locks in the exact behavior so the richness/weighting work added in the hardening round couldn't silently change what counts as "missing").
- `completeness_score()`: matches the present fraction, full CV = 1.0, empty CV = 0.0, and `test_completeness_score_richer_list_scores_higher_though_both_not_missing` — the specific hardening-round proof that `FIELD_WEIGHTS` + the list-field richness factor (`min(1.0, len(value) / 3)`) rewards a candidate with 3 skills over one with 1, even though `compute_missing_fields()` correctly treats both as "not missing" (this is the exact "richness-aware" behavior called out in the round-1 hardening summary).
- `question_for_field()`: known field, and unknown-field fallback (`"Can you provide your {field}?"`).

**Known gap:** no direct unit test asserts the literal numeric values in `FIELD_WEIGHTS` sum to 1.0 (the module docstring claims this) — the richness test above proves the *relative* ordering works, but a future edit that breaks the sum-to-1.0 invariant would not be caught by any existing test. Not a blocker, just a note for anyone touching `cv_completeness.py` next.

### 4.2 CV completeness chatbot (`cv_chat_service.py`, `llm_tools.py`)

```bash
cd backend
pytest tests/test_cv_chat.py -v
```

22 tests. Beyond the original plan's 6 (§9.2), this file was measurably hardened — it now covers:
- Session lifecycle: create with missing fields, resume an existing active session, reject an unprocessed document (409), 404 for another user's document, and the edge case where a document already has zero missing fields (session completes immediately with no chat needed).
- Turn handling: tool-call applies and advances to the next field, no-tool-call reprompts the same field, the hard turn limit (`cv_chat_max_turns`) is enforced, 404 for an unknown session, rejecting a turn on a non-active session, and completing the session correctly whether the *last* field was just resolved or *all* fields were already resolved before this call.
- `_call_llm_with_tool`: returns `None` on an HTTP error, returns `None` on malformed tool-call arguments (never crashes the turn), and `test_record_cv_answer_tool_is_strict_mode` — asserts `RECORD_CV_ANSWER_TOOL["function"]["strict"] is True`, i.e. proving the OpenAI strict-mode tool-schema hardening actually took effect, not just that a schema exists.
- `test_post_message_uses_values_array_for_list_field` — the specific proof that a list-valued field (e.g. `technical_skills`) is recorded via the tool's `values` array, not the scalar `value` field, exercising the nullable `value`/`values` pair added during hardening.
- `_apply_field_value`: comma-separated list fields split correctly, numeric years-of-experience parses, and an invalid years-of-experience value becomes `None` rather than raising or storing garbage.
- **Transient-retry proof** (hardening round): `test_call_llm_with_tool_retries_transient_error_then_succeeds` and `test_post_message_completes_turn_after_transient_retry` — these mock a transient (e.g. 429/503) failure on the first call and a success on the retry, and assert the turn completes successfully rather than failing outright. See §6.5 below for how to read this test as proof the "`raise_for_status()` inside the retried closure" bug fix actually works.

### 4.3 CV improvement / feedback (`feedback_generator.generate_cv_improvement`, `workers/tasks/cv_improvement.py`)

```bash
cd backend
pytest tests/test_cv_improvement.py tests/test_cv_improvement_worker.py -v
```

`test_cv_improvement.py` — 14 tests. Beyond the original plan's 6 (§9.3):
- `_parse_cv_improvement_response`: valid JSON, malformed input falls back to `ats_score=0`, score clamps at both ends (150→100, tested separately from a low-end clamp), bullets/lists are capped, incomplete bullets (missing `original`/`rewritten`) are dropped, non-list fields default to empty lists defensively, **`test_parse_cv_improvement_response_drops_bullets_with_fabricated_numbers`** — the hardening-round proof for `_drop_fabricated_metric_bullets()`: a rewritten bullet containing a number not present in the original text is dropped entirely rather than shown to the candidate, and `ats_score_methodology` is set on both the success and the malformed-fallback path (i.e. the disclaimer field is never silently absent).
- `generate_cv_improvement()`: empty text short-circuits without calling OpenAI, no API key raises `ValueError`, a real (mocked) call parses correctly, long CV text truncates at the documented 12,000-character bound, and **`test_generate_cv_improvement_retries_transient_error_then_succeeds`** — the transient-retry proof for this specific call site.

`test_cv_improvement_worker.py` — 4 tests: the RQ job succeeds and writes a `CvFeedbackReport` + marks the `DocumentJob` completed, a missing document marks the job failed (not an unhandled exception), a generation failure (exception from `generate_cv_improvement`) also marks the job failed, and the sync-entrypoint-wraps-async pattern (`generate_cv_improvement_job` calling `asyncio.run(...)`) is exercised directly.

**Known gap:** no test asserts the exact 5-bullet cap end-to-end through a real (mocked) OpenAI response containing more than 5 candidate bullets — `test_parse_cv_improvement_response_caps_bullets_and_lists` covers the cap at the parser level, but nothing drives it through `generate_cv_improvement()`'s full call path. Low-risk (the parser is the only thing that applies the cap, and it's directly tested), but worth knowing if you're auditing for gaps.

### 4.4 Portfolio (`app/modules/portfolio/`)

```bash
cd backend
pytest tests/test_portfolio.py -v
```

23 tests, materially expanded from the plan's original 7 (§9.6). Slug validation: rejects leading hyphen, trailing hyphen (new), too short, invalid characters (new), accepts a valid slug, and normalizes uppercase to lowercase (new — proves the `.lower()` normalization in the field validator, not just that uppercase is rejected outright, which it isn't — it's normalized, not rejected). Profile CRUD: create-then-update, slug-taken-by-another-user rejected (409), same-owner-reusing-own-slug is allowed (new — an important edge case: "slug taken" must only apply to *other* users), `get_my_profile` 404 when none exists vs. returns the existing one, and `test_my_profile_response_includes_user_id_and_public_url` (new — asserts the *owner's own* view of their profile does include `user_id`/`public_url`, the mirror-image check to the public response's privacy test below). Items: adding requires an existing profile first (409), items round-trip through both "my profile" and the public profile view, delete removes the item and 404s if the profile or item doesn't exist. Public lookup: unpublished profiles 404, published profiles are visible, and unknown slugs 404. Two tests are specific to the hardening-round `image_url` field: **`test_add_item_with_image_url_round_trips_through_my_and_public_profile`** and **`test_add_item_without_image_url_defaults_to_none`** — together proving the new nullable column is optional and, when set, survives the my-profile → public-profile round trip. `test_migration_032_adds_image_url_and_reverses_cleanly` independently proves the migration itself (not just the ORM-level behavior).

### 4.5 Job swipe (`app/modules/job_swipe/`)

```bash
cd backend
pytest tests/test_job_swipe.py -v
```

11 tests, up from the plan's original 4 (§9.7). Deck: returns unswiped matches, empty for a user with no matches (new). Swipe: removes the card from the next fetch, overwriting a previous decision doesn't duplicate the row, `up` direction is accepted for super-like (new — proves all 3 directions, not just right/left), rejects a match owned by another user (404), rejects an unknown match id (404, new), and `test_swipe_action_request_rejects_invalid_direction` (new — Pydantic-level validation that `direction` is one of exactly `right`/`left`/`up`). Two hardening-round-specific tests: **`test_swipe_right_boosts_similar_posting_above_dissimilar_one`** — the direct proof of the embedding-similarity re-ranking in `job_swipe/repository.py._compute_similarity_boosts()`/`get_unswiped_matches()`; and the undo pair, **`test_undo_last_swipe_restores_card_to_next_deck_fetch`** and **`test_undo_last_swipe_raises_404_when_no_prior_swipes`**.

**Known gap:** `_compute_similarity_boosts()` has a Postgres-specific code path (raw `pgvector` `<=>` SQL via `literal_column`, with a `try/except` fallback to the pure-Python `cosine_similarity()` path) and a separate SQLite/fallback path. `test_swipe_right_boosts_similar_posting_above_dissimilar_one` runs against this repo's default SQLite test database, so it only exercises the **Python fallback branch**, not the real pgvector SQL branch or the exception-triggered fallback-from-Postgres branch. If you need to prove the pgvector branch itself, that requires the `@pytest.mark.postgres` pattern (a `TEST_DATABASE_URL` pointing at real Postgres) — worth doing once against a real Postgres instance before calling the re-ranking feature fully proven in production, since a raw SQL string-interpolation query like this is exactly the kind of code that can pass on SQLite and still break on Postgres.

### 4.6 Outreach (`app/modules/outreach/`, `app/clients/perplexity.py`, `app/workers/tasks/outreach.py`)

```bash
cd backend
pytest tests/test_outreach.py tests/test_outreach_worker.py -v
```

`test_outreach.py` — 18 tests, up from the plan's original 5 (§9.8). Perplexity client: empty summary with no API key, fails soft on an HTTP error, returns a real (mocked) summary on success (new), and **`test_perplexity_client_retries_transient_error_then_succeeds`** — the transient-retry proof for this call site. Draft editing: rejects editing a sent message (409), successfully updates subject/body on a draft (new), 404 for an unowned message (new). Sending: appends the disclosure footer and marks sent, rejects sending an already-sent message (409), **`test_send_message_uses_absolute_privacy_url_when_configured`** — the hardening-round proof that the privacy-policy link in the footer resolves to an absolute URL when `APP_PUBLIC_BASE_URL` is set, and a 404-for-unowned-message case for send too. Listing: only returns the current user's own messages (new — a real cross-user leak test, not just an auth check). Draft request/enqueue: rejects when `OUTREACH_ENABLED=false` (403), requires a processed CV (409), enqueues successfully for a completed document, **`test_request_draft_second_call_rejected_while_lock_held`** — the direct proof of the Redis `SET NX EX 60` idempotency lock (409 on collision). Response shaping: `test_to_response_marks_research_degraded_true_when_source_none` and its `false`/`perplexity` counterpart — the two-sided proof of the `research_degraded` field's derivation from `company_context_used["source"]`.

`test_outreach_worker.py` — 5 tests: the RQ job succeeds end-to-end (mocked Perplexity + mocked OpenAI) and writes an `OutreachMessage`, a missing document raises, the sync-wrapper-invokes-async pattern is exercised directly, and `_draft_with_llm` both without an API key (generic fallback message) and with one (parses the mocked OpenAI response).

### 4.7 Shared retry/client infrastructure (`app/clients/retry.py`)

```bash
cd backend
pytest tests/test_retry.py -v
```

2 tests, parametrized over the 4 transient status codes (`429`, `502`, `503`, `504`) plus one non-transient case (`400`). This is the one file every "raise_for_status() inside the retry closure" fix across `cv_chat_service.py`, `feedback_generator.py`, `perplexity.py`, and `workers/tasks/outreach.py` ultimately depends on being correct — `is_transient_http_error()` is what decides whether `with_transient_retry()` retries at all. The 429-added-to-the-transient-set change (hardening round) is covered directly by the `429` parametrize case.

### 4.8 Router-level / API tests (`test_module2_api.py`)

```bash
cd backend
pytest tests/test_module2_api.py -v
```

21 tests (via `fastapi.testclient.TestClient`, not `httpx.AsyncClient` as the original plan sketched — the real file uses the synchronous `TestClient`, which is the correct/established convention in this repo's other router-level test files). Covers, per route: auth-required 401 for unauthenticated requests, envelope-shape assertions (`{"success": true, "data": {...}}}` per the `EnvelopeAPIRoute` convention), and success-path behavior for: CV completeness, CV chat session start, CV chat message posting, CV feedback request (returns `job_id`) and fetch (404 when no report exists yet) and accept-bullet, portfolio profile PUT/GET/items-add/items-delete, the public portfolio 200-and-404 cases, swipe deck fetch and swipe action, and outreach draft-request/list/edit/send.

### 4.9 Migration tests (`test_module2_migrations.py`)

```bash
cd backend
pytest tests/test_module2_migrations.py -v
```

25 tests — actually run in this session, **all 25 passed**. Far more thorough than the plan's single-test §9.10 sketch: per-table column/nullability assertions for all 7 Module 2 tables (`cv_chat_sessions`, `cv_chat_messages`, `cv_feedback_reports`, `portfolio_profiles`, `portfolio_items`, `job_swipe_actions`, `outreach_messages`), foreign-key assertions, index/uniqueness assertions, a per-revision downgrade test (each of `030` → `025` downgrades in reverse order, proving each migration's `downgrade()` drops exactly what its own `upgrade()` created, not more and not less), and a full downgrade-past-Module-2 → re-upgrade-to-head round trip.

### 4.10 Regression tests for the two prerequisite bug fixes (§2.1 of the original plan)

```bash
cd backend
pytest tests/test_cv_extraction.py tests/test_session_tracking.py -v
```

`test_cv_extraction.py::test_extract_cv_data_does_not_await_sync_json_method` — regression test proving `httpx.Response.json()` is called synchronously (never `await`ed) in `cv_extractor.py`'s LLM call path. `test_session_tracking.py`'s `TestUserIdUuidCoercion` class (3 tests: `test_create_session_accepts_uuid_user_id`, `test_create_session_accepts_str_user_id`, `test_add_attempt_accepts_str_user_id`) — regression tests proving `SessionManager` coerces a `user_id` passed as either a `uuid.UUID` or a plain `str` to the same `UUID` before binding it to the ORM column.

### 4.11 Frontend feature test suites

```bash
cd frontend
npx vitest run features/cv-management features/job-swipe features/portfolio features/outreach
npx vitest run "app/app/documents/[documentId]/DocumentDetailView.test.tsx"
```

Actually run in this session: **14 test files, 70 tests, all passing** for the 4 feature modules, plus **1 file, 2 tests, passing** for `DocumentDetailView.test.tsx` (the page that surfaces the CV-chat/feedback UI for a specific document). Breakdown by file:

| Feature | Test files |
|---|---|
| `cv-management` | `CompletenessBanner.test.tsx` (3), `CvChatWidget.test.tsx` (4), `CvFeedbackPanel.test.tsx` (6), `hooks/useCvChat.test.tsx` (4), `hooks/useCvFeedback.test.tsx` (8) |
| `job-swipe` | `components/SwipeCard.test.tsx` (8), `components/SwipeDeckView.test.tsx` (6), `hooks/useSwipeDeck.test.tsx` (3) |
| `portfolio` | `components/PortfolioEditor.test.tsx` (6), `components/PublicPortfolioPage.test.tsx` (5), `components/SlugField.test.tsx` (5), `hooks/usePortfolioProfile.test.tsx` (4) |
| `outreach` | `components/OutreachDraftCard.test.tsx` (4), `hooks/useOutreach.test.tsx` (4) |

Note the exact command differs from the original plan's §9.11 sketch (`npm test -- features/...`) — the real `package.json` `test:unit` script runs `vitest run`, and there is no plain `npm test` script at all; use `npx vitest run <paths>` (or `npm run test:unit` for the whole frontend suite) directly, as shown above.

**Known gap:** none of these frontend component/hook tests exercise the real Next.js BFF routes (`frontend/app/api/{documents,cv-chat,cv-feedback,portfolio,matches,outreach}/*`) — they mock at the `fetch`/hook level. The BFF routes themselves have no dedicated unit test file found under `frontend/app/api/`; their correctness is only exercised indirectly, either by these mocked component tests (which don't actually call them) or by the integration tests in §5 below (which do, against a real running stack). If a BFF route's URL, method, or response-unwrapping logic is wrong, no automated frontend test catches it today — only §5's manual integration pass would.

---

## 5. Integration tests

These are end-to-end flows spanning the frontend, the BFF layer, the FastAPI backend, the worker, and (where relevant) mocked/real external calls. Run them against the stack started in §2.2/§2.3. Each flow is written as concrete numbered steps; a tester (human or agent) can execute them either through the browser UI or directly against the backend API with `curl`/`httpx` — both are noted where they differ.

### 5.1 CV completeness chat → CV improvement feedback

1. Upload a CV (`POST /api/documents/upload`, `document_type=cv`) and poll `GET /api/documents/jobs/{job_id}` until `status == "completed"`. Note the returned `document_id`.
2. `GET /api/documents/{document_id}/completeness` — verify `completeness_score` is between 0.0 and 1.0, and `missing_fields` lists whichever of the 8 `REQUIRED_FIELDS` (`email`, `phone`, `linkedin_url`, `technical_skills`, `total_years_experience`, `desired_roles`, `desired_locations`, `remote_preference`) the extractor didn't find on the uploaded CV.
3. `POST /api/documents/{document_id}/cv-chat/sessions` — verify `status == "active"` (assuming at least one field is missing) and the first assistant message asks about the first missing field, in the `REQUIRED_FIELDS` order.
4. For a **scalar** field (e.g. `phone`), `POST /api/documents/cv-chat/sessions/{session_id}/messages` with a plausible answer (e.g. `"555-0100"`). Verify the turn's `assistant_message` moves on to the next missing field, and `session.fields_resolved` now includes `phone`.
5. For a **list** field (e.g. `technical_skills`), post an answer like `"Python, SQL, Docker"`. This is the flow that must produce a `values`-array tool call, not a scalar `value` — verify (either by inspecting the resulting `extracted_data` or, if you have LLM-call visibility, the actual tool-call arguments) that `extracted_data["technical_skills"]` is a list (`["Python", "SQL", "Docker"]`), not a comma-joined string.
6. Continue answering until `session.status == "completed"`. Then `GET /api/documents/{document_id}/cv-data` and verify `extracted_data` now reflects every answer given in steps 4-5.
7. `POST /api/documents/{document_id}/feedback` with a `target_role` — verify the response has a `job_id` (this enqueues onto `QUEUE_FEEDBACK`, serviced by the running worker from §2.2). Poll `GET /api/documents/jobs/{job_id}` until completed.
8. `GET /api/documents/{document_id}/feedback` — verify: `ats_score` is between 0-100, `ats_score_methodology` is present and non-empty (the heuristic-estimate disclaimer), and — if the underlying CV text contains a bullet the LLM might plausibly try to "improve" with an invented number — verify no `rewritten_bullets` entry contains a numeric token absent from its own `original` text (the `_drop_fabricated_metric_bullets` guard). This is easiest to force deterministically by mocking the OpenAI response in a lower-level test (§4.3) rather than depending on a live model's behavior; treat the live end-to-end check here as a spot-check, not the primary proof.
9. `POST /api/documents/{document_id}/feedback/{report_id}/accept` with a `bullet_index` — verify `accepted_bullet_indices` now includes that index, and that the underlying `CandidateDocument.raw_text`/`extracted_data` was **not** modified by this call (Decision 3: accept only records endorsement, never auto-rewrites the stored CV).

### 5.2 Portfolio profile + item with an image, public page round trip

1. `PUT /api/portfolio/profile` with `{"slug": "jane-doe-test", "display_name": "Jane Doe", "headline": "Backend Engineer", "is_published": true}`. Verify the response's `public_url` ends in `/jane-doe-test` (built from `PORTFOLIO_PUBLIC_BASE_URL`).
2. `POST /api/portfolio/items` with `{"item_type": "github", "title": "My Project", "url": "https://github.com/example/repo", "image_url": "https://example.com/thumb.png"}`. Verify `201` and that the response includes `image_url` unchanged.
3. As an unauthenticated request (no cookie), `GET /api/portfolio/public/jane-doe-test` — verify `200`, and that the returned item's `image_url` matches step 2's value exactly (the image-url round-trip through the public response path, not just the owner's own view).
4. In a browser, visit `/p/jane-doe-test` — verify the page renders the item with its image, and does not throw (this exercises `frontend/app/p/[slug]/page.tsx`'s server-side `backendFetchPublic` + `adaptPublicPortfolioProfile` path against a real backend, not a mock).
5. `PUT /api/portfolio/profile` again with the same slug but `"is_published": false`. Then `GET /api/portfolio/public/jane-doe-test` (still unauthenticated) — verify `404`.
6. As a **second, different** authenticated user, attempt `PUT /api/portfolio/profile` with `{"slug": "jane-doe-test", ...}` — verify `409` (slug already taken by another user), confirming cross-user slug collision is still enforced.

### 5.3 Swipe right → deck update → similarity boost → undo

This flow needs at least 2-3 seeded `job_matches`/`job_postings` rows for the test user (via Module 1's normal scan flow, or seeded directly if testing in isolation) plus embeddings on the relevant postings if you want to exercise the similarity-boost step (step 3 below) — Module 1's `job_postings.embedding`/`JobPostingEmbedding` rows must exist for the postings involved, or the boost step is a no-op (falls back to score-only ordering, which is still correct, just not what step 3 is trying to prove).

1. `GET /api/matches/swipe-deck` — note the card ordering and the top card's `match_id`.
2. `POST /api/matches/{match_id}/swipe` with `{"direction": "right"}` on the top card. Verify `200` and `direction == "right"` in the response.
3. `GET /api/matches/swipe-deck` again — verify the just-swiped card no longer appears.
4. If you seeded a job posting with an embedding similar to the one just liked, and another with a dissimilar embedding, both still unswiped and belonging to the same user: fetch the deck again and verify the similar posting now ranks above the dissimilar one, even if the dissimilar one has a higher raw `overall_score` — this is the `_SIMILARITY_BOOST_WEIGHT = 15.0`-weighted re-ranking from `job_swipe/repository.py`. **Note:** on SQLite this exercises the Python `cosine_similarity()` fallback branch, not the pgvector SQL branch — see the "Known gap" in §4.5 for why you'd want to repeat this specific step against real Postgres before considering the pgvector path itself proven.
5. `DELETE /api/matches/swipe/undo` — verify `200`, and that the response's `match_id`/`direction` matches step 2's swipe.
6. `GET /api/matches/swipe-deck` once more — verify the undone match has reappeared in the deck.
7. Immediately call `DELETE /api/matches/swipe/undo` a second time (nothing left to undo) — verify `404` ("No previous swipe to undo").

### 5.4 Outreach draft → idempotency lock → send → disclosure footer

1. Ensure you have a `document_id` with `processing_status == "completed"` (from §5.1 step 1, or any previously-processed CV).
2. `POST /api/outreach/drafts` with `{"company_name": "Acme Corp", "recipient_role_title": "Hiring Manager", "document_id": "<id>"}`. Verify `200` and a `rq_job_id` in the response. Poll (there is no dedicated job-status endpoint for outreach in this module — check via `GET /api/outreach` and look for a new `draft`-status message for "Acme Corp" appearing once the worker processes it) until the draft appears.
3. Inspect the resulting message: if `PERPLEXITY_API_KEY` is unset/empty, verify `research_degraded == true` in the response (the `PerplexityClient.get_company_context()` fail-soft path returning `{"summary": "", "source": "none"}`). If a real Perplexity key is configured, verify `research_degraded == false` and that the drafted `body` plausibly references something concrete about "Acme Corp" (a loose check — LLM output isn't deterministic; the goal is confirming the Perplexity call round-tripped at all, not grading its content).
4. **Immediately** (within 60 seconds — the lock's `ex=60`) call `POST /api/outreach/drafts` again with the **same** `company_name` (case-insensitive — the lock key lowercases it) and the same `job_match_id` (or lack thereof). Verify `409 Conflict` — the Redis `SET NX EX 60` idempotency lock rejecting the collision.
5. Wait 60+ seconds (or manually clear the Redis key `outreach-draft-lock:{user_id}:{company_name_lower}:{job_match_id_or_none}`) and repeat step 4 — verify it now succeeds (`200`), proving the lock actually expires rather than being permanent.
6. `PATCH /api/outreach/{message_id}` on the still-`draft` message with a new `subject`/`body` — verify `200` and the edit is reflected.
7. `POST /api/outreach/{message_id}/send` — verify `200`, `status == "sent"`, `sent_at` is set, and the returned `body` contains both the unsubscribe language (`"unsubscribe"` or "prefer not to receive further outreach") **and** a `"Privacy policy:"` line with a URL — the two things Decision 5 requires in the disclosure footer (the unsubscribe line was in the original plan; the privacy-policy link is the hardening-round addition).
8. Attempt `POST /api/outreach/{message_id}/send` again on the now-`sent` message — verify `409` (already sent).
9. Attempt `PATCH /api/outreach/{message_id}` on the now-`sent` message — verify `409` (only drafts can be edited).

### 5.5 Transient-retry proof (429/503 from an LLM/Perplexity call)

This is best demonstrated via the already-existing mocked unit tests rather than actually forcing a live 429/503 from OpenAI/Perplexity (which is neither reliable nor something you should intentionally try to trigger against a real paid API in a test run). Run these directly and read their assertions as the proof:

```bash
cd backend
pytest tests/test_cv_chat.py::test_call_llm_with_tool_retries_transient_error_then_succeeds -v
pytest tests/test_cv_chat.py::test_post_message_completes_turn_after_transient_retry -v
pytest tests/test_cv_improvement.py::test_generate_cv_improvement_retries_transient_error_then_succeeds -v
pytest tests/test_outreach.py::test_perplexity_client_retries_transient_error_then_succeeds -v
```

Each test mocks the first HTTP call to raise (or return) a transient status (429/502/503/504) and the second to succeed, then asserts the overall operation (chat turn, CV improvement generation, or Perplexity lookup) completes successfully rather than propagating the failure — proving `with_transient_retry()` is actually wired in at each of these four call sites, and specifically that `raise_for_status()` is called **inside** each retried closure (if it were called after `with_transient_retry()` returned, as the pre-hardening bug did, the retry would never trigger on a 429/503 status — only on network-level exceptions — and these tests would fail). There is no equivalent test for the fifth call site, `app/workers/tasks/outreach.py`'s own OpenAI drafting call (`_draft_with_llm`) — confirm this yourself: `test_outreach_worker.py` does not currently include a transient-retry test for `_draft_with_llm`, even though the round-1 hardening summary states this call site was included in the `with_transient_retry` rollout. Reading `app/workers/tasks/outreach.py` directly (done in this session) confirms the code itself does call `with_transient_retry(_do_post)` with `raise_for_status()` inside the closure — the fix is real — but its own dedicated retry-test coverage is a **known gap**: worth adding a `test_draft_with_llm_retries_transient_error_then_succeeds` test to `test_outreach_worker.py` for parity with the other four call sites.

---

## 6. Full-suite + coverage gate

### 6.1 Backend

```bash
cd backend
pytest --cov=app --cov-report=term-missing --cov-fail-under=78
```

**Actually run in this session.** Result: **1042 passed, 23 skipped, 10 failed**, total coverage **78.76%** (gate is `--cov-fail-under=78`, configured in `pyproject.toml`'s `[tool.coverage.report]` — confirmed by reading it directly). "Success" for this command means: the coverage gate line reads `Required test coverage of 78% reached. Total coverage: 78.76%` and the only failures present are exactly the 10 listed below — any additional or different failure is a real regression and should block sign-off.

**The 10 known, pre-existing, out-of-scope failures** (confirmed present and unrelated to Module 2 — they are Module 1 / AI Job Matching enrichment-pipeline issues, per this session's ground truth and independently reproduced by actually running the suite):

- `tests/test_job_matching_worker.py::TestScanJobsForCandidate::test_skips_embedding_when_posting_already_has_stored_embedding`
- `tests/test_job_status_clarity.py::test_job_with_data_shows_completed`
- `tests/test_job_status_clarity.py::test_job_with_no_data_shows_completed_no_data`
- `tests/test_job_status_clarity.py::test_job_with_handles_shows_completed`
- `tests/test_job_status_clarity.py::test_job_with_emails_shows_completed`
- `tests/test_job_status_clarity.py::test_job_with_verified_emails_shows_completed`
- `tests/test_job_status_clarity.py::test_job_with_business_shows_completed`
- `tests/test_job_status_clarity.py::test_job_with_only_sources_shows_completed`
- `tests/test_job_status_clarity.py::test_multiple_enrichers_one_succeeds_shows_completed`
- `tests/test_job_status_clarity.py::test_suppressed_job_not_affected`

**Do not mistake these for a Module 2 regression.** They fail identically on the base branch before any Module 2 hardening/gap-closure work, per the task's ground truth (pydantic validation + a fakeredis-await issue in the job-matching worker path, unrelated to CV chat/portfolio/swipe/outreach code). If you see a *different* set of failures, or these plus new ones, treat the new ones as real and investigate; if you see exactly these 10 and nothing else, the run is clean from a Module 2 standpoint.

For scoping to just Module 2 + directly-adjacent files without the Module 1 noise:

```bash
pytest tests/test_cv_completeness.py tests/test_cv_chat.py tests/test_cv_improvement.py \
       tests/test_cv_improvement_worker.py tests/test_portfolio.py tests/test_job_swipe.py \
       tests/test_outreach.py tests/test_outreach_worker.py tests/test_module2_api.py \
       tests/test_module2_migrations.py tests/test_cv_extraction.py tests/test_session_tracking.py \
       tests/test_retry.py -v
```

**Actually run in this session:** 179 passed (the 11 files without `test_module2_migrations.py`, which was separately confirmed at 25/25 passing) — 0 failed.

Lint/type (not independently re-verified line-by-line in this session, but present in the repo's existing tooling per `phase2_module2.md` §9.11 — run and confirm clean before sign-off):

```bash
ruff check app/
mypy app/
```

### 6.2 Frontend

```bash
cd frontend
npm run typecheck
npm run lint
npm run build
npx vitest run features/cv-management features/job-swipe features/portfolio features/outreach
npm run test:unit    # full frontend suite, if you want the broader regression check too
```

**Actually run in this session:** `npm run lint` exits `0` (warnings only, all outside Module 2 files). `npm run build` succeeds, all 47 routes generated including every Module 2 page. The 4 feature-module vitest suites: 70/70 passing across 14 files. `npm run typecheck` was not independently re-run in this session as a separate step — the `next build` step above runs its own TypeScript type-check as part of compilation and did not report any type errors, which is a strong (though not 100% identical) proxy; run `npm run typecheck` explicitly before final sign-off for the exact same guarantee `tsc --noEmit` gives standalone.

---

## 7. Final acceptance checklist

Mirrors `phase2_module2.md` §17's structure, updated to reflect what was actually verified in this session. Check off each box only once you've personally confirmed it (or trust the "actually run in this session" evidence cited above/below for the boxes marked verified here).

**Prerequisites (§2.1 of the original plan):**
- [x] `cv_extractor.py`'s `await response.json()` bug fixed (confirmed via `test_extract_cv_data_does_not_await_sync_json_method`, passing)
- [x] `session_manager.py`'s `user_id` UUID-coercion bug fixed (confirmed via `TestUserIdUuidCoercion`, passing)
- [x] Both have passing regression tests

**Database:**
- [x] `025_cv_chat_sessions.py` through `030_outreach_messages.py` created, applied, and reversible (confirmed: `alembic upgrade head` succeeds, `test_module2_migrations.py` 25/25 passing including per-revision downgrade tests)
- [x] `032_portfolio_item_image_url.py` (hardening-round addition, not in the original plan) applied and reversible, chaining correctly through the two merge-heads migrations (`025_merge_job_matching_and_stabilization_heads`, `031_merge_job_board_cv_and_stabilization_heads`) onto a single confirmed head
- [x] `outreach_messages.job_match_id` foreign key correctly references `job_matches` (confirmed via `TestOutreachMessagesSchema::test_foreign_keys`)
- [ ] **Not independently re-verified in this session:** the plan's original numbering (`022`-`027`) doesn't match the real files (`025`-`030` plus two merge revisions and `032`) — this is expected given real-world migration-chain reconciliation with a concurrently-developed Module 1 branch, not a defect, but if you're auditing against the plan's literal filenames you will not find them; audit against the real files listed above instead.

**Backend:**
- [x] `app/domain/cv_completeness.py` created, with the hardening-round `FIELD_WEIGHTS`/richness-factor `completeness_score()` on top of the original `compute_missing_fields()`
- [x] `app/modules/documents/models.py` includes `CvChatSession`, `CvChatMessage`, `CvFeedbackReport`
- [x] `app/clients/llm_tools.py` created, `RECORD_CV_ANSWER_TOOL` is strict-mode with nullable `value`/`values`
- [x] `app/modules/documents/cv_chat_service.py` created
- [x] `app/modules/documents/{schemas,service,router}.py` include the completeness/chat/feedback routes
- [x] `app/services/feedback_generator.py` includes `generate_cv_improvement()`, `_drop_fabricated_metric_bullets()`, `ats_score_methodology`
- [x] `app/workers/tasks/cv_improvement.py` created
- [x] `app/modules/portfolio/{__init__,models,schemas,repository,service,router}.py` created, including the hardening-round `image_url` field
- [x] `app/modules/job_swipe/{__init__,models,schemas,repository,service,router}.py` created, including the hardening-round similarity-boost re-ranking and undo endpoint
- [x] `app/clients/perplexity.py` created
- [x] `app/modules/outreach/{__init__,models,schemas,repository,service,router}.py` created, including the hardening-round idempotency lock, `research_degraded` field, and privacy-policy footer link
- [x] `app/workers/tasks/outreach.py` created
- [x] `app/workers/queue.py`/`app/workers/rq_worker.py` include `QUEUE_OUTREACH`, positioned after `QUEUE_FEEDBACK` in the general-purpose worker's queue list (confirmed by reading `rq_worker.py` directly)
- [x] `app/main.py` mounts `portfolio_router`, `portfolio_public_router`, `job_swipe_router`, `outreach_router` (confirmed by reading `main.py` directly, and by the §3.1 smoke test)
- [x] `app/core/config.py` includes the new settings fields (confirmed by reading `config.py` directly)
- [x] `backend/.env.example` includes the Module 2 section (confirmed; note `OUTREACH_SENDER_EMAIL` from the original plan's §7 is **not** present — deliberate deviation, see §2.1 above)
- [ ] **Not independently re-verified in this session:** `app/database/orm_registry.py` new-module imports, and `app/services/email_service.py` `CV_COMPLETENESS_REMINDER`/`PORTFOLIO_PUBLISHED` template additions — plausible given everything else works (ORM models clearly load correctly, since every DB-backed test above passes), but neither file was directly opened and read in this session; a quick `grep` before final sign-off would close this out cheaply.

**Testing:**
- [x] All Module 2 backend test files created and passing (179/179 across the 11 core files, actually run)
- [x] Migration upgrade/downgrade tests pass (25/25, actually run)
- [x] Coverage gate (`--cov-fail-under=78`) passes: **78.76%** actual, actually run
- [x] Full existing test suite passes except the 10 named pre-existing, out-of-scope failures (1042 passed, 23 skipped, 10 known failures — actually run)
- [x] 4 frontend feature-module test suites created and passing (70/70 across 14 files, actually run)
- [ ] Lint (`ruff check app/`) and type-check (`mypy app/`) were not independently re-run as standalone commands in this session — run before final sign-off.

**Frontend:**
- [x] `frontend/features/cv-management/`, `job-swipe/`, `portfolio/`, `outreach/` all exist with hooks/components/tests as expected (confirmed by directory listing)
- [x] `frontend/app/app/documents/`, `matches/swipe/`, `outreach/`, `portfolio/`, `p/[slug]/` pages exist and build successfully
- [x] `frontend/components/layout/nav-config.ts` includes the "Swipe jobs" nav entry (round-2 gap-closure fix — confirmed by reading the file directly: `{ href: "/app/matches/swipe", label: "Swipe jobs", icon: Briefcase }`), plus `Portfolio` and `Outreach` entries
- [x] `frontend/eslint.config.js` exists (round-2 addition — flat config extending `next/core-web-vitals`/`next/typescript`, confirmed by reading it directly)
- [x] `npm run build` and `npm run lint` both succeed (actually run in this session)
- [x] `SwipeCard.tsx` has the "Draft outreach" button (confirmed by reading the file directly)
- [ ] **Not independently re-verified in this session:** the exact frontend file/function counts from the original plan's §11-13 (e.g. "10 new interfaces", "8 new adapter functions", "16 new functions") — the *features* those numbers were meant to add up to are all present and tested, but the granular counts were not re-tallied line-by-line against `src/lib/types.ts`/`api-adapter.ts`/`api-client.ts` in this session. Low risk given the passing build/tests, but flagged here rather than silently checked off.

**Documentation:**
- [x] `docs/adr/0014-cv-chat-portfolio-outreach.md` exists (confirmed via directory listing)
- [x] `backend/docs/ARCHITECTURE.md` includes Module 2's "Implementation status" rows and "Agent quick reference" myth-busting entries (confirmed by reading the relevant sections directly — CV chat, CV improvement feedback, portfolio, job swipe, and outreach are all listed as "Real, implemented per `phase2_module2.md`")
- [ ] **Not independently re-verified in this session:** whether `docs/adr/README.md`'s index was updated to list ADR 0014 — not opened in this session; a one-line check before final sign-off.

**Round 2 (plan §17 gap-closure) — verified present in this session:**
- [x] `{ href: "/app/matches/swipe", label: "Swipe jobs" }` nav entry
- [x] `/verify-email` page wraps its `useSearchParams()`-consuming component in `<Suspense>` (confirmed by reading the file directly — `VerifyEmailContent` is wrapped by `VerifyEmailPage`'s `<Suspense fallback=...>`)
- [x] `frontend/eslint.config.js` exists
- [x] Backend coverage gate closed: 78.76% actual vs. the 78% floor (was ~77.4% before the round-2 test additions per this task's ground truth; the 6 named files/additions — `test_auth_permissions.py`, `test_backward_compat_reexports.py`, `test_compliance_lazy_exports.py`, `test_core_openapi.py`, `test_signals_store.py`, plus extra `test_question_bank.py` cases — all confirmed present via directory listing, though not read line-by-line in this session since they're explicitly Module-1-adjacent utility coverage, not Module 2 itself)

**Overall: Module 2 is functionally complete and its own test suite is fully green.** The only open items are the handful of "not independently re-verified in this session" checkboxes above — none of which surfaced as broken when checked indirectly (imports work, tests pass, build succeeds), but which deserve a direct look before a final, zero-caveats sign-off. Nothing found during this pass indicates a genuinely missing or broken piece of Module 2 functionality.
