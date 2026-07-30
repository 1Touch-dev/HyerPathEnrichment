# Troubleshooting Guide

Quick diagnostic reference for common Hyrepath Enrichment issues. For detailed operational procedures, see [OPS.md](OPS.md), [ALERTING.md](ALERTING.md), and [backend/docs/TESTING_TIER234.md](../backend/docs/TESTING_TIER234.md).

---

## 1. API Issues

### Problem: GET /health returns 503

**Cause:** Postgres or Redis unreachable, or database migration failed on startup.

**Solution:**

```bash
# Check all services are running
docker ps

# Inspect specific service logs
docker logs hyrepath-api
docker logs hyrepath-postgres
docker logs hyrepath-redis

# Verify database connectivity from API container
docker exec hyrepath-api psql $DATABASE_URL -c "SELECT 1"

# Check Redis connectivity
docker exec hyrepath-api redis-cli -u $REDIS_URL ping

# Restart failed service
docker compose -f backend/docker/docker-compose.yml \
  -f backend/docker/docker-compose.prod.yml \
  restart postgres redis api
```

**Related:** If Alembic migrations failed, check `docker logs hyrepath-api` for `sqlalchemy.exc` errors. Restore from backup rather than downgrading schema. See [OPS.md § Rollback](OPS.md#rollback).

---

### Problem: Jobs stuck in "queued" status

**Cause:** No workers running, Redis disconnected, or worker crashed during startup.

**Solution:**

```bash
# Check worker is running
docker ps | grep worker

# Inspect worker logs for startup errors
docker logs hyrepath-worker --tail 100

# Verify Redis connectivity from worker
docker exec hyrepath-worker redis-cli -u $REDIS_URL ping

# Check RQ queue status (inside worker container)
docker exec hyrepath-worker python -c "
from app.queue import q
print(f'Queued: {len(q)}, Failed: {len(q.failed_job_registry)}')
"

# Restart worker
docker compose -f backend/docker/docker-compose.yml \
  -f backend/docker/docker-compose.prod.yml \
  restart worker
```

**Related:** Check audit logs for repeated `identifier_hash` patterns if many jobs are stuck: `psql $DATABASE_URL -c "SELECT identifier_hash, COUNT(*) FROM audit_log WHERE status='queued' GROUP BY identifier_hash ORDER BY COUNT(*) DESC LIMIT 10"`

---

### Problem: GET /ready returns unhealthy

**Cause:** Redis connection pool exhausted, rate limiter unavailable, or worker queue unreachable.

**Solution:**

```bash
# Check Redis memory and connections
docker exec hyrepath-redis redis-cli INFO stats | grep -E 'total_connections|rejected_connections'
docker exec hyrepath-redis redis-cli INFO memory | grep used_memory_human

# Test rate limiter manually
curl -fsS http://localhost:8000/ready | python -m json.tool

# Review API logs for rate limiter exceptions
docker logs hyrepath-api | grep -i "rate limit"
```

**Related:** If Redis is OOM, review [OPS.md § Rate limits](OPS.md#rate-limits-and-incidents) to lower limits temporarily or scale Redis.

---

## 2. Worker Issues

### Problem: Tier 1 jobs fail with "Connection refused to Multilogin"

**Cause:** Network mode mismatch — worker not running in `host` mode, or Multilogin service not on host.

**Solution:**

```bash
# Verify network mode for both containers
docker inspect hyrepath-worker | grep NetworkMode
# Should show: "NetworkMode": "host"

# Check Multilogin is reachable from worker
docker exec hyrepath-worker curl -fsS http://localhost:35000/api/v1/profile/list

# Fix: Ensure both worker AND Multilogin use host mode in compose
# backend/docker/docker-compose.prod.yml:
#   worker:
#     network_mode: host
```

**Related:** Tier 1 is a paid feature requiring Multilogin. Default tier is 2–4 (free). See [backend/docs/ARCHITECTURE.md § Tiers](../backend/docs/ARCHITECTURE.md).

---

### Problem: Worker container exits immediately

**Cause:** Invalid environment variables (missing secrets, malformed URLs) or Python import error.

**Solution:**

```bash
# Check container exit code and logs
docker logs hyrepath-worker
docker inspect hyrepath-worker --format='{{.State.ExitCode}}'

# Validate environment variables before restart
cd backend && bash scripts/validate_env.sh

# Common issues:
# - DATABASE_URL missing or malformed
# - REDIS_URL incorrect (should be redis://redis:6379/0)
# - Missing API_SECRET or MULTILOGIN_API_TOKEN (Tier 1)

# Test worker startup manually
docker compose -f backend/docker/docker-compose.yml \
  -f backend/docker/docker-compose.prod.yml \
  run --rm worker python -c "from app.queue import q; print('OK')"
```

**Related:** For enricher prerequisites (Sherlock, Maigret, GitRecon), run Layer 1 audit: `docker exec hyrepath-worker bash -c 'which sherlock maigret theHarvester crosslinked email-sleuth 2>/dev/null'`. See [TESTING_TIER234.md § Layer 1](../backend/docs/TESTING_TIER234.md#layer-1--prerequisites-audit).

---

### Problem: Worker processes jobs but enrichers return empty data

**Cause:** Missing enricher dependencies (CLI tools, sidecar URLs, API tokens) or enricher failed silently.

**Solution:**

```bash
# Check enricher prerequisites inside worker
docker exec hyrepath-worker python scripts/probe_enrichers.py --prereqs

# Probe specific enricher in isolation
docker exec hyrepath-worker python scripts/probe_enrichers.py --only sherlock,maigret

# Expected statuses:
# - OK: Enricher returned data
# - SKIP: Required request field missing
# - EMPTY {}: Tool missing, timeout, or no results

# Verify sidecar connectivity
docker exec hyrepath-worker curl -fsS http://social-analyzer:9005/get_settings
docker exec hyrepath-worker curl -fsS http://google-maps-scraper:8080/api/docs
docker exec hyrepath-worker curl -fsS http://email-verifier:8080/health

# Check GitRecon (subprocess CLI, not sidecar)
docker exec hyrepath-worker ls -l /opt/gitrecon/gitrecon.py
docker exec hyrepath-worker python /opt/gitrecon/gitrecon.py --help
```

**Related:** Enrichers fail **silently** — `status: "completed"` with no error. Always inspect `dossier.sources` array in API response to see which enrichers contributed. Missing source = enricher returned `{}`. See [TESTING_TIER234.md](../backend/docs/TESTING_TIER234.md) intro.

---

## 3. Rate Limiting Issues

### Problem: Getting HTTP 429 errors

**Cause:** Exceeded rate limits (30 async/min or 10 sync/min per API token by default).

**Solution:**

```bash
# Check current rate limit config
grep -E 'MAX_(SYNC|ASYNC|COMPLIANCE)_REQUESTS_PER_MINUTE' backend/.env.production

# Slow down requests on client side
# Implement exponential backoff: 1s, 2s, 4s, 8s...

# Temporarily lower limits during incident
# backend/.env.production:
#   MAX_ASYNC_REQUESTS_PER_MINUTE=15
#   MAX_SYNC_REQUESTS_PER_MINUTE=5

# Restart API to apply new limits
docker compose -f backend/docker/docker-compose.yml \
  -f backend/docker/docker-compose.prod.yml \
  restart api worker

# Review audit logs for repeated identifier_hash patterns
psql $DATABASE_URL -c "
  SELECT identifier_hash, COUNT(*) as attempts
  FROM audit_log
  WHERE created_at > NOW() - INTERVAL '1 hour'
  GROUP BY identifier_hash
  ORDER BY attempts DESC
  LIMIT 10;
"
```

**Related:** Rate limits are per-token and use Redis sliding windows. If Redis is down, rate limiter fails open (allows all requests). See [OPS.md § Rate limits and incidents](OPS.md#rate-limits-and-incidents).

---

### Problem: "Profile pool exhausted" errors (Tier 1)

**Cause:** `MULTILOGIN_DAILY_VIEW_LIMIT` reached (default 22 profiles/day).

**Solution:**

```bash
# Check current profile usage
curl -fsS http://localhost:35000/api/v1/profile/list \
  -H "Authorization: Bearer $MULTILOGIN_API_TOKEN" \
  | python -m json.tool

# Increase limit (if more profiles available)
# backend/.env.production:
#   MULTILOGIN_DAILY_VIEW_LIMIT=50

# Or wait for 24-hour cooldown period
# Profile view counters reset daily per LinkedIn's rate limit

# Alternative: Use Tier 2–4 (free) without LinkedIn
curl -X POST http://localhost:8000/enrich \
  -H "Authorization: Bearer $API_TOKEN" \
  -d '{"username":"torvalds","requested_tiers":["tier2","tier3","tier4"]}'
```

**Related:** One LinkedIn profile view per Tier 1 enrichment job. Product boundary documented in [backend/docs/LEGAL.md](../backend/docs/LEGAL.md). See also [OPS.md § Source limits](OPS.md#source-limits-product-boundaries).

---

## 4. Data Quality Issues

### Problem: Dossier has empty fields

**Cause:** Data not publicly available, enricher failed gracefully, or enricher prerequisites missing.

**Solution:**

```bash
# Check dossier.sources array in API response
curl -X POST http://localhost:8000/enrich/sync \
  -H "Authorization: Bearer $API_TOKEN" \
  -d '{"username":"torvalds","requested_tiers":["tier2"]}' \
  | jq '.dossier.sources'

# Expected output: ["sherlock", "maigret", "social_analyzer"]
# Missing source = enricher returned {} (not an error)

# Probe missing enricher in isolation
docker exec hyrepath-worker python scripts/probe_enrichers.py --only sherlock

# Common reasons for empty results:
# 1. Username doesn't exist on those platforms
# 2. Enricher CLI timed out (check logs)
# 3. Sidecar unreachable (Social Analyzer, GMaps)
# 4. GitHub API rate limited (use GITHUB_TOKEN)

# For theHarvester empty results:
docker logs hyrepath-worker | grep theHarvester
# May show "No results found" — this is expected for uncommon domains
```

**Related:** Use stable test subjects from docs: `torvalds`, `satyanadella` (GitHub), `noreply@github.com`, company `Microsoft`. See [TESTING_TIER234.md § Layer 3](../backend/docs/TESTING_TIER234.md#layer-3--enricher-isolation).

---

### Problem: Low confidence scores

**Cause:** Username doesn't match across platforms (e.g., `john_doe` on Twitter but `johndoe` on GitHub).

**Solution:**

```bash
# Try different identifier combinations
curl -X POST http://localhost:8000/enrich/sync \
  -H "Authorization: Bearer $API_TOKEN" \
  -d '{
    "username":"torvalds",
    "email":"torvalds@linux-foundation.org",
    "company":"Linux Foundation",
    "requested_tiers":["tier2","tier3"]
  }' | jq '.dossier.merged_data.confidence_score'

# Confidence calculation (see app/pipeline.py):
# - 0.9–1.0: High (3+ sources agree)
# - 0.7–0.89: Medium (2 sources agree)
# - 0.5–0.69: Low (1 source or conflicting data)
# - <0.5: Very low (no cross-validation)

# Inspect per-source data before merge
curl ... | jq '.dossier.sources_detail'
```

**Related:** Confidence scoring uses handle/email/company overlap across sources. See `app/scoring.py` for merge logic.

---

### Problem: Email verification returns "unknown" status

**Cause:** Email Verify level set to `basic` (syntax + DNS only), or SMTP verification disabled.

**Solution:**

```bash
# Check current verification level
grep EMAIL_VERIFY_LEVEL backend/.env.production

# For deeper SMTP verification (requires Reacher sidecar):
# backend/.env.production:
#   EMAIL_VERIFY_LEVEL=smtp
#   EMAIL_VERIFY_MAX_PER_JOB=10
#   EMAIL_VERIFY_SMTP_DELAY_SECONDS=5

# Start Reacher sidecar (paid profile)
docker compose -f backend/docker/docker-compose.yml \
  -f backend/docker/docker-compose.prod.yml \
  --profile paid up -d reacher

# Test SMTP verification
curl -X POST http://localhost:8000/enrich/sync \
  -H "Authorization: Bearer $API_TOKEN" \
  -d '{"email":"noreply@github.com","requested_tiers":["tier3"]}' \
  | jq '.dossier.merged_data.verified_emails'
```

**Related:** Two-phase verify: AfterShip sidecar (basic) → Reacher (SMTP). See [TESTING_TIER234.md § Email Verify](../backend/docs/TESTING_TIER234.md#layer-1--prerequisites-audit).

---

## 5. Frontend Issues

### Problem: "Backend unreachable" message

**Cause:** API down, incorrect `BACKEND_API_URL`, or CORS misconfiguration.

**Solution:**

```bash
# Verify API is healthy
curl -fsS http://localhost:8000/health

# Check CORS headers
curl -i -X OPTIONS http://localhost:8000/enrich \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST"
# Should return Access-Control-Allow-Origin: *

# Inspect frontend config (browser console)
# BACKEND_API_URL should match API base URL

# Common mistakes:
# - BACKEND_API_URL=http://api:8000 (internal Docker name, not accessible from browser)
# - Correct: BACKEND_API_URL=http://localhost:8000 (or public IP)

# Fix in frontend/.env.local:
#   NEXT_PUBLIC_API_URL=http://localhost:8000
#   # OR for production:
#   NEXT_PUBLIC_API_URL=https://enrich.hyrepath.io
```

**Related:** CORS is disabled by default (`CORS_ORIGINS=*`). For production, set explicit origins: `CORS_ORIGINS=https://app.hyrepath.io,https://staging.hyrepath.io`.

---

### Problem: Job progress stuck at 95%

**Cause:** Frontend polling timeout (default 5 minutes) or job actually stuck in worker.

**Solution:**

```bash
# Check job status via API directly
curl -fsS http://localhost:8000/enrich/{job_id} \
  -H "Authorization: Bearer $API_TOKEN" \
  | jq '.status'

# If API shows "completed" but frontend shows 95%:
# → Frontend polling timed out. Refresh job detail page manually.

# If API shows "processing" for >5 minutes:
# → Worker may be stuck. Check worker logs:
docker logs hyrepath-worker --tail 100 | grep {job_id}

# Inspect RQ queue
docker exec hyrepath-worker python -c "
from app.queue import q
from rq.job import Job
job = Job.fetch('{job_id}', connection=q.connection)
print(f'Status: {job.get_status()}')
print(f'Started: {job.started_at}')
print(f'Ended: {job.ended_at}')
"

# If job is truly stuck, restart worker
docker compose restart worker
```

**Related:** Frontend polls every 2 seconds for up to 5 minutes. After timeout, user must manually refresh. See `frontend/app/jobs/[id]/page.tsx`.

---

## 6. Database Issues

### Problem: Alembic migration fails on startup

**Cause:** Schema mismatch (local dev vs production), corrupted Alembic version table, or concurrent migrations.

**Solution:**

```bash
# Check current Alembic version
docker exec hyrepath-api python -c "
from alembic.config import Config
from alembic import script
from alembic.runtime.migration import MigrationContext
from app.db import engine
cfg = Config('alembic.ini')
script_dir = script.ScriptDirectory.from_config(cfg)
with engine.connect() as conn:
    context = MigrationContext.configure(conn)
    print(f'Current: {context.get_current_revision()}')
    print(f'Head: {script_dir.get_current_head()}')
"

# View failed migration logs
docker logs hyrepath-api | grep -A 20 "alembic.runtime.migration"

# PREFERRED: Restore from backup
# 1. Stop all services
docker compose -f backend/docker/docker-compose.yml \
  -f backend/docker/docker-compose.prod.yml down

# 2. Restore Postgres from backup
docker run --rm -v hyrepath-postgres-data:/data -v $(pwd):/backup \
  postgres:15-alpine sh -c "cd /data && tar xvf /backup/postgres-backup.tar"

# 3. Restart services
docker compose -f backend/docker/docker-compose.yml \
  -f backend/docker/docker-compose.prod.yml up -d

# LAST RESORT: Manual downgrade (NOT recommended for production)
docker exec hyrepath-api alembic downgrade -1
docker exec hyrepath-api alembic upgrade head
```

**Related:** Alembic runs forward-only migrations on API startup. Never downgrade schema in production — restore from backup instead. See [OPS.md § Rollback](OPS.md#rollback).

---

### Problem: Postgres out of disk space

**Cause:** Too many old jobs retained, or audit log not being purged.

**Solution:**

```bash
# Check database size
docker exec hyrepath-postgres psql -U enrichment -d enrichment -c "
  SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
  FROM pg_tables
  WHERE schemaname='public'
  ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"

# Check audit log row count
psql $DATABASE_URL -c "SELECT COUNT(*) FROM audit_log;"

# Manual purge (retention policy not yet implemented)
# CAUTION: This deletes data permanently
psql $DATABASE_URL -c "
  DELETE FROM audit_log
  WHERE created_at < NOW() - INTERVAL '90 days'
  RETURNING id;
"

# Set up weekly cron for audit log purge (if not already configured)
# See OPS.md § Audit log purge:
# 0 3 * * 0 cd /opt/hyrepath && .venv/bin/python backend/scripts/purge_audit_logs.py

# Vacuum to reclaim disk space
docker exec hyrepath-postgres psql -U enrichment -d enrichment -c "VACUUM FULL;"
```

**Related:** Default audit log retention is 5 years (`AUDIT_LOG_RETENTION_YEARS=5`). Configure weekly purge cron. See [OPS.md § Audit log purge](OPS.md#audit-log-purge-cron).

---

### Problem: "too many connections" Postgres error

**Cause:** Connection pool exhausted (SQLAlchemy defaults: pool_size=5, max_overflow=10).

**Solution:**

```bash
# Check current Postgres connections
docker exec hyrepath-postgres psql -U enrichment -d enrichment -c "
  SELECT count(*) FROM pg_stat_activity WHERE datname='enrichment';
"

# View connection pool config
docker exec hyrepath-api python -c "
from app.db import engine
print(f'Pool size: {engine.pool.size()}')
print(f'Max overflow: {engine.pool._max_overflow}')
"

# Increase pool size (if necessary)
# backend/.env.production:
#   DB_POOL_SIZE=10
#   DB_MAX_OVERFLOW=20

# Restart API and worker
docker compose restart api worker

# Alternative: Increase Postgres max_connections
docker exec hyrepath-postgres psql -U postgres -c "
  ALTER SYSTEM SET max_connections = 200;
"
docker compose restart postgres
```

**Related:** Each worker process can hold up to `DB_POOL_SIZE + DB_MAX_OVERFLOW` connections. Scale conservatively based on container count.

---

## Diagnostic Commands Reference

### Quick health check

```bash
# All services
docker ps
docker compose -f backend/docker/docker-compose.yml \
  -f backend/docker/docker-compose.prod.yml ps

# API health
curl -fsS http://localhost:8000/health | python -m json.tool

# API ready (includes Redis + worker queue check)
curl -fsS http://localhost:8000/ready | python -m json.tool

# Database connectivity
docker exec hyrepath-api psql $DATABASE_URL -c "SELECT 1"

# Redis connectivity
docker exec hyrepath-api redis-cli -u $REDIS_URL ping
```

### View logs

```bash
# Last 100 lines
docker logs hyrepath-api --tail 100
docker logs hyrepath-worker --tail 100

# Follow live logs
docker logs -f hyrepath-worker

# Search logs for errors
docker logs hyrepath-worker | grep -i error

# Specific job ID
docker logs hyrepath-worker | grep abc123def456
```

### Validate environment

```bash
# Run validation script
cd backend && bash scripts/validate_env.sh

# Check specific vars
docker exec hyrepath-api env | grep -E '(DATABASE_URL|REDIS_URL|API_SECRET)'

# Test enricher prerequisites
docker exec hyrepath-worker python scripts/probe_enrichers.py --prereqs
```

### Queue inspection

```bash
# Queue stats
docker exec hyrepath-worker python -c "
from app.queue import q
print(f'Queued: {len(q)}')
print(f'Failed: {len(q.failed_job_registry)}')
print(f'Started: {len(q.started_job_registry)}')
"

# View failed jobs
docker exec hyrepath-worker rq info --url $REDIS_URL

# Clear failed jobs (CAUTION)
docker exec hyrepath-worker python -c "
from app.queue import q
q.failed_job_registry.cleanup(0)  # Delete all failed jobs
"
```

### Enricher isolation testing

```bash
# All enrichers
docker exec hyrepath-worker python scripts/probe_enrichers.py

# Specific enricher
docker exec hyrepath-worker python scripts/probe_enrichers.py --only sherlock,maigret

# JSON output
docker exec hyrepath-worker python scripts/probe_enrichers.py --json

# 20-profile canary set
docker exec hyrepath-worker python scripts/probe_enrichers.py \
  --canary docs/tier234_canary_set.example.json --json
```

---

## See Also

- [OPS.md](OPS.md) — Operations runbook (rollback, rate limits, alerting)
- [ALERTING.md](ALERTING.md) — Prometheus rules, health-check notify, Sentry checklist
- [backend/docs/TESTING_TIER234.md](../backend/docs/TESTING_TIER234.md) — Layer-by-layer testing guide
- [backend/docs/ARCHITECTURE.md](../backend/docs/ARCHITECTURE.md) — System design, tiers, enricher flow
- [backend/docs/LEGAL.md](../backend/docs/LEGAL.md) — Source limits, compliance boundaries
- [deployment.md](deployment.md) — CD workflow, image pinning, rollback procedure
- [PROD_SMOKE.md](PROD_SMOKE.md) — Production smoke tests
- [PROD_ACCEPTANCE.md](PROD_ACCEPTANCE.md) — Full acceptance test suite
