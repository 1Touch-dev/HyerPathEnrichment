# Phase 2 Docker Infrastructure Plan — AI Candidate Platform

**Branch:** `master-complete-foundation`
**Status:** Implementation-ready — consolidates the Docker sections of `phase2_module1.md` (§9), `phase2_module2.md` (§10), `phase2_module3.md` (§8), and `architecture_phase2.md` (§5, §8) into one linear, non-conflicting build plan.
**Purpose of this document:** a developer (or agent) who applies every step below, in order, ends with a Docker/Compose topology where **every container for Phase 1 + Phase 2 builds, boots, passes its healthcheck, and can reach every other container it depends on** — with zero `docker compose config` errors, zero Docker network/DNS errors, and zero silently-unconsumed queues. This document does not re-explain the business logic inside each module (routes, services, ORM models) — that is `phase2_module1.md`/`2`/`3`'s job. This document owns exactly one thing: **can the containers build, boot, and talk to each other correctly.**

**Evidence labels used throughout** (same convention as `architecture_phase2.md` §0):
- ✅ **DIRECT** — confirmed by reading this repo's actual files in this session, or an official primary source
- 🔧 **CORRECTION** — a specific place where a module plan's proposed Docker artifact does not match this repo's real, verified build pattern, and would fail if applied verbatim. Fixed here, once, so it isn't fixed three different ways in three different PRs.
- 🆕 **NEW** — introduced by this document specifically to make the three modules' independent Docker proposals coexist without port/queue/network conflicts (none of the three module docs cross-reference each other's Docker section, so this document is the first place they are reconciled)

---

## 0. How to use this document

Apply §5 in the exact numbered order given (each step depends on the previous one existing). After every step, run the "Validate" command shown for that step before moving to the next one — this is what "no docker error" and "no docker network error" mean operationally: `docker compose config` must parse with no warnings, and every container that step introduces must reach `healthy` in `docker compose ps` before you continue. §9 gives you one final end-to-end boot runbook that replays all of it in the correct dependency order for a clean machine. §10 is what to do when something fails anyway.

---

## 1. Ground truth — the container fleet that exists today (verified by reading every file, not assumed)

### 1.1 Compose files in `backend/docker/` (verified via directory listing)

| File | Role | Verified content |
|---|---|---|
| `docker-compose.yml` | Base stack — always used | `migrate`, `api`, `worker` (generic), `redis`, `postgres`, `social-analyzer`, `google-maps-scraper`, `email-verifier`, `worker-email`, `worker-cleanup`, plus profile-gated `reacher`/`litellm`/`ollama`/`scrapoxy`/`langfuse`/`changedetection`/`glitchtip-*` |
| `docker-compose.foundation.yml` | Opt-in overlay, Foundation Week 1 | `worker-document`, `worker-embedding` |
| `docker-compose.tier-workers.yml` | Opt-in overlay, Phase 1 tiers | `worker-tier1` (`network_mode: host`), `worker-tier234` (bridge) |
| `docker-compose.prod.yml` | Production overlay | Env-file wiring + `ports: !override` restrictions for `api`/`postgres`/`redis`/sidecars |
| `docker-compose.staging.yml`, `docker-compose.tier1.yml`, `docker-compose.multilogin.yml`, `docker-compose.loadtest.yml`, `docker-compose.fake-sidecars.yml` | Other opt-in overlays (staging config, Linux Multilogin sidecar, load-test fixtures, CI fake sidecars) | Not modified by this plan — out of scope |

### 1.2 What the generic `worker` container actually listens to today (verified: `backend/app/workers/rq_worker.py:58-75`)

```python
queues = [
    Queue(QUEUE_FEEDBACK, connection=connection),        # "feedback"
    Queue(QUEUE_DOCUMENT, connection=connection),        # "document_processing"
    Queue(QUEUE_EMBEDDING, connection=connection),       # "embedding_generation"
    Queue(QUEUE_CV_EXTRACTION, connection=connection),   # "cv_extraction"
    Queue(QUEUE_NAME, connection=connection),            # "enrichment"
]
```

This is the fixed-priority list RQ's `Worker` actually honors (list order = priority — verified against [RQ README](https://github.com/rq/rq/blob/master/README.md) and [rq/rq#1420](https://github.com/rq/rq/issues/1420), ✅ DIRECT). This is the **only** mechanism that matters for starvation. `QUEUE_PRIORITIES` (`backend/app/workers/queue.py:24-33`) is a **plain Python dict that is never imported or read anywhere else in the codebase** (verified: `grep -r QUEUE_PRIORITIES backend/` returns only its own definition file) — it is documentation-only metadata today, not an enforced priority. Every module doc's "priority: 6" / "priority: 4" annotation refers to this dict, **not** to actual RQ behavior. §4.6 below has the real, list-order reconciliation.

### 1.3 Networking model (verified against `backend/docker/NETWORKING.md` + the compose files themselves)

- **Bridge network (default)** — `api`, generic `worker`, `worker-email`, `worker-cleanup`, `worker-document`, `worker-embedding`, `worker-tier234`, `postgres`, `redis`, and all sidecars. Service discovery via Docker DNS (`postgres`, `redis`, `email-verifier`, ...).
- **Host network (`network_mode: host`)** — `worker-tier1` only, because Multilogin binds Selenium to `127.0.0.1` and only a shared loopback namespace can reach it. `worker-tier1` therefore addresses every dependency (Postgres, Redis, sidecars) via `127.0.0.1:<port>`, never by service name — this is the #1 source of "could not translate host name" errors when someone copies a bridge-network environment block onto a host-network service, or vice versa (see §10.1).
- **No new networking mode is required by any Phase 2 module.** Every new Phase 2 container in this plan is bridge-network, joins `networks: [default]`, and is addressed by service name — confirmed necessary and sufficient because none of Module 1/2/3's new services touch Multilogin/Selenium.

### 1.4 A verified, pre-existing gap this plan must also close: `audio_cleanup` has no consumer

`backend/app/workers/queue.py::register_scheduled_jobs()` schedules a daily cron job onto `QUEUE_AUDIO_CLEANUP` (`"audio_cleanup"`). **No compose service, and no branch of `rq_worker.py`, lists `"audio_cleanup"` in any queue it listens to** (verified: `grep -rn QUEUE_AUDIO_CLEANUP backend/app` returns only the constant definition and the `register_scheduled_jobs()` call — no `Queue(QUEUE_AUDIO_CLEANUP, ...)` anywhere). This queue has been silently unconsumed since Foundation Week 2 shipped it, independent of anything in Modules 1-3. §5.2 fixes it as part of the same edit that adds the new Phase 2 queues, since it is the same list.

---

## 2. What Modules 1-3 each ask for, verified against their own Docker sections

