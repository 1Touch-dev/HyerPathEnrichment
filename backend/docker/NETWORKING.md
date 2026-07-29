# Docker Networking Architecture

This document explains the hybrid networking architecture used in the Hyrepath Enrichment backend infrastructure.

## Overview

The backend uses a **hybrid networking approach** that combines:
- **Bridge networking** (default) for most services
- **Host networking** (only for Tier 1 worker) when using containerized Multilogin

This design balances **scalability**, **isolation**, and **technical requirements** for browser automation.

## Network Topology

```
┌────────────────────────────────────────────────────────────────┐
│                    BRIDGE NETWORK (Default)                    │
│                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                │
│  │   API    │───▶│ Postgres │    │  Redis   │                │
│  │  :8000   │    │  :5432   │    │  :6379   │                │
│  └──────────┘    └──────────┘    └──────────┘                │
│       │                                  ▲                     │
│       │                                  │                     │
│       ▼                                  │                     │
│  ┌──────────────────────────────────────┴─────────┐           │
│  │         Tier 2-4 Workers (Scalable)            │           │
│  │  • Handle hunting (Sherlock, Maigret)          │           │
│  │  • OSINT (gitrecon, email tools)               │           │
│  │  • Jobs & business (JobSpy, Google Maps)       │           │
│  └─────────────────┬────────────────────┬─────────┘           │
│                    │                    │                     │
│                    ▼                    ▼                     │
│          ┌──────────────┐    ┌─────────────────┐             │
│          │   Sidecars   │    │  External Proxy │             │
│          │ (email, gmaps│    │  (Oxylabs)      │             │
│          │  analyzer)   │    │  Internet       │             │
│          └──────────────┘    └─────────────────┘             │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│              HOST NETWORK (Tier 1 Only)                        │
│                                                                 │
│  ┌──────────────────────────────────────────┐                 │
│  │  Linux Host's 127.0.0.1 Loopback         │                 │
│  │                                           │                 │
│  │  ┌────────────────┐  ┌─────────────────┐ │                 │
│  │  │  Multilogin    │  │ Tier 1 Worker   │ │                 │
│  │  │  Container     │◀─│ Container       │ │                 │
│  │  │                │  │                 │ │                 │
│  │  │ Binds Selenium │  │ Connects via    │ │                 │
│  │  │ to 127.0.0.1   │  │ 127.0.0.1       │ │                 │
│  │  └────────────────┘  └─────────────────┘ │                 │
│  │                                           │                 │
│  │  Shared loopback = Communication works!  │                 │
│  └──────────────────────────────────────────┘                 │
│                                                                 │
│  Tier 1 worker also reaches postgres/redis via 127.0.0.1      │
└────────────────────────────────────────────────────────────────┘
```

## Why Hybrid Networking?

### Bridge Network (Default) - Used By:
- API service
- Tier 2-4 workers
- PostgreSQL
- Redis
- All sidecar services (email-verifier, social-analyzer, google-maps-scraper, etc.)

**Benefits:**
1. **Service Discovery**: Automatic DNS resolution via Docker (e.g., `postgres:5432`)
2. **Scalability**: Can run multiple instances without port conflicts
3. **Isolation**: Each container has its own network namespace
4. **Maintainability**: Clear service boundaries and easier debugging

**Service Resolution:**
```bash
# In bridge network containers
DATABASE_URL=postgresql+asyncpg://hyrepath:password@postgres:5432/hyrepath
REDIS_URL=redis://redis:6379/0
EMAIL_VERIFIER_URL=http://email-verifier:8080
```

### Host Network - Used By:
- Tier 1 worker (LinkedIn photo scraping)
- Multilogin container (when containerized on Linux)

**Why Required for Tier 1:**

Multilogin binds its Selenium ChromeDriver ports to `127.0.0.1` (localhost) **ONLY**, not `0.0.0.0` (all interfaces). This is a security design choice by Multilogin.

**The Problem with Bridge Network:**
```
Container A (Multilogin):
├─ Has IP: 172.18.0.5
├─ Binds Selenium to: 127.0.0.1:9222 (its own loopback)
└─ This port is NOT accessible from other containers

Container B (Worker):
├─ Has IP: 172.18.0.6
├─ Its 127.0.0.1 is DIFFERENT from Container A's 127.0.0.1
└─ Cannot reach Multilogin's Selenium port ❌
```

