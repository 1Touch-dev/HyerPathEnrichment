# Testing with Real Infrastructure

This guide explains how to test Foundation Week 1 with **real infrastructure as configured** (PostgreSQL, Redis, OpenAI, and the configured document storage backend).

## ⚠️ Important Warnings

- **This will cost money!** OpenAI API calls ~$0.01 per test run
- **Uses the configured document storage backend** - files go to Cloudflare R2 only when R2 credentials are configured; otherwise they use local `.asset-cache/`
- **Uses real PostgreSQL** - data will persist in the database
- **Not for CI/CD** - only for local/staging validation

## Prerequisites

1. **Docker & Docker Compose** installed and running
2. **`.env.production`** configured with:
   - PostgreSQL credentials
   - Redis URL
   - OpenAI API key (valid, with credits)
   - R2 credentials (Cloudflare) only if you specifically want real R2 coverage instead of the local cache fallback
3. **Port availability**:
   - 5432 (PostgreSQL)
   - 6379 (Redis)
   - 8000 (API)

## Quick Start

### Option 1: Automated Script (Recommended)

**Windows (PowerShell):**
```powershell
cd backend\docker
.\run_real_infrastructure_tests.ps1
```

**Linux/Mac/WSL (Bash):**
```bash
cd backend/docker
chmod +x run_real_infrastructure_tests.sh
./run_real_infrastructure_tests.sh
```

The script will:
1. Start all services (PostgreSQL, Redis, API, workers)
2. Verify infrastructure is healthy
3. Check pgvector extension
4. Run all 13 integration tests
5. Show cost usage and results
6. Display post-test statistics

### Option 2: Manual Steps

The commands below stay in `backend/docker` and use the same Compose services
as `run_real_infrastructure_tests.sh`.

1. **Start infrastructure:**
   ```bash
   cd backend/docker
   docker compose --env-file ../.env.production \
       -f docker-compose.yml \
       -f docker-compose.foundation.yml \
       up -d --build postgres redis migrate api worker-document worker-embedding
   ```

2. **Wait for services to be healthy** (60-90 seconds):
   ```bash
   docker compose --env-file ../.env.production \
       -f docker-compose.yml \
       -f docker-compose.foundation.yml \
       ps
   # postgres/redis/api/worker-document/worker-embedding should show "Up" or
   # "Up (healthy)"; migrate is a one-shot container and should exit 0 after success.
   ```

3. **Verify pgvector:**
   ```bash
   docker compose --env-file ../.env.production \
       -f docker-compose.yml \
       -f docker-compose.foundation.yml \
       exec -T postgres psql -U hyrepath -d hyrepath -c \
       "SELECT extversion FROM pg_extension WHERE extname='vector';"
   # Expected: 0.7.4 or newer
   ```

4. **Run tests:**
   ```bash
   set -a
   source ../.env.production
   set +a
   docker compose --env-file ../.env.production \
       -f docker-compose.yml \
       -f docker-compose.foundation.yml \
       exec -T api env \
       PYTEST_USE_REAL_INFRA=true \
       PYTHONPATH=/app/backend \
       TEST_DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER:-hyrepath}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-hyrepath}" \
       TEST_REDIS_URL="${TEST_REDIS_URL:-redis://redis:6379/0}" \
       python -m pytest -p tests.conftest_real_infrastructure \
       tests/test_foundation_week1_integration.py -v
   ```

5. **Check results:**
   ```bash
   # View worker logs
   docker compose --env-file ../.env.production \
       -f docker-compose.yml \
       -f docker-compose.foundation.yml \
       logs --tail 50 worker-document worker-embedding

   # Check database
   docker compose --env-file ../.env.production \
       -f docker-compose.yml \
       -f docker-compose.foundation.yml \
       exec -T postgres psql -U hyrepath -d hyrepath -c \
       "SELECT COUNT(*) FROM document_embeddings;"
   ```

6. **Stop services:**
   ```bash
   docker compose --env-file ../.env.production \
       -f docker-compose.yml \
       -f docker-compose.foundation.yml \
       down
   ```

## What Gets Tested

### Infrastructure Tests (✅ Should Pass)
1. File validation (size, type, corruption)
2. API health checks
3. Configuration loading
4. pgvector extension
5. Cost tracking enabled

### Integration Tests (✅ Should Pass with Real Services)
6. PDF upload → configured document storage backend
7. DOCX upload → configured document storage backend
8. Duplicate detection (SHA256 hash)
9. Text extraction & chunking
10. OpenAI embedding generation (1536 dimensions)
11. pgvector storage with HNSW index
12. Semantic search (cosine similarity)
13. End-to-end pipeline (upload → embeddings → search)

## Expected Results

### All 13 Tests Pass ✅

```
============================= test session starts ==============================
collected 13 items

test_foundation_week1_integration.py::TestDocumentUploadFlow::test_upload_pdf_complete_flow PASSED
test_foundation_week1_integration.py::TestDocumentUploadFlow::test_upload_docx_complete_flow PASSED
test_foundation_week1_integration.py::TestDocumentUploadFlow::test_duplicate_upload_detected PASSED
test_foundation_week1_integration.py::TestEmbeddingGeneration::test_embeddings_generated_after_upload PASSED
test_foundation_week1_integration.py::TestVectorSearch::test_semantic_search PASSED
test_foundation_week1_integration.py::TestVectorSearch::test_search_relevance PASSED
test_foundation_week1_integration.py::TestCVExtraction::test_cv_data_extraction PASSED
test_foundation_week1_integration.py::TestCVExtraction::test_cv_completeness_score PASSED
test_foundation_week1_integration.py::TestErrorHandling::test_malformed_pdf_rejected PASSED
test_foundation_week1_integration.py::TestErrorHandling::test_file_too_large_rejected PASSED
test_foundation_week1_integration.py::TestErrorHandling::test_invalid_file_type_rejected PASSED
test_foundation_week1_integration.py::TestCostMonitoring::test_cost_tracking_enabled PASSED
test_foundation_week1_integration.py::TestFullPipeline::test_complete_pipeline_e2e PASSED

============================== 13 passed in 45.23s ==============================
```

