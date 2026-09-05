# Foundation Week 1 & Week 2 — Test & Verification Plan

**Branch under test:** `master-complete-foundation`
**Purpose:** Give a tester a precise, repeatable procedure to confirm that every Week 1 (Core Infrastructure) and Week 2 (Module-Specific Infrastructure) foundation task from the original 12-day plan is **actually** 100% complete — not just "documented as complete."

> ⚠️ **Why this document exists:** Several self-authored reports already living in this repo (`FOUNDATION_WEEK1_FINAL_COMPLETE.md`, `WEEK2_INTEGRATION_REPORT.md`, `backend/WEEK2_TEST_REPORT.md`) claim 100%/"production-ready" status. However, `WEEK2_INTEGRATION_REPORT.md` (dated 2026-08-06) also records only **50/68 tests passing (74%)** with **18 failing Session Tracking tests** at that time. This plan does **not** assume those issues are fixed — it gives you the exact commands to independently re-verify current status on `master-complete-foundation` after pulling latest.

---

## 0. How to use this document

1. Pull the latest `master-complete-foundation` branch.
2. Work through **Section 1 (Environment Setup)** once.
3. Work through **Section 2 (Week 1)** and **Section 3 (Week 2)** task-by-task. Each task has:
   - A **file existence checklist** (static verification — no environment needed)
   - **Automated test commands** (pytest) with the exact expected test count
   - **Manual/API verification steps** where relevant (curl examples)
   - A **sign-off checkbox row** to fill in with ✅ / ❌ / ⚠️ and notes
4. Fill in **Section 6 (Final Sign-Off Summary Table)** as you go.
5. Anything that fails should be filed as a bug **before** declaring the branch 100% complete — do not just re-mark the checklist ✅ without evidence (a passing `pytest` run, a successful `curl` response, etc.).

---

## 1. Environment Setup (do this once)

### 1.1 Get the code

```bash
git fetch origin
git checkout master-complete-foundation
git pull origin master-complete-foundation
git log -1 --oneline   # sanity check you're on the latest commit
```

### 1.2 Python environment

Requires Python **3.12+** (project uses modern typing syntax; 3.12/3.13 recommended — 3.14 also works but is untested by the original authors).

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -e ".[dev]"
```

This installs the **full dependency set required for Week 1 + Week 2**, including:
- `PyMuPDF`, `python-docx`, `tiktoken`, `langchain-text-splitters` (Task 1/3)
- `pgvector`, `openai` (Task 2)
- `pydub` (Task 5)
- `pytest`, `pytest-asyncio`, `pytest-cov` (test running)

> **Note:** `librosa` (mentioned as *optional* in the original Task 5 spec) is **not** in `pyproject.toml`. This is expected/acceptable — flag it only as a minor deviation, not a failure.

### 1.3 Environment variables

Copy the example env file — **no real Postgres/Redis/OpenAI credentials are required for the automated test suite** (see 1.4):

```bash
cp .env.example .env
```

Key variables (all already defaulted sensibly in `.env.example`):
| Variable | Default | Needed for |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./hyrepath.db` | All tasks (SQLite fallback works for tests) |
| `REDIS_URL` | `redis://localhost:6379/0` | Cost tracking, session metrics, audio cleanup cron (mocked in tests by default) |
| `OPENAI_API_KEY` | unset/commented | Only needed for **live** embedding/CV-extraction/feedback/Whisper calls — tests mock the OpenAI client |
| `R2_BUCKET`, `R2_ACCOUNT_ID`, etc. | placeholder | Only needed for **live** document/audio storage — tests use local `.asset-cache/` fallback |

### 1.4 How the test suite avoids needing real infra

`backend/tests/conftest.py` automatically:
- Forces `DATABASE_URL` to a temp SQLite file and runs `alembic upgrade head` against it (`ensure_db_schema` fixture)
- Injects a `FakeRedis` in place of real Redis for most tests (`fake_redis` fixture) unless you explicitly opt into real infra
- Overrides auth so protected endpoints can be exercised without a real login flow

This means **you can run 95% of this plan without Docker, Postgres, or Redis running.** Postgres-only tests are marked `@pytest.mark.postgres` and require `TEST_DATABASE_URL` — skip them unless you specifically want to validate pgvector on real Postgres (see Section 4).

### 1.5 Sanity check the migration chain (do this first, before any test)

```bash
python -m alembic heads
```

**Expected:** exactly **one** head: `017_practice_audio_recordings`. If you see more than one head, this is a **real regression** — record it as a failure immediately (do not proceed to declare 100% completion).

```bash
python -m alembic upgrade head
python -m alembic downgrade -1
python -m alembic upgrade head
```

**Expected:** all three commands succeed with no errors (proves the migration chain is reversible and clean).

---

## 2. Week 1: Core Infrastructure

### Task 1 — Document Processing (PDF/DOCX upload, extraction, storage)

