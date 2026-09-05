# ORCH-INFRA Wave 1 G1 Packet — 2026-09-04

Baseline carried forward:

- `G0` passed on baseline `R2-BASELINE-2026-09-04`
- branch `product-doors/baseline`
- HEAD `6da855b33b78f2cc8fa2cfa0fa18206e1570135f`
- recovery bundle `/tmp/dev-b-r2-baseline-R2-BASELINE-2026-09-04`

This packet prepares Wave 1 for ORCH-INFRA only. It does **not** claim live validation, owner approval, or certified environment access. All commands below are **deferred execution commands** for later authorized runs.

## Scope and ownership

Owned blockers in this run:

- `BLK-PG-001`
- `BLK-PILOT-001`
- Infra-owned portion of `BLK-T4-001`

Owned execution packets in this run:

- `PG-REHEARSAL-001`
- `PG-CONCURRENCY-001`
- `T4-ENV-001`
- `PILOT-DEPLOY-001`
- `ROLLBACK-LIVE-001`

Infra ownership remains exclusive on these surfaces:

- `backend/docker/*`
- `.github/workflows/deploy.yml`
- deployment and rollback env/secrets
- evidence packaging under `docs/audits/multi-orch/evidence/`

## Allowed status vocabulary used here

Task statuses in this packet use the plan vocabulary only:

- `READY`
- `READY AFTER GATE`
- `WAITING FOR OWNER DECISION`
- `WAITING FOR ENVIRONMENT`

Blocker statuses use the plan vocabulary only:

- `OPEN`
- `BLOCKED`

Evidence statuses use the plan vocabulary only:

- `EVIDENCE NOT STARTED`
- `PARTIAL`
- `READY FOR REVIEW`
- `APPROVED`
- `REJECTED`

## G1 decision and credential dependencies

### Required decisions outside Infra sole authority

| Decision / gate | Owner | Required reviewers | Blocks | Current status |
|---|---|---|---|---|
| `DEC-T4-SETUP` | Infra + QA | Security | `AUTH-SETUP-001`, `T4-LIVE-001` | `WAITING FOR OWNER DECISION` |
| `DEC-PILOT-ACCEPT` | Product + Infra | `ORCH-INFRA` | `PILOT-DEPLOY-001` | `WAITING FOR OWNER DECISION` |
| `DEC-ROLLBACK-ACCEPT` | Infra + Product | `ORCH-INFRA` | `ROLLBACK-LIVE-001` | `WAITING FOR OWNER DECISION` |
| `INFRA_TEST_DATABASE_URL_AND_COMPOSE_PASSWORD` | Infra human | `ORCH-INFRA` | `PG-REHEARSAL-001`, `PG-CONCURRENCY-001` | `WAITING FOR OWNER DECISION` |

### Environment facts that stay honest

- No certified PostgreSQL credentials are currently available.
- No live pilot environment is currently certified for this gate.
- No approved live `auth.setup` path exists yet for `T4`.
- `backend/.env.staging.example` and `backend/.env.production.example` are **not sufficient by themselves** for staging/production startup because `backend/app/core/config.py` requires at least `SECRET_KEY`, non-default `API_TOKEN`, `COOKIE_SECURE=true`, and `CHANGEDETECTION_API_KEY` in production-like environments.
- `PROMETHEUS_QUERY_URL` remains optional in code, but without it the pilot cannot claim monitoring-backed acceptance evidence.

## Readiness summary

### Blockers

| Blocker | Owner | Readiness status | Reason |
|---|---|---|---|
| `BLK-PG-001` | `ORCH-INFRA` | `BLOCKED` | No approved `TEST_DATABASE_URL` / compose password gate yet |
| `BLK-PILOT-001` | `ORCH-INFRA` + Product | `OPEN` | Deploy and rollback procedure defined, but no accepted live pilot env/evidence |
| Infra portion of `BLK-T4-001` | `ORCH-INFRA` + `ORCH-QA` | `BLOCKED` | Live API env can be defined, but `DEC-T4-SETUP` and non-prod-only control are still pending |

### Tasks

