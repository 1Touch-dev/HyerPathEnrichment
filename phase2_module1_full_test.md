# Phase 2 — Module 1: AI Job Matching & Notifications — Full Test Guide

This is a hand-off test guide for anyone who did **not** write this code and needs
to verify, on their own machine, that Module 1 (as specified in
[`phase2_module1.md`](./phase2_module1.md)) is fully implemented and working —
including everything added *after* the original spec during the post-implementation
audit and remediation rounds (bug fixes, cost tracking, dedup, retry state machine,
digest fix, real-time SSE badge, and browser push notifications).

Follow the sections in order. Each section says whether it's **automated**
(you just run a command and read pass/fail) or **manual** (you click through the UI
and eyeball the result). Do the automated sections first — if those are red, don't
bother with manual QA yet.

---

## 0. What "Module 1" actually shipped (read this first)

The original spec ([`phase2_module1.md`](./phase2_module1.md)) asked for 3 user-facing
features and 5 technical components. All of them are implemented. On top of that,
a post-implementation audit found and fixed several real bugs, and one scope
addition (real-time push) was approved mid-project. This guide tests **all** of it,
not just the original spec.

### 0.1 The 3 user-facing features (original spec, §0–§4)

| # | Feature | Status |
|---|---------|--------|
| 1 | **CV Parser** — extract skills, experience, roles, companies, industries, education, certifications, salary/location/remote preferences from an uploaded PDF/DOCX | ✅ Implemented, wired into upload pipeline |
| 2 | **AI Search Agent** — scan JobSpy (5 boards) every 24h, embedding-similarity match, filter by salary/location/remote, score 0–100 | ✅ Implemented |
| 3 | **Smart Notifications** — email/SMS/webhook/push on high-score matches, daily top-5 digest, "why this job matches you" LLM explanation | ✅ Implemented (SMS is an intentional stub per Decision 6 in the spec — `NOTIFY_SMS_ENABLED=false` with no real SMS client wired; not a bug) |

### 0.2 The 5 technical components (original spec table)

| Component | Tool/Library | Status |
|---|---|---|
| CV parsing (PDF/DOCX) | PyMuPDF + OpenAI GPT-4o-mini | ✅ `backend/app/services/cv_extractor.py`, wired into `backend/app/workers/tasks/document.py` |
| Embeddings + vector search | OpenAI `text-embedding-3-small` + pgvector | ✅ `backend/app/modules/job_matching/models.py`, `repository.py` |
| Job matching scorer | Deterministic scorer + LLM explanation | ✅ `backend/app/modules/job_matching/scorer.py`, `explainer.py` |
| Notification engine | RQ + `rq-scheduler` (not Celery — see Decision 5 in the spec) + email/webhook/push workers | ✅ `backend/app/workers/tasks/job_matching.py` |
| User preference UI | Next.js forms + BFF API routes | ✅ `frontend/features/job-matching/`, `frontend/app/app/matches/` |

### 0.3 What was added *after* the original spec (audit fixes + scope additions)

These are real bugs found during a skeptical post-implementation audit, plus one
approved scope addition. This guide has a dedicated regression checklist for each
one in §8.

| # | What it was | Fix |
|---|---|---|
| 1 | CV parser was broken end-to-end (sync/async bug in `cv_extractor.py`, and it was never called by the upload pipeline) | Fixed + wired into `document.py` |
| 2 | `PreferencesForm.tsx` only exposed 4 of 8 preference fields, and saving one field wiped the rest | All 8 fields exposed; partial updates (`PUT` no longer destructive) |
| 3 | `session_manager.py` passed `str` where the ORM expected `uuid.UUID` | `_coerce_uuid()` helper added |
| 4 | Digest bug: marked **all** unnotified matches as notified but only emailed the top 5 ("marks 30, emails 5") | `mark_notified()` now only stamps the top 5 actually sent |
| 5 | Webhook/push-only notification preference was silently broken (code required "email" to be enabled before sending anything) | Email-specific early return removed |
| 6 | No cost visibility into embedding/LLM spend | `track_embedding_cost`/`track_llm_cost` + failure counters wired in |
| 7 | Job postings were re-embedded every scan (duplicate OpenAI spend) | `has_posting_embedding()` guard added |
| 8 | A failed LLM explanation call was retried forever with no backoff/give-up | Retry state machine (`explanation_status`, `retry_count`, max-retries) |
| 9 | **Scope addition**: real-time in-app notification (approved mid-project, on top of the email digest) | Server-Sent Events (`GET /api/job-matching/events`) + unread-count badge in nav |
| 10 | **Scope addition**: browser push notifications | VAPID + `pywebpush`, service worker, subscribe/unsubscribe UI |
| 11 | Two stray, unrelated pytest collection errors were blocking `pytest --cov` from ever completing | Fixed (see §6.4) |

