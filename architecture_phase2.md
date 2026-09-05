# Phase 2 Architecture — AI Candidate Platform at 10,000 Users/Day

**Branch:** `master-complete-foundation`
**Status:** Planning reference — synthesizes verified codebase findings + evidence-checked scaling research
**Scope:** Architecture for scaling the Phase 2 candidate-platform modules (job matching, CV/portfolio tooling, interview practice) to **10,000 users/day**, on top of the already-shipped Foundation Week 1/2 work.

**Evidence labels used throughout:**
- ✅ **DIRECT** — confirmed by reading this repo's code, or a primary source (official docs, paper, or company engineering blog) that explicitly states the claim
- 🔗 **INDIRECT** — a real, citable source that supports the point but doesn't state it in exactly this form/number
- 🔎 **NOT FOUND** — a claim that was checked against the cited primary source and could not be verified there (flagged, not silently dropped, because an earlier draft of this analysis contained several fabricated big-tech statistics — see §7)

---

## 1. Current state — what's actually running today

### 1.1 Phase 1 (enrichment tiers) — already solved, already documented

Confirmed in `backend/docker/docker-compose.tier-workers.yml`:

- `worker-tier1`: `network_mode: host`, `WORKER_QUEUE_MODE=per_tier`, `WORKER_TARGET_QUEUE=tier1`. Pinned 1-per-physical-host (Multilogin needs the loopback interface), **not** horizontally scalable via Docker.
- `worker-tier234`: bridge network, `WORKER_TARGET_QUEUE=tier234`, horizontally scalable (`docker compose up -d --scale worker-tier234=N`).

Both extend the same `worker` service/Dockerfile but are forced into single-queue mode by `app/workers/rq_worker.py`:

```python
if settings.worker_queue_mode == "per_tier":
    if not settings.worker_target_queue:
        raise ValueError(...)
    queues = [Queue(settings.worker_target_queue, connection=connection)]
```

`docs/CAPACITY_PLANNING.md` already has a sizing table for this, including a **10,000 jobs/day** row (48 vCPU / 96GB RAM / 5 Tier-1 hosts / 20 Tier-234 workers). This is solved and documented — nothing in this file changes Phase 1.

### 1.2 Phase 2 (candidate platform) — the actual gap

When `WORKER_QUEUE_MODE` is not `per_tier` (the default), a **single generic `worker` process** listens to five queues in a hardcoded priority order:

```python
# app/workers/rq_worker.py — "else" branch
queues = [
    Queue(QUEUE_FEEDBACK, connection=connection),
    Queue(QUEUE_DOCUMENT, connection=connection),
    Queue(QUEUE_EMBEDDING, connection=connection),
    Queue(QUEUE_CV_EXTRACTION, connection=connection),
    Queue(QUEUE_NAME, connection=connection),  # enrichment
]
```

`backend/docker/docker-compose.foundation.yml` adds two **opt-in** dedicated containers (`worker-document`, `worker-embedding`) that overlay this — but by default they aren't running, and even when they are, they compete for the same queues the generic worker already polls rather than replacing it. `feedback`, `cv_extraction`, and the cron-scheduled `audio_cleanup` queue have **no dedicated container at all**.

**Confirmed gap:** `docs/CAPACITY_PLANNING.md`'s sizing tables (Small/Medium/Large, up to 10,000 jobs/day) model **only** Phase 1 tiers. Phase 2 workers do not appear anywhere in that document at any load level. This file exists to close that gap.

### 1.3 Why a single Phase-2 worker is a real (not hypothetical) risk

RQ's own maintainers confirm queues are polled in **strict fixed priority order** — a worker started with `rq worker high low` will never touch `low` while `high` has backlog ([RQ README](https://github.com/rq/rq/blob/master/README.md); [rq/rq#1420](https://github.com/rq/rq/issues/1420) — ✅ DIRECT). This is exactly the shape of the list above: `feedback` > `document` > `embedding` > `cv_extraction` > `enrichment`. At 10,000 users/day, a burst of feedback-generation jobs will starve embedding generation and CV extraction indefinitely — this is documented RQ behavior, not a bug that would need to be filed.