| Task | Owner | Readiness status | Evidence status | Notes |
|---|---|---|---|---|
| `PG-REHEARSAL-001` | `ORCH-INFRA` | `WAITING FOR ENVIRONMENT` | `EVIDENCE NOT STARTED` | Commands defined below; requires approved disposable PG credentials |
| `PG-CONCURRENCY-001` | `ORCH-INFRA` | `WAITING FOR ENVIRONMENT` | `EVIDENCE NOT STARTED` | Commands defined below; same credential gate as rehearsal |
| `T4-ENV-001` | `ORCH-INFRA` | `WAITING FOR ENVIRONMENT` | `EVIDENCE NOT STARTED` | Env packet ready, but cannot be treated as live T4 proof |
| `PILOT-DEPLOY-001` | `ORCH-INFRA` + Product | `WAITING FOR ENVIRONMENT` | `EVIDENCE NOT STARTED` | Also blocked by `DEC-PILOT-ACCEPT` |
| `ROLLBACK-LIVE-001` | `ORCH-INFRA` + Product | `WAITING FOR ENVIRONMENT` | `EVIDENCE NOT STARTED` | Also blocked by `DEC-ROLLBACK-ACCEPT` and DB restore point |

## Execution packets

### `BLK-PG-001` — PostgreSQL credentials, migration rehearsal, and concurrency

Blocker status: `BLOCKED`

Owned tasks:

- `PG-REHEARSAL-001`
- `PG-CONCURRENCY-001`

#### Shared prerequisites

Environment:

- Disposable non-production runner with Docker, Python, and repo checkout
- Repo root `/home/axiz/HyerPathEnrichment`
- Isolated Compose project name, not the operator's shared stack

Required secrets/config:

- `POSTGRES_PASSWORD` for the disposable compose Postgres
- `DATABASE_URL=postgresql+asyncpg://hyrepath:${POSTGRES_PASSWORD}@127.0.0.1:5433/hyrepath`
- `TEST_DATABASE_URL=postgresql+asyncpg://hyrepath:${POSTGRES_PASSWORD}@127.0.0.1:5433/hyrepath`
- Python dependencies installed for backend tests, including `psycopg`, `asyncpg`, and pytest extras

Evidence root:

- `docs/audits/multi-orch/evidence/pg/`

Reviewer gates:

- Execution agent: `INFRA-DB`
- Tester: `QA-PG-TEST`
- Reviewer: `INFRA-REVIEW`
- Handoff: `ORCH-ROOT`

Stop conditions:

- No approved `POSTGRES_PASSWORD`
- No approved `DATABASE_URL` / `TEST_DATABASE_URL`
- Attempt would target a shared or long-lived DB instead of a disposable environment
- Compose resolves blank `POSTGRES_PASSWORD`
- Alembic head is not `066_privileged_idempotency_records`
- Any migration or postgres-marked test fails

#### `PG-REHEARSAL-001`

Task status: `WAITING FOR ENVIRONMENT`

Evidence location:

- `docs/audits/multi-orch/evidence/pg/PG-REHEARSAL-001/`

Deferred execution commands:

```bash
export REPO=/home/axiz/HyerPathEnrichment
export COMPOSE_PROJECT_NAME=pg-rehearsal-001
export POSTGRES_PASSWORD='<set-by-infra-out-of-band>'
export DATABASE_URL="postgresql+asyncpg://hyrepath:${POSTGRES_PASSWORD}@127.0.0.1:5433/hyrepath"
export TEST_DATABASE_URL="$DATABASE_URL"

mkdir -p "$REPO/docs/audits/multi-orch/evidence/pg/PG-REHEARSAL-001"

cd "$REPO"
python3 -m venv backend/.venv
backend/.venv/bin/pip install -e "backend[dev]"

cd "$REPO/backend/docker"
docker compose --env-file ../.env config --quiet
docker compose --env-file ../.env up -d postgres
docker compose --env-file ../.env ps postgres \
  | tee "$REPO/docs/audits/multi-orch/evidence/pg/PG-REHEARSAL-001/compose-ps.txt"
docker compose --env-file ../.env exec postgres \
  psql -U hyrepath -d hyrepath -tAc "SHOW server_version" \
  | tee "$REPO/docs/audits/multi-orch/evidence/pg/PG-REHEARSAL-001/pg-version.txt"
docker compose --env-file ../.env exec postgres \
  psql -U hyrepath -d hyrepath -tAc "SELECT 1 FROM pg_extension WHERE extname='vector'" \
  | tee "$REPO/docs/audits/multi-orch/evidence/pg/PG-REHEARSAL-001/pgvector-check.txt"

cd "$REPO/backend"
DATABASE_URL="$DATABASE_URL" python3 -m alembic current \
  | tee "$REPO/docs/audits/multi-orch/evidence/pg/PG-REHEARSAL-001/alembic-before.txt"
DATABASE_URL="$DATABASE_URL" python3 -m alembic upgrade head \
  | tee "$REPO/docs/audits/multi-orch/evidence/pg/PG-REHEARSAL-001/alembic-upgrade-head.txt"
DATABASE_URL="$DATABASE_URL" python3 -m alembic current \
  | tee "$REPO/docs/audits/multi-orch/evidence/pg/PG-REHEARSAL-001/alembic-after-head.txt"
DATABASE_URL="$DATABASE_URL" python3 -m alembic downgrade 062_widen_auth_secret_fields \
  | tee "$REPO/docs/audits/multi-orch/evidence/pg/PG-REHEARSAL-001/alembic-downgrade-062.txt"
DATABASE_URL="$DATABASE_URL" python3 -m alembic upgrade head \
  | tee "$REPO/docs/audits/multi-orch/evidence/pg/PG-REHEARSAL-001/alembic-reupgrade-head.txt"
TEST_DATABASE_URL="$TEST_DATABASE_URL" python3 -m pytest tests/test_alembic_migrations.py -m postgres -q \
  | tee "$REPO/docs/audits/multi-orch/evidence/pg/PG-REHEARSAL-001/pytest-alembic-postgres.txt"
TEST_DATABASE_URL="$TEST_DATABASE_URL" python3 -m pytest tests/test_privileged_contract_migrations.py -m postgres -q \
  | tee "$REPO/docs/audits/multi-orch/evidence/pg/PG-REHEARSAL-001/pytest-privileged-migrations.txt"
docker compose --env-file ../.env exec postgres psql -U hyrepath -d hyrepath -tAc \
  "SELECT version_num FROM alembic_version" \
  | tee "$REPO/docs/audits/multi-orch/evidence/pg/PG-REHEARSAL-001/alembic-version-row.txt"
```

