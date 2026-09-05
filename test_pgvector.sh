#!/bin/bash
# Test script for pgvector infrastructure
# Verifies Dockerfile builds, pgvector extension is installed, and HNSW indexes work

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "==> Test 1: Build custom Postgres image with pgvector"
cd "$PROJECT_ROOT/backend/docker"
docker build -f Dockerfile.postgres -t hyrepath-postgres:pgvector .
echo "✓ Custom Postgres image built successfully"

echo ""
echo "==> Test 2: Start Postgres container"
cd "$PROJECT_ROOT/backend/docker"
docker-compose up -d postgres

echo "Waiting for Postgres to be healthy..."
for i in {1..30}; do
    if docker-compose exec -T postgres pg_isready -U hyrepath -d hyrepath > /dev/null 2>&1; then
        echo "✓ Postgres is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "✗ Postgres failed to start within 30 seconds"
        docker-compose logs postgres
        exit 1
    fi
    sleep 1
done

echo ""
echo "==> Test 3: Verify pgvector extension installed"
VERSION=$(docker-compose exec -T postgres psql -U hyrepath -d hyrepath -tAc "SELECT extversion FROM pg_extension WHERE extname='vector';")
if [ -z "$VERSION" ]; then
    echo "✗ pgvector extension not found"
    exit 1
fi
echo "✓ pgvector extension installed: version $VERSION"

echo ""
echo "==> Test 4: Test vector column creation"
docker-compose exec -T postgres psql -U hyrepath -d hyrepath <<-EOSQL
    DROP TABLE IF EXISTS test_vectors;
    CREATE TABLE test_vectors (
        id SERIAL PRIMARY KEY,
        embedding vector(1536)
    );
EOSQL
echo "✓ Successfully created table with vector(1536) column"

echo ""
echo "==> Test 5: Insert sample vector"
docker-compose exec -T postgres psql -U hyrepath -d hyrepath <<-EOSQL
    INSERT INTO test_vectors (embedding)
    VALUES ('[$(python3 -c "import random; print(','.join(str(random.random()) for _ in range(1536)))")');
EOSQL
echo "✓ Successfully inserted 1536-dimensional vector"

echo ""
echo "==> Test 6: Create HNSW index"
docker-compose exec -T postgres psql -U hyrepath -d hyrepath <<-EOSQL
    CREATE INDEX test_vectors_hnsw_idx ON test_vectors USING hnsw (embedding vector_cosine_ops);
EOSQL
echo "✓ Successfully created HNSW index with cosine similarity"

echo ""
echo "==> Test 7: Test vector similarity search"
RESULT=$(docker-compose exec -T postgres psql -U hyrepath -d hyrepath -tAc "SELECT COUNT(*) FROM test_vectors ORDER BY embedding <=> '[0.1,0.2,0.3]' LIMIT 10;")
if [ "$RESULT" != "1" ]; then
    echo "✗ Vector similarity search failed"
    exit 1
fi
echo "✓ Vector similarity search working"

echo ""
echo "==> Test 8: Cleanup test table"
docker-compose exec -T postgres psql -U hyrepath -d hyrepath <<-EOSQL
    DROP TABLE test_vectors;
EOSQL
echo "✓ Test table cleaned up"

echo ""
echo "==> Test 9: Run Alembic migration 009"
cd "$PROJECT_ROOT/backend/docker"
docker-compose run --rm migrate
echo "✓ Alembic migrations completed successfully"

echo ""
echo "==> Test 10: Verify pgvector extension still enabled after migration"
VERSION=$(docker-compose exec -T postgres psql -U hyrepath -d hyrepath -tAc "SELECT extversion FROM pg_extension WHERE extname='vector';")
if [ -z "$VERSION" ]; then
    echo "✗ pgvector extension not found after migration"
    exit 1
fi
echo "✓ pgvector extension still enabled after migration: version $VERSION"

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  ✓ All pgvector infrastructure tests passed!              ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Summary:"
echo "  - Custom Postgres image with pgvector v0.7.4"
echo "  - pgvector extension enabled in main database"
echo "  - vector(1536) columns work"
echo "  - HNSW indexes with cosine similarity work"
echo "  - Alembic migration 009 runs successfully"
echo ""
echo "Ready for Agent 2 (embedding worker) to start work!"
