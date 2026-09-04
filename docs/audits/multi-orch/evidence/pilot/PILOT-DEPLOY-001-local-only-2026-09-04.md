# `PILOT-DEPLOY-001` Local-Only Evidence — 2026-09-04

## Label

This evidence is **local-only**. It does **not** claim staging or production
equivalence, and it does **not** establish any remote host provenance.

## Chosen local target

- Target: isolated localhost `staging`-shaped compose rehearsal
- Compose project: `wave3pilotlocal`
- Compose path used: `backend/docker/docker-compose.yml` +
  `backend/docker/docker-compose.staging.yml` + a generated local image-override file
- Why this target: it is the closest local equivalent of the repo's real pilot
  deploy path without inventing a remote host

## Inputs prepared

- Local env file: `/tmp/hyrepath-wave3-local-staging.env`
- Local service-image override: `/tmp/hyrepath-wave3-local-service-images.yml`
- RC image override: `/tmp/hyrepath-wave3-local-current-images.yml`
- Candidate rollback anchor image override: `/tmp/hyrepath-wave3-local-good-images.yml`

## Rollback anchor assessment

- Candidate previous-version anchor: `6da855b`
- Current RC deploy SHA: `85fa8f5654ef6393a90c65dfb1905c1c5859dde1`
- Diff check: no `backend/alembic/` changes between `6da855b` and the RC, so a
  code-only rollback rehearsal would have been acceptable if both image sets
  could be built and started locally

## Commands executed

```bash
bash backend/scripts/validate_env.sh /tmp/hyrepath-wave3-local-staging.env
git worktree add --detach /tmp/hyrepath-wave3-rc-85fa8f5 85fa8f5
git worktree add --detach /tmp/hyrepath-wave3-good-6da855b 6da855b
docker build -t hyrepath-local/api:85fa8f5 -f /tmp/hyrepath-wave3-rc-85fa8f5/backend/docker/Dockerfile.api /tmp/hyrepath-wave3-rc-85fa8f5/backend
docker build -t hyrepath-local/worker:85fa8f5 -f /tmp/hyrepath-wave3-rc-85fa8f5/backend/docker/Dockerfile.worker /tmp/hyrepath-wave3-rc-85fa8f5/backend
COMPOSE_PROJECT_NAME=wave3pilotlocal docker compose \
  -f backend/docker/docker-compose.yml \
  -f backend/docker/docker-compose.staging.yml \
  -f /tmp/hyrepath-wave3-local-service-images.yml \
  --env-file /tmp/hyrepath-wave3-local-staging.env \
  up -d --no-build migrate api redis postgres social-analyzer google-maps-scraper email-verifier
```

## Observed outcomes

### Env validation

- `validate_env.sh` completed successfully for the local-only staging-shaped env file

### Image preparation

- `hyrepath-local/api:85fa8f5` became locally available
- Current RC worker image build failed
- Previous-version anchor image build did not complete

### Exact blocker observed

The local-only rehearsal hit machine-capacity limits rather than app startup
validation:

```text
no space left on device
```

Observed in two places:

1. RC image export / extraction during Docker build
2. `docker compose up` while extracting the `migrate` image layer for the local stack

Supporting local machine evidence captured during this run:

- root filesystem free space was approximately `741M`
- `docker system df` reported roughly `12.97GB` build cache and `34.86GB` image usage

## What did NOT happen

Because the current RC could not be fully extracted and started locally:

- the local pilot stack never reached a running API state
- no live local `/health` or `/ready` result could be collected from the RC stack
- no smoke run could be executed against the RC stack
- no queue/worker verification could be completed
- no local pilot acceptance evidence could be honestly created

## Result

`PILOT-DEPLOY-001` was revised to a local-only rehearsal and attempted via the
repo's real compose deploy path. It remains **blocked** because the current RC
cannot be fully started on this machine under the available Docker disk headroom.

Even if the local stack had started successfully, that evidence would still have
remained explicitly local-only and would not by itself prove remote staging or
production readiness.