Exit evidence required:

- Postgres version and pgvector presence
- Alembic before/after showing head `066_privileged_idempotency_records`
- Downgrade to `062_widen_auth_secret_fields` and re-upgrade back to head
- Postgres migration pytest logs
- Integrity confirmation from `alembic_version`

#### `PG-CONCURRENCY-001`

Task status: `WAITING FOR ENVIRONMENT`

Evidence location:

- `docs/audits/multi-orch/evidence/pg/PG-CONCURRENCY-001/`

Deferred execution commands:

```bash
export REPO=/home/axiz/HyerPathEnrichment
export POSTGRES_PASSWORD='<set-by-infra-out-of-band>'
export TEST_DATABASE_URL="postgresql+asyncpg://hyrepath:${POSTGRES_PASSWORD}@127.0.0.1:5433/hyrepath"

mkdir -p "$REPO/docs/audits/multi-orch/evidence/pg/PG-CONCURRENCY-001"

cd "$REPO/backend"
TEST_DATABASE_URL="$TEST_DATABASE_URL" python3 -m pytest tests/test_admin_be_003_staff_invite_hardening.py -m postgres -q \
  | tee "$REPO/docs/audits/multi-orch/evidence/pg/PG-CONCURRENCY-001/pytest-admin-be-003-postgres.txt"
TEST_DATABASE_URL="$TEST_DATABASE_URL" python3 -m pytest tests/test_staff_invites.py -m postgres -q \
  | tee "$REPO/docs/audits/multi-orch/evidence/pg/PG-CONCURRENCY-001/pytest-staff-invites-postgres.txt"
TEST_DATABASE_URL="$TEST_DATABASE_URL" python3 -m pytest tests/test_db.py -m postgres -q \
  | tee "$REPO/docs/audits/multi-orch/evidence/pg/PG-CONCURRENCY-001/pytest-db-postgres.txt"
```

Exit evidence required:

- Staff-invite/idempotency postgres race coverage logs
- No duplicate privileged winner under concurrent redemption/reissue
- No replay secret leakage in persisted response bodies
- Infra reviewer summary for lock/race behavior

### Infra-owned portion of `BLK-T4-001` — live API environment for Playwright

Blocker status: `BLOCKED`

Owned task in this run:

- `T4-ENV-001`

Non-owned but blocking follow-ons:

- `AUTH-SETUP-001`
- `T4-LIVE-001`

Decision dependency:

- `DEC-T4-SETUP` must be approved by Infra + QA with Security review before any live auth-setup path is used.

Required environment:

- Non-production environment only
- Docker-backed API + Postgres + Redis + supporting sidecars
- Frontend dev server launched by Playwright

Required secrets/config:

