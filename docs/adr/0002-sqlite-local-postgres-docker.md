# 0002. SQLite for local dev, Postgres for Docker/prod

- **Status:** Accepted
- **Date:** 2026-07-20

## Context

Contributors need zero-infra local development, while Docker and production need durable multi-process storage with JSON document columns and Alembic migrations. We had to pick a default database strategy that does not force Postgres on every laptop.

## Decision

We chose **SQLite for local dev** (`sqlite+aiosqlite:///./hyrepath.db`) **plus Postgres for Docker/prod** (`postgresql+asyncpg://...@postgres:5432/hyrepath`) over **Postgres everywhere** because SQLite removes the Postgres install requirement for quick iteration, while Compose and production share one Postgres instance so API and worker see the same job rows. Postgres-everywhere was rejected for local DX — it adds setup friction with no benefit for single-process dev.

## Tradeoffs

- Schema must work on both engines; JSON columns use JSONB on Postgres and compatible types on SQLite.
- Operators must not assume Postgres semantics when running bare `uvicorn` locally.
- Alembic migrations are the single schema path (`init_db` → upgrade head).

## Consequences

- Default in `.env.example` is SQLite; `backend/docker/docker-compose.yml` wires Postgres for API + worker.
- Job polling across processes requires Postgres (or another shared DB) — not SQLite with separate API/worker processes.
- See `backend/app/database/session.py` and `backend/alembic/` for session and migration ownership.
