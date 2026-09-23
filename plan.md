# EC2 Live Preview Deployment Plan

**Status:** Plan only — do **not** implement scripts or run deploys from this document until explicitly asked.
**Host model:** This EC2 is edit + deploy + git source of truth. Fix here → redeploy here → push `main` from here.
**Branch:** `main` only (no feature branches for this loop).
**Date captured:** 2026-09-23

---

## 1. Locked decisions

| Item | Decision |
|------|----------|
| Machine | This EC2 (live testing / preview environment) |
| Git flow | Work on `main` → deploy on EC2 → verify → `git push origin main` |
| Images | Build on this EC2 with `docker compose … --build` (do not rely on GitHub Actions CD for this loop) |
| Env file | `backend/.env.staging` (mode `600`) |
| Day-1 Multilogin | **Off** — no `multilogin`, no `worker-tier1` |
| Day-1 scope | Entire frontend + backend + DB + all Docker profiles/services except Multilogin |
| God test user | Seeded in app Postgres with `is_superuser=True` |
| Schema changes | Alembic `upgrade head` only; never `alembic downgrade` in preview |
| Volume wipe | Never raw `docker compose down -v`; only via guarded nuclear script |

---

## 2. Host prep (once)

1. Keep a single OS user; delete the unused user.
2. Install Docker Engine + Compose plugin; add deploy user to `docker` group.
3. Clone/work in this repo on `main` (path example: `/opt/hyrepath/HyerPathEnrichment` or `/home/<user>/HyerPathEnrichment`).
4. Copy `backend/.env.staging.example` → `backend/.env.staging`; fill real secrets.
5. Day-1 env flags:
   - `APP_ENV=staging`
   - `ENABLE_TIER1=false`
   - `ENABLE_LINUX_MLX=false`
   - LLM / proxy modes aligned with running profiles (e.g. LiteLLM + Scrapoxy when those containers are up)
6. Install Node for frontend (`npm ci`, `npm run build`, `npm run start`).
7. Point reverse proxy (Caddy/nginx) at:
   - UI → host `:3000`
   - API → `127.0.0.1:8000`
8. Create deploy scripts under `backend/scripts/deploy/` (listed below — **not implemented by this plan**).
9. Schedule daily DB backup cron for `10-backup-db.sh`.

---

## 3. Day-1 compose topology

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

**Core**

| Service | Role |
|---------|------|
| `migrate` | Alembic upgrade (once per up) |
| `api` | FastAPI |
| `postgres` | App + observability DBs |
| `redis` | Queue / cache |

**Enrichment**

| Service | Role |
|---------|------|
| `worker` | Main RQ worker |
| `worker-email` | Email queue |
| `worker-cleanup` | Maintenance |
| `worker-tier234` | Tier 2–4 pool |
| `social-analyzer` | Sidecar |
| `google-maps-scraper` | Sidecar |
| `email-verifier` | Sidecar |

**Foundation / AI**

| Service | Role |
|---------|------|
| `worker-document` | Documents |
| `worker-embedding` | Embeddings |
| `worker-job-matching` | Job matching |
| `worker-interview-ai` | Feedback / questions |

**Paid / LLM / proxy**

| Service | Profile |
|---------|---------|
| `reacher` | `paid` |
| `litellm` | `llm` / `paid` |
| `scrapoxy` | `paid` / `scrapoxy` |
| `ollama` | `ollama` |

**Observability**

| Service | Profile |
|---------|---------|
| `langfuse` | `observability` |
| `changedetection` | `observability` |
| `glitchtip-migrate` | `observability` |
| `glitchtip-web` | `observability` |
| `glitchtip-worker` | `observability` |

**Off until Multilogin day**

| Service | Reason |
|---------|--------|
| `multilogin` | Deferred |
| `worker-tier1` | Requires Multilogin host network |

### Frontend (same EC2, not Docker)

This repo has no frontend container. Day-1:

```bash
cd frontend
# BACKEND_API_URL + BACKEND_API_TOKEN (= API_TOKEN)
npm ci && npm run build && npm run start -- -p 3000
```

### One-time observability DBs

Create separate Postgres databases for Langfuse and GlitchTip (do not share the `hyrepath` app schema), then bring up observability profile services.

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

Then start frontend; run health check; seed god user.

---

## 4. God test user

### App (HyrePath Postgres `users`)

| Field | Value |
|-------|--------|
| Email | `god@hyrepath.local` |
| Password | `HyrepathGodTest123!` |
| Flags | `is_verified=True`, `is_active=True`, `is_superuser=True` |

`is_superuser` bypasses all RBAC (`user_has_permission` short-circuit). No role assignment required.

**Note:** `backend/scripts/create_test_user.py` refuses `APP_ENV=staging|production`. Preview seed must be a dedicated idempotent script (`06-seed-god-user.sh`) that writes the row the same way `smoke_admin_live.py` does.

### Observability (same credentials, separate auth)

Langfuse and GlitchTip do **not** use HyrePath `users`. Operator rule: register the **same** email/password in each UI on Day-1.

| System | Auth |
|--------|------|
| HyrePath app / admin | Seeded god user |
| Langfuse | Manual register — same email/password |
| GlitchTip | Manual register — same email/password |
| BFF / smoke | `API_TOKEN` in `.env.staging` (machine token) |

---

## 5. Bug-fix loop (always)

```text
1. Edit on main (code / env / compose)
2. Run matching redeploy script
3. Run 99-health.sh — must pass
4. git add -A && git commit && git push origin main
```

Deploy on this EC2 first. Push records what is already live.