- `POSTGRES_PASSWORD`
- backend runtime `API_TOKEN`
- `BACKEND_API_URL=http://localhost:8000`
- `BACKEND_API_TOKEN` matching backend `API_TOKEN`
- `FRONTEND_USE_MOCKS=false`
- `PLAYWRIGHT_PORT=3100` or another free local port
- dedicated integration identities:
  - `INTEGRATION_TEST_EMAIL`
  - `INTEGRATION_TEST_PASSWORD`
  - `INTEGRATION_ADMIN_TEST_EMAIL`
  - `INTEGRATION_ADMIN_TEST_PASSWORD`

Evidence location:

- `docs/audits/multi-orch/evidence/t4/T4-ENV-001/`

Reviewer gates:

- Env owner: `ORCH-INFRA`
- Receiving tester: `ORCH-QA`
- Decision reviewer for setup path: Security via `DEC-T4-SETUP`
- Read-only future cert reviewer: `ORCH-CERT`

Stop conditions:

- `APP_ENV` is `staging` or `production` for any auth-setup attempt
- `DEC-T4-SETUP` is not approved
- `scripts/create_test_user.py` would be used against a production-like environment
- `/health` or `/ready` fails
- Frontend points at mocks instead of the live backend

#### `T4-ENV-001`

Task status: `WAITING FOR ENVIRONMENT`

Deferred execution commands:

```bash
export REPO=/home/axiz/HyerPathEnrichment
export COMPOSE_PROJECT_NAME=t4-env-001
export POSTGRES_PASSWORD='<set-by-infra-out-of-band>'
export API_TOKEN='<set-by-infra-out-of-band>'

mkdir -p "$REPO/docs/audits/multi-orch/evidence/t4/T4-ENV-001"

cd "$REPO/backend/docker"
docker compose --env-file ../.env config --quiet
docker compose --env-file ../.env up -d api worker redis postgres social-analyzer google-maps-scraper email-verifier
docker compose --env-file ../.env ps \
  | tee "$REPO/docs/audits/multi-orch/evidence/t4/T4-ENV-001/compose-ps.txt"

curl -fsS http://127.0.0.1:8000/health \
  | tee "$REPO/docs/audits/multi-orch/evidence/t4/T4-ENV-001/health.json"
curl -fsS http://127.0.0.1:8000/ready \
  | tee "$REPO/docs/audits/multi-orch/evidence/t4/T4-ENV-001/ready.json"

cd "$REPO/frontend"
FRONTEND_USE_MOCKS=false \
BACKEND_API_URL=http://localhost:8000 \
BACKEND_API_TOKEN="$API_TOKEN" \
PLAYWRIGHT_PORT=3100 \
npx playwright test e2e/integration/connectivity.spec.ts --project integration \
  | tee "$REPO/docs/audits/multi-orch/evidence/t4/T4-ENV-001/playwright-connectivity.txt"
```

Exit evidence required:

- Compose services healthy
- `/health` and `/ready` returning 200 on the live API
- Playwright connectivity proof against live backend
- Explicit note that this is environment proof only, not final `T4-LIVE-001`
- Post-`DEC-T4-SETUP` live-suite execution remains a separate ORCH-QA handoff, not part of this task

### `BLK-PILOT-001` — pilot deploy and rollback packet

Blocker status: `OPEN`

Owned tasks:

- `PILOT-DEPLOY-001`
- `ROLLBACK-LIVE-001`

Shared prerequisites:

- G2-pinned RC SHA or image digest
- Named non-local pilot environment
- GitHub Environment secrets present for the chosen target
- Host-side `.env.staging` or `.env.production` supplemented with required prod-like values:
  - `SECRET_KEY`
  - non-default `API_TOKEN`
  - `COOKIE_SECURE=true`
  - `CHANGEDETECTION_API_KEY`
- Product acceptance packet approved
- Metrics/observability plan explicit; no config-only closure

Environment secrets/config required by `.github/workflows/deploy.yml`:

- `SSH_HOST`
- `SSH_USER`
- `SSH_KEY`
- optional `SSH_PORT`
- `GHCR_USERNAME`
- `GHCR_TOKEN`
- optional `DEPLOY_PATH`
- optional `COMPOSE_ENV_FILE`

Environment secrets/config required on host env file:

