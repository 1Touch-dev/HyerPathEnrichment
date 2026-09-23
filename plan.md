# EC2 Live Preview Deployment Plan

**Status:** Plan only — do **not** implement scripts or run deploys from this document until explicitly asked.
**Host model:** This EC2 is edit + deploy + git source of truth. Fix here → redeploy here → push `main` from here.
**Branch:** `main` only (no feature branches for this loop).
**Date captured:** 2026-09-23 (updated same day: soft-env + full env inventory)

---

## 1. Locked decisions

| Item | Decision |
|------|----------|
| Machine | This EC2 (live testing / preview environment) |
| Git flow | Work on `main` → deploy on EC2 → verify → `git push origin main` |
| Images | Build on this EC2 with `docker compose … --build` (do not rely on GitHub Actions CD for this loop) |
| Env file | `backend/.env.staging` (mode `600`) — **every key from the master inventory present** |
| Git / GitHub | **Never** commit or push `.env`, `.env.local`, `.env.production`, `.env.staging`, or any non-template `.env*` — host-only secrets |
| Missing / expired keys | **Still deploy.** Report them. Fill later. Do not block the stack for optional/paid/deferred secrets |
| Day-1 Multilogin | **Off** — no `multilogin`, no `worker-tier1` |
| Day-1 scope | Entire frontend + backend + DB + all Docker profiles/services except Multilogin |
| God test user | Seeded in app Postgres with `is_superuser=True` |
| Schema changes | Alembic `upgrade head` only; never `alembic downgrade` in preview |
| Volume wipe | Never raw `docker compose down -v`; only via guarded nuclear script |

---

## 2. Soft-env policy (deploy even when keys are missing)

### Rule

1. **Ship the full stack Day-1** with all containers (except Multilogin / `worker-tier1`).
2. **`.env.staging` must list every variable** in §12 (master inventory). Empty string or a clear placeholder is allowed for non-boot keys.
3. **Boot-blocking keys only** stop bring-up (see §12.A). Everything else is reported as `NEED_LATER` / `PLACEHOLDER` / `EXPIRED` / `EMPTY` and you add values over time via `02-redeploy-env.sh`.
4. **Feature flags stay off** when a feature would fail-fast without secrets (e.g. leave `ENABLE_TIER1=false`, `ENABLE_BILLING=false` until Stripe/Multilogin keys exist). Containers for that feature still run when they are independent (LiteLLM, Langfuse, etc.).
5. After every full-up / env change, run **`07-env-report.sh`**. It prints which keys are OK, missing, placeholder, or flagged expired — so you know exactly what to add later.

### Status codes for `07-env-report.sh` (to implement later)

| Code | Meaning |
|------|---------|
| `OK` | Set, non-empty, not a known placeholder |
| `EMPTY` | Key present, value blank — feature degraded or off |
| `PLACEHOLDER` | Value matches `REPLACE_*`, `change-me`, `your-*`, `pplx-...`, example CDN, etc. |
| `EXPIRED` | Operator-marked or optional live probe failed (API key / token rejected) — still deploy |
| `NEED_LATER` | Required for a feature you want next, currently EMPTY/PLACEHOLDER |
| `DEFERRED` | Intentionally unused while Multilogin / billing / etc. is off |

Operator marks expired keys in a sidecar file (not secrets): `backend/.env.staging.status` lines like `OPENAI_API_KEY=EXPIRED` or `GITHUB_TOKEN=NEED_LATER`. Report merges file status + value heuristics.

### Boot vs later

| Class | Behavior on Day-1 |
|-------|-------------------|
| **Boot-required (§12.A)** | Must be real before `01-full-up.sh` succeeds (staging refuses insecure defaults) |
| **Have-defaults / self-host** | Set to compose service URLs / safe defaults; stack runs |
| **Optional / paid / deferred (§12.C–E)** | May be empty or placeholder; report lists them; add later |

Sources of truth for the inventory: `backend/app/core/config.py` (Settings aliases), `backend/.env.example`, `backend/.env.staging.example`, `backend/docker/docker-compose*.yml`, `frontend/.env.example`. Staging template alone is incomplete — Day-1 file is the **union of all keys**.

