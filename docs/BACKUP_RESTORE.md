# Backup and Restore

Backup strategy, automation, and disaster recovery procedures for Hyrepath Enrichment production.

See also: [OPS.md](OPS.md) (rollback, alerting, rate limits), [ALERTING.md](ALERTING.md), [backend/docs/ARCHITECTURE.md](../backend/docs/ARCHITECTURE.md).

## Backup Strategy Overview

### What to Back Up

| Component | Data | Criticality | Method |
|-----------|------|-------------|--------|
| **Postgres** | Jobs, suppression list, audit logs | Critical | Daily automated dumps |
| **Redis** | Queue state, rate-limit counters | High | AOF persistence + manual snapshots |
| **R2** | Scraped photo assets | Medium | Versioning + periodic snapshots |

### Backup Frequency

- **Postgres**: Daily at 2:00 AM UTC
- **Redis**: Continuous AOF (appendonly mode), manual snapshots on demand
- **R2**: Bucket versioning enabled; weekly full snapshots to separate bucket

### Retention Policy

- **Standard backups**: 30 days rolling window
- **Compliance archives**: 90 days (jobs with `audit_flags`)
- **R2 versioning**: 30 days (deleted objects recoverable)

### Recovery Objectives

- **RTO** (Recovery Time Objective): 4 hours for full system restore
- **RPO** (Recovery Point Objective): 24 hours (daily Postgres backups + Redis AOF)

## Postgres Backup Automation

### Script Location

`backend/scripts/backup_postgres.sh` — automated daily backup with 30-day rotation.

### Cron Setup

Add to the production host crontab (as the deployment user):

```cron
# Daily Postgres backup at 2 AM
0 2 * * * /opt/hyrepath/HyerPathEnrichment/backend/scripts/backup_postgres.sh >> /var/log/hyrepath-backup.log 2>&1
```

### Backup Directory

Backups are stored in `/backups/postgres/` on the production host. Ensure this directory exists and has sufficient disk space:

```bash
sudo mkdir -p /backups/postgres
sudo chown $(whoami):$(whoami) /backups/postgres
```

Recommended: Mount `/backups` on a separate volume with at least 50 GB capacity.

### Rotation Policy

The backup script automatically deletes backups older than 30 days. Adjust the retention period by editing the `-mtime +30` flag in `backup_postgres.sh`.

### Manual Backup

To trigger an immediate backup:

```bash
cd /opt/hyrepath/HyerPathEnrichment
bash backend/scripts/backup_postgres.sh
```

Backup files are named: `hyrepath-YYYYMMDD-HHMMSS.sql.gz`

### Monitoring

Check backup logs:

```bash
tail -f /var/log/hyrepath-backup.log
```

Alert on backup failures (cron stderr) via your monitoring system.

## Postgres Restore Procedure

### Prerequisites

1. Identify the backup file to restore (e.g., `hyrepath-20260728-020001.sql.gz`)
2. Ensure services are healthy before stopping them
3. Notify users of planned downtime (estimated 30-60 minutes)

### Restore Steps

**1. Stop API and Workers**

```bash
cd /opt/hyrepath/HyerPathEnrichment/backend/docker
docker compose stop api worker worker-tier1 worker-tier234
```

**2. Drop and Recreate Database**

```bash
docker exec -it docker-postgres-1 psql -U hyrepath -c "DROP DATABASE hyrepath;"
docker exec -it docker-postgres-1 psql -U hyrepath -c "CREATE DATABASE hyrepath OWNER hyrepath;"
```

**3. Restore from Backup**

```bash
cd /opt/hyrepath/HyerPathEnrichment
bash backend/scripts/restore_postgres.sh /backups/postgres/hyrepath-20260728-020001.sql.gz
```

The script will:
- Decompress and restore the SQL dump
- Run Alembic migrations to bring schema up to date
- Start API and worker services
- Prompt you to verify health

**4. Verify Data Integrity**

```bash
# Check health endpoint
curl http://localhost:8000/health

# Check job count
docker exec -it docker-postgres-1 psql -U hyrepath -d hyrepath -c "SELECT COUNT(*) FROM jobs;"

# Verify recent jobs
docker exec -it docker-postgres-1 psql -U hyrepath -d hyrepath -c "SELECT id, status, created_at FROM jobs ORDER BY created_at DESC LIMIT 5;"
```

**5. Resume Operations**

Once verified, notify users and monitor for 1-2 hours:

```bash
docker compose logs -f api worker
```

### Restore to Staging

Test backups monthly by restoring to staging:

```bash
# On staging host
scp prod:/backups/postgres/hyrepath-20260728-020001.sql.gz /tmp/
cd /opt/hyrepath-staging/HyerPathEnrichment
bash backend/scripts/restore_postgres.sh /tmp/hyrepath-20260728-020001.sql.gz
```

Run full acceptance tests:

```bash
BASE_URL=http://localhost:8000 API_TOKEN=staging-token bash scripts/prod_full_acceptance.sh --local
```

## Redis Backup and Restore

### AOF Persistence (Default)

