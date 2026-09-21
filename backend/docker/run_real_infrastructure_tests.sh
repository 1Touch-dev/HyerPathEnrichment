#!/bin/bash
# Foundation Week 1 real-infrastructure proof harness.
# Scope: base + foundation compose topology only (postgres, redis, api,
# worker-document, worker-embedding). This is not a Linux MLX / Tier 1 proof.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

ENV_FILE="${REAL_INFRA_ENV_FILE:-../.env.production}"
COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.foundation.yml)
SERVICES=(postgres redis migrate api worker-document worker-embedding)

echo -e "${CYAN}======================================================${NC}"
echo -e "${CYAN} Foundation Week 1 Real Infrastructure Harness        ${NC}"
echo -e "${CYAN} Uses real Postgres, Redis, OpenAI, and configured    ${NC}"
echo -e "${CYAN} document storage backend (R2 or local cache)         ${NC}"
echo -e "${CYAN}======================================================${NC}"
echo

if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}ERROR:${NC} Must run from backend/docker directory"
    echo "  cd backend/docker && ./run_real_infrastructure_tests.sh"
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}ERROR:${NC} Env file not found: $ENV_FILE"
    exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

POSTGRES_USER_EFFECTIVE="${POSTGRES_USER:-hyrepath}"
POSTGRES_DB_EFFECTIVE="${POSTGRES_DB:-hyrepath}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set in ${ENV_FILE}}"
TEST_DATABASE_URL="${TEST_DATABASE_URL:-postgresql+asyncpg://${POSTGRES_USER_EFFECTIVE}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB_EFFECTIVE}}"
TEST_REDIS_URL="${TEST_REDIS_URL:-redis://redis:6379/0}"

compose() {
    docker compose --env-file "$ENV_FILE" "${COMPOSE_FILES[@]}" "$@"
}

compose_exec() {
    local service=$1
    shift
    compose exec -T "$service" "$@"
}

wait_for_check() {
    local service=$1
    local label=$2
    local max_wait=$3
    shift 3

    local interval=5
    local elapsed=0
    echo -n "  Checking ${label}... "

    while [ "$elapsed" -lt "$max_wait" ]; do
        if "$@" >/dev/null 2>&1; then
            echo -e "${GREEN}OK${NC} (${elapsed}s)"
            return 0
        fi
        sleep "$interval"
        elapsed=$((elapsed + interval))
        echo -n "."
    done

    echo -e "${RED}TIMEOUT${NC} (>${max_wait}s)"
    echo "    Recent logs for ${service}:"
    compose logs --tail=20 "$service" | sed 's/^/    /'
    return 1
}

run_psql_scalar() {
    local sql=$1
    compose_exec postgres psql \
        -U "$POSTGRES_USER_EFFECTIVE" \
        -d "$POSTGRES_DB_EFFECTIVE" \
        -tAc "$sql" | xargs
}

echo -e "${BLUE}Phase 1: Infrastructure Startup${NC}"
echo "Starting services for the foundation real-infra topology..."
compose up -d --build "${SERVICES[@]}"
echo

wait_for_check postgres "Postgres + pgvector" 90 \
    compose_exec postgres bash -lc "pg_isready -U '$POSTGRES_USER_EFFECTIVE' -d '$POSTGRES_DB_EFFECTIVE' && psql -U '$POSTGRES_USER_EFFECTIVE' -d '$POSTGRES_DB_EFFECTIVE' -tAc \"SELECT 1 FROM pg_extension WHERE extname='vector'\" | grep -q 1"
wait_for_check redis "Redis ping" 45 \
    compose_exec redis redis-cli ping
wait_for_check api "API readiness" 120 \
    compose_exec api curl -fsS http://127.0.0.1:8000/ready
wait_for_check worker-document "document worker queue health" 60 \
    compose_exec worker-document python -c "from app.workers.tasks.document import check_worker_health; import sys; sys.exit(0 if check_worker_health('document_processing') else 1)"
wait_for_check worker-embedding "embedding worker queue health" 60 \
    compose_exec worker-embedding python -c "from app.workers.tasks.embedding import check_worker_health; import sys; sys.exit(0 if check_worker_health('embedding_generation') else 1)"

echo
echo -e "${GREEN}All required services are responding.${NC}"
echo

echo -e "${BLUE}Phase 2: Database + Settings Verification${NC}"
PGVECTOR_VERSION="$(run_psql_scalar "SELECT extversion FROM pg_extension WHERE extname='vector';")"
if [ -z "$PGVECTOR_VERSION" ]; then
    echo -e "${RED}FAIL:${NC} pgvector extension not loaded"
    exit 1
