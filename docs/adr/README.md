# Architecture Decision Records (ADRs)

Short notes that capture why we chose one approach over another — so onboarding and future-you do not re-litigate settled debates.

**Format:** Each ADR answers *"We chose X over Y because … Tradeoffs: … Date: …"*

## Status legend

| Status | Meaning |
|--------|---------|
| Proposed | Under discussion; not yet binding |
| Accepted | Current decision; follow unless superseded |
| Superseded by NNNN | Replaced by a newer ADR |

## When to add an ADR

- Picking or reversing storage, queue, auth, or layer-ownership patterns
- Choosing between two viable architectures with real tradeoffs
- Anything you expect someone to ask *"why not the other way?"* about in six months

Copy [`template.md`](template.md), assign the next number, open a PR, and link from [`backend/docs/ARCHITECTURE.md`](../../backend/docs/ARCHITECTURE.md) if implementation status changes.

## Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [0001](0001-async-redis-rq.md) | Async job execution via Redis + RQ | Accepted | 2026-07-20 |
| [0002](0002-sqlite-local-postgres-docker.md) | SQLite for local dev, Postgres for Docker/prod | Accepted | 2026-07-20 |
| [0003](0003-pipeline-enricher-model.md) | Pipeline + registry enricher execution model | Accepted | 2026-07-20 |
| [0004](0004-public-compliance-apis.md) | Public opt-out and DSAR APIs | Accepted | 2026-07-20 |
| [0005](0005-suppression-sql-redis-dual-store.md) | SQL durable suppression with Redis cache | Accepted | 2026-07-20 |
| [0006](0006-llm-heuristic-default.md) | Heuristic LLM stub default with opt-in LiteLLM | Accepted | 2026-07-20 |