- `API_TOKEN`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `REDIS_URL`
- `SECRET_KEY`
- `COOKIE_SECURE=true`
- `CHANGEDETECTION_API_KEY`
- optional but strongly recommended: `METRICS_TOKEN`, `PROMETHEUS_QUERY_URL`, `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `SENTRY_RELEASE`

Evidence root:

- `docs/audits/multi-orch/evidence/pilot/`

Reviewer gates:

- Execution agent: `INFRA-RELEASE`
- Infra reviewer: `INFRA-REVIEW`
- Required human approvers: Product + Infra
- Handoff: `ORCH-ROOT`, `ORCH-QA`, later `ORCH-CERT`

Stop conditions:

- No RC SHA/image pinned after G2
- No named pilot host/environment
- Missing any required GitHub Environment secret
- Missing host env values required by production-like startup validation
- No Product acceptance
- No DB restore point before rollback rehearsal
- Monitoring unavailable and Product/Infra did not explicitly accept `INSUFFICIENT EVIDENCE`

#### `PILOT-DEPLOY-001`

Task status: `WAITING FOR ENVIRONMENT`

Additional decision dependency:

- `DEC-PILOT-ACCEPT`

Evidence location:

- `docs/audits/multi-orch/evidence/pilot/PILOT-DEPLOY-001/`

Deferred execution commands:

```bash
export REPO=/home/axiz/HyerPathEnrichment
export RC_SHA='<set-after-g2>'
export RC_REF='<remote-branch-or-tag-containing-the-pinned-rc>'
export PILOT_BASE_URL='https://<named-pilot-host>'

mkdir -p "$REPO/docs/audits/multi-orch/evidence/pilot/PILOT-DEPLOY-001"

cd "$REPO"
gh workflow run deploy.yml --ref "$RC_REF" -f target=staging -f dry_run=false \
  | tee "$REPO/docs/audits/multi-orch/evidence/pilot/PILOT-DEPLOY-001/deploy-dispatch.txt"
gh run list --workflow deploy.yml --limit 5 \
  | tee "$REPO/docs/audits/multi-orch/evidence/pilot/PILOT-DEPLOY-001/deploy-run-list.txt"
printf '%s\n' "$RC_SHA" \
  | tee "$REPO/docs/audits/multi-orch/evidence/pilot/PILOT-DEPLOY-001/rc-sha.txt"

curl -fsS "$PILOT_BASE_URL/ready" \
  | tee "$REPO/docs/audits/multi-orch/evidence/pilot/PILOT-DEPLOY-001/ready.json"
BASE_URL="$PILOT_BASE_URL" API_TOKEN='<pilot-api-token>' make smoke-prod \
  | tee "$REPO/docs/audits/multi-orch/evidence/pilot/PILOT-DEPLOY-001/make-smoke-prod.txt"
BASE_URL="$PILOT_BASE_URL" API_TOKEN='<pilot-api-token>' bash scripts/prod_full_acceptance.sh --prod \
  | tee "$REPO/docs/audits/multi-orch/evidence/pilot/PILOT-DEPLOY-001/prod-full-acceptance.txt"
```

Required human-verified checks after command execution:

- Product confirms accepted pilot scope and smoke coverage
- Infra confirms deploy target and env provenance
- If `PROMETHEUS_QUERY_URL` is present, export the monitoring evidence used for acceptance
- If `PROMETHEUS_QUERY_URL` is absent, record `INSUFFICIENT EVIDENCE` instead of closing the blocker

Exit evidence required:

- Dispatch record and resolved deploy run
- `/ready` success on live pilot host
- `make smoke-prod` result
- `prod_full_acceptance.sh --prod` result
- Product + Infra sign-off note stored under evidence root

#### `ROLLBACK-LIVE-001`

Task status: `WAITING FOR ENVIRONMENT`

Additional decision dependency:

- `DEC-ROLLBACK-ACCEPT`

Evidence location:

- `docs/audits/multi-orch/evidence/pilot/ROLLBACK-LIVE-001/`

Deferred execution commands:

```bash
export REPO=/home/axiz/HyerPathEnrichment
export GOOD_SHA='<last-known-good-sha>'
export PILOT_BASE_URL='https://<named-pilot-host>'
export API_IMAGE='ghcr.io/<owner>/<repo>/api'
export WORKER_IMAGE='ghcr.io/<owner>/<repo>/worker'

mkdir -p "$REPO/docs/audits/multi-orch/evidence/pilot/ROLLBACK-LIVE-001"

cd "$REPO"
printf '%s\n' "$GOOD_SHA" \
  | tee "$REPO/docs/audits/multi-orch/evidence/pilot/ROLLBACK-LIVE-001/good-sha.txt"

