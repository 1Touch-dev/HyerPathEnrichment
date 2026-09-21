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

## TLS (Caddy example)

Install Caddy on the host. Example `/etc/caddy/Caddyfile`:

```
enrich.hyrepath.io {
    reverse_proxy 127.0.0.1:8000
}
```

Caddy obtains Let's Encrypt certificates automatically. For Cloudflare, use DNS challenge or Cloudflare proxy with origin cert.

Frontend (if separate): deploy to Vercel/Cloudflare Pages with `BACKEND_API_URL=https://enrich.hyrepath.io`.

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

Workflow: [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml).

| Trigger | Build → GHCR | Staging | Production |
|---------|--------------|---------|------------|
| Push to `main` | Yes | Auto (`environment: staging`) | — |
| `workflow_dispatch` + `target=staging` | Yes | Auto | — |
| `workflow_dispatch` + `target=production` | Yes | — | Manual approval (`environment: production`) |
| `workflow_dispatch` + `dry_run=true` | Plan only (verify Dockerfiles; no build/push) | Skipped | Skipped |

Images (per commit SHA + `latest`):

- `ghcr.io/<owner>/<repo>/api:<sha>`
- `ghcr.io/<owner>/<repo>/worker:<sha>`

Dockerfiles: [`backend/docker/Dockerfile.api`](../backend/docker/Dockerfile.api), [`backend/docker/Dockerfile.worker`](../backend/docker/Dockerfile.worker).

Remote compose overlays (from `backend/docker` on the host):

- **Staging:** `docker-compose.yml` + `docker-compose.staging.yml` + generated `docker-compose.cd-images.yml`
- **Production:** `docker-compose.yml` + `docker-compose.prod.yml` + generated `docker-compose.cd-images.yml`

### GitHub Environments and secrets

Create Environments **`staging`** and **`production`**. On **production**, enable **Required reviewers** so deploys wait for approval.

Set these secrets on each Environment (values may differ per env; never commit them):

| Secret | Required | Purpose |
|--------|----------|---------|
| `SSH_HOST` | Yes | Deploy host hostname or IP |
| `SSH_USER` | Yes | SSH username |
| `SSH_KEY` | Yes | Private key (PEM) for `SSH_USER` |
| `SSH_PORT` | No | SSH port (appleboy default `22` if unset) |
| `GHCR_USERNAME` | Yes | GitHub user/bot that can pull packages |
| `GHCR_TOKEN` | Yes | PAT or fine-grained token with `read:packages` (host `docker login`) |
| `DEPLOY_PATH` | No | Host path to `backend/docker` (default `/opt/hyrepath/HyerPathEnrichment/backend/docker`) |
| `COMPOSE_ENV_FILE` | No | Env file on host (default `../.env.staging` or `../.env.production`) |

Registry **push** from Actions uses `GITHUB_TOKEN` with `packages: write` (workflow permission). Host **pull** uses `GHCR_TOKEN` — do not rely on job `GITHUB_TOKEN` on the VPS.

App secrets (`API_TOKEN`, `DATABASE_URL`, R2, Multilogin, etc.) stay on the host env files — not in GitHub Actions secrets unless you deliberately migrate them later.

### Dry-run

1. Actions → **Deploy** → **Run workflow**
2. Set `dry_run=true` (optional: pick `target` for the plan summary)
3. Job verifies Dockerfiles/compose overlays exist and prints planned image tags; **does not** build, push to GHCR, or SSH

### Validate the workflow (actionlint)

```bash
# Install: https://github.com/rhysd/actionlint
#   go install github.com/rhysd/actionlint/cmd/actionlint@latest
#   # or download a release binary
actionlint .github/workflows/deploy.yml
```

If `actionlint` is unavailable, use the UI dry-run above as the proof path.

### CD rollback

1. Find the last known-good commit SHA (previous green Deploy run or GHCR tag).
2. On the host (`backend/docker`), pin images and recreate:

```bash
API=ghcr.io/<owner>/<repo>/api
WORKER=ghcr.io/<owner>/<repo>/worker
GOOD_SHA=<previous-sha>

{
  echo "services:"
  echo "  migrate:"
  echo "    image: ${API}:${GOOD_SHA}"
  echo "  api:"
  echo "    image: ${API}:${GOOD_SHA}"
  echo "  worker:"
  echo "    image: ${WORKER}:${GOOD_SHA}"
} > docker-compose.cd-images.yml

# staging:
docker compose -f docker-compose.yml -f docker-compose.staging.yml -f docker-compose.cd-images.yml \
  --env-file ../.env.staging pull api worker migrate
docker compose -f docker-compose.yml -f docker-compose.staging.yml -f docker-compose.cd-images.yml \
  --env-file ../.env.staging up -d --no-build

# production: swap staging overlay for docker-compose.prod.yml and ../.env.production
```

3. Or re-run **Deploy** via `workflow_dispatch` on the good commit (production still needs approval).
4. Database: Alembic is forward-only — restore Postgres from backup if a migration was the failure (see [OPS.md](OPS.md)).

## Related docs

- [backend/docs/ARCHITECTURE.md](../backend/docs/ARCHITECTURE.md) — env table, request flow
- [backend/docs/LEGAL.md](../backend/docs/LEGAL.md) — compliance boundaries
- [OPS.md](OPS.md) — rollback, audit purge, incidents