---

## 3. Host prep (once)

1. Keep a single OS user; delete the unused user.
2. Install Docker Engine + Compose plugin; add deploy user to `docker` group.
3. Clone/work in this repo on `main` (path example: `/opt/hyrepath/HyerPathEnrichment` or `/home/<user>/HyerPathEnrichment`).
4. Build `backend/.env.staging` from the **full key list in §12** (start from `backend/.env.example` + staging overlay values). Mode `600`.
5. Fill §12.A boot-required keys for real. Leave optional keys empty or `REPLACE_*`; run `07-env-report.sh` and keep the report.
6. Day-1 flags:
   - `APP_ENV=staging`
   - `COOKIE_SECURE=true`
   - `ENABLE_TIER1=false`
   - `ENABLE_LINUX_MLX=false`
   - `ENABLE_BILLING=false` until Stripe keys are real
   - `LLM_MODE=stub` until vendor keys work (containers for litellm/ollama still up)
   - `PROXY_MODE=none` until Scrapoxy credentials work (scrapoxy container still up)
   - `EMAIL_ENABLED=false` / `EMAIL_TEST_MODE=true` until SendGrid works
7. Install Node for frontend (`npm ci`, `npm run build`, `npm run start`).
8. Point reverse proxy (Caddy/nginx) at UI `:3000` and API `127.0.0.1:8000`.
9. Create deploy scripts under `backend/scripts/deploy/` (listed below — **not implemented by this plan**).
10. Schedule daily DB backup cron for `10-backup-db.sh`.

---

## 4. Day-1 compose topology

### Compose files to load

```text
-f docker-compose.yml
-f docker-compose.staging.yml
-f docker-compose.foundation.yml
-f docker-compose.week2-ai.yml
-f docker-compose.tier-workers.yml   # for worker-tier234 only
```

### Compose files / services to exclude

```text
-f docker-compose.multilogin.yml   # do not load
-f docker-compose.tier1.yml        # do not load
services: multilogin, worker-tier1 # do not start
```

### Profiles (all on for Day-1)

```text
--profile paid
--profile llm
--profile observability
--profile ollama
--profile scrapoxy
```

### Day-1 containers

**Core:** `migrate`, `api`, `postgres`, `redis`

**Enrichment:** `worker`, `worker-email`, `worker-cleanup`, `worker-tier234`, `social-analyzer`, `google-maps-scraper`, `email-verifier`

**Foundation / AI:** `worker-document`, `worker-embedding`, `worker-job-matching`, `worker-interview-ai`

**Paid / LLM / proxy:** `reacher`, `litellm`, `scrapoxy`, `ollama`

**Observability:** `langfuse`, `changedetection`, `glitchtip-migrate`, `glitchtip-web`, `glitchtip-worker`

**Off until Multilogin day:** `multilogin`, `worker-tier1`

### Frontend (same EC2, not Docker)

```bash
cd frontend
# BACKEND_API_URL + BACKEND_API_TOKEN (= API_TOKEN)
npm ci && npm run build && npm run start -- -p 3000
```

### One-time observability DBs

Create Postgres DBs `langfuse` and `glitchtip` (separate from `hyrepath`).

### Day-1 bring-up command (reference for `01-full-up.sh`)

```bash
cd backend/docker

docker compose \
  -f docker-compose.yml \
  -f docker-compose.staging.yml \
  -f docker-compose.foundation.yml \
  -f docker-compose.week2-ai.yml \
  -f docker-compose.tier-workers.yml \
  --env-file ../.env.staging \
  --profile paid \
  --profile llm \
  --profile observability \
  --profile ollama \
  --profile scrapoxy \
  up -d --build \
  migrate api redis postgres \
  worker worker-email worker-cleanup worker-tier234 \
  social-analyzer google-maps-scraper email-verifier \
  worker-document worker-embedding worker-job-matching worker-interview-ai \
  reacher litellm scrapoxy ollama \
  langfuse changedetection \
  glitchtip-migrate glitchtip-web glitchtip-worker
```