fi
echo "  pgvector version: $PGVECTOR_VERSION"

CANDIDATE_TABLE="$(run_psql_scalar "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='candidate_documents');")"
EMBEDDINGS_TABLE="$(run_psql_scalar "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='document_embeddings');")"
if [ "$CANDIDATE_TABLE" != "t" ] || [ "$EMBEDDINGS_TABLE" != "t" ]; then
    echo -e "${RED}FAIL:${NC} expected document tables missing"
    exit 1
fi
echo "  candidate_documents table: present"
echo "  document_embeddings table: present"

DOC_COUNT_BEFORE="$(run_psql_scalar "SELECT COUNT(*) FROM candidate_documents;")"
EMB_COUNT_BEFORE="$(run_psql_scalar "SELECT COUNT(*) FROM document_embeddings;")"
echo "  documents before tests: $DOC_COUNT_BEFORE"
echo "  embeddings before tests: $EMB_COUNT_BEFORE"

API_CONFIG="$(compose_exec api python - <<'PY'
from app.core.config import get_settings
from app.storage.r2 import r2_is_configured

s = get_settings()
print(
    "database_url="
    + s.database_url
    + ",redis_url="
    + s.redis_url
    + f",embeddings={s.enable_embeddings}"
    + f",document_storage_backend={'r2' if r2_is_configured(s) else 'local-cache'}"
    + f",openai_configured={bool(s.openai_api_key)}"
)
PY
)"
echo "  api settings: $API_CONFIG"

echo
echo -e "${YELLOW}WARNING:${NC} This run will use real infrastructure and may incur cost."
echo "  - Configured document storage writes (R2 if configured, local cache otherwise)"
echo "  - OpenAI embedding calls"
echo "  - PostgreSQL + Redis state changes"
echo
read -r -p "Continue? (yes/no): " REPLY
if [[ ! $REPLY =~ ^[Yy]([Ee][Ss])?$ ]]; then
    echo "Aborted."
    exit 0
fi

echo
echo -e "${BLUE}Phase 3: Running Target Integration Suite${NC}"
echo "  pytest plugin: tests.conftest_real_infrastructure"
echo "  TEST_DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER_EFFECTIVE}:***@postgres:5432/${POSTGRES_DB_EFFECTIVE}"
echo "  TEST_REDIS_URL: ${TEST_REDIS_URL}"
echo

TEST_EXIT_CODE=0
compose_exec api env \
    PYTEST_USE_REAL_INFRA=true \
    PYTHONPATH=/app/backend \
    TEST_DATABASE_URL="$TEST_DATABASE_URL" \
    TEST_REDIS_URL="$TEST_REDIS_URL" \
    python -m pytest \
    -p tests.conftest_real_infrastructure \
    tests/test_foundation_week1_integration.py \
    -v --tb=short --color=yes || TEST_EXIT_CODE=$?

echo
echo -e "${BLUE}Phase 4: Post-Test Snapshot${NC}"
DOC_COUNT_AFTER="$(run_psql_scalar "SELECT COUNT(*) FROM candidate_documents;")"
EMB_COUNT_AFTER="$(run_psql_scalar "SELECT COUNT(*) FROM document_embeddings;")"
echo "  documents after tests: $DOC_COUNT_AFTER (+$((DOC_COUNT_AFTER - DOC_COUNT_BEFORE)))"
echo "  embeddings after tests: $EMB_COUNT_AFTER (+$((EMB_COUNT_AFTER - EMB_COUNT_BEFORE)))"

echo
echo "  Recent document worker logs:"
compose logs --tail=20 worker-document | sed 's/^/    /'
echo
echo "  Recent embedding worker logs:"
compose logs --tail=20 worker-embedding | sed 's/^/    /'

echo
if [ "$TEST_EXIT_CODE" -eq 0 ]; then
    echo -e "${GREEN}ALL TARGET TESTS PASSED${NC}"
else
    echo -e "${RED}TARGET TESTS FAILED${NC}"
    echo "Troubleshooting hints:"
    echo "  - compose logs api"
    echo "  - compose logs worker-document"
    echo "  - compose logs worker-embedding"
fi

echo
echo "To stop the proof stack:"
echo "  docker compose --env-file $ENV_FILE ${COMPOSE_FILES[*]} down"

exit "$TEST_EXIT_CODE"
