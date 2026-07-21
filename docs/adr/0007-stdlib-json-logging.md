# 0007. Stdlib JSON logging over structlog

- **Status:** Accepted
- **Date:** 2026-07-21

## Context

API and RQ workers need one logging setup with machine-parseable lines in staging/production and readable output locally, plus optional `request_id` / `job_id` correlation. We already use Sentry's `LoggingIntegration`, so the solution must stay compatible with stdlib `logging` handlers.

## Decision

We chose **stdlib `logging` + a small `JsonFormatter`** over **structlog** (or similar) because correlation and JSON shape are enough for v1, and an extra logging stack would compete with Sentry's handler wiring. Explicit `LOG_FORMAT=json|text` overrides the default (`json` when `APP_ENV` is `staging`/`production`, else `text`).

## Tradeoffs

- No structlog processors/processors pipeline or rich binding ergonomics.
- Operators must rely on contextvars / `extra=` for correlation rather than a fluent bind API.
- Custom formatters are ours to maintain (kept small in `app/core/logging.py`).

## Consequences

- Configure once via `configure_logging()` from API lifespan and the RQ worker entrypoint, **before** `init_error_tracking()`.
- Settings: `LOG_FORMAT`, `LOG_LEVEL`, `LOG_SERVICE` in `core/config.py`.
- Request middleware sets `request_id`; enrichment tasks set `job_id`.