Order: fill boot env → `07-env-report.sh` → `01-full-up.sh` → seed god user → frontend → `99-health.sh`.

---

## 5. God test user

| Field | Value |
|-------|--------|
| Email | `god@hyrepath.local` |
| Password | `HyrepathGodTest123!` |
| Flags | `is_verified=True`, `is_active=True`, `is_superuser=True` |

`is_superuser` bypasses all RBAC. Seed via `06-seed-god-user.sh` (do not use `create_test_user.py` under `APP_ENV=staging` — it refuses).

Langfuse / GlitchTip: register the **same** email/password manually (separate auth systems).

---

## 6. Bug-fix loop

```text
1. Edit on main (code / env / compose)
2. Run matching redeploy script
3. If env changed: 07-env-report.sh
4. 99-health.sh — must pass
5. git add -A && git commit && git push origin main
```

| Change type | Script |
|-------------|--------|
| `.env.staging` only | `02-redeploy-env.sh` then `07-env-report.sh` |
| App / sidecar code | `03-redeploy-code.sh <services…>` |
| Compose / Docker config | `04-redeploy-compose.sh` |
| Enable Multilogin later | `05-deploy-multilogin.sh` |

**Code → container:** API → `api`; enrichers/workers → `worker` (+ email / job-matching / cleanup / document / embedding / interview as needed); sidecars → that sidecar; migration → `migrate` then recreate `api`.

---

## 7. Script inventory (to implement later — not in this commit)

All under `backend/scripts/deploy/`.

| Script | Purpose |
|--------|---------|
| `01-full-up.sh` | Full Day-1 stack (no Multilogin); call `07-env-report.sh` first (warn-only for non-boot) |
| `02-redeploy-env.sh` | Force-recreate containers that read env |
| `03-redeploy-code.sh` | Rebuild named services |
| `04-redeploy-compose.sh` | Re-apply full Day-1 compose |
| `05-deploy-multilogin.sh` | Multilogin + `worker-tier1` later |
| `06-seed-god-user.sh` | Idempotent god user |
| `07-env-report.sh` | Audit **all** keys: OK / EMPTY / PLACEHOLDER / EXPIRED / NEED_LATER / DEFERRED |
| `10-backup-db.sh` | Postgres backup wrapper |
| `11-stack-down.sh` | `down` without `-v` |
| `12-restore-db.sh` | Restore dump + forward migrate |
| `13-nuclear-reset.sh` | Guarded `down -v` |
| `99-health.sh` | `/health` + `/ready` |

### Hard ops rules

```text
NEVER: docker compose down -v          → 13-nuclear-reset.sh
NEVER: alembic downgrade               → 12-restore-db.sh
ALWAYS: backup before nuclear          → 10-backup-db.sh
ALWAYS: report env after env edits     → 07-env-report.sh
SAFE STOP: 11-stack-down.sh
```

### Data preserve matrix

| Action | Data |
|--------|------|
| `alembic upgrade head` | Preserved |
| Rebuild app containers | Preserved |
| `docker compose down` (no `-v`) | Preserved |
| `docker compose down -v` | Destroyed |
| Alembic downgrade | Forbidden |

---

## 8. Multilogin (later)

1. Real Multilogin / LinkedIn / R2 / AWS build keys.
2. `ENABLE_TIER1=true`, `ENABLE_LINUX_MLX=true`.
3. `/etc/hyrepath/worker.env` (mode `600`).
4. `05-deploy-multilogin.sh` → health → push `main`.

---

## 9. Feature test order

1. `/health` + `/ready`
2. God-user login
3. Admin / staff
4. Enrichment Tiers 2–4 / sidecars
5. Documents / embeddings / job matching / interview AI (needs `OPENAI_API_KEY` when testing those paths)
6. LiteLLM / Ollama when keys exist
7. Observability UIs
8. Compliance paths
9. Multilogin last

---

## 10. Day-1 execution checklist

