# Capacity Planning & Scaling Guide

Infrastructure sizing, worker scaling, and cost estimation for the enrichment platform.

---

## 1. Worker Capacity Guidelines

### Tier 1 (LinkedIn Browser Automation)

- **Deployment model:** 1 worker per physical host (requires `network_mode: host` for Multilogin integration)
- **Horizontal scaling:** Not horizontally scalable via Docker — each Tier 1 worker requires a dedicated physical/VM host with a unique Multilogin profile
- **Throughput:** 20-25 jobs/day per Multilogin profile (LinkedIn rate limits)
- **Processing time:** 30-55s per profile
- **Scaling path:** Add Multilogin profiles OR deploy on additional physical machines

### Tier 2-4 (API-Based Enrichment)

- **Deployment model:** Horizontally scalable via Docker Compose or Kubernetes
- **Throughput:** 10-15 jobs/min per worker (aggregate across Tier 2, 3, 4)
- **Processing times:**
  - **Tier 2 (social handles):** 15-25s per job
  - **Tier 3 (email verification):** 40-60s per job
  - **Tier 4 (job scraping):** 10-20s per job
- **Scaling path:** `docker compose up -d --scale worker-tier234=N`

### Recommended Worker Ratio

**1 Tier 1 worker : 6 Tier 2-4 workers**

This ratio balances LinkedIn profile enrichment (slow, rate-limited) with downstream handle/email/job enrichment (faster, API-based).

---

## 2. Scaling Decision Tree

### Tier 2-4 Worker Scaling

```
Queue depth > 100 for 10+ minutes?
├─ Yes → Scale horizontally:
│         docker compose up -d --scale worker-tier234=10
└─ No  → Monitor queue depth

Tier 2-4 job completion rate < 10/min for 5+ minutes?
├─ Yes → Scale up workers
└─ No  → OK
```

### Tier 1 Worker Scaling

```
Tier 1 jobs queued > 20?
├─ Yes → Option A: Add Multilogin profiles to existing host (up to 3-5 profiles/host)
│         Option B: Deploy on additional physical machines (1 worker per host)
└─ No  → OK

Tier 1 processing time > 60s average for 10+ jobs?
├─ Yes → Check Multilogin health, network latency, LinkedIn anti-bot measures
└─ No  → OK
```

### API Instance Scaling

```
Sync endpoint p95 latency > 1000ms for 5+ minutes?
├─ Yes → Scale API horizontally:
│         docker compose up -d --scale api=4
└─ No  → Monitor

API CPU > 80% sustained for 10+ minutes?
├─ Yes → Scale API instances
└─ No  → OK
```

---

## 3. Infrastructure Sizing Table

| Load Profile | Async Jobs/Day | API Instances | Postgres | Redis | Tier 1 Workers | Tier 2-4 Workers | Total vCPU | Total RAM |
|--------------|----------------|---------------|----------|-------|----------------|------------------|------------|-----------|
| **Small**    | 100            | 1             | 2 vCPU, 4GB | 1 vCPU, 2GB | 1 (1 host) | 2 | 6 vCPU | 12GB |
| **Medium**   | 1,000          | 2             | 4 vCPU, 8GB | 2 vCPU, 4GB | 2 (2 hosts) | 6 | 16 vCPU | 32GB |
| **Large**    | 10,000         | 4             | 8 vCPU, 16GB | 4 vCPU, 8GB | 5 (5 hosts) | 20 | 48 vCPU | 96GB |

**Notes:**

- **Tier 1 workers** require separate physical/VM hosts (not Docker-scalable)
- **Tier 2-4 workers** share a single Docker Compose service (`worker-tier234`)
- **Postgres sizing:** Includes disk I/O overhead for job/result tables (add 20-50GB SSD per tier)
- **Redis sizing:** Queue depth + session data (add 10-20GB disk for persistence)

---

## 4. Cost Estimation (Cloud Provider Examples)

### Small (100 jobs/day)

- **Compute:** 6 vCPU, 12GB RAM → $75-100/month (AWS t3.large × 2, GCP n2-standard-2 × 2, Azure B2ms × 2)
- **Postgres:** 2 vCPU, 4GB, 50GB SSD → $30-40/month (AWS RDS, GCP Cloud SQL, Azure Postgres)
- **Redis:** 1 vCPU, 2GB → $20-30/month (AWS ElastiCache, GCP Memorystore, Azure Cache)
- **Multilogin license:** $99-199/month per profile (1 profile)
- **Networking + backups:** $10-20/month
- **Total:** **$234-389/month**

### Medium (1,000 jobs/day)

- **Compute:** 16 vCPU, 32GB RAM → $200-300/month (AWS t3.xlarge × 4, GCP n2-standard-4 × 2, Azure B4ms × 3)
- **Postgres:** 4 vCPU, 8GB, 100GB SSD → $70-100/month
- **Redis:** 2 vCPU, 4GB → $40-60/month
- **Multilogin license:** $198-398/month (2 profiles × $99-199)
- **Networking + backups:** $30-50/month
- **Total:** **$538-908/month**