---

## 1. Prerequisites

### 1.1 Required for everything in this guide

- Python 3.11+ (the repo's `backend/.venv` was created under Python 3.13/3.14 — either works; **do not** try to reuse a `.venv` created on a different OS, see §9.3)
- Node.js 20+ and npm
- Git

### 1.2 Required only for the parts noted "needs live services"

- A running Redis (`redis://localhost:6379/0` by default) — needed for the worker/scan/digest/SSE tests
- An `OPENAI_API_KEY` — needed for real CV parsing and real embeddings/explanations. Without it, the **unit test suite still passes** (LLM calls are mocked), but the **real-world manual test** in §7 will fail at the CV-upload step.
- Optional Postgres + pgvector — local dev defaults to SQLite and that's fully supported; Postgres is only needed if you want to test the production dialect path (see §9.2 for the one test that's dialect-sensitive)
- Optional `SENDGRID_API_KEY` — only needed to see a real delivered email; digest logic is fully testable without it (`EMAIL_TEST_MODE=true` logs instead of sending)
- Optional VAPID keypair — only needed to test real browser push delivery end-to-end

You do **not** need JobSpy to hit real job boards for the automated tests — those
are mocked. If you want to test a real live scan, see §7.4.

---

## 2. Get the code

```bash
git clone <repo-url> HyerEnrichment
cd HyerEnrichment
git checkout feat/AI-Job-Matching-Notifications
git log --oneline -5   # sanity check you're on the right commit
```

