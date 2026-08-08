# Foundation Week 1 - Rollback & Recovery Guide

**Version**: 1.0
**Date**: 2026-08-04
**Status**: Production Ready

## Quick Rollback Commands

If Foundation Week 1 integration causes production issues:

```bash
# Option 1: Revert last merge (safest)
git checkout master
git revert HEAD --no-edit
git push origin master

# Option 2: Reset to specific agent tag
git checkout master
git reset --hard agent-1-merged  # or agent-4-merged, etc.
git push origin master --force  # Use with caution!

# Option 3: Full rollback to pre-foundation state
git checkout master
git reset --hard $(git merge-base master stage)
git push origin master --force
```

## Git Tags for Rollback

Each agent merge was tagged for easy rollback:

| Tag | Description | Includes |
|-----|-------------|----------|
| `agent-4-merged` | pgvector only | Postgres + pgvector extension |
| `agent-1-merged` | + Document worker | PDF/DOCX parsing, storage |
| `agent-3-merged` | + Chunking/CV extraction | Text chunking, CV extraction |
| `agent-5-merged` | + API routes | Document upload endpoints |
| `agent-2-merged` | + Embeddings (complete) | Embedding generation, search |

### Rollback to Specific Tag

```bash
# View available tags
git tag -l "agent-*-merged"

# Rollback to Agent 1 (removes Agent 2, 3, 5)
git checkout master
git reset --hard agent-1-merged
git push origin master --force
```

## Database Rollback

Foundation Week 1 added 3 migrations:

```
008_candidate_documents.py    - CandidateDocument table
009_enable_pgvector.py         - pgvector extension
010_document_embeddings.py     - DocumentEmbedding table (with HNSW index)
```

### Downgrade Migrations

```bash
cd backend

# Rollback all Foundation Week 1 migrations
alembic downgrade -1  # Downgrades 010
alembic downgrade -1  # Downgrades 009
alembic downgrade -1  # Downgrades 008

# Or rollback to specific revision
alembic downgrade 007  # Before Foundation Week 1
```

### Database Cleanup (if needed)

```sql
-- Manually drop tables if migration fails
DROP TABLE IF EXISTS document_embeddings CASCADE;
DROP TABLE IF EXISTS document_jobs CASCADE;
DROP TABLE IF EXISTS candidate_documents CASCADE;

-- Remove pgvector extension
DROP EXTENSION IF EXISTS vector;
```

## Docker Rollback

Foundation Week 1 added 2 new containers:

- `worker-document`
- `worker-embedding`

### Stop Foundation Containers

```bash
cd backend/docker

# Stop only foundation workers
docker-compose -f docker-compose.foundation.yml down

# Remove volumes (WARNING: deletes stored documents)
docker-compose -f docker-compose.foundation.yml down -v
```

### Revert Postgres Image

If pgvector causes issues:

```bash
# Edit docker-compose.yml
# Change:
#   image: hyrepath-postgres:pgvector
# To:
#   image: postgres:16-alpine

# Rebuild
docker-compose up -d postgres
```

## Environment Variables Rollback

Foundation Week 1 added these env vars:

```bash
ENABLE_EMBEDDINGS=true
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_DIMENSIONS=1536
CV_EXTRACTION_MODEL=gpt-4o-mini
DOCUMENT_UPLOAD_MAX_SIZE_MB=10
```

### Disable Foundation Features

```bash
# backend/.env
ENABLE_EMBEDDINGS=false
```

This disables embeddings without code changes.

## Queue Rollback

Foundation Week 1 added 3 queues:

- `document_processing`
- `embedding_generation`
- `cv_extraction`

### Clear Queues

```bash
# Redis CLI
redis-cli

# Clear foundation queues
DEL rq:queue:document_processing
DEL rq:queue:embedding_generation
DEL rq:queue:cv_extraction

# Or flush all queues (WARNING: affects all jobs)
FLUSHDB
```

## API Rollback

Foundation Week 1 added these endpoints:

```
POST /api/documents/upload
GET  /api/documents/jobs/{job_id}
POST /api/documents/search
GET  /api/documents/{id}/cv-data
GET  /api/documents
```

### Disable API Routes

```python
# backend/app/main.py
# Comment out:
# from app.modules.documents.router import router as documents_router
# app.include_router(documents_router, prefix="/api/documents", tags=["documents"])
```

Or use feature flag:

```python
if get_settings().enable_embeddings:
    app.include_router(documents_router)
```

