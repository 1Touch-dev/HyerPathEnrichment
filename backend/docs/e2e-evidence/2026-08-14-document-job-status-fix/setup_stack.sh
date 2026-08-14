#!/usr/bin/env bash
# Chunk 4 e2e evidence: bring up real Postgres + Redis (docker-compose),
# run real alembic migrations, start a real uvicorn process and a real RQ
# worker process for the document_processing queue.
#
# Run from WSL2 Ubuntu with Docker Engine. See README.md in this folder for
# the full narrative / results.
set -uo pipefail

REPO=/mnt/g/ThunderMarketingCorp/HyerEnrichment
BACKEND=$REPO/backend
DOCKER_DIR=$BACKEND/docker
VENV=$HOME/hyre-e2e-venv

echo "=== [1/7] tearing down any pre-existing 'docker' compose project (clean slate) ==="
cd "$DOCKER_DIR"
docker compose -f docker-compose.yml down -v --remove-orphans || true

echo "=== [2/7] bringing up Postgres + Redis via docker-compose ==="
docker compose --env-file "$BACKEND/.env.production" -f docker-compose.yml up -d postgres redis

echo "=== waiting for postgres+redis health ==="
for i in $(seq 1 40); do
  pg=$(docker inspect --format='{{.State.Health.Status}}' docker-postgres-1 2>/dev/null || echo "starting")
  rd=$(docker inspect --format='{{.State.Health.Status}}' docker-redis-1 2>/dev/null || echo "starting")
  echo "  [$i] postgres=$pg redis=$rd"
  if [ "$pg" = "healthy" ] && [ "$rd" = "healthy" ]; then break; fi
  sleep 3
done
docker compose -f docker-compose.yml ps

echo "=== [3/7] creating Python venv on native ext4 (not /mnt/g, for speed) ==="
if [ ! -d "$VENV" ]; then
  python3 -m venv "$VENV"
fi
source "$VENV/bin/activate"
pip install --upgrade pip -q
pip install -e "$BACKEND" -q
echo "venv ready: $(python3 --version)"

echo "=== [4/7] loading backend/.env.production for POSTGRES_USER/PASSWORD/API_TOKEN (values never echoed) ==="
# .env.production is CRLF (Windows-authored); source a CRLF-stripped copy so
# bash doesn't choke on trailing \r in each value. Never echoed below.
ENV_PROD_CLEAN=$(mktemp)
tr -d '\r' < "$BACKEND/.env.production" > "$ENV_PROD_CLEAN"
set -a
# shellcheck disable=SC1091
source "$ENV_PROD_CLEAN"
set +a
rm -f "$ENV_PROD_CLEAN"
export DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5433/hyrepath"
export REDIS_URL="redis://localhost:6379/0"
export EMAIL_ENABLED=false
export EMAIL_TEST_MODE=true
export FRONTEND_URL=http://localhost:3000
export APP_ENV=e2e-test

echo "=== [5/7] alembic upgrade head (real Postgres migration) ==="
cd "$BACKEND"
alembic upgrade head
alembic current

echo "=== [6/7] starting real uvicorn (background) ==="
nohup "$VENV/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8000 --app-dir "$BACKEND" \
  > "$HOME/hyre-e2e-uvicorn.log" 2>&1 &
echo $! > "$HOME/hyre-e2e-uvicorn.pid"
echo "uvicorn pid=$(cat $HOME/hyre-e2e-uvicorn.pid)"

echo "=== waiting for API health ==="
for i in $(seq 1 30); do
  code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health || true)
  echo "  [$i] health=$code"
  [ "$code" = "200" ] && break
  sleep 2
done

echo "=== [7/7] starting real RQ worker for the document_processing queue (background) ==="
nohup "$VENV/bin/rq" worker document_processing --url redis://localhost:6379/0 \
  > "$HOME/hyre-e2e-worker.log" 2>&1 &
echo $! > "$HOME/hyre-e2e-worker.pid"
echo "worker pid=$(cat $HOME/hyre-e2e-worker.pid)"
sleep 3

echo "=== setup complete ==="
