# 0001. Async job execution via Redis + RQ

- **Status:** Accepted
- **Date:** 2026-07-20

## Context

Enrichment runs can take minutes (browser automation, SMTP verification, sidecar calls). The API must return quickly with a job ID clients can poll. We needed a background execution model that fits a small self-hosted deployment without heavy ops overhead.

## Decision

We chose **Redis + RQ** over **in-process async** and **Celery** because RQ is simple to operate (one Redis, one worker process), matches our sync-worker model (`asyncio.run()` inside jobs), and keeps job state in Postgres while the queue lives in Redis. In-process execution was rejected for `/enrich` because long-running work would block API workers and defeat polling across processes.

## Tradeoffs

- RQ workers are process-based, not native async — we wrap pipeline execution with `asyncio.run()` in worker jobs.
- Redis is a required dependency for async enrichment; local dev without Redis must use `/enrich/sync`.
- Celery would add broker complexity and configuration surface we do not need at current scale.

## Consequences

- `POST /enrich` enqueues via `workers/queue.py`; the worker runs `Pipeline.run()` through `workers/tasks.py`.
- `/enrich/sync` remains inline for quick tests and sync-only clients; sync mode skips Tier 1 browser work (`runner.py` sync_mode).
- Docker Compose runs API + worker + Redis + Postgres so polling works cross-process.