```text
[ ] Single OS user + Docker ready
[ ] backend/.env.staging contains EVERY key from §12
[ ] §12.A boot-required keys are real (not placeholders)
[ ] 07-env-report.sh run; save/print NEED_LATER + EXPIRED list
[ ] Scripts under backend/scripts/deploy/ (future task)
[ ] 01-full-up.sh
[ ] Create langfuse + glitchtip databases
[ ] 06-seed-god-user.sh
[ ] Register same email/password in Langfuse + GlitchTip
[ ] Frontend .env.local + build + start on :3000
[ ] Reverse proxy wired
[ ] 99-health.sh
[ ] Cron for 10-backup-db.sh
[ ] Smoke features that do not need missing keys
[ ] git push origin main after deployed fixes
```

---

## 11. Out of scope for this plan document

- Implementing any of the scripts above
- Running the Day-1 bring-up
- Enabling Multilogin
- Changing GitHub Actions `deploy.yml`
- Creating ADRs

---

## 12. Master environment inventory

**Every key below must appear in `backend/.env.staging` on Day-1.** Values for non-boot keys may be empty or placeholder. `07-env-report.sh` classifies them.

Compose-only / host-only keys (not always in Settings) are included so nothing is forgotten.

### 12.A Boot-required (staging must start)

Fail-fast from `validate_production_security_settings` / `validate_env.sh` / outreach when enabled:

| Key | Notes |
|-----|--------|
| `APP_ENV` | `staging` |
| `API_TOKEN` | Non-default, prefer ≥32 chars |
| `SECRET_KEY` | `openssl rand -hex 32`, ≥32 chars, not `change-me*` |
| `COOKIE_SECURE` | `true` |
| `CHANGEDETECTION_API_KEY` | Required when staging (signals webhook fail-closed) |
| `POSTGRES_USER` | e.g. `hyrepath` |
| `POSTGRES_PASSWORD` | Strong, not `change-me` / `password` |
| `POSTGRES_DB` | e.g. `hyrepath` |
| `DATABASE_URL` | `postgresql+asyncpg://…@postgres:5432/…` |
| `REDIS_URL` | `redis://redis:6379/0` |
| `WORKER_QUEUE_MODE` | `per_tier` for this topology |
| `OUTREACH_PHYSICAL_ADDRESS` | Required while `OUTREACH_ENABLED=true`; or set `OUTREACH_ENABLED=false` |

### 12.B Core app + URLs (set on Day-1; safe defaults OK)

| Key | Day-1 default / note |
|-----|----------------------|
| `APP_NAME` | `Hyrepath Enrichment Backend` |
| `API_HOST_PORT` | `8000` |
| `METRICS_TOKEN` | empty → falls back to `API_TOKEN` |
| `REDIS_HOST_PORT` | `6379` |
| `FRONTEND_URL` | preview UI origin |
| `CORS_ALLOWED_ORIGINS` | empty → uses `FRONTEND_URL` |
| `ENABLE_BRAND_CORS_ORIGINS` | `false` |
| `COOKIE_DOMAIN` | empty or preview domain |
| `JWT_ALGORITHM` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` |
| `SOCIAL_ANALYZER_URL` | `http://social-analyzer:9005` |
| `GMAPS_SCRAPER_URL` | `http://google-maps-scraper:8080` |
| `EMAIL_VERIFIER_URL` | `http://email-verifier:8080` |
| `REACHER_URL` | `http://reacher:8080` (paid profile up) |
| `REACHER_FROM_EMAIL` | EMPTY / NEED_LATER until SMTP verify |
| `LOG_FORMAT` | empty = auto json on staging |
| `LOG_LEVEL` | `INFO` |
| `LOG_SERVICE` | `hyrepath-enrichment` |

### 12.C Mode switches + flags

