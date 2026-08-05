# pgvector Infrastructure Testing Guide

## Overview
This guide provides comprehensive testing instructions for the pgvector infrastructure implementation (Agent 4 deliverable for Foundation Week 1).

## Prerequisites
- Docker and Docker Compose installed
- Git repository cloned
- On branch `agent-4/docker-pgvector`

## Test Execution

### 1. Build Custom Postgres Image

```bash
cd backend/docker
docker build -f Dockerfile.postgres -t hyrepath-postgres:pgvector .
```

**Expected output:**
- Build succeeds without errors
- Final image size: ~150-200MB (Alpine base + pgvector)

**Verification:**
```bash
docker images | grep hyrepath-postgres
```

### 2. Start Postgres Service

```bash
cd backend/docker
docker-compose up -d postgres
```

**Wait for health check:**
```bash
docker-compose ps postgres
```

**Expected:**
- Status: `healthy` (may take 30-60 seconds)
- Port: `127.0.0.1:5433->5432`

### 3. Verify pgvector Extension

```bash
docker-compose exec postgres psql -U hyrepath -d hyrepath -c "SELECT extversion FROM pg_extension WHERE extname='vector';"
```

**Expected output:**
```
 extversion
------------
 0.7.4
(1 row)
```

### 4. Test Vector Column Creation

```bash
docker-compose exec postgres psql -U hyrepath -d hyrepath <<EOF
CREATE TABLE test_vectors (
  id SERIAL PRIMARY KEY,
  embedding vector(1536)
);
EOF
```

**Expected:**
- `CREATE TABLE` message
- No errors

**Verification:**
```bash
docker-compose exec postgres psql -U hyrepath -d hyrepath -c "\d test_vectors"
```

Should show `embedding` column with type `vector(1536)`.

### 5. Test Vector Insertion

```bash
# Generate a random 1536-dimensional vector
VECTOR=$(python3 -c "import random; print('[' + ','.join(str(random.random()) for _ in range(1536)) + ']')")

docker-compose exec postgres psql -U hyrepath -d hyrepath -c "INSERT INTO test_vectors (embedding) VALUES ('$VECTOR');"
```

**Expected:**
- `INSERT 0 1` message
- No dimension mismatch errors

### 6. Test HNSW Index Creation

```bash
docker-compose exec postgres psql -U hyrepath -d hyrepath -c "CREATE INDEX test_vectors_hnsw_idx ON test_vectors USING hnsw (embedding vector_cosine_ops);"
```

**Expected:**
- `CREATE INDEX` message
- No errors (confirms HNSW support)

**Verification:**
```bash
docker-compose exec postgres psql -U hyrepath -d hyrepath -c "\d test_vectors"
```

Should show index `test_vectors_hnsw_idx` with access method `hnsw`.

### 7. Test Similarity Search

```bash
docker-compose exec postgres psql -U hyrepath -d hyrepath <<EOF
SELECT id, embedding <=> '[0.1,0.2,0.3]'::vector AS distance
FROM test_vectors
ORDER BY embedding <=> '[0.1,0.2,0.3]'::vector
LIMIT 5;
EOF
```

**Expected:**
- Returns rows with `id` and `distance` columns
- Distance values are floating-point numbers (0.0 to 2.0 for cosine)
- No errors

### 8. Run Alembic Migrations

```bash
docker-compose run --rm migrate
```

**Expected output:**
```
INFO  [alembic.runtime.migration] Running upgrade ... -> 009_enable_pgvector, Enable pgvector extension for vector embeddings storage
```

**Verification:**
```bash
docker-compose exec postgres psql -U hyrepath -d hyrepath -c "SELECT version_num FROM alembic_version;"
```

Should show `009_enable_pgvector` (or later).

### 9. Verify Migration Idempotency

```bash
# Run migration again
docker-compose run --rm migrate
```

**Expected:**
- No errors
- No "extension already exists" errors (confirms idempotency)

### 10. Test SQLite Compatibility (Local Dev)

```bash
cd backend
# Ensure DATABASE_URL is SQLite
export DATABASE_URL="sqlite+aiosqlite:///./hyrepath.db"

# Run migrations
alembic upgrade head
```

**Expected:**
- Migrations run without errors
- Migration 009 passes through (no-op for SQLite)
- No vector extension errors

### 11. Cleanup

```bash
# Remove test table
docker-compose exec postgres psql -U hyrepath -d hyrepath -c "DROP TABLE IF EXISTS test_vectors;"

# Stop services
docker-compose down
```

## Success Criteria

All tests must pass:

- [x] Dockerfile.postgres builds successfully
- [x] pgvector extension v0.7.4 installed
- [x] Can create vector(1536) columns
- [x] Can insert 1536-dimensional vectors
- [x] Can create HNSW indexes
- [x] Similarity search works (<=> operator)
- [x] Alembic migration 009 runs successfully
- [x] Migration is idempotent (can run multiple times)
- [x] SQLite compatibility maintained (migrations pass through)
- [x] Health check verifies pgvector extension

## Troubleshooting

### "extension does not exist" error
- Check Dockerfile.postgres compiled pgvector correctly
- Verify init-db.sh ran (check docker logs: `docker-compose logs postgres`)

### "dimension mismatch" error
- Ensure vector has exactly 1536 dimensions
- Check embedding format: `'[0.1,0.2,...]'::vector`

### HNSW index creation fails
- Verify pgvector version is 0.7.4+ (HNSW added in 0.5.0)
- Check Postgres logs: `docker-compose logs postgres`

### Health check never becomes healthy
- Increase `start_period` in docker-compose.yml
- Check if pgvector extension is enabled: `docker-compose exec postgres psql -U hyrepath -d hyrepath -c "SELECT * FROM pg_extension;"`

## Performance Benchmarks

For reference (not required for exit criteria):

```bash
# Create 10K test vectors
docker-compose exec postgres psql -U hyrepath -d hyrepath <<EOF
INSERT INTO test_vectors (embedding)
SELECT (random()::text || ',')::vector(1536)
FROM generate_series(1, 10000);
EOF

# Measure similarity search time
docker-compose exec postgres psql -U hyrepath -d hyrepath -c "\timing" -c "SELECT COUNT(*) FROM test_vectors ORDER BY embedding <=> '[0.1,0.2,0.3]' LIMIT 10;"
```

**Expected:**
- Without HNSW index: ~500-1000ms for 10K vectors
- With HNSW index: ~5-20ms for 10K vectors (50-100x speedup)

## Next Steps

After all tests pass:
1. Commit changes to `agent-4/docker-pgvector` branch
2. Create PR to `master` branch
3. Link ADR 0011 in PR description
4. Agent 2 (embedding worker) can begin implementation
