# 0014. CV Chat, Portfolio, and Outreach — Storage, Queue, and External API Choices

- **Status:** Accepted
- **Date:** 2026-08-13

## Context

Module 2 ("Tinder-Style Job Board + CV Management") adds five features on top
of Foundation Week 1/2 and Module 1's existing schema. Three of them introduce
genuinely new architectural surface that RULE.md's "When to add an ADR"
criteria (new storage, new queue, new external API, new layer ownership)
require recording:

1. A CV-completeness chatbot needs somewhere to persist multi-turn
   conversation state across requests.
2. Outreach drafting needs live, per-company context that nothing already
   integrated (OpenAI, SendGrid, JobSpy) can provide.
3. A public-facing portfolio page needs to exist **outside** authentication
   entirely — a new trust boundary this codebase has only crossed once before
   (`/api/opt-out`, `/api/dsar`'s public half).

Job swipe (reads Module 1's existing `job_matches`/`job_postings` read-only)
and CV feedback (reuses the existing `QUEUE_FEEDBACK` queue and
`feedback_generator.py` pattern) are deliberately **not** covered by this ADR
— neither introduces new storage, queue, or external-API surface; they are
ordinary extensions of already-decided architecture (see `phase2_module2.md`
§3 Decisions 3 and 6 for their reasoning, which does not rise to ADR weight).

## Decision

We chose, in each case, the option that reuses this repo's existing
primitives **over** introducing a new one, except where no existing
primitive could do the job (Perplexity):

1. **CV chat storage**: two new tables, `cv_chat_sessions` +
   `cv_chat_messages` (Alembic `025_cv_chat_sessions`), owned by the existing
   `documents` module (not a new top-level module) — chat state is a
   side-effect of one specific document's completeness check, the same
   ownership boundary `candidate_documents` already has. **Chat runs
   synchronously on the `api` container**, not a worker queue — each OpenAI
   round trip is single-digit seconds and the user is actively waiting in a
   conversation, the same shape as any other request/response endpoint, not a
   background job (`phase2_module2.md` §3 Decision 2). The chatbot's only
   possible actions are constrained to a single defined "tool"
   (`record_cv_answer`, `app/clients/llm_tools.py`) via OpenAI function
   calling, so it cannot free-form invent CV data (`phase2_module2.md` §3
   Decision 1).
2. **Outreach's external API**: **Perplexity Sonar**, not a second OpenAI
   call with retrieval bolted on, and not a bespoke web-scraping client.
   Perplexity's API returns web-grounded summaries directly, with built-in
   recency — the exact shape "company context" needs, verified against
   Perplexity's own API documentation before this ADR was written. Failure
   mode: on any error, timeout, or missing API key, `PerplexityClient`
   (`app/clients/perplexity.py`) returns `{"summary": "", "source": "none"}`
   and outreach generation proceeds with a generic (still real, still useful)
   draft rather than failing the whole job — a new external dependency must
   degrade, not become a new single point of failure (`phase2_module2.md` §3
   Decision 7).
3. **Outreach queue**: `outreach_generation` (`QUEUE_OUTREACH` in
   `app/workers/queue.py`), appended to the **existing generic worker's**
   queue list in `rq_worker.py` (not a new dedicated container) — see
   `phase2_module2.md` §10 for the full reasoning distinguishing this from
   Module 1's `worker-job-matching` isolation decision. In short: outreach's
   per-job latency and per-click (not per-burst) trigger pattern put it in the
   same risk class as CV feedback, which already safely shares that worker
   today.
4. **Public portfolio trust boundary**: `GET /api/portfolio/public/{slug}`
   is the **only** unauthenticated route this module adds, deliberately kept
   to read-only, deliberately excluded from the app's global auth dependency
   by routing it through a separate `APIRouter` (`public_router` in
   `app/modules/portfolio/router.py`) mounted in `main.py` **without** the
   `Depends(current_verified_user)` the authenticated `portfolio_router` gets
   (mirroring how `/api/opt-out` already carves out its own public exception
   today). `PublicPortfolioResponse` is a distinct Pydantic schema from the
   authenticated portfolio response — it has no `user_id` field at all, not a
   field that is merely omitted at serialization time, so leaking it is a
   type error, not a runtime mistake (`phase2_module2.md` §9.6).

## Tradeoffs

- Reusing `documents` for CV chat keeps ownership simple but means that
  module's `router.py`/`service.py` grow by several endpoints/methods —
  judged acceptable because they are all about the *same* document, not scope
  creep into unrelated concerns.
- Perplexity adds a second paid LLM-adjacent vendor (alongside OpenAI) to
  track spend for — mitigated by the same `cost_tracking.py`/admin-costs
  instrumentation Foundation Week 2 already built for OpenAI calls, extended
  rather than duplicated.
- Keeping outreach on the shared worker instead of isolating it now is a
  YAGNI bet: if wrong, the fix is mechanical (§10.2's documented playbook),
  but it is a real bet, not a guarantee.

## Consequences

- 6 new Alembic revisions (`025_cv_chat_sessions` through
  `030_outreach_messages`, plus 3 unrelated Module-1-adjacent revisions
  `022`-`024` already landed ahead of them), 0 new containers, 0 new
  Dockerfiles, 1 new environment variable group (`PERPLEXITY_API_KEY`,
  `PERPLEXITY_API_BASE`, plus `PORTFOLIO_PUBLIC_BASE_URL` for the path-based
  public URL — `backend/.env.example`).
- `docs/adr/README.md`'s ADR index gets a new row for `0014`.
- The Postgres pool-sizing gap already flagged in `phase2_module1.md` §4 /
  ADR 0013 (and originally documented in `architecture_phase2.md` §5.1's
  connection-exhaustion analysis) is **not worsened** by this ADR — Module 2
  adds zero new containers and therefore zero new connections to the pool
  ceiling beyond what the existing `api` and `worker` containers already
  hold open. This is a deliberate, stated contrast with Module 1's own ADR
  0013, which *did* have to accept worsening that same risk when it added a
  dedicated `worker-job-matching` container. The risk itself remains real,
  documented, and un-fixed — PgBouncer / explicit pool sizing is still future
  work, tracked in `architecture_phase2.md` §10, not something either this
  ADR or ADR 0013 claims to resolve.

## Alternatives considered

- **CV chat as a new top-level `modules/cv_chat/`**: rejected — would split
  one document's lifecycle (upload → completeness → chat → feedback) across
  two module boundaries for no ownership benefit; `documents` already owns
  the document.
- **Google/Bing web search API instead of Perplexity**: rejected — would
  require a second LLM call to summarize raw search results into prose,
  duplicating what Perplexity's API already returns in one call; more
  latency, more cost, more code for the same output shape.
- **A second OpenAI-only outreach flow with `browsing` tool-calling**:
  rejected at the time this ADR was written — OpenAI's hosted browsing tool
  was not yet available/stable enough to depend on for a production feature
  when this decision was made; revisit if that changes.
- **Isolate outreach on its own worker container immediately**: rejected —
  no demonstrated starvation evidence yet (§10.2 of `phase2_module2.md`);
  revisit if evidence appears.