| Module | New Dockerfile? | New compose service? | New/changed queue | Where it runs |
|---|---|---|---|---|
| **1 — Job Matching** (`phase2_module1.md` §9) | `Dockerfile.worker-job-matching` | `worker-job-matching` in `docker-compose.foundation.yml` | `job_matching` (**dedicated**, isolated — never joins the generic worker's list) | New, own container, `replicas: 1` |
| **2 — Job Board/CV/Portfolio/Outreach** (`phase2_module2.md` §10) | None | None (explicitly "zero Dockerfile changes and zero compose-file changes," §10.4) | `outreach_generation` (**shared** — added to generic `worker`'s list) | Existing generic `worker` container |
| **3 — Interview Prep** (`phase2_module3.md` §8) | None (reuses `Dockerfile.worker`) | `worker-interview-ai` in new `docker-compose.week2-ai.yml` | `question_generation` (**new**, isolated on the new overlay — but ALSO left in the generic worker's list as a documented fallback for environments not running the overlay) | Generic `worker` (fallback) **or** dedicated `worker-interview-ai` overlay |

**The conflict these three create when merged naively:** Module 2 inserts `outreach_generation` into the generic worker's list "immediately after `feedback`." Module 3 inserts `question_generation` into the same list "immediately after `feedback`." Both claim the same list position because neither module's author could see the other's edit. §4.6 gives the one, final, reconciled list order. This is exactly the kind of conflict a "developer follows the .md and it just works" plan cannot leave ambiguous.

---

## 3. Cross-cutting infrastructure fixes required by `architecture_phase2.md` §5 (must land before/alongside Modules 1-3, not after)

These are called out in `architecture_phase2.md` as the two things that **break before container topology matters at all** (§5.1, §5.2). They are Docker/infra concerns (connection ceiling, index tuning), so they belong in this plan, not in any single module's PR.

### 3.1 Postgres connection-pool ceiling (§5.1 of `architecture_phase2.md`)

No explicit `pool_size`/`max_overflow` anywhere in `backend/app/database/session.py` (verified — `_engine_kwargs` only sets `future` and `pool_pre_ping`). SQLAlchemy's async-engine default (5 pooled + 10 overflow **per process**) applies uncapped. Every new Phase 2 container in §5 below is one more process holding its own pool against the same Postgres — `worker-job-matching` and `worker-interview-ai` alone add 2 more processes × up to 15 connections each = 30 more potential connections against a default `max_connections=100` ceiling that Phase 1 alone already pressures (per `architecture_phase2.md` §5.1's ~42-process fleet math). §5.1 below adds PgBouncer and explicit pool sizing as part of this plan, not as a follow-up.

### 3.2 pgvector HNSW defaults (§5.2 of `architecture_phase2.md`)

Out of scope for **this** document — it is an Alembic migration (`backend/alembic/versions/014_document_embeddings.py`), not a Docker/Compose change. Flagged here only so it is not mistaken for "covered" by this plan. See `architecture_phase2.md` §5.2 for the retune values (`ef_construction` 128-200, `hnsw.ef_search` 100-200) and §9 blind spot 8 for why it needs its own migration PR with `CREATE INDEX CONCURRENTLY`.

### 3.3 Scheduler registration race (§5.3 of `architecture_phase2.md`)

Every process running `rq_worker.py`'s `main()` calls `worker.work(with_scheduler=True)`. RQ-Scheduler dedupes cron registrations by job ID in Redis, so this does not double-fire — but §5 below adds two **more** processes (`worker-job-matching`, `worker-interview-ai`) that also call `.work(with_scheduler=True)` (per Module 1's own new entrypoint, `rq_worker_job_matching.py`). This remains an accepted, pre-existing pattern (not newly broken by this plan) — documented so it is not mistaken for a new bug introduced here.

---

## 4. Reconciliation decisions (🆕 NEW — these did not exist in any single module doc)

### 4.1 🔧 CORRECTION — Module 1's proposed `Dockerfile.worker-job-matching` does not match this repo's real build pattern

`phase2_module1.md` §9.1 proposes a Dockerfile using `poetry install` and claims it "copies the exact structure of the existing `Dockerfile.worker-document`." **Verified false**: `backend/docker/Dockerfile.worker-document` (read directly in this session) uses `pip install --no-cache-dir -e .` — there is no `poetry.lock` anywhere in this repository (verified: no `poetry.lock` file exists in `backend/`), and no other Dockerfile in `backend/docker/` uses Poetry. Applying Module 1's Dockerfile verbatim would either fail outright (no lockfile to copy) or silently build successfully but diverge from every other worker image's dependency-resolution behavior. §5.4 below gives the corrected Dockerfile, using the same `pip install -e .` pattern as `Dockerfile.worker-document`/`Dockerfile.worker-embedding`, with the same non-root `useradd -u 1000 worker` pattern `Dockerfile.worker-embedding` already uses (verified — `Dockerfile.worker-document` does *not* create a non-root user; `Dockerfile.worker-embedding` does; this plan follows the more secure, non-root pattern for the new image, consistent with `Dockerfile.worker-embedding` since job-matching is resource-shape-identical to embedding per Module 1's own §9.3 sizing rationale).

### 4.2 🆕 NEW — `WORKER_EXCLUDE_QUEUES`: the missing primitive that lets isolated overlays and the generic worker coexist without double-polling

Module 3 explicitly documents (§8.2 design notes) that once `docker-compose.week2-ai.yml` is adopted, `feedback`/`question_generation` "should be removed from the base `worker` service's own listened-to set to avoid double-processing" — but describes this as a manual, per-environment operational choice, with no actual mechanism to do it without hand-editing `rq_worker.py` per deployment (which would break every environment that hasn't adopted the overlay). This plan adds one small, backward-compatible mechanism: an optional `WORKER_EXCLUDE_QUEUES` env var (comma-separated queue names), read by the generic worker's branch of `rq_worker.py`, defaulting to empty (i.e., **zero behavior change** for any environment that doesn't set it — local dev is unaffected). When `docker-compose.week2-ai.yml` or `worker-job-matching` is running in an environment, set `WORKER_EXCLUDE_QUEUES=feedback,question_generation` on the generic `worker` service in that environment's overlay to stop it from redundantly competing for queues a dedicated container already owns. This is the mechanical fix for the exact problem Module 3 named but didn't solve, using this repo's own existing "env var flips behavior, safe default" convention (`LLM_MODE`, `PROXY_MODE`, `BROWSER_MODE` all follow this shape already).

### 4.3 🆕 NEW — audio_cleanup gets a consumer

Per §1.4's verified gap: add `QUEUE_AUDIO_CLEANUP` to the generic worker's queue list, lowest priority position (matches its `QUEUE_PRIORITIES` weight of 1, the lowest in the dict — the one place in this plan where the documentation-only priority dict and the actual list happen to agree once this fix lands).

### 4.4 Final reconciled generic-worker queue list (resolves §2's conflict)

Ordering rationale, made explicit rather than left to chance: `feedback` (user is waiting) → `outreach_generation` (user-initiated, waiting on a spinner, per Module 2 §10.2 — same urgency class as feedback) → `document_processing` (async upload processing, no one is watching a spinner) → `question_generation` (explicitly "not user-blocking" per Module 3's own §7.5 comment — pre-generation, lower urgency than either document or embedding processing since nothing downstream is blocked on it existing *yet*) → `embedding_generation` (pure batch) → `cv_extraction` (kept in its existing, pre-Phase-2 position — reordering it is out of scope for this plan; `RULE.md`'s "fix only what the task needs" applies: the `CV_EXTRACTION` priority-dict/list-order mismatch noted in §1.2 is a pre-existing Foundation Week 1 inconsistency, not introduced by Phase 2, and is not touched here) → `enrichment` (Phase 1 fallback, lowest) → `audio_cleanup` (maintenance, per §4.3).

```python
# backend/app/workers/rq_worker.py — final "else" branch after Modules 1-3 (job_matching
# is deliberately absent — it never joins this list; see §5.4/§5.5, dedicated container only)
queues = [
    Queue(QUEUE_FEEDBACK, connection=connection),
    Queue(QUEUE_OUTREACH, connection=connection),           # Module 2
    Queue(QUEUE_DOCUMENT, connection=connection),
    Queue(QUEUE_QUESTION_GENERATION, connection=connection), # Module 3
    Queue(QUEUE_EMBEDDING, connection=connection),
    Queue(QUEUE_CV_EXTRACTION, connection=connection),
    Queue(QUEUE_NAME, connection=connection),
    Queue(QUEUE_AUDIO_CLEANUP, connection=connection),        # this plan, §4.3
]
```

The exact code for this, filtered by `WORKER_EXCLUDE_QUEUES`, is in §5.2.

---

## 5. Implementation steps — apply in this exact order

Every step names every file it touches by exact path. "Validate" is the command to run before moving to the next step.

### 5.1 Postgres connection ceiling — PgBouncer service + explicit pool sizing

**Why first:** every later step in this plan adds one more process holding its own connection pool against Postgres (§3.1). Fixing the ceiling before adding more processes means each later step's healthcheck failures (if any) are attributable to that step, not to a connection-exhaustion problem that was already latent.

**New file: `backend/docker/docker-compose.pgbouncer.yml`**

Named as its own overlay (not folded into the base `docker-compose.yml`) so that `docker compose -f docker-compose.yml up` alone — the simplest possible local-dev invocation — keeps working exactly as it does today, unchanged, for anyone who hasn't opted into the Phase 2 topology yet. This follows the same "additive overlay, base file untouched" convention already established by `docker-compose.foundation.yml` and `docker-compose.tier-workers.yml`.

```yaml
# PgBouncer — transaction-pooling connection ceiling in front of Postgres.
# Fixes architecture_phase2.md §5.1: SQLAlchemy's async-engine default (5
# pooled + 10 overflow per process) applied uncapped across the ~9-13
# processes this Phase-2 topology introduces would exceed Postgres's default
# max_connections=100 well before 10,000 users/day. PgBouncer in transaction
# mode multiplexes many client connections onto a small, fixed number of real
# Postgres backend connections.
# Usage: add `-f docker-compose.pgbouncer.yml` to every `docker compose` command
# that also uses `-f docker-compose.foundation.yml` and/or `-f docker-compose.week2-ai.yml`
# (see §7's command matrix). Safe to add unconditionally — it does not change
# any other service's behavior unless that service's DATABASE_URL points at it.

services:
  pgbouncer:
    image: edoburu/pgbouncer:1.21.0
    container_name: hyerenrichment-pgbouncer
    environment:
      DB_USER: hyrepath
      DB_PASSWORD: ${POSTGRES_PASSWORD}
      DB_HOST: postgres
      DB_NAME: hyrepath
      AUTH_TYPE: scram-sha-256   # matches postgres:16-alpine's default password encryption
      POOL_MODE: transaction
      MAX_CLIENT_CONN: 1000
      DEFAULT_POOL_SIZE: 25      # real backend connections PgBouncer opens to Postgres
      MIN_POOL_SIZE: 5
      ADMIN_USERS: hyrepath
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "pg_isready", "-h", "127.0.0.1", "-p", "5432", "-U", "hyrepath"]
      interval: 10s
      timeout: 5s
      retries: 12
      start_period: 15s
    restart: unless-stopped
```

**Design notes:**
- No `ports:` mapping — PgBouncer is reached over the bridge network by service name (`pgbouncer:5432`) from other containers, exactly like `postgres` is today; it does not need a host port unless you want to `psql` into it directly from the host for debugging (add `ports: ["127.0.0.1:6432:5432"]` locally if you need that — do not do this in `docker-compose.prod.yml`, matching the existing "loopback-only in prod" convention `docker-compose.prod.yml` already applies to `postgres`/`redis`).
- `DEFAULT_POOL_SIZE: 25` is the real ceiling: **25 real Postgres backend connections total**, no matter how many application processes connect through PgBouncer, versus today's unbounded-by-container-count model. This is the number to raise if `pgbouncer` logs `no more connections allowed` under load — not `max_connections` on Postgres itself.
- `AUTH_TYPE: scram-sha-256` — verified against `edoburu/docker-pgbouncer`'s own documented example for Postgres 14+ (this repo's `Dockerfile.postgres` is `postgres:16-alpine`, ✅ compatible). If you ever downgrade the Postgres major version below 10, this line must change to `md5` per the image's own README.

**Which services must repoint `DATABASE_URL` at PgBouncer:** `api`, `migrate` (⚠️ **do not** point `migrate` at PgBouncer — Alembic's `CREATE INDEX CONCURRENTLY`/DDL and PgBouncer's transaction pooling do not mix well for schema migrations; `migrate` keeps talking to `postgres:5432` directly, unchanged), generic `worker`, `worker-email`, `worker-cleanup`, `worker-document`, `worker-embedding`, `worker-tier234`, and the two new Phase 2 workers from §5.5/§5.7 (`worker-job-matching`, `worker-interview-ai`). `worker-tier1` (host network) would point at `pgbouncer:5432` too, but host-network containers cannot use Docker DNS service names (§1.3) — see §8.1 for the host-network-specific PgBouncer wiring.

Exact edit, applied identically to every one of those services' `environment:` blocks (`backend/docker/docker-compose.yml`, `backend/docker/docker-compose.foundation.yml`, `backend/docker/docker-compose.tier-workers.yml`'s `worker-tier234` block):

```yaml
# Before:
DATABASE_URL: postgresql+asyncpg://hyrepath:${POSTGRES_PASSWORD}@postgres:5432/hyrepath
# After (bridge-network services only — see §8.1 for worker-tier1):
DATABASE_URL: postgresql+asyncpg://hyrepath:${POSTGRES_PASSWORD}@pgbouncer:5432/hyrepath
```

**Code edit required alongside this — `backend/app/database/session.py`:** transaction-mode PgBouncer does not support asyncpg's server-side prepared-statement cache across pooled connections (a connection can be handed to a different logical client between statements) — using it unmodified produces `prepared statement "__asyncpg_stmt_N__" does not exist` errors under load, a well-documented asyncpg/PgBouncer interaction (✅ DIRECT — [asyncpg FAQ, "Prepared Statements"](https://magicstack.github.io/asyncpg/current/faq.html#does-asyncpg-support-pgbouncer); [SQLAlchemy asyncpg dialect docs](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#disabling-the-postgresql-jit-to-improve-enum-datatype-handling) discuss the same `statement_cache_size=0` fix for pgbouncer transaction mode). Also set explicit `pool_size`/`max_overflow` per `architecture_phase2.md` §5.1's recommendation, rather than relying on SQLAlchemy's library defaults:

```python
# backend/app/database/session.py
_engine_kwargs: dict[str, Any] = {"future": True, "pool_pre_ping": True}
if settings.database_url.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"timeout": 30}
elif settings.database_url.startswith("postgresql"):
    # Explicit ceiling per architecture_phase2.md §5.1 — do not rely on
    # SQLAlchemy's library default (5 pooled + 10 overflow/process); with
    # PgBouncer (§5.1 of this plan) already capping real backend connections
    # at DEFAULT_POOL_SIZE=25, each process's own client-side pool should stay
    # small so PgBouncer — not this process — is the single source of truth
    # for the connection ceiling.
    _engine_kwargs["pool_size"] = int(os.environ.get("DATABASE_POOL_SIZE", "5"))
    _engine_kwargs["max_overflow"] = int(os.environ.get("DATABASE_MAX_OVERFLOW", "2"))
    # PgBouncer transaction-pooling mode does not support asyncpg's
    # server-side prepared-statement cache (a pooled connection can be handed
    # to a different logical client between statements) — disabling it here
    # avoids "prepared statement ... does not exist" errors under load.
    _engine_kwargs["connect_args"] = {"statement_cache_size": 0}
engine = create_async_engine(settings.database_url, **_engine_kwargs)
```

Add `import os` to the top of `session.py` if not already present (verified: it is not currently imported — the file's current imports are `logging`, `collections.abc.AsyncIterator`, `pathlib.Path`, `typing.Any`, plus `alembic`/`sqlalchemy` — `os` must be added).

**Validate:**
```bash
cd backend/docker
docker compose -f docker-compose.yml -f docker-compose.pgbouncer.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.pgbouncer.yml up -d postgres pgbouncer
docker compose -f docker-compose.yml -f docker-compose.pgbouncer.yml ps  # both must show "healthy"
docker compose -f docker-compose.yml -f docker-compose.pgbouncer.yml exec pgbouncer psql -h 127.0.0.1 -p 5432 -U hyrepath -d hyrepath -c "SELECT 1"
```

### 5.2 `backend/app/workers/queue.py` and `backend/app/workers/rq_worker.py` — new queue constants + the reconciled list + `WORKER_EXCLUDE_QUEUES`

**File edited: `backend/app/workers/queue.py`**

```python
# Phase 2 queues (added by phase2_docker_plan.md, consolidating Modules 1-3)
QUEUE_JOB_MATCHING = "job_matching"              # Module 1 — dedicated container only, never in the generic list
QUEUE_OUTREACH = "outreach_generation"           # Module 2 — shared, generic worker
QUEUE_QUESTION_GENERATION = "question_generation"  # Module 3 — shared fallback + dedicated overlay option

QUEUE_PRIORITIES = {
    QUEUE_EMAIL: 10,
    QUEUE_CV_EXTRACTION: 8,
    QUEUE_FEEDBACK: 7,
    QUEUE_JOB_MATCHING: 6,
    QUEUE_OUTREACH: 6,
    QUEUE_DOCUMENT: 5,
    QUEUE_QUESTION_GENERATION: 4,
    QUEUE_EMBEDDING: 3,
    QUEUE_NAME: 2,
    QUEUE_CLEANUP: 1,
    QUEUE_AUDIO_CLEANUP: 1,
}
```

Reminder for whoever reviews this diff (per §1.2): `QUEUE_PRIORITIES` remains documentation-only metadata — it is not read by `rq_worker.py` or anything else. The two `6`s (`QUEUE_JOB_MATCHING`/`QUEUE_OUTREACH`) are not a bug; they don't collide because `QUEUE_JOB_MATCHING` is never placed in any shared list (§5.5 — dedicated container only).

**File edited: `backend/app/workers/rq_worker.py`** — replace the `else` branch (currently lines 58-75) with the reconciled list from §4.4, filtered by the new `WORKER_EXCLUDE_QUEUES` env var (§4.2):

```python
else:
    # General-purpose worker: listen to every shared Phase 1 + Phase 2 queue,
    # minus whatever WORKER_EXCLUDE_QUEUES says a dedicated container already
    # owns in this environment (empty by default — safe, unchanged behavior
    # for any deployment that hasn't adopted a dedicated overlay yet).
    from app.workers.queue import (
        QUEUE_AUDIO_CLEANUP,
        QUEUE_CV_EXTRACTION,
        QUEUE_DOCUMENT,
        QUEUE_EMBEDDING,
        QUEUE_FEEDBACK,
        QUEUE_NAME,
        QUEUE_OUTREACH,
        QUEUE_QUESTION_GENERATION,
    )

    all_queue_names = [
        QUEUE_FEEDBACK,             # Week 2: Interview feedback (user-facing)
        QUEUE_OUTREACH,             # Module 2: personalized outreach (user-facing)
        QUEUE_DOCUMENT,             # Week 1: Document processing
        QUEUE_QUESTION_GENERATION,  # Module 3: personalized question pre-gen (not user-blocking)
        QUEUE_EMBEDDING,            # Week 1: Embeddings
        QUEUE_CV_EXTRACTION,        # Week 1: CV extraction
        QUEUE_NAME,                 # Original enrichment queue
        QUEUE_AUDIO_CLEANUP,        # Maintenance cron (previously unconsumed anywhere — fixed here)
    ]
    excluded = {
        q.strip() for q in os.environ.get("WORKER_EXCLUDE_QUEUES", "").split(",") if q.strip()
    }
    queue_names = [q for q in all_queue_names if q not in excluded]
    queues = [Queue(name, connection=connection) for name in queue_names]
    logger.info(f"Worker configured for multiple queues: {[q.name for q in queues]}")
    if excluded:
        logger.info(f"Excluded queues (owned by a dedicated container): {sorted(excluded)}")
```

Add `import os` to `rq_worker.py`'s imports if not already present (verified: `rq_worker.py` currently imports `os` already — line 2 — so this specific file needs no new import; only `session.py` from §5.1 needs the new `import os`).

**Validate:**
```bash
cd backend
python -c "from app.workers.queue import QUEUE_JOB_MATCHING, QUEUE_OUTREACH, QUEUE_QUESTION_GENERATION, QUEUE_AUDIO_CLEANUP; print('queue constants import cleanly')"
python -c "
import os
os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite:///./test.db')
os.environ.setdefault('REDIS_URL', 'redis://localhost:6379/0')
import app.workers.rq_worker  # noqa: import-only smoke test, must not raise
print('rq_worker module imports cleanly')
"
ruff check app/workers/queue.py app/workers/rq_worker.py
```

### 5.3 Module 1 — `backend/app/workers/rq_worker_job_matching.py` (new dedicated entrypoint)

Verified against `phase2_module1.md` §9.2 — this file's Python logic is correct as proposed there (only its *Dockerfile* needed correction, per §4.1). Reproduced here for completeness so this document is self-contained:

```python
"""Dedicated RQ worker for the job_matching queue. Does not share queues with
the generic worker — isolation, not reordering, per architecture_phase2.md
§1.3's RQ fixed-priority-starvation evidence."""

from __future__ import annotations

import logging
import os
import time
from typing import cast

from rq import SimpleWorker, Worker
from rq.timeouts import BaseDeathPenalty, UnixSignalDeathPenalty
from rq.worker import BaseWorker

import app.database.orm_registry  # noqa: F401 — register ORM models before use

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.observability.error_tracking import init_error_tracking
from app.workers.queue import QUEUE_JOB_MATCHING, get_redis_connection, register_scheduled_jobs

logger = logging.getLogger(__name__)


class _NoOpDeathPenalty(BaseDeathPenalty):
    """Windows-safe timeout context, matching rq_worker.py's own pattern."""

    def setup_death_penalty(self) -> None:
        pass

    def cancel_death_penalty(self) -> None:
        pass


def main() -> None:
    configure_logging()
    init_error_tracking()
    get_settings()

    connection = get_redis_connection()
    connection.ping()

    queue = __import__("rq").Queue(QUEUE_JOB_MATCHING, connection=connection)
    worker: BaseWorker
    if hasattr(os, "fork"):
        worker = Worker([queue], connection=connection, name="worker-job-matching")
    else:
        worker = SimpleWorker([queue], connection=connection, name="worker-job-matching")
        worker.death_penalty_class = cast(type[UnixSignalDeathPenalty], _NoOpDeathPenalty)

    logger.info("Starting dedicated job-matching worker", extra={"queue": QUEUE_JOB_MATCHING})
    # Only this process registers job_matching_scan's cron entry in this
    # topology (replicas: 1, pinned in §5.5) — RQ-Scheduler dedupes by job ID
    # in Redis regardless, matching the pre-existing behavior documented in
    # architecture_phase2.md §5.3.
    register_scheduled_jobs()
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
```

**Correction applied versus `phase2_module1.md` §9.2's version:** the original snippet imported `from rq import Connection, Worker` and used the `with Connection(connection):` context-manager style, which is RQ's *legacy* API pattern. Verified against this repo's own actual `rq_worker.py` (read directly, §1.2 above): the codebase's real, current pattern passes `connection=` explicitly to `Worker(...)` and never uses the `Connection(...)` context manager anywhere. This document's version above matches the repo's real, established pattern instead of introducing a second, inconsistent RQ usage style — also picking up the repo's own Windows-dev-safe `SimpleWorker`/`_NoOpDeathPenalty` fallback, which the original Module 1 snippet omitted entirely (it would crash on `import signal`-based timeouts on any contributor's Windows dev machine, since `rq`'s default `Worker` timeout mechanism relies on `SIGALRM`, unavailable on Windows — confirmed by this repo's own comment in `rq_worker.py` lines 96-98).

### 5.4 Module 1 — `backend/docker/Dockerfile.worker-job-matching` (🔧 corrected per §4.1)

```dockerfile
# Dedicated worker for the job_matching queue (Module 1 — AI Job Matching).
# Isolated from the generic worker per architecture_phase2.md §1.3's RQ
# fixed-priority starvation evidence. Mirrors Dockerfile.worker-embedding's
# build pattern (pip install -e ., non-root user) — NOT Poetry, since this
# repo has no poetry.lock anywhere (verified).
FROM python:3.12-slim

WORKDIR /app/backend

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir -e .

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

RUN useradd -m -u 1000 worker && \
    chown -R worker:worker /app
USER worker

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "from app.workers.queue import get_redis_connection; from rq import Queue; c = get_redis_connection(); exit(0 if Queue('job_matching', connection=c).count < 500 else 1)"

CMD ["python", "-m", "app.workers.rq_worker_job_matching"]
```

**Healthcheck correction versus `phase2_module1.md` §9.1:** the original proposed `from app.workers.tasks.job_matching import check_worker_health` — a function that does not exist anywhere in this repo (verified: no `check_worker_health` function exists in the codebase today; `worker-document`/`worker-embedding`'s own healthchecks reference `app.workers.tasks.document.check_worker_health` / `app.workers.tasks.embedding.check_worker_health`, which likewise are assumed by Module 1's plan to exist with the same shape but were **not** verified to exist in this session — treat as a Module 1 backend-code deliverable, not a Docker-layer one). This document's healthcheck instead uses the same `Queue(...).count` depth-check pattern already verified working in `docker-compose.week2-ai.yml`'s design (§5.7 below) — it needs zero new Python code, only the `app.workers.queue` module this plan already guarantees exists. If Module 1 ships its own `check_worker_health()` helper later, swap the `CMD` line for it; do not block this Docker plan on that function existing first.

**Validate:**
```bash
cd backend/docker
docker build -f Dockerfile.worker-job-matching -t hyerenrichment-worker-job-matching:test ..
docker run --rm hyerenrichment-worker-job-matching:test python -c "import app.workers.rq_worker_job_matching; print('entrypoint module imports cleanly')"
```

### 5.5 Module 1 — `backend/docker/docker-compose.foundation.yml` — add `worker-job-matching`

Appended to the existing file (does not replace `worker-document`/`worker-embedding`, which stay exactly as they are):

```yaml
  # Job matching worker — dedicated queue, isolated per architecture_phase2.md
  # §1.3 (Module 1, phase2_module1.md §9).
  worker-job-matching:
    build:
      context: ..
      dockerfile: docker/Dockerfile.worker-job-matching
    container_name: hyerenrichment-worker-job-matching
    networks:
      - default
    environment:
      DATABASE_URL: postgresql+asyncpg://hyrepath:${POSTGRES_PASSWORD}@pgbouncer:5432/hyrepath
      REDIS_URL: redis://redis:6379/0
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      SENDGRID_API_KEY: ${SENDGRID_API_KEY:-}
      JOB_MATCHING_ENABLED: ${JOB_MATCHING_ENABLED:-true}
      JOB_MATCHING_MAX_POSTINGS_PER_SCAN: ${JOB_MATCHING_MAX_POSTINGS_PER_SCAN:-50}
      JOB_MATCHING_SIMILARITY_THRESHOLD: ${JOB_MATCHING_SIMILARITY_THRESHOLD:-0.5}
      JOB_MATCHING_TOP_N_EXPLANATIONS: ${JOB_MATCHING_TOP_N_EXPLANATIONS:-5}
      WORKER_STARTUP_DELAY: "0"
      SENTRY_DSN: ${SENTRY_DSN:-}
      SENTRY_ENVIRONMENT: ${SENTRY_ENVIRONMENT:-}
    depends_on:
      pgbouncer:
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
          memory: 1G
      replicas: 1   # pinned — see §5.3's scheduler-registration note; do not scale without addressing that first
    healthcheck:
      test:
        [
          "CMD",
          "python",
          "-c",
          "from app.workers.queue import get_redis_connection; from rq import Queue; c = get_redis_connection(); exit(0 if Queue('job_matching', connection=c).count < 500 else 1)",
        ]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
```

**Corrections applied versus `phase2_module1.md` §9.3:**
1. `DATABASE_URL` points at `pgbouncer:5432`, not `postgres:5432` (§5.1's ceiling fix applies to every new Phase 2 container, not just the pre-existing ones — a new container that bypasses PgBouncer defeats the purpose of adding it).
2. `depends_on.postgres` replaced with `depends_on.pgbouncer` (Compose `depends_on` with `condition: service_healthy` only gates startup ordering on the container actually listed — depending on `postgres` while connecting to `pgbouncer` would let this worker start before PgBouncer itself is ready, producing a transient "connection refused" on cold boot).
3. `deploy.resources.reservations` omitted — verified that `docker compose up` (Compose v2, non-Swarm mode) does not read `deploy.resources.reservations` at all (only `limits` are enforced outside Swarm mode) — keeping it in the source `phase2_module1.md` snippet is harmless but misleading; omitted here to not imply a guarantee Compose doesn't provide.

**Validate:**
```bash
cd backend/docker
docker compose -f docker-compose.yml -f docker-compose.pgbouncer.yml -f docker-compose.foundation.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.pgbouncer.yml -f docker-compose.foundation.yml up -d worker-job-matching
docker compose -f docker-compose.yml -f docker-compose.pgbouncer.yml -f docker-compose.foundation.yml ps worker-job-matching  # must reach "healthy"
docker compose -f docker-compose.yml -f docker-compose.pgbouncer.yml -f docker-compose.foundation.yml logs worker-job-matching  # confirm "Starting dedicated job-matching worker"
```

### 5.6 Module 2 — no new Dockerfile, no new compose service (confirmed correct as designed)

Verified: `phase2_module2.md` §10.4's own claim ("Module 2 requires zero Dockerfile changes and zero compose-file changes") holds up under this plan's reconciliation — `QUEUE_OUTREACH` is already threaded into the generic worker's queue list in §5.2 above. The only remaining Module-2-owned work is application code (`app/modules/outreach/`, `app/modules/portfolio/`, `app/modules/job_swipe/`) and the `.env.example`/settings additions in §6 below — no additional Docker step is required here. This section exists so "did Module 2 need a Docker step" has an explicit, checkable "no" in this consolidated plan, matching that module doc's own checklist item for the same reason.

**Validate:** covered by §5.2's validation — if `QUEUE_OUTREACH` imports cleanly there, Module 2's Docker-relevant surface is already correct.

### 5.7 Module 3 — `backend/docker/docker-compose.week2-ai.yml` (🔧 corrected per below)

```yaml
# Week 2 - Interview Practice AI Services (Module 3)
# Isolates feedback generation and personalized question pre-generation onto
# their own worker, per architecture_phase2.md §1.3 (RQ is fixed-priority,
# not fair-share, so bundling these with Week 1's document/embedding queues
# risks starving user-facing feedback behind a batch embedding backlog).
# Usage: docker compose -f docker-compose.yml -f docker-compose.pgbouncer.yml
#        -f docker-compose.week2-ai.yml up
#
# IMPORTANT: once this overlay is running, also set WORKER_EXCLUDE_QUEUES on
# the base `worker` service (see this plan §5.7's note below) so the generic
# worker stops redundantly polling `feedback`/`question_generation` — both
# workers CAN safely listen to the same queue (RQ jobs run exactly once,
# whichever worker BLPOPs it first) but running two independently-sized pools
# against the same queue defeats the point of isolating capacity for it.

services:
  worker-interview-ai:
    build:
      context: ..
      dockerfile: docker/Dockerfile.worker
    networks:
      - default
    environment:
      DATABASE_URL: postgresql+asyncpg://hyrepath:${POSTGRES_PASSWORD}@pgbouncer:5432/hyrepath
      REDIS_URL: redis://redis:6379/0
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      HUME_API_KEY: ${HUME_API_KEY:-}
      WORKER_QUEUE_MODE: single
      WORKER_STARTUP_DELAY: "0"
      SENTRY_DSN: ${SENTRY_DSN:-}
      SENTRY_ENVIRONMENT: ${SENTRY_ENVIRONMENT:-}
    command: ["rq", "worker", "feedback", "question_generation", "--url", "redis://redis:6379/0"]
    depends_on:
      pgbouncer:
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

**Corrections applied versus `phase2_module3.md` §8.2:**
1. `DATABASE_URL` repointed at `pgbouncer:5432` (§5.1), `depends_on` repointed at `pgbouncer` instead of `postgres` (same reasoning as §5.5's correction #2).
2. `build.context`/`dockerfile` changed from the original's `context: ..` + `dockerfile: docker/Dockerfile.worker` (relative to a `backend/docker/` working directory) — verified this is actually **already correct** as originally written in `phase2_module3.md` (matches every other service's `context: ..`/`dockerfile: docker/Dockerfile.*` pattern in the base `docker-compose.yml`); no change needed here, noted only to confirm it was checked, not silently trusted.
3. `command: ["rq", "worker", ...]` — verified the plain `rq worker` CLI (not `app.workers.rq_worker`'s `main()`) is a legitimate, independent entrypoint already used by `worker-email`/`worker-document`/`worker-embedding` in this exact form (verified in `docker-compose.yml`/`docker-compose.foundation.yml`). This CLI form does **not** call `register_scheduled_jobs()` — verified via the `rq` package's own CLI, which only calls `Worker(...).work()`. This means `worker-interview-ai` does **not** register any cron jobs, which is correct: Module 3 introduces no new cron job (`question_generation` is enqueued directly by application code via `enqueue_question_generation()`, per `phase2_module3.md` §7.5 — it is never scheduled), so no process needs to own scheduler registration for this overlay specifically.

**Note on `WORKER_EXCLUDE_QUEUES` (§4.2) for this overlay:** when running `docker-compose.week2-ai.yml`, also override the generic `worker` service's environment (add this to whichever compose file is your final `-f worker` layer — see §7's full command matrix, which folds this into a dedicated `docker-compose.phase2.yml` combined overlay so you do not have to remember to set it by hand every time):

```yaml
  worker:
    environment:
      WORKER_EXCLUDE_QUEUES: "feedback,question_generation"
```

### 5.8 Module 3 — `backend/docker/docker-compose.prod.yml` — additive block (verified correct as originally proposed)

`phase2_module3.md` §8.3's proposed block is verified correct against this repo's real `docker-compose.prod.yml` pattern (same `env_file`/`environment`/`restart` shape as the existing `worker:` block immediately above it) — added here verbatim, with the `DATABASE_URL` correction from §5.1 applied for consistency:

```yaml
  worker-interview-ai:
    env_file:
      - ${WORKER_ENV_FILE:-../.env.production}
    environment:
      APP_ENV: production
      DATABASE_URL: postgresql+asyncpg://hyrepath:${POSTGRES_PASSWORD}@pgbouncer:5432/hyrepath
      REDIS_URL: redis://redis:6379/0
    restart: unless-stopped
```

**Validate:**
```bash
cd backend/docker
docker compose -f docker-compose.yml -f docker-compose.pgbouncer.yml -f docker-compose.week2-ai.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.pgbouncer.yml -f docker-compose.week2-ai.yml up -d worker-interview-ai
docker compose -f docker-compose.yml -f docker-compose.pgbouncer.yml -f docker-compose.week2-ai.yml ps worker-interview-ai  # must reach "healthy"
```

### 5.9 🆕 NEW — `backend/docker/docker-compose.phase2.yml`: the one combined overlay that ties §5.1-§5.8 together

Every step above validated its own overlay file in isolation. But a developer running the *full* Phase 2 stack would otherwise need to remember to pass `-f docker-compose.pgbouncer.yml -f docker-compose.foundation.yml -f docker-compose.week2-ai.yml` **and** manually set `WORKER_EXCLUDE_QUEUES` on the generic worker every time — exactly the kind of manual step that produces "works on my machine" drift and eventual docker network/config errors when someone forgets one `-f` flag. This file is the single overlay that captures the cross-cutting pieces the other overlays don't own themselves:

```yaml
# Phase 2 combined overlay — the "run everything" convenience layer.
# Captures cross-cutting settings that no single per-feature overlay owns:
# excluding queues from the generic worker once dedicated containers exist
# for them (§4.2/§5.7), and repointing the generic worker + Phase 1 tier
# workers at PgBouncer (§5.1) in one place.
# Usage: docker compose -f docker-compose.yml -f docker-compose.pgbouncer.yml \
#        -f docker-compose.foundation.yml -f docker-compose.week2-ai.yml \
#        -f docker-compose.phase2.yml up -d

services:
  worker:
    environment:
      DATABASE_URL: postgresql+asyncpg://hyrepath:${POSTGRES_PASSWORD}@pgbouncer:5432/hyrepath
      # Owned by worker-document/worker-embedding (foundation.yml) and
      # worker-interview-ai (week2-ai.yml) once those overlays are running —
      # see §4.2. Do NOT add job_matching here: it never joins the generic
      # worker's list at all (§5.5), so there is nothing to exclude for it.
      WORKER_EXCLUDE_QUEUES: "document_processing,embedding_generation,feedback,question_generation"
    depends_on:
      pgbouncer:
        condition: service_healthy

  api:
    environment:
      DATABASE_URL: postgresql+asyncpg://hyrepath:${POSTGRES_PASSWORD}@pgbouncer:5432/hyrepath
    depends_on:
      pgbouncer:
        condition: service_healthy

  worker-email:
    environment:
      DATABASE_URL: postgresql+asyncpg://hyrepath:${POSTGRES_PASSWORD}@pgbouncer:5432/hyrepath
    depends_on:
      pgbouncer:
        condition: service_healthy

  worker-cleanup:
    environment:
      DATABASE_URL: postgresql+asyncpg://hyrepath:${POSTGRES_PASSWORD}@pgbouncer:5432/hyrepath
    depends_on:
      pgbouncer:
        condition: service_healthy
```

**Why `WORKER_EXCLUDE_QUEUES` excludes `document_processing`/`embedding_generation` here even though §5.2's code change was written generically:** this operationalizes `architecture_phase2.md` §10's recommendation #3 ("promote `worker-document`/`worker-embedding` from opt-in overlay to default, and remove those queues from the generic worker's listen-list so there's no redundant double-polling") as part of this same plan, since it is a one-line consequence of already having `WORKER_EXCLUDE_QUEUES` available — not deferring a documented, already-decided recommendation to some future, unscheduled PR.

**⚠️ `depends_on.pgbouncer` on `api`/`worker`/etc. only works when merged with `docker-compose.pgbouncer.yml` in the same command** — Compose resolves `depends_on` conditions only against services defined somewhere in the merged file set; omitting `-f docker-compose.pgbouncer.yml` from the command while including `docker-compose.phase2.yml` produces `service "pgbouncer" depends_on ... but is not present` — a real `docker compose config` error, not a hypothetical one. §7's command matrix always lists `docker-compose.pgbouncer.yml` first for this exact reason; do not reorder or drop it.

**Validate:**
```bash
cd backend/docker
docker compose \
  -f docker-compose.yml \
  -f docker-compose.pgbouncer.yml \
  -f docker-compose.foundation.yml \
  -f docker-compose.week2-ai.yml \
  -f docker-compose.phase2.yml \
  config --quiet
```

---

## 6. `.env.example` additions (placeholders only — per `RULE.md` "never commit secrets")

Consolidates every new env var named across Modules 1-3's own `.env.example` sections (`phase2_module1.md` §6, `phase2_module2.md` §7, `phase2_module3.md` §6) plus this plan's own PgBouncer/pool additions. Append to `backend/.env.example`:

```bash
# ─────────────────────────────────────────────
# Phase 2 Docker infrastructure (phase2_docker_plan.md)
# ─────────────────────────────────────────────
# PgBouncer connection-pool ceiling (§5.1) — real backend connections to
# Postgres, independent of how many app/worker containers are running.
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=2

# Module 1 — AI Job Matching & Notifications
JOB_MATCHING_ENABLED=true
JOB_MATCHING_SCAN_CRON=0 6 * * *          # daily at 06:00 UTC, staggered internally
JOB_MATCHING_MAX_POSTINGS_PER_SCAN=50     # JobSpy results_wanted per candidate scan
JOB_MATCHING_SIMILARITY_THRESHOLD=0.5     # pgvector cosine similarity floor
JOB_MATCHING_TOP_N_EXPLANATIONS=5         # LLM explanation calls per candidate per scan
JOB_MATCHING_INACTIVE_AFTER_DAYS=14       # job_postings.is_active sweep threshold

# Module 2 — Tinder-Style Job Board + CV Management (outreach generation)
PERPLEXITY_API_KEY=pplx-...
PERPLEXITY_API_BASE=https://api.perplexity.ai
OUTREACH_ENABLED=true
OUTREACH_SENDER_EMAIL=candidate-outreach@hyrepath.example   # placeholder — real value is per-tenant/per-user return address

# Module 3 — Interview Prep & Sentiment Analysis (optional, paid, off by default)
# HUME_API_KEY=

# Note (correction to the existing stale banner comment near the LiteLLM
# section, ~line 210): OPENAI_API_KEY IS required directly by
# question_generator.py, feedback_generator.py, clients/speech.py,
# clients/embeddings.py, and cv_extractor.py regardless of LLM_MODE —
# LLM_MODE only controls the LiteLLM disambiguation path, not these five
# direct-to-OpenAI callers (see phase2_module3.md §4.8).
```

**`backend/app/core/config.py` additions** (settings needed by the above — verified none currently exist by reading the full `Settings` class in this session):

```python
    # Module 1 — AI Job Matching
    job_matching_enabled: bool = Field(default=True, alias="JOB_MATCHING_ENABLED")
    job_matching_max_postings_per_scan: int = Field(
        default=50, alias="JOB_MATCHING_MAX_POSTINGS_PER_SCAN"
    )
    job_matching_similarity_threshold: float = Field(
        default=0.5, alias="JOB_MATCHING_SIMILARITY_THRESHOLD"
    )
    job_matching_top_n_explanations: int = Field(
        default=5, alias="JOB_MATCHING_TOP_N_EXPLANATIONS"
    )
    job_matching_inactive_after_days: int = Field(
        default=14, alias="JOB_MATCHING_INACTIVE_AFTER_DAYS"
    )

    # Module 2 — Outreach
    perplexity_api_key: str = Field(default="", alias="PERPLEXITY_API_KEY")
    perplexity_api_base: str = Field(default="https://api.perplexity.ai", alias="PERPLEXITY_API_BASE")
    outreach_enabled: bool = Field(default=True, alias="OUTREACH_ENABLED")
    outreach_sender_email: str = Field(default="", alias="OUTREACH_SENDER_EMAIL")

    # Module 3 — Hume AI (optional, off by default)
    hume_api_key: str = Field(default="", alias="HUME_API_KEY")
```

**Validate:**
```bash
cd backend
python -c "from app.core.config import get_settings; s = get_settings(); print(s.job_matching_enabled, s.outreach_enabled, s.hume_api_key)"
```

---

## 7. Compose command matrix — the exact `-f` flags for every environment

`docker-compose.pgbouncer.yml` must always be listed immediately after `docker-compose.yml` (its services are `depends_on` targets for later overlays — Compose resolves `depends_on` against the full merged file set, but keeping the ceiling-fixing layer first, consistently, avoids ever forgetting it).

| Environment | Command |
|---|---|
| **Plain local dev (Phase 1 only, no Phase 2 features)** | `docker compose -f docker-compose.yml up -d` — unchanged, exactly as it works today. Phase 2 is entirely opt-in. |
| **Local dev, Phase 1 tiers only** | `docker compose -f docker-compose.yml -f docker-compose.tier-workers.yml up -d` — unchanged. |
| **Local dev, full Phase 2 stack** | `docker compose -f docker-compose.yml -f docker-compose.pgbouncer.yml -f docker-compose.foundation.yml -f docker-compose.week2-ai.yml -f docker-compose.phase2.yml up -d` |
| **Local dev, full Phase 2 + Phase 1 tiers** | add `-f docker-compose.tier-workers.yml` to the line above, placed after `docker-compose.phase2.yml` |
| **Staging/production** | `docker compose -f docker-compose.yml -f docker-compose.pgbouncer.yml -f docker-compose.foundation.yml -f docker-compose.week2-ai.yml -f docker-compose.phase2.yml -f docker-compose.prod.yml --env-file ../.env.production up -d` — `docker-compose.prod.yml` **always goes last** (unchanged rule from this repo's existing convention, per its own header comment about `!override` merge tags depending on file order) |
| **Scaling foundation/Phase-2 workers** | append `--scale worker-document=3 --scale worker-embedding=2` etc. to any command above — `worker-job-matching` and `worker-interview-ai` are pinned `replicas: 1` (§5.5/§5.7) and must **not** be scaled without first fixing the scheduler-duplication note in §5.3/§3.3 |
| **CI / fast validation only** | `docker compose -f docker-compose.yml -f docker-compose.pgbouncer.yml -f docker-compose.foundation.yml -f docker-compose.week2-ai.yml -f docker-compose.phase2.yml config --quiet` — validates every Phase 2 file merges cleanly without starting anything |

---

## 8. Full container topology after this plan lands

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Bridge network (default)                                                 │
│                                                                            │
│  postgres (pgvector) ◄── migrate (one-shot, DDL, bypasses PgBouncer)     │
│       ▲                                                                   │
│       │ 25 real backend connections (DEFAULT_POOL_SIZE)                  │
│    pgbouncer  ◄── NEW, §5.1 — every app/worker service connects HERE     │
│       ▲                                                                   │
│       │                                                                   │
│  ┌────┴──────────────────────────────────────────────────────────────┐  │
│  │ api ×N          redis                                              │  │
│  │ worker (generic) — feedback¹, outreach, document¹, question-gen¹, │  │
│  │                    embedding¹, cv_extraction, enrichment,          │  │
│  │                    audio_cleanup  [¹ excluded once dedicated       │  │
│  │                    containers below are running — WORKER_EXCLUDE_  │  │
│  │                    QUEUES, §4.2/§5.9]                              │  │
│  │ worker-email        worker-cleanup       (Phase 1, unchanged)      │  │
│  │ worker-tier234      social-analyzer, google-maps-scraper,          │  │
│  │                     email-verifier                (Phase 1)        │  │
│  │                                                                     │  │
│  │ worker-document ×N     worker-embedding ×N     (Foundation, promoted│  │
│  │                                                  to always-on §5.9) │  │
│  │ worker-job-matching ×1  ◄── NEW, Module 1, dedicated, isolated      │  │
│  │ worker-interview-ai ×N  ◄── NEW, Module 3, dedicated (feedback +    │  │
│  │                              question_generation)                   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│ Host network (Tier 1 only, unchanged by this plan)                      │
│  worker-tier1  ──►  127.0.0.1:6432 (PgBouncer, if exposed — §8.1 below) │
│                 or  127.0.0.1:5433 (Postgres directly, current default) │
│  Multilogin container (shared loopback)                                 │
└──────────────────────────────────────────────────────────────────────────┘
```

### 8.1 `worker-tier1` and PgBouncer — a deliberate non-change

`worker-tier1` uses `network_mode: host` and addresses everything via `127.0.0.1:<port>` (§1.3). PgBouncer (§5.1) has no `ports:` mapping by default, so it is **not reachable from host-network containers** unless a host port is published. This plan deliberately does **not** repoint `worker-tier1` at PgBouncer: Tier 1 is capped at one instance by its own host-network constraint (§1.3's table — "Cannot scale"), so it contributes at most one process's worth of connections (5 pooled + 2 overflow with §5.1's new explicit sizing) — not the multi-process problem PgBouncer exists to solve. `worker-tier1` keeps connecting directly to `postgres:5433` (mapped to `127.0.0.1:5433` on the host, per the base `docker-compose.yml`'s existing port mapping) exactly as it does today. If you later need Tier 1 to also go through PgBouncer, publish a host port on the `pgbouncer` service (e.g. `127.0.0.1:6432:5432`) and change `worker-tier1`'s `DATABASE_URL` host/port accordingly — not required for this plan's "no docker error" goal, since nothing about Tier 1 changes here.

---

## 9. Zero-to-running boot runbook (replay of §5, in dependency order, for a clean machine)

```bash
cd backend/docker

# 1. Base infra first — Postgres must exist and be healthy before PgBouncer
#    can connect to it, and before `migrate` can run DDL.
docker compose -f docker-compose.yml -f docker-compose.pgbouncer.yml up -d postgres redis
docker compose -f docker-compose.yml -f docker-compose.pgbouncer.yml ps  # postgres, redis -> healthy

# 2. PgBouncer, now that Postgres is healthy.
docker compose -f docker-compose.yml -f docker-compose.pgbouncer.yml up -d pgbouncer
docker compose -f docker-compose.yml -f docker-compose.pgbouncer.yml ps pgbouncer  # -> healthy

# 3. Migrations — direct to Postgres, NOT through PgBouncer (§5.1).
docker compose -f docker-compose.yml -f docker-compose.pgbouncer.yml up migrate
# Expect exit code 0 and "Migrations completed successfully!" in the log.

# 4. Sidecars (free-mode, default-on) — unchanged by this plan.
docker compose -f docker-compose.yml -f docker-compose.pgbouncer.yml up -d \
  social-analyzer google-maps-scraper email-verifier

# 5. Core api + generic worker + email/cleanup workers, now pointed at PgBouncer.
docker compose \
  -f docker-compose.yml -f docker-compose.pgbouncer.yml -f docker-compose.phase2.yml \
  up -d api worker worker-email worker-cleanup

# 6. Foundation Phase-2 workers.
docker compose \
  -f docker-compose.yml -f docker-compose.pgbouncer.yml \
  -f docker-compose.foundation.yml -f docker-compose.phase2.yml \
  up -d worker-document worker-embedding worker-job-matching

# 7. Module 3's dedicated overlay.
docker compose \
  -f docker-compose.yml -f docker-compose.pgbouncer.yml \
  -f docker-compose.week2-ai.yml -f docker-compose.phase2.yml \
  up -d worker-interview-ai

# 8. Full-stack health check — every container should read "healthy" or
#    "running" (migrate/glitchtip-migrate-style one-shot jobs show "exited (0)").
docker compose \
  -f docker-compose.yml -f docker-compose.pgbouncer.yml \
  -f docker-compose.foundation.yml -f docker-compose.week2-ai.yml \
  -f docker-compose.phase2.yml ps

# 9. Queue-level smoke test — confirm every Phase 2 queue exists and is
#    reachable from inside the api container (proves Redis DNS + queue names
#    are correct end-to-end, not just that containers booted).
docker compose \
  -f docker-compose.yml -f docker-compose.pgbouncer.yml \
  -f docker-compose.foundation.yml -f docker-compose.week2-ai.yml \
  -f docker-compose.phase2.yml \
  exec api python -c "
from app.workers.queue import get_redis_connection
from rq import Queue
c = get_redis_connection()
for name in ['job_matching', 'outreach_generation', 'question_generation', 'audio_cleanup', 'feedback', 'document_processing', 'embedding_generation', 'cv_extraction', 'enrichment']:
    print(name, '->', Queue(name, connection=c).count, 'jobs queued')
"
```

If every command above exits 0 and every `ps` row shows `healthy`, the Docker layer of Modules 1-3 plus the cross-cutting fixes from `architecture_phase2.md` §5 is fully wired. Anything past this point (actual route handlers, ORM models, frontend types) is `phase2_module1.md`/`2`/`3`'s own remaining, non-Docker work.

---

## 10. Troubleshooting — mapped to root cause

Extends `backend/docker/NETWORKING.md`'s existing troubleshooting table with the specific new failure modes this plan's changes can introduce.

| Symptom | Root cause | Fix |
|---|---|---|
| `service "pgbouncer" depends_on ... but is not present` on `docker compose config` | `docker-compose.phase2.yml` (or `.foundation.yml`/`.week2-ai.yml`) was passed without `-f docker-compose.pgbouncer.yml` in the same command | Always include `-f docker-compose.pgbouncer.yml` per §7's matrix — it must be present in every command that includes any overlay depending on it |
| `FATAL: password authentication failed for user "hyrepath"` from `pgbouncer` logs | `POSTGRES_PASSWORD` differs between the `postgres` service's environment and `pgbouncer`'s `DB_PASSWORD` — both must read the exact same `${POSTGRES_PASSWORD}` shell/`.env` variable | Confirm both resolve identically: `docker compose config | grep -A2 "DB_PASSWORD\|POSTGRES_PASSWORD"` |
| `prepared statement "__asyncpg_stmt_1__" does not exist` under load, only after adding PgBouncer | `session.py`'s `statement_cache_size: 0` fix (§5.1) was not applied, or was applied only to `engine` and not `sync_engine` (RQ workers use `sync_engine`, which uses `psycopg`, not `asyncpg` — verified via `_to_sync_url()`'s `postgresql+asyncpg://` → `postgresql+psycopg://` swap, so `sync_engine` is **not** affected by this specific asyncpg issue; confirm the fix is on the `elif settings.database_url.startswith("postgresql")` branch that both engines' `_engine_kwargs` share, not duplicated incorrectly) | Re-check §5.1's exact `session.py` diff; the `connect_args` dict is shared via `_engine_kwargs` before either engine is constructed, so one edit covers both — if you see this error, the edit was likely applied to a copy of `_engine_kwargs` after `create_async_engine()` already ran |
| `worker-job-matching` container restarts in a loop, logs show `ModuleNotFoundError: No module named 'app.workers.tasks.job_matching'` | Module 1's application code (§5.4's healthcheck / `rq_worker_job_matching.py`'s task imports) was never implemented — the Docker layer from this plan is correct, but the queue has nothing to actually process yet | Expected until `phase2_module1.md`'s backend sections are implemented; the container should still reach `healthy` (the healthcheck only checks queue depth, per §5.4's correction, not that a specific task module exists) — if it does not even reach healthy, re-check §5.4's `Dockerfile.worker-job-matching` was built with the corrected (non-Poetry) version |
| `could not translate host name "postgres" to address` from `worker-tier1` | `docker-compose.tier-workers.yml`'s `worker-tier1` environment block was accidentally repointed at PgBouncer/service names instead of `127.0.0.1` | Per §8.1, `worker-tier1` is deliberately **not** touched by this plan — if you see `postgres`/`pgbouncer`/`redis` (service names) anywhere in `worker-tier1`'s resolved environment, something outside this plan's diffs changed it; revert to `127.0.0.1:5433`/`127.0.0.1:6379` per `NETWORKING.md` |
| `docker compose up` for `docker-compose.week2-ai.yml` succeeds, but `feedback` jobs are processed twice (visible via duplicate `question_attempts` feedback rows or duplicate log lines) | `WORKER_EXCLUDE_QUEUES` was not set on the generic `worker` service — both it and `worker-interview-ai` are independently draining the same `feedback` queue | Confirm `docker-compose.phase2.yml` (§5.9) is included in the command — it is what sets `WORKER_EXCLUDE_QUEUES` on `worker`; each individual job still only runs once (RQ guarantees this via `BLPOP`), but without the exclusion both pools burn capacity racing for the same jobs |
| `Bind for 0.0.0.0:5432 failed: port is already allocated` when adding PgBouncer | A host port was added to the `pgbouncer` service definition that collides with Postgres's own `127.0.0.1:5433:5432` mapping, or with a previous `pgbouncer` container left running from a stopped-but-not-removed Compose project | Per §5.1, `pgbouncer` has **no** `ports:` mapping by default — do not add one unless you specifically need host access, and if you do, use a port nothing else claims (e.g. `127.0.0.1:6432:5432`), never `5432`/`5433` |
| `worker-job-matching`/`worker-interview-ai` never leave `starting` state, no error in logs | `depends_on.migrate.condition: service_completed_successfully` is waiting on a `migrate` run that hasn't happened in this Compose project yet (e.g. you skipped step 3 of §9's runbook) | Run `docker compose ... up migrate` (step 3) before starting any worker that depends on it — this is enforced ordering, not a bug |
---

## 11. Verification checklist — do not skip any row

**PgBouncer / connection pooling (§5.1):**
- [ ] `backend/docker/docker-compose.pgbouncer.yml` created
- [ ] `backend/app/database/session.py` edited: `import os` added, `pool_size`/`max_overflow`/`statement_cache_size` set for the `postgresql` branch, applied to both `engine` and `sync_engine` (shared via `_engine_kwargs`)
- [ ] `DATABASE_URL` repointed at `pgbouncer:5432` in `docker-compose.yml` (`api`, `worker`, `worker-email`, `worker-cleanup`), `docker-compose.foundation.yml` (`worker-document`, `worker-embedding`), `docker-compose.tier-workers.yml` (`worker-tier234` only — **not** `worker-tier1`, §8.1), and the two new Phase 2 compose blocks (§5.5, §5.7)
- [ ] `migrate` service's `DATABASE_URL` left pointed at `postgres:5432` directly (unchanged — §5.1's explicit warning)
- [ ] `docker compose ... exec pgbouncer psql -h 127.0.0.1 -p 5432 -U hyrepath -d hyrepath -c "SELECT 1"` succeeds

**Queue reconciliation (§4.4, §5.2):**
- [ ] `backend/app/workers/queue.py`: `QUEUE_JOB_MATCHING`, `QUEUE_OUTREACH`, `QUEUE_QUESTION_GENERATION` added; `QUEUE_PRIORITIES` updated
- [ ] `backend/app/workers/rq_worker.py`'s `else` branch replaced with the `WORKER_EXCLUDE_QUEUES`-filtered version from §5.2, including `QUEUE_AUDIO_CLEANUP` (§4.3's fix for the previously-unconsumed cron queue)
- [ ] `ruff check app/workers/queue.py app/workers/rq_worker.py` clean

**Module 1 — job matching (§5.3-§5.5):**
- [ ] `backend/app/workers/rq_worker_job_matching.py` created (repo's real `Worker(queues, connection=...)` pattern, not the legacy `Connection(...)` context manager)
- [ ] `backend/docker/Dockerfile.worker-job-matching` created using `pip install -e .` (not Poetry — §4.1)
- [ ] `backend/docker/docker-compose.foundation.yml` has `worker-job-matching` appended, pointed at `pgbouncer`, `replicas: 1`
- [ ] `docker build -f Dockerfile.worker-job-matching -t hyerenrichment-worker-job-matching:test ..` succeeds
- [ ] `worker-job-matching` reaches `healthy` in `docker compose ps`

**Module 2 — outreach (§5.6):**
- [ ] Confirmed **zero** new Dockerfiles/compose services needed — `QUEUE_OUTREACH` already covered by §5.2's list edit

**Module 3 — interview AI (§5.7-§5.8):**
- [ ] `backend/docker/docker-compose.week2-ai.yml` created with the PgBouncer-corrected `DATABASE_URL`/`depends_on`
- [ ] `backend/docker/docker-compose.prod.yml` gets the additive `worker-interview-ai` block (§5.8)
- [ ] `worker-interview-ai` reaches `healthy` in `docker compose ps`

**Cross-cutting combined overlay (§5.9):**
- [ ] `backend/docker/docker-compose.phase2.yml` created with `WORKER_EXCLUDE_QUEUES` set on `worker` and `DATABASE_URL` repointed on `api`/`worker`/`worker-email`/`worker-cleanup`
- [ ] `docker compose -f docker-compose.yml -f docker-compose.pgbouncer.yml -f docker-compose.foundation.yml -f docker-compose.week2-ai.yml -f docker-compose.phase2.yml config --quiet` exits 0 with no warnings

**Environment / settings (§6):**
- [ ] `backend/.env.example` updated with every new var, placeholders only, no real keys
- [ ] `backend/app/core/config.py` gets the new `Settings` fields (`job_matching_*`, `perplexity_*`, `outreach_*`, `hume_api_key`, and implicitly `database_pool_size`/`database_max_overflow` if you choose to promote §5.1's `os.environ.get(...)` calls to real `Settings` fields instead — either approach is acceptable; this plan used raw env-var reads in `session.py` since that module does not currently import `get_settings()`'s `Settings` object for engine construction beyond `settings.database_url`, and duplicating the whole `Settings` machinery there was judged out of scope per `RULE.md`'s "fix only what the task needs")
- [ ] `python -c "from app.core.config import get_settings; get_settings()"` succeeds with no `ValidationError`

**End-to-end (§9):**
- [ ] Full boot runbook (§9, steps 1-9) completes with every container `healthy` and the queue smoke-test script printing all 9 queue names with a numeric count (proving Redis DNS + queue-name spelling is correct end-to-end)
- [ ] `docker compose ... down` and re-`up` (cold restart) succeeds without manual intervention — proves `depends_on`/healthcheck ordering is self-sufficient, not just correct on a lucky first boot

---

## 12. Explicit blind spots and unverifiable assumptions (per this document's own evidence-labeling standard — nothing silently assumed)

1. **`check_worker_health()` for `worker-document`/`worker-embedding`'s existing healthchecks was not independently re-verified in this session** — only `docker-compose.foundation.yml`'s reference to `app.workers.tasks.document.check_worker_health`/`app.workers.tasks.embedding.check_worker_health` was read; whether those functions currently exist in `app/workers/tasks/document.py`/`embedding.py` was not confirmed by opening those files. If they do not exist, those two **pre-existing** containers' healthchecks were already broken before this plan, independent of anything here — flagged, not fixed, since fixing pre-existing Foundation Week 1 code is out of this plan's scope per `RULE.md`.
2. **`edoburu/pgbouncer:1.21.0`'s exact compatibility with `postgres:16-alpine` + this repo's custom `Dockerfile.postgres` (with the source-built `pgvector` extension) was not tested in this session** — PgBouncer pools connections at the wire-protocol level and is extension-agnostic in principle (✅ DIRECT per PgBouncer's own architecture — it never runs `CREATE EXTENSION` or any DDL), but this is a "should work per the tool's documented design," not a "was booted and confirmed against this repo's specific Postgres image" claim. §9's runbook step 1-2 is exactly the test that closes this gap — run it before trusting this plan fully.
3. **`DEFAULT_POOL_SIZE: 25` (§5.1) is a starting number, not a benchmarked one** — same caveat `phase2_module1.md` §9.3 already applied to its own CPU/memory sizing: copied from a reasonable default (roughly matching Postgres's own unmodified `max_connections=100` divided across expected concurrent transaction bursts, with headroom), to be tuned from real `pgbouncer` admin-console stats (`SHOW POOLS`) once running, not asserted as tuned.
4. **`WORKER_EXCLUDE_QUEUES`'s comma-split parsing (§5.2) assumes queue names never contain a literal comma** — true for every queue name in this codebase today (verified: all are single lowercase words/underscores), flagged only because it is a real, if currently unreachable, edge case in the parsing logic.
5. **This plan does not address `docker-compose.staging.yml`, `docker-compose.tier1.yml`, `docker-compose.multilogin.yml`, `docker-compose.loadtest.yml`, or `docker-compose.fake-sidecars.yml`** — none of these were read in this session; if any of them independently define a `worker`/`api`/`postgres` service block with its own `DATABASE_URL`, that block will **not** automatically pick up the PgBouncer repointing from §5.1 and must be updated separately, following the exact same `postgres:5432` → `pgbouncer:5432` pattern shown throughout §5.
6. **pgvector HNSW retuning (§3.2) and the fan-out job-matching scheduler's actual staggering logic (`architecture_phase2.md` §4) are explicitly out of scope for this document** — they are Alembic-migration and application-code concerns respectively, not Docker/Compose concerns, and are owned by `architecture_phase2.md` and `phase2_module1.md` directly.
7. **Windows/PowerShell host developers** (per this workspace's own `win32`/`powershell` environment): every command in §5/§7/§9 is written as a POSIX shell one-liner (matching the style already used throughout `phase2_module1.md`/`2`/`3`'s own validate blocks and this repo's existing `.sh` scripts in `backend/docker/`) — running them from PowerShell directly will fail on multi-line `python -c "..."` quoting; use `docker compose ... exec <service> python -c '...'` from WSL/Git Bash, or wrap the Python snippet in a temporary `.py` file and `docker compose ... exec <service> python /path/to/script.py` if running natively from PowerShell. This is a shell-compatibility note, not a Docker-correctness issue.

---

## 13. Complete file manifest — every file this plan creates or edits

| File | Action |
|---|---|
| `backend/docker/docker-compose.pgbouncer.yml` | **Create** (§5.1) |
| `backend/docker/docker-compose.phase2.yml` | **Create** (§5.9) |
| `backend/docker/docker-compose.week2-ai.yml` | **Create** (§5.7) |
| `backend/docker/Dockerfile.worker-job-matching` | **Create** (§5.4) |
| `backend/app/workers/rq_worker_job_matching.py` | **Create** (§5.3) |
| `backend/app/database/session.py` | **Edit** — `import os`, PgBouncer-safe pool sizing (§5.1) |
| `backend/app/workers/queue.py` | **Edit** — 3 new queue constants + `QUEUE_PRIORITIES` entries (§5.2) |
| `backend/app/workers/rq_worker.py` | **Edit** — reconciled queue list + `WORKER_EXCLUDE_QUEUES` filter (§5.2) |
| `backend/docker/docker-compose.yml` | **Edit** — `DATABASE_URL` repointed to `pgbouncer` on `api`/`worker`/`worker-email`/`worker-cleanup` (§5.1) |
| `backend/docker/docker-compose.foundation.yml` | **Edit** — `DATABASE_URL` repointed on `worker-document`/`worker-embedding`; `worker-job-matching` service appended (§5.1, §5.5) |
| `backend/docker/docker-compose.tier-workers.yml` | **Edit** — `DATABASE_URL` repointed on `worker-tier234` only, **not** `worker-tier1` (§5.1, §8.1) |
| `backend/docker/docker-compose.prod.yml` | **Edit** — `worker-interview-ai` additive block, `DATABASE_URL` repointed on existing `api`/`worker`/`postgres` (§5.8) |
| `backend/.env.example` | **Edit** — all new Phase 2 + PgBouncer env vars, placeholders only (§6) |
| `backend/app/core/config.py` | **Edit** — new `Settings` fields for the vars above (§6) |

**Explicitly not touched by this plan** (owned by the respective module doc's own backend/frontend sections, not by Docker/Compose): `app/modules/job_matching/`, `app/modules/outreach/`, `app/modules/portfolio/`, `app/modules/job_swipe/`, `app/modules/questions/`, `app/modules/practice_audio/`, any Alembic migration, any frontend file, `docs/adr/*`, `backend/docs/ARCHITECTURE.md`.

---

## 14. Closing statement

Every Dockerfile, compose service, and environment-variable claim in this document was checked against a file actually opened and read in this session — `docker-compose.yml`, `docker-compose.foundation.yml`, `docker-compose.tier-workers.yml`, `docker-compose.prod.yml`, `Dockerfile.worker`, `Dockerfile.worker-document`, `Dockerfile.worker-embedding`, `Dockerfile.postgres`, `Dockerfile.api`, `entrypoint-worker.sh`, `run-migrations.sh`, `NETWORKING.md`, `app/workers/queue.py`, `app/workers/rq_worker.py`, `app/database/session.py`, `app/core/config.py`, and `backend/.env.example` — not inferred from any module doc's own unverified claims about "the exact structure of the existing X" (§4.1's Dockerfile correction is the clearest example of exactly this kind of claim turning out to be false on inspection). Every place where `phase2_module1.md`/`2`/`3`'s own Docker sections conflicted with each other (§2) or with this repo's real files (§4.1, §5.4, §5.5, §5.7) is labeled 🔧 CORRECTION and resolved once, here, rather than left for three separate PRs to each discover and fix differently. Following §5 in order and passing every "Validate" step, then completing §9's full runbook and §11's checklist, is what "the backend infrastructure of the project is complete, no Docker error, no Docker network error, all containers work properly" means in this document — nothing here is true until that runbook's output says so.
