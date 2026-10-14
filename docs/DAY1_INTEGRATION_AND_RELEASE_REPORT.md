# Day-1 Integration and Release Report

**Document date:** 2026-10-13
**Audience:** operators, engineers, and future agents
**Host:** single-host EC2 Day-1 preview (`HyerPathEnrichment`)
**Authoritative live release at write time:** `e7cff415b40d4e3ab3bca3dc4ad9c7872fc5b47c`

This report summarizes work completed on **2026-10-12** and **2026-10-13**: domain and DNS cutover, Caddy TLS routing, Perplexity Agent API integration, Stripe test/sandbox billing, and GitHub Actions continuous deployment. It is grounded in repository commits, host state (`.deploy/`, Caddy, compose), and session memory—not aspirational roadmap items.

---

## 1. Executive summary

| Area | Outcome |
|------|---------|
| Domain / DNS / TLS | Public brands on `hyerpath.com` (+ `www`, `app`, `osint`, `desk`) terminate TLS at host Caddy and serve the Next.js frontend |
| Perplexity | Worker-side company research via Agent API `POST /v1/responses` (`preset=fast`); soft-fail preserves outreach/resume jobs |
| Stripe | Test/sandbox billing live on Day-1: checkout sessions, signed webhooks over HTTPS, subscription entitlement updates |
| GitHub CI/CD | Push to `main` → CI → GHCR SHA images → SSH `cd-on-host.sh` → health gate → `.deploy/current_sha` |
| Overall verdict | **READY — TEST/INTERNAL PRODUCTION** (not live customer billing; Stripe still uses test credentials) |

---

## 2. Timeline of work

### 2026-10-12 (yesterday)

- Recorded and pushed the **live EC2 single-host CD path** (`6fff09a` / related Day-1 deploy work from PR `#288` / `e6a4ebc`).
- Day-1 leftovers tracked conceptually: **domain, DNS, GitHub CI/CD, Perplexity, Stripe**, plus pilot/Multilogin notes.
- EC2 host and Elastic IP treated as already in place for preview.
- Phase 2 product surface rechecked against `backend/app` and `frontend` (implementation status vs gaps such as SMS digest stub).

### 2026-10-13 (today)

1. **Verification campaign** for Stripe, Perplexity, Caddy, and Day-1 CD against real host paths.
2. **CD reliability fixes** after `HEALTH_FAIL` / missing `current_sha` on `b3005ef`.
3. **Domain-aware env + Caddy Stripe webhook routing** applied on the host.
4. **Production CD** of reliability release (`b1fba71`), then hygiene release (`e7cff41`).
5. **Phase 6 authenticated billing smoke** on `https://app.hyerpath.com`.

---

## 3. Domain, DNS, and TLS (Caddy)

### What exists

- **No Caddyfile in git.** TLS and routing live on the host: `/etc/caddy/Caddyfile` (systemd `caddy.service`).
- Public sites reverse-proxy to the pm2 Next.js app on `127.0.0.1:3000`:
  - `hyerpath.com`, `www.hyerpath.com`
  - `app.hyerpath.com` (canonical product origin)
  - `osint.hyerpath.com`
  - `desk.hyerpath.com`
- HTTP → HTTPS redirect is active (observed `308` to HTTPS).
- Day-1 API remains on host port **`API_HOST_PORT=8002`** (compose preview map). Docs historically mentioned `:8000`; that is the in-container / future prod-overlay port, not this host’s public Day-1 map.

### Stripe webhook path (applied 2026-10-13)

Next.js has no `/api/billing/webhooks/stripe` route. Without a dedicated Caddy handle, public POSTs returned **404**. The host Caddyfile was updated so **only** that path reaches FastAPI:

```text
handle /api/billing/webhooks/stripe*  →  127.0.0.1:8002
handle (everything else)             →  127.0.0.1:3000
```

Applied on `hyerpath.com` / `www` and `app.hyerpath.com`. Other frontend routes unchanged. Backup retained under `/etc/caddy/Caddyfile.bak.*`.

**Verification:**

| Probe | Result |
|-------|--------|
| `GET https://app.hyerpath.com/` (and apex / www / osint / desk) | 200 |
| Unsigned `POST …/api/billing/webhooks/stripe` (public) | **400** Invalid signature (not 404) |
| Loopback `POST http://127.0.0.1:8002/api/billing/webhooks/stripe` | 400 |
| Signed test webhook over public HTTPS | 200 `processed` / replay `already_processed` |

### Cookie / CORS alignment with domains

Host `backend/.env.production` (backed up before edit) was aligned to public brands:

