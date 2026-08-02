# 0004. Public opt-out and DSAR APIs

- **Status:** Superseded by ADR 0009
- **Date:** 2026-07-20
- **Superseded:** 2026-07-31

## Context

Data subjects must be able to opt out and exercise DSAR rights without holding an API key. Enrichment endpoints remain customer-authenticated. We needed a split auth model that satisfies compliance accessibility without exposing enrichment to anonymous abuse.

## Decision

~~We chose **public opt-out and DSAR routes** (IP rate-limited) over **Bearer auth on all compliance endpoints** because subjects cannot be required to obtain customer API tokens to suppress their data. Bearer-only compliance was rejected — it blocks legitimate opt-out flows and conflicts with accessibility expectations documented in `backend/docs/LEGAL.md`. Enrichment routes stay Bearer-protected.~~

**SUPERSEDED:** With the implementation of user authentication (ADR 0009), DSAR endpoints now require authenticated and verified users. Only opt-out remains public. See ADR 0009 for current authentication requirements.

## Current Status (as of ADR 0009)

- **Opt-out**: Remains PUBLIC (IP rate-limited only)
- **DSAR**: Requires authenticated and verified user
- **Enrichment**: Requires authenticated and verified user

Rationale: DSAR requests contain sensitive personal data and should be tied to authenticated user accounts for access control and audit trail.

## Tradeoffs

- Compliance endpoints rely on IP rate limits (`MAX_COMPLIANCE_REQUESTS_PER_MINUTE`) instead of token identity.
- Public surface requires careful input validation and audit logging — no PII in logs.
- Product boundaries (what enrichment may do vs what compliance must do) stay in LEGAL.md, not duplicated in ADRs.

## Consequences

- ~~`POST /api/opt-out` and `POST/GET /api/dsar` are public with rate limiting; `/enrich` and `/enrich/sync` require Bearer.~~
- `POST /api/opt-out` is public with rate limiting; `POST/GET /api/dsar` require authenticated verified user; `/enrich` and `/enrich/sync` require authenticated verified user.
- Suppression runs before any outbound provider call in `Pipeline`.
- See `app/modules/opt_out/` and `app/compliance/` for implementation.
