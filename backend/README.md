# Hyrepath Enrichment Backend

FastAPI backend for asynchronous and synchronous enrichment dossier generation.

## Run locally

Local dev uses SQLite by default (see `.env.example`) — no Postgres needed.

```bash
uvicorn app.main:app --reload --app-dir backend
```

## Run with Docker Compose (Postgres + Redis)

API and worker images build from the `backend/` directory (not the repo root), so
local virtualenvs and frontend assets are not sent to Docker.

API and worker share one Postgres instance, and job data survives restarts via
the `postgres_data` volume. Supported async `POST /enrich` routing under the
shipped per-tier contract uses the tier-worker family described below.

```bash
cd backend/docker
docker compose up --build api worker redis postgres
```

This base compose shape is a quick local smoke path. Under the shipped
`WORKER_QUEUE_MODE=per_tier` contract it is not the supported async enrichment
topology; use `docker-compose.tier-workers.yml` (or
`bash backend/scripts/start_production.sh --with-linux-mlx` on real Linux) when
you need the production-style worker family.

## Fast local dev (full stack)

`dev-up.sh` is a "nodemon for Docker" entrypoint: it brings up the whole
backend — base services + AI/document/embedding/job-matching/interview-AI
workers + the `llm`/`paid`/`observability` profiles (LiteLLM, Reacher,
Scrapoxy, Langfuse, changedetection.io, GlitchTip) — using your existing
`backend/.env.production`, then keeps it live-reloading while you code:

- **Inner loop** — `docker compose watch` (`docker-compose.watch.yml`,
  `develop.watch`): syncs `backend/app` into the running containers and
  restarts them on save. No image rebuild, no bind-mount I/O overhead.
- **Outer loop** — `watch-infra.sh`, run alongside it: watches the things
  `docker compose watch` can't react to — `docker-compose*.yml`,
  `Dockerfile.*`, `.env`, `.env.production` — and re-runs `up -d --build`
  (cheap, Docker-layer-cached) when one of those changes.

Multilogin / Tier 1 are never started by this workflow. The supported real-Linux
Tier 1 path is `bash backend/scripts/start_production.sh --with-linux-mlx`,
which resolves the full required family (`docker-compose.prod.yml` +
`docker-compose.foundation.yml` + `docker-compose.tier-workers.yml` +
`docker-compose.multilogin.yml`). The legacy `docker-compose.tier1.yml` path is
diagnostic-only for WSL2/Windows and is rejected for effective Tier 1 on real
Linux.

**Prerequisites:**

- `backend/.env.production` already exists locally, populated with real
  values (never committed — see the Security note in
  `docker-compose.prod.yml`'s header and `scripts/validate_env.sh`).
- [`watchfiles`](https://pypi.org/project/watchfiles/) on `PATH`:
  `pip install watchfiles`.
- Docker Compose v2.20+ (this workflow was verified on Docker Compose
  v5.4.0 / Docker 29.7.2) for `docker compose watch` support.

**Run it:**

```bash
cd backend/docker
bash dev-up.sh
```

This does an initial `up -d --build`, launches `watch-infra.sh` in the
background, then runs `docker compose watch` in the foreground. Ctrl-C
stops the foreground watch and cleans up the background infra watcher.
Tear the whole stack down separately with:

```bash
docker compose -f docker-compose.yml -f docker-compose.foundation.yml \
  -f docker-compose.week2-ai.yml -f docker-compose.watch.yml \
  --env-file ../.env.production down
```

**Per-OS setup notes:**

- **Linux / macOS** — run `dev-up.sh` directly in a native terminal with
  Docker Desktop (or Docker Engine) and `watchfiles` installed.
- **Windows** — Docker Desktop's Linux containers require WSL2; run
  `dev-up.sh` from a WSL2 shell (or Git Bash with Docker Desktop's
  Windows/WSL2 integration enabled) — not plain PowerShell/cmd, since the
  script is POSIX/bash. Same command either way: `bash dev-up.sh` from
  `backend/docker`.

Optional troubleshooting tip, not a required setup step: if the full
profile set feels heavy on your machine, tune Docker's resource limits —
Docker Desktop's Settings → Resources on Windows/macOS, a `.wslconfig`
specifically for WSL2 (personal, local file — not part of this repo), or
cgroup limits on native Linux.

### Worker Scaling

**Single-queue mode (legacy/local override):** All workers process jobs from one shared queue when you explicitly run with `WORKER_QUEUE_MODE=single`.

```bash
# Scale workers horizontally (4 workers processing any tier)
docker compose up -d --scale worker=4
```

**Tier-specific workers:** Dedicated worker pools per tier with separate concurrency levels.

```bash
# Deploy with tier-specific workers for the supported auxiliary + tier234 path
docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.foundation.yml \
  -f docker-compose.tier-workers.yml \
  up -d api worker worker-email worker-cleanup worker-job-matching worker-tier234

# Tier 1 on real Linux is single-instance and must use:
#   bash backend/scripts/start_production.sh --with-linux-mlx
# Tier 2-4 (API): N workers via --scale worker-tier234=N
```

**Environment variables for tier-specific routing:**

```bash
# Queue routing mode (settings default: single; shipped Docker contract: per_tier)
WORKER_QUEUE_MODE=per_tier  # or "single"

# For per_tier mode, each worker specifies its queue
WORKER_TARGET_QUEUE=tier1    # or "tier234"
```

See `docker-compose.tier-workers.yml` for the tier-specific worker configuration.
Do not scale `worker-tier1`; host networking plus Multilogin loopback sharing
make the supported Linux Tier 1 path single-instance only.

Then:

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/enrich \
  -H "Authorization: Bearer change-me" \
  -H "Content-Type: application/json" \
  -d '{"username": "jane-doe"}'
# poll with the returned job id until status is "completed"
curl http://localhost:8000/enrich/<job_id> -H "Authorization: Bearer change-me"
```

## Test

```bash
make test
# or: cd backend && pytest tests -m "not postgres" -q --cov=app --cov-report=term-missing
```

CI enforces a line-coverage floor for `app/` via `fail_under` in `pyproject.toml`.

Architecture decisions (why Redis vs in-process, SQLite vs Postgres, etc.): [`docs/adr/README.md`](../docs/adr/README.md).

Change-signal ops (changedetection.io → `NOTIFY_WEBHOOK_URL`): see [ARCHITECTURE.md — Change signals](docs/ARCHITECTURE.md#change-signals-changedetectionio).

Tier 2–4 debugging (prerequisites, isolation probes, tier-by-tier API curls): [`docs/TESTING_TIER234.md`](docs/TESTING_TIER234.md). Tier 2 full E2E: `bash scripts/e2e_tier2.sh`. Tier 3 full E2E: `bash scripts/e2e_tier3.sh`.

```bash
cd backend
python scripts/probe_enrichers.py
python scripts/probe_enrichers.py --prereqs
```