Redis is configured with `appendonly yes` in `backend/docker/redis.conf`. The AOF log is persisted to the Docker volume `redis-data`.

**Benefits**:
- Continuous write logging (sub-second data loss on crash)
- Automatic replay on Redis restart

**Tradeoff**:
- Larger disk usage than RDB snapshots
- Slower startup on large datasets

### Manual Backup (RDB Snapshot)

To create a point-in-time RDB snapshot:

```bash
docker exec docker-redis-1 redis-cli BGSAVE
```

The snapshot is saved to `/data/dump.rdb` inside the container (mapped to the `redis-data` volume).

**Copy snapshot to host**:

```bash
docker cp docker-redis-1:/data/dump.rdb /backups/redis/redis-$(date +%Y%m%d-%H%M%S).rdb
```

### Restore from AOF

**1. Stop Redis**

```bash
cd /opt/hyrepath/HyerPathEnrichment/backend/docker
docker compose stop redis
```

**2. Replace AOF File**

```bash
# Backup current AOF
docker cp docker-redis-1:/data/appendonly.aof /backups/redis/appendonly.aof.backup

# Copy restored AOF
docker cp /backups/redis/appendonly-20260728.aof docker-redis-1:/data/appendonly.aof
```

**3. Restart Redis**

```bash
docker compose up -d redis
docker logs -f docker-redis-1
```

**4. Verify Queue State**

```bash
docker exec docker-redis-1 redis-cli LLEN enrichment_queue
docker exec docker-redis-1 redis-cli KEYS "rate_limit:*"
```

### Restore from RDB Snapshot

Similar to AOF restore, but replace `dump.rdb` instead:

```bash
docker compose stop redis
docker cp /backups/redis/redis-20260728.rdb docker-redis-1:/data/dump.rdb
docker compose up -d redis
```

**Note**: RDB restore loses any queue changes made after the snapshot was created.

## R2 Asset Backup

### Enable Bucket Versioning

In the Cloudflare dashboard:

1. Navigate to **R2** → `hyrepath-enrichment-photos`
2. **Settings** → **Object versioning** → Enable
3. Set retention policy: 30 days for deleted objects

Now deleted or overwritten photos can be recovered within 30 days.

### Periodic Full Snapshots

Use the Cloudflare API or `rclone` to sync the bucket to a separate backup bucket weekly.

**Setup rclone** (one-time):

```bash
rclone config create r2-prod s3 \
  provider=Cloudflare \
  access_key_id=$R2_ACCESS_KEY_ID \
  secret_access_key=$R2_SECRET_ACCESS_KEY \
  endpoint=https://$CLOUDFLARE_ACCOUNT_ID.r2.cloudflarestorage.com

rclone config create r2-backup s3 \
  provider=Cloudflare \
  access_key_id=$R2_BACKUP_ACCESS_KEY_ID \
  secret_access_key=$R2_BACKUP_SECRET_ACCESS_KEY \
  endpoint=https://$CLOUDFLARE_ACCOUNT_ID.r2.cloudflarestorage.com
```

**Weekly sync cron**:

```cron
# Sync R2 production bucket to backup bucket every Sunday at 3 AM
0 3 * * 0 rclone sync r2-prod:hyrepath-enrichment-photos r2-backup:hyrepath-enrichment-photos-backup --log-file=/var/log/r2-backup.log
```

### Restore Individual Assets

**From versioning**:

1. In Cloudflare dashboard, navigate to the object
2. **Versions** tab → select the version to restore
3. Click **Restore**

**From backup bucket**:

```bash
# Restore a single photo
rclone copy r2-backup:hyrepath-enrichment-photos-backup/photos/abc123.jpg r2-prod:hyrepath-enrichment-photos/photos/
```

### Full Bucket Restore

In a disaster scenario, sync the entire backup bucket back to production:

```bash
# Verify backup bucket first
rclone ls r2-backup:hyrepath-enrichment-photos-backup | wc -l

# Restore
rclone sync r2-backup:hyrepath-enrichment-photos-backup r2-prod:hyrepath-enrichment-photos --dry-run
rclone sync r2-backup:hyrepath-enrichment-photos-backup r2-prod:hyrepath-enrichment-photos
```

## Disaster Recovery Scenarios

### Scenario 1: Complete Data Loss

**Cause**: Host failure, ransomware, accidental `docker volume rm`

**Recovery**:

1. Provision new host or clean existing one
2. Deploy application stack (see [deployment.md](deployment.md))
3. Restore Postgres: `bash backend/scripts/restore_postgres.sh /backups/postgres/hyrepath-YYYYMMDD-HHMMSS.sql.gz`
4. Restore Redis AOF: Copy `appendonly.aof` to `redis-data` volume
5. Restore R2: Sync from backup bucket (see above)
6. Verify: Run smoke tests (`make smoke-prod`)

**Estimated RTO**: 2-4 hours (depends on data size and network speed)

**Data Loss (RPO)**: Up to 24 hours (since last Postgres backup) + queue jobs in flight

### Scenario 2: Corrupted Database

