# Legal and Compliance

Hyrepath Enrichment — compliance reference for operators and developers.

**Version:** 0.4 (August 2026)

---

## Policy summary

- **Public data only** — public profiles, commits, and search results.
- **Customer-supplied identifiers only** — no unsolicited people-finding.
- **Opt-out is permanent** — once registered, the identifier is blocked across all tiers.
- **Data erasure on opt-out** — matching job dossiers (`dossier_payload` + `request_payload`), photo cache, R2/local assets, outreach recipient fields, and sourced-lead PII are purged/scrubbed.
- **LGPD / GDPR / CCPA** — data subject requests supported via opt-out and DSAR endpoints.

---

## Authentication (v1)

Enrichment routes (`/enrich`, `/enrich/sync`, …) require an **authenticated, verified user** (cookie JWT session; ADR 0009). Operator tooling may still use `API_TOKEN` where documented.

- `POST /api/opt-out` and `GET /api/opt-out/check` remain **public** (IP rate-limited) so data subjects can exercise opt-out without an account.
- `POST /api/dsar` and `GET /api/dsar/{id}` require an **authenticated verified user**.

The public frontend form at `/opt-out` proxies requests to the backend.

---

## Identifier normalization

All suppression, purge, and audit hashing uses `app/compliance/identifiers.py`:

| Input | Canonical form |
|-------|----------------|
| Email | `strip().lower()` |
| LinkedIn URL | `linkedin:{slug}` via `extract_linkedin_slug()` |
| Username / company / business / job_search | `strip().lower()` |

LinkedIn URL variants (with/without `www`, trailing slash) hash identically.

**Note:** Opt-out is per submitted identifier. Opting out an email does not block enrichment by username unless that username is also opted out.

---

## What purge deletes

On opt-out or DSAR deletion (`app/compliance/purge.py`):

1. **Jobs** — matching rows get `dossier_payload = {}`, `request_payload = {}`, and `status = purged`
2. **Photo cache** — `photo_cache` SQL rows and Redis `tier1:photo:*` keys
3. **Object storage** — R2 objects (or local `.asset-cache/` files) referenced by `asset_key`
4. **Outreach** — recipient PII on matching messages scrubbed
5. **Sourced leads** — PII scrubbed when the identifier matches

Suppression list entries are **never** deleted.

**Account self-delete** (`DELETE /auth/me` via `account_erase.py`) additionally deletes the user's CV documents/chat sessions and outreach rows, and scrubs sourced leads they acted on. Document blobs in R2/local storage for those documents should be treated as follow-up operator cleanup if not already unlinked by storage keys on the deleted rows.

---

## Audit logging

Events are stored in SQL table `audit_logs` (no raw PII — only `identifier_hash` and job IDs):

- `opt_out`
- `data_purged`
- `dsar_created` / `dsar_completed`
- `enrichment_suppressed`

**Retention:** 5 years by default (`AUDIT_LOG_RETENTION_YEARS=5`).

**Cleanup:** Run periodically via cron:

```bash
cd backend && python scripts/purge_audit_logs.py
```

---

## DSAR (30-day SLA)

| Endpoint | Purpose |
|----------|---------|
| `POST /api/dsar` | Create access or deletion request (authenticated verified user) |
| `GET /api/dsar/{id}` | Poll status and summary |

**v1 behavior:** Requests are processed immediately on create (automated self-hosted stack).

- **Access** — returns a machine-readable summary of enrichment jobs for the authenticated subject (includes enriched dossier fields stored on those jobs).
- **Deletion** — runs suppression + purge, same as opt-out for the subject's identifiers.

Manual review queues and email confirmation before opt-out purge are deferred.

**Escalation:** For requests that cannot be satisfied automatically, contact your Hyrepath operator with the DSAR id from the API response.

---

## Enforcement in code

1. `PipelineOrchestrator._is_suppressed()` runs before any tier dispatch.
2. `POST /enrich` pre-checks suppression and returns `status: suppressed` without enqueueing.
3. `register_opt_out()` writes suppression, audits, and purges stored data.

See `backend/docs/ARCHITECTURE.md` for architecture details.

---

## Product boundaries

1. No face recognition.
2. No bulk scraping.
3. No private data sources.
4. No enrichment without a customer-supplied identifier.

---

## LinkedIn scraping considerations

Tier 1 (LinkedIn profile photo) is the only path that drives a browser against LinkedIn. Operators must treat it as high-risk automation and keep it narrowly scoped.