**File existence checklist:**
```bash
ls backend/app/services/document_processor.py
ls backend/app/storage/document_storage.py
ls backend/alembic/versions/008_candidate_documents.py
ls backend/app/modules/documents/router.py
ls backend/tests/test_document_processor.py
```
All 5 must exist.

**Dependency check:**
```bash
python -c "import fitz; import docx; print('PyMuPDF + python-docx OK')"
```

**Automated tests:**
```bash
pytest tests/test_document_processor.py -v
```
**Expected:** **21 tests pass**, 0 failures.

**Manual API smoke test** (server must be running: `uvicorn app.main:app --reload`, and you need an authenticated session/cookie — see `docs/authentication-guide.md`):
```bash
curl -X POST http://localhost:8000/api/documents/upload \
  -H "Cookie: <auth-cookie>" \
  -F "file=@backend/tests/fixtures/sample_cv.pdf" \
  -F "document_type=cv"
# Expect 200 with a job_id

curl http://localhost:8000/api/documents/jobs/<job_id> \
  -H "Cookie: <auth-cookie>"
# Expect status progressing from "pending" -> "processing" -> "completed"

curl http://localhost:8000/api/documents \
  -H "Cookie: <auth-cookie>"
# Expect the uploaded document listed
```

**Also verify (from the plan's exit criteria):** "Can upload PDF/DOCX, extract text, store in DB and R2/local."
- [ ] Confirm `raw_text` is populated on the `candidate_documents` row after processing (inspect via `sqlite3 hyrepath.db "select length(raw_text) from candidate_documents;"` or a DB browser)
- [ ] Confirm a file actually lands in `.asset-cache/` (or R2 if configured) after upload

| Check | Result | Notes |
|---|---|---|
| Files exist | ☐ | |
| Dependencies importable | ☐ | |
| `pytest tests/test_document_processor.py` → 21/21 | ☐ | |
| Upload → extract → store E2E (manual) | ☐ | |

---

### Task 2 — Embeddings + pgvector Vector Search

**File existence checklist:**
```bash
ls backend/app/clients/embeddings.py
ls backend/app/services/vector_search.py
ls backend/alembic/versions/010_enable_pgvector.py
ls backend/alembic/versions/014_document_embeddings.py
ls backend/tests/test_embeddings.py
ls backend/tests/test_vector_search.py
```

**Note on naming vs. the original spec:** the spec pseudocode named the client methods `embed_text`/`embed_batch` and the search function `find_similar`. The actual implementation uses `generate_embedding`/`generate_embeddings` (with retry + exponential backoff) and `similarity_search`/`store_embeddings`. This is a **naming deviation, not a functional gap** — confirm the behavior matches, not the literal names.

**Automated tests:**
```bash
pytest tests/test_embeddings.py -v          # expect 11/11 pass
pytest tests/test_vector_search.py -v       # expect 12/12 pass
```

**pgvector-specific verification (requires real Postgres — optional but recommended):**
```bash
# with TEST_DATABASE_URL pointing at a Postgres+pgvector instance
pytest tests/test_vector_search.py -v -m postgres
docker exec -it <postgres-container> psql -U postgres -d hyrepath \
  -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
```
**Expected:** row returned confirming the `vector` extension is enabled.

**Manual API smoke test:**
```bash
curl -X POST http://localhost:8000/api/documents/search \
  -H "Cookie: <auth-cookie>" -H "Content-Type: application/json" \
  -d '{"query": "python backend engineer", "limit": 5}'
```
**Expected:** 200 with a `results` array (empty is OK if no documents/embeddings exist yet, but it must not error).

| Check | Result | Notes |
|---|---|---|
| Files exist | ☐ | |
| `pytest tests/test_embeddings.py` → 11/11 | ☐ | |
| `pytest tests/test_vector_search.py` → 12/12 | ☐ | |
| pgvector extension enabled (Postgres) | ☐ | Optional but recommended |
| Search API smoke test | ☐ | |

---

### Task 3 — Semantic Chunking

**File existence checklist:**
```bash
ls backend/app/utils/text_chunking.py
ls backend/tests/test_chunking.py
```

**Implementation note:** uses `langchain_text_splitters.RecursiveCharacterTextSplitter` + `tiktoken` for token-accurate chunking (max 512 tokens/chunk, 50-token overlap, paragraph-aware `\n\n` splitting) — matches spec intent even though it delegates to LangChain rather than a hand-rolled splitter.

**Automated tests:**
```bash
pytest tests/test_chunking.py -v
```
**Expected:** **9 tests pass.**

**Manual verification:**
```bash
python -c "
from app.utils.text_chunking import chunk_document
text = ('Paragraph one. ' * 100) + '\n\n' + ('Paragraph two. ' * 100)
chunks = chunk_document(text, max_tokens=512, overlap=50)
for c in chunks:
    print(c['chunk_index'], c['token_count'])
assert all(c['token_count'] <= 512 for c in chunks)
print('OK -', len(chunks), 'chunks, all <= 512 tokens')
"
```
**Expected:** prints `OK - N chunks, all <= 512 tokens` with no assertion error.

| Check | Result | Notes |
|---|---|---|
| Files exist | ☐ | |
| `pytest tests/test_chunking.py` → 9/9 | ☐ | |
| Manual token-limit check | ☐ | |

---

### Task 4 — CV Structured Extraction

**File existence checklist:**
```bash
ls backend/app/domain/candidate.py
ls backend/app/services/cv_extractor.py
ls backend/tests/test_cv_extraction.py
```

**Schema check** — confirm `CVData` model matches spec fields:
```bash
python -c "
from app.domain.candidate import CVData
f = CVData.model_fields.keys()
required = {'full_name','email','phone','linkedin_url','github_url','portfolio_url',
            'technical_skills','soft_skills','languages','total_years_experience',
            'current_role','current_company','work_history','highest_degree',
            'field_of_study','desired_roles','desired_locations','remote_preference',
            'salary_expectation','completeness_score','missing_fields'}
missing = required - set(f)
print('Missing fields:', missing if missing else 'NONE - schema matches spec')
"
```

**Implementation note:** the extraction prompt lives directly in `cv_extractor.py` (as `CV_EXTRACTION_PROMPT`) rather than centralized in `app/clients/llm.py` as the spec pseudocode suggested — functionally equivalent, just organized differently.

**Automated tests:**
```bash
pytest tests/test_cv_extraction.py -v
```
**Expected:** **11 tests pass** (should cover valid CV parsing, incomplete CV handling, and malformed input per the original task spec — verify all three scenarios are actually present in the test file, not just happy-path).

```bash
grep -n "def test_" tests/test_cv_extraction.py
```
Confirm you see tests for: missing/incomplete fields, malformed/garbage input, and a full valid-CV happy path.

| Check | Result | Notes |
|---|---|---|
| Files exist | ☐ | |
| `CVData` schema field check → NONE missing | ☐ | |
| `pytest tests/test_cv_extraction.py` → 11/11 | ☐ | |
| Malformed-input / incomplete-CV test cases present | ☐ | |

---

### Week 1 — Combined Integration Test

```bash
pytest tests/test_foundation_week1_integration.py -v
```
**Expected:** **14 tests pass.** This is the full E2E suite covering upload → extract → chunk → embed → search, plus error handling (malformed PDF, oversized files) and duplicate detection. If this fails while the individual unit tests above pass, it indicates a **wiring/integration problem** between components, not a component-level bug — investigate before marking Week 1 complete.

```bash
pytest tests/test_document_processor.py tests/test_embeddings.py tests/test_vector_search.py \
       tests/test_chunking.py tests/test_cv_extraction.py tests/test_foundation_week1_integration.py \
       --cov=app/services --cov=app/clients/embeddings --cov=app/utils/text_chunking \
       --cov=app/storage --cov-report=term-missing
```
**Expected total:** **21 + 11 + 12 + 9 + 11 + 14 = 78 tests**, all passing.

### Week 1 Sign-off

| Task | Status | Evidence |
|---|---|---|
| 1. Document Processing | ☐ | |
| 2. Embeddings + pgvector | ☐ | |
| 3. Semantic Chunking | ☐ | |
| 4. CV Structured Extraction | ☐ | |
| Week 1 Integration Suite | ☐ | |

---

## 3. Week 2: Module-Specific Infrastructure

### Task 5 — Audio Processing Infrastructure (Whisper)

**File existence checklist:**
```bash
ls backend/app/clients/speech.py
ls backend/app/services/audio_storage.py
ls backend/app/services/audio_analysis.py
ls backend/alembic/versions/017_practice_audio_recordings.py
ls backend/tests/test_audio_processing.py
```

**Dependency check:**
```bash
python -c "import pydub; print('pydub OK')"
```
> `librosa` is **not** installed (optional dep per spec) — do not fail this task for its absence.

**Automated tests:**
```bash
pytest tests/test_audio_processing.py -v
```
**Expected:** **33 tests pass.** This is a large test file — confirm it covers all three sub-components from the spec:
```bash
grep -n "def test_" tests/test_audio_processing.py | grep -iE "transcrib|whisper"   # speech.py coverage
grep -n "def test_" tests/test_audio_processing.py | grep -iE "storage|upload|retention"  # audio_storage.py coverage
grep -n "def test_" tests/test_audio_processing.py | grep -iE "filler|wpm|words_per_minute|sentiment"  # audio_analysis.py coverage
```
Each grep should return at least one match — if any returns nothing, that sub-component may be under-tested despite the overall file passing.

**Manual verification of filler-word/WPM analysis:**
```bash
python -c "
from app.services.audio_analysis import analyze_transcript  # adjust import if named differently
result = analyze_transcript('um so like I think uh the answer is yes', duration_seconds=10)
print(result)
"
```
(If the function name differs, check `backend/app/services/audio_analysis.py` directly for the actual public API and adapt this snippet — do not skip this check, just correct the import.)

| Check | Result | Notes |
|---|---|---|
| Files exist | ☐ | |
| `pydub` importable | ☐ | |
| `pytest tests/test_audio_processing.py` → 33/33 | ☐ | |
| Sub-component coverage (transcription/storage/analysis) confirmed | ☐ | |

---

### Task 6 — Session Tracking System

**File existence checklist:**
```bash
ls backend/alembic/versions/015_add_session_tracking.py
ls backend/app/services/session_manager.py
ls backend/app/modules/sessions/router.py
ls backend/app/modules/sessions/models.py
ls backend/app/modules/sessions/schemas.py
ls backend/tests/test_session_tracking.py
ls backend/tests/test_session_integration.py
```

**⚠️ Known historical issue — verify this is actually fixed:**
`WEEK2_INTEGRATION_REPORT.md` (2026-08-06) reports **only 7/25 (28%) session-tracking tests passing** at that time, with a documented root cause: "Sessions are created but cannot be retrieved in subsequent queries... database transaction/session persistence issue in tests." This was explicitly called out as deferred/non-blocking rather than fixed. **This is the single highest-risk area in the whole foundation — do not accept a verbal claim that it's fixed. Run the tests yourself.**

**Automated tests:**
```bash
pytest tests/test_session_tracking.py -v
```
**Expected per the original task spec:** all tests pass. **Expected per historical evidence:** possibly still failing (only 7/25 as of last report). Record the actual pass/fail count you observe:

```
Actual result: ____ / 26 passed   (file currently contains 26 test functions)
```

```bash
pytest tests/test_session_integration.py -v
```
**Expected:** **9 tests pass.**

**Manual API smoke test** (this exercises the exact bug class reported above — create then immediately read back):
```bash
SESSION_ID=$(curl -s -X POST http://localhost:8000/sessions \
  -H "Cookie: <auth-cookie>" -H "Content-Type: application/json" \
  -d '{"session_type": "interview_practice"}' | jq -r '.data.id')
echo "Created session: $SESSION_ID"

curl -s http://localhost:8000/sessions/$SESSION_ID -H "Cookie: <auth-cookie>"
# MUST return the session, not a 404 "Session not found"

curl -s http://localhost:8000/sessions -H "Cookie: <auth-cookie>"
# MUST include the session just created in the list, not an empty array
```
**This manual check is critical** — it is exactly the scenario that was failing in automated tests per the historical report. If either of these returns empty/404 right after creation, session tracking is **not** actually complete regardless of what any status document claims.

```bash
curl -s -X PATCH http://localhost:8000/sessions/$SESSION_ID \
  -H "Cookie: <auth-cookie>" -H "Content-Type: application/json" \
  -d '{"status": "completed"}'
curl -s -X DELETE http://localhost:8000/sessions/$SESSION_ID -H "Cookie: <auth-cookie>"
```

| Check | Result | Notes |
|---|---|---|
| Files exist | ☐ | |
| `pytest tests/test_session_tracking.py` pass count | ☐ | Write actual N/26 — compare to historical 7/25 |
| `pytest tests/test_session_integration.py` → 9/9 | ☐ | |
| Manual create→read-back works (no 404) | ☐ | **Critical — known historical failure mode** |
| Manual list shows newly created session | ☐ | **Critical — known historical failure mode** |
| PATCH / DELETE work | ☐ | |

---

### Task 7 — Interview Question Bank

**File existence checklist:**
```bash
ls backend/alembic/versions/016_interview_questions.py
ls backend/app/services/question_generator.py
ls backend/app/services/question_selector.py
ls backend/scripts/seed_questions.py
ls backend/tests/test_question_bank.py
```

**Automated tests:**
```bash
pytest tests/test_question_bank.py -v
```
**Expected:** **16 tests pass.**

**Seed script check — this is the exit criterion from the original spec ("Database seeded with 200+ questions"):**
```bash
grep -n "categories" backend/scripts/seed_questions.py
```
> ⚠️ **Deviation to flag:** the seed script as implemented only generates for **2 categories** (`behavioral`, `technical`) via LLM generation, not a static pre-written bank of "100 behavioral + 50×N technical" questions as literally specified. Whether it reaches 200+ actual rows depends on the `count` parameter passed at runtime and requires a live LLM call (uses GPT-4o per spec) — it is **not** a fully offline/deterministic seed. Confirm this explicitly:

```bash
python backend/scripts/seed_questions.py --help 2>&1 || python -c "
import inspect
from backend.scripts import seed_questions
print(inspect.getsource(seed_questions.seed_questions))
" 2>&1 | head -50
```

Then, with a valid `OPENAI_API_KEY` set and a test/dev database configured:
```bash
cd backend
python scripts/seed_questions.py
sqlite3 hyrepath.db "SELECT COUNT(*) FROM interview_questions;"
```
**Expected:** count ≥ 200 to satisfy the original exit criterion. **If it seeds fewer than 200, mark this task ⚠️ partial, not ✅ complete**, even though the code exists and tests pass — "database seeded with 200+ questions" is an explicit, checkable exit criterion from the plan.

| Check | Result | Notes |
|---|---|---|
| Files exist | ☐ | |
| `pytest tests/test_question_bank.py` → 16/16 | ☐ | |
| Seed script run, DB row count ≥ 200 | ☐ | **Explicit exit criterion — verify the actual number, don't assume** |
| Question selector avoids repeats / personalizes (check test coverage) | ☐ | |

---

### Task 8 — Feedback Generation Pipeline

**File existence checklist:**
```bash
ls backend/app/services/feedback_generator.py
ls backend/app/workers/tasks/feedback.py
ls backend/tests/test_feedback_generation.py
ls backend/tests/test_feedback_worker.py
```

**Implementation note:** provides `generate_interview_feedback()` (Module 3). The spec also asked for `generate_cv_feedback()` (Module 2) and `generate_match_explanation()` (Module 1) as a "unified feedback service for all modules" — **confirm whether these exist**, since Module 1/2 aren't built yet this session may legitimately only need the interview-feedback path, but don't assume:

```bash
grep -n "^async def \|^def " backend/app/services/feedback_generator.py
```
**Expected functions to check for:** `generate_interview_feedback` (should exist). `generate_cv_feedback` / `generate_match_explanation` (likely **do not exist yet** — flag as scoped-out-of-this-foundation rather than a bug, since Modules 1/2 aren't built).

**Automated tests:**
```bash
pytest tests/test_feedback_generation.py -v
```
**Expected:** **13 tests pass.** Historical report noted 12/13 with one test hitting the real API instead of a mock — check if that's fixed:
```bash
pytest tests/test_feedback_generation.py -v -k "no_api_key"
```
**Expected:** this specific test should pass without making a real network call. If it fails with a connection/API error rather than a clean assertion, the mock is still broken.

```bash
pytest tests/test_feedback_worker.py -v
```
**Expected:** **10 tests pass.** This file previously could not even be collected ("0/0 — import error — expected") because it depends on `app.modules.sessions.models.QuestionAttempt`, which now exists after Task 6 was merged. Confirm it **imports and runs** cleanly now — this is a good regression check that Week 2 module dependencies are correctly wired together.

**Manual smoke test:**
```bash
python -c "
import asyncio
from app.services.feedback_generator import generate_interview_feedback
async def main():
    result = await generate_interview_feedback(
        question='Tell me about a time you resolved conflict on a team.',
        answer='I noticed two teammates disagreed on approach, so I set up a call to align on priorities.',
    )
    print(result)
asyncio.run(main())
"
```
(Requires a valid `OPENAI_API_KEY` for a real call, or run against the mocked test suite only if you don't want to spend API credits.)

| Check | Result | Notes |
|---|---|---|
| Files exist | ☐ | |
| `generate_interview_feedback` present | ☐ | |
| `generate_cv_feedback` / `generate_match_explanation` present? | ☐ | Expected **absent** — Modules 1/2 not built yet, not a bug |
| `pytest tests/test_feedback_generation.py` → 13/13 | ☐ | |
| `no_api_key` test passes without real network call | ☐ | Known historical flake |
| `pytest tests/test_feedback_worker.py` → 10/10 (imports cleanly) | ☐ | Confirms cross-module wiring with Task 6 |

---

### Task 9 — Audio Cleanup Worker (7-day retention / GDPR)

**File existence checklist:**
```bash
ls backend/app/workers/tasks/audio_cleanup.py
ls backend/tests/test_audio_cleanup.py
```

**Cron registration check:**
```bash
grep -n "QUEUE_AUDIO_CLEANUP\|register_scheduled_jobs\|cleanup_expired_audio\|0 2 \* \* \*" backend/app/workers/queue.py
```
**Expected:** confirms `register_scheduled_jobs()` registers `cleanup_expired_audio` on a daily `0 2 * * *` (2 AM UTC) cron via `rq-scheduler`, matching the spec.

> ⚠️ Note: `rq-scheduler` registration only takes effect if the scheduler process is actually run (`register_scheduled_jobs()` must be called on scheduler startup, and `rq-scheduler` must be installed/running as its own process). Confirm this is wired into the deployment (check `backend/docker/docker-compose.yml` / worker entrypoint scripts) — not just defined in code.

```bash
grep -rn "rq_scheduler\|rqscheduler\|register_scheduled_jobs" backend/docker/
```

**Automated tests:**
```bash
pytest tests/test_audio_cleanup.py -v
```
**Expected:** **15 tests pass.**

**Manual verification — run the cleanup task directly:**
```bash
python -c "
from app.workers.tasks.audio_cleanup import cleanup_expired_audio
stats = cleanup_expired_audio()
print('Cleanup stats:', stats)
"
```
**Expected:** returns a dict with cleanup counts (e.g. deleted count, errors) without raising — even with zero expired recordings in a fresh DB, it should return `{... 0 ...}` cleanly, not error.

**GDPR audit logging check (spec explicitly calls for this):**
```bash
grep -n "audit\|log" backend/app/workers/tasks/audio_cleanup.py | head -20
```
Confirm cleanup actions are actually logged (not just silently deleted) — this was an explicit exit-criteria item ("Add audit logging for GDPR compliance").

| Check | Result | Notes |
|---|---|---|
| Files exist | ☐ | |
| Cron registration present in `queue.py` | ☐ | |
| Scheduler process wired into Docker/worker startup | ☐ | Verify it's not just dead code |
| `pytest tests/test_audio_cleanup.py` → 15/15 | ☐ | |
| Manual `cleanup_expired_audio()` runs cleanly | ☐ | |
| Audit logging present | ☐ | |

---

### Task 10 — Cost Monitoring

**File existence checklist:**
```bash
ls backend/app/observability/cost_tracking.py
ls backend/app/observability/budget_alerts.py
ls backend/app/modules/admin/router.py
ls backend/tests/test_cost_tracking.py
ls backend/tests/test_admin_costs.py
```

**Automated tests:**
```bash
pytest tests/test_cost_tracking.py -v    # expect 21/21 pass
pytest tests/test_admin_costs.py -v      # expect 9/9 pass
```

**API endpoint check** — the spec asked for a single `GET /api/admin/costs` dashboard; the actual implementation instead splits this into 5 sub-routes. Confirm all 5 exist and require superuser auth:
```bash
grep -n "@router.get\|@router.post" backend/app/modules/admin/router.py
```
**Expected routes:** `/api/admin/costs/daily`, `/api/admin/costs/monthly`, `/api/admin/costs/total`, `/api/admin/costs/top-users`, `/api/admin/costs/breakdown`.

**Manual API smoke test (requires a superuser account):**
```bash
curl -s http://localhost:8000/api/admin/costs/daily -H "Cookie: <superuser-auth-cookie>"
curl -s http://localhost:8000/api/admin/costs/monthly -H "Cookie: <superuser-auth-cookie>"
curl -s http://localhost:8000/api/admin/costs/total -H "Cookie: <superuser-auth-cookie>"
curl -s http://localhost:8000/api/admin/costs/breakdown -H "Cookie: <superuser-auth-cookie>"

# Confirm non-superuser is rejected:
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/admin/costs/daily -H "Cookie: <regular-user-cookie>"
# Expected: 403
```

**Budget alert check:**
```bash
grep -n "DAILY_COST_THRESHOLD_USD\|MONTHLY_COST_THRESHOLD_USD\|ENABLE_BUDGET_ALERTS" backend/.env.example backend/app/observability/budget_alerts.py
```
**Expected:** thresholds are configurable via env (`DAILY_COST_THRESHOLD_USD=100.0`, `MONTHLY_COST_THRESHOLD_USD=2000.0`) and gated by `ENABLE_BUDGET_ALERTS`.

> Historical coverage note: `backend/WEEK2_TEST_REPORT.md` recorded `budget_alerts.py` at only **59% coverage**. Not a hard blocker, but worth spot-checking that edge cases (threshold exceeded, alert firing) are actually exercised:
```bash
grep -n "def test_" backend/tests/test_cost_tracking.py | grep -i "budget\|threshold\|alert"
```

| Check | Result | Notes |
|---|---|---|
| Files exist | ☐ | |
| `pytest tests/test_cost_tracking.py` → 21/21 | ☐ | |
| `pytest tests/test_admin_costs.py` → 9/9 | ☐ | |
| All 5 `/api/admin/costs/*` routes present | ☐ | |
| Non-superuser gets 403 | ☐ | |
| Budget threshold env vars present | ☐ | |
| Budget alert edge-case tests present | ☐ | Historically only 59% coverage |

---

### Week 2 — Combined Integration Test

```bash
pytest tests/test_week2_integration.py -v
```
**Expected:** **2 tests pass.** This is a thin integration file per the repo's own report; it is **not** a substitute for the per-task manual verification above, especially for Session Tracking (Task 6).

```bash
pytest tests/test_audio_processing.py tests/test_audio_cleanup.py \
       tests/test_session_tracking.py tests/test_session_integration.py \
       tests/test_question_bank.py \
       tests/test_feedback_generation.py tests/test_feedback_worker.py \
       tests/test_cost_tracking.py tests/test_admin_costs.py \
       tests/test_week2_integration.py \
       --cov=app/services --cov=app/modules/sessions --cov=app/modules/admin \
       --cov=app/observability --cov=app/workers/tasks \
       --cov-report=term-missing
```
**Expected total if everything is genuinely fixed:** 33+15+26+9+16+13+10+21+9+2 = **154 tests**, all passing. **Do not accept this number on faith — run it and record the actual pass/fail split.** Given the documented history of session-tracking DB fixture issues, this is the number most likely to diverge from 100%.

### Week 2 Sign-off

| Task | Status | Evidence |
|---|---|---|
| 5. Audio Processing | ☐ | |
| 6. Session Tracking | ☐ | **Highest risk — verify manually, not just via report claims** |
| 7. Question Bank | ☐ | Verify actual seeded row count ≥ 200 |
| 8. Feedback Pipeline | ☐ | |
| 9. Audio Cleanup Worker | ☐ | |
| 10. Cost Monitoring | ☐ | |
| Week 2 Integration Suite | ☐ | |

---

## 4. Full Foundation Test Suite (single command)

Run everything from Sections 2 and 3 in one pass and capture full output for the sign-off record:

```bash
cd backend
pytest \
  tests/test_document_processor.py \
  tests/test_embeddings.py \
  tests/test_vector_search.py \
  tests/test_chunking.py \
  tests/test_cv_extraction.py \
  tests/test_foundation_week1_integration.py \
  tests/test_audio_processing.py \
  tests/test_audio_cleanup.py \
  tests/test_session_tracking.py \
  tests/test_session_integration.py \
  tests/test_question_bank.py \
  tests/test_feedback_generation.py \
  tests/test_feedback_worker.py \
  tests/test_cost_tracking.py \
  tests/test_admin_costs.py \
  tests/test_week2_integration.py \
  -v --tb=short 2>&1 | tee foundation_test_run.log
```

**Total expected test count: 232** (78 Week 1 + 154 Week 2, per the per-task counts above). Search the log for `FAILED` and `ERROR` and list every one in the sign-off table — a single command like this:

```bash
grep -E "FAILED|ERROR" foundation_test_run.log
```

If this returns anything, **Week 1/Week 2 is not 100% complete**, regardless of what any other document in the repo says. Attach `foundation_test_run.log` to your verification report.

### 4.1 Coverage gate check

The repo enforces a coverage floor via `pyproject.toml` (`fail_under = 78`):
```bash
pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=78 -q 2>&1 | tail -40
```
Note: this runs the **entire** backend test suite (not just foundation tests), so failures unrelated to Week 1/2 may appear — only treat failures in the files listed above as in-scope for this sign-off; log anything else separately.

### 4.2 Postgres + pgvector validation (recommended, not strictly required)

SQLite is sufficient for functional correctness, but Task 2's exit criteria explicitly mention pgvector, which SQLite cannot exercise. If Docker is available:

```bash
cd backend/docker
docker compose up -d postgres redis
export TEST_DATABASE_URL="postgresql+asyncpg://hyrepath:hyrepath@localhost:5432/hyrepath_test"
cd ..
python -m alembic -x db_url=$TEST_DATABASE_URL upgrade head   # or however the repo's postgres test setup expects the URL
pytest tests/test_vector_search.py tests/test_embeddings.py -v -m postgres
```
**Expected:** pgvector-specific tests pass against real Postgres, and:
```bash
docker exec -it <postgres-container> psql -U hyrepath -d hyrepath_test \
  -c "\d document_embeddings"
```
shows the `embedding` column as type `vector(1536)` with an `hnsw` index (`idx_embeddings_hnsw` or similar) on it.

---

## 5. Documentation Completeness Check (Task 12)

The original spec asked for specific artifacts. Verify presence (content quality is secondary to existence for this checklist):

```bash
ls docs/FOUNDATION_ARCHITECTURE.md          # exists
ls docs/adr/0011-pgvector-vs-dedicated-vector-db.md   # exists (spec asked for "0010-text-embedding-3-small.md" — name differs but topic covered)
ls docs/adr/0012-semantic-chunking-strategy.md        # exists (spec asked for "0011-semantic-chunking.md" — name differs, topic matches)
ls docs/FOUNDATION_ROLLBACK_GUIDE.md        # exists (not explicitly asked for, but valuable — bonus)
ls docs/FOUNDATION_WEEK1_COMPLETION.md      # exists
```

**Gaps to flag (do not block sign-off on these, but record them):**
- [ ] No ADR specifically titled/numbered for **7-day audio retention / GDPR rationale** (spec asked for `0012-7-day-audio-retention.md`). Check if this rationale is folded into another doc:
  ```bash
  grep -rn "7 day\|7-day\|GDPR" docs/ backend/docs/ 2>/dev/null
  ```
- [ ] No standalone `docs/FOUNDATION_OPERATIONS.md` runbook (spec asked for one covering: monitoring costs, clearing embeddings cache, running audio cleanup manually, troubleshooting). Check whether this content exists elsewhere:
  ```bash
  grep -rln "audio cleanup\|clear.*cache\|troubleshoot" docs/*.md backend/docs/*.md 2>/dev/null
  ```

| Check | Result | Notes |
|---|---|---|
| `FOUNDATION_ARCHITECTURE.md` exists | ☐ | |
| pgvector ADR exists (any number) | ☐ | |
| Chunking ADR exists (any number) | ☐ | |
| Audio retention/GDPR rationale documented somewhere | ☐ | Not necessarily its own ADR |
| Operations runbook exists (any name) | ☐ | |

---

## 6. Final Sign-Off Summary Table

Fill this in last, after completing Sections 1–5.

| # | Task | Files Present | Automated Tests | Manual Verification | Overall |
|---|---|---|---|---|---|
| 1 | Document Processing | ☐ | ☐ (21) | ☐ | ☐ |
| 2 | Embeddings + pgvector | ☐ | ☐ (11+12) | ☐ | ☐ |
| 3 | Semantic Chunking | ☐ | ☐ (9) | ☐ | ☐ |
| 4 | CV Structured Extraction | ☐ | ☐ (11) | ☐ | ☐ |
| — | **Week 1 Integration** | — | ☐ (14) | — | ☐ |
| 5 | Audio Processing | ☐ | ☐ (33) | ☐ | ☐ |
| 6 | Session Tracking | ☐ | ☐ (26+9) | ☐ | ☐ |
| 7 | Question Bank | ☐ | ☐ (16) | ☐ (≥200 seeded) | ☐ |
| 8 | Feedback Pipeline | ☐ | ☐ (13+10) | ☐ | ☐ |
| 9 | Audio Cleanup Worker | ☐ | ☐ (15) | ☐ | ☐ |
| 10 | Cost Monitoring | ☐ | ☐ (21+9) | ☐ | ☐ |
| — | **Week 2 Integration** | — | ☐ (2) | — | ☐ |
| 12 | Documentation | ☐ | — | — | ☐ |

**Verdict:** Foundation Week 1 + Week 2 is only "100% complete" if **every row above is ✅ with actual evidence** (pytest output, curl responses, DB row counts) — not because a prior report says so. Given the documented 74%-pass-rate history on Session Tracking specifically, that row deserves the most scrutiny.

---

## 7. Known Deviations From Original Spec (context, not necessarily blockers)

These were found by comparing the actual codebase against the original task descriptions. None of these are automatically failures, but a tester should be aware of them when deciding pass/fail:

1. **Naming differences**: `embed_text`/`embed_batch` → `generate_embedding`/`generate_embeddings`; `find_similar` → `similarity_search`. Functionally equivalent.
2. **Prompt location**: CV extraction and feedback-generation prompts live inside their respective service files rather than centralized in `app/clients/llm.py` as originally sketched.
3. **`librosa` not installed** — was marked optional in the original spec, so acceptable, but `pydub`-only means no advanced audio-analysis features (pitch, spectral) beyond what `audio_analysis.py` implements manually.
4. **`ENABLE_EMBEDDINGS` env var does not exist** — cost gating instead uses `ENABLE_BUDGET_ALERTS` + threshold env vars. Functionally covers the same need (ability to control cost exposure) but not via the literal flag named in the spec.
5. **Admin costs dashboard is 5 routes, not 1** (`/daily`, `/monthly`, `/total`, `/top-users`, `/breakdown`) instead of a single `GET /api/admin/costs`. More granular than spec, not a regression.
6. **Question bank seed script generates via live LLM call for 2 categories**, not a static hand-curated bank of 100+50×N pre-written questions. Reaching "200+ questions" depends on runtime parameters and OpenAI availability — verify actual seeded count rather than assuming the script guarantees it.
7. **Feedback generator only implements `generate_interview_feedback`** — `generate_cv_feedback` (Module 2) and `generate_match_explanation` (Module 1) are not present, which is expected since those modules aren't built yet, but means Task 8 is only partially "unified" as originally envisioned.
8. **No `0010-text-embedding-3-small.md` / `0011-semantic-chunking.md` / `0012-7-day-audio-retention.md` ADRs by those exact names** — equivalent ADRs exist under different numbers (`0011-pgvector-...`, `0012-semantic-chunking-strategy.md`), and audio-retention rationale, if present, is not in its own dedicated ADR.
9. **No standalone `docs/FOUNDATION_OPERATIONS.md`** runbook file.

---

## 8. Reporting Template

After running through this plan, report back using this format:

```
FOUNDATION VERIFICATION REPORT
Branch: master-complete-foundation
Commit: <git log -1 --format=%H>
Date: <date>
Tester: <name>

Week 1: <PASS / FAIL> — <N of 78 automated tests passing>
Week 2: <PASS / FAIL> — <N of 154 automated tests passing>

Blocking issues found:
- ...

Non-blocking deviations confirmed (see Section 7):
- ...

Recommendation: <READY FOR NEXT PHASE / NOT READY — needs fixes to: ...>
```