| Key | Day-1 |
|-----|--------|
| `PROXY_MODE` | `none` until Scrapoxy creds work |
| `BROWSER_MODE` | ignore for Day-1 (Tier 1 off); later `multilogin` |
| `LLM_MODE` | `stub` until keys work; flip to `litellm` / `ollama` later |
| `EMAIL_VERIFY_LEVEL` | `basic` |
| `ENABLE_TIER1` | `false` |
| `ENABLE_LINUX_MLX` | `false` |
| `OUTREACH_ENABLED` | `true` only if physical address set; else `false` |
| `ENABLE_BILLING` | `false` |
| `ENABLE_EMBEDDINGS` | `true` (needs OpenAI when actually embedding) |
| `ENABLE_DEMAND_INTELLIGENCE` | `true` |
| `ENABLE_COMPANY_TIER_IN_OUTREACH_DRAFTING` | `false` |
| `ENABLE_DEMAND_INTELLIGENCE_IN_OUTREACH` | `false` |
| `ENABLE_DEMAND_INTELLIGENCE_IN_RESUME_TAILORING` | `false` |
| `ENABLE_ERROR_TRACKING_PROBE` | `false` |
| `ENABLE_BUDGET_ALERTS` | `true` |
| `JOB_MATCHING_ENABLED` | `true` |
| `NOTIFY_SMS_ENABLED` | `false` |
| `EMAIL_ENABLED` | `false` until SendGrid |
| `EMAIL_TEST_MODE` | `true` |

### 12.D Optional / paid / vendor keys (EMPTY or PLACEHOLDER OK on Day-1 → report NEED_LATER)

| Key | Feature blocked until set |
|-----|---------------------------|
| `OPENAI_API_KEY` | CV extract, embeddings, Whisper, interview AI, job explanations |
| `GEMINI_API_KEY` | LiteLLM Gemini routes (compose → litellm) |
| `LITELLM_API_BASE` | e.g. `http://litellm:4000` when `LLM_MODE=litellm` |
| `LITELLM_API_KEY` | optional proxy auth |
| `LITELLM_MASTER_KEY` | litellm proxy; leave unset if unused |
| `LITELLM_MODEL` | e.g. `gpt-4o-mini` |
| `LITELLM_FALLBACKS` | e.g. `gemini/gemini-2.5-flash` |
| `OLLAMA_BASE_URL` | e.g. `http://ollama:11434` when using ollama |
| `OLLAMA_MODEL` | e.g. `llama3.1` |
| `GITHUB_TOKEN` | gitrecon rate limits |
| `GITRECON_SCRIPT` | path to gitrecon |
| `JSEARCH_API_KEY` | paid job source |
| `PERPLEXITY_API_KEY` | outreach research |
| `PERPLEXITY_API_BASE` | `https://api.perplexity.ai` |
| `HUME_API_KEY` | voice tone signals |
| `SENDGRID_API_KEY` | real email |
| `SENDGRID_FROM_EMAIL` | |
| `SENDGRID_FROM_NAME` | |
| `SENDGRID_REPLY_TO` | |
| `GOOGLE_OAUTH_CLIENT_ID` | Google login |
| `GOOGLE_OAUTH_CLIENT_SECRET` | |
| `GOOGLE_OAUTH_REDIRECT_URL` | |
| `SCRAPOXY_URL` | when `PROXY_MODE=scrapoxy` |
| `SCRAPOXY_USERNAME` | |
| `SCRAPOXY_PASSWORD` | |
| `SCRAPOXY_BACKEND_JWT_SECRET` | staging scrapoxy compose |
| `SCRAPOXY_FRONTEND_JWT_SECRET` | staging scrapoxy compose |
| `R2_ACCOUNT_ID` | Tier 1 / prod asset upload |
| `R2_ACCESS_KEY_ID` | |
| `R2_SECRET_ACCESS_KEY` | |
| `R2_BUCKET` | set name even if keys later |
| `R2_PUBLIC_BASE_URL` | CDN URL |
| `STRIPE_MODE` | `live` (mock forbidden on staging) |
| `STRIPE_API_BASE` | |
| `STRIPE_SECRET_KEY` | when `ENABLE_BILLING=true` |
| `STRIPE_WEBHOOK_SECRET` | |
| `STRIPE_PRICE_ID_PREMIUM` | |
| `VAPID_PUBLIC_KEY` | web push |
| `VAPID_PRIVATE_KEY` | |
| `VAPID_SUBJECT` | |
| `LANGFUSE_HOST` | e.g. `http://langfuse:3000` |
| `LANGFUSE_PUBLIC_KEY` | after Langfuse project create |
| `LANGFUSE_SECRET_KEY` | |
| `LANGFUSE_DATABASE_URL` | compose default to langfuse DB |
| `CHANGEDETECTION_URL` | `http://changedetection:5000` |
| `CHANGEDETECTION_PUBLIC_URL` | |
| `CHANGEDETECTION_SIGNAL_URL` | |
| `NOTIFY_WEBHOOK_URL` | outbound signals |
| `SENTRY_DSN` | GlitchTip/Sentry DSN after bootstrap |
| `SENTRY_ENVIRONMENT` | `staging` |
| `SENTRY_RELEASE` | |
| `SENTRY_TRACES_SAMPLE_RATE` | `0` |
| `SENTRY_SEND_DEFAULT_PII` | `false` |
| `GLITCHTIP_HOST_PORT` | `8001` |
| `GLITCHTIP_PUBLIC_URL` | |
| `GLITCHTIP_SECRET_KEY` | set a real secret |
| `GLITCHTIP_DATABASE_URL` | compose default |
| `PROMETHEUS_QUERY_URL` | optional admin health |
| `AWS_ACCESS_KEY_ID` | Multilogin image build only — DEFERRED Day-1 |
| `AWS_SECRET_ACCESS_KEY` | DEFERRED |
| `AWS_SESSION_TOKEN` | optional |
| `AWS_DEFAULT_REGION` | `us-east-1` |