| Variable | Value (Day-1) |
|----------|----------------|
| `FRONTEND_URL` | `https://app.hyerpath.com` |
| `CORS_ALLOWED_ORIGINS` | `app`, apex, `www`, `osint`, `desk` HTTPS origins |
| `COOKIE_DOMAIN` | **empty** (host-only cookies on `app.hyerpath.com`) |
| `COOKIE_SECURE` | `true` |

**Decision:** keep host-only cookies. Do **not** set `COOKIE_DOMAIN=.hyerpath.com` unless `osint` / `desk` are proven to need shared browser auth cookies.

Compose now passes `FRONTEND_URL` / `CORS_ALLOWED_ORIGINS` / `COOKIE_DOMAIN` into the **api** service (api has no full `env_file`; without passthrough it defaulted to localhost).

---

## 4. Perplexity integration

### Code

- Sole client: `backend/app/clients/perplexity.py`
- Uses **Agent API** `POST {PERPLEXITY_API_BASE}/v1/responses` with `preset=fast` (not legacy Sonar `/chat/completions`)
- Callers:
  - `workers/tasks/outreach.py` (`generate_outreach_draft_job`)
  - `workers/tasks/resume_tailoring.py` (`tailor_resume_job`)
- Queue: `outreach_generation`
- Soft-fail: missing key / HTTP / parse errors → `source=none`; jobs continue with `research_degraded`

### Injection

- Workers load secrets via `env_file` (`docker-compose.tier-workers.yml` → `WORKER_ENV_FILE` / `.env.production`)
- API container does **not** need Perplexity (enqueue only)
- Host cleanup: removed duplicate empty `PERPLEXITY_API_KEY=` line (kept the non-empty `pplx-` key). Note: `07-env-report.sh` may still mark `pplx-*` as PLACEHOLDER (heuristic false positive)

### Live verification

- Inside `docker-worker-1`: `get_company_context("OpenAI", "Software Engineer")` → `source=perplexity` with non-empty summary
- Unit coverage: outreach / resume worker tests assert Agent API payload and degraded flags

---

## 5. Stripe sandbox / test billing

### What was integrated

| Piece | Location / behavior |
|-------|---------------------|
| Feature flag | `ENABLE_BILLING=true` |
| Client mode | `STRIPE_MODE=live` means **real Stripe SDK** (not mock). Test money still uses **test keys** (`rk_test` / `cs_test_`) |
| Live client | `integrations/stripe/client.py` |
| Mock client | `integrations/stripe/mock_client.py` (rejected in staging/production-like `APP_ENV`) |
| Auth API | `/api/billing/checkout-session`, `/portal-session`, `/subscription` |
| Webhooks | `POST /api/billing/webhooks/stripe` (raw body + `Stripe-Signature`) |
| Handled events | `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted` |
| Idempotency | `stripe_webhook_events` ledger → `already_processed` on replay |
| Paywall | Job matching / swipe / documents / worker tasks blur free tier when billing on |
| Frontend | BFF under `frontend/app/api/billing/*`; Settings `SubscriptionCard` |

### Host configuration (no secrets printed)

- Restricted test secret key class: `rk_test`
- Webhook secret class: `whsec_`
- Premium price id present (`price_…`)
- Checkout create verified → `https://checkout.stripe.com/…/cs_test_…`

### Authenticated smoke (Phase 6)

Against `https://app.hyerpath.com` with dedicated smoke users:

1. Login → host-only `Secure` / `HttpOnly` cookies
2. Settings + `GET /api/billing/subscription`
3. `POST /api/billing/checkout-session` → Stripe test Checkout URL
4. Entitlement path: test subscription + signed `checkout.session.completed` → `effectiveTier=premium`
5. Re-login still premium
6. Cancel/abandon path leaves user free (`incomplete` pre-pay row is expected when checkout creates a Stripe customer)

**Limitation:** headless Playwright could not complete Stripe-hosted Checkout card UI in this environment; entitlement was proven via test-mode Subscription API + public signed webhook. A manual browser Upgrade → `4242` remains optional polish.

**Not live billing:** rotating to `sk_live` / live webhook secret / live price IDs is a **separate go-live switch**.

---

## 6. GitHub CI/CD (Day-1 continuous deployment)

### Pipeline

```text
push main
  → CI (audit, pre-commit, lint-test, frontend-contract, e2e, docker-smoke)
  → Deploy workflow_run (success + push to main only)
  → build five GHCR images tagged :<git-sha>
  → SSH → cd-on-host.sh
  → pull images, ensure DBs, Day-1 compose up, frontend redeploy
  → 99-health.sh
  → verify running API image tag == SHA
  → record .deploy/current_sha (only on full success)
```

### Reliability work (2026-10-13)

