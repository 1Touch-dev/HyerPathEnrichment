# 0017. Interview Practice Question Personalization, Queue Isolation, and Voice-Tone Scope Limits (Module 3)

- **Status:** Accepted
- **Date:** 2026-08-14

## Context

Module 3 ("Interview Prep & Sentiment Analysis") adds AI-generated interview
questions personalized to a candidate's résumé, retry/backoff for the two
direct-to-`api.openai.com` calls this feature area makes, and an optional
voice-tone signal on top of the existing text-transcript coaching heuristics.
Four separate architectural questions needed settling before writing code:
(1) how personalization data flows into an existing, unpersonalized question
generator without breaking every existing call site; (2) whether "sentiment
analysis... nervousness" (the original spec's wording) should ship as a
hire/no-hire-adjacent signal or something narrower; (3) whether transient
OpenAI API failures should be retried, and with what pattern; (4) whether the
new `feedback`/`question_generation` RQ queues need a new worker topology or
queueing framework. `docs/adr/0013-job-matching-queue-and-storage.md` already
established the "new queue over appending to the generic worker's fixed
priority list" pattern for `job_matching`; this ADR extends that reasoning to
`question_generation` while explicitly choosing *not* to repeat the "new
dedicated container" part of that decision, because the underlying queue
(`feedback`) was already being served by the existing generic worker with no
Docker change required — a different, narrower situation than Module 1's.

## Decision

We chose, in each case, the option that **reuses this repo's existing
primitives over introducing a new one**, and the **narrower, evidence-backed
scope over the original spec's more aggressive wording**:

1. **Personalization via one new optional field, not a new pipeline.**
   `generate_questions()` gains one new **additive** parameter,
   `candidate_context: CandidateContext | None = None` (a small dataclass:
   `skills`, `target_role`, `years_experience`, `recent_job_titles`), chosen
   **over** building a separate "personalized question" code path. Default
   `None` preserves every existing call site's output byte-for-byte. The
   rubric/scoring stays generic and deterministic — personalization changes
   *what is asked*, never *how it is graded* — matching Module 1's own
   decision to keep LLM scoring auditable rather than opaque.