## Verification After Rollback

After rollback, verify system health:

```bash
# 1. Check API health
curl http://localhost:8000/health

# 2. Check database
psql -h localhost -U hyrepath -d hyrepath -c "\dt"

# 3. Check Redis queues
redis-cli KEYS "rq:queue:*"

# 4. Check Docker containers
docker ps

# 5. Run smoke tests
cd backend
pytest tests/test_health.py -v
```

## Partial Rollback Options

### Keep pgvector, Remove Workers

```bash
# Stop workers only
docker-compose -f docker-compose.foundation.yml stop worker-document worker-embedding

# Keep Postgres with pgvector for future use
```

### Keep Database, Disable API

```python
# backend/app/core/config.py
ENABLE_EMBEDDINGS: bool = False
```

This keeps data but disables document upload endpoints.

### Keep Everything, Clear Data

```sql
-- Clear all uploaded documents (keeps tables)
TRUNCATE TABLE document_embeddings CASCADE;
TRUNCATE TABLE document_jobs CASCADE;
TRUNCATE TABLE candidate_documents CASCADE;
```

## Data Backup Before Rollback

Always backup before rolling back:

```bash
# Backup database
pg_dump -h localhost -U hyrepath hyrepath > backup_before_rollback.sql

# Backup Redis
redis-cli --rdb backup_redis.rdb

# Backup document storage (if using local storage)
tar -czf documents_backup.tar.gz backend/.asset-cache/
```

## Recovery After Rollback

If you need to re-apply Foundation Week 1:

```bash
# 1. Restore git state
git checkout master
git pull origin master

# 2. Re-run migrations
cd backend
alembic upgrade head

# 3. Restart containers
docker-compose -f docker-compose.yml -f docker-compose.foundation.yml up -d

# 4. Verify
curl http://localhost:8000/health
```

## Known Issues & Workarounds

### Issue 1: pgvector Extension Conflict

**Symptom**: `ERROR: extension "vector" already exists`

**Fix**:
```sql
DROP EXTENSION IF EXISTS vector CASCADE;
-- Then re-run migration
alembic upgrade head
```

### Issue 2: Worker Can't Connect to Redis

**Symptom**: `ConnectionRefusedError: [Errno 111]`

**Fix**:
```bash
# Check Redis is running
docker-compose ps redis

# Restart Redis
docker-compose restart redis
```

### Issue 3: OpenAI Rate Limit

**Symptom**: `RateLimitError: Rate limit exceeded`

**Fix**:
```bash
# Pause embedding worker
docker-compose stop worker-embedding

# Clear embedding queue
redis-cli DEL rq:queue:embedding_generation

# Restart after rate limit window
docker-compose start worker-embedding
```

### Issue 4: Storage Path Not Found

**Symptom**: `FileNotFoundError: .asset-cache`

**Fix**:
```bash
# Create storage directory
mkdir -p backend/.asset-cache
chmod 755 backend/.asset-cache
```

## Emergency Contacts

If rollback fails:

1. Check `#incidents` Slack channel
2. Page on-call engineer: `@oncall-backend`
3. Escalate to Tech Lead: @tech-lead

## Rollback Decision Matrix

| Severity | Action | Timeline |
|----------|--------|----------|
| P0 (Production down) | Full rollback immediately | < 5 min |
| P1 (Feature broken) | Partial rollback, keep infra | < 15 min |
| P2 (Performance degraded) | Disable features, investigate | < 1 hour |
| P3 (Minor issues) | Hot-fix, no rollback | Next sprint |

## Post-Rollback Checklist

- [ ] All services running (`docker ps`)
- [ ] API health check passes (`/health`)
- [ ] Database schema verified (`\dt`)
- [ ] Queues cleared/stable
- [ ] No error spikes in logs
- [ ] Monitoring dashboards green
- [ ] Incident report filed
- [ ] Team notified on Slack
- [ ] Postmortem scheduled

## Testing Rollback (Staging)

Before production rollback, test on staging:

```bash
# 1. Deploy Foundation Week 1 to staging
git push staging master

# 2. Generate load
python scripts/load_test.py

# 3. Practice rollback
git checkout master
git revert HEAD
git push staging master --force

# 4. Verify staging healthy
./scripts/smoke_test.sh staging
```

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-08-04 | Initial rollback guide for Foundation Week 1 |

---

**Last Updated**: 2026-08-04
**Owner**: Backend Team
**Review Cycle**: Quarterly