| Change type | Script |
|-------------|--------|
| `.env.staging` only | `02-redeploy-env.sh` |
| App / sidecar code | `03-redeploy-code.sh <services…>` |
| Compose / Docker config | `04-redeploy-compose.sh` |
| Enable Multilogin later | `05-deploy-multilogin.sh` |

**Code → container map**

| Change location | Rebuild |
|-----------------|---------|
| API / modules / routes | `api` |
| Enrichers / pipeline / workers | `worker` (+ email / job-matching / cleanup when that path) |
| Document / embedding / interview workers | matching `worker-*` |
| Sidecar Dockerfile | that sidecar |
| Migration only | `migrate`, then recreate `api` |

---

## 6. Script inventory (to implement later — not in this commit)

All under `backend/scripts/deploy/`. Shared defaults: `REPO`, `ENV_FILE=$REPO/backend/.env.staging`, compose file set + profiles from §3.

| Script | Purpose |
|--------|---------|
| `01-full-up.sh` | First / full Day-1 stack (no Multilogin) |
| `02-redeploy-env.sh` | Force-recreate containers that read env (no rebuild) |
| `03-redeploy-code.sh` | `up -d --build --no-deps` for named services |
| `04-redeploy-compose.sh` | Re-apply full Day-1 compose after YAML/Docker config change |
| `05-deploy-multilogin.sh` | Load tier-workers + multilogin; start `multilogin` + `worker-tier1` (+ `worker-tier234` if needed) |
| `06-seed-god-user.sh` | Idempotent god user seed |
| `10-backup-db.sh` | Wrapper around `backend/scripts/backup_postgres.sh` |
| `11-stack-down.sh` | `docker compose down` **without** `-v` (volumes kept) |
| `12-restore-db.sh` | Restore dump via `restore_postgres.sh`, then forward `alembic upgrade head`, recreate app workers |
| `13-nuclear-reset.sh` | Only legal `down -v`: mandatory backup + typed phrase `WIPE ALL DATA` |
| `99-health.sh` | `GET /health` + `GET /ready` (+ optional `make smoke-prod`) |

### Hard ops rules (encode in scripts / comments)

```text
NEVER: docker compose down -v          → use 13-nuclear-reset.sh
NEVER: alembic downgrade               → use 12-restore-db.sh
ALWAYS: backup before nuclear / scary migration → 10-backup-db.sh
SAFE STOP: 11-stack-down.sh
```

### Data preserve matrix

| Action | Data |
|--------|------|
| `alembic upgrade head` | Preserved |
| Rebuild/recreate app containers | Preserved |
| `docker compose down` (no `-v`) | Preserved (`postgres_data` volume) |
| Restart postgres container | Preserved |
| `docker compose down -v` | **Destroyed** |
| Alembic downgrade | **Forbidden** — restore backup |

Postgres durability: Docker volume `postgres_data`. Redeploy scripts must never pass `-v` except `13-nuclear-reset.sh`.

---

## 7. Multilogin (later phase)

When Tier 1 LinkedIn testing starts:

1. Set `ENABLE_TIER1=true`, `ENABLE_LINUX_MLX=true`.
2. Put Multilogin / LinkedIn / R2 secrets in `/etc/hyrepath/worker.env` (mode `600`).
3. Keep AWS build args for `Dockerfile.multilogin` in compose `--env-file` (`.env.staging`).
4. Run `05-deploy-multilogin.sh` (compose + `docker-compose.multilogin.yml`).
5. Health-check Multilogin launcher + `worker-tier1`.

Until then: test every other feature first.

---

## 8. Feature test order (Day-1)

1. `/health` + `/ready`
2. Login as god user (frontend)
3. Admin / staff surfaces
4. Sync + async enrichment (Tiers 2–4 / sidecars)
5. Email verifier / social / maps paths
6. Documents, embeddings, job matching, interview AI
7. LiteLLM / Ollama paths as configured
8. Langfuse / GlitchTip / changedetection with same credentials
9. Compliance / opt-out / DSAR as implemented
10. **Last:** Multilogin via `05`

---

## 9. Day-1 execution checklist

```text
[ ] Single OS user + Docker ready
[ ] backend/.env.staging filled
[ ] Scripts implemented under backend/scripts/deploy/ (future task)
[ ] 01-full-up.sh
[ ] Create langfuse + glitchtip databases
[ ] 06-seed-god-user.sh
[ ] Register same email/password in Langfuse + GlitchTip
[ ] Frontend build + start on :3000
[ ] Reverse proxy wired
[ ] 99-health.sh
[ ] Cron for 10-backup-db.sh
[ ] Manual smoke of features (no Multilogin)
[ ] git push origin main (after any fixes already deployed)
```

---

## 10. Out of scope for this plan document

- Implementing any of the scripts above
- Running the Day-1 bring-up
- Enabling Multilogin
- Changing GitHub Actions `deploy.yml` behavior
- Creating ADRs (no storage/queue/auth/layer ownership change yet)

---

## 11. Related existing repo docs

- `docs/deployment.md` — staging/prod compose, secrets, CD
- `docs/OPS.md` — rollback, forward-only migrations, restore-from-backup
- `backend/scripts/start_production.sh` — production-shaped entrypoint
- `backend/scripts/backup_postgres.sh` / `restore_postgres.sh` — backup engines to wrap
- `backend/docker/docker-compose*.yml` — overlays and profiles
- ADR 0008 — Tier 1 Linux host network / Multilogin

---

## Implementation note

When implementing later: add only `backend/scripts/deploy/*.sh` (and optionally a short operator pointer from `docs/deployment.md`). Keep changes minimal. Do not invent a seventh “smart” deploy that guesses change type — operators pick `02` / `03` / `04` / `05` explicitly.