A single process is also a **single point of failure across five pipelines**: one OOM (e.g., a large PDF, a bad Whisper batch) stops document processing, embeddings, feedback, and CV extraction simultaneously.

---

## 2. Sizing methodology — Little's Law, not guesswork

`capacity = throughput × latency` ([J.D.C. Little, 1961, *A Proof for the Queuing Formula: L = λW*, Operations Research](https://pubsonline.informs.org/doi/10.1287/opre.9.3.383), cited via [Shopify's engineering blog](https://shopify.engineering/building-resilient-payment-systems) — ✅ DIRECT, real academic origin, MIT). This is the one formula from the research pass that survived verification and is used for every worker-count estimate below.

Rearranged for worker sizing: `workers needed ≈ (jobs/day ÷ 86,400s) × latency_per_job_seconds`, rounded up, with a capacity buffer for spikes.

### Complementary framework: Google's "four golden signals"

To decide whether a feature needs new infrastructure at all (not just how many workers), this document uses Google's SRE "four golden signals" — **latency, traffic, errors, saturation** ([Google SRE Book, ch. 6](https://sre.google/sre-book/monitoring-distributed-systems/) — ✅ DIRECT, official, freely published). A feature only becomes an architectural "heavy hitter" when **all three** of traffic (volume), latency-per-unit (external API/LLM seconds vs. DB milliseconds), and saturation risk (does it compete for an already-tight resource) are simultaneously non-trivial. High traffic with sub-50ms Postgres CRUD is not heavy. Low traffic with a 5-second LLM call is not heavy either. See §6 for the full 13-feature classification built on this rubric.

---

## 3. Sizing table — Phase 2 queues at 10,000 users/day

Assumptions stated explicitly (change these and the table changes — see §9 blind spots):

- "10,000 users/day" = 10,000 daily-active candidates generating Phase-2 activity, not just signups
- 1 CV upload/user/day, ~8 embeddable chunks/CV
- 3-5 interview-practice attempts/user/day
- Job-matching scan runs once/day per user (fan-out, see §4)

| Queue | Volume/day | Latency/job | Workers (Little's Law) | Container status |
|---|---|---|---|---|
| `document_processing` | 10,000 | 8-15s | 2 | Exists (`worker-document`, opt-in overlay) |
| `embedding_generation` | ~160,000 (CVs + job postings, once Module 1 embeds postings too) | 1-2s | 3-4 | Exists (`worker-embedding`, opt-in overlay); real ceiling is the OpenAI rate-limit tier, not container count — unverifiable from repo, see §9 |
| `cv_extraction` | 10,000 | 4-8s | 1 | **New** — currently folded into the generic worker |
| `feedback` (interview scoring + CV rewrite + question generation, see §6.1) | ~80,000-90,000 (feedback ~40k + reclassified question generation ~30-50k) | 3-6s | 4-5 | Exists as a queue; needs more workers than currently allocated once question generation moves onto it |
| `job_matching_scan` (fan-out trigger) | 1 trigger → 10,000 staggered enqueues | n/a (scheduler, not a worker) | 1 scheduler process | **New** |
| `job_matching_score` (pgvector rank + top-5 LLM summary) | 10,000 rank queries + 50,000 LLM summaries | rank: ms; summary: 3-5s | 2-3 | **New** |
| `outreach_generation` | Variable, user-triggered (not scheduled) | 5-10s (LLM + external web-search API) | 1-2 | **New** — new external client required |
| `audio_cleanup` | 1 cron trigger/day | n/a | shares scheduler with `job_matching_scan` | Exists, but currently depends on whichever of `worker`/`worker-tier1`/`worker-tier234` happens to call `.work(with_scheduler=True)` first — see §5.3 |
| `notification` (email/SMS/webhook digest) | ~10,000 digests | <1s | 1 (reuse `worker-email`) | Exists, new job type only |

Net new worker processes beyond what exists today: **~10-12**, not the 6 *heavy dedicated containers* an earlier, unverified version of this plan proposed (see §7). Total Phase-2 process count at this scale: **~15-17**, which combined with Phase 1's ~29 (5 tier1 + 20 tier234 + 4 api, per `CAPACITY_PLANNING.md`) puts the full fleet at **~40-45 processes** — this number drives the Postgres connection-pool math in §5.1.

---

## 4. New primitive: the fan-out scheduler (AI job-matching scan)

`audio_cleanup_daily` (the only cron job that exists today, registered in `app/workers/queue.py::register_scheduled_jobs()`) is a **singleton** — one trigger, one function call, one queue entry, once a day. "Scan job boards for each of 10,000 users every 24h" is a fundamentally different shape: **one trigger needs to fan out into 10,000 independent enqueues**, and those 10,000 enqueues must not all hit JobSpy, Postgres, and pgvector in the same second.

This primitive does not exist in the codebase today and needs to be built new:

1. A single daily cron trigger (extends the existing `rq_scheduler.Scheduler.cron()` pattern already used for `audio_cleanup_daily` — no new scheduling framework needed).
2. The trigger reads the active-user table and enqueues N `job_matching_score` jobs, **staggered** across the day (e.g., bucketed by `user_id % N` into hourly windows) rather than dumped into the queue simultaneously.
3. Scoring itself should be **pgvector-first, LLM-last** (see §6.1 for why): rank job postings against the candidate's CV embedding via the existing HNSW-indexed `document_embeddings` table for the bulk of the 10,000 × ~50 candidate-jobs comparisons, and reserve GPT-4o-mini calls for the "why this job matches you" summary on only the **top 5** matches per user (10,000 × 5 = 50,000 LLM calls/day, not 500,000).

### Notification-engine tech mismatch (flagged, not yet fixed)

An earlier version of the Module 1 spec called for *"Notification engine — Celery beat + email/SMS workers."* This repo has **no Celery anywhere** — confirmed via `pyproject.toml` (only `redis`, `rq`, `rq_scheduler` are listed as queue dependencies). Introducing Celery beat alongside RQ would mean operating two separate queue frameworks for a capability (recurring/scheduled jobs) that `rq-scheduler` already provides. The fan-out scheduler in this section should extend `rq-scheduler`, not introduce Celery.

---

## 5. Two constraints that break before container topology matters

### 5.1 Postgres connection exhaustion

No connection pool size is configured anywhere in the codebase:

```python
# backend/app/database/session.py
_engine_kwargs: dict[str, Any] = {"future": True, "pool_pre_ping": True}
...
engine = create_async_engine(settings.database_url, **_engine_kwargs)
```

No `pool_size`/`max_overflow` override → SQLAlchemy's async-engine defaults apply: **5 pooled + 10 overflow = 15 connections per process** ([SQLAlchemy `create_engine` docs](https://docs.sqlalchemy.org/en/20/core/engines.html#sqlalchemy.create_engine.params.pool_size) — ✅ DIRECT). Postgres itself defaults to `max_connections = 100` ([PostgreSQL docs](https://www.postgresql.org/docs/current/runtime-config-connection.html) — ✅ DIRECT), unmodified in `backend/docker/Dockerfile.postgres` (confirmed: no `max_connections`, `shared_buffers`, or any `postgresql.conf` override present in that file at all).

At the ~40-45 process fleet size from §3:

```
~42 processes × 5 pooled connections  = 210 baseline connections
~42 processes × (5 + 10 overflow)     = 630 worst-case
```

**This is roughly 2x the default connection ceiling from idle pools alone**, before any overflow — this fails outright at well below 10,000 users/day, not gracefully.

**Fix (industry-standard, not a novel recommendation):** insert PgBouncer in transaction-pooling mode between all app/worker processes and Postgres — the documented standard pattern for exactly this many-clients/limited-backend-connections shape ([PgBouncer docs](https://www.pgbouncer.org/) — ✅ DIRECT). Additionally, set `pool_size`/`max_overflow` explicitly in `session.py` rather than relying on library defaults, so the ceiling is a deliberate, tested number.

### 5.2 pgvector HNSW index — confirmed still on out-of-the-box defaults

```python
# backend/alembic/versions/014_document_embeddings.py
# HNSW parameters: m=16 (connections per layer), ef_construction=64 (index build quality)
op.execute(
    "CREATE INDEX idx_embeddings_hnsw ON document_embeddings "
    "USING hnsw (embedding vector_cosine_ops) "
    "WITH (m = 16, ef_construction = 64)"
)
```

`m=16` and `ef_construction=64` are **pgvector's own shipped defaults** ([pgvector README](https://github.com/pgvector/pgvector/blob/master/README.md); cross-checked against multiple independent 2026 tuning guides — ✅ DIRECT). This migration wrote the defaults down explicitly; nothing was actually tuned.

At 10,000 users/day × ~8 chunks/CV ≈ 80,000 new rows/day even before Module 1 starts embedding job postings too → **~29M rows/year**. Multiple independent tuning sources flag the 10M-row mark as where untouched defaults measurably hurt recall/latency (e.g., [particula.tech's HNSW-at-scale guide](https://particula.tech/blog/pgvector-hnsw-tuning-millions-rows-production) — 🔗 INDIRECT, third-party but consistent across every source checked, not pgvector's own docs). At this growth rate, that threshold is crossed in **under 4-5 months**.

**Recommended change** (consistent across every tuning source checked): keep `m=16` (only raise if `ef_search` tuning alone can't hit your recall target), raise `ef_construction` to **128-200** (requires an index rebuild — plan this as a migration), and set the query-time `hnsw.ef_search` GUC to **100-200** per session (no rebuild required — this is the cheap, reversible dial to pull first and measure against before touching build-time parameters).

### 5.3 Scheduler registration is accidentally shared

```python
# backend/app/workers/rq_worker.py, line 108
worker.work(with_scheduler=True)
```

Every process that runs `app.workers.rq_worker.main()` — the generic `worker`, `worker-tier1`, **and** `worker-tier234` (all three extend the same Dockerfile/entrypoint) — calls `.work(with_scheduler=True)`, meaning the `audio_cleanup_daily` cron registration (and the new `job_matching_scan` fan-out trigger from §4) is registered by whichever of these processes happens to start first, not by a container whose job it is to own scheduling. RQ-Scheduler dedupes by job ID in Redis, so this doesn't double-fire — but it does mean Phase-2 scheduled work has an implicit, undocumented dependency on Phase-1 tier workers being up. Worth a dedicated lightweight `worker-scheduler` process if this dependency is ever a problem operationally.

---

## 6. Feature-by-feature classification (all 13 features named across this conversation)

### 6.1 Build status against actual code

| # | Feature | Status | Evidence |
|---|---|---|---|
| 1 | CV parser | ✅ Exists | `app/services/document_processor.py`, `app/services/cv_extractor.py`, `app/domain/candidate.py` (`CVData`) |
| 2 | AI search agent | ⚠️ Partial | `app/enrichers/jobspy.py` exists but runs on-demand per enrichment request, not as a recurring per-user scan (§4 covers the gap) |
| 3 | Smart notification | ⚠️ Partial | `worker-email` + SendGrid exist; scoring/digest logic is new; spec's "Celery beat" is a tech mismatch (§4) |
| 4 | Job swipe interface | ❌ New | No `swipe` matches anywhere in `backend/` |
| 5 | CV upload + completeness check | ✅ Exists (data side) | `completeness_score`, `missing_fields` already in `CVData` (`app/domain/candidate.py:46-47`), computed by `cv_extractor.py` |
| 5b | └ Chatbot for missing info | ❌ New | No `chatbot`/websocket matches anywhere; new real-time/streaming primitive, see §6.3 |
| 6 | CV improvement engine | ⚠️ Partial | `app/services/feedback_generator.py` + `feedback` queue already generate feedback; "rewrite bullet points" is a new prompt on existing infra |
| 7 | Portfolio manager | ❌ New | No `portfolio` matches; pure CRUD, no AI, no queue |
| 8 | Personalized outreach | ❌ New | No `outreach` matches; needs a new external client (e.g., Perplexity-class web-search API) |
| 9 | Question bank | ⚠️ Reclassified mid-conversation — see below | `app/services/question_generator.py`, `app/services/question_selector.py` |
| 10 | Text practice mode | ✅ Exists | Scored via `feedback` queue |
| 11 | Audio practice mode | ✅ Exists | `app/clients/speech.py` (Whisper), `app/services/audio_analysis.py`, `app/services/audio_storage.py` |
| 12 | Video practice mode | 🕒 Explicitly out of scope | Source spec itself: "future — not in 20-day scope" |
| 13 | Feedback report | ✅ Exists | `app/services/feedback_generator.py`, `app/workers/tasks/feedback.py` |

**Question bank correction (important — this changes the sizing in §3):** the current `question_generator.py::generate_questions()` takes **no `user_id`, no CV data, no job description** — it's a generic bulk/seed-time generator (role/category/difficulty only) that fills a shared pool. The per-candidate-facing path, `question_selector.py::select_questions()`, makes **zero LLM calls** — it's a filtered DB read (job-role match, exclude-recently-attempted-in-7-days, rotate by `usage_count`, random tiebreak). This is why an initial pass classified question bank as "Light."

**Confirmed requirement during this conversation: every practice question should be freshly AI-generated per candidate**, not selected from the shared pool. This reclassifies question generation from a one-time seed cost to a recurring per-candidate LLM cost: ~10,000 candidates × 3-5 questions/session ≈ **30,000-50,000 fresh GPT-4o-mini calls/day**, same execution shape as `feedback`/`cv_extraction` (async batch, LLM-per-user, external-provider-latency-bound). No new container is needed — extend `generate_questions()` to accept `user_id` + CV/job context and route it through the existing `feedback` queue's worker pool rather than building a dedicated `worker-question-gen`. `select_questions()`'s rotation/dedup logic should be retired or repurposed as a per-candidate history check rather than a shared-pool filter. This is reflected in the `feedback` queue's volume estimate in §3 (~80,000-90,000/day, combining feedback scoring + question generation).

### 6.2 Classification by the golden-signals rubric (§2)

| # | Feature | Traffic/day | Latency/unit | Saturation risk | Verdict |
|---|---|---|---|---|---|
| 1 | CV parser | 10,000 | 8-15s | Low (isolated queue) | 🟡 Medium |
| 2 | AI search agent | 10,000 fan-out (500k naive / ~60k with pgvector-first design) | High if LLM-per-job; low if pgvector-first | **High** — new fan-out primitive | 🔴 **Heavy** |
| 3 | Smart notification | ~10,000 | <1s | Low (reuses `worker-email`) | 🟢 Light |
| 4 | Job swipe interface | Potentially 100,000+ (many swipes/user) | <50ms (CRUD) | Low individually; high traffic ≠ heavy per this rubric | 🟡 Medium |
| 5 | CV upload + completeness check | 10,000 | 4-8s | Low (isolated queue) | 🟡 Medium |
| 5b | Chatbot follow-up questions | Session-based, variable | Streaming, held-open | **High** — new resource class (connection concurrency, not throughput) | 🔴 **Heavy** (different reason than #2/#8) |
| 6 | CV improvement engine | ~10,000 | 3-6s | Low (reuses `feedback`) | 🟡 Medium |
| 7 | Portfolio manager | Low-moderate | <50ms (CRUD) | None | 🟢 Light |
| 8 | Personalized outreach | User-triggered, lower than scheduled features | 5-10s (LLM + external search API) | **Medium-high** — new rate-limited external dependency | 🔴 **Heavy** |
| 9 | Question bank (per-candidate generation, confirmed) | ~30,000-50,000 | 2-4s | Medium (shares `feedback` queue/LLM saturation) | 🟡 **Medium-Heavy** (reclassified from Light) |
| 10 | Text practice mode | ~10,000-30,000 | 2-4s | Low (reuses `feedback`) | 🟡 Medium |
| 11 | Audio practice mode | ~30,000 | 2-4s (Whisper) | Medium (external API + storage churn) | 🟡 Medium |
| 12 | Video practice mode | N/A | N/A | N/A | ⚪ Out of scope |
| 13 | Feedback report | ~40,000+ | 3-6s | Low (reuses `feedback`) | 🟡 Medium |

**Final tally:** 3 genuine heavy hitters (AI search agent, personalized outreach, question generation), 1 heavy-for-a-different-reason (chatbot concurrency), 7 medium, 2 light (portfolio, notification delivery), 1 out of scope (video). This is a materially smaller "genuinely new infrastructure" surface than "13 features, treat them all as heavy" would suggest — consistent with the real (verified) Uber Cadence and Google Borg lesson in §7: consolidate where traffic doesn't justify a split, isolate only where it does.

### 6.3 The chatbot's different resource class

Swipe UI, the CV-completeness chatbot, and text-practice mode all imply request/response or streaming interactions held open on the `api` container — a **concurrency-per-instance** problem (ASGI event loop capacity), not a **queue-depth** problem. This doesn't need new RQ workers; it needs the `api` service's replica count and Postgres pool sizing (§5.1) to account for held-open streaming connections, which behave differently under load than short REST calls. This has not been load-tested and can't be sized from the repo alone — flagged as an open item in §9.

---

## 7. Evidence audit — what earlier big-tech citations actually say

An earlier pass at this plan cited six companies as "all DIRECT evidence" for a 6-dedicated-container strategy. Each claim was re-checked against its primary source. Several do not hold up, and two actually argue the opposite:

| Original claim | What the primary source actually says | Verdict |
|---|---|---|
| RQ starves low-priority queues under fixed multi-queue polling unless split into separate workers | [RQ README](https://github.com/rq/rq/blob/master/README.md) + [rq/rq#1420](https://github.com/rq/rq/issues/1420): confirmed verbatim — "`rq worker high low` will always dequeue from `high` first... `low` will only be processed when `high` is empty" | ✅ **DIRECT** — matches this repo's own code exactly (§1.3) |
| Little's Law (`capacity = throughput × latency`) is the correct first-principles sizing tool | [Little, 1961, *Operations Research*](https://pubsonline.informs.org/doi/10.1287/opre.9.3.383), cited by [Shopify's eng blog](https://shopify.engineering/building-resilient-payment-systems) | ✅ **DIRECT** — real, peer-reviewed, MIT origin |
| Shopify: priority-queue separation cut P99 from 45min to 2min | Could not find this statistic anywhere in Shopify's public engineering writing. [Kir Shatrov's "State of Background Jobs in 2019"](https://kirshatrov.com/posts/state-of-background-jobs) (Shopify staff eng) says the **opposite** — that simple priority-queue separation "has issues with aging and scaling" at Shopify's actual scale (2B jobs/day) | 🔎 **NOT FOUND** — likely fabricated |
| Uber Cadence: separating activity workers from orchestration improved reliability by 40% | [Uber's actual Cadence blog](https://www.uber.com/gb/en/blog/cadence-multi-tenant-task-processing/) describes the **opposite** direction of change: Uber *consolidated* from per-shard worker pools to one shared host-level pool, cutting goroutines from 16,000 to 100 (a 95% reduction), and fixed noisy-neighbor problems via **prioritization inside one pool** | 🔎 **NOT FOUND** — real Uber lesson contradicts the claim as stated |
| Google Borg: dedicate separate machine pools by resource type (CPU vs. memory), cutting cost 30% | [Verma et al., *Large-scale cluster management at Google with Borg*, EuroSys 2015](https://static.googleusercontent.com/media/research.google.com/en/us/pubs/archive/43438.pdf): Borg deliberately **shares** machines between latency-sensitive and batch workloads; splitting into separate pools by resource type would need "2-16× as many cells, and 20-150% additional machines" | 🔎 **NOT FOUND** — the paper argues against exactly this strategy |
| Airbnb: "Kubernetes at Airbnb" blog mandates splitting CPU-heavy and memory-heavy workers into dedicated pools | Could not locate this claim under this title on Airbnb's engineering blog. Airbnb's real, verifiable resource-profile split is in their data-infra post (Hive/HDFS = storage-bound, Presto/Spark = memory-bound; ~2x speedup, 70% cost cut from that specific split) | 🔎 **NOT FOUND** as originally cited; 🔗 **INDIRECT** support exists for the general principle, under a different, real citation |
| Netflix: container-per-service isolates blast radius, prevents cascading failure | Netflix's Data Gateway post: sharding "minimize[s] the blast radius of misbehaving applications and protect[s] the broader Netflix product from noisy neighbors"; Hystrix gives each dependency its own thread pool/bulkhead; Titus gives each container its own IAM role | ✅ **DIRECT** — the one claim from the original six that holds up as stated, once re-sourced to Hystrix/Data Gateway/Titus rather than the chaos-engineering posts (which are about *testing* blast radius, not *creating* the isolation) |

**Implication for this document:** the sizing decisions in §3-§6 are built on Little's Law + this repo's own confirmed code behavior + Google's golden-signals framework — the two claims that survived verification — rather than on the six-company "consensus" that motivated the original 6-container proposal. The actual verified lesson from Uber and Google is **consolidate, don't fragment, unless traffic specifically justifies the split** — which is why §3 proposes ~10-12 new processes split by queue, not 6 new heavyweight service images.

---

## 8. Proposed container/queue layout at 10,000 users/day

Reusing the `extends:` pattern this repo already uses for Phase 1 (`docker-compose.tier-workers.yml` extending the base `worker` service) rather than inventing a new mechanism:

```
Postgres (pgvector, ef_construction retuned to 128-200 — §5.2)
   ↑ via PgBouncer (transaction pooling — new, §5.1)
   │
API ×4 (existing) ── Redis ── ┬─ worker-tier1 ×5           (Phase 1, existing, unchanged)
                               ├─ worker-tier234 ×20         (Phase 1, existing, unchanged)
                               ├─ worker-document ×2         (Phase 2, promote foundation.yml overlay to default)
                               ├─ worker-embedding ×3-4      (Phase 2, promote; cap by verified OpenAI rate-limit tier)
                               ├─ worker-cv-extraction ×1    (Phase 2, NEW — split off generic worker)
                               ├─ worker-feedback ×4-5       (Phase 2, existing queue, NEW dedicated container —
                               │                              absorbs feedback + question generation + text practice)
                               ├─ worker-job-matching ×2-3   (Phase 2, NEW — job_matching_score queue)
                               ├─ worker-outreach ×1-2       (Phase 2, NEW — outreach_generation queue)
                               ├─ worker-scheduler ×1        (Phase 2, NEW — owns job_matching_scan fan-out +
                               │                              audio_cleanup_daily, decouples from Phase 1 workers, §5.3)
                               ├─ worker-email ×1            (existing, unchanged)
                               └─ worker-cleanup ×1          (existing, unchanged)
```

Total: ~29 Phase-1 processes + ~15-17 Phase-2 processes ≈ **~40-45 processes**, all behind one PgBouncer instance, each queue getting its own worker so no Phase-2 queue can starve another the way the current single generic worker can.

Implementation note: this requires editing `app/workers/rq_worker.py`'s "else" branch (§1.2) to stop listening to `feedback`/`document`/`embedding`/`cv_extraction` once dedicated containers exist for them — otherwise the generic worker keeps double-polling queues it was never sized for.

---

## 9. Explicit blind spots and unverifiable assumptions

Flagged deliberately rather than silently assumed, per this document's evidence-labeling standard:

1. **"10,000 users/day" ambiguity.** This document assumes 10,000 *daily-active* candidates generating Phase-2 activity. If it instead means 10,000 new signups/day with a lower daily-active rate (e.g., 20%), every volume estimate in §3 and §6.2 shrinks proportionally — re-run the Little's Law math under the real definition before committing hardware spend.
2. **OpenAI (or other LLM provider) rate-limit tier is unknown from the repo.** `worker-embedding` and every `feedback`-queue consumer (feedback, CV extraction, question generation, job-match summaries) share this ceiling. Container count is irrelevant once the provider's requests-per-minute/tokens-per-minum cap is hit — this must be checked against the actual account tier, not estimated.
3. **Job swipe volume (#4, §6.2) is a placeholder guess** (100,000+/day assumes heavy multi-swipe sessions). Real behavioral data or a target session length would let this be sized precisely instead of bounded.
4. **Chatbot / streaming connection concurrency (§6.3) has not been load-tested.** ASGI event-loop capacity per `api` replica under held-open SSE/WebSocket connections is a different failure mode than short REST latency and needs its own test, not an estimate.
5. **New external dependencies (Perplexity-class search for outreach, Hume AI/Deepgram-class sentiment for audio) are unpriced and unrate-limited in this analysis.** Per this repo's own established convention (`LLM_MODE` stub-by-default, R2→local fallback, Reacher behind `profiles: ["paid"]`, all documented in `backend/docs/ARCHITECTURE.md`'s "Do not assume" table), any new client for these should degrade to empty/stubbed output when the key is absent, not become a hard dependency.
6. **Video practice mode (#12) is intentionally excluded** per the source spec's own scope statement — not sized here, will need its own architecture pass if pulled into scope later.
7. **Postgres `max_connections` and PgBouncer pool-size tuning (§5.1) are stated as a fix, not yet load-tested against the real ~40-45 process count.** The math shown is a ceiling calculation from documented defaults, not a benchmark.
8. **HNSW `ef_construction` retune (§5.2) requires a migration + index rebuild on a live table.** At 10k-scale daily embedding volume, this should be scheduled as a planned maintenance window (`CREATE INDEX CONCURRENTLY` where supported), not a hot-swap.

---

## 10. Summary — what changes, in priority order

1. **Set explicit Postgres pool sizing + PgBouncer** (§5.1) — this fails silently below 10,000 users/day regardless of any other decision in this document; highest priority.
2. **Split `feedback`/`cv_extraction` off the generic worker** into dedicated containers (§8) — cheap, immediate fix for the confirmed RQ starvation risk (§1.3), no new Dockerfiles needed (same image, different `command:`).
3. **Promote `worker-document`/`worker-embedding` from opt-in overlay to default**, and remove those queues from the generic worker's listen-list (§8) so there's no redundant double-polling.
4. **Build the fan-out scheduler primitive** (§4) for job-matching scans — does not exist today, needed for Module 1 regardless of container topology.
5. **Design `job_matching_score` as pgvector-first, LLM-last** (§4, §6.1) — this single design choice is what keeps Module 1 from requiring 500,000 LLM calls/day instead of ~60,000.
6. **Reclassify and route per-candidate question generation through the `feedback` queue** (§6.1) rather than building a dedicated container — reuses existing sizing.
7. **Retune the HNSW index** (§5.2) before the 10M-row threshold is crossed (~4-5 months at this growth rate).
8. **Add a Phase-2 section to `docs/CAPACITY_PLANNING.md`** — it currently only models Phase 1, at any load level, which is the root gap this document was written to close.
9. **Load-test the chatbot's streaming concurrency separately** (§6.3, §9) — it's a different resource class than every other item in this list and hasn't been estimated, only flagged.