2. **Voice-tone analysis ships opt-in, coaching-framed, and separate from
   scoring — over building it as a "sentiment"/"confidence" signal that
   feeds `ai_score`.** Text-transcript heuristics (filler words, pace,
   rule-based clarity) stay the always-on default. An optional Hume AI
   prosody integration (`HUME_API_KEY` unset by default, matching this
   repo's existing fail-soft convention for `LLM_MODE`/R2/Reacher) is stored
   as nullable `voice_tone_signals` JSON and surfaced only as a
   self-reflection prompt, never a numeric confidence score, never fed into
   scoring, never shown to any third party. This is chosen **over** shipping
   the original spec's more literal "sentiment analysis... nervousness"
   framing, and **over** using Deepgram-style transcript-based "sentiment"
   as if it were vocal-tone analysis (it is not — see Tradeoffs).
3. **Retry/backoff reuses the existing `with_transient_retry` helper
   (`app/clients/retry.py`) already proven at 6+ call sites (`outreach.py`,
   `cv_chat_service.py`, `perplexity.py`, `sidecar.py`,
   `generate_cv_improvement()`), over inventing a second retry convention.**
   Both `feedback_generator.py` and `question_generator.py` wrap only their
   raw `httpx.AsyncClient.post()` call (not the whole function, so
   `ValueError`s from missing keys or parse failures are not retried) with
   `with_transient_retry(...)`, which retries `ConnectError`/`ReadTimeout`/
   `WriteTimeout`/`PoolTimeout` and `HTTPStatusError` with status in
   `{429, 502, 503, 504}`, up to `max_retries=2` (3 attempts total) with
   exponential backoff. This repo has two superficially similar retry
   patterns — a single-use `tenacity` decorator in `clients/speech.py`, and
   the plain-function `with_transient_retry` helper reused across 6+ other
   call sites — and this decision picks the more-reused, zero-new-dependency
   one **over** the single-use decorator, since consistency with the
   dominant existing pattern outweighs matching `speech.py` specifically.
   `tenacity` remains a transitive dependency only (still added directly to
   `pyproject.toml` per repo convention of listing direct imports
   explicitly, even though no code in this module ends up calling it).
4. **`question_generation` gets a new RQ queue constant and priority weight,
   consumed by the existing generic worker by default, with a new optional
   dedicated-worker overlay (`docker-compose.week2-ai.yml`) — over building a
   second dedicated container immediately, and over a new queueing
   framework.** Unlike Module 1's `job_matching` (which had no consumer at
   all until a dedicated container was added), the base `worker` service
   already listens to `QUEUE_FEEDBACK` by default (`WORKER_QUEUE_MODE=single`
   in `core/config.py`) — verified directly by reading
   `docker-compose.yml`'s `worker` service block and `rq_worker.py`'s
   general-purpose branch. So the *minimum* correct change is: add
   `QUEUE_QUESTION_GENERATION` next to `QUEUE_FEEDBACK` in that same list
   (jobs run immediately, no topology change required), and give
   `question_generation` its own `QUEUE_PRIORITIES` weight below `feedback`
   (interview feedback is user-facing/blocking; personalized question
   pre-generation is not). A second, additive overlay
   (`docker-compose.week2-ai.yml`) adds an *optional* dedicated
   `worker-interview-ai` container for operators who want to isolate this
   capacity from Week 1's document/embedding pool, following RQ's own
   documented fixed-priority (not fair-share) queue behavior
   ([rq/rq#1420](https://github.com/rq/rq/issues/1420)).

## Tradeoffs

- Decision 1's additive-parameter approach means `question_generator.py`'s
  prompt-building helper now has two code paths (with/without context)
  inside one function rather than two cleanly separated functions, **traded
  for** zero risk to every existing caller/test and no duplicated
  prompt-assembly logic.
- Decision 2 means Module 3 ships a visibly smaller feature than the
  original spec's "sentiment analysis... nervousness" wording promised,
  **traded for** not shipping a scientifically contested, high real-world-
  harm-risk signal — regulators (AI Now Institute) and the largest
  commercial vendor of exactly this technology (HireVue) have both already
  concluded voice/visual affect analysis is not decision-grade for hiring.
  This is a deliberate scope reduction, not an oversight; it is expected to
  read as "less than the ticket asked for" without this ADR's context.
- Decision 3's function-scoped retry means a hard rate-limit outage across
  an entire `generate_questions()`/`generate_interview_feedback()` call
  still fails after 3 attempts (max ~0.75s of backoff, `with_transient_retry`'s
  default `max_retries=2`/`base_delay_seconds=0.25`) rather than being queued
  indefinitely — **traded for** simplicity and consistency with the
  dominant existing retry helper already used at 6+ other call sites,
  rather than introducing a different, more complex backoff/circuit-breaker
  mechanism for only these two call sites.
- Decision 4's "consumed by the existing generic worker by default" choice
  means `feedback`/`question_generation` remain bundled with Week 1's
  document/embedding/CV-extraction queues in production until an operator
  explicitly adopts the `docker-compose.week2-ai.yml` overlay, **traded
  for** zero required Docker/deployment change to ship Module 3 at all —
  every existing deployment keeps working unmodified. The overlay is
  additive-only (both worker pools may safely listen to the same queue;
  RQ only runs a job once), so this is genuinely optional, not a hidden
  requirement.

## Consequences

- `backend/app/services/question_generator.py`: new `CandidateContext`
  dataclass, one new optional parameter on `generate_questions()`,
  `with_transient_retry(...)` wrapped around its `httpx` call.
- `backend/app/services/feedback_generator.py`: `with_transient_retry(...)`
  wrapped around `generate_interview_feedback()`'s `httpx` call only (not
  `generate_cv_improvement()`, which already had its own
  `with_transient_retry(...)` call from Module 2).
- `backend/app/modules/questions/`: new module (schemas, service, router)
  — the API-facing use case layer that calls `question_generator.py`/
  `question_selector.py`, per `RULE.md` layer ownership (does not touch
  `enrichers/`, `workers/`, or `compliance/` directly).
- `backend/app/modules/practice_audio/`: new module; first ORM-mapped
  access to the `practice_audio_recordings` table (previously raw-SQL-only
  in `workers/tasks/audio_cleanup.py`), plus a new nullable
  `voice_tone_signals` JSON column (migration `035`).
- `backend/app/workers/queue.py`: new `QUEUE_QUESTION_GENERATION` constant
  and `QUEUE_PRIORITIES` entry; `backend/app/workers/rq_worker.py`'s
  general-purpose branch gains one line.
- `backend/docker/docker-compose.week2-ai.yml`: new, optional overlay file.
  No changes to `docker-compose.prod.yml` — verified directly that adding a
  `worker-interview-ai` block there would break the documented 2-file
  production deploy command
  (`docker-compose.yml -f docker-compose.prod.yml`,
  `backend/docs/evidence/prod-deploy-86.md`), matching the existing
  precedent that `docker-compose.foundation.yml`'s own
  `worker-document`/`worker-embedding`/`worker-job-matching` services have no
  `prod.yml` blocks either.
- `HUME_API_KEY` unset (default) means `voice_tone_signals` stays `NULL`
  forever for that deployment — a fail-soft default consistent with this
  repo's `LLM_MODE`/R2/Reacher conventions, documented in
  `backend/docs/ARCHITECTURE.md`'s "Do not assume" table.
- Deferred, explicitly not built: true SM-2 spaced repetition (the existing
  `ORDER BY usage_count ASC, random()` heuristic in `question_selector.py`
  stays, now actually functional once its recency-exclusion query is fixed
  to read from `QuestionAttempt` instead of the never-written
  `InterviewAttempt` table); any pass/fail or ranking signal derived from
  vocal tone; Glassdoor/LeetCode-scraped questions (both sites' Terms of Use
  prohibit scraping).

## Alternatives considered

- **Build personalization as a separate `generate_personalized_questions()`
  function**: rejected — would duplicate prompt-assembly logic and every
  future prompt change would need to be made twice.
- **Ship voice-tone as a numeric "confidence"/"nervousness" score**:
  rejected — no scientific foundation found in any source consulted
  (including the largest commercial vendor's own public retreat from this
  exact framing); would also risk becoming a de facto hiring signal this
  repo has no legal/ethical basis to defend.
- **A new dedicated `worker-question-generation` container immediately,
  mirroring Module 1's `worker-job-matching`**: rejected for the *required*
  path — unlike `job_matching`, `feedback`/`question_generation` already run
  on the existing generic worker with zero Docker changes; a mandatory new
  container would be an unjustified abstraction added "for later" per
  `RULE.md`. Offered instead as an *optional* overlay for operators who want
  the isolation.
- **Celery-style dedicated queue framework, or a Redis Streams-based
  priority system, to fix RQ's fixed-priority starvation risk generally**:
  rejected — out of scope for one new queue; the existing `QUEUE_PRIORITIES`
  dict + additive overlay is sufficient and consistent with Decision 6 of
  `phase2_module1.md`'s own scope boundary (fixing RQ's general fairness
  model is not this module's job).
