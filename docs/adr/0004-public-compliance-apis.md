# 0004. Public opt-out and DSAR APIs

- **Status:** Accepted
- **Date:** 2026-07-20

## Context

Data subjects must be able to opt out and exercise DSAR rights without holding an API key. Enrichment endpoints remain customer-authenticated. We needed a split auth model that satisfies compliance accessibility without exposing enrichment to anonymous abuse.

## Decision

We chose **public opt-out and DSAR routes** (IP rate-limited) over **Bearer auth on all compliance endpoints** because subjects cannot be required to obtain customer API tokens to suppress their data. Bearer-only compliance was rejected — it blocks legitimate opt-out flows and conflicts with accessibility expectations documented in `backend/docs/LEGAL.md`. Enrichment routes stay Bearer-protected.

## Tradeoffs

- Compliance endpoints rely on IP rate limits (`MAX_COMPLIANCE_REQUESTS_PER_MINUTE`) instead of token identity.
- Public surface requires careful input validation and audit logging — no PII in logs.
- Product boundaries (what enrichment may do vs what compliance must do) stay in LEGAL.md, not duplicated in ADRs.

## Consequences

- `POST /api/opt-out` and `POST/GET /api/dsar` are public with rate limiting; `/enrich` and `/enrich/sync` require Bearer.
- Suppression runs before any outbound provider call in `Pipeline`.
- See `app/modules/opt_out/` and `app/compliance/` for implementation.
