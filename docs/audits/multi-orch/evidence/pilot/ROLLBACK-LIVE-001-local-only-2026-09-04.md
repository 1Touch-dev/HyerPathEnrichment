# `ROLLBACK-LIVE-001` Local-Only Status — 2026-09-04

## Label

This is **local-only** rollback evidence/status. It does **not** claim any
remote staging or production rollback rehearsal.

## Execution decision

- Status: `PASS (local-only rehearsal)`
- Scope: current RC -> previous-version anchor -> current RC re-deploy

## Preconditions checked

- Current RC image set: `85fa8f5654ef6393a90c65dfb1905c1c5859dde1`
- Previous-version anchor: `6da855b`
- No `backend/alembic/` changes were found between `6da855b` and the RC
- Both image sets were built locally before rollback execution

## Rollback path executed

Rollback used the same local-only stack shape as the successful pilot:

- compose project: `wave3pilotlocal`
- compose files:
  - `backend/docker/docker-compose.yml`
  - `backend/docker/docker-compose.staging.yml`
  - `backend/docker/docker-compose.tier-workers.yml`
  - `/tmp/hyrepath-wave3-local-service-images.yml`
  - `/tmp/hyrepath-wave3-local-good-images.yml`
  - `/tmp/hyrepath-wave3-local-ports.yml`
- scale flags:
  - `--scale worker=0`
  - `--scale worker-tier1=0`
  - `--scale worker-tier234=1`

Executed rollback command shape:

```bash
WORKER_ENV_FILE=/tmp/hyrepath-wave3-local-staging.env \
COMPOSE_PROJECT_NAME=wave3pilotlocal docker compose \
  -f backend/docker/docker-compose.yml \
  -f backend/docker/docker-compose.staging.yml \
  -f backend/docker/docker-compose.tier-workers.yml \
  -f /tmp/hyrepath-wave3-local-service-images.yml \
  -f /tmp/hyrepath-wave3-local-good-images.yml \
  -f /tmp/hyrepath-wave3-local-ports.yml \
  --env-file /tmp/hyrepath-wave3-local-staging.env \
  up -d --no-build --scale worker=0 --scale worker-tier1=0 --scale worker-tier234=1
```

## Observed rollback outcomes

### Recovery to previous-version anchor

Observed running images after rollback:

- `api`: `hyrepath-local/api:6da855b`
- `worker-tier234`: `hyrepath-local/worker:6da855b`
- `worker-email`: `hyrepath-local/worker:6da855b`
- `worker-cleanup`: `hyrepath-local/worker:6da855b`

Observed live results after rollback:

- `/health` returned success
- `/ready` returned success
- `alembic current` reported `066_privileged_idempotency_records (head)`
- verified staff sync enrich: `200`, terminal status `completed`
- verified staff async enrich: `202` then `queued` -> `running` -> `completed`

This confirms the previous-version anchor could start against the same local
database shape and process queue-backed work successfully.

### Re-deploy confirmation back to current RC

After rollback verification, the stack was switched back to the current RC image set.

Observed running images after re-deploy:

- `api`: `hyrepath-local/api:85fa8f5`
- `worker-tier234`: `hyrepath-local/worker:85fa8f5`
- `worker-email`: `hyrepath-local/worker:85fa8f5`
- `worker-cleanup`: `hyrepath-local/worker:85fa8f5`

Observed live results after re-deploy:

- `/health` returned success
- `/ready` returned success
- `alembic current` remained `066_privileged_idempotency_records (head)`
- verified staff sync enrich: `200`, terminal status `completed`
- verified staff async enrich: `202` then `queued` -> `running` -> `completed`

## What was preserved

The approved rollback criteria were not faked:

- rollback was only claimed after a real current-RC local deployment succeeded
- previous-version recovery was only claimed after runnable anchor artifacts existed
- DB compatibility was checked both by no-Alembic-diff review and by live
  `alembic current` remaining at head across rollback and re-deploy
- queue/worker verification was demonstrated by successful async completion
- re-deploy confirmation was executed and verified

## Result

`ROLLBACK-LIVE-001` is now **PASS for a local-only rehearsal**.

This lowers local operational risk and proves a controlled image rollback path
for the local stack. It still does **not** satisfy the separate need for a true
remote environment rollback rehearsal with host provenance.

## Related evidence

- `docs/audits/multi-orch/evidence/pilot/PILOT-DEPLOY-001-local-only-2026-09-04.md`
- `docs/audits/multi-orch/evidence/pilot/PILOT-DEPLOY-001-2026-09-04.md`