### 12.E Multilogin / Tier 1 (DEFERRED Day-1 — keys still listed in file)

Prefer `/etc/hyrepath/worker.env` at Multilogin day; still list in staging inventory for the report:

| Key |
|-----|
| `MULTILOGIN_API_URL` |
| `MULTILOGIN_LAUNCHER_URL` |
| `MULTILOGIN_EMAIL` |
| `MULTILOGIN_PASSWORD` |
| `MULTILOGIN_FOLDER_ID` |
| `MULTILOGIN_WORKSPACE_ID` |
| `MULTILOGIN_PROFILE_ID` |
| `MULTILOGIN_PROFILE_POOL_SIZE` |
| `MULTILOGIN_DAILY_VIEW_LIMIT` |
| `MULTILOGIN_PROFILE_COOLDOWN_SECONDS` |
| `MULTILOGIN_RATE_LIMIT_COOLDOWN_SECONDS` |
| `MULTILOGIN_SELENIUM_HOST` |
| `MULTILOGIN_CDP_URL` |
| `MULTILOGIN_HOST_IP` |
| `LINKEDIN_BOT_EMAIL` |
| `LINKEDIN_BOT_PASSWORD` |
| `TIER1_BROWSER_TIMEOUT_SECONDS` |
| `TIER1_MAX_CONCURRENT_BROWSERS` |
| `TIER1_SKIP_LOGIN_IF_SESSION_VALID` |
| `TIER1_PLACEHOLDER_DENYLIST` |
| `WORKER_ENV_FILE` |
| `API_ENV_FILE` |

### 12.F Rate limits, TTLs, tunables (defaults OK)