**The Solution with Host Network:**
```
Both containers:
├─ Share the Linux host's network namespace
├─ Share the SAME 127.0.0.1 loopback interface
├─ Multilogin binds to: 127.0.0.1:9222
└─ Worker connects to: 127.0.0.1:9222 ✅ WORKS!
```

**Service Resolution in Host Network:**
```bash
# Tier 1 worker must use 127.0.0.1
DATABASE_URL=postgresql+asyncpg://hyrepath:password@127.0.0.1:5432/hyrepath
REDIS_URL=redis://127.0.0.1:6379/0
MULTILOGIN_SELENIUM_HOST=http://127.0.0.1
```

## Configuration Files

### 1. Environment Variables (`.env.production`)

The `.env.production` file uses **bridge network service names** by default:

```bash
# Default for bridge network services
DATABASE_URL=postgresql+asyncpg://hyrepath:${POSTGRES_PASSWORD}@postgres:5432/hyrepath
REDIS_URL=redis://redis:6379/0
EMAIL_VERIFIER_URL=http://email-verifier:8080
SOCIAL_ANALYZER_URL=http://social-analyzer:9005
```

**Tier 1 worker overrides these** in `docker-compose.tier-workers.yml`:

```yaml
worker-tier1:
  network_mode: host
  environment:
    DATABASE_URL: postgresql+asyncpg://hyrepath:${POSTGRES_PASSWORD}@127.0.0.1:5432/hyrepath
    REDIS_URL: redis://127.0.0.1:6379/0
    # ... overrides all URLs to 127.0.0.1
```

### 2. Docker Compose Files

**`docker-compose.yml`** (base):
- All services use bridge network by default
- No `network_mode` specified = bridge

**`docker-compose.prod.yml`** (production overlay):
- Uses bridge network service names
- Port bindings restricted to `127.0.0.1` for security

**`docker-compose.tier-workers.yml`** (tier-specific workers):
- `worker-tier1`: **Explicit `network_mode: host`**
- `worker-tier234`: **No `network_mode` (bridge by default)**

**`docker-compose.multilogin.yml`** (Linux containerized Multilogin):
- `multilogin`: **`network_mode: host`**
- `worker`: **Overridden to `network_mode: host`** (if using this overlay)

## Scaling Workers

### Scaling Tier 2-4 Workers (Bridge Network)

You can horizontally scale tier 2-4 workers because they use bridge networking:

```bash
cd backend/docker

# Start with 5 tier 2-4 workers
docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier-workers.yml \
  --env-file ../.env.production \
  up -d --scale worker-tier234=5

# No port conflicts! Each container gets its own network namespace
```

### Tier 1 Worker (Host Network) - Cannot Scale

You **cannot** run multiple Tier 1 workers with host networking:

```bash
# This FAILS with port conflicts
docker compose up -d --scale worker-tier1=2
# Error: Both workers try to bind the same ports on 127.0.0.1
```

**Limitation:** Host network mode means all containers share the host's ports. Only one Tier 1 worker instance is supported.

**Workaround:** If you need more Tier 1 capacity:
1. Run on multiple physical/virtual machines
2. Use a load balancer to distribute Tier 1 jobs
3. Increase `TIER1_MAX_CONCURRENT` in `.env.production`

## Troubleshooting

### Worker Cannot Connect to Database

**Symptom:**
```
ERROR: could not translate host name "postgres" to address
```

**Diagnosis:**
- Worker is on host network but trying to use service name `postgres`

**Solution:**
- Ensure Tier 1 worker has `DATABASE_URL` with `127.0.0.1`, not `postgres`
- Check `docker-compose.tier-workers.yml` has correct environment overrides

### Tier 1 Worker Cannot Reach Multilogin

**Symptom:**
```
ERROR: Connection refused to http://127.0.0.1:9222
```

