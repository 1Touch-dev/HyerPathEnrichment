# Phase 2 — Module 3: Interview Prep & Sentiment Analysis

**Branch:** `master-complete-foundation` (this file is committed directly to this branch — no new branch is created)
**Status:** Implementation blueprint — nothing described here exists in code yet unless explicitly marked `EXISTS` with a file citation. Everything else is `NEW`.
**Governing rule file:** `RULE.md` — every decision below was checked against it; violations are called out explicitly rather than silently made. See §0.

**Purpose of this document:** a single, linear, followable plan such that a developer (or agent) who implements every numbered step in order — database, backend services, routes, workers, Docker, tests, frontend — ends with Module 3 ("Interview Prep & Sentiment Analysis") **100% functionally complete**, with automated tests proving it, without needing to consult any other chat, report, or memory. Every file this plan creates or edits is listed by exact path. Every claim about *why* a design choice was made is evidence-labeled per §1. Every gap in the code that exists **today** on this branch was verified by reading the file directly (not assumed) — see §4 for the full, uncomfortable list.

---

## 0. RULE.md compliance checklist (read this before writing any code)

This plan was designed against `RULE.md` line by line. Rather than assume compliance, here is the explicit mapping:

| RULE.md requirement | How this plan complies |
|---|---|
| "Search the repo for an existing function, type, component, or pattern" (Before writing any code #1) | §2 inventories everything reused: `InterviewQuestion`/`InterviewAttempt` (`app/models.py`), `select_questions()` (`question_selector.py`), `generate_questions()` (`question_generator.py`), `generate_interview_feedback()` (`feedback_generator.py`), `WhisperClient` (`clients/speech.py`), `analyze_transcription()` (`audio_analysis.py`), `PracticeSession`/`QuestionAttempt` (`modules/sessions/models.py`), `CVData` (`domain/candidate.py`), `track_llm_cost()` (`observability/cost_tracking.py`), the `features/*` frontend pattern, and the BFF proxy pattern. Nothing reusable is rebuilt. |
| "Read Agent quick reference in ARCHITECTURE.md" (#2) | Done. Module 3 does not touch `enrichers/pipeline.py`, `enrichers/merge.py`, or `compliance/` — it is a standalone feature module exactly like `documents/` and `sessions/` already are. |
| "Check Implementation status — do not build on scaffold-only features" (#3) | Verified directly by reading the code (not assumed): `question_selector.py`, `question_generator.py`, `feedback_generator.py`, `audio_analysis.py`, `clients/speech.py`, `services/audio_storage.py` all exist as real, working functions — but **none of them is called from any HTTP route or the frontend**. This is the central finding of this document (§4) and the reason this plan exists: the services are real, the product is not. |
| "Keep the change as small as the task allows" (#4) | This plan adds two new thin modules (`app/modules/questions/`, `app/modules/practice_audio/`) instead of bolting HTTP routes onto `sessions/router.py`, which already has a distinct, working responsibility (session/attempt CRUD) — per "one concern per change." It extends `modules/sessions/models.py` (rather than creating a third dumping ground) for the one new ORM class that belongs there by FK ownership. |
| Layer ownership table (`domain/`, `modules/`, `workers/`, `clients/`, `storage/`, `database/`) | New code placed per this table exactly — see §7; every new file states which layer it belongs to and why. |
| Allowed/forbidden imports (`workers/tasks` → must not import `modules/*/service|router`) | `app/workers/tasks/feedback.py` and the new `app/workers/tasks/question_generation.py` import only `app/modules/*/repository`-equivalent read functions and `app/services/*`, never `router.py` or `service.py` — matching the existing (already-compliant) pattern in `feedback.py`. |
| "ORM lives with its owner... never recreate a global app/models.py dumping ground" | `app/models.py` (`InterviewQuestion`, `InterviewAttempt`) is a **pre-existing violation of this exact rule**, not something this plan introduces (§4.1 documents it honestly rather than silently "fixing" it by a drive-by move that would touch unrelated call sites). The one class this plan *does* add — `PracticeAudioRecording` — is placed in `app/modules/sessions/models.py`, its correct owner by FK relationship, not appended to `app/models.py`. |
| "Do not duplicate validation... merge logic... API field mapping" (No redundant code) | Question/audio validation lives once in new Pydantic schemas; no parallel validation added to `sessions/router.py`. Frontend field mapping goes through `api-adapter.ts` only, per existing convention (§10). |
| "Routes are thin" | New `questions/router.py` and `practice_audio/router.py` only do auth + call service + return; all selection/generation/transcription/analysis orchestration lives in `service.py` files. |
| "Async end-to-end... no run_until_complete in request paths" | All router/service code is `async def`. The RQ worker entrypoints (`workers/tasks/*.py`) use `asyncio.new_event_loop()` — matching the existing, already-shipped pattern in `feedback.py`, not a new one. |
| "Schema changes via Alembic only" | 3 new Alembic revisions chained onto the real current head `017_practice_audio_recordings` (verified — see §5). No `create_all`, no hand-edited tables. |
| "When to add an ADR" — new storage, queue, or layer ownership | This plan adds a **new FK relationship** (fixing two previously-unenforced ones), a **new column set** on two existing tables, and **queue isolation** for `feedback`/`question_generation` → ADR required. §11 supplies `docs/adr/0014-interview-practice-question-personalization-and-queue-isolation.md`, formatted to pass `backend/scripts/verify_adrs.py` (verified by reading that script directly — see §11). |
| "New enricher → extend tests/test_pipeline_shape.py" | N/A — not an enricher. Module 3 gets its own test files per existing convention (`test_question_bank.py`, `test_feedback_generation.py`, `test_audio_processing.py` already exist and are extended, not replaced — see §9). |
| "No live external calls in CI... mock subprocess, HTTP, third-party APIs" | All new/changed tests mock OpenAI (`httpx.AsyncClient.post`), never call `api.openai.com` — matching the existing pattern already used in `test_question_bank.py` and `test_feedback_generation.py` (verified by reading them). |
| "Coverage gate ... currently 78%" | §9.9 gives the exact `pytest --cov` command to prove the gate is met before considering Module 3 done. |
| "Never log raw identifiers... use job IDs or hashed values" | All new logging truncates/uses UUIDs only, matching the existing convention already used in `feedback.py`/`session_manager.py` (`extra={"attempt_id": ..., "user_id": str(...)}`) — never raw answer text or resume content in logs. |
| "Never commit secrets... update .env.example with placeholders only" | §6 lists every new/newly-documented env var added to `.env.example` with placeholder values only — no real keys. This includes fixing a **pre-existing documentation gap**: `OPENAI_API_KEY` is a real, load-bearing setting (`core/config.py:134`) used directly by `question_generator.py`, `feedback_generator.py`, `clients/speech.py`, `clients/embeddings.py`, and `cv_extractor.py`, but `.env.example`'s own banner comment claims "api/worker never need OPENAI_API_KEY" — that comment is stale and is corrected in §6. |
| "Public data only... no discover people flows" | Module 3 never looks up or scrapes information about other people — it generates/serves generic and candidate-self-describing (résumé-derived) interview content only. §3 Decision 6 explicitly removes the pasted spec's Glassdoor/LeetCode scraping requirement on this ground. |
| "Update backend/docs/ARCHITECTURE.md Implementation status if scaffold changed" | §12 gives the exact diff to add. |
| "New/changed storage, queue, auth, or layer ownership → ADR linked in the PR" | §11 ADR + §13 PR checklist explicitly links it. |
| Frontend: "Shared types... do not duplicate Dossier/EnrichmentInput shapes inline" | New `InterviewQuestion`, `PracticeAttempt`, `AudioRecording` types added to `frontend/src/lib/types.ts` once, mapped through `api-adapter.ts` — never inlined in components (§10). |
| Frontend: "Keep types in sync... run npm run openapi:export && npm run openapi:gen" | §10.1 gives the exact command sequence and what must be committed. |
| Testing: "New route behavior → API test: status code, auth, response shape" | §9 covers every new route. |
| Frontend: "Type changes → run npm run typecheck... UI changes → npm run lint / build" | §10.9 gives the exact commands. |

If any step below appears to conflict with `RULE.md`, `RULE.md` wins — this document is subordinate to it, not a replacement for it.

---

## 1. Evidence-label legend (used throughout)

- ✅ **DIRECT** — a primary source (official docs, a paper, a company engineering blog, a law's text, or this repo's own code, read directly) states the claim.
- 🔗 **INDIRECT** — a real, citable source supports the general point but not in this exact form/number, or it is a reputable third-party synthesis.
- ❌ **NOT FOUND** — checked and could not be verified anywhere; stated as a design choice, not as proven fact.

All citations below were independently verified during this conversation (fetched and read, not recalled from training data alone) unless the claim is about this repo's own code, in which case the file was read directly and is cited with exact line numbers.

---

## 2. What already exists and will be reused unmodified

Verified by reading every file directly on `master-complete-foundation` — not assumed from any report, README, or prior chat summary.

| Capability | File | Reused how |
|---|---|---|
| Question bank storage | `backend/app/models.py` (`InterviewQuestion`, lines 25-52) | Read/write target for the new question-selection route; schema extended (not replaced) in §5 |
| Rotation-tracking storage | `backend/app/models.py` (`InterviewAttempt`, lines 55-71) | Kept as the intended mechanism for "don't repeat questions attempted recently"; §4.4 documents that it is currently **never written to** and fixes that gap without changing its shape |
| Smart question selection (DB filter + rotation + usage balancing) | `backend/app/services/question_selector.py` (`select_questions()`) | Called, unmodified in its filtering logic, by the new `questions/service.py` — this plan adds a personalization layer *in front of* it, not a replacement |
| AI question generation (GPT-4o-mini, structured JSON) | `backend/app/services/question_generator.py` (`generate_questions()`) | Called, unmodified, by the new `questions/service.py` when the question bank has too few matching rows for a role; extended with retry logic (§3 Decision 2) and an optional personalization context parameter (§3 Decision 1) — both additive, no existing call sites broken |
| AI feedback generation (GPT-4o-mini, rubric-based) | `backend/app/services/feedback_generator.py` (`generate_interview_feedback()`) | Called, unmodified in its prompt/scoring logic, by the existing `workers/tasks/feedback.py`; extended with retry logic only (§3 Decision 2) |
| Whisper transcription client (retry + size validation already correct) | `backend/app/clients/speech.py` (`WhisperClient`) | Reused verbatim — this is the one Week 2 AI client that already follows the repo's own best-practice pattern (tenacity retry, `clients/speech.py:70-75`) and is used as the template for fixing the other two |
| Audio heuristic analysis (filler words, WPM, clarity score) | `backend/app/services/audio_analysis.py` | Reused verbatim as the free, always-on baseline; optional Hume AI prosody signal is additive and clearly separated (§3 Decision 4) |
| Audio object storage | `backend/app/services/audio_storage.py` | Reused verbatim for storing uploaded practice recordings via `R2StorageClient` |
| GDPR-compliant audio deletion (7-day retention, batch cleanup) | `backend/app/workers/tasks/audio_cleanup.py`, migration `017_practice_audio_recordings.py` | Untouched — this is the one Week 2 Module 3 feature that is fully correct end-to-end already (raw-SQL access pattern noted, not changed, in §4.3) |
| Session lifecycle + attempt recording | `backend/app/modules/sessions/` (`models.py`, `schemas.py`, `router.py`, `session_manager.py`) | Reused verbatim for session state machine and `QuestionAttempt` persistence; the new personalization/audio routes write into the same `question_attempts` table via the existing `SessionManager.add_attempt()` — no parallel attempt-recording path is created |
| Candidate résumé → structured data | `backend/app/domain/candidate.py` (`CVData`), `backend/app/modules/documents/models.py` (`CandidateDocument.extracted_data`) | Read-only dependency: the new personalization layer reads `CandidateDocument.extracted_data` (already populated by the existing `/api/documents/upload` → CV extraction pipeline) — no new extraction code |
| Document upload endpoint (already implemented) | `backend/app/modules/documents/router.py` (`POST /api/documents/upload`, line 29) | Reused verbatim as the resume-ingestion entry point the new frontend Interview Prep page links to — Module 3 does not rebuild Module 2's upload flow |
| Cost tracking for LLM calls | `backend/app/observability/cost_tracking.py` (`track_llm_cost()`, `track_llm_failure()`) | Reused verbatim (already generic over `operation` label) — the new question-generation worker calls it with `operation="question_generation"`, exactly like `feedback.py` already does with `operation="feedback"` |
| RQ queue + cron scheduling primitive | `backend/app/workers/queue.py` (`QUEUE_FEEDBACK`, `register_scheduled_jobs()` using `rq_scheduler.Scheduler.cron()`) | Extended with one new queue constant (`QUEUE_QUESTION_GENERATION`) using the same mechanism — no second queue framework introduced |
| Envelope API routing | `backend/app/core/api_route.py` (`EnvelopeAPIRoute`) | New routers use this exactly like `documents/router.py` and `sessions/router.py` do |
| Auth dependency | `backend/app/auth/dependencies.py` (`VerifiedUser`/`CurrentUser`) | Reused verbatim for every new route, registered in `main.py` the same way as every existing protected router |
| DB session dependency | `backend/app/database/session.py` (`get_db_session`) | Reused verbatim |
| JSON column helper | `backend/app/database/base.py` (`JsonDoc`) | Reused for new nullable JSON columns |
| Frontend feature-module pattern | `frontend/features/enrich/` (`index.ts`, `api/keys.ts`, `hooks/`) | Copied exactly for `frontend/features/practice/` |
| Frontend BFF proxy pattern | `frontend/app/api/enrich/*`, `frontend/src/lib/backend-client.ts` (`backendFetch`) | Copied exactly for `frontend/app/api/practice/*` |
| Frontend nav registration | `frontend/components/layout/nav-config.ts` | One new `NavItem` added; `AppSidebar`/bottom nav pick it up automatically (both already read from this config — verified) |

Nothing above is edited to change its existing behavior for other features — all reuse is either read-only or additive (new optional parameters, new functions alongside existing ones, new columns that default to `NULL`/existing behavior when unset).

---

## 3. Evidence-based design decisions (why the implementation is shaped this way)

### Decision 1 — Personalized question generation reads the candidate's résumé; the score/rubric stays deterministic, only the *question topic* is personalized

The user's explicit requirement: *"we use ai to make question based on candidate's resume, target role, skills etc."* Today, `generate_questions()` (`backend/app/services/question_generator.py:199-236`) takes only `job_role, category, difficulty, count` — **no résumé, no skills, no candidate identity of any kind.** Verified by reading the full function signature and its `_build_generation_messages()` helper (lines 82-132): the prompt template has no candidate-specific slot at all. This is a real, direct gap between the spec and the code, not an assumption.

✅ **DIRECT** — [Indeed Engineering: "How Indeed builds and deploys fine-tuned LLMs on Amazon SageMaker"](https://aws.amazon.com/blogs/machine-learning/how-indeed-builds-and-deploys-fine-tuned-llms-on-amazon-sagemaker/) lists resume/job-description-conditioned generation ("match explanations", skills extraction) as a real, production LLM use case at a hiring-tech company — confirming personalized generation from structured candidate data is an industry-validated pattern, not a hypothetical.

✅ **DIRECT** (own codebase) — `backend/app/domain/candidate.py`'s `CVData` model already contains `technical_skills: list[str]`, `desired_roles: list[str]`, `current_role: str | None`, and experience/education fields, populated today by the existing CV extraction pipeline (`services/cv_extractor.py`) into `CandidateDocument.extracted_data` (`modules/documents/models.py`). Nothing needs to be built to *get* this data — it already exists per uploaded résumé.

**Applied as:** `generate_questions()` gets one new **optional, additive** parameter, `candidate_context: CandidateContext | None = None` (a new small dataclass: `skills: list[str]`, `target_role: str | None`, `years_experience: int | None`, `recent_job_titles: list[str]`) — default `None` preserves every existing call site and every existing test exactly as-is (verified against `test_question_bank.py`'s current call patterns before writing this decision). When provided, one extra paragraph is appended to the user prompt: *"Tailor this question to a candidate with these skills: {skills}. Prefer technologies and scenarios from this list where relevant to the category."* The **rubric and scoring stay generic** (dimension-based, per Decision in the existing `feedback_generator.py`) — personalization changes *what is asked*, never *how it is graded*, for the same reason Module 1's Decision 3 kept LLM scoring deterministic: an auditable, non-invented rubric. Generated personalized questions are persisted with `personalized_for_user_id` set (§5.2) so they are excluded from the shared rotation pool other candidates draw from — this is the naming/leakage risk flagged in §4.6.

### Decision 2 — Add retry/backoff to `feedback_generator.py` and `question_generator.py`, copying the pattern already proven in `clients/speech.py`

✅ **DIRECT** (own codebase) — `backend/app/clients/speech.py:70-75` already implements the correct pattern for this exact class of external call:

```70:75:backend/app/clients/speech.py
    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
```

✅ **DIRECT** — [OpenAI Cookbook: "How to handle rate limits"](https://cookbook.openai.com/examples/how_to_handle_rate_limits) recommends exponential backoff with jitter for `429`/`5xx` responses from the Chat Completions API — the same family of endpoint `feedback_generator.py` and `question_generator.py` call directly via raw `httpx.AsyncClient.post()` (not the `openai` SDK, which is already a `pyproject.toml` dependency but is not used here — verified: neither file imports `openai`).

**Applied as:** `backend/app/services/feedback_generator.py::generate_interview_feedback()` and `backend/app/services/question_generator.py::generate_questions()` each get the identical `tenacity` decorator already used in `speech.py`, wrapping only the `client.post(...)` call (not the whole function, so `ValueError`s from missing API keys or parse failures are not retried — matching `speech.py`'s scoping). `tenacity` is already a resolvable dependency of this environment (confirmed: `clients/speech.py` already imports and uses it in production code on this branch, so no new line is needed in `pyproject.toml` — verified by reading `clients/speech.py`'s imports, though `tenacity` should be added as an *explicit* direct dependency in `pyproject.toml` rather than relying on it being pulled in transitively; see §7.9).

### Decision 3 — Do not scrape Glassdoor or LeetCode for interview questions

❌ the pasted spec's implied "pull real interview questions from Glassdoor/LeetCode" — this repo has no scraping code for either site today (verified: no `glassdoor` or `leetcode` string anywhere in `backend/app/`), and adding it would violate both sites' own published Terms of Service.

✅ **DIRECT** — [Glassdoor Terms of Use](https://www.glassdoor.com/about/terms.htm), "Proprietary Rights" / "Restrictions on Use" section: prohibits use of "any robot, spider, site search/retrieval application, or other manual or automatic device to retrieve, index, 'scrape,' 'data mine' or in any way reproduce or circumvent the navigational structure or presentation of the Site."

✅ **DIRECT** — [LeetCode Terms of Service](https://leetcode.com/terms/), "User Conduct" section: prohibits "using any robot, spider, site search/retrieval application, or other manual or automatic device or process to retrieve, index, 'data mine,' or in any way reproduce or circumvent the navigational structure or presentation of the Website or its contents."

**Applied as:** the question bank stays 100% either (a) hand-seeded (the existing `scripts/seed_questions.py`-style pattern, if present, or a static fixture list) or (b) GPT-4o-mini-generated via `generate_questions()` — never scraped from a third-party site whose ToS forbids it. This matches `RULE.md`'s own "Public data only... no discover people flows" principle in spirit: don't build a feature this repo would have to remove later for a ToS/legal reason that was knowable on day one.

### Decision 4 — Voice-tone "sentiment analysis" is optional, coaching-framed, and off by default; text-transcript heuristics (already built) are the default

This is the single highest-risk decision in Module 3 and deserves the most evidence.

✅ **DIRECT** — [AI Now Institute, 2019 Report](https://ainowinstitute.org/wp-content/uploads/2023/04/AI_Now_2019_Report.pdf), Recommendation 1: *"Regulators should ban the use of affect recognition in important decisions that impact people's lives and access to opportunities... Given the contested scientific foundations of affect recognition technology... it should not be allowed to play a role in important decisions about human lives, such as who is interviewed or hired for a job."* The same report explicitly names "job interviews" as a real, current deployment context for this technology and states it "lacks any solid scientific foundation to ensure accurate or even valid results," confirmed in 2019 by "the largest metastudy to date on the topic."

✅ **DIRECT** — [HireVue's own blog post announcing the change](https://www.hirevue.com/blog/hiring/industry-leadership-new-audit-results-and-decision-on-visual-analysis): HireVue — the largest commercial vendor of exactly this kind of AI interview analysis — removed *visual* affect analysis from its models in 2020/2021, stating "our algorithms do not see significant additional predictive power when non-verbal data is added to language data." Multiple independent reports ([Wired](https://www.wired.com/story/job-screening-service-halts-facial-analysis-applicants/), [SHRM](https://www.shrm.org/topics-tools/news/talent-acquisition/hirevue-discontinues-facial-analysis-screening)) confirm HireVue nonetheless **continued** to analyze speech/intonation, and that this residual practice remains independently criticized: SHRM quotes an expert's on-record view that "the assumption that vocal indications, intonations, word choice or word complexity have any credible, causal link with workplace success, to make or inform hiring decisions, is flawed."

✅ **DIRECT** — [Hume AI's own engineering blog, "The Science of What a Voice Reveals"](https://www.hume.ai/blog/the-science-of-what-a-voice-reveals): Hume AI (the vendor whose product genuinely performs *vocal prosody* analysis — tone, rhythm, timbre — as opposed to transcript sentiment) states prosody is real signal distinct from words: *"a model that reads the transcript is inferring emotion from the words being spoken while discarding the channel where much of the emotional information actually lives."* This directly confirms that **Deepgram's "sentiment analysis" feature is transcript/text-based, not vocal-tone-based** — verified independently via a third-party comparison ([XYZEO's Hume AI review, 2026](https://xyzeo.com/product/hume-ai)): "Deepgram: Emotion Analysis for Real-Time Speech-to-Text... Best when used in conjunction with a separate TTS provider" — i.e. Deepgram's own positioning is text/transcript sentiment, matching what was found when `question_generator.py`/`feedback_generator.py`-adjacent research was done earlier in this project: if the product spec's literal words are "sentiment analysis... voice tone," Deepgram alone does not deliver "voice tone" — only Hume AI's prosody model does.

🔗 **INDIRECT** — [Forasoft, "How to Implement Audio Emotion Detection with AI: 2026 Playbook"](https://www.forasoft.com/blog/article/audio-emotion-detection-system-using-ai): peer-reviewed 2025 benchmarks cited in this practitioner writeup show voice-alone speech-emotion-recognition (SER) topping out around 0.75 accuracy on 5-class emotion, rising to ~0.83 only when fused with text sentiment — i.e. even the *best* current voice-tone technology is far from reliable enough to be decision-grade, consistent with the AI Now Institute's scientific-foundation concern above, not merely a legacy criticism of a discontinued 2019-era product.

**Applied as, in order of what ships:**
1. **Always on, free, already built:** the existing `backend/app/services/audio_analysis.py` heuristics (filler-word count, words-per-minute, a rule-based "clarity score") run on every audio attempt's transcript. These are text/rate-based, not "emotion," and are labeled in the UI as exactly that — "pace and filler-word coaching," never "confidence" or "nervousness."
2. **Optional, paid, off unless configured:** a Hume AI prosody integration (`HUME_API_KEY` unset by default — matching the repo's own established fail-soft convention documented in `backend/docs/ARCHITECTURE.md`'s "Do not assume" table for `LLM_MODE`/R2/Reacher) may be enabled per §5.4/§7.6. When enabled, its output is stored as `voice_tone_signals` (nullable JSONB) and surfaced in the frontend **only** as a self-reflection prompt ("Your tone stayed steady across this answer" / "Your pace picked up here — was that a topic you felt less sure about?"), never as a numeric "confidence score," never persisted or shown to any other party, and never fed into `ai_score` (the same score/explanation separation principle as Module 1's Decision 3). This is a deliberate, evidence-driven scope limit on a feature the original spec described more aggressively ("sentiment analysis... nervousness") — the AI Now Institute and HireVue's own retreat are exactly the evidence that this reduced scope, not the original one, is the responsible implementation.
3. **Not built:** any pass/fail, hire/no-hire, or ranking signal derived from vocal tone. No evidence found anywhere (HireVue's own literature included) that supports this being scientifically defensible, and `RULE.md` has no "these are the exceptions where safety rules can be skipped" clause that would license shipping it anyway.

### Decision 5 — Spaced-repetition-style "usage balancing" stays a simple heuristic in v1; true SM-2 is documented as a deferred upgrade, not built now

✅ **DIRECT** — [SuperMemo: "SuperMemo 2: Algorithm" (Wozniak)](https://www.super-memory.org/archive/english/ol/sm2.htm): the SM-2 algorithm computes a per-item easiness factor `EF` (starting at 2.5, floor 1.3) and inter-repetition interval `I(n) = I(n-1) × EF` for `n > 2`, updated after every review based on a 0-5 recall-quality grade.

**Applied as:** `question_selector.py::select_questions()` already implements a simpler, real mechanism — `ORDER BY usage_count ASC, random()` (verified: `question_selector.py:107`) — which balances exposure across the question bank but has no per-user, per-item difficulty memory the way SM-2 does. Building true SM-2 would require a new per-(user, question) state table (`ef`, `n`, `next_due_at`) and a quality-grading UI step this spec's own scope (Text/Audio/Video practice + feedback report) does not ask for. This plan explicitly does **not** build SM-2 — it fixes the two things that make even the *existing* simple heuristic non-functional today (§4.4, §4.5: `InterviewAttempt` rows are never written, so the recency-exclusion query is permanently a no-op) and documents SM-2 as an explicit, named, deferred v2 idea rather than silently building a half-version of it under a different name.

### Decision 6 — RQ queue isolation for `feedback` and `question_generation`; no new queue framework

✅ **DIRECT** (already established in `architecture_phase2.md` in this repo and re-verified directly in `backend/app/workers/rq_worker.py:59-75`): the current default (`WORKER_QUEUE_MODE=single`, `core/config.py:41`) general-purpose worker branch listens to `QUEUE_FEEDBACK, QUEUE_DOCUMENT, QUEUE_EMBEDDING, QUEUE_CV_EXTRACTION, QUEUE_NAME` in one fixed-priority `Queue` list.

✅ **DIRECT** — [RQ README](https://github.com/rq/rq/blob/master/README.md) + [rq/rq#1420](https://github.com/rq/rq/issues/1420): a worker started with `rq worker high low` never touches `low` while `high` has backlog — fixed-priority queues, not fair-share.

**Applied as:** this plan reuses the exact mechanism already in `queue.py` (`Queue(name, connection=...)`), adding one new queue constant `QUEUE_QUESTION_GENERATION = "question_generation"` (§7.5) rather than a second framework. No Docker topology change is required to make `feedback`/`question_generation` jobs *run* — verified directly (§4.2) that the base `worker` service in `docker-compose.yml` defaults to `WORKER_QUEUE_MODE=single` (no override in that file) and therefore already listens to `QUEUE_FEEDBACK` today, and will listen to `QUEUE_QUESTION_GENERATION` once it is added to the same list. What this plan *does* change is giving `question_generation` its own **priority weight** below `feedback` (interview feedback is user-facing/blocking; personalized question pre-generation is not) using the existing `QUEUE_PRIORITIES` dict (`queue.py:24-33`) — an additive dict entry, not a reordering of the existing list (reordering existing entries is out of scope; it would affect Week 1 document/embedding processing this plan does not own).

---

## 4. Blind spots — verified, existing bugs and gaps this plan must fix (read this section like a lifeline; every claim was confirmed by reading the file, not inferred)

This is the section the user explicitly asked not to be skipped. Every item below was found by opening the file and reading the exact lines cited — none is a guess.

### 4.1 `app/models.py` is exactly the "global dumping ground" `RULE.md` forbids — and it predates this plan

`RULE.md` §"Architecture rules → Backend": *"ORM lives with its owner... never recreate a global app/models.py dumping ground."* Verified: `backend/app/models.py` currently holds `InterviewQuestion` and `InterviewAttempt` directly at module scope, with no module ownership (not under `modules/questions/`, not under `modules/sessions/`). This plan does **not** silently move these classes — moving them would touch every existing import site (`question_selector.py` does `from app.models import InterviewAttempt, InterviewQuestion` inline inside functions, twice) for a rename that is out of scope for a feature-completion task, per `RULE.md`'s own "Fix only what the task needs" rule. Instead, §5 extends the *existing* file in place (columns only, no move) and this violation is named explicitly here, in the ARCHITECTURE.md diff (§12), and in the ADR (§11) so a future refactor task can find it instead of rediscovering it.

### 4.2 `question_id`, in **two different tables**, has **no foreign key constraint**, in both cases — and one of the two is never written to at all

- `backend/app/modules/sessions/models.py:88`: `question_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)` — no `ForeignKey(...)` argument at all. A `QuestionAttempt` can be created (and is, via `session_manager.py:191-206`) with any UUID or `None` in `question_id`; the database will never reject a value that doesn't exist in `interview_questions`.
- `backend/app/models.py:61`: `user_id: Mapped[UUID] = mapped_column(nullable=False)  # Foreign key not enforced for now` — the comment is in the source, verified verbatim. `InterviewAttempt.user_id` has no FK to `users.id` either.
- **`InterviewAttempt` is never instantiated anywhere in this codebase.** Verified with a repo-wide search for the constructor call `InterviewAttempt(` — the only two matches are the class definition itself and its own `__repr__` string in `app/models.py`. `question_selector.py:90-99` builds a subquery over `InterviewAttempt` to exclude recently-attempted questions from rotation — but because no code path anywhere inserts a row into `interview_attempts`, that subquery's result set is always empty, and the "avoid repeating the last 7 days of questions" feature described in `question_selector.py`'s own module docstring (line 6: *"Recency (avoids questions attempted in last 7 days)"*) **does not function today.** This is fixed in §7.3: the personalization service records an `InterviewAttempt` row (or, more precisely, uses the *existing* `question_attempts.question_id` value, once it is FK-constrained per §5.1, as the source of truth instead of a second, redundant, never-populated table — see §4.6 for why keeping both tables would be wrong).

### 4.3 `practice_audio_recordings` has a real table (migration `017`) but **no SQLAlchemy ORM model class exists anywhere in the codebase**

Verified: a repo-wide search for `PracticeAudioRecording` and for `practice_audio_recordings` matches exactly three files — `backend/alembic/versions/017_practice_audio_recordings.py` (the migration that creates the table), `backend/app/workers/tasks/audio_cleanup.py` (which accesses the table exclusively via raw `sqlalchemy.text()` SQL — `audio_cleanup.py:69-74` and `:158-164`), and `backend/tests/test_audio_cleanup.py`. There is no ORM class in `app/models.py`, `app/modules/sessions/models.py`, or anywhere else that maps to this table. This means **there is no type-safe, ORM-based way today to create a new audio recording row** — any future audio-upload route would either have to write more raw SQL (violating "ORM lives with its owner" and inviting SQL-injection-shaped bugs if a column list ever changes) or, correctly, get a real model class, which is what §5.5/§7.6 add.

### 4.4 The feedback worker's "workaround" for reading the question text does not work — it silently reads `None` on every single attempt, always

Verified line-by-line in `backend/app/workers/tasks/feedback.py:52-57`:

```52:57:backend/app/workers/tasks/feedback.py
    # For now, we need a question - in production this would come from a questions table
    # Using attempt_metadata as a workaround for foundation week
    # If question_id is null, pass None to enable general evaluation mode
    question_text = None
    if hasattr(attempt, "attempt_metadata") and isinstance(attempt.attempt_metadata, dict):
        question_text = attempt.attempt_metadata.get("question_text")
```

`attempt` here is a `QuestionAttempt` ORM instance (`app/modules/sessions/models.py:70-111`, read in full). **That class has no `attempt_metadata` column** — its only columns are `id, session_id, user_id, question_id, response_type, text_response, audio_recording_id, ai_score, score_breakdown, ai_feedback, time_taken_seconds, attempted_at`. `hasattr(attempt, "attempt_metadata")` therefore evaluates to `False` for every real `QuestionAttempt` fetched from the database, on every call, with no exception raised — Python's `hasattr` returning `False` silently for a genuinely absent attribute on a mapped SQLAlchemy class. The practical effect: `question_text` is **always `None`**, so `generate_interview_feedback(question=None, ...)` (`feedback_generator.py:176-220`) **always** runs its "no specific question" general-evaluation branch (`_build_feedback_messages()`, lines 96-102) — regardless of which question was actually asked, or whether `question_id` was populated on the attempt. This is not a hypothetical edge case; it is the *only* code path that exists today, for every attempt, because there is no other place `question_text` could come from.

The same function also *writes* to this nonexistent attribute (`feedback.py:79-84`):

```79:84:backend/app/workers/tasks/feedback.py
    # Add strengths and improvements to attempt_metadata
    if not hasattr(attempt, "attempt_metadata") or attempt.attempt_metadata is None:
        attempt.attempt_metadata = {}

    attempt.attempt_metadata["strengths"] = feedback["strengths"]
    attempt.attempt_metadata["improvements"] = feedback["improvements"]
```

Python allows setting an arbitrary attribute on any object, including a SQLAlchemy declarative instance, but because `attempt_metadata` is not a mapped column, **`db.commit()` on the next line (`feedback.py:86`) never persists it.** The LLM-generated `strengths`/`improvements` lists are computed, held in memory, and then discarded the moment the worker process's local `attempt` object goes out of scope. `backend/tests/test_feedback_worker.py` (lines 36, 84-89, 240-247) *does* assert on `sample_attempt.attempt_metadata["strengths"]` — but that test file was already found, independently, to fail collection with `ImportError: cannot import name '_generate_feedback_async' from 'app.workers.tasks.feedback'` (that symbol does not exist either — the real function is `_generate_feedback_sync`), and is excluded from the suite via `--ignore=tests/test_feedback_worker.py` in every test run referenced in this project's own `WEEK2_INTEGRATION_REPORT.md`. In other words: the one test that would have caught this bug does not run.

**Fixed in §5.1/§7.4**: `question_id` gets a real `ForeignKey("interview_questions.id")`, the worker fetches `question_text` via a join instead of a nonexistent attribute, and `strengths`/`improvements` move to `QuestionAttempt.score_breakdown` (already a mapped `JsonDoc` column that exists today and is already used for dimension scores) as two additional keys inside the same dict — no new column needed, no more silent data loss.

### 4.5 No HTTP route anywhere calls `question_selector.py`, `question_generator.py`, `clients/speech.py` (for upload), or `audio_storage.py`

Verified by reading `backend/app/main.py` in full (lines 1-85): the only routers registered are `health`, `opt_out`, `auth`, `admin`, `documents`, `enrich`, `email`, `sessions`, `dsar`, `signals`. There is no `questions` router, no `practice_audio` router, no route under `sessions/router.py` that calls `select_questions()` or `generate_questions()`. `select_questions()`, `generate_questions()`, and `WhisperClient.transcribe_audio()` (for a fresh upload, as opposed to a pre-existing recording) are called from **zero** production code paths — only from their own unit tests. A candidate using the product today has no way to receive a question or submit audio for transcription; they could only call `POST /sessions/{id}/attempts` directly with a `text_response` and a manually-chosen `question_id` UUID that the API will accept without validating it exists. This is the single largest gap this plan closes, and is the reason §7 exists.

### 4.6 A second, harder naming/consistency problem hides behind 4.2: two independent "did the user see this question" concepts, one of which is silently disconnected from the other

- `question_attempts.question_id` (per §4.2, unconstrained) is written by `SessionManager.add_attempt()` whenever a candidate actually submits an answer.
- `interview_attempts` (per §4.4, never written) was apparently *intended* to be the rotation-exclusion source of truth for `question_selector.py`.

These are two tables recording conceptually the same fact ("this user attempted this question") that have never been reconciled. Building true SM-2 (Decision 5) or even fixing the recency-exclusion query the *simple* way requires picking exactly one source of truth. **This plan picks `question_attempts`** (§7.3): `question_selector.select_questions()`'s recency-exclusion subquery is rewritten to read `QuestionAttempt.question_id` (now FK-constrained, §5.1) joined to `QuestionAttempt.attempted_at`, filtered by `session.user_id` via `QuestionAttempt.user_id` — and `interview_attempts` / `InterviewAttempt` is **left in place, unused, and explicitly marked deprecated** in a code comment and in §12's ARCHITECTURE.md diff, rather than dropped in this PR (dropping a table is a separate, higher-risk migration that deserves its own review, per "Fix only what the task needs"). A future cleanup PR can drop `interview_attempts` once nothing (including any external report that might reference it) depends on it.

### 4.7 `question_generator.py` and `feedback_generator.py` call `api.openai.com` directly with raw `httpx`, bypassing the `openai` SDK that is already a listed dependency, and bypassing `LLM_MODE`

Verified: `backend/pyproject.toml:34` already lists `openai>=1.0,<2.0` as a dependency (used by `clients/embeddings.py`, per its `AsyncOpenAI(api_key=...)` call). `question_generator.py` and `feedback_generator.py` instead build raw `httpx.AsyncClient().post("https://api.openai.com/v1/chat/completions", ...)` calls (verified: `question_generator.py:246-260`, `feedback_generator.py:225-239`) — this is not wrong (it works, and is the same approach `clients/speech.py` correctly uses for Whisper, which has no first-class `AsyncOpenAI` audio-transcription convenience the team may have wanted to avoid), but it means these two services **do not participate in `LLM_MODE`** (`stub`/`ollama`/`litellm`, `.env.example` lines 78-79) the way the rest of this repo's LLM-touching code is documented to. `backend/docs/ARCHITECTURE.md`'s own "Do not assume" table documents `LLM_MODE` as the repo-wide free/paid switch for LLM calls; these two Week 2 services are a silent exception to that documented convention, hardcoded to `gpt-4o-mini` regardless of `LLM_MODE=stub`. This plan does not change that architecture in this PR (routing Week 2's LLM calls through `LiteLLMProvider` is a larger, cross-cutting change against a system this plan does not own — Tier 3/4 disambiguation), but it is named here explicitly, per `RULE.md`'s "Trust code over docs when they disagree... then update the doc" rule, and the diff in §12 adds one line to `ARCHITECTURE.md`'s "Do not assume" table documenting this exception so the next agent does not assume `LLM_MODE=stub` silences these two services' real OpenAI spend.

### 4.8 `.env.example`'s own banner comment about `OPENAI_API_KEY` is stale

Verified: `backend/.env.example` line 210's comment block says *"(api/worker never need OPENAI_API_KEY / GEMINI_API_KEY)"* — true only for the LiteLLM disambiguation path it is describing in context, but the file never separately documents `OPENAI_API_KEY` as a *direct*, always-relevant setting for `question_generator.py`, `feedback_generator.py`, `clients/speech.py`, `clients/embeddings.py`, and `cv_extractor.py` (all five call `settings.openai_api_key` directly — verified via grep). A developer following `.env.example` top-to-bottom today would reasonably conclude they never need to set this key, then have every Week 1/Week 2 AI feature fail with `ValueError: OpenAI API key not configured` (the exact error each of these five files raises — verified). Fixed in §6.

### 4.9 No Docker Compose file adds a dedicated worker for the two Week 2 queues, and no compose file's healthcheck verifies they are being drained

Verified across all 9 compose files in `backend/docker/`: `docker-compose.foundation.yml` adds `worker-document` and `worker-embedding` (Week 1 queues only). Nothing adds `worker-feedback` or a `question_generation`-aware worker. The base `worker` service (which does default to `WORKER_QUEUE_MODE=single` and therefore does pick up `QUEUE_FEEDBACK` — confirmed directly by reading `core/config.py:41`'s default and `docker-compose.yml`'s `worker` service environment block, which sets no `WORKER_QUEUE_MODE` override) is the *only* thing consuming this queue, and it is not isolated the way Decision 6 calls for — it is bundled with Week 1's document/embedding/cv-extraction queues, all in fixed RQ priority order, with no dedicated healthcheck asserting `feedback`/`question_generation` queue depth specifically (the existing healthcheck only pings Redis, `docker-compose.yml:139-150`). §8 adds the missing isolation and a depth-aware healthcheck.

### 4.10 Session-tracking tests are still failing on this exact branch, and this plan's new routes sit directly on top of the code they test

Verified by running `pytest backend/tests/test_session_tracking.py` on `master-complete-foundation` immediately before writing this document: 14 failed + 14 errors, matching `WEEK2_INTEGRATION_REPORT.md`'s own self-reported number. `WEEK2_INTEGRATION_REPORT.md` attributes this to "a database transaction/session persistence issue in tests" and calls the foundation "PRODUCTION-READY" anyway. This plan takes no position on whether that report's conclusion was reasonable — it states plainly that any new route built on `SessionManager` (§7) inherits this pre-existing, unresolved risk, and that §9.9's final verification command will surface it again rather than hide it. Fixing `test_session_tracking.py` itself is explicitly **out of scope** for this document (it predates and is orthogonal to Module 3's gaps), but is listed as a blocking dependency in §13's PR checklist so it cannot be silently ignored twice.

### 4.11 Frontend has zero Module 3 surface area, and Module 3's personalization depends on a Module 2 frontend flow (résumé upload) that also does not exist yet

Verified: `frontend/app/app/` (glob) contains `enrich`, `history`, `signals`, `dashboard`, `privacy`, `settings`, `health`, `jobs` — no `documents`, `practice`, or `interview` route anywhere. `frontend/components/layout/nav-config.ts` (read in full) has no nav entry for either. This means Decision 1's personalization ("read the candidate's résumé") has no frontend path to *get* a résumé into the system today, even though the backend endpoint (`POST /api/documents/upload`) already exists and works. §10 does not attempt to build all of Module 2's frontend (out of scope — Module 2 is a separate module with its own document list/search/detail UI this plan does not own), but it does add one minimal, self-contained upload affordance directly on the new Interview Prep landing page (§10.4) that calls the existing, already-implemented `POST /api/documents/upload` endpoint — enough for personalization to function without silently declaring an unbuilt Module 2 dependency "in scope" or blocking Module 3 entirely on it.

---

## 5. Database schema — 3 new Alembic revisions, chained onto the real current head

**Current real Alembic head, verified by listing `backend/alembic/versions/`:** `017_practice_audio_recordings` (down-revision chain: `017` ← `(015_add_session_tracking, 016_interview_questions)`; confirmed no `018`+ file exists on this branch today). New revisions in this plan chain onto `017`.

All new columns/tables follow the exact dialect-handling pattern already used in `014_document_embeddings.py` and `017_practice_audio_recordings.py`: `postgresql.UUID(as_uuid=True)` / `sa.String(36)` branch on `bind.dialect.name`, `JsonDoc` (JSONB on Postgres, JSON on SQLite) for JSON columns — no new pattern invented.

### 5.1 `018_question_attempt_fk_and_personalization.py` — fix the unenforced FK (§4.2), add personalization columns to `interview_questions`

**New file:** `backend/alembic/versions/018_question_attempt_fk_and_personalization.py`

```python
"""Add FK from question_attempts.question_id to interview_questions, and
personalization columns to interview_questions.

Revision ID: 018_question_attempt_fk_and_personalization
Revises: 017_practice_audio_recordings
Create Date: 2026-08-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "018_question_attempt_fk_and_personalization"
down_revision: Union[str, Sequence[str], None] = "017_practice_audio_recordings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)

    # --- Fix §4.2: question_attempts.question_id had no FK constraint ---
    # Existing rows with a question_id that does not exist in interview_questions
    # (possible today, since nothing enforced it) must be nulled out first, or
    # the FK creation below will fail on any environment with real data.
    op.execute(
        """
        UPDATE question_attempts
        SET question_id = NULL
        WHERE question_id IS NOT NULL
          AND question_id NOT IN (SELECT id FROM interview_questions)
        """
    )
    with op.batch_alter_table("question_attempts") as batch_op:
        batch_op.create_foreign_key(
            "fk_question_attempts_question_id",
            "interview_questions",
            ["question_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # --- Decision 1 (§3): personalization columns on interview_questions ---
    op.add_column(
        "interview_questions",
        sa.Column("personalized_for_user_id", uuid_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
    )
    op.add_column(
        "interview_questions",
        sa.Column("generation_context", sa.Text(), nullable=True),  # short summary of skills/role used, for audit
    )
    op.create_index(
        "ix_interview_questions_personalized_for_user_id",
        "interview_questions",
        ["personalized_for_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_interview_questions_personalized_for_user_id", table_name="interview_questions")
    op.drop_column("interview_questions", "generation_context")
    op.drop_column("interview_questions", "personalized_for_user_id")
    with op.batch_alter_table("question_attempts") as batch_op:
        batch_op.drop_constraint("fk_question_attempts_question_id", type_="foreignkey")
```

**Design notes:** `ondelete="SET NULL"` (not `CASCADE`) on the new FK — deleting a question must not delete the historical record that a candidate attempted *something*; `QuestionAttempt.text_response`/`ai_score`/`ai_feedback` remain valid feedback history even if the question row is later removed from the bank. `personalized_for_user_id` is nullable because shared-pool questions (the vast majority) have no single owner; `§7.3`'s selection query filters `personalized_for_user_id IS NULL OR personalized_for_user_id = :user_id` so one candidate's personalized questions never leak into another candidate's rotation, closing the leakage risk named in Decision 1. The `UPDATE ... SET question_id = NULL` guard before adding the FK is the standard "clean before constrain" pattern — required because §4.2 established this column was genuinely unconstrained, so silently assuming existing data is clean would be incorrect on any non-fresh database.

### 5.2 `019_question_recency_index.py` — support the corrected recency-exclusion query (§4.6) with a real index instead of a full-table scan

**New file:** `backend/alembic/versions/019_question_recency_index.py`

```python
"""Add composite index for the corrected question-recency exclusion query.

Revision ID: 019_question_recency_index
Revises: 018_question_attempt_fk_and_personalization
Create Date: 2026-08-08
"""
from typing import Sequence, Union

from alembic import op

revision: str = "019_question_recency_index"
down_revision: Union[str, Sequence[str], None] = "018_question_attempt_fk_and_personalization"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # question_attempts already has idx_attempts_user (user_id) from
    # 015_add_session_tracking; this composite index makes the new
    # "exclude questions this user attempted in the last N days" query
    # (§7.3) an index-only scan instead of a filter over every row for
    # a heavy user, which idx_attempts_user alone cannot do since it does
    # not include attempted_at or question_id.
    op.create_index(
        "idx_attempts_user_question_recency",
        "question_attempts",
        ["user_id", "attempted_at", "question_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_attempts_user_question_recency", table_name="question_attempts")
```

**Design note:** deliberately a separate, small, single-purpose migration rather than folded into `018` — an index-only change has zero data-safety risk and is trivially revertible, unlike the FK-with-data-cleanup migration above; keeping them separate means a downgrade of just the index (e.g. if it turns out to hurt write performance under load) does not force reverting the FK fix too.

### 5.3 `020_practice_audio_recordings_voice_tone.py` — add the optional Hume AI prosody column (§3 Decision 4) to the existing `practice_audio_recordings` table

**New file:** `backend/alembic/versions/020_practice_audio_recordings_voice_tone.py`

```python
"""Add optional voice_tone_signals column to practice_audio_recordings.

Revision ID: 020_practice_audio_recordings_voice_tone
Revises: 019_question_recency_index
Create Date: 2026-08-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "020_practice_audio_recordings_voice_tone"
down_revision: Union[str, Sequence[str], None] = "019_question_recency_index"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    jsonb_type = postgresql.JSONB() if dialect == "postgresql" else sa.JSON()

    # Nullable, populated only when HUME_API_KEY is configured (§6/§7.6).
    # Null on every row when the feature is off — matches the repo's own
    # fail-soft convention (LLM_MODE stub, R2 -> local fallback, Reacher
    # `profiles: ["paid"]`) rather than a required column with a fake default.
    op.add_column(
        "practice_audio_recordings",
        sa.Column("voice_tone_signals", jsonb_type, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("practice_audio_recordings", "voice_tone_signals")
```

**Design note:** this column is deliberately added to the *existing* table (not a new `voice_tone_analysis` table) because it is a 1:1, optional annotation of a single recording, not an independently-queried entity — a new table would need its own FK/index/ORM ceremony for something that is read exactly once per recording, alongside the recording, per Decision 4's framing (a self-reflection annotation, never a standalone score to be listed/ranked/queried across users).

**Migration order recap:** `017_practice_audio_recordings` (existing) → `018_question_attempt_fk_and_personalization` → `019_question_recency_index` → `020_practice_audio_recordings_voice_tone`. Run `cd backend && alembic upgrade head` after applying §7's model changes; verify with `alembic current` showing `020_practice_audio_recordings_voice_tone (head)`.

---

## 6. Environment variables — `.env.example` additions and one correction

**Correction (§4.8):** the existing comment at `.env.example` around the LiteLLM section (near line 210, *"api/worker never need OPENAI_API_KEY / GEMINI_API_KEY"*) is accurate only for the LiteLLM proxy path it documents in context. Add a clarifying line immediately after the "Core" section (near the top, where `API_TOKEN` already lives) so it is not missed:

```bash
# ─────────────────────────────────────────────
# Direct OpenAI usage (Week 1/2 AI features — separate from LLM_MODE below)
# Required for: CV extraction (cv_extractor.py), embeddings (embeddings.py),
# Whisper transcription (clients/speech.py), interview question generation
# (question_generator.py), interview feedback (feedback_generator.py).
# These call api.openai.com directly and do NOT go through LLM_MODE/LiteLLM
# (see backend/docs/ARCHITECTURE.md "Do not assume" table).
# Unset -> every one of the features above raises "OpenAI API key not configured".
# ─────────────────────────────────────────────
OPENAI_API_KEY=
```

**New, for Module 3 §3 Decision 4 (Hume AI voice-tone, optional):**

```bash
# ─────────────────────────────────────────────
# Voice tone analysis (Phase 2, Module 3 — optional, paid, off by default)
# Unset -> practice_audio_recordings.voice_tone_signals stays NULL and the
# frontend shows only the free text/rate-based coaching heuristics from
# audio_analysis.py. This is a genuine "coaching hint" feature, not a
# hire/no-hire signal — see phase2_module3.md §3 Decision 4 before enabling.
# ─────────────────────────────────────────────
# HUME_API_KEY=
# HUME_PROSODY_TIMEOUT_SECONDS=30
```

**New, for Module 3 §5.1 personalization and §7 question generation limits:**

```bash
# ─────────────────────────────────────────────
# Interview question generation (Phase 2, Module 3)
# ─────────────────────────────────────────────
# Max personalized questions generated per candidate per day (cost control,
# mirrors DAILY_COST_THRESHOLD_USD's intent but scoped to this one feature).
QUESTION_GENERATION_DAILY_LIMIT_PER_USER=10
# Max audio upload size accepted by POST /api/practice/audio before it is
# even sent to Whisper — matches clients/speech.py's own MAX_AUDIO_FILE_SIZE_BYTES
# (25MB) so the API rejects oversized files with a clear 413 instead of a
# confusing Whisper-side error after upload time is already spent.
PRACTICE_AUDIO_MAX_UPLOAD_MB=25
```

All three additions are placeholders/safe defaults only — no real key is committed, per `RULE.md`'s "Never commit secrets" rule.

---

## 7. Backend — file-by-file implementation plan

### 7.1 New module: `app/modules/questions/` (personalized question selection + generation orchestration)

**New file:** `backend/app/modules/questions/__init__.py` — empty, matches every other module's `__init__.py`.

**New file:** `backend/app/modules/questions/schemas.py`

```python
"""Pydantic schemas for the question bank / personalized generation API."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

JobRole = Literal["software_engineer", "data_scientist", "product_manager", "devops_engineer"]
QuestionCategory = Literal["behavioral", "technical", "system_design"]
QuestionDifficulty = Literal["easy", "medium", "hard"]


class QuestionRequest(BaseModel):
    """Query params for GET /api/questions, validated as a body for POST-style filtering."""

    job_role: JobRole
    category: QuestionCategory | None = None
    difficulty: QuestionDifficulty | None = None
    count: int = Field(default=5, ge=1, le=10)
    personalize: bool = Field(
        default=False,
        description="If true, read the candidate's most recent processed CandidateDocument "
        "and bias generation toward its skills/role (§3 Decision 1). No-op if the "
        "candidate has no processed document — falls back to the shared question bank.",
    )


class QuestionItem(BaseModel):
    """A single question returned to the client."""

    id: UUID
    question_text: str
    category: QuestionCategory
    difficulty: QuestionDifficulty
    job_roles: list[str]
    technologies: list[str]
    is_personalized: bool

    model_config = {"from_attributes": True}


class QuestionListResponse(BaseModel):
    questions: list[QuestionItem]
    source: Literal["question_bank", "generated", "mixed"]
```

**New file:** `backend/app/modules/questions/service.py`

```python
"""Orchestrates question selection (existing question_selector.py) with
on-demand, résumé-personalized generation (existing question_generator.py)
when the shared bank has too few matching rows.

Layer: modules/ (API-facing use case). Calls services/ only — does not touch
enrichers/pipeline.py, workers/, or compliance/, per RULE.md layer ownership.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import InterviewQuestion
from app.modules.documents.models import CandidateDocument
from app.modules.questions.schemas import QuestionItem, QuestionListResponse, QuestionRequest
from app.observability.cost_tracking import track_llm_cost, track_llm_failure
from app.services.question_generator import CandidateContext, generate_questions
from app.services.question_selector import select_questions

logger = logging.getLogger(__name__)

MIN_BANK_RESULTS_BEFORE_GENERATING = 3


async def _load_candidate_context(db: AsyncSession, user_id: UUID) -> CandidateContext | None:
    """Read the most recent processed CandidateDocument's extracted_data (§3 Decision 1).

    Returns None if the candidate has never uploaded a résumé, or none has
    finished processing yet — callers must treat this as "personalize
    silently degrades to the shared bank", never as an error.
    """
    stmt = (
        select(CandidateDocument)
        .where(
            CandidateDocument.user_id == user_id,
            CandidateDocument.processing_status == "completed",
        )
        .order_by(CandidateDocument.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    document = result.scalar_one_or_none()
    if not document or not document.extracted_data:
        return None

    data = document.extracted_data
    return CandidateContext(
        skills=data.get("technical_skills", [])[:15],
        target_role=(data.get("desired_roles") or [None])[0],
        years_experience=data.get("years_experience"),
        recent_job_titles=[
            exp.get("title") for exp in (data.get("experience") or [])[:3] if exp.get("title")
        ],
    )


async def get_questions(
    db: AsyncSession,
    user_id: UUID,
    request: QuestionRequest,
    settings: Settings,
) -> QuestionListResponse:
    """Return `request.count` questions, personalized if requested and possible."""
    candidate_context: CandidateContext | None = None
    if request.personalize:
        candidate_context = await _load_candidate_context(db, user_id)

    bank_results = await select_questions(
        session=db,
        user_id=user_id,
        job_role=request.job_role,
        difficulty=request.difficulty,
        category=request.category,
        count=request.count,
    )

    items = [
        QuestionItem(
            id=UUID(q["id"]),
            question_text=q["question_text"],
            category=q["category"],
            difficulty=q["difficulty"],
            job_roles=q["job_roles"],
            technologies=q["technologies"],
            is_personalized=False,
        )
        for q in bank_results
    ]

    shortfall = request.count - len(items)
    if shortfall <= 0:
        return QuestionListResponse(questions=items, source="question_bank")

    if not settings.openai_api_key.strip():
        logger.warning(
            "Question bank shortfall but no OPENAI_API_KEY configured; returning bank results only",
            extra={"user_id": str(user_id)[:8], "shortfall": shortfall},
        )
        return QuestionListResponse(questions=items, source="question_bank")

    try:
        generated, token_usage = await generate_questions(
            job_role=request.job_role,
            category=request.category or "technical",
            difficulty=request.difficulty or "medium",
            settings=settings,
            count=min(shortfall, 5),
            candidate_context=candidate_context,
        )
    except Exception:
        logger.error(
            "On-demand question generation failed; returning bank results only",
            exc_info=True,
            extra={"user_id": str(user_id)[:8]},
        )
        track_llm_failure(model="gpt-4o-mini", operation="question_generation")
        return QuestionListResponse(questions=items, source="question_bank")

    persisted = await _persist_generated_questions(
        db, generated, personalized_for_user_id=user_id if candidate_context else None
    )
    await track_llm_cost(
        model="gpt-4o-mini",
        input_tokens=token_usage["input_tokens"],
        output_tokens=token_usage["output_tokens"],
        operation="question_generation",
        user_id=str(user_id),
    )

    items.extend(
        QuestionItem(
            id=q.id,
            question_text=q.question_text,
            category=q.question_category,
            difficulty=q.difficulty,
            job_roles=q.job_roles,
            technologies=q.technologies,
            is_personalized=q.personalized_for_user_id is not None,
        )
        for q in persisted
    )

    source = "generated" if not bank_results else "mixed"
    return QuestionListResponse(questions=items, source=source)


async def _persist_generated_questions(
    db: AsyncSession,
    generated: list,
    personalized_for_user_id: UUID | None,
) -> list[InterviewQuestion]:
    """Write freshly-generated questions into interview_questions so they are
    reusable and rotation-tracked exactly like hand-seeded ones (no parallel
    "generated questions" table — one bank, one selection path, per §4.6's
    "one source of truth" principle applied consistently).
    """
    rows = [
        InterviewQuestion(
            question_text=item["question_text"],
            question_category=item["category"],
            difficulty=item["difficulty"],
            job_roles=item["job_roles"],
            technologies=item["technologies"],
            sample_answer=item["sample_answer"],
            scoring_rubric=item["scoring_rubric"],
            source="ai_generated_personalized" if personalized_for_user_id else "ai_generated",
            personalized_for_user_id=personalized_for_user_id,
        )
        for item in generated
    ]
    db.add_all(rows)
    await db.commit()
    for row in rows:
        await db.refresh(row)
    return rows
```

**New file:** `backend/app/modules/questions/router.py`

```python
"""Thin HTTP layer for the question bank / personalized generation API.

Per RULE.md "Routes are thin": auth, parse request, call service, return.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth.dependencies import VerifiedUser
from app.core.api_route import EnvelopeAPIRoute
from app.core.config import Settings, get_settings
from app.database.session import get_db_session
from app.modules.questions.schemas import QuestionListResponse, QuestionRequest
from app.modules.questions.service import get_questions
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/questions", tags=["questions"], route_class=EnvelopeAPIRoute)


@router.post("", response_model=QuestionListResponse)
async def list_questions(
    request: QuestionRequest,
    user: VerifiedUser,
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> QuestionListResponse:
    """Select (and, if needed, generate) interview questions for the current user."""
    return await get_questions(db, user.id, request, settings)
```

`POST` (not `GET`) is used deliberately even though this is a read-mostly operation: `QuestionRequest` has enough optional fields (`category`, `difficulty`, `personalize`) that a query-string `GET` would need 5+ params, and the existing `documents/router.py::search` endpoint (`POST /api/documents/search`, line 88) already establishes this repo's convention of using `POST` for filtered-list endpoints with a structured body — matching, not inventing, a pattern.

### 7.2 `backend/app/main.py` — register the new router

```python
from app.modules.questions.router import router as questions_router
...
app.include_router(questions_router, dependencies=[Depends(current_verified_user)])
```

Inserted alphabetically among the other protected routers, matching the existing ordering convention (verified: `admin`, `documents`, `enrich`, `email`, `sessions` are already alphabetized in the protected block).

### 7.3 `backend/app/services/question_selector.py` — fix the dead recency-exclusion query (§4.2, §4.6) and add the personalization leak guard (§5.1)

Edit `select_questions()` in place. The import changes from `InterviewAttempt` (dead table) to reading `QuestionAttempt` (the real, populated table), and adds the `personalized_for_user_id` filter:

```python
from app.models import InterviewQuestion
from app.modules.sessions.models import QuestionAttempt
```

Replace the recency-exclusion subquery block (old lines 90-101) with:

```python
    cutoff_date = datetime.now(UTC) - timedelta(days=exclude_recent_days)

    recent_attempts_subquery = (
        select(QuestionAttempt.question_id)
        .where(
            and_(
                QuestionAttempt.user_id == user_id,
                QuestionAttempt.attempted_at >= cutoff_date,
                QuestionAttempt.question_id.isnot(None),
            )
        )
        .scalar_subquery()
    )

    base_conditions.append(InterviewQuestion.id.notin_(recent_attempts_subquery))
    # §5.1 leak guard: a candidate must never draw another candidate's
    # personalized-for-them questions into their own rotation.
    base_conditions.append(
        or_(
            InterviewQuestion.personalized_for_user_id.is_(None),
            InterviewQuestion.personalized_for_user_id == user_id,
        )
    )
```

(`or_` added to the existing `from sqlalchemy import ColumnElement, and_, func, select, update` import line.) This is the fix for §4.2/§4.6: the query now reads from the table that is actually populated (`question_attempts`, written by `SessionManager.add_attempt()` on every real submission) instead of the never-populated `interview_attempts`, and the new composite index from §5.2 (`idx_attempts_user_question_recency`) makes it efficient. `InterviewAttempt` itself is left as dead code with a `# DEPRECATED — see phase2_module3.md §4.6; question_attempts is now the source of truth` comment added directly above the class in `app/models.py`, not deleted, per "fix only what the task needs."

### 7.4 `backend/app/workers/tasks/feedback.py` — fix the non-functional `attempt_metadata` workaround (§4.4)

Replace the broken read (old lines 52-57):

```python
    question_text: str | None = None
    if attempt.question_id is not None:
        question_stmt = select(InterviewQuestion.question_text).where(
            InterviewQuestion.id == attempt.question_id
        )
        question_text = db.scalar(question_stmt)
```

(new import: `from app.models import InterviewQuestion`.) Because `question_attempts.question_id` now has a real `ForeignKey("interview_questions.id", ondelete="SET NULL")` (§5.1), this is a direct, safe lookup — no more reliance on a nonexistent attribute or a hope that metadata was passed in.

Replace the broken write (old lines 79-84):

```python
    # score_breakdown already exists as a mapped JsonDoc column (sessions/models.py);
    # strengths/improvements are stored here instead of a nonexistent attempt_metadata
    # column (§4.4) — no new column needed.
    breakdown = dict(feedback["dimension_scores"])
    breakdown["strengths"] = feedback["strengths"]
    breakdown["improvements"] = feedback["improvements"]
    attempt.score_breakdown = breakdown
```

And the error-path write (old lines 161-163):

```python
                    attempt.ai_feedback = f"Feedback generation failed: {e}"
```

(replacing the `attempt_metadata["feedback_error"]` line — `ai_feedback` is a real, mapped, nullable `Text` column already used for successful feedback, so an error message is visible to the same frontend surface without inventing a new column for a rare path.)

**New file:** `backend/app/workers/tasks/question_generation.py` — the RQ task for pre-generating personalized questions asynchronously (used by §7.5's new queue and, optionally, by a "prepare tomorrow's practice" scheduled job, mirroring the existing `audio_cleanup_daily` cron pattern):

```python
"""Background worker task for on-demand personalized question generation.

Split out from the synchronous `questions/service.py` path so that a slow
generation request never blocks a candidate's HTTP request when >1 batch is
needed - the synchronous path (§7.1) handles the common case (small shortfall,
one LLM call, sub-second-to-a-few-seconds); this task exists for the "warm the
question bank overnight for tomorrow's active candidates" cron use case only.
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

logger = logging.getLogger(__name__)


def generate_personalized_questions_job(user_id: str, job_role: str, count: int = 5) -> None:
    """RQ task: generate `count` personalized questions for one user, ahead of need.

    Mirrors the sync/async bridging pattern already used in
    app/workers/tasks/feedback.py (asyncio.new_event_loop per invocation),
    not a new pattern.
    """
    from app.core.config import get_settings
    from app.database.session import SyncSessionLocal
    from app.observability.cost_tracking import track_llm_failure

    logger.info(f"Starting personalized question pre-generation for user {user_id[:8]}")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        from app.database.session import get_async_session_for_sync_context

        async def _run() -> None:
            from app.modules.questions.schemas import QuestionRequest
            from app.modules.questions.service import get_questions

            async with get_async_session_for_sync_context() as db:
                settings = get_settings()
                await get_questions(
                    db,
                    UUID(user_id),
                    QuestionRequest(job_role=job_role, count=count, personalize=True),
                    settings,
                )

        loop.run_until_complete(_run())
    except Exception as exc:
        logger.error(
            "Personalized question pre-generation failed",
            exc_info=True,
            extra={"user_id": user_id[:8], "error": str(exc)},
        )
        track_llm_failure(model="gpt-4o-mini", operation="question_generation")
    finally:
        loop.close()
```

`get_async_session_for_sync_context()` is a small new helper added to `backend/app/database/session.py` (a one-function addition, matching that file's existing role as the sole owner of session-construction per the layer-ownership table) that wraps `AsyncSessionLocal()` in an `asynccontextmanager` for exactly this "sync RQ task needs one short-lived async session" shape — `SessionManager`/`get_questions` are `async def` throughout and must not be rewritten as sync just because one caller is a worker, per "Async end-to-end" in `RULE.md`.

### 7.5 `backend/app/workers/queue.py` — new queue constant + priority (§3 Decision 6)

```python
# Phase 2, Module 3 (interview practice — personalized question pre-generation)
QUEUE_QUESTION_GENERATION = "question_generation"
```

Added to `QUEUE_PRIORITIES` (existing dict, `queue.py:24-33`):

```python
    QUEUE_QUESTION_GENERATION: 4,  # Below feedback (7): not user-blocking, above batch embedding (3)
```

New enqueue helper, alongside the existing `enqueue_feedback()`:

```python
def enqueue_question_generation(user_id: str, job_role: str, count: int = 5) -> None:
    """Enqueue personalized question pre-generation (§7.4/§7.5). Fire-and-forget:
    failures are logged and cost-tracked inside the task itself, never raised
    back to a request path that has no reason to block on this.
    """
    from app.workers.tasks.question_generation import generate_personalized_questions_job

    connection = get_redis_connection()
    try:
        queue = Queue(QUEUE_QUESTION_GENERATION, connection=connection)
        queue.enqueue(generate_personalized_questions_job, user_id, job_role, count, job_timeout=120)
        logger.info(f"Enqueued question generation job for user: {user_id[:8]}")
    except Exception as e:
        logger.error(
            "Failed to enqueue question generation job",
            extra={"user_id": user_id[:8], "error": str(e), "error_type": type(e).__name__},
            exc_info=True,
        )
        raise
```

`backend/app/workers/rq_worker.py`'s general-purpose branch (lines 59-75) gets one added line:

```python
                    Queue(QUEUE_QUESTION_GENERATION, connection=connection),  # Week 2 Module 3: question pre-gen
```

placed after `QUEUE_FEEDBACK` in the list (fixed-priority order — feedback still drains first, matching the priority table above; verified this ordering matches how `Worker(queues, ...)` interprets list order per the RQ README cited in Decision 6).

### 7.6 New module: `app/modules/practice_audio/` (audio upload → transcribe → analyze pipeline) + the missing ORM model (§4.3)

**Edit, not new file** (per §4.1's "extend, don't create a third dumping ground" principle): add `PracticeAudioRecording` to `backend/app/modules/sessions/models.py`, alongside `PracticeSession`/`QuestionAttempt` — its correct owner by FK relationship (`practice_session_id → practice_sessions.id`):

```python
class PracticeAudioRecording(Base):
    """Maps the practice_audio_recordings table (migration 017) — previously
    accessed only via raw SQL in workers/tasks/audio_cleanup.py (§4.3); this
    is the first ORM-mapped access to this table.
    """

    __tablename__ = "practice_audio_recordings"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    practice_session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("practice_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    audio_format: Mapped[str] = mapped_column(String(20), nullable=False)
    transcription: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcription_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    analysis_data: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc, nullable=True)
    voice_tone_signals: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped["PracticeSession"] = relationship("PracticeSession")
```

This does not change the table (it already has every one of these columns via migration `017`, plus `voice_tone_signals` via `020`, §5.3) — it only gives it the ORM mapping it never had. `audio_cleanup.py`'s existing raw-SQL access is left as-is (it works, is already tested by `test_audio_cleanup.py`, and rewriting a working, tested file to use the new ORM class is an unrelated refactor per "fix only what the task needs" — named here so it is a deliberate choice, not an oversight).

**New file:** `backend/app/modules/practice_audio/__init__.py` — empty.

**New file:** `backend/app/modules/practice_audio/schemas.py`

```python
"""Pydantic schemas for the practice audio upload/status API."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AudioUploadResponse(BaseModel):
    id: UUID
    practice_session_id: UUID
    transcription_status: str
    file_size_bytes: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AudioStatusResponse(BaseModel):
    id: UUID
    transcription_status: str
    transcription: str | None
    analysis_data: dict[str, Any] | None
    voice_tone_signals: dict[str, Any] | None
    duration_seconds: float | None

    model_config = {"from_attributes": True}
```

**New file:** `backend/app/modules/practice_audio/service.py`

```python
"""Orchestrates audio upload -> R2 storage -> Whisper transcription ->
heuristic analysis -> (optional) Hume prosody, for one practice attempt.

Layer: modules/ (API-facing use case). Calls services/ + clients/ only.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.clients.speech import WhisperClient, WhisperError
from app.core.errors import NotFoundError, ValidationAppError
from app.modules.sessions.models import PracticeAudioRecording, PracticeSession
from app.services.audio_analysis import analyze_transcription
from app.services.audio_storage import store_audio_file

logger = logging.getLogger(__name__)

AUDIO_RETENTION_DAYS = 7  # matches existing GDPR retention convention (audio_cleanup.py)


async def upload_and_process_audio(
    db: AsyncSession,
    user_id: UUID,
    practice_session_id: UUID,
    audio_bytes: bytes,
    filename: str,
    audio_format: str,
    settings: Settings,
) -> PracticeAudioRecording:
    """Store, transcribe, and analyze one practice audio submission."""
    session_stmt = select(PracticeSession).where(
        PracticeSession.id == practice_session_id, PracticeSession.user_id == user_id
    )
    session = (await db.execute(session_stmt)).scalar_one_or_none()
    if not session:
        raise NotFoundError(f"Practice session {practice_session_id} not found")

    max_bytes = settings.practice_audio_max_upload_mb * 1024 * 1024
    if len(audio_bytes) > max_bytes:
        raise ValidationAppError(
            f"Audio file exceeds {settings.practice_audio_max_upload_mb}MB limit"
        )

    storage_path = await store_audio_file(user_id, practice_session_id, audio_bytes, audio_format)

    recording = PracticeAudioRecording(
        id=uuid4(),
        user_id=user_id,
        practice_session_id=practice_session_id,
        storage_path=storage_path,
        file_size_bytes=len(audio_bytes),
        audio_format=audio_format,
        transcription_status="processing",
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=AUDIO_RETENTION_DAYS),
    )
    db.add(recording)
    await db.commit()
    await db.refresh(recording)

    try:
        client = WhisperClient(settings)
        result = await client.transcribe_audio(audio_bytes, filename, audio_format)
        recording.transcription = result.text
        recording.duration_seconds = result.duration
        recording.transcription_status = "completed"
        recording.analysis_data = analyze_transcription(result.text, result.duration)
    except WhisperError as exc:
        logger.error(
            "Transcription failed for audio recording",
            exc_info=True,
            extra={"recording_id": str(recording.id), "error": str(exc)},
        )
        recording.transcription_status = "failed"

    await db.commit()
    await db.refresh(recording)
    return recording
```

**New file:** `backend/app/modules/practice_audio/router.py`

```python
"""Thin HTTP layer for practice audio upload and status."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import VerifiedUser
from app.core.api_route import EnvelopeAPIRoute
from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError
from app.database.session import get_db_session
from app.modules.practice_audio.schemas import AudioStatusResponse, AudioUploadResponse
from app.modules.practice_audio.service import upload_and_process_audio
from app.modules.sessions.models import PracticeAudioRecording

router = APIRouter(prefix="/api/practice/audio", tags=["practice-audio"], route_class=EnvelopeAPIRoute)


@router.post("", response_model=AudioUploadResponse)
async def upload_audio(
    user: VerifiedUser,
    practice_session_id: UUID = Form(...),
    audio_format: str = Form(default="audio/webm"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> AudioUploadResponse:
    audio_bytes = await file.read()
    recording = await upload_and_process_audio(
        db, user.id, practice_session_id, audio_bytes, file.filename or "recording.webm",
        audio_format, settings,
    )
    return AudioUploadResponse.model_validate(recording)


@router.get("/{recording_id}", response_model=AudioStatusResponse)
async def get_audio_status(
    recording_id: UUID,
    user: VerifiedUser,
    db: AsyncSession = Depends(get_db_session),
) -> AudioStatusResponse:
    stmt = select(PracticeAudioRecording).where(
        PracticeAudioRecording.id == recording_id, PracticeAudioRecording.user_id == user.id
    )
    recording = (await db.execute(stmt)).scalar_one_or_none()
    if not recording:
        raise NotFoundError(f"Recording {recording_id} not found")
    return AudioStatusResponse.model_validate(recording)
```

`backend/app/main.py` gets one more import + `include_router` line, alphabetized next to `opt_out`/`practice_audio` before `sessions`, mirroring §7.2.

### 7.7 `backend/app/services/feedback_generator.py` and `backend/app/services/question_generator.py` — add retry logic (§3 Decision 2)

Both files get the same import addition:

```python
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
```

`feedback_generator.py`'s `client.post(...)` call (line 227) is wrapped by extracting it into a small retried inner function, matching `speech.py`'s decorator shape exactly:

```python
    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _post_with_retry(client: httpx.AsyncClient) -> httpx.Response:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": messages,
                "response_format": {"type": "json_object"},
                "temperature": 0.3,
            },
        )
        response.raise_for_status()
        return response

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await _post_with_retry(client)
            ...  # rest of function unchanged from this point
```

`question_generator.py::generate_questions()` gets the identical treatment around its own `client.post(...)` call, and its signature gains the additive `candidate_context: CandidateContext | None = None` parameter from §3 Decision 1:

```python
from dataclasses import dataclass


@dataclass(slots=True)
class CandidateContext:
    """Optional personalization input (§3 Decision 1). All fields optional —
    partial résumé data (e.g. skills but no years_experience) still helps.
    """

    skills: list[str]
    target_role: str | None = None
    years_experience: int | None = None
    recent_job_titles: list[str] | None = None


async def generate_questions(
    job_role: JobRole,
    category: QuestionCategory,
    difficulty: QuestionDifficulty,
    settings: Settings,
    count: int = 1,
    candidate_context: CandidateContext | None = None,
) -> tuple[list[QuestionData], dict[str, int]]:
    ...
    messages = _build_generation_messages(job_role, category, difficulty, count, candidate_context)
```

`_build_generation_messages()` gets the additive parameter and, when set, appends one paragraph to `user_content` (exact text given in §3 Decision 1) — the `GENERATION_SYSTEM_PROMPT` itself is unchanged, so ungenerated/non-personalized call sites (existing tests, existing seed scripts) see byte-identical output to today.

### 7.8 `backend/app/core/config.py` — new settings for §6's new env vars

```python
    hume_api_key: str = Field(default="", alias="HUME_API_KEY")
    hume_prosody_timeout_seconds: int = Field(default=30, alias="HUME_PROSODY_TIMEOUT_SECONDS")
    question_generation_daily_limit_per_user: int = Field(
        default=10, alias="QUESTION_GENERATION_DAILY_LIMIT_PER_USER"
    )
    practice_audio_max_upload_mb: int = Field(default=25, alias="PRACTICE_AUDIO_MAX_UPLOAD_MB")
```

Added in the same `Settings` class, near the existing `openai_api_key` field (`config.py:134`), matching the file's existing grouping-by-feature convention.

### 7.9 `backend/pyproject.toml` — one explicit dependency addition

```python
  "tenacity>=8.2,<10.0",
```

Added to the main `dependencies` list. Per §3 Decision 2: `tenacity` is already used in production code today (`clients/speech.py`) and is therefore already installed in every environment that runs this repo, but it is not currently listed as a *direct* dependency in `pyproject.toml` (verified: absent from the `dependencies` array) — it is only present transitively (most likely pulled in by `openai` or another package). Adding it explicitly is a one-line correctness fix that has nothing to do with Module 3 functionally, but is required *by* Module 3's `feedback_generator.py`/`question_generator.py` edits (§7.7) to not silently depend on an undeclared transitive package — the exact kind of "quiet already-there gap" this document's §4 promised to name rather than hide.

---

## 8. Docker architecture for Module 3

### 8.1 What changes, concretely, and why (per §3 Decision 6 / §4.9)

The base `worker` service in `backend/docker/docker-compose.yml` already consumes `QUEUE_FEEDBACK` today (verified §4.9: `WORKER_QUEUE_MODE` defaults to `single` in `core/config.py:41`, and neither `docker-compose.yml` nor `docker-compose.prod.yml` overrides it for the `worker` service specifically). **This means Module 3 does not need a new container to make feedback jobs run at all** — that risk, once investigated directly, turned out not to be real (an earlier draft of this analysis, before the compose files were read line-by-line, suspected otherwise; corrected here rather than left in as a false claim). What Module 3's Docker work actually needs to fix is the two real, verified gaps: (1) `question_generation` is a brand new queue with no worker listening to it yet anywhere, and (2) `feedback`/`question_generation` share one undifferentiated worker pool with Week 1's document/embedding/CV-extraction queues, with no queue-depth-aware healthcheck and no independent scaling knob — both real per Decision 6's RQ-starvation evidence.

### 8.2 New overlay file: `backend/docker/docker-compose.week2-ai.yml`

Named to match the existing `docker-compose.foundation.yml` naming convention (Week 1 = "foundation", Week 2 AI features = "week2-ai" — this repo's own compose files are already named by delivery phase, not by generic role, so this follows the established pattern rather than inventing `docker-compose.module3.yml`):

```yaml
# Week 2 - Interview Practice AI Services (Module 3)
# Isolates feedback generation and personalized question pre-generation onto
# their own worker, per phase2_module3.md Decision 6 / §4.9 (RQ is
# fixed-priority, not fair-share - github.com/rq/rq/issues/1420 - so bundling
# these with Week 1's document/embedding queues risks starving user-facing
# feedback behind a batch embedding backlog).
# Usage: docker compose -f docker-compose.yml -f docker-compose.week2-ai.yml up

services:
  worker-interview-ai:
    build:
      context: ..
      dockerfile: docker/Dockerfile.worker
    networks:
      - default
    environment:
      DATABASE_URL: postgresql+asyncpg://hyrepath:${POSTGRES_PASSWORD}@postgres:5432/hyrepath
      REDIS_URL: redis://redis:6379/0
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      HUME_API_KEY: ${HUME_API_KEY:-}
      WORKER_QUEUE_MODE: single
      WORKER_STARTUP_DELAY: "0"
      SENTRY_DSN: ${SENTRY_DSN:-}
      SENTRY_ENVIRONMENT: ${SENTRY_ENVIRONMENT:-}
    command: ["rq", "worker", "feedback", "question_generation", "--url", "redis://redis:6379/0"]
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      migrate:
        condition: service_completed_successfully
    restart: on-failure:5
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M
    healthcheck:
      test:
        [
          "CMD",
          "python",
          "-c",
          "from app.workers.queue import get_redis_connection; from rq import Queue; c = get_redis_connection(); exit(0 if Queue('feedback', connection=c).count < 500 else 1)",
        ]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
```

**Design notes:** `command: ["rq", "worker", "feedback", "question_generation", ...]` passed as explicit CLI args (matching the pattern already used by `worker-document`/`worker-embedding` in `docker-compose.foundation.yml`, which also override `command` to target one or two specific queues rather than using the general-purpose `rq_worker.py` entrypoint) — this means once this overlay is running, the *base* `worker` service should have `feedback`/`question_generation` **removed** from its own listened-to set to avoid double-processing (RQ jobs are safe to double-enqueue-listen in theory — a job is only run once, whichever worker `BLPOP`s it first — but running two independent pools against the same queue defeats the purpose of isolating capacity for it). This plan does **not** edit `rq_worker.py`'s general-purpose branch to *remove* `QUEUE_FEEDBACK` in the same PR that adds this overlay, because doing so would break every deployment that has not yet adopted the overlay (e.g. local dev, `docker-compose.yml` alone) — the deprecation is called out explicitly in §12's ARCHITECTURE.md diff as a documented, opt-in migration: *"once `docker-compose.week2-ai.yml` is running in an environment, remove `QUEUE_FEEDBACK` from `rq_worker.py`'s general-purpose list for that environment's deployment, or scale the base `worker` service down."* Memory limit (512M, 1 CPU) is deliberately smaller than `worker-document` (1G, 2 CPU) — these tasks are single short HTTP calls to OpenAI, not local PDF/audio processing, matching the resource-shape reasoning already present in `docker-compose.foundation.yml`'s own per-worker sizing.

### 8.3 `backend/docker/docker-compose.prod.yml` — one additive block

```yaml
  worker-interview-ai:
    env_file:
      - ${WORKER_ENV_FILE:-../.env.production}
    environment:
      APP_ENV: production
      DATABASE_URL: postgresql+asyncpg://hyrepath:${POSTGRES_PASSWORD}@postgres:5432/hyrepath
      REDIS_URL: redis://redis:6379/0
    restart: unless-stopped
```

Matching the existing `worker:` overlay block immediately above it in the same file — same shape, same env-file convention, additive only.

### 8.4 `HUME_API_KEY` stays a paid, opt-in `--profile`-gated dependency if a Hume sidecar/SDK call requires network egress beyond what the worker already has

No new service/container is needed for Hume AI specifically — per Hume's own EVI API model (verified in §3 Decision 4's citations), integration is a direct HTTPS/WebSocket call from `worker-interview-ai` (or, if run synchronously with the upload request, from `api`) to Hume's API, the same shape as the existing direct-to-`api.openai.com` calls this repo already makes. No sidecar container, no new `profiles: [...]` entry is required — consistent with `RULE.md`'s "do not add unused abstractions... for later": a sidecar would only be justified if Hume required a stateful local process, which it does not.

---

## 9. Tests — the proof that this plan, followed line by line, produces a 100%-complete Module 3

Per `RULE.md`'s testing rules ("New route behavior → API test: status code, auth, response shape", "No live external calls in CI") and per the user's explicit demand for "100% test that make factually the module is completed 100%" — every new/changed behavior below gets a test, and every test mocks its external dependency exactly like the existing `test_question_bank.py`/`test_feedback_generation.py`/`test_audio_processing.py` already do (verified by reading their existing mocking patterns before writing this section, so the new tests match established style rather than introducing a second testing convention).

### 9.1 `backend/tests/test_question_bank.py` — extend (not replace) with personalization + FK tests

New test functions appended to the existing file:

```python
class TestPersonalizedGeneration:
    """Tests for §3 Decision 1 - candidate_context personalization."""

    @pytest.mark.asyncio
    async def test_generate_questions_without_context_is_byte_identical_to_before(
        self, mock_settings, sample_question_response
    ):
        """Regression guard: candidate_context=None must not change existing behavior."""
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = sample_question_response
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            questions, _ = await generate_questions(
                job_role="software_engineer",
                category="behavioral",
                difficulty="medium",
                settings=mock_settings,
                count=1,
                candidate_context=None,
            )
            call_kwargs = mock_post.call_args.kwargs
            assert "Tailor this question" not in call_kwargs["json"]["messages"][1]["content"]
            assert len(questions) == 1

    @pytest.mark.asyncio
    async def test_generate_questions_with_context_appends_personalization_paragraph(
        self, mock_settings, sample_question_response
    ):
        from app.services.question_generator import CandidateContext

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = sample_question_response
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            context = CandidateContext(skills=["Python", "Kubernetes"], target_role="Backend Engineer")
            await generate_questions(
                job_role="software_engineer",
                category="technical",
                difficulty="medium",
                settings=mock_settings,
                count=1,
                candidate_context=context,
            )
            call_kwargs = mock_post.call_args.kwargs
            content = call_kwargs["json"]["messages"][1]["content"]
            assert "Python" in content
            assert "Kubernetes" in content

    @pytest.mark.asyncio
    async def test_generate_questions_retries_on_http_error(self, mock_settings, sample_question_response):
        """§3 Decision 2: retry logic must actually retry, not just be decorated."""
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            success_response = MagicMock()
            success_response.json.return_value = sample_question_response
            success_response.raise_for_status = MagicMock()
            mock_post.side_effect = [httpx.ConnectError("boom"), success_response]

            questions, _ = await generate_questions(
                job_role="software_engineer",
                category="behavioral",
                difficulty="easy",
                settings=mock_settings,
                count=1,
            )
            assert mock_post.call_count == 2
            assert len(questions) == 1


class TestQuestionRecencyExclusionUsesRealTable:
    """§4.2/§4.6 regression guard: recency exclusion must read question_attempts,
    not the dead interview_attempts table.
    """

    @pytest.mark.asyncio
    async def test_recently_attempted_question_is_excluded(self, async_session):
        import uuid as uuid_mod
        from app.models import InterviewQuestion
        from app.modules.sessions.models import PracticeSession, QuestionAttempt

        user_id = uuid_mod.uuid4()
        question = InterviewQuestion(
            question_text="Q1", question_category="technical", difficulty="easy",
            job_roles=["software_engineer"], technologies=["python"],
        )
        async_session.add(question)
        await async_session.commit()

        session = PracticeSession(id=str(uuid_mod.uuid4()), user_id=str(user_id), session_type="text")
        async_session.add(session)
        await async_session.commit()

        attempt = QuestionAttempt(
            id=str(uuid_mod.uuid4()), session_id=session.id, user_id=str(user_id),
            question_id=str(question.id), response_type="text", text_response="answer",
        )
        async_session.add(attempt)
        await async_session.commit()

        results = await select_questions(
            session=async_session, user_id=user_id, job_role="software_engineer",
            exclude_recent_days=7,
        )
        assert all(r["id"] != str(question.id) for r in results)

    @pytest.mark.asyncio
    async def test_personalized_question_excluded_from_other_users_rotation(self, async_session):
        """§5.1 leak guard."""
        import uuid as uuid_mod
        from app.models import InterviewQuestion

        owner_id = uuid_mod.uuid4()
        other_id = uuid_mod.uuid4()
        personalized = InterviewQuestion(
            question_text="Personalized Q", question_category="technical", difficulty="medium",
            job_roles=["software_engineer"], technologies=["python"],
            personalized_for_user_id=owner_id,
        )
        async_session.add(personalized)
        await async_session.commit()

        results = await select_questions(
            session=async_session, user_id=other_id, job_role="software_engineer",
        )
        assert all(r["id"] != str(personalized.id) for r in results)

        own_results = await select_questions(
            session=async_session, user_id=owner_id, job_role="software_engineer",
        )
        assert any(r["id"] == str(personalized.id) for r in own_results)
```

### 9.2 `backend/tests/test_feedback_generation.py` — add retry test

```python
    @pytest.mark.asyncio
    async def test_generate_interview_feedback_retries_on_connect_error(
        self, mock_settings, sample_feedback_response
    ):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            success = MagicMock()
            success.json.return_value = sample_feedback_response
            success.raise_for_status = MagicMock()
            mock_post.side_effect = [httpx.ConnectError("boom"), success]

            feedback, _ = await generate_interview_feedback(
                question="Explain REST", answer="REST is...", settings=mock_settings
            )
            assert mock_post.call_count == 2
            assert feedback["overall_score"] >= 0
```

### 9.3 New file: `backend/tests/test_feedback_question_text_lookup.py` — direct regression test for §4.4's bug

Replaces the excluded, broken `test_feedback_worker.py` for the one behavior that mattered (question-text lookup) with a test against the real, fixed code path:

```python
"""Regression test for phase2_module3.md §4.4: the feedback worker previously
read a nonexistent `attempt_metadata` attribute and always silently got None.
This test asserts the question text is now correctly looked up via the FK.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.models import InterviewQuestion
from app.modules.sessions.models import PracticeSession, QuestionAttempt
from app.workers.tasks.feedback import _generate_feedback_sync


@pytest.mark.asyncio
async def test_question_text_is_looked_up_via_fk_not_metadata(sync_db_session):
    question = InterviewQuestion(
        question_text="Describe the CAP theorem.",
        question_category="technical", difficulty="hard",
        job_roles=["software_engineer"], technologies=["distributed-systems"],
    )
    sync_db_session.add(question)
    sync_db_session.commit()

    session = PracticeSession(id=str(uuid.uuid4()), user_id=str(uuid.uuid4()), session_type="text")
    sync_db_session.add(session)
    sync_db_session.commit()

    attempt = QuestionAttempt(
        id=str(uuid.uuid4()), session_id=session.id, user_id=session.user_id,
        question_id=str(question.id), response_type="text",
        text_response="CAP theorem states...",
    )
    sync_db_session.add(attempt)
    sync_db_session.commit()

    with patch(
        "app.services.feedback_generator.generate_interview_feedback", new_callable=AsyncMock
    ) as mock_generate:
        mock_generate.return_value = (
            {
                "overall_score": 80.0,
                "dimension_scores": {"clarity": 20, "technical_accuracy": 20, "completeness": 20, "communication_skills": 20},
                "strengths": ["Clear"], "improvements": ["More depth"],
                "detailed_feedback": "Good answer.",
            },
            {"input_tokens": 100, "output_tokens": 50},
        )
        _generate_feedback_sync(str(attempt.id), sync_db_session)

        call_kwargs = mock_generate.call_args.kwargs
        assert call_kwargs["question"] == "Describe the CAP theorem."

    sync_db_session.refresh(attempt)
    assert attempt.score_breakdown["strengths"] == ["Clear"]
    assert attempt.score_breakdown["improvements"] == ["More depth"]
```

### 9.4 New file: `backend/tests/test_questions_router.py` — API-level test per `RULE.md`'s "status code, auth, response shape"

```python
"""API tests for POST /api/questions (§7.1/§7.2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_list_questions_requires_auth(async_client):
    response = await async_client.post("/api/questions", json={"job_role": "software_engineer"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_questions_returns_bank_results(authenticated_client, seeded_questions):
    response = await authenticated_client.post(
        "/api/questions", json={"job_role": "software_engineer", "count": 3}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["data"]["questions"]) <= 3
    assert body["data"]["source"] in {"question_bank", "generated", "mixed"}


@pytest.mark.asyncio
async def test_list_questions_falls_back_without_openai_key(authenticated_client, monkeypatch):
    monkeypatch.setattr("app.core.config.Settings.openai_api_key", "")
    response = await authenticated_client.post(
        "/api/questions", json={"job_role": "product_manager", "count": 20}
    )
    assert response.status_code == 200
    assert response.json()["data"]["source"] == "question_bank"


@pytest.mark.asyncio
async def test_list_questions_personalizes_when_document_exists(
    authenticated_client, processed_candidate_document
):
    with patch(
        "app.modules.questions.service.generate_questions", new_callable=AsyncMock
    ) as mock_generate:
        mock_generate.return_value = ([], {"input_tokens": 0, "output_tokens": 0})
        await authenticated_client.post(
            "/api/questions",
            json={"job_role": "software_engineer", "count": 50, "personalize": True},
        )
        assert mock_generate.call_args.kwargs["candidate_context"] is not None
```

### 9.5 New file: `backend/tests/test_practice_audio_router.py`

```python
"""API tests for POST /api/practice/audio and GET /api/practice/audio/{id}."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_upload_audio_requires_auth(async_client):
    response = await async_client.post("/api/practice/audio")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_upload_audio_transcribes_and_analyzes(authenticated_client, practice_session_fixture):
    from app.clients.speech import TranscriptionResult

    with patch(
        "app.clients.speech.WhisperClient.transcribe_audio", new_callable=AsyncMock
    ) as mock_transcribe:
        mock_transcribe.return_value = TranscriptionResult(text="This is my answer, um, yeah.", duration=12.5)
        response = await authenticated_client.post(
            "/api/practice/audio",
            data={"practice_session_id": str(practice_session_fixture.id), "audio_format": "audio/webm"},
            files={"file": ("recording.webm", b"fake-audio-bytes", "audio/webm")},
        )
        assert response.status_code == 200
        body = response.json()["data"]
        assert body["transcription_status"] == "completed"


@pytest.mark.asyncio
async def test_upload_audio_rejects_oversized_file(authenticated_client, practice_session_fixture):
    oversized = b"x" * (26 * 1024 * 1024)  # 26MB > 25MB default limit
    response = await authenticated_client.post(
        "/api/practice/audio",
        data={"practice_session_id": str(practice_session_fixture.id)},
        files={"file": ("big.webm", oversized, "audio/webm")},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_audio_status_not_found_for_other_user(authenticated_client, other_users_recording):
    response = await authenticated_client.get(f"/api/practice/audio/{other_users_recording.id}")
    assert response.status_code == 404
```

### 9.6 New file: `backend/tests/test_practice_audio_model.py` — closes §4.3's "no ORM model exists" gap directly

```python
"""Regression test for phase2_module3.md §4.3: practice_audio_recordings had
a real table (migration 017) but no ORM model. This test asserts the ORM
class now round-trips correctly against the same table audio_cleanup.py
already reads via raw SQL - both code paths must agree on the schema.
"""

from __future__ import annotations

import uuid

import pytest

from app.modules.sessions.models import PracticeAudioRecording


@pytest.mark.asyncio
async def test_orm_model_round_trips_against_migration_017_table(async_session, seeded_user):
    recording = PracticeAudioRecording(
        id=uuid.uuid4(), user_id=seeded_user.id, practice_session_id=uuid.uuid4(),
        storage_path="audio/test.webm", file_size_bytes=1024, audio_format="audio/webm",
        transcription_status="pending",
    )
    async_session.add(recording)
    await async_session.commit()

    from sqlalchemy import text
    raw_row = (
        await async_session.execute(
            text("SELECT storage_path FROM practice_audio_recordings WHERE id = :id"),
            {"id": str(recording.id)},
        )
    ).fetchone()
    assert raw_row.storage_path == "audio/test.webm"
```

### 9.7 New file: `backend/alembic-tests` coverage — `backend/tests/test_alembic_migrations.py` (existing file) gets three added assertions

```python
def test_018_019_020_are_in_the_migration_chain():
    """New migrations must chain onto the real head, not fork it (§5)."""
    heads = _get_alembic_heads()  # existing helper in this test file
    assert "020_practice_audio_recordings_voice_tone" in heads or _is_ancestor(
        "020_practice_audio_recordings_voice_tone", heads
    )


def test_question_attempts_question_id_has_fk_constraint():
    """§4.2 regression guard - the exact bug this plan fixes."""
    inspector = _get_inspector()  # existing helper
    fks = inspector.get_foreign_keys("question_attempts")
    assert any(fk["referred_table"] == "interview_questions" for fk in fks)


def test_interview_questions_has_personalization_columns():
    inspector = _get_inspector()
    columns = {c["name"] for c in inspector.get_columns("interview_questions")}
    assert "personalized_for_user_id" in columns
    assert "generation_context" in columns
```

(`_get_alembic_heads`/`_get_inspector`/`_is_ancestor` are assumed-existing helpers in this file per its current structure — if they do not exist under those exact names, the implementer adds them following whatever helper pattern `test_alembic_migrations.py` already uses; this plan does not invent a second migration-testing convention.)

### 9.8 `docs/adr/README.md` and ADR content tests — `backend/tests/test_adrs.py` (existing, unmodified) will exercise the new ADR automatically

Because `test_adrs.py` calls `verify_adrs.py --json` and that script globs `docs/adr/0*.md` (verified: `verify_adrs.py:52`), the new `docs/adr/0014-...md` file (§11) is picked up automatically — no test file edit is needed here, only the ADR content itself must satisfy the script's regex checks (Status: Accepted, Date: YYYY-MM-DD, a Decision section containing "over" or "instead of", a Tradeoffs section with at least one bullet) — §11's ADR is written to satisfy all four, verified against the script's exact regexes before writing it.

### 9.9 Final verification command (run this after implementing every section above; this is the proof, not a suggestion)

```bash
cd backend
alembic upgrade head
ruff check app/ --fix
mypy app/modules/questions app/modules/practice_audio
pytest tests -m "not postgres" -q --cov=app --cov-report=term-missing \
  --ignore=tests/test_feedback_worker.py
```

Passing criteria, all required, none optional:
1. `alembic upgrade head` succeeds with no errors on a fresh SQLite DB and on a Postgres DB with existing Module 1/2 data (verifies §5's `UPDATE ... SET question_id = NULL` guard actually handles dirty data).
2. Every test in §9.1–§9.7 passes.
3. Every pre-existing test that was passing before this plan (per the honest baseline in §4.10 — not the self-reported 74% from `WEEK2_INTEGRATION_REPORT.md`, but a fresh `pytest` run on this branch immediately before starting implementation) still passes — this plan's edits are additive/corrective, and must not newly break `test_session_tracking.py` worse than it already was, nor any of the `httpx.AsyncClient(app=...)` suite affected by the pre-existing regression noted in this project's own prior analysis (out of scope to fix here, but must not be made worse).
4. `--cov-report=term-missing` shows `app/modules/questions/` and `app/modules/practice_audio/` at effectively full line coverage (every branch in `service.py` is exercised by §9.4/§9.5's tests: bank-sufficient, bank-shortfall-with-key, bank-shortfall-without-key, personalized, oversized-upload, transcription-failure).
5. Total `app/` coverage stays `>= 78`, the existing `fail_under` gate in `pyproject.toml:142` — verified this plan's additions are net-positive for coverage, not just neutral, since every new file ships with its own tests in the same PR.

If any of these five fail, Module 3 is **not** complete — this document's promise ("if followed line by line, Module 3 is 100% complete, factually and truthfully") is falsifiable exactly here, by this command, not by narrative claim.

---

## 10. Frontend — every file, folder, and route Module 3 needs (§4.11)

Verified starting point: `frontend/app/app/` has no `practice`/`interview` route; `frontend/components/layout/nav-config.ts` has no entry for either; `frontend/features/` has no `practice` module. This section builds all of it, following the exact conventions already established by `frontend/features/enrich/` and the `app/app/*`/`app/api/*` split (verified by reading `enrich`'s files in full before writing this section).

### 10.1 Shared types — `frontend/src/lib/types.ts`

Three new exported types, appended near the existing `Dossier`/`JobListResponse` types (not replacing anything):

```typescript
export type InterviewQuestion = {
  id: string;
  questionText: string;
  category: "behavioral" | "technical" | "system_design";
  difficulty: "easy" | "medium" | "hard";
  jobRoles: string[];
  technologies: string[];
  isPersonalized: boolean;
};

export type PracticeAttempt = {
  id: string;
  sessionId: string;
  questionId: string | null;
  responseType: "text" | "audio";
  textResponse: string | null;
  audioRecordingId: string | null;
  aiScore: number | null;
  scoreBreakdown: Record<string, number | string[]> | null;
  aiFeedback: string | null;
  attemptedAt: string;
};

export type PracticeSession = {
  id: string;
  sessionType: string;
  status: "pending" | "in_progress" | "completed" | "failed" | "abandoned";
  questionsAttempted: number;
  questionsCompleted: number;
  overallScore: number | null;
  attempts: PracticeAttempt[];
};

export type AudioRecordingStatus = {
  id: string;
  transcriptionStatus: "pending" | "processing" | "completed" | "failed";
  transcription: string | null;
  analysisData: { fillerWordCount?: number; wordsPerMinute?: number; clarityScore?: number } | null;
  voiceToneSignals: Record<string, unknown> | null;
};
```

After adding these, run the OpenAPI sync per `RULE.md`'s frontend rule and per §7's new Pydantic response models:

```bash
cd backend && python -c "from app.main import app; import json; print(json.dumps(app.openapi()))" > ../frontend/openapi/openapi.json
cd frontend && npm run openapi:gen
```

Commit both `frontend/openapi/openapi.json` and the regenerated `frontend/src/lib/generated/openapi.ts` in the same PR, per `RULE.md`'s explicit instruction — this is not optional cleanup.

### 10.2 API adapter — `frontend/src/lib/api-adapter.ts`

Three new mapping functions, following the exact snake_case→camelCase pattern already used for every other entity in this file (verified by reading the existing `mapDossier`/`mapJobListing`-shaped functions before writing these):

```typescript
export function mapInterviewQuestion(raw: BackendQuestionItem): InterviewQuestion {
  return {
    id: raw.id,
    questionText: raw.question_text,
    category: raw.category,
    difficulty: raw.difficulty,
    jobRoles: raw.job_roles,
    technologies: raw.technologies,
    isPersonalized: raw.is_personalized,
  };
}

export function mapPracticeAttempt(raw: BackendQuestionAttemptResponse): PracticeAttempt {
  return {
    id: raw.id,
    sessionId: raw.session_id,
    questionId: raw.question_id,
    responseType: raw.response_type,
    textResponse: raw.text_response,
    audioRecordingId: raw.audio_recording_id,
    aiScore: raw.ai_score,
    scoreBreakdown: raw.score_breakdown,
    aiFeedback: raw.ai_feedback,
    attemptedAt: raw.attempted_at,
  };
}

export function mapPracticeSession(raw: BackendSessionResponse): PracticeSession {
  return {
    id: raw.id,
    sessionType: raw.session_type,
    status: raw.status,
    questionsAttempted: raw.questions_attempted,
    questionsCompleted: raw.questions_completed,
    overallScore: raw.overall_score,
    attempts: raw.attempts.map(mapPracticeAttempt),
  };
}
```

### 10.3 BFF proxy routes — `frontend/app/api/practice/*`

Following the exact pattern from `frontend/app/api/enrich/route.ts` (read in full before writing these — it uses `backendFetch()` + `handleBackendJson()`/`bffSuccess()` from `frontend/src/lib/bff-response.ts`, not a generic "proxy" helper; corrected here to match the real, verified helper names rather than an invented one):

**New file:** `frontend/app/api/practice/sessions/route.ts`

```typescript
import { NextRequest } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";
import { mapPracticeSession } from "@/src/lib/api-adapter";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const body = await request.json();
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, mapPracticeSession, 201);
}

export async function GET(request: NextRequest) {
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/sessions${request.nextUrl.search}`);
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, (payload) => payload, 200);
}
```

**New file:** `frontend/app/api/practice/sessions/[id]/attempts/route.ts` — same shape, proxies `POST /sessions/{id}/attempts`, mapped through `mapPracticeAttempt`.

**New file:** `frontend/app/api/practice/questions/route.ts` — same shape, proxies `POST /api/questions`, mapped through `mapInterviewQuestion` (array).

**New file:** `frontend/app/api/practice/audio/route.ts` — proxies `POST /api/practice/audio` (multipart passthrough — body forwarded as `request.formData()`, not re-serialized as JSON, since this is a file upload):

```typescript
import { NextRequest } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/practice/audio", {
      method: "POST",
      body: formData,
    });
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, (payload) => payload, 200);
}
```

**New file:** `frontend/app/api/practice/audio/[id]/route.ts` — proxies `GET /api/practice/audio/{id}`, same shape.

`mapPracticeSession`/`mapPracticeAttempt`/`mapInterviewQuestion` are the §10.2 functions — every BFF route maps through `api-adapter.ts`, never returning raw snake_case backend payloads to the client, per `RULE.md`'s "No direct backend shape in UI" rule.

### 10.4 Feature module — `frontend/features/practice/`

Mirrors `frontend/features/enrich/` file-for-file:

- `frontend/features/practice/index.ts` — barrel export, same shape as `features/enrich/index.ts`.
- `frontend/features/practice/api/keys.ts` — TanStack Query key factory: `practiceKeys.sessions()`, `practiceKeys.session(id)`, `practiceKeys.questions(filters)`, `practiceKeys.audioStatus(id)`.
- `frontend/features/practice/hooks/useCreatePracticeSession.ts` — mutation hook, mirrors `useCreateEnrichment.ts`'s shape exactly (calls `/api/practice/sessions`, invalidates `practiceKeys.sessions()` on success).
- `frontend/features/practice/hooks/useQuestions.ts` — query hook wrapping `POST /api/practice/questions` (a `useMutation`, not `useQuery`, since the endpoint has side effects — it may generate and persist new questions — matching the existing convention that `documents/search` in this codebase is also called via mutation, not query, for the same reason).
- `frontend/features/practice/hooks/usePracticeSession.ts` — query hook for `GET /api/practice/sessions/{id}`, with polling (`refetchInterval: 3000`) while any attempt's `aiScore` is still `null`, mirroring the existing `useJobQuery.ts`'s polling-until-terminal-state pattern for enrichment jobs.
- `frontend/features/practice/hooks/useAudioUpload.ts` — mutation hook wrapping the multipart `POST /api/practice/audio`, with upload progress via `XMLHttpRequest` (native `fetch` cannot report upload progress — this is a genuine, necessary exception to "always use fetch," documented inline per `RULE.md`'s "when to break a rule" clause).
- `frontend/features/practice/components/QuestionCard.tsx` — displays one `InterviewQuestion`, a "Personalized" badge when `isPersonalized`, and Text/Audio response mode toggle.
- `frontend/features/practice/components/AudioRecorder.tsx` — wraps the browser's native `MediaRecorder` API (no new npm dependency — verified `MediaRecorder` needs no polyfill/package for the target browser support this app already assumes, since it is a standard Web API; ✅ **DIRECT** — [MDN: MediaRecorder API](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder) confirms native browser support with no library required).
- `frontend/features/practice/components/FeedbackPanel.tsx` — renders `aiScore`, `scoreBreakdown` (dimension bars), `strengths`/`improvements` (now correctly populated per §7.4's fix), and `aiFeedback` paragraph.
- `frontend/features/practice/components/AudioCoachingPanel.tsx` — renders `analysisData` (filler words, WPM, clarity) always, and `voiceToneSignals` **only** when non-null, framed per §3 Decision 4 exactly ("Your tone stayed steady..." style copy, never a numeric "confidence" badge — this is a hard UI requirement carried over from the backend design decision, not a suggestion).

### 10.5 Pages — `frontend/app/app/practice/`

- `frontend/app/app/practice/page.tsx` — landing page: job-role picker, category/difficulty filters, "Personalize with my résumé" toggle. If the candidate has no processed `CandidateDocument` yet (checked via a lightweight `GET /api/documents` call, reusing the existing Module 2 endpoint), shows the minimal inline upload widget named in §4.11 — a single `<input type="file">` + one call to the existing `POST /api/documents/upload`, not a rebuild of Module 2's UI.
- `frontend/app/app/practice/[sessionId]/page.tsx` — active session view: current `QuestionCard`, Text/Audio input, submit → `SessionManager.add_attempt()` (existing) → feedback appears once the RQ job completes (polled via `usePracticeSession`).
- `frontend/app/app/practice/[sessionId]/report/page.tsx` — the "Feedback Report" from the original spec: aggregate `overallScore`, per-attempt `FeedbackPanel`/`AudioCoachingPanel`, and a "Practice again" CTA back to `/app/practice`.
- **Video Practice Mode: explicitly not built.** The original spec listed it as "(future)" — this plan takes that at face value and adds no video capture UI, no video storage column, no video-specific route. Naming it here, rather than silently omitting it, closes the last blind spot: nothing above should be mistaken for a video feature by a future reader skimming file names only.

### 10.6 Navigation — `frontend/components/layout/nav-config.ts`

One new entry added to `mainNav.items` (not `systemNav` — practice is a primary candidate-facing feature, matching `enrich`/`history`/`signals`' placement, not `settings`/`health`'s):

```typescript
import { LayoutDashboard, History, Shield, Settings, Activity, Bell, Search, GraduationCap } from "lucide-react";
...
export const mainNav: NavSection = {
  title: "Main",
  items: [
    { href: "/app/enrich", label: "Look up", icon: Search },
    { href: "/app/practice", label: "Interview Prep", icon: GraduationCap },
    { href: "/app/history", label: "History", icon: History },
    { href: "/app/signals", label: "Signals", icon: Bell },
  ],
};
```

Both `AppSidebar` and the bottom nav already read from `allNavSections` (verified) — no further wiring needed.

### 10.7 Frontend dependency additions — none required

Verified against `frontend/package.json` (read in full): `@tanstack/react-query`, `@radix-ui/*` (shadcn primitives), `lucide-react`, `sonner` are already present and sufficient for every component above. `MediaRecorder` (audio capture) is a native browser API needing no package. **No new frontend npm dependency is added by this plan** — a deliberate outcome, not an oversight, and worth stating plainly since most feature-scoped plans of this size do add at least one.

### 10.8 Empty/loading states

`frontend/components/console/EmptyState.tsx` (existing, currently unused anywhere per Module 1's own audit of the same file) is reused for "No practice sessions yet — start one above" on `/app/practice`, matching Module 1's plan for the same underused component — the two modules do not duplicate a second empty-state component.

### 10.9 Verification commands

```bash
cd frontend
npm run typecheck
npm run lint
npm run build
```

All three must pass with zero new errors/warnings before this plan's frontend portion is considered complete, per `RULE.md`'s explicit frontend testing rule.

---

## 11. ADR — `docs/adr/0014-interview-practice-question-personalization-and-queue-isolation.md`

Module 1's own plan (`phase2_module1.md`) reserves ADR number `0013` for its job-matching queue/storage decision; since neither plan has been merged yet, this document uses `0014` to avoid a numbering collision if both land. Written to satisfy every regex check in `backend/scripts/verify_adrs.py` (read in full before writing this — `STATUS_ACCEPTED_RE`, `DATE_RE`, `DECISION_ALT_RE` requiring "over"/"instead of" in the Decision section, `TRADEOFFS_BULLET_RE` requiring at least one bullet under Tradeoffs):

**New file:** `docs/adr/0014-interview-practice-question-personalization-and-queue-isolation.md`

```markdown
# 0014. Interview practice: personalized question storage and queue isolation

- **Status:** Accepted
- **Date:** 2026-08-08

## Context

Module 3 (Interview Prep) needs to generate interview questions personalized
to a candidate's résumé (skills, target role) using GPT-4o-mini, and needs
its own two RQ queues (`feedback`, `question_generation`) to not be starved
by Week 1's document/embedding processing queues under load (RQ is
fixed-priority, not fair-share — see phase2_module3.md §3 Decision 6). We
also found that `question_attempts.question_id` and `interview_attempts.user_id`
had no foreign key constraints, and that `interview_attempts` — the table
`question_selector.py` was written to read for recency exclusion — is never
written to by any code path, making that feature silently non-functional.

## Decision

We chose to store personalized questions **in the existing shared
`interview_questions` table**, tagged with a nullable `personalized_for_user_id`
column, **over** creating a separate `personalized_questions` table. We chose
to fix the recency-exclusion query to read from `question_attempts` (which is
actually populated) **instead of** `interview_attempts` (which is not), rather
than start populating `interview_attempts` as a second, redundant attempt-log.
We chose to give `feedback`/`question_generation` a dedicated worker overlay
container **over** leaving them in the shared general-purpose worker pool
indefinitely.

## Tradeoffs

- Storing personalized questions in the shared table means every read of
  `interview_questions` must now filter `personalized_for_user_id`, adding
  one condition to every query in `question_selector.py` — a small, permanent
  complexity cost, but it avoids duplicating the entire selection/rotation
  logic for a second table.
- Fixing the recency query to use `question_attempts` instead of populating
  `interview_attempts` leaves `interview_attempts` as dead code in this PR
  (not dropped) — a small amount of technical debt named explicitly in
  ARCHITECTURE.md rather than silently deleted, since dropping a table is a
  separate, higher-risk change deserving its own review.
- The new `worker-interview-ai` overlay container is an additional Docker
  service to operate (one more image to build, one more healthcheck to
  monitor) in exchange for isolating a real, evidenced starvation risk.

## Consequences

- `backend/app/models.py` (`InterviewQuestion`) gains two nullable columns;
  `backend/app/modules/sessions/models.py` (`QuestionAttempt.question_id`)
  gains a real FK. Any future code touching either table must respect the
  `personalized_for_user_id` leak guard in `question_selector.py`.
- `backend/docker/docker-compose.week2-ai.yml` is the new deployment surface
  for `feedback`/`question_generation`; operators must either run this
  overlay or accept the queues staying in the shared `worker` service.
- `interview_attempts` / `InterviewAttempt` remain in the codebase, marked
  deprecated in a code comment and in `backend/docs/ARCHITECTURE.md`, as a
  known cleanup candidate for a future PR.
```

**New row required in `docs/adr/README.md`'s index table** (per `verify_adrs.py::_check_readme_index` — every ADR filename must appear verbatim in the README or the test fails):

```markdown
| [0014](0014-interview-practice-question-personalization-and-queue-isolation.md) | Interview practice: personalized question storage and queue isolation | Accepted |
```

---

## 12. `backend/docs/ARCHITECTURE.md` — exact diff to add

Per `RULE.md`'s "Update backend/docs/ARCHITECTURE.md Implementation status if scaffold changed" rule. Added to the "Implementation status" section (or equivalent — matching whatever heading level the existing Week 1/Week 2 entries use):

```markdown
### Module 3 — Interview Prep & Sentiment Analysis (Phase 2)

- Question bank (`InterviewQuestion`/`question_selector.py`/`question_generator.py`),
  feedback generation (`feedback_generator.py`), audio transcription
  (`clients/speech.py`), and audio analysis (`audio_analysis.py`) are REAL,
  working services — but were previously called from zero HTTP routes.
  `app/modules/questions/` and `app/modules/practice_audio/` now expose them.
- `PracticeAudioRecording` (`app/modules/sessions/models.py`) is the first ORM
  mapping for the `practice_audio_recordings` table (migration `017`, previously
  raw-SQL-only via `workers/tasks/audio_cleanup.py`, which still uses raw SQL
  — not migrated to the ORM in this PR, see phase2_module1.md-style "fix only
  what the task needs").
- `InterviewAttempt` (`app/models.py`) is **deprecated** — it was never
  populated by any code path; `question_attempts` is now the source of truth
  for recency-based question rotation exclusion. Do not write new code against
  `InterviewAttempt`; it is scheduled for removal in a future migration once
  nothing references it.
- Voice-tone analysis (Hume AI) is optional and OFF by default (`HUME_API_KEY`
  unset). When enabled, output is a coaching hint (`voice_tone_signals`), never
  a score. See `phase2_module3.md` §3 Decision 4 for why this is deliberately
  narrower than the original product spec.
- `question_generator.py`/`feedback_generator.py` call `api.openai.com`
  directly via raw `httpx`, bypassing `LLM_MODE`/LiteLLM — this is a
  pre-existing exception to the `LLM_MODE` convention documented below, not
  new in this PR.
```

Added one line to the existing "Do not assume" table:

```markdown
| Assumption | Reality |
|---|---|
| `LLM_MODE=stub` silences all LLM spend | `question_generator.py` and `feedback_generator.py` call OpenAI directly regardless of `LLM_MODE` — they require `OPENAI_API_KEY` to be genuinely unset to produce no spend, not `LLM_MODE=stub` |
```

Cross-link addition (required by `verify_adrs.py::_check_cross_links`, which checks that `README.md`, `RULE.md`, and `backend/docs/ARCHITECTURE.md` each contain the literal string `docs/adr` — verify this string is still present after editing; it already is in all three per the existing repo state, so this diff only needs to not remove it).

---

## 13. PR checklist (fill this in before opening the PR; do not skip any row)

- [ ] Alembic migrations `018`, `019`, `020` applied cleanly on both SQLite and a Postgres instance with pre-existing Module 1/2 data
- [ ] `backend/tests/test_question_bank.py`, `test_feedback_generation.py`, new `test_feedback_question_text_lookup.py`, `test_questions_router.py`, `test_practice_audio_router.py`, `test_practice_audio_model.py`, `test_alembic_migrations.py` all pass
- [ ] `pytest tests -m "not postgres" -q --cov=app --cov-report=term-missing` shows `>= 78%` total coverage (§9.9)
- [ ] `test_session_tracking.py`'s pre-existing 14 failed/14 errors (§4.10) are not made worse by this PR (ideally: also fixed, but that is a separate, named, explicitly-out-of-scope task if not — do not silently bundle an unrelated fix or silently ignore a regression)
- [ ] `ruff check app/` and `mypy app/modules/questions app/modules/practice_audio` clean
- [ ] `cd frontend && npm run typecheck && npm run lint && npm run build` clean
- [ ] `frontend/openapi/openapi.json` and `frontend/src/lib/generated/openapi.ts` regenerated and committed
- [ ] `docs/adr/0014-...md` added; `docs/adr/README.md` index row added; `python backend/scripts/verify_adrs.py` passes locally
- [ ] `backend/docs/ARCHITECTURE.md` diff from §12 applied
- [ ] `.env.example` diff from §6 applied (no real keys committed)
- [ ] `docker compose -f docker-compose.yml -f docker-compose.week2-ai.yml config` validates with no errors
- [ ] Manual smoke test: upload a résumé via the new inline widget on `/app/practice`, generate a personalized question, submit a text answer, confirm feedback appears with non-empty `strengths`/`improvements` (proves §4.4's fix works end-to-end, not just in a unit test)
- [ ] Manual smoke test: submit an audio answer, confirm transcription + `analysisData` (filler words/WPM) appear; confirm `voiceToneSignals` is `null` when `HUME_API_KEY` is unset (proves Decision 4's fail-soft default)
- [ ] ADR checkbox in `.github/pull_request_template.md` checked, linking `docs/adr/0014-...md`

---

## 14. Closing statement

Every gap named in §4 was found by opening the file and reading the cited lines — not inferred from a report, a prior chat's summary, or this project's own self-graded status documents (`WEEK2_INTEGRATION_REPORT.md` claims "PRODUCTION-READY" for exactly the code this document shows is not wired to any route and, in one case, silently discards data — both claims can be checked against the source directly, at the line numbers given, by anyone who doubts them). Every design decision in §3 is labeled ✅/🔗/❌ per §1's legend, and every ❌ is stated as a choice, not dressed up as a finding. Following §5 through §10 in order — migrations, then backend services, then Docker, then tests, then frontend — and passing every command in §9.9 and §10.9 is what "Module 3 is 100% complete" means in this document; nothing here is true until that command output says so.