| Key |
|-----|
| `LINKEDIN_PHOTO_TTL_SECONDS` |
| `USERNAME_LOOKUP_TTL_SECONDS` |
| `BUSINESS_LOOKUP_TTL_SECONDS` |
| `JOB_LOOKUP_TTL_SECONDS` |
| `MAX_SYNC_REQUESTS_PER_MINUTE` |
| `MAX_ASYNC_REQUESTS_PER_MINUTE` |
| `MAX_COMPLIANCE_REQUESTS_PER_MINUTE` |
| `MAX_AUTH_REQUESTS_PER_MINUTE` |
| `MAX_AUTH_REFRESH_REQUESTS_PER_MINUTE` |
| `MAX_DOCUMENTS_UPLOAD_REQUESTS_PER_MINUTE` |
| `MAX_SIGNALS_WEBHOOK_REQUESTS_PER_MINUTE` |
| `MAX_JOB_MATCHING_SCAN_REQUESTS_PER_MINUTE` |
| `MAX_ADMIN_IMPERSONATION_START_REQUESTS_PER_MINUTE` |
| `MAX_ADMIN_MFA_VERIFY_REQUESTS_PER_MINUTE` |
| `MAX_ADMIN_REVIEW_QUEUE_DECIDE_REQUESTS_PER_MINUTE` |
| `MAX_ADMIN_MODERATION_REQUESTS_PER_MINUTE` |
| `MAX_QUESTIONS_REQUESTS_PER_MINUTE` |
| `MAX_PRACTICE_AUDIO_UPLOAD_REQUESTS_PER_MINUTE` |
| `MAX_JD_PRACTICE_REQUESTS_PER_MINUTE` |
| `MAX_APPLICATION_TRACKER_STATUS_UPDATE_REQUESTS_PER_MINUTE` |
| `MAX_INTERVIEW_SCHEDULING_REQUESTS_PER_MINUTE` |
| `MAX_MANUAL_JOB_ENTRY_CREATE_REQUESTS_PER_MINUTE` |
| `MAX_OUTREACH_SEND_REQUESTS_PER_MINUTE` |
| `MAX_JOB_MATCHING_APPLY_REQUESTS_PER_MINUTE` |
| `AUDIT_LOG_RETENTION_YEARS` |
| `DAILY_COST_THRESHOLD_USD` |
| `MONTHLY_COST_THRESHOLD_USD` |
| `ENRICHER_MAX_RETRIES` |
| `ENRICHER_RETRY_BACKOFF` |
| `MAX_PARALLEL_TIERS` |
| `TIER1_MAX_CONCURRENT` |
| `TIER2_MAX_CONCURRENT` |
| `TIER3_MAX_CONCURRENT` |
| `TIER4_MAX_CONCURRENT` |
| `WORKER_TARGET_QUEUE` |
| `WORKER_STARTUP_DELAY` |
| `RQ_JOB_TIMEOUT_SECONDS` |
| `SHERLOCK_TIMEOUT_SECONDS` |
| `MAIGRET_TIMEOUT_SECONDS` |
| `GITRECON_MAX_PER_MINUTE` |
| `GITRECON_RATE_LIMIT_BACKOFF_SECONDS` |
| `GITRECON_COOLDOWN_SECONDS` |
| `THEHARVESTER_TIMEOUT_SECONDS` |
| `CROSSLINKED_TIMEOUT_SECONDS` |
| `CROSSLINKED_SEARCH_ENGINES` |
| `EMAIL_SLEUTH_BIN` |
| `EMAIL_VERIFY_MAX_PER_JOB` |
| `EMAIL_VERIFY_SMTP_DELAY_SECONDS` |
| `JOBSPY_RESULTS_PER_BOARD` |
| `JOB_SOURCE_PROVIDER` |
| `JSEARCH_API_HOST` |
| `JSEARCH_NUM_PAGES` |
| `JSEARCH_TIMEOUT_SECONDS` |
| `GMAPS_JOB_TIMEOUT_SECONDS` |
| `GMAPS_JOB_POLL_SECONDS` |
| `DISAMBIGUATION_THRESHOLD` |
| `JOB_MATCHING_SCAN_CRON` |
| `JOB_MATCHING_MAX_POSTINGS_PER_SCAN` |
| `JOB_MATCHING_SIMILARITY_THRESHOLD` |
| `JOB_MATCHING_TOP_N_EXPLANATIONS` |
| `JOB_MATCHING_INACTIVE_AFTER_DAYS` |
| `JOB_MATCHING_EXPLANATION_MAX_RETRIES` |
| `JOB_MATCHING_MIN_RESULTS` |
| `ADMIN_AUDIT_LOG_RETENTION_DAYS` |
| `ADMIN_AGGREGATE_CACHE_TTL_SECONDS` |
| `ADMIN_DEFAULT_PAGE_SIZE` |
| `ADMIN_MAX_PAGE_SIZE` |
| `ADMIN_MFA_ISSUER_NAME` |
| `ADMIN_IMPERSONATION_MAX_DURATION_MINUTES` |
| `PORTFOLIO_PUBLIC_BASE_URL` |
| `APP_PUBLIC_BASE_URL` |
| `APPLY_REDIRECT_BASE_URL` |
| `CV_CHAT_MAX_TURNS` |
| `CV_FEEDBACK_MODEL` |
| `EMBEDDING_CHUNK_SIZE` |
| `EMBEDDING_CHUNK_OVERLAP` |
| `HUME_PROSODY_TIMEOUT_SECONDS` |
| `QUESTION_GENERATION_DAILY_LIMIT_PER_USER` |
| `JD_QUESTION_GENERATION_DAILY_LIMIT_PER_USER` |
| `PRACTICE_AUDIO_MAX_UPLOAD_MB` |
| `INTERVIEW_REMINDER_HOURS_BEFORE` |
| `INTERVIEW_ICS_ORGANIZER_EMAIL` |
| `OUTREACH_LINKEDIN_INMAIL_BODY_MAX_CHARS` |
| `OUTREACH_LINKEDIN_INMAIL_SUBJECT_MAX_CHARS` |
| `OUTREACH_LINKEDIN_CONNECTION_NOTE_MAX_CHARS` |

