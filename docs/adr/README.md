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

**Do not skip this.** Architectural PRs without an ADR (or a link to an existing one) are incomplete.

Add or update an ADR when you:

- Introduce or reverse **storage**, **queue**, **auth**, or **layer-ownership** patterns
- Choose between two viable architectures with real tradeoffs
- Expect someone to ask *"why not the other way?"* in six months

**How:**

1. Copy [`template.md`](template.md), assign the next number, fill Decision (X over Y) + Tradeoffs
2. Index the file in this README
3. Open a PR and check the ADR box in [`.github/pull_request_template.md`](../../.github/pull_request_template.md) — link the ADR (or mark N/A only when the change is not architectural)
4. Link from [`backend/docs/ARCHITECTURE.md`](../../backend/docs/ARCHITECTURE.md) if implementation status changes

**Verify:** `python backend/scripts/verify_adrs.py` (structure, Accepted set, cross-links, PR template present).

## Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [0001](0001-async-redis-rq.md) | Async job execution via Redis + RQ | Accepted | 2026-07-20 |
| [0002](0002-sqlite-local-postgres-docker.md) | SQLite for local dev, Postgres for Docker/prod | Accepted | 2026-07-20 |
| [0003](0003-pipeline-enricher-model.md) | Pipeline + registry enricher execution model | Accepted | 2026-07-20 |
| [0004](0004-public-compliance-apis.md) | Public opt-out and DSAR APIs | Accepted | 2026-07-20 |
| [0005](0005-suppression-sql-redis-dual-store.md) | SQL durable suppression with Redis cache | Accepted | 2026-07-20 |
| [0006](0006-llm-heuristic-default.md) | Heuristic LLM stub default with opt-in LiteLLM | Accepted | 2026-07-20 |
| [0007](0007-stdlib-json-logging.md) | Stdlib JSON logging over structlog | Accepted | 2026-07-21 |