# Host-side commands, during an approved maintenance window only:
cat <<'EOF' > "$REPO/docs/audits/multi-orch/evidence/pilot/ROLLBACK-LIVE-001/host-rollback-commands.sh"
cd /opt/hyrepath/HyerPathEnrichment/backend/docker
{
  echo "services:"
  echo "  migrate:"
  echo "    image: ${API_IMAGE}:${GOOD_SHA}"
  echo "  api:"
  echo "    image: ${API_IMAGE}:${GOOD_SHA}"
  echo "  worker:"
  echo "    image: ${WORKER_IMAGE}:${GOOD_SHA}"
} > docker-compose.cd-images.yml

docker compose -f docker-compose.yml -f docker-compose.staging.yml -f docker-compose.cd-images.yml \
  --env-file ../.env.staging pull api worker migrate
docker compose -f docker-compose.yml -f docker-compose.staging.yml -f docker-compose.cd-images.yml \
  --env-file ../.env.staging up -d --no-build api worker redis postgres social-analyzer google-maps-scraper email-verifier
docker compose -f docker-compose.yml -f docker-compose.staging.yml -f docker-compose.cd-images.yml ps
EOF

curl -fsS "$PILOT_BASE_URL/ready" \
  | tee "$REPO/docs/audits/multi-orch/evidence/pilot/ROLLBACK-LIVE-001/post-rollback-ready.json"
BASE_URL="$PILOT_BASE_URL" API_TOKEN='<pilot-api-token>' make smoke-prod \
  | tee "$REPO/docs/audits/multi-orch/evidence/pilot/ROLLBACK-LIVE-001/post-rollback-smoke.txt"
```

Mandatory rollback guardrails:

- Do not run an older pre-hardening API binary against schema `065_staff_invite_security` or later.
- Treat migration failures as restore-from-backup incidents, not in-place schema downgrade.
- Require a DB restore point identifier before the rollback window opens.
- Require explicit maintenance window approval and operator acknowledgment of stop-the-world constraints.

Exit evidence required:

- Last known good SHA or image tag
- DB restore point identifier
- Host rollback command transcript
- Post-rollback `/ready` and smoke evidence
- Product + Infra rollback acceptance note

## Evidence packaging required for G1 readiness

Even before live execution, the following evidence stubs must exist conceptually and remain empty until a real run occurs:

- `docs/audits/multi-orch/evidence/pg/PG-REHEARSAL-001/`
- `docs/audits/multi-orch/evidence/pg/PG-CONCURRENCY-001/`
- `docs/audits/multi-orch/evidence/t4/T4-ENV-001/`
- `docs/audits/multi-orch/evidence/pilot/PILOT-DEPLOY-001/`
- `docs/audits/multi-orch/evidence/pilot/ROLLBACK-LIVE-001/`

Minimum reviewer artifacts expected after later execution:

- One Infra-written command transcript per task
- One tester summary for PG and T4 env consumption
- One reviewer note per task (`INFRA-REVIEW`, Security for `DEC-T4-SETUP`, Product+Infra for pilot/rollback)
- One owner decision record for each pending decision gate

## ORCH-INFRA concise G1 handoff

To `ORCH-ROOT`:

- Infra has defined exact deferred execution packets for `PG-REHEARSAL-001`, `PG-CONCURRENCY-001`, `T4-ENV-001`, `PILOT-DEPLOY-001`, and `ROLLBACK-LIVE-001`.
- G1 is **not yet reachable** from the Infra side because `DEC-T4-SETUP`, `DEC-PILOT-ACCEPT`, `DEC-ROLLBACK-ACCEPT`, and `INFRA_TEST_DATABASE_URL_AND_COMPOSE_PASSWORD` remain unresolved.
- No task may be promoted beyond `WAITING FOR ENVIRONMENT` or `WAITING FOR OWNER DECISION` on config inspection alone.

To receiving `ORCH-QA`:

- Consume `T4-ENV-001` only as environment proof.
- Do not run or bless `AUTH-SETUP-001` until `DEC-T4-SETUP` is explicitly approved with Security review.
- Planned live entrypoints are `frontend/e2e/integration/connectivity.spec.ts` and `frontend/e2e/integration/product-doors-t4.spec.ts`.

To receiving `ORCH-CERT`:

- Treat all Infra tracks as preparatory only.
- There is no blocker-closing evidence yet for PG, T4 live, pilot, or rollback.
- If live monitoring is absent, certification must treat pilot evidence as incomplete rather than inferred.