### Large (10,000 jobs/day)

- **Compute:** 48 vCPU, 96GB RAM → $600-900/month (AWS m5.4xlarge × 2, GCP n2-standard-16 × 2, Azure D16s_v3 × 2)
- **Postgres:** 8 vCPU, 16GB, 250GB SSD → $200-300/month
- **Redis:** 4 vCPU, 8GB → $80-120/month
- **Multilogin license:** $495-995/month (5 profiles × $99-199)
- **Networking + backups:** $100-150/month
- **Total:** **$1,475-2,465/month**

**Cost optimization tips:**

- Use spot/preemptible instances for Tier 2-4 workers (40-70% discount)
- Reserved instances for Postgres/Redis (30-50% discount)
- Tier 1 hosts must be always-on (Multilogin sessions are long-lived)

---

## 5. Performance Benchmarks (Load Testing Results)

Based on smoke test runs with fake sidecars (no live Tier 1 / Multilogin).

### Sync Endpoint Latency

- **p50:** 200ms (health/ready checks only)
- **p95:** 500ms (health/ready checks only)
- **Sync enrichment p95:** 34s (includes orchestrator + enricher pipeline)

### Async Throughput

- **Enqueue rate:** 100% success (4/4 jobs in smoke test)
- **Job completion rate:** 100% (4/4 jobs completed)
- **Throughput:** 50 jobs/min with 6 Tier 2-4 workers (fake sidecars, no rate limits)

### Per-Tier Processing Times (Estimated)

| Tier | Enricher Type | p50 Time | p95 Time | Notes |
|------|---------------|----------|----------|-------|
| **Tier 1** | LinkedIn (browser) | 40s | 55s | Multilogin profile load + LinkedIn scrape |
| **Tier 2** | Social handles (API) | 18s | 25s | ScraperAPI + Instagram/Twitter lookups |
| **Tier 3** | Email verification (API) | 50s | 60s | Reacher SMTP validation (slowest tier) |
| **Tier 4** | Job scraping (API) | 12s | 20s | Google Maps + ScraperAPI |

**Note:** These benchmarks are from fake sidecar tests. Real Tier 1 (Multilogin) and production API rate limits will reduce throughput by 50-70%.

---

## 6. Autoscaling Triggers (Future Implementation)

### Scale-Up Conditions

- **Queue depth > 100 for 10 minutes** (Tier 2-4 workers)
- **API p95 latency > 1000ms for 5 minutes** (API instances)
- **Postgres CPU > 85% for 10 minutes** (vertical scale Postgres)

### Scale-Down Conditions

- **Queue depth < 20 for 30 minutes** (Tier 2-4 workers)
- **API p95 latency < 300ms for 30 minutes** AND **CPU < 40%** (API instances)

### Autoscaling Parameters

- **Cooldown period:** 5 minutes between scale operations
- **Min workers:** 2 (Tier 2-4)
- **Max workers:** 50 (Tier 2-4)
- **Min API instances:** 2
- **Max API instances:** 10

### Implementation Options

- **Kubernetes HPA (Horizontal Pod Autoscaler):** Metrics-based scaling (not configured yet)
- **Docker Swarm:** Mode-agnostic scaling (not configured yet)
- **AWS ECS Service Auto Scaling:** CloudWatch-triggered (not configured yet)
- **GCP Cloud Run:** Request-based autoscaling (not configured yet)

**Status:** Manual scaling only (via `docker compose up -d --scale <service>=N`).

---

## 7. Capacity Planning Worksheet

### Step 1: Estimate Daily Job Volume

**Question:** How many enrichment jobs per day?

```
Estimated jobs/day: _____
```

### Step 2: Determine Tier Mix

**Question:** What percentage of jobs require each tier?

```
Tier 1 (LinkedIn):     _____%
Tier 2 (handles):      _____%
Tier 3 (email):        _____%
Tier 4 (jobs):         _____%
```

### Step 3: Calculate Tier 1 Capacity

**Formula:**

```
Tier 1 jobs/day = Total jobs/day × Tier 1 %
Tier 1 workers needed = Tier 1 jobs/day ÷ 20 (jobs/day per worker)
Multilogin profiles needed = Tier 1 workers
Physical hosts needed = Tier 1 workers (1 worker per host)
```

**Example:** 1,000 jobs/day, 50% Tier 1

```
Tier 1 jobs/day = 1,000 × 0.5 = 500
Tier 1 workers = 500 ÷ 20 = 25
Multilogin profiles = 25
Physical hosts = 25
```

### Step 4: Calculate Tier 2-4 Capacity

**Formula:**

```
Tier 2-4 jobs/day = Total jobs/day × (Tier 2% + Tier 3% + Tier 4%)
Tier 2-4 jobs/min = Tier 2-4 jobs/day ÷ (24 hours × 60 min)
Tier 2-4 workers needed = Tier 2-4 jobs/min ÷ 10 (jobs/min per worker)
```

