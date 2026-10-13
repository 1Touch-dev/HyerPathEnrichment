# Production deployment

Operator guide for deploying Hyrepath Enrichment to staging and production. The API listens on HTTP port 8000 inside Docker; **TLS terminates at the reverse proxy**.

Target production host: `enrich.hyrepath.io` (or agreed domain).

**Status (2026-07-21):** The deploy + acceptance automation below (compose
file, env templates, `scripts/prod_full_acceptance.sh`) is verified end-to-end
via a local dry run — see [PROD_ACCEPTANCE.md](PROD_ACCEPTANCE.md#local-dry-run-evidence-2026-07-21)
and evidence at [`backend/docs/e2e-evidence/prod-dryrun-2026-07-21/`](../backend/docs/e2e-evidence/prod-dryrun-2026-07-21/).
**What this repo currently proves:** deployment automation and compose
resolution via local dry run. **What still needs external validation:** a real
Linux-host Tier 1 run for the supported Linux MLX path, plus the usual VPS/DNS
go-live work. Those are operational validation steps, not additional code
changes in this repo.

## Architecture

```
Internet → Caddy/nginx (TLS :443) → API :8000 (127.0.0.1 only)
                                  → Frontend static/BFF (if co-hosted)
         → Managed Postgres / Redis (or internal compose services)
         → Sidecars: social-analyzer, google-maps-scraper, email-verifier
         → Queue consumers: worker, worker-email, worker-job-matching
         → Maintenance: worker-cleanup
         → Tier workers: worker-tier234, worker-tier1, multilogin (Linux MLX path)
```

## Secrets checklist

| Secret | Services | Notes |
|--------|----------|-------|
| `API_TOKEN` | api, worker, frontend `BACKEND_API_TOKEN` | Must match across all |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `DATABASE_URL` | api, worker, postgres | Use strong password; no dev `hyrepath` default |
| `REDIS_URL` | api, worker | Internal network URL with auth if exposed |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN` | compose build for `multilogin` | Keep these in `backend/.env.production` / the compose `--env-file`; build-arg interpolation does not read `WORKER_ENV_FILE` |
| `R2_*` | worker (Tier 1) | Required when `APP_ENV=production\|staging` and `ENABLE_TIER1=true` |
| `MULTILOGIN_*`, `LINKEDIN_BOT_*` | worker only | Via `WORKER_ENV_FILE=/etc/hyrepath/worker.env` |
| `GITHUB_TOKEN`, LLM keys, webhooks | per feature flags | See [backend/.env.production.example](../backend/.env.production.example) |

### Secret delivery

1. **API + worker (non-Tier-1):** copy [backend/.env.production.example](../backend/.env.production.example) to `backend/.env.production` on the host (mode `600`). Set `API_ENV_FILE` if using a different path.
2. **Linux MLX build:** keep `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and optional `AWS_SESSION_TOKEN` in `backend/.env.production` (or whatever file you pass as `API_ENV_FILE` / compose `--env-file`). That is the single source of truth for `docker-compose.multilogin.yml` build args.
3. **Tier 1 worker runtime:** create `/etc/hyrepath/worker.env` (mode `600`) with Multilogin, LinkedIn bot, and R2 credentials. Use the supported Linux production family only: `docker-compose.foundation.yml` + `docker-compose.tier-workers.yml` + `docker-compose.multilogin.yml`, or `bash backend/scripts/start_production.sh --with-linux-mlx`.
4. **Frontend:** set `BACKEND_API_URL=https://enrich.hyrepath.io` and `BACKEND_API_TOKEN` (same as `API_TOKEN`) in the deployment platform — never expose in client bundles.

## Staging / production env parity

Both environments must define the **same variable keys**. Values differ (URLs, tokens, bucket names).

Templates:

- [backend/.env.staging.example](../backend/.env.staging.example)
- [backend/.env.production.example](../backend/.env.production.example)

Verify parity before deploy:

```bash
python backend/scripts/verify_env_parity.py \
  --staging backend/.env.staging.example \
  --production backend/.env.production.example
```

Set `APP_ENV=staging` or `APP_ENV=production` — this enables R2 fail-fast validation when Tier 1 is on.

## Docker Compose (production overlay)

Recommended entrypoint:

```bash
bash backend/scripts/start_production.sh
```

Manual base compose example (API/readiness only under the shipped `WORKER_QUEUE_MODE=per_tier` contract: this is a partial diagnostic bring-up, not a supported async enrichment production path, and it intentionally starts no async workers):

From `backend/docker`:

```bash
export API_TOKEN='…'
export DATABASE_URL='postgresql+asyncpg://…'
export REDIS_URL='redis://…'
export POSTGRES_USER='…'
export POSTGRES_PASSWORD='…'

docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  --env-file ../.env.production \
  up -d migrate api redis postgres social-analyzer google-maps-scraper email-verifier
```

Tier 1 worker (supported Linux production path only):

```bash
export WORKER_ENV_FILE=/etc/hyrepath/worker.env
docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.foundation.yml \
  -f docker-compose.tier-workers.yml \
  -f docker-compose.multilogin.yml \
  up -d migrate api redis postgres social-analyzer google-maps-scraper email-verifier worker worker-email worker-cleanup worker-job-matching worker-tier234 worker-tier1 multilogin
```

[docker-compose.prod.yml](../backend/docker/docker-compose.prod.yml) binds the API and host-network Tier 1 dependencies to `127.0.0.1` only, and requires `${API_TOKEN}`, `${DATABASE_URL}`, `${REDIS_URL}`. On the supported Linux MLX path, `worker` drains the auxiliary queues (including `audio_cleanup`), `worker-email` drains the `email` queue, `worker-job-matching` owns scheduler seeding and the dedicated `job_matching` queue, and `worker-cleanup` handles orphan-job maintenance.

For the current S3-backed `Dockerfile.multilogin` build, AWS credentials come from the main compose env file (`backend/.env.production` by default), not from `WORKER_ENV_FILE`. `WORKER_ENV_FILE` is runtime-only for `worker-tier1`.

The Linux MLX path above is the supported operational target. On real Linux, Tier 1 should be treated as unsupported unless `ENABLE_LINUX_MLX=true` / `bash backend/scripts/start_production.sh --with-linux-mlx` selects that full family. This Windows/WSL repo host proves the compose/config/service-health contract for that topology, but a real Linux-host end-to-end Tier 1 validation run is still the final proof step for `worker-tier1 -> multilogin -> LinkedIn`.

## TLS (Caddy)

Day-1 host terminates TLS at systemd Caddy (`/etc/caddy/Caddyfile`, **not** in git). Frontend domains reverse-proxy to Next on `127.0.0.1:3000`. The API is published on the host as `API_HOST_PORT` (this EC2: **8002**).

### Stripe webhook path (proposed — apply only with approval)

Next.js has no `/api/billing/webhooks/stripe` route. Public POSTs today return **404**. FastAPI serves `POST /api/billing/webhooks/stripe` on the API port and requires a valid `Stripe-Signature` over the **raw body**.

Route **only** that path to the API; keep all other traffic on the frontend:

```caddy
# Apply on each public site that should accept Stripe webhooks
# (recommend canonical: https://app.hyerpath.com/api/billing/webhooks/stripe).
handle /api/billing/webhooks/stripe* {
	reverse_proxy 127.0.0.1:8002
}
handle {
	reverse_proxy 127.0.0.1:3000
}
```

Validate before reload:

```bash
sudo cp -a /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak.$(date -u +%Y%m%dT%H%M%SZ)
# edit /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
# Expect 400 (signature), not 404:
curl -sS -o /dev/null -w '%{http_code}\n' -X POST \
  https://app.hyerpath.com/api/billing/webhooks/stripe
```

Rollback: restore the `.bak.*` file, `caddy validate`, `systemctl reload caddy`.

Caddy obtains Let's Encrypt certificates automatically. For Cloudflare, use DNS challenge or Cloudflare proxy with origin cert.

R2 CDN: configure custom domain TLS in Cloudflare for the bucket public URL (`R2_PUBLIC_BASE_URL`).

## Readiness

- `GET /health` — liveness (no dependency checks)
- `GET /ready` — returns 503 if Postgres or Redis is unreachable

Configure the reverse proxy or load balancer to use `/ready` for routing decisions.

## Post-deploy verification

```bash
BASE_URL=https://enrich.hyrepath.io API_TOKEN='…' make smoke-prod
BASE_URL=https://enrich.hyrepath.io API_TOKEN='…' bash backend/scripts/prod_acceptance.sh
```

See [PROD_SMOKE.md](PROD_SMOKE.md) and [PROD_ACCEPTANCE.md](PROD_ACCEPTANCE.md).

## Continuous deployment (GitHub Actions)

Single host, single GitHub Environment **`production`**. Testing now; later the same Environment becomes live (turn on Required reviewers — no second stack).

Workflow: [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml). Host script: [`backend/scripts/deploy/cd-on-host.sh`](../backend/scripts/deploy/cd-on-host.sh).

```text
push main → CI success (push only) → five :<sha> images → GHCR
  → Environment production → SSH this EC2
  → refuse dirty/unpushed; skip if .deploy/hold; flock .deploy/lock
  → git checkout main && git reset --hard SHA
  → write .deploy/candidate_sha (not success yet)
  → compose config → pull → ensure langfuse/glitchtip DBs (idempotent)
  → Day-1 up → frontend (bounded wait_for_http) → health
  → verify running api image tag matches SHA
  → record .deploy/current_sha (only on full success)
```

Host state under `.deploy/`:

| File | Meaning |
|------|---------|
| `hold` | Skip CD entirely (exit 0) |
| `lock` | `flock` — concurrent SSH deploys refuse |
| `candidate_sha` | In-flight SHA (set before mutate; may remain after failure) |
| `current_sha` | Last **healthy** release — never written on HEALTH_FAIL |
| `previous_sha` | Prior `current_sha` (updated only when success advances) |
| `history.log` | Append-only SUCCESS / HEALTH_FAIL / IMAGE_MISMATCH / STATE_REJECT |

Idempotent DB ensure and readiness helpers live in [`_common.sh`](../backend/scripts/deploy/_common.sh). Host self-check: `bash backend/scripts/deploy/test-cd-reliability.sh`.

| Trigger | Build → GHCR | SSH deploy |
|---------|--------------|------------|
| Green **CI** after **push** to `main` | Yes | Yes (`environment: production`) |
| Green CI from a **PR** | No | No (`workflow_run.event` must be `push`) |
| Failed / cancelled CI | No | No |
| Commit message contains `[skip cd]` | No | No |
| `.deploy/hold` on the host | Images may build | SSH exits 0 without touching git/compose |
| `workflow_dispatch` + `dry_run=true` | Plan only | Skipped |
| `workflow_dispatch` + `dry_run=false` | Yes | Yes |

CD never `git commit` or `git push`. After deploy, the repo stays on **`main`** (not detached) so you can SSH, edit, commit, and push.

### Day-1 stack (what CD starts)

Same files, profiles, and services as [`01-full-up.sh`](../backend/scripts/deploy/01-full-up.sh) / [`_common.sh`](../backend/scripts/deploy/_common.sh):

- Files: `docker-compose.yml` + `foundation.yml` + `week2-ai.yml` + `tier-workers.yml` + `staging.yml` (last, so `APP_ENV=staging` wins) + `--env-file backend/.env.production`
- Profiles: `paid`, `llm`, `observability`, `scrapoxy`. Ollama is not started; LLM calls use API keys (`LLM_MODE=litellm`).
- All `DAY1_SERVICES` (api, workers, sidecars, LLM, observability). **Not** `multilogin` / `worker-tier1`. Do not load `docker-compose.multilogin.yml` or `docker-compose.tier1.yml`.
- Frontend: full Next.js via [`08-redeploy-frontend.sh`](../backend/scripts/deploy/08-redeploy-frontend.sh) (pm2 `:3000`).
- Health: [`99-health.sh`](../backend/scripts/deploy/99-health.sh).

Do **not** switch CD to `docker-compose.prod.yml` until go-live (that overlay binds API to `127.0.0.1:8000` and would break the current `:8002` public map).

### Images (SHA is the version)

`ghcr.io/<owner>/<repo>/…:<git-sha>` (lowercase). `:latest` is also pushed but production always pins `:<sha>`.

| Image | Services |
|-------|----------|
| `…/api:<sha>` | `migrate`, `api` |
| `…/worker:<sha>` | `worker`, `worker-email`, `worker-cleanup`, `worker-tier234`, `worker-interview-ai` |
| `…/worker-document:<sha>` | `worker-document` |
| `…/worker-embedding:<sha>` | `worker-embedding` |
| `…/worker-job-matching:<sha>` | `worker-job-matching` |

Sidecars stay public or host-built images. Overlay: generated `backend/docker/docker-compose.cd-images.yml` (gitignored).

### GitHub Environment secrets

Create Environment **`production`**. Leave Required reviewers **off** while this host is the test environment.

| Secret | Required | Purpose |
|--------|----------|---------|
| `SSH_HOST` | Yes | EC2 Elastic IP (this host: `54.87.41.86`) |
| `SSH_USER` | Yes | SSH username (`ubuntu`) |
| `SSH_KEY` | Yes | Private key (PEM) for `SSH_USER` |
| `SSH_PORT` | No | Default `22` |
| `SSH_HOST_FINGERPRINT` | No | Host key fingerprint (prefer over skipping host checks) |
| `GHCR_USERNAME` | Yes | Account that can `docker pull` |
| `GHCR_TOKEN` | Yes | PAT with `read:packages` only (host login) |
| `DEPLOY_PATH` | No | Host path to `backend/docker` (default `/home/ubuntu/HyerPathEnrichment/backend/docker`) |

Registry **push** uses job `GITHUB_TOKEN` (`packages: write`). Host **pull** uses `GHCR_TOKEN`.

App secrets stay in `backend/.env.production` and `frontend/.env.local` on the host (`chmod 600`). CD does not copy them from GitHub.

### SSH hotfix when CD is broken

Host scripts do not need GHCR:

```bash
cd /home/ubuntu/HyerPathEnrichment
mkdir -p .deploy && touch .deploy/hold   # block incoming CD
# edit files
bash backend/scripts/deploy/01-full-up.sh
bash backend/scripts/deploy/08-redeploy-frontend.sh
bash backend/scripts/deploy/99-health.sh
git add -A && git commit -m "hotfix [skip cd]" && git push origin main
rm -f .deploy/hold
```

- Dirty working tree or unpushed commits → CD **fails** and does not `reset --hard`.
- `.deploy/hold` → CD **skips** (green) and does not touch git or compose.
- `[skip cd]` in the commit message → Actions skips image build and SSH.
- To pause all auto-deploys: Actions → Deploy → Disable workflow. Host scripts still work.

### Dry-run

1. Actions → **Deploy** → **Run workflow**
2. Set `dry_run=true`
3. Job verifies Dockerfiles/compose/host scripts exist and prints planned image tags; **does not** build, push, or SSH

### Validate the workflow (actionlint)

```bash
actionlint .github/workflows/deploy.yml
```

### CD rollback

1. Read `.deploy/previous_sha` on the host (or the last green Deploy SHA).
2. `workflow_dispatch` that SHA, or on the host:

```bash
cd /home/ubuntu/HyerPathEnrichment
PREV=$(cat .deploy/previous_sha)
# set the five image names + IMAGE_TAG=$PREV and re-run cd-on-host.sh
# or: 01-full-up.sh after git checkout main && git reset --hard "$PREV"
```

3. Database: Alembic is forward-only — restore Postgres from backup if a migration was the failure (see [OPS.md](OPS.md)). Do not assume automatic DB rollback is safe.

### Go-live later (same Environment, same stack)

- Turn on **Required reviewers** on `production`.
- Point DNS at the Elastic IP; terminate TLS at Caddy; bind API via `docker-compose.prod.yml` when you are ready to drop public `:8002`.
- Rotate secrets; restrict SSH; wire [`10-backup-db.sh`](../backend/scripts/deploy/10-backup-db.sh) before migrate.

## Related docs

- [backend/docs/ARCHITECTURE.md](../backend/docs/ARCHITECTURE.md) — env table, request flow
- [backend/docs/LEGAL.md](../backend/docs/LEGAL.md) — compliance boundaries
- [OPS.md](OPS.md) — rollback, audit purge, incidents