Prior failure on `b3005ef`: `RESULT=HEALTH_FAIL`, no `current_sha`.

| Failure | Root cause | Fix |
|---------|------------|-----|
| Frontend probe | pm2 restart returned before `:3000` accepted | `wait_for_http` in `08-redeploy-frontend.sh` / `99-health.sh` |
| `database "langfuse" already exists` | `docker exec -i` + non-idempotent `CREATE` under SSH stdin | `ensure_postgres_database` (no `-i`, race-safe) |
| Concurrent / order risk | No lock; early `previous_sha` copy | `acquire_cd_lock`, `record_cd_success`, image-tag gate |
| Ollama on Day-1 | Profile pulled Ollama | Removed from Day-1 profiles/services (`b3005ef`) |
| Actions warning | Unsupported `script_stop` on ssh-action | Removed (`e7cff41`) |

Host self-check: `bash backend/scripts/deploy/test-cd-reliability.sh` (42 PASS).
Billing smoke helper: `bash backend/scripts/deploy/phase6-billing-smoke.sh`.

### Important Day-1 semantics

- **`APP_ENV`:** file may say `production`, but Day-1 compose applies `docker-compose.staging.yml` **last** → processes run as **`APP_ENV=staging`**. Intentional. Do not “fix” without an ADR. Go-live uses `docker-compose.prod.yml`.
- **CI ≠ Day-1:** CI docker-smoke uses free stack on port 8000; Day-1 uses overlays, profiles, and host port 8002.
- **Never forge** `.deploy/current_sha` after a failed health gate.

### Release SHAs (this window)

| SHA | Role |
|-----|------|
| `465e0cd` / `c35e6a6` | Perplexity Agent API + CI unblock |
| `6fff09a` / `e6a4ebc` | Day-1 EC2 CD path |
| `b3005ef` | Stop starting Ollama on Day-1 CD |
| `f04982b` → merge `b1fba71` | CD reliability + FRONTEND_URL passthrough (PR `#292`) |
| `7dea541` → merge `e7cff41` | script_stop removal, APP_ENV docs, Phase 6 smoke script (PR `#293`) |

At document write: **live** = `e7cff41` (api/worker images pinned; `99-health` green).

---

## 7. Architecture sketch (as verified)

```text
Browser (https://*.hyerpath.com)
  └─ Caddy :443
       ├─ /api/billing/webhooks/stripe* → API :8002 (FastAPI)
       └─ all other paths              → Next :3000 (pm2)
            └─ BFF /api/billing/*      → API :8002

API (compose Day-1)
  └─ ENABLE_BILLING + STRIPE_* via staging/foundation environment:

Worker (env_file .env.production)
  └─ outreach_generation → PerplexityClient → OpenAI draft/tailor

GitHub Actions
  └─ CI → GHCR :<sha> → SSH cd-on-host.sh → .deploy/current_sha
```

---

## 8. Explicit non-goals / remaining work

| Item | Notes |
|------|-------|
| Live Stripe money | Separate go-live: live keys, live webhook secret, live prices, controlled live charge |
| Cross-subdomain cookies | Keep `COOKIE_DOMAIN` empty unless product requires shared auth |
| Multilogin / Tier-1 Linux MLX | Not part of Day-1 CD service list |
| `docker-compose.prod.yml` in CD | Do not enable until go-live (binds API `127.0.0.1:8000`, breaks `:8002` preview) |
| Manual Checkout UI pay | Optional human Upgrade → `4242` in a real browser |

---

## 9. Operator quick checks

```bash
# Live identity
cat .deploy/current_sha
docker inspect docker-api-1 --format '{{.Config.Image}}'

# Health
bash backend/scripts/deploy/99-health.sh

# Public surfaces
curl -sS -o /dev/null -w '%{http_code}\n' https://app.hyerpath.com/
curl -sS -o /dev/null -w '%{http_code}\n' -X POST \
  https://app.hyerpath.com/api/billing/webhooks/stripe   # expect 400

# CD reliability self-test
bash backend/scripts/deploy/test-cd-reliability.sh

# Authenticated billing smoke (host)
PHASE6_SKIP_PLAYWRIGHT=1 bash backend/scripts/deploy/phase6-billing-smoke.sh
```

---

## 10. Verdict

```text
Domain / DNS / Caddy:     PASS (webhook path included)
Perplexity (worker live): PASS
Stripe test/sandbox:      PASS (rk_test / cs_test)
GitHub CI → Day-1 CD:     PASS (current_sha advances on success only)

READY — TEST/INTERNAL PRODUCTION
```

Promote to **READY — LIVE BILLING** only after the separate live-credential go-live checklist above.