You should be on branch `feat/AI-Job-Matching-Notifications`, which is the open
[PR #235](https://github.com/1Touch-dev/HyerPathEnrichment/pull/235). If your
colleague gives you a different branch/commit, make sure it's this one or later —
an earlier checkout will be missing several of the fixes in §0.3.

---

## 3. Backend setup

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -e ".[dev]"   # or: pip install -r requirements.txt if that's what the repo has
cp .env.example .env
```

Edit `.env` and set at minimum:

```bash
OPENAI_API_KEY=sk-...        # required for real CV parsing / embeddings / explanations
REDIS_URL=redis://localhost:6379/0
JOB_MATCHING_ENABLED=true
```

Leave `DATABASE_URL` on the default SQLite line — no Postgres needed for this guide.

Run migrations:

```bash
alembic upgrade head
```

You should see it apply through `024_push_subscriptions` (the last job-matching
migration) with no errors. If you want to confirm downgrade/upgrade both work
cleanly (a common way for schema bugs to hide):

```bash
alembic downgrade 017_practice_audio_recordings
alembic upgrade head
```

Start Redis (if not already running):

```bash
docker run -d --name jm-redis -p 6379:6379 redis:7
```

Start the API:

```bash
uvicorn app.main:app --reload
```

Start the job-matching worker (separate terminal, same venv):

```bash
python -m app.workers.rq_worker_job_matching
```

---

## 4. Frontend setup

```bash
cd frontend
npm install
cp .env.example .env.local   # if present; otherwise set BACKEND_API_URL to point at :8000
npm run dev
```

Open `http://localhost:3000`.

---

## 5. Automated backend tests

Run these from `backend/` with the venv active.

### 5.1 Job-matching module + directly related test files

This is the fastest, most targeted check — it covers every file the module
introduced or touched:

```bash
pytest tests/test_job_matching_scorer.py tests/test_job_matching_repository.py \
       tests/test_job_matching_api.py tests/test_job_matching_worker.py \
       tests/test_job_matching_explainer.py tests/test_job_matching_events.py \
       tests/test_job_matching_push.py tests/test_job_matching_migrations.py \
       tests/test_feedback_worker.py tests/test_cv_extraction.py \
       tests/test_session_tracking.py -v
```

**Expected result: `230 passed, 2 skipped`.**

The 2 skips are intentional and documented in the test output itself, not failures:

- `test_embedding_getter_parses_json_string_on_sqlite` — this test only exercises
  the SQLite-JSON-fallback code path on `JobPostingEmbedding.embedding`, which is
  compiled out whenever the `pgvector` Python package is importable (it is, in a
  normal dev install). It's not a bug; there's nothing to fix — this is expected on
  any machine with `pgvector` installed. See §9.2 if you want to actually exercise
  that code path.
- `test_malformed_payload_is_logged_and_skipped_not_crashed` (in
  `test_job_matching_events.py`) — pre-existing, documented skip in that test file
  for a timing-sensitive SSE edge case; not something this module regressed.

If you get **collection errors** instead of a clean run (pytest fails before even
starting, mentioning `ImportError` or `ModuleNotFoundError` on `test_feedback_worker.py`
or a file called `test_feedback_with_null_question.py`), you're on a stale commit
from before the fix in §0.3 item 11 — `git pull` / re-checkout the branch.

### 5.2 Coverage gate for the job-matching module specifically

```bash
pytest --cov=app.modules.job_matching --cov=app.workers.tasks.job_matching \
       --cov-report=term-missing --cov-fail-under=78 \
       tests/test_job_matching_scorer.py tests/test_job_matching_repository.py \
       tests/test_job_matching_api.py tests/test_job_matching_worker.py \
       tests/test_job_matching_explainer.py tests/test_job_matching_events.py \
       tests/test_job_matching_push.py tests/test_job_matching_migrations.py
```

Should pass the `--cov-fail-under=78` gate.

### 5.3 Full backend suite (regression check)

```bash
pytest -q
```

**Important — read this before panicking:** this repo has a known, pre-existing
issue *unrelated to job matching* where running the **entire** test suite together
causes ~80 failures / ~40 errors in unrelated modules (tier/pipeline/opt-out/session
tests) due to cross-test SQLite state contamination when hundreds of tests share one
in-memory database across the whole run. This is not something this module
introduced, and it does not affect job-matching or feedback tests specifically
(verify: `grep` the failure list for `job_matching` or `feedback` — you should find
nothing). If you want a true full-suite regression signal without that noise, run
module-by-module as in §5.1, or ask whoever owns those other modules whether that's
been fixed yet.

### 5.4 Lint and type checks

```bash
ruff check app/modules/job_matching app/workers/tasks/job_matching.py
ruff format --check app/modules/job_matching app/workers/tasks/job_matching.py tests/test_job_matching*.py
mypy app/modules/job_matching
```

All three should pass clean for the job-matching module itself. (Running bare
`mypy app` across the *whole* backend will show pre-existing errors in unrelated
files — that's expected and not part of this module's scope; see §9.4.)

---

## 6. Automated frontend tests

Run these from `frontend/`.

### 6.1 Unit tests

```bash
npx vitest run features/job-matching \
  components/layout/AppSidebar.test.tsx \
  components/layout/AppNavRail.test.tsx \
  components/layout/AppBottomNav.test.tsx
```

**Expected result: 9 test files, 46 tests, all passing.**

### 6.2 Typecheck / lint / build

```bash
npm run typecheck
npm run lint
npm run build
```

All three should succeed.

### 6.3 OpenAPI contract check

Confirms the frontend's generated types still match the backend's actual API
surface (catches silent drift when someone changes a backend schema without
regenerating):

```bash
npm run openapi:check
```

Should exit clean (no diff).

---

## 7. Manual smoke test — real API, real UI, no mocks

This is the actual "does it work" test. You'll register a user, upload a CV,
set preferences, trigger a scan, and see matches appear in the UI.

Both the API (`uvicorn`, port 8000) and the frontend (`npm run dev`, port 3000)
must be running, and the job-matching worker (§3) must be running for the scan
step. Redis must be up.

### 7.1 Register and verify a user

All job-matching endpoints require a **verified** user (`current_verified_user`
dependency in `app/main.py`), not just a logged-in one.

1. Go to `http://localhost:3000` and register a new account (or use the app's
   sign-up flow).
2. With `EMAIL_ENABLED=false` or `EMAIL_TEST_MODE=true` (the `.env.example`
   default), the verification email won't actually be delivered — it's logged
   instead. Check the `uvicorn` terminal output for the verification link/token
   right after registering, or query the DB directly:

   ```bash
   python -c "
   import sqlite3
   conn = sqlite3.connect('hyrepath.db')
   print(conn.execute('SELECT email, verification_token, is_verified FROM users').fetchall())
   "
   ```
3. Hit the verify-email endpoint with that token (`POST /auth/verify-email`), or
   click the link if you did configure real SendGrid delivery.
4. Confirm `GET /auth/me` now shows `is_verified: true`.

If you skip this step, every job-matching request will 401/403 and you'll wrongly
conclude the module is broken.

### 7.2 Upload a CV and confirm parsing works

**Important:** there is no CV upload page in the frontend UI — this is a documented,
intentional gap (see `phase2_module1.md` §11.10, "Blind spot: CV upload UI is
entirely missing"). Only the backend `/api/documents/upload` endpoint exists, and
job-matching's `PreferencesForm` is designed to work standalone (all fields are
plain, manually-enterable form fields, not CV-derived-only) precisely because of
this gap. Do not go looking for an upload button in the app — there isn't one yet.
Test CV parsing directly against the API:

1. Upload a real PDF or DOCX resume via the API:

   ```bash
   curl -X POST http://localhost:8000/api/documents/upload \
     -H "Authorization: Bearer <your-access-token>" \
     -F "file=@/path/to/resume.pdf"
   ```
2. Poll `GET /api/documents/jobs/{job_id}` (the response from step 1 gives you the
   job id) until the processing job completes.
3. Fetch `GET /api/documents/{document_id}/cv-data` and confirm the response
   includes populated:
   - `skills` (non-empty list)
   - `years_of_experience`
   - `previous_roles` / `companies`
   - `industries` — this field was added post-audit; if it's missing or always
     empty, you're on a stale checkout (see §0.3 item 1)
   - `education`
   - `certifications` — also added post-audit
   - `salary_expectations`, `location_preferences`, `remote_preference`

If this endpoint returns all-empty/null fields despite a real resume being
uploaded, the sync/async bug from §0.3 item 1 has regressed — that's a serious
failure, not a minor one, since the entire matching pipeline depends on this data.

**No `OPENAI_API_KEY` set?** This step will fail or return empty data — that's
expected, not a bug. Set the key and retry, or skip to §7.3 by manually inserting
a `candidate_job_preferences` row via SQL/API instead of relying on CV extraction.

### 7.3 Set job preferences (all 8 fields)

1. Navigate to `/app/matches/settings` in the frontend.
2. Confirm the form shows (not just 4 of them — this was the pre-audit bug):
   - Desired roles
   - Desired locations
   - Remote preference (remote/hybrid/onsite)
   - Salary min/max + currency
   - Notification channels (email/sms/webhook/push — checkboxes)
   - Webhook URL (only enabled/visible when "webhook" channel is checked)
   - Digest frequency (daily/weekly/off)
3. Set some values, save, reload the page, and confirm they persisted.
4. **Partial-update regression check**: change *only* the salary range and save.
   Reload and confirm your desired roles/locations from step 3 are still there
   (not wiped out). This is the destructive-overwrite bug from §0.3 item 2 — if
   any field you didn't touch gets reset to empty/default, that bug has regressed.

### 7.4 Trigger a scan

Real JobSpy calls hit live job boards and can be slow/rate-limited, so this is
optional but worth doing once to prove the pipeline end-to-end:

```bash
curl -X POST http://localhost:8000/api/job-matching/scan \
  -H "Authorization: Bearer <your-access-token>"
```

Watch the worker terminal (§3, `rq_worker_job_matching`). You should see log lines
for `scan_jobs_for_candidate`, embedding generation, scoring, and (if any match
scores high enough) `generate_explanations_for_candidate`.

Then:

```bash
curl http://localhost:8000/api/job-matching/matches \
  -H "Authorization: Bearer <your-access-token>"
```

Confirm you get back a `matches` array with `overall_score`, `score_breakdown`,
and (for the top few) a non-null `explanation` field with a plain-English
"why this job matches you" summary.

### 7.5 View matches in the UI

1. Navigate to `/app/matches`.
2. Confirm match cards render with title, company, score, and explanation text.
3. Click a card (or its "mark viewed" action) and confirm the unread badge in the
   nav (sidebar on desktop, bottom nav / rail depending on viewport) decrements
   in real time, without a page reload. This is the SSE-backed live badge —
   if it only updates after a manual refresh, the SSE wiring has regressed
   (see §8.9 below).
4. Give a match thumbs up/down feedback and confirm it's not resettable to
   nothing afterward (feedback should be sticky).

### 7.6 Digest email (test mode)

With `EMAIL_TEST_MODE=true` (default), no real email is sent, but the render
path still runs and logs. Manually invoke the digest task to confirm rendering:

```bash
python -c "
from app.workers.tasks.job_matching import send_match_digest
send_match_digest('<your-user-id>')
"
```

Check the `uvicorn`/worker log output for a `TEST MODE: job_match_digest email to ...`
line. If you have real SendGrid creds and flip `EMAIL_TEST_MODE=false`, you should
receive an actual email listing the top 5 matches — count them; it must be 5 or
fewer, never more (§0.3 item 4).

### 7.7 Browser push (optional, needs HTTPS or localhost + VAPID keys)

1. Generate a VAPID keypair (one-time):

   ```bash
   pip install py-vapid
   vapid --gen
   ```

   Put the resulting public/private keys and a `mailto:` subject into `.env`
   (`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT`).
2. Restart the API so it picks up the new settings.
3. In the browser, go to `/app/matches/settings`, check the "push" notification
   channel, and grant the browser permission prompt when it appears.
4. Confirm a `push_subscriptions` row was created:

   ```bash
   python -c "
   import sqlite3
   conn = sqlite3.connect('backend/hyrepath.db')
   print(conn.execute('SELECT user_id, endpoint FROM push_subscriptions').fetchall())
   "
   ```
5. Trigger a digest (§7.6) or a new high-score match and confirm a real OS-level
   push notification appears, even with the browser tab closed (this is the point
   of push vs. SSE — SSE only works while the tab is open).

---

## 8. Regression checklist — every audit-round bug, one line each

Run through this list explicitly; each row maps to an item in §0.3 and to a
specific automated test that pins it down, so you have both a manual check and
an automated one for each:

| # | Bug | How to confirm it's fixed |
|---|---|---|
| 1 | CV parser sync/async bug | §7.2 above returns real, non-empty `cv-data`. Automated: `pytest tests/test_cv_extraction.py -v` |
| 2 | Preferences form only 4/8 fields, destructive overwrite | §7.3 above. Automated: `pytest tests/test_job_matching_api.py -k partial_update -v` |
| 3 | `session_manager.py` UUID coercion | Automated: `pytest tests/test_session_tracking.py -k UuidCoercion -v` |
| 4 | Digest "marks 30, emails 5" | Automated: `pytest tests/test_job_matching_worker.py -k "digest and top_5" -v` or search test names for `mark_notified` |
| 5 | Webhook/push-only notification silently broken | Automated: `pytest tests/test_job_matching_worker.py -k "channel" -v` — look for tests asserting webhook/push fire without email enabled |
| 6 | No cost tracking | Automated: `pytest tests/test_job_matching_worker.py -k "cost" -v` — confirms `track_embedding_cost`/`track_llm_cost` are called |
| 7 | Duplicate embedding spend | Automated: `pytest tests/test_job_matching_repository.py -k "has_posting_embedding" -v` and `test_job_matching_worker.py -k "already" -v` |
| 8 | Explanation retries forever | Automated: `pytest tests/test_job_matching_repository.py -k "claim_match_for_explanation or record_explanation_failure" -v` |
| 9 | Real-time SSE badge | §7.5 step 3 above. Automated: `pytest tests/test_job_matching_events.py -v` and `npx vitest run features/job-matching/hooks/useUnreadMatchEvents.test.tsx` |
| 10 | Browser push | §7.7 above. Automated: `pytest tests/test_job_matching_push.py -v` and `npx vitest run features/job-matching/hooks/usePushSubscription.test.tsx` |
| 11 | Stray pytest collection errors | `pytest --collect-only -q` from `backend/` exits 0 with no `ERROR` lines |

---

## 9. Known non-issues — don't file a bug for these

These look alarming on a fresh clone but are pre-existing / environment quirks,
not regressions introduced by this module. Saves you (and whoever you report to)
time re-diagnosing something already understood.

### 9.1 Full-suite `pytest -q` shows ~80 failures / ~40 errors

Explained in §5.3 — pre-existing cross-test SQLite contamination in unrelated
modules when the *entire* suite runs together. Verify none of them mention
`job_matching` or `feedback` in the test path; if they don't, this is not your
concern for this module.

### 9.2 `test_embedding_getter_parses_json_string_on_sqlite` shows `SKIPPED`

Expected whenever `pgvector` is importable in your environment (the normal case).
To actually exercise the SQLite JSON-fallback code path this test targets, run in
an environment where `pip uninstall pgvector` (a throwaway venv, not your main one)
and re-run just that test.

### 9.3 Do not reuse a `.venv` created on a different OS

If `backend/.venv` was created inside WSL and you're testing from native Windows
(or vice versa), the interpreter binary won't actually run — you'll see errors
like `did not find executable at '/usr/bin\python.exe'`. Delete `.venv` and
recreate it fresh from whichever OS you're actually running commands in. The
pre-commit `mypy` hook now defends against this automatically
(`scripts/hooks/run_mypy.py` verifies the candidate interpreter is runnable before
using it), but a manually-activated broken venv will still fail.

### 9.4 `ruff` flags `B008 Do not perform function call Depends in argument defaults` on WSL but not on Windows/CI

Both environments run the exact same `ruff` version against the exact same
`pyproject.toml`, yet WSL flags `Depends(get_db_session)` default-argument usage
in `job_matching/router.py` (and, if you check, in the pre-existing
`documents/router.py` too — this pattern is used throughout the codebase, not
introduced by this module) while Windows reports zero issues on the identical
files. This points to a stray user-level ruff config on that particular WSL
install, not a real lint violation. If your colleague's `ruff check` disagrees
with CI/this guide, diff `ruff --show-settings` between environments before
assuming the code is wrong.

### 9.5 Bare `mypy app` across the whole backend shows ~35 pre-existing errors

None of them are in `app/modules/job_matching/`. They're pre-existing debt in
unrelated files (`cost_tracking.py`, `vector_search.py`, `admin/router.py`, etc.)
that predate this module and are out of scope for it. Scope your `mypy` run to
`app/modules/job_matching` (§5.4) to get a signal that's actually about this
module.

---

## 10. Sign-off checklist

Check every box before declaring Module 1 verified on your machine:

- [ ] `alembic upgrade head` applies clean, `alembic downgrade` + re-upgrade is clean
- [ ] §5.1 backend job-matching tests: `230 passed, 2 skipped`
- [ ] §5.2 coverage gate passes at `--cov-fail-under=78`
- [ ] §5.4 lint/format/mypy clean for `app/modules/job_matching`
- [ ] §6.1 frontend tests: `9 files, 46 tests` passing
- [ ] §6.2 frontend typecheck/lint/build all succeed
- [ ] §6.3 OpenAPI contract check is clean
- [ ] §7.1–7.6 manual walkthrough completed at least once with a real resume
- [ ] §7.7 push notification tested at least once (optional but recommended)
- [ ] §8 regression checklist — all 11 rows confirmed
- [ ] §9 known non-issues reviewed so you don't waste time re-reporting them

If every box is checked, Module 1 — including everything added during the
post-implementation audit — is verified working on your machine.