### Post-Test Statistics

```
Documents created: +3
Embeddings generated: +24 (1536 dimensions each)
OpenAI API calls: ~30 requests
Cost: $0.008 - $0.015
Document storage: +3 files (~200 KB, R2 only if configured)
```

## Troubleshooting

### Tests Fail: "Connection refused"

**Cause:** Services not fully started

**Fix:**
```bash
# Check service status
docker compose --env-file ../.env.production \
    -f docker-compose.yml \
    -f docker-compose.foundation.yml \
    ps

# View logs
docker compose --env-file ../.env.production \
    -f docker-compose.yml \
    -f docker-compose.foundation.yml \
    logs api worker-document

# Restart services
docker compose --env-file ../.env.production \
    -f docker-compose.yml \
    -f docker-compose.foundation.yml \
    down
docker compose --env-file ../.env.production \
    -f docker-compose.yml \
    -f docker-compose.foundation.yml \
    up -d --build postgres redis migrate api worker-document worker-embedding
```

### Tests Fail: "Failed to enqueue document"

**Cause:** Redis not connected or workers not running

**Fix:**
```bash
# Check Redis
docker compose --env-file ../.env.production \
    -f docker-compose.yml \
    -f docker-compose.foundation.yml \
    exec -T redis redis-cli ping
# Expected: PONG

# Check workers
docker compose --env-file ../.env.production \
    -f docker-compose.yml \
    -f docker-compose.foundation.yml \
    logs worker-document | grep "worker started"
docker compose --env-file ../.env.production \
    -f docker-compose.yml \
    -f docker-compose.foundation.yml \
    logs worker-embedding | grep "worker started"
```

### Tests Fail: "OpenAI API error"

**Cause:** Invalid API key or no credits

**Fix:**
1. Verify API key in `.env.production`
2. Check OpenAI dashboard for credits
3. Test API key:
   ```bash
   curl https://api.openai.com/v1/models \
       -H "Authorization: Bearer $OPENAI_API_KEY"
   ```

### Tests Fail: "pgvector extension not found"

**Cause:** Migration didn't run or Dockerfile.postgres issue

**Fix:**
```bash
# Check extension
docker compose --env-file ../.env.production \
    -f docker-compose.yml \
    -f docker-compose.foundation.yml \
    exec -T postgres psql -U hyrepath -d hyrepath -c \
    "SELECT * FROM pg_extension WHERE extname='vector';"

# If not found, rebuild postgres
docker compose --env-file ../.env.production \
    -f docker-compose.yml \
    -f docker-compose.foundation.yml \
    down -v  # WARNING: Deletes data!
docker compose --env-file ../.env.production \
    -f docker-compose.yml \
    -f docker-compose.foundation.yml \
    up -d --build postgres
```

### High Costs

**Cause:** Tests running repeatedly or large documents

**Fix:**
- Run tests max once per day
- Use smaller test documents
- Monitor OpenAI dashboard
- Set budget alerts at $500/day

## Cost Breakdown

| Item | Cost per Test Run | Monthly (30 runs) |
|------|------------------|-------------------|
| OpenAI embeddings | $0.008 - $0.015 | $0.24 - $0.45 |
| Object storage (R2 only if configured) | ~$0.0001 | $0.003 |
| Postgres (local) | Free | Free |
| Redis (local) | Free | Free |
| **Total** | **~$0.01** | **~$0.30** |

## Best Practices

1. **Run tests once per day maximum** - avoid burning API credits
2. **Use staging OpenAI project** - isolate test costs from production
3. **Clean up test data** - delete test documents after validation
4. **Monitor costs** - set up OpenAI usage alerts
5. **Use smaller fixtures** - 1-2 page CVs instead of 10-page resumes

## Comparison: Mock vs. Real Testing

| Aspect | Mock (Default) | Real Infrastructure |
|--------|---------------|---------------------|
| Speed | < 10s | 30-60s |
| Cost | $0 | ~$0.01 |
| Services | SQLite + FakeRedis | PostgreSQL + Redis |
| OpenAI | Mocked (random vectors) | Real API |
| Storage | Local `.asset-cache/` | Configured backend (R2 or local `.asset-cache/`) |
| Confidence | Validates logic | Validates integration against the configured storage backend |

**Recommendation**: Use mock tests for development/CI, real tests for pre-production validation.

## Next Steps After Passing

1. **Deploy to staging** - run same tests in staging environment
2. **Load testing** - test with 100+ concurrent uploads
3. **Cost monitoring** - set up alerts for $500/day threshold
4. **Performance tuning** - optimize pgvector HNSW index
5. **Production deployment** - merge to main and deploy

## Getting Help

If tests still fail after troubleshooting:

1. Check `PRODUCTION_CONFIG_TEST_RESULTS.md` for detailed test info
2. Review service logs: `docker compose logs --tail=100`
3. Verify `.env.production` has all required variables
4. Ensure Docker has enough resources (4GB RAM minimum)

---

**Last Updated**: Aug 4, 2026
**Test Environment**: Docker Compose (local)
**Expected Pass Rate**: 100% (13/13 tests)
