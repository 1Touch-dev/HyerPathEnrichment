#!/bin/bash
# Foundation Week 1 - Real Infrastructure Testing Script
# This script tests with REAL services: PostgreSQL, Redis, R2, OpenAI
# ⚠️  WARNING: This will incur real costs (~$0.01 per run)

set -e  # Exit on error

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  Foundation Week 1 - Real Infrastructure Tests      ║${NC}"
echo -e "${CYAN}║  ⚠️  Uses REAL services & incurs costs               ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# Check we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}ERROR: Must run from backend/docker directory${NC}"
    echo "cd backend/docker && ./run_real_infrastructure_tests.sh"
    exit 1
fi

# Load production config
if [ ! -f "../.env.production" ]; then
    echo -e "${RED}ERROR: .env.production not found${NC}"
    exit 1
fi

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Phase 1: Infrastructure Startup${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Start all foundation services
echo "Starting services (this may take 60-90 seconds)..."
docker compose --env-file ../.env.production \
    -f docker-compose.yml \
    -f docker-compose.foundation.yml \
    up -d --build

echo ""
echo "Waiting for services to be healthy..."

# Function to check service health
check_service() {
    local service=$1
    local max_wait=$2
    local interval=5
    local elapsed=0

    echo -n "  Checking ${service}... "

    while [ $elapsed -lt $max_wait ]; do
        if docker compose ps | grep "$service" | grep -q "Up (healthy)"; then
            echo -e "${GREEN}OK${NC} (${elapsed}s)"
            return 0
        elif docker compose ps | grep "$service" | grep -q "unhealthy"; then
            echo -e "${RED}UNHEALTHY${NC}"
            echo "    Logs:"
            docker compose logs --tail=20 "$service" | sed 's/^/    /'
            return 1
        fi
        sleep $interval
        elapsed=$((elapsed + interval))
        echo -n "."
    done

    echo -e "${RED}TIMEOUT${NC} (>${max_wait}s)"
    return 1
}

# Check critical services
check_service "hyer-postgres" 60 || exit 1
check_service "hyer-redis" 30 || exit 1
check_service "hyer-api" 90 || exit 1
check_service "hyer-worker-document" 45 || exit 1
check_service "hyer-worker-embedding" 45 || exit 1

echo ""
echo -e "${GREEN}✓${NC} All services are healthy!"

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Phase 2: Database & Extension Verification${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Check pgvector extension
echo -n "  Checking pgvector extension... "
PGVECTOR_VERSION=$(docker exec hyer-postgres psql -U hyrepath -d hyrepath -t -c \
    "SELECT extversion FROM pg_extension WHERE extname='vector';" 2>/dev/null | xargs)

if [ -n "$PGVECTOR_VERSION" ]; then
    echo -e "${GREEN}OK${NC} (version: $PGVECTOR_VERSION)"
else
    echo -e "${RED}FAIL${NC} - pgvector extension not loaded!"
    exit 1
fi

# Check tables exist
echo -n "  Checking candidate_documents table... "
TABLE_EXISTS=$(docker exec hyer-postgres psql -U hyrepath -d hyrepath -t -c \
    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='candidate_documents');" 2>/dev/null | xargs)

if [ "$TABLE_EXISTS" = "t" ]; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAIL${NC} - table not found!"
    exit 1
fi

echo -n "  Checking document_embeddings table... "
TABLE_EXISTS=$(docker exec hyer-postgres psql -U hyrepath -d hyrepath -t -c \
    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='document_embeddings');" 2>/dev/null | xargs)

if [ "$TABLE_EXISTS" = "t" ]; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAIL${NC} - table not found!"
    exit 1
fi

# Get baseline counts
DOC_COUNT_BEFORE=$(docker exec hyer-postgres psql -U hyrepath -d hyrepath -t -c \
    "SELECT COUNT(*) FROM candidate_documents;" 2>/dev/null | xargs)
EMB_COUNT_BEFORE=$(docker exec hyer-postgres psql -U hyrepath -d hyrepath -t -c \
    "SELECT COUNT(*) FROM document_embeddings;" 2>/dev/null | xargs)

echo "  Current documents: $DOC_COUNT_BEFORE"
echo "  Current embeddings: $EMB_COUNT_BEFORE"

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Phase 3: Configuration Validation${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Check API can read config
echo "  Fetching API config..."
API_HEALTH=$(docker exec hyer-api python -c \
    "from app.core.config import get_settings; s=get_settings(); print(f'embeddings={s.enable_embeddings},r2={s.r2_enabled},model={s.openai_embedding_model}')" 2>/dev/null)

echo "    $API_HEALTH"

if echo "$API_HEALTH" | grep -q "embeddings=True"; then
    echo -e "  ${GREEN}✓${NC} Embeddings enabled"
else
    echo -e "  ${RED}✗${NC} Embeddings NOT enabled!"
    exit 1
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Phase 4: Worker Health Check${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo "  Checking RQ workers..."
WORKER_DOC_LOG=$(docker logs hyer-worker-document --tail 5 2>&1 | grep -i "worker started\|listening" || echo "")
WORKER_EMB_LOG=$(docker logs hyer-worker-embedding --tail 5 2>&1 | grep -i "worker started\|listening" || echo "")

if [ -n "$WORKER_DOC_LOG" ]; then
    echo -e "  ${GREEN}✓${NC} Document worker listening"
else
    echo -e "  ${YELLOW}⚠${NC}  Document worker status unclear (check logs)"
fi

if [ -n "$WORKER_EMB_LOG" ]; then
    echo -e "  ${GREEN}✓${NC} Embedding worker listening"
else
    echo -e "  ${YELLOW}⚠${NC}  Embedding worker status unclear (check logs)"
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Phase 5: Cost Tracking Baseline${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo "  Recording baseline costs..."
COST_BEFORE=$(curl -s http://localhost:8000/api/admin/costs 2>/dev/null | grep -o '"total_usd":[0-9.]*' | head -1 | cut -d':' -f2 || echo "0")
echo "  Starting cost: \$${COST_BEFORE}"

echo ""
echo -e "${YELLOW}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║  ⚠️  ABOUT TO RUN TESTS WITH REAL INFRASTRUCTURE    ║${NC}"
echo -e "${YELLOW}║                                                      ║${NC}"
echo -e "${YELLOW}║  This will:                                          ║${NC}"
echo -e "${YELLOW}║  • Upload documents to R2 (cloud storage)            ║${NC}"
echo -e "${YELLOW}║  • Call OpenAI API for embeddings (~\$0.01)          ║${NC}"
echo -e "${YELLOW}║  • Store data in PostgreSQL                          ║${NC}"
echo -e "${YELLOW}║                                                      ║${NC}"
echo -e "${YELLOW}║  Expected cost: ~\$0.01 per test run                 ║${NC}"
echo -e "${YELLOW}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
read -p "Continue? (yes/no): " -r
if [[ ! $REPLY =~ ^[Yy]([Ee][Ss])?$ ]]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Phase 6: Running Integration Tests${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

cd ..

# Use the real infrastructure conftest
export PYTEST_CONFTEST="conftest_real_infrastructure.py"

# Run tests with real infrastructure
echo "Running tests (this may take 2-5 minutes)..."
echo ""

docker exec hyer-api bash -c "cd /app/backend && \
    export PYTHONPATH=/app/backend && \
    python -m pytest tests/test_foundation_week1_integration.py \
    --confcutdir=tests \
    --override-ini='python_files=conftest_real_infrastructure.py test_*.py' \
    -v --tb=short --color=yes" || TEST_EXIT_CODE=$?

cd docker

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Phase 7: Post-Test Verification${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Get final counts
DOC_COUNT_AFTER=$(docker exec hyer-postgres psql -U hyrepath -d hyrepath -t -c \
    "SELECT COUNT(*) FROM candidate_documents;" 2>/dev/null | xargs)
EMB_COUNT_AFTER=$(docker exec hyer-postgres psql -U hyrepath -d hyrepath -t -c \
    "SELECT COUNT(*) FROM document_embeddings;" 2>/dev/null | xargs)

echo "  Documents after tests: $DOC_COUNT_AFTER (+$((DOC_COUNT_AFTER - DOC_COUNT_BEFORE)))"
echo "  Embeddings after tests: $EMB_COUNT_AFTER (+$((EMB_COUNT_AFTER - EMB_COUNT_BEFORE)))"

# Check embedding dimensions
if [ "$EMB_COUNT_AFTER" -gt 0 ]; then
    AVG_DIM=$(docker exec hyer-postgres psql -U hyrepath -d hyrepath -t -c \
        "SELECT AVG(array_length(embedding, 1)) FROM document_embeddings;" 2>/dev/null | xargs)
    echo "  Average embedding dimensions: $AVG_DIM"

    if [ "${AVG_DIM%.*}" = "1536" ]; then
        echo -e "  ${GREEN}✓${NC} Embeddings have correct dimensions (1536)"
    else
        echo -e "  ${YELLOW}⚠${NC}  Unexpected embedding dimensions (expected 1536)"
    fi
fi

# Final cost
COST_AFTER=$(curl -s http://localhost:8000/api/admin/costs 2>/dev/null | grep -o '"total_usd":[0-9.]*' | head -1 | cut -d':' -f2 || echo "0")
echo "  Ending cost: \$${COST_AFTER}"

if [ "$COST_AFTER" != "0" ] && [ "$COST_BEFORE" != "0" ]; then
    TEST_COST=$(echo "$COST_AFTER - $COST_BEFORE" | bc 2>/dev/null || echo "unknown")
    echo "  Test run cost: \$${TEST_COST}"

    if [ "$TEST_COST" != "unknown" ]; then
        COST_CHECK=$(echo "$TEST_COST > 0.50" | bc -l 2>/dev/null || echo "0")
        if [ "$COST_CHECK" = "1" ]; then
            echo -e "  ${YELLOW}⚠${NC}  Cost higher than expected (\$${TEST_COST} > \$0.50)"
        else
            echo -e "  ${GREEN}✓${NC} Cost within expected range"
        fi
    fi
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Phase 8: Service Logs (Last 20 lines)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo ""
echo "  Document Worker Logs:"
docker logs hyer-worker-document --tail 20 2>&1 | sed 's/^/    /'

echo ""
echo "  Embedding Worker Logs:"
docker logs hyer-worker-embedding --tail 20 2>&1 | sed 's/^/    /'

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║              Test Execution Complete                 ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

if [ "${TEST_EXIT_CODE:-0}" -eq 0 ]; then
    echo -e "${GREEN}✓ ALL TESTS PASSED${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Review cost usage in OpenAI dashboard"
    echo "  2. Verify R2 bucket contents"
    echo "  3. Check pgvector search performance"
else
    echo -e "${RED}✗ SOME TESTS FAILED${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Check worker logs: docker logs hyer-worker-document"
    echo "  2. Check API logs: docker logs hyer-api"
    echo "  3. Verify OpenAI API key is valid"
    echo "  4. Check R2 credentials"
fi

echo ""
echo "To stop all services:"
echo "  docker compose -f docker-compose.yml -f docker-compose.foundation.yml down"
echo ""

exit ${TEST_EXIT_CODE:-0}