| Constraint | Rule |
|------------|------|
| **Public photo only** | Enrichment may collect the **public profile photo** only. No private profile fields, connection lists, messaging, or non-public content. |
| **Customer-supplied URL only** | A LinkedIn profile is fetched only when the customer supplies that profile URL (or an identifier that resolves to it). No unsolicited people-finding or URL discovery for LinkedIn. |
| **No bulk scrape** | One enrichment job → at most one profile view for that request. Do not batch-crawl, directory-walk, or harvest profiles outside a single customer-initiated enrich. Matches product boundary #2. |
| **Multilogin / session reuse** | Browser sessions run via Multilogin (stealth profiles). Prefer session reuse (`TIER1_SKIP_LOGIN_IF_SESSION_VALID` and related hardening) to reduce login churn and detection risk. Profiles are pooled and rate-limited; see `docs/TESTING_TIER1.md` and `docs/ARCHITECTURE.md`. |
| **ToS / rate-limit operator risk** | LinkedIn’s Terms of Service and anti-automation controls apply to the **operator** of this self-hosted stack. Account restriction, CAPTCHA, and IP/profile bans are operational risks. Respect configured cooldowns and the production guidance of ~20–25 profile views/day per Multilogin profile. Hyrepath does not indemnify operators for ToS violations. |
| **Gated by `ENABLE_TIER1`** | Tier 1 is **off by default**. Set `ENABLE_TIER1=true` on the **worker** only when Multilogin and bot credentials are configured. The API should keep `ENABLE_TIER1=false`. `/enrich/sync` never runs Tier 1 even when `tier1` is requested. |

**Default posture:** leave Tier 1 disabled unless you accept LinkedIn automation risk and have Multilogin + rate limits operational.

---

## Appendix: Upstream source limits

Single operator reference for **external** rate limits and the Hyrepath env vars that tune them. Ingress limits (this API) are enforced in Redis; upstream limits are enforced in enricher code where hooks exist, or are **operator responsibility** when doc-only.

| Source | Typical cap | Enforced by | Config / env vars | Notes |
|--------|-------------|-------------|-------------------|-------|
| **LinkedIn / Multilogin** (Tier 1) | ~20–25 profile views/day per MLX profile | Code — profile pool + daily counter | `MULTILOGIN_DAILY_VIEW_LIMIT` (default 22), `MULTILOGIN_PROFILE_COOLDOWN_SECONDS`, `MULTILOGIN_RATE_LIMIT_COOLDOWN_SECONDS`, `MULTILOGIN_PROFILE_POOL_SIZE`, `MULTILOGIN_PROFILE_ID`, `MULTILOGIN_FOLDER_ID`, `MULTILOGIN_EMAIL`, `MULTILOGIN_PASSWORD`, `MULTILOGIN_WORKSPACE_ID`, `MULTILOGIN_LAUNCHER_URL`, `MULTILOGIN_SELENIUM_HOST`, `ENABLE_TIER1` | One customer-initiated enrich → at most one profile view. See [LinkedIn scraping considerations](#linkedin-scraping-considerations) and `docs/TESTING_TIER1.md`. |
| **GitHub / gitrecon** (Tier 3) | GitHub 403/429 on abuse or quota | Code — Redis throttle + cooldown after rate-limit stderr | `GITRECON_SCRIPT`, `GITRECON_MAX_PER_MINUTE`, `GITRECON_RATE_LIMIT_BACKOFF_SECONDS`, `GITRECON_COOLDOWN_SECONDS`, `GITHUB_TOKEN` | Soft-fails to empty fragment on limit; prefer authenticated token. |
| **SMTP / Reacher** (Tier 3, `EMAIL_VERIFY_LEVEL=smtp`) | ~10 verifications/min per Reacher instance | Code — inter-check delay in runner | `EMAIL_VERIFY_SMTP_DELAY_SECONDS` (default 6 ≈ 10/min), `EMAIL_VERIFY_LEVEL`, `EMAIL_VERIFY_MAX_PER_JOB`, `REACHER_URL`, `REACHER_FROM_EMAIL` | Requires clean IP and port 25; basic mode uses AfterShip sidecar instead. |
| **Hyrepath API ingress** | 10 sync / 30 async / 20 compliance req/min | Code — Redis fixed-window per route | `MAX_SYNC_REQUESTS_PER_MINUTE`, `MAX_ASYNC_REQUESTS_PER_MINUTE`, `MAX_COMPLIANCE_REQUESTS_PER_MINUTE` | Scoped per API token (enrich) or client IP (opt-out/DSAR). Returns `429` over limit; fails open if Redis unavailable. |
| **GitHub REST API** (general) | 5,000 req/hour authenticated | **Doc-only — operator** | `GITHUB_TOKEN` (recommended) | Applies to gitrecon, theHarvester, and any direct GitHub API use. Unauthenticated limit is much lower. Monitor usage outside Hyrepath throttles. |

**Where to read more:** architecture and Redis counter wiring — `backend/docs/ARCHITECTURE.md` (production rate limits). Tier-specific runbooks — `docs/TESTING_TIER1.md`, `backend/docs/TESTING_TIER234.md`.