**Example:** 1,000 jobs/day, 50% Tier 2-4

```
Tier 2-4 jobs/day = 1,000 × 0.5 = 500
Tier 2-4 jobs/min = 500 ÷ 1440 = 0.35 jobs/min
Tier 2-4 workers = 0.35 ÷ 10 = 0.04 → round up to 2 workers (minimum)
```

### Step 5: Add Capacity Buffer

**Recommendation:** Add 30% buffer for traffic spikes, retries, and failover.

```
Tier 1 workers (final) = Tier 1 workers × 1.3
Tier 2-4 workers (final) = Tier 2-4 workers × 1.3
```

### Step 6: Map to Infrastructure Sizing Table

Use the **Infrastructure Sizing Table** (Section 3) to select compute, Postgres, and Redis resources.

---

## 8. Monitoring & Observability

### Key Metrics

| Metric | Tool | Alert Threshold |
|--------|------|-----------------|
| Queue depth | RQ Dashboard, Prometheus | > 100 for 10 min |
| Job completion rate | Custom metrics endpoint | < 10/min for 5 min |
| API p95 latency | FastAPI `/metrics`, Prometheus | > 1000ms for 5 min |
| Postgres CPU | CloudWatch, Stackdriver, Azure Monitor | > 85% for 10 min |
| Redis memory | CloudWatch, Stackdriver, Azure Monitor | > 80% for 5 min |
| Worker health | RQ worker heartbeats | No heartbeat for 5 min |

### Dashboards

- **Grafana + Prometheus:** Real-time queue depth, job throughput, API latency
- **RQ Dashboard:** Worker status, failed jobs, queue size
- **Cloud provider metrics:** Postgres/Redis CPU, memory, disk I/O

### Alerting Channels

- **PagerDuty / Opsgenie:** Critical alerts (queue depth, API outage)
- **Slack / Discord:** Warnings (high latency, worker restarts)
- **Email:** Daily capacity reports

---

## 9. Scaling Playbook (Operator Runbook)

### Scenario: Queue depth > 100 for 10 minutes

**Diagnosis:**

1. Check RQ dashboard: queue size, failed jobs, worker health
2. Check API logs: HTTP 429 (rate limit) or 503 (overload)
3. Check Postgres: slow queries, connection pool exhaustion

**Action:**

```bash
# Scale Tier 2-4 workers to 10
docker compose up -d --scale worker-tier234=10

# Monitor queue depth for 5 minutes
watch -n 10 'docker exec redis redis-cli llen rq:queue:tier2'
```

### Scenario: Tier 1 jobs queued > 20

**Diagnosis:**

1. Check Multilogin: profile health, session timeouts
2. Check Tier 1 worker logs: LinkedIn anti-bot measures, network errors

**Action:**

```bash
# Option A: Add Multilogin profile to existing host (if < 3 profiles/host)
# 1. Create new Multilogin profile in web UI
# 2. Update backend/.env.production:
#    MULTILOGIN_PROFILE_IDS=profile1,profile2,profile3
# 3. Restart Tier 1 worker:
docker compose restart worker-tier1

# Option B: Deploy on new physical host
# 1. Provision new VM with Docker + Multilogin
# 2. Clone repo, copy .env.production
# 3. Start Tier 1 worker on new host
```

### Scenario: API p95 latency > 1000ms

**Diagnosis:**

1. Check API logs: slow enrichers, DB queries
2. Check Postgres: connection pool size, slow queries
3. Check Redis: memory usage, eviction policy

**Action:**

```bash
# Scale API instances to 4
docker compose up -d --scale api=4

# Check slow queries in Postgres
docker exec postgres psql -U hyper -d hyper -c \
  "SELECT query, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"
```

---

## 10. Future Work

- [ ] Kubernetes HPA for Tier 2-4 workers (metrics-based autoscaling)
- [ ] CloudWatch / Stackdriver autoscaling policies (queue depth triggers)
- [ ] Grafana dashboards for capacity planning (queue depth, throughput, latency)
- [ ] Load testing with real Tier 1 / Multilogin (smoke + full profiles)
- [ ] Cost optimization: spot instances for Tier 2-4 workers
- [ ] Multi-region deployment for low-latency global enrichment

---

## References

- [LOAD_TESTING.md](../backend/docs/LOAD_TESTING.md) — k6 harness, thresholds, smoke/full profiles
- [e2e-evidence/2026-07-20-load-test-smoke.md](../backend/docs/e2e-evidence/2026-07-20-load-test-smoke.md) — Smoke test results
- [ARCHITECTURE.md](../backend/docs/ARCHITECTURE.md) — Enrichment pipeline, tier responsibilities
- [DEPLOYMENT.md](DEPLOYMENT.md) — Docker Compose production setup
