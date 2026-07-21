# Operations runbook

Operator procedures for Hyrepath Enrichment production and staging.

See also: [ALERTING.md](ALERTING.md) (Prometheus rules, health-alert notify, Sentry checklist), [deployment.md](deployment.md), [PROD_SMOKE.md](PROD_SMOKE.md), [PROD_ACCEPTANCE.md](PROD_ACCEPTANCE.md), [backend/docs/LEGAL.md](../backend/docs/LEGAL.md).

## Rollback

Prefer the CD rollback in [deployment.md](deployment.md) (pin previous GHCR SHA via `docker-compose.cd-images.yml`). Manual fallback:

1. **Identify last known-good image tag** (or git SHA used for the build).
2. On the host:
   ```bash
   cd backend/docker
   docker compose -f docker-compose.yml -f docker-compose.prod.yml down
   # Pin images or rebuild from previous SHA, then:
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```
3. **Database migrations:** Alembic runs forward-only on boot. If a bad migration shipped, restore Postgres from backup rather than downgrading schema in place.
4. Verify: `BASE_URL=https://<host> API_TOKEN=... make smoke-prod`

## Audit log purge (cron)

Retention default: 5 years (`AUDIT_LOG_RETENTION_YEARS`).

Weekly cron (example):

```cron
0 3 * * 0 cd /opt/hyrepath/HyerPathEnrichment/backend && .venv/bin/python scripts/purge_audit_logs.py >> /var/log/hyrepath-audit-purge.log 2>&1
```

Monitor the log for `purged N audit log rows`. Zero rows is normal when nothing exceeds retention.

## Rate limits and incidents

| Scope | Env var | Default | On exceed |
|-------|---------|---------|-----------|
| Sync enrich | `MAX_SYNC_REQUESTS_PER_MINUTE` | 10 | HTTP 429 |
| Async enrich | `MAX_ASYNC_REQUESTS_PER_MINUTE` | 30 | HTTP 429 |
| Compliance (opt-out/DSAR) | `MAX_COMPLIANCE_REQUESTS_PER_MINUTE` | 20 | HTTP 429 |
| gitrecon GitHub | `GITRECON_MAX_PER_MINUTE` | 10 | Soft-fail empty fragment + cooldown |

**Incident response (429 storm / upstream abuse):**

1. Check Redis connectivity (`GET /ready` should be 200).
2. Lower rate limits temporarily via env reload + worker/api restart.
3. Review audit logs for repeated `identifier_hash` patterns.
4. For compliance endpoint abuse, tighten firewall/WAF before API token rotation.

## Source limits (product boundaries)

Documented in [backend/docs/LEGAL.md](../backend/docs/LEGAL.md):

- One LinkedIn profile view per enrichment job when Tier 1 enabled (`MULTILOGIN_DAILY_VIEW_LIMIT`, default 22/day).
- No bulk scraping; customer-supplied URLs only.
- Email SMTP verification ~10/min per job (`EMAIL_VERIFY_MAX_PER_JOB`, `EMAIL_VERIFY_SMTP_DELAY_SECONDS`).
- GitHub API: prefer `GITHUB_TOKEN`; gitrecon throttle handles 403/429.

## Alerting

Production alert signals, silence/ack, Prometheus rules, and the health-check notify cron are documented in [ALERTING.md](ALERTING.md). Quick probe:

```bash
DRY_RUN=1 BASE_URL="$BASE_URL" python backend/scripts/health_alert_notify.py
```

## Change signals

When `CHANGEDETECTION_URL` and `NOTIFY_WEBHOOK_URL` are set, change watches post to the API signals route. Verify webhook delivery after deploy:

```bash
curl -fsS "$BASE_URL/health"
# Check changedetection UI + NOTIFY_WEBHOOK_URL receiver logs
```

## Full acceptance

Local:

```bash
bash scripts/prod_full_acceptance.sh --local
```

Production (after Task 86 deploy):

```bash
BASE_URL=https://enrich.hyrepath.io API_TOKEN="$PROD_TOKEN" bash scripts/prod_full_acceptance.sh --prod
```

Report path: `backend/.e2e-results/prod-acceptance-report.json`
