# Alerting runbook

Production/staging monitoring for Hyrepath Enrichment. **Offline-verified** artifacts ship in-repo; this document does **not** claim a live production pager is wired.

See also: [OPS.md](OPS.md), [deployment.md](deployment.md), Prometheus rules at [`backend/observability/alerts/hyrepath.rules.yml`](../backend/observability/alerts/hyrepath.rules.yml).

## What to alert on

| Signal | How detected | Severity | Action |
|--------|--------------|----------|--------|
| API down | Prometheus `up{job=~"hyrepath.*"}==0`, blackbox `/health`, or `health_alert_notify.py` | critical | Check API container/process, compose, host networking; `curl -fsS "$BASE_URL/health"` |
| Readiness fail | `/ready` non-200 (DB/Redis/schema) | critical | Postgres, Redis, Alembic head; see OPS rollback |
| Error rate (Tier 1) | `tier1_scrape_total` / `tier1_upload_total` rules | warning | Multilogin pool, captcha, R2 |
| Profile pool exhausted | `tier1_profile_pool_exhausted_total` | warning | Add MLX profiles or raise daily view limit |
| Queue depth / failures | `health_alert_notify.py` RQ snapshot; optional `hyrepath_rq_*` gauges | warning/critical | Scale workers; drain RQ failed registry |
| Sentry / GlitchTip spike | Sentry alert rules (checklist below) | critical/warning | Triage issues by environment; no PII in alerts |

Metric names on `GET /metrics` today (when `prometheus_client` is installed):

- `tier1_cache_hits_total`, `tier1_cache_misses_total`
- `tier1_scrape_total{outcome=...}`
- `tier1_upload_total{result=...}`
- `tier1_profile_views_total{profile_id=...}`
- `tier1_profile_pool_exhausted_total`

Plus process metrics from the Prometheus client library. Scrape `/metrics` and `/health` separately for liveness vs readiness.

## Notify path (webhook)

Env: `NOTIFY_WEBHOOK_URL` (same as change-signal notify). Unset → no-op.

| Path | Entry |
|------|--------|
| Library | `app.clients.notify.notify_ops_alert` / `app.observability.health_alerts.notify_on_health_failure` |
| CLI | `backend/scripts/health_alert_notify.py` |
| CI | `.github/workflows/ci-alerts.yml` uses `ALERT_WEBHOOK_URL` secret (no-op if unset) |

Payloads are **non-PII**: alert name, severity, summary, HTTP status/reason codes, queue counts. Never include emails, LinkedIn URLs, dossier fields, or request bodies.

### Cron example

```cron
*/2 * * * * cd /opt/hyrepath/HyerPathEnrichment/backend && .venv/bin/python scripts/health_alert_notify.py >> /var/log/hyrepath-health-alert.log 2>&1
```

Dry-run (probe only, no POST):

```bash
DRY_RUN=1 BASE_URL=http://localhost:8000 python backend/scripts/health_alert_notify.py
```

## Silence / acknowledge

| Mechanism | When to use |
|-----------|-------------|
| **Prometheus silence** | Planned maintenance window; silence `HyrepathApiDown` / Tier 1 rules by matcher `service=hyrepath-enrichment` |
| **Inhibit rules** | Optional: inhibit warnings while `HyrepathApiDown` is firing |
| **Ack in chat/pager** | After webhook delivery: acknowledge in Slack/PagerDuty; fix root cause before lifting silence |
| **Disable cron** | Temporarily stop `health_alert_notify.py` cron only during known outages (prefer silence over deleting cron) |
| **Sentry resolve / ignore** | Spike noise: resolve issue or set inbound filter; do not send PII to clear an alert |

Always leave a short ops note (who/when/why) when silencing for more than 30 minutes.

## Prometheus rules

File: `backend/observability/alerts/hyrepath.rules.yml`

Load into Prometheus / Grafana Alloy / Mimir. CI validates YAML parse. Queue gauge rules are inert until `hyrepath_rq_queue_depth` / `hyrepath_rq_failed_jobs` are exported; until then use the health-alert cron for queue depth/failures.

## Sentry / GlitchTip alert rules checklist

Configure in the Sentry-compatible UI (GlitchTip or Sentry SaaS) when `SENTRY_DSN` is set:

1. **Issue spike** — alert when event count for environment `production` exceeds a baseline (e.g. >50 events / 10m).
2. **New issue** — notify on first seen in `production` for unhandled exceptions.
3. **Fatal / error rate** — filter `level:error` or higher; exclude known probe tags (`probe=e2e`) in non-prod.
4. **Release regression** — spike after new `SENTRY_RELEASE`.
5. **Webhook action** — point at the same ops channel as `NOTIFY_WEBHOOK_URL` (or PagerDuty); ensure payloads exclude PII (`SENTRY_SEND_DEFAULT_PII=false`).
6. **Environment filter** — never page on `development` / `test`.
7. **Quota / drop** — monitor SDK outbound failures so a silent DSN break does not hide errors.

Verify with the internal probe only in non-prod: `ENABLE_ERROR_TRACKING_PROBE=1` + `POST /internal/error-tracking-probe`.

## CI failure notify

Workflow: `.github/workflows/ci-alerts.yml`

- Validates Prometheus rules YAML and runs alert-related tests.
- On job failure, POSTs to `ALERT_WEBHOOK_URL` when the secret is set; **no-op when unset**.

This is a CI signal only — not a production uptime pager.

## Proof / dry-run evidence

Offline checks (no live prod pager claimed):

```bash
# Rules parse
python -c "import yaml,pathlib; yaml.safe_load(pathlib.Path('backend/observability/alerts/hyrepath.rules.yml').read_text())"

# Unit tests (mock webhook)
pytest backend/tests/test_health_alerts.py backend/tests/test_prometheus_alert_rules.py -q

# CLI dry-run against local/stub base URL
DRY_RUN=1 BASE_URL=http://127.0.0.1:9 python backend/scripts/health_alert_notify.py || true
```
