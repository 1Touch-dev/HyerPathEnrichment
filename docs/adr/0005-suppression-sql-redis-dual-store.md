# 0005. SQL durable suppression with Redis cache

- **Status:** Accepted
- **Date:** 2026-07-20

## Context

Opt-out and suppression must survive Redis restarts and remain auditable for compliance. Pipeline checks suppression on every enrichment before calling external providers. We needed a store that is fast at read time but durable for legal retention.

## Decision

We chose **SQL table `suppression_list` as durable record** with **Redis set `suppression:hashes` as fast-path cache** over **Redis-only suppression** because compliance data must not evaporate when Redis is flushed or restarted. Redis-only was rejected — it is not a durable system of record and complicates DSAR/audit workflows.

## Tradeoffs

- Dual-write on suppress: SQL first, then Redis cache update in `compliance/suppression.py`.
- Pipeline checks Redis when available, falls back to SQL on cache miss.
- Extra consistency edge cases if Redis and SQL diverge — mitigated by SQL as source of truth.

## Consequences

- Implementation in `app/compliance/suppression.py`; ORM in `app/compliance/models.py`.
- Identifier hashing via `hash_identifier()` in `compliance/identifiers.py` — never store raw opt-out identifiers in Redis keys logged externally.
- Opt-out service triggers suppress + purge jobs for photos and R2/local assets.