**Diagnosis:**
1. Check Multilogin is running: `docker ps | grep multilogin`
2. Verify host network: `docker inspect hyrepath-multilogin | grep NetworkMode`
3. Check Tier 1 worker network: `docker inspect docker-worker-tier1-1 | grep NetworkMode`

**Solution:**
- Both must use `network_mode: host`
- Verify with: `docker compose config | grep -A5 "worker-tier1"`

### Services Cannot Resolve Each Other

**Symptom:**
```
ERROR: could not translate host name "redis" to address
```

**Diagnosis:**
- Service is using bridge network but environment variable has `127.0.0.1`

**Solution:**
- Check `.env.production` uses service names for bridge network
- Verify `docker-compose.prod.yml` doesn't override with `127.0.0.1`

### Port Conflicts When Scaling

**Symptom:**
```
ERROR: Bind for 0.0.0.0:8080 failed: port is already allocated
```

**Diagnosis:**
- Trying to scale a service with fixed port bindings
- Or scaling a host-network service

**Solution:**
- Only scale services without explicit port bindings (tier234 workers)
- Remove port bindings from scaled services in compose file
- Use bridge networking for scalable services

## Network Testing

### Test Bridge Network Service Discovery

From any bridge-network container:

```bash
# Enter API container
docker exec -it docker-api-1 bash

# Test DNS resolution
ping postgres
ping redis
ping email-verifier

# Test connectivity
curl http://email-verifier:8080/v1/health@test@example.com/verification
```

### Test Host Network Loopback Sharing

From Tier 1 worker:

```bash
# Enter Tier 1 worker
docker exec -it docker-worker-tier1-1 bash

# Test loopback connectivity
curl -k https://127.0.0.1:45001/api/v1/version  # Multilogin API
redis-cli -h 127.0.0.1 ping  # Redis
psql -h 127.0.0.1 -U hyrepath -d hyrepath -c "SELECT 1;"  # Postgres
```

## Best Practices

1. **Default to Bridge Network**: Unless you have a specific technical requirement (like Multilogin), use bridge networking

2. **Use Service Names**: In `.env.production`, prefer service names over `127.0.0.1`:
   ```bash
   # Good (bridge network)
   DATABASE_URL=postgresql://user:pass@postgres:5432/db

   # Bad (hard to maintain)
   DATABASE_URL=postgresql://user:pass@172.18.0.5:5432/db
   ```

3. **Override Only When Needed**: Let `docker-compose.tier-workers.yml` override URLs for Tier 1, don't duplicate in `.env`

4. **Document Network Mode**: If a service needs host networking, document WHY in the compose file

5. **Test Network Connectivity**: After changes, verify services can reach each other:
   ```bash
   # From API container
   docker exec docker-api-1 python -c "import redis; r = redis.from_url('redis://redis:6379'); r.ping()"
   ```

6. **Validate Before Deploy**: Run `bash backend/scripts/validate_env.sh` before starting infrastructure

## Architecture Decision Records

For more context on why these networking decisions were made:

- **ADR-0008**: Tier 1 Linux Host Network Architecture
- See `docs/adr/` for full ADR documentation

## Quick Reference

| Component | Network Mode | Service Resolution | Scalable? |
|-----------|-------------|-------------------|-----------|
| API | Bridge | `postgres:5432` | ✅ Yes |
| Tier 2-4 Workers | Bridge | `postgres:5432` | ✅ Yes |
| Tier 1 Worker | Host | `127.0.0.1:5432` | ❌ No |
| PostgreSQL | Bridge | N/A | ❌ No (stateful) |
| Redis | Bridge | N/A | ❌ No (stateful) |
| Sidecars | Bridge | N/A | ✅ Yes |
| Multilogin | Host | `127.0.0.1` only | ❌ No |

## Summary

The hybrid networking approach:
- ✅ Maximizes scalability for Tier 2-4 workers
- ✅ Maintains proper isolation with bridge networking
- ✅ Enables Tier 1 to reach Multilogin's localhost-only ports
- ✅ Uses Docker's built-in service discovery where possible
- ✅ Minimizes configuration complexity

**Key Takeaway:** Bridge networking is the default and preferred approach. Host networking is only used for Tier 1 due to Multilogin's technical constraint of binding to `127.0.0.1`.