### 12.G Frontend (`frontend/.env.local`)

| Key | Notes |
|-----|--------|
| `BACKEND_API_URL` | API origin on this EC2 |
| `BACKEND_API_TOKEN` | Same as `API_TOKEN` |
| `BACKEND_FETCH_TIMEOUT_MS` | optional |
| `FRONTEND_USE_MOCKS` | `false` for live |
| `NEXT_PUBLIC_VAPID_PUBLIC_KEY` | match backend VAPID when push enabled |
| `PORTFOLIO_SUBDOMAINS_ENABLED` | `false` until DNS |
| `PORTFOLIO_SUBDOMAIN_ROOT` | |

### 12.H Adding a key later

```text
1. Edit backend/.env.staging (or frontend/.env.local)
2. Clear EXPIRED/NEED_LATER in .env.staging.status if used
3. 02-redeploy-env.sh <affected services>   # or rebuild frontend
4. 07-env-report.sh   # confirm OK
5. 99-health.sh
6. git commit + push main (**never** stage env secret files — only code/docs/scripts)
```

### Never push these to git / GitHub

| File | Why |
|------|-----|
| `.env` | Real secrets |
| `.env.local` | Frontend secrets |
| `.env.production` | Production secrets |
| `.env.staging` | Preview secrets on this EC2 |
| Any other non-template `.env*` | Same |

**Allowed in git:** `.env.example`, `.env.staging.example`, `.env.production.example`, `.env.production.template`, etc.

Enforced by `.gitignore` + pre-commit hook `scripts/hooks/block_env_files.py`. Real secrets stay on the host only.

---

## 13. Related existing repo docs

- `docs/deployment.md` — staging/prod compose, secrets, CD
- `docs/OPS.md` — rollback, forward-only migrations
- `backend/scripts/validate_env.sh` — strict validator (boot keys); `07-env-report.sh` is the soft full-inventory reporter
- `backend/scripts/backup_postgres.sh` / `restore_postgres.sh`
- `backend/app/core/config.py` — Settings aliases (authoritative for app keys)
- `backend/.env.example` — richest template
- ADR 0008 — Tier 1 Linux Multilogin

---

## Implementation note

When implementing later:

1. Add `backend/scripts/deploy/*.sh` only (plus optional pointer in `docs/deployment.md`).
2. `07-env-report.sh` must print **all** §12 keys with status — never silent skip.
3. `01-full-up.sh` hard-fails only on §12.A; soft-warns the rest.
4. Operators pick `02` / `03` / `04` / `05` explicitly — no auto-guess deploy.
