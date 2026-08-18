# 0013. Dedicated Queue and Storage for Job Matching (Module 1)

- **Status:** Accepted
- **Date:** 2026-08-10

## Context

Module 1 ("AI Job Matching & Notifications") requires: (1) persisting scraped
job postings independent of any single enrichment request, (2) scoring them
against candidate CVs, and (3) running this on a recurring schedule. None of
the three existing queues (`document_processing`, `embedding_generation`,
`cv_extraction`) nor the existing tables (`candidate_documents`,
`document_embeddings`) are the right owner for this — they belong to the CV
*intake* pipeline, not job *matching*.

## Decision

We chose a **dedicated queue + dedicated module + `rq_scheduler` cron**, in each
case picking the option that reuses this repo's existing primitives **over**
introducing a new one:

1. **New queue**: `job_matching`, consumed by a **dedicated worker container**
   (`worker-job-matching`), chosen **over appending it to the generic worker's
   queue list**. Rationale: the generic worker's fixed-priority queue list
   (`rq_worker.py`) already has a documented starvation risk (RQ's own docs
   confirm workers never touch lower-priority queues while higher-priority
   ones have backlog); adding a 6th queue there would worsen that risk in both
   directions. See `phase2_module1.md` §4 for the full analysis.
2. **New storage**: 4 tables — `job_postings`, `job_posting_embeddings`,
   `candidate_job_preferences`, `job_matches` — owned by a new
   `app/modules/job_matching/` module, chosen **over bolting them onto
   `documents/`**. Rationale: job postings are shared across all candidates
   (many-to-many via `job_matches`), fundamentally different cardinality from
   `candidate_documents` (one-to-one with a candidate).
3. **Scheduling**: extends the existing `rq_scheduler`-based cron pattern
   (`register_scheduled_jobs()`), chosen **instead of introducing Celery**.
   Rationale: this repo has no Celery dependency anywhere; introducing one for
   a single cron job would violate "keep the change as small as the task
   allows."

## Tradeoffs

- Dedicated worker container (Decision 1) means one more container to deploy
  and monitor, **traded for** avoiding worsened queue starvation on the
  shared generic worker — see Consequences below for the concrete cost.
- New module + 4 tables (Decision 2) means more schema surface area up front,
  **traded for** avoiding polymorphic/cardinality-mismatched queries against
  `documents/` later.
- Reusing `rq_scheduler` (Decision 3) means staying on a simpler, less
  feature-rich scheduler than Celery beat (no distributed lock beyond the
  scheduler-duplication caveat below), **traded for** zero new infrastructure
  dependency for a single cron job.

## Consequences

- One more container in `docker-compose.foundation.yml`, pinned to 1 replica
  (scaling requires first fixing the scheduler-duplication issue noted in
  `rq_worker_job_matching.py`'s docstring — tracked as future work, not blocking).
- Postgres connection count grows by up to 15 (SQLAlchemy default pool per
  process) — the pool-sizing ADR gap already flagged in `architecture_phase2.md`
  §5.1 is not fixed by this ADR; it is made marginally worse, within the
  already-accepted risk envelope for Phase 2's first module.
- `job_matches.feedback` column exists now but is unused until a v2
  behavior-based re-ranker is built — an intentional forward-compatible hook,
  not scope creep (Decision 2, `phase2_module1.md` §3).

## Alternatives considered

- **Reuse `documents` module for job postings**: rejected — cardinality
  mismatch (one candidate's CV vs. many-candidates-to-many-jobs), would force
  polymorphic queries and break "ORM lives with its owner."
- **Celery beat**: rejected — no existing Celery dependency; `rq_scheduler`
  already does the job.
- **Append `job_matching` to the generic worker's queue list**: rejected —
  worsens existing starvation risk (§4).

## Decision 7 — Real-time push via SSE (not WebSocket), reusing the existing `job_events.py` pattern

Real-time in-app push of "you have new job matches" (an unread-match count, on
top of the already-implemented email digest) uses **Server-Sent Events over
WebSocket**, implemented as a second, independent SSE primitive
(`job_matching/events.py`) that mirrors the shape of the existing
`enrichment/job_events.py` (dedicated Redis pub/sub client, per-entity channel,
heartbeat ping on idle, max-duration close) rather than introducing a new
transport or sharing that module's connection. Rationale: this repo already
operates this exact pattern in production for enrichment job status, so SSE is
proven-in-repo, not speculative; and this is a one-way, low-frequency,
server-to-client signal with no need for client-to-server messages, which is
squarely SSE's sweet spot over WebSocket. On reconnect, the route re-queries
Postgres for the authoritative unread count instead of implementing
`Last-Event-ID` replay — a missed pub/sub message is never a correctness bug,
since the next reconnect (or a plain page refresh via `GET /matches`)
self-heals to the true count.

Research backing this over WebSocket/MQTT/a managed push vendor: Shopify uses
SSE for exactly this kind of one-way, low-frequency dashboard-style push;
Uber's own writeups on SSE confirm it only breaks down at guaranteed-delivery
or mobile-background-connection scale, neither of which applies to a
browser-tab job-match counter; and Redis pub/sub's single-instance
fan-out ceiling is many orders of magnitude above this repo's current
candidate count. WebSocket and managed vendors would add bidirectional
complexity and/or a new infrastructure dependency for a feature that needs
neither.