**Cause**: Bad migration, manual SQL error, disk corruption

**Recovery**:

1. **Test restore in staging first** (see [Restore to Staging](#restore-to-staging))
2. If staging restore succeeds, proceed with production restore
3. If staging restore fails, attempt an older backup

**Estimated RTO**: 30 minutes (if staging test passes)

### Scenario 3: Accidental Job Deletion

**Cause**: Admin error, bug in job cleanup logic

**Recovery**:

1. Check audit logs for deletion timestamp:
   ```sql
   SELECT * FROM audit_log WHERE action = 'job_deleted' AND created_at > NOW() - INTERVAL '7 days';
   ```
2. Restore from the most recent backup **before** the deletion
3. If deletion was recent (<1 hour), check Redis queue for in-flight jobs

**Preventive Measures**:
- Enable `AUDIT_LOG_RETENTION_YEARS=5` (default)
- Review audit logs before dropping large batches

### Scenario 4: Region Failure

**Cause**: Cloud provider outage, network partition

**Status**: Not currently implemented. Future enhancement: standby replica in separate region with automatic failover.

**Workaround**: Restore to a new region manually (same as Scenario 1).

## Backup Verification

### Monthly Restore Test

**Goal**: Verify backups are restorable and complete.

**Process** (run on first Monday of each month):

1. Identify the most recent production backup
2. Restore to staging environment
3. Run full acceptance tests
4. Compare job counts:
   ```sql
   -- Production
   SELECT COUNT(*) FROM jobs WHERE created_at < NOW() - INTERVAL '1 day';

   -- Staging (after restore)
   SELECT COUNT(*) FROM jobs WHERE created_at < NOW() - INTERVAL '1 day';
   ```
5. Document results in `#ops-log` channel

**Pass criteria**:
- Restore completes without errors
- Job count matches within 1% (accounting for ongoing production writes)
- Full acceptance test passes
- Enrichment workflow functions end-to-end

### Automated Integrity Checks

Add to cron (daily, after backup):

```cron
# Verify backup file integrity
5 2 * * * gzip -t /backups/postgres/hyrepath-$(date +%Y%m%d-*.sql.gz) 2>&1 | logger -t backup-verify
```

Alert on gzip test failures.

## Backup Security

### Access Control

- Backup directory: `chmod 700 /backups`, owned by deployment user
- Backup files: `chmod 600` (read/write owner only)
- R2 backup bucket: Separate access key with read-only permissions for staging

### Encryption

- **At rest**: Backups stored on encrypted volumes (LUKS or cloud provider encryption)
- **In transit**: R2 sync uses TLS; scp backups to remote storage with `-c aes256-ctr`

### Offsite Storage

**Recommended**: Copy backups to offsite storage weekly:

```bash
# Upload to S3 (or another cloud provider)
aws s3 sync /backups/postgres/ s3://hyrepath-offsite-backups/postgres/ --storage-class GLACIER
```

**Retention**: Keep 12 monthly backups offsite for 1 year.

## Troubleshooting

### Backup Script Fails

**Symptom**: Cron emails error, no backup file created

**Diagnosis**:

1. Check logs: `cat /var/log/hyrepath-backup.log`
2. Verify Postgres container is running: `docker ps | grep postgres`
3. Test `pg_dump` manually:
   ```bash
   docker exec docker-postgres-1 pg_dump -U hyrepath -d hyrepath | head -n 20
   ```

**Common causes**:
- Disk full (`df -h /backups`)
- Postgres not responding (`docker logs docker-postgres-1`)
- Permissions on `/backups` directory

### Restore Hangs

**Symptom**: `restore_postgres.sh` stuck during SQL import

**Diagnosis**:

1. Check Postgres logs: `docker logs -f docker-postgres-1`
2. Monitor disk I/O: `iostat -x 5`
3. Verify backup file is not corrupted: `gzip -t hyrepath-YYYYMMDD-HHMMSS.sql.gz`

**Workaround**: Restore to a fresh Postgres instance on a faster disk.

### Job Count Mismatch After Restore

**Symptom**: Restored database has fewer jobs than expected

**Diagnosis**:

1. Check backup timestamp vs. current time: 24-hour gap is expected (daily backups)
2. Review audit logs for deletions: `SELECT * FROM audit_log WHERE action = 'job_deleted' AND created_at > 'BACKUP_TIMESTAMP';`
3. Verify no jobs were dropped due to failed enrichments (check `status = 'failed'`)

**Action**: If gap exceeds 24 hours, use an older backup or recover from Redis queue.

## Related Documentation

- [OPS.md](OPS.md) — rollback procedures, rate limits, alerting
- [ALERTING.md](ALERTING.md) — Prometheus rules, health-check notify
- [deployment.md](deployment.md) — CD pipeline, GHCR image pinning
- [PROD_ACCEPTANCE.md](PROD_ACCEPTANCE.md) — full acceptance test suite
- [backend/docs/ARCHITECTURE.md](../backend/docs/ARCHITECTURE.md) — storage layer, queue design
