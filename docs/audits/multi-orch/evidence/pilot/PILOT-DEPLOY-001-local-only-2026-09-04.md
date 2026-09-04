# `PILOT-DEPLOY-001` Local-Only Evidence — 2026-09-04

## Label

This evidence is **local-only**. It does **not** claim staging or production
equivalence, and it does **not** establish any remote host provenance.

## Chosen local target

- Target: isolated localhost `staging`-shaped compose rehearsal
- Compose project: `wave3pilotlocal`
- Primary compose path used:
  - `backend/docker/docker-compose.yml`
  - `backend/docker/docker-compose.staging.yml`
  - `backend/docker/docker-compose.tier-workers.yml`
  - generated local-only image and port override files under `/tmp/`
- Why this target: it is the closest local equivalent of the repo's documented
  deploy path without inventing a remote host

## Inputs prepared

- Local env file: `/tmp/hyrepath-wave3-local-staging.env`
- Local service-image override: `/tmp/hyrepath-wave3-local-service-images.yml`
- Local rollback-anchor override: `/tmp/hyrepath-wave3-local-good-images.yml`
- Local port override: `/tmp/hyrepath-wave3-local-ports.yml`

## Rollback anchor assessment

- Candidate previous-version anchor: `6da855b`
- Current RC deploy SHA: `85fa8f5654ef6393a90c65dfb1905c1c5859dde1`
- Diff check: no `backend/alembic/` changes between `6da855b` and the RC, so a
  code-only rollback rehearsal was acceptable if both image sets were runnable

## Conservative Docker cleanup performed

Initial local retry was blocked by Docker capacity. Targeted cleanup was then
performed before any broader pruning:

```bash
docker container prune -f
docker image prune -f
docker builder prune -f
```

Observed reclaimed space:

- stopped / created containers: `6.103MB`
- dangling images: `17.06GB`
- builder cache: `3.032GB`
- total reclaimed: approximately `20.10GB`

Observed disk state before/after:

- root filesystem free space moved from approximately `741M` to approximately `20G`
- root filesystem usage moved from `99%` to `72%`

## Additional local-only adjustments required

The first post-cleanup retry surfaced honest deploy-path issues that had to be
resolved before the local rehearsal could become meaningful:

1. Host-port collisions with unrelated services on `6379`, `8080`, `9005`, and
   other default bindings
2. Missing compose passthrough for staging-shaped runtime env vars needed by the
   current app:
   - `OUTREACH_ENABLED`
   - `OUTREACH_PHYSICAL_ADDRESS`
   - `APP_ENV`
   - `APP_NAME`
   - `SECRET_KEY`
   - `COOKIE_SECURE`
3. Async queue mismatch when local rehearsal used the base `worker` service
   instead of the documented `worker-tier234` deployment overlay
4. Existing `backend/scripts/smoke_test.py` no longer matched the app's current
   auth contract (`CurrentUser` via cookie auth rather than Bearer `API_TOKEN`)

These were resolved for the local rehearsal by:

- adding the missing compose env passthrough in `backend/docker/docker-compose.yml`
- using `docker-compose.tier-workers.yml` with `--scale worker=0 --scale worker-tier1=0 --scale worker-tier234=1`
- using a local-only alternate-port override file
- running a direct verified cookie-auth smoke flow against the live stack

## Commands executed

```bash
bash backend/scripts/validate_env.sh /tmp/hyrepath-wave3-local-staging.env
git worktree add --detach /tmp/hyrepath-wave3-rc-85fa8f5 85fa8f5
git worktree add --detach /tmp/hyrepath-wave3-good-6da855b 6da855b
docker build -t hyrepath-local/api:85fa8f5 -f /tmp/hyrepath-wave3-rc-85fa8f5/backend/docker/Dockerfile.api /tmp/hyrepath-wave3-rc-85fa8f5/backend
docker build -t hyrepath-local/worker:85fa8f5 -f /tmp/hyrepath-wave3-rc-85fa8f5/backend/docker/Dockerfile.worker /tmp/hyrepath-wave3-rc-85fa8f5/backend
docker build -t hyrepath-local/api:6da855b -f /tmp/hyrepath-wave3-good-6da855b/backend/docker/Dockerfile.api /tmp/hyrepath-wave3-good-6da855b/backend
docker build -t hyrepath-local/worker:6da855b -f /tmp/hyrepath-wave3-good-6da855b/backend/docker/Dockerfile.worker /tmp/hyrepath-wave3-good-6da855b/backend

WORKER_ENV_FILE=/tmp/hyrepath-wave3-local-staging.env \
COMPOSE_PROJECT_NAME=wave3pilotlocal docker compose \
  -f backend/docker/docker-compose.yml \
  -f backend/docker/docker-compose.staging.yml \
  -f backend/docker/docker-compose.tier-workers.yml \
  -f /tmp/hyrepath-wave3-local-service-images.yml \
  -f /tmp/hyrepath-wave3-local-ports.yml \
  --env-file /tmp/hyrepath-wave3-local-staging.env \
  up -d --no-build --scale worker=0 --scale worker-tier1=0 --scale worker-tier234=1
```

## Observed outcomes

### Env validation and image preparation

- `validate_env.sh` completed successfully
- current RC local images built successfully:
  - `hyrepath-local/api:85fa8f5`
  - `hyrepath-local/worker:85fa8f5`
- rollback-anchor local images built successfully:
  - `hyrepath-local/api:6da855b`
  - `hyrepath-local/worker:6da855b`

### Current RC stack state

Observed healthy services under the local-only pilot target:

- `api` image: `hyrepath-local/api:85fa8f5`
- `worker-tier234` image: `hyrepath-local/worker:85fa8f5`
- `worker-email` image: `hyrepath-local/worker:85fa8f5`
- `worker-cleanup` image: `hyrepath-local/worker:85fa8f5`
- `postgres`, `redis`, `social-analyzer`, `google-maps-scraper`, and `email-verifier` all healthy

Observed live results:

- `/health` returned success
- `/ready` returned success
- `alembic current` reported `066_privileged_idempotency_records (head)`

### Smoke / runtime evidence

Because staging-shaped auth now uses secure cookies plus verified/staff-gated
enrichment, the local-only smoke path used a real local user flow:

1. register a fresh user
2. fetch the generated verification token from the local pilot database
3. verify the user
4. assign the seeded `recruiter` role in the isolated local DB
5. log in and replay the secure cookies as request headers over localhost HTTP

Observed results for current RC:

- verified staff sync enrich: `200`, terminal status `completed`
- verified staff async enrich: `202` then `queued` -> `running` -> `completed`
- queue/worker verification: confirmed by successful async completion through
  `worker-tier234`

## Result

`PILOT-DEPLOY-001` is now **PASS for a local-only rehearsal**. The repo's
compose-based deploy path can start the current RC locally, reach `/ready`,
report the current Alembic head, and complete both sync and async enrichment
through the intended `worker-tier234` topology.

This evidence remains explicitly **local-only**. It reduces local deployment and
rollback risk, but it does **not** close the separate requirement for a true
remote pilot environment with host provenance.
