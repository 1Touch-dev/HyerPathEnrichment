# 🐳 Complete Container Architecture & Data Flow

**HyerEnrichment Platform - Docker Container Inventory**

**Total Container Count:** 27 containers (varies by profile)

---

## 📊 Quick Summary

| Category | Count | When Active |
|----------|-------|-------------|
| Core Infrastructure | 4 | Always |
| Core Workers | 3 | Always |
| Free Sidecars | 3 | Always |
| Tier-Specific Workers | 2 | Optional (`tier-workers.yml`) |
| Multilogin | 1 | Optional (Linux production) |
| Foundation Workers | 2 | Optional (`foundation.yml`) |
| Paid Services | 2 | Optional (`--profile paid`) |
| LLM Services | 2 | Optional (`--profile llm`) |
| Observability | 5 | Optional (`--profile observability`) |

---

## 🏗️ Core Infrastructure (Always Running) - 4 Containers

### 1. **postgres**
- **Purpose:** PostgreSQL database with pgvector extension
- **Port:** 5432 (internal), 5433 (host)
- **Data Storage:**
  - `enrichment_jobs` - Job status, input, results (JSONB)
  - `users` - Auth users with email verification
  - `refresh_tokens` - Token rotation tracking
  - `token_blacklist` - Revoked JTIs
  - `auth_audit_logs` - Login/logout events
  - `audit_logs` - Compliance audit trail
  - `suppression_list` - Opt-out SHA256 hashes
  - `candidate_documents` - CV/resume metadata
  - `candidate_embeddings` - pgvector embeddings
- **Data Flow:**
  - **IN:** SQL queries from API/workers
  - **OUT:** Job status, dossiers, audit logs, users, tokens

### 2. **redis**
- **Purpose:** Job queue (RQ) + cache + token blacklist + rate limiting
- **Port:** 6379
- **Queues:**
  - `default` - General enrichment jobs
  - `tier1` - LinkedIn photo jobs (per_tier mode)
  - `tier234` - API enrichers (per_tier mode)
  - `email` - Email verification jobs
  - `document_processing` - PDF/DOCX parsing
  - `embedding_generation` - Vector embeddings
- **Data Flow:**
  - **IN:** Job enqueue from API, blacklist writes from auth
  - **OUT:** Job dequeue to workers, cached suppression reads

### 3. **migrate**
- **Purpose:** One-shot Alembic database migration
- **Lifecycle:** Runs once at startup, exits on success
- **Data Flow:**
  - **IN:** Alembic migration scripts
  - **OUT:** Updated Postgres schema
- **Dependencies:** Postgres must be healthy

### 4. **api**
- **Purpose:** FastAPI REST API server
- **Port:** 8000
- **Endpoints:**
  - `POST /api/enrich` - Enqueue async job
  - `POST /api/enrich/sync` - Inline enrichment
  - `GET /api/jobs/{id}` - Poll job status
  - `POST /auth/login` - Cookie auth + refresh tokens
  - `POST /auth/refresh` - Token rotation
  - `POST /auth/logout` - Token blacklist
  - `POST /api/opt-out` - Suppression (public)
  - `POST /api/dsar` - Data access request (authenticated)
- **Data Flow:**
  - **IN:** HTTP requests from Next.js frontend
  - **OUT:** Enqueues jobs to Redis, writes to Postgres
- **Calls:** social-analyzer, google-maps-scraper, email-verifier (sync mode)

---

## ⚙️ Core Workers (Always Running) - 3 Containers

### 5. **worker**
- **Purpose:** Default RQ worker for general enrichment (Tier 2-4)
- **Queue:** `default` (or `tier234` if `WORKER_QUEUE_MODE=per_tier`)
- **Process:** Dequeue → Pipeline → Enrichers → Merge → Write to Postgres
- **Calls:**
  - social-analyzer (social handles)
  - google-maps-scraper (business data)
  - email-verifier (email validation)
  - litellm (disambiguation)
- **Data Flow:**
  - **IN:** Jobs from Redis `default` queue
  - **OUT:** Enriched dossiers → Postgres

### 6. **worker-email**
- **Purpose:** SendGrid email worker for verification emails
- **Queue:** `email`
- **Process:** Dequeue → Format email → SendGrid API
- **Data Flow:**
  - **IN:** Email jobs from Redis `email` queue
  - **OUT:** SMTP emails via SendGrid API

### 7. **worker-cleanup**
- **Purpose:** Detects and fixes orphaned/stuck jobs
- **Interval:** Every 5 minutes (configurable via `CLEANUP_INTERVAL_SECONDS`)
- **Process:** Scan Postgres for stuck jobs → Retry or mark failed
- **Data Flow:**
  - **IN:** Scans Postgres + Redis for orphaned jobs
  - **OUT:** Updates job status in Postgres

---

## 🎯 Free-Mode Sidecars (Always Running) - 3 Containers

### 8. **social-analyzer**
- **Purpose:** AGPL social media handle finder
- **Port:** 9005
- **Technology:** Node.js HTTP server
- **Process:** HTTP POST with name/email → scrape/API calls → return JSON
- **Data Flow:**
  - **IN:** HTTP POST from API/workers with `{"name": "...", "email": "..."}`
  - **OUT:** JSON with social profiles (GitHub, X, Reddit, etc.)

### 9. **google-maps-scraper**
- **Purpose:** AGPL business location scraper for Google Maps
- **Port:** 8080
- **Technology:** Go binary + Playwright browser automation
- **Process:** HTTP POST with business query → scrape Maps → return place data
- **Data Flow:**
  - **IN:** HTTP POST with `{"query": "business name + location"}`
  - **OUT:** JSON with business details, address, phone, photos

### 10. **email-verifier**
- **Purpose:** Basic SMTP email verification
- **Port:** 8080 (internal), 8081 (host)
- **Process:** DNS MX lookup + SMTP handshake → return deliverability
- **Data Flow:**
  - **IN:** HTTP GET `/v1/health@example.com/verification`
  - **OUT:** JSON verification status (syntax, MX, SMTP)

---

## 🔧 Tier-Specific Workers (Optional) - 2 Containers

### 11. **worker-tier1**
- **Purpose:** Heavy browser automation for LinkedIn photo scraping
- **Queue:** `tier1` (requires `WORKER_QUEUE_MODE=per_tier`)
- **Network:** **Host network mode** (shares 127.0.0.1 with multilogin)
- **Process:**
  1. Dequeue job from Redis `tier1` queue
  2. Send Selenium commands to multilogin (127.0.0.1)
  3. LinkedIn login + photo scrape
  4. Download photo → R2/local cache
  5. Write metadata → Postgres
- **Special:** Uses Multilogin stealth browser to avoid LinkedIn detection
- **Concurrency:** 1-2 instances (heavy resource usage)
- **Data Flow:**
  - **IN:** Jobs from Redis `tier1` queue
  - **OUT:** Photos → R2/local cache, metadata → Postgres

### 12. **worker-tier234**
- **Purpose:** Lightweight API enrichers (scalable to N instances)
- **Queue:** `tier234`
- **Network:** Bridge network (uses Docker service names)
- **Scalable:** `docker compose up -d --scale worker-tier234=8`
- **Process:** Same as default worker but isolated queue
- **Data Flow:**
  - **IN:** Jobs from Redis `tier234` queue
  - **OUT:** OSINT data → Postgres

---

## 🌐 Multilogin Container (Linux Production) - 1 Container

### 13. **multilogin**
- **Purpose:** Containerized stealth browser for anti-detection
- **Network:** **Host network mode** (binds Selenium to 127.0.0.1)
- **Technology:** Multilogin X desktop app in Docker
- **Process:**
  - Runs Selenium server on ephemeral ports (e.g., `127.0.0.1:35001`)
  - Per-profile browser instances with fingerprint randomization
- **Why Host Network:**
  - Multilogin binds Selenium ports to `127.0.0.1` only (not `0.0.0.0`)
  - worker-tier1 must share the same loopback to reach these ports
  - Both containers in host mode share Linux host's 127.0.0.1 namespace
- **Data Flow:**
  - **IN:** Selenium commands from worker-tier1 (HTTP over 127.0.0.1)
  - **OUT:** Browser sessions with LinkedIn

---

## 📄 Foundation Workers (Document Processing) - 2 Containers

### 14. **worker-document**
- **Purpose:** Parse CV/resume files (PDF, DOCX)
- **Queue:** `document_processing`
- **Technology:** Python libraries (PyPDF2, python-docx)
- **Process:**
  1. Dequeue document job
  2. Parse with libraries
  3. Extract text + metadata
  4. Upload to R2/local cache
  5. Write metadata → Postgres
- **Resource Limits:** 2 CPU, 1GB RAM
- **Data Flow:**
  - **IN:** Document jobs from Redis `document_processing` queue
  - **OUT:** Parsed text → Postgres, files → R2/local

### 15. **worker-embedding**
- **Purpose:** Generate OpenAI embeddings for semantic search
- **Queue:** `embedding_generation`
- **Technology:** OpenAI API + pgvector
- **Process:**
  1. Dequeue embedding job
  2. Call OpenAI API (text-embedding-3-small)
  3. Store vector in Postgres pgvector column
- **Resource Limits:** 1 CPU, 512MB RAM
- **Data Flow:**
  - **IN:** Embedding jobs from Redis `embedding_generation` queue
  - **OUT:** Vectors → Postgres (`candidate_embeddings` table with pgvector)

---

## 💰 Paid Services (`--profile paid`) - 2 Containers

### 16. **reacher**
- **Purpose:** Deep SMTP email verification
- **Port:** 8082
- **Technology:** Rust binary (reacherhq/backend)
- **Features:** Catch-all detection, disposable email detection, mailbox full check
- **Cost:** Self-hosted (free), but requires dedicated IP for SMTP
- **Data Flow:**
  - **IN:** HTTP POST from workers with email
  - **OUT:** JSON with detailed deliverability score

### 17. **scrapoxy**
- **Purpose:** Rotating proxy pool manager
- **Technology:** Node.js proxy orchestrator
- **Use Case:** Rate limit avoidance for Tier 2-4 enrichers
- **Cost:** ~$50-200/month depending on provider (Oxylabs, etc.)
- **Data Flow:**
  - **IN:** HTTP requests from workers (Tier 2-4)
  - **OUT:** Proxied responses via rotating IPs

---

## 🤖 LLM Services (`--profile llm`) - 2 Containers

### 18. **litellm**
- **Purpose:** Unified LLM proxy for OpenAI/Gemini/Claude
- **Port:** 4000
- **Technology:** Python FastAPI proxy
- **Use Case:** Name disambiguation, low-confidence handle matching
- **Cost:** $0.10-5.00 per 1K enrichments (depends on model)
- **Data Flow:**
  - **IN:** HTTP POST from workers with disambiguation prompt
  - **OUT:** LLM completion (JSON structured)

### 19. **ollama**
- **Purpose:** Self-hosted local LLM inference
- **Technology:** Ollama runtime (Llama 3.1, Mistral, etc.)
- **Use Case:** Free alternative to OpenAI for disambiguation
- **Cost:** Free (but requires GPU for good performance)
- **Data Flow:**
  - **IN:** HTTP POST from workers with prompt
  - **OUT:** LLM completion

---

## 📊 Observability (`--profile observability`) - 5 Containers

### 20. **langfuse**
- **Purpose:** LLM observability and tracing
- **Port:** 3002
- **Technology:** Next.js dashboard + PostgreSQL
- **Features:** Traces, costs, latency, prompt versioning
- **Cost:** Self-hosted (free), OpenAI API costs apply
- **Data Flow:**
  - **IN:** Traces from API/workers (LLM calls)
  - **OUT:** Dashboard UI for analysis

### 21. **changedetection**
- **Purpose:** Website change monitoring
- **Port:** 5000
- **Technology:** Python + Playwright
- **Use Case:** Monitor competitor pricing, track profile changes
- **Cost:** Free (self-hosted)
- **Data Flow:**
  - **IN:** Configured URLs to monitor
  - **OUT:** Webhooks on change detection

### 22. **glitchtip-web**
- **Purpose:** Self-hosted Sentry-compatible error tracking UI
- **Port:** 8001
- **Technology:** Django web app
- **Cost:** Free (self-hosted)
- **Data Flow:**
  - **IN:** Sentry DSN events from API/workers
  - **OUT:** Error dashboard UI

### 23. **glitchtip-worker**
- **Purpose:** Celery worker for GlitchTip background tasks
- **Technology:** Python Celery worker
- **Process:** Process error events asynchronously
- **Data Flow:**
  - **IN:** Error events from Redis
  - **OUT:** Processed errors → Postgres

### 24. **glitchtip-migrate**
- **Purpose:** One-shot GlitchTip schema migration
- **Lifecycle:** Runs once at startup, exits on success
- **Data Flow:**
  - **IN:** Django migrations
  - **OUT:** GlitchTip schema in Postgres (`glitchtip` database)

---

## 🔄 Complete Data Flow Diagrams

### **Async Enrichment Flow (POST /api/enrich)**

```
┌─────────┐      ┌──────────┐      ┌─────┐      ┌─────────┐
│  User   │─────▶│ Next.js  │─────▶│ API │─────▶│  Redis  │
│ Browser │      │ Frontend │      │     │      │ (queue) │
└─────────┘      └──────────┘      └─────┘      └─────────┘
                                       │               │
                                       │               │ dequeue
                                       │               ▼
                                       │         ┌──────────┐
                                       │         │  Worker  │
                                       │         │          │
                                       │         └─────┬────┘
                                       │               │
                                       │         ┌─────▼────────┐
                                       │         │ Enrichers    │
                                       │         │ - social     │
                                       │         │ - gmaps      │
                                       │         │ - email      │
                                       │         │ - litellm    │
                                       │         └─────┬────────┘
                                       │               │
                                       ▼               ▼
                                  ┌──────────────────────┐
                                  │     Postgres         │
                                  │ (enrichment_jobs)    │
                                  └──────────────────────┘
                                       │
                                       │ poll status
                                       ▼
                                  ┌─────┐      ┌──────────┐      ┌─────────┐
                                  │ API │─────▶│ Next.js  │─────▶│  User   │
                                  └─────┘      │ Frontend │      │ Browser │
                                               └──────────┘      └─────────┘
```

### **LinkedIn Photo Flow (Tier 1)**

```
┌─────┐      ┌─────────┐      ┌───────────────┐
│ API │─────▶│  Redis  │─────▶│ worker-tier1  │
└─────┘      │  tier1  │      │ (host network)│
             │  queue  │      └───────┬───────┘
             └─────────┘              │
                                      │ Selenium commands
                                      │ via 127.0.0.1
                                      ▼
                              ┌────────────────┐
                              │  multilogin    │
                              │ (host network) │
                              │ 127.0.0.1:XXXXX│
                              └───────┬────────┘
                                      │
                                      │ scrape
                                      ▼
                              ┌────────────────┐
                              │   LinkedIn     │
                              │  (download     │
                              │   photo)       │
                              └───────┬────────┘
                                      │
                    ┌─────────────────┴────────────────┐
                    │                                  │
                    ▼                                  ▼
            ┌───────────────┐                  ┌──────────┐
            │ R2 / Local    │                  │ Postgres │
            │ Photo Cache   │                  │ metadata │
            └───────────────┘                  └──────────┘
```

### **Authentication Flow**

```
POST /auth/login
       │
       ▼
┌──────────────────┐
│ API validate     │
│ email + password │
└────────┬─────────┘
         │
         ▼
┌────────────────────┐
│ Postgres           │
│ (users table)      │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐      ┌──────────────────┐
│ Create tokens:     │      │ Set HttpOnly     │
│ - access (15min)   │─────▶│ cookies:         │
│ - refresh (7d)     │      │ - access_token   │
└────────────────────┘      │ - refresh_token  │
         │                  └──────────────────┘
         │
         ▼
┌────────────────────┐
│ Redis + Postgres   │
│ (token tracking)   │
└────────────────────┘
```

### **Token Refresh Flow (with Rotation)**

```
POST /auth/refresh (with refresh_token cookie)
       │
       ▼
┌──────────────────────────────┐
│ Validate refresh token       │
│ - Check expiry               │
│ - Detect reuse (security)    │
└────────────┬─────────────────┘
             │
             ├─────────────────────────────┐
             │                             │
        Valid & Unused                 Already Used
             │                             │
             ▼                             ▼
┌─────────────────────────┐    ┌──────────────────────┐
│ Mark old token as used  │    │ SECURITY BREACH:     │
│ Create new token        │    │ Revoke entire family │
│ (with parent tracking)  │    │ Force re-login       │
└────────────┬────────────┘    └──────────────────────┘
             │
             ▼
┌─────────────────────────┐
│ Set new cookies:        │
│ - new access_token      │
│ - new refresh_token     │
└─────────────────────────┘
```

---

## 🌐 Network Architecture

### **Hybrid Networking Strategy**

The platform uses **two network modes** based on container requirements:

#### **Bridge Network** (Default - Most Containers)
- **Containers:** api, workers, sidecars, postgres, redis
- **DNS:** Automatic service discovery (e.g., `postgres:5432`)
- **Benefits:** Isolation, scalability, standard Docker patterns
- **Use Cases:** API, Tier 2-4 workers, all sidecars

#### **Host Network** (Tier 1 Only)
- **Containers:** worker-tier1, multilogin
- **Reason:** Multilogin binds Selenium ports to `127.0.0.1` only (not `0.0.0.0`)
- **How It Works:** Both containers share the Linux host's network namespace
- **Result:** `127.0.0.1` is shared between containers
- **Limitation:** Cannot scale (port conflicts)

### **Why This Matters**

```
┌─────────────────────────────────────────────────────┐
│ Bridge Network (worker-tier234)                     │
│                                                     │
│  postgres:5432  ──▶  Works (Docker DNS)            │
│  redis:6379     ──▶  Works (Docker DNS)            │
│  multilogin:XXXXX ──▶  FAILS (not in bridge)       │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ Host Network (worker-tier1 + multilogin)            │
│                                                     │
│  127.0.0.1:5433 ──▶  postgres (via host port)      │
│  127.0.0.1:6379 ──▶  redis (via host port)         │
│  127.0.0.1:XXXXX ──▶  multilogin Selenium (WORKS!) │
└─────────────────────────────────────────────────────┘
```

---

## 📦 Production Deployment Scenarios

### **Minimal Production** (10 containers)
```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  up -d
```
**Containers:** postgres, redis, migrate, api, worker, worker-email, worker-cleanup, social-analyzer, google-maps-scraper, email-verifier

**Use Case:** Basic enrichment without LinkedIn photos

---

### **With Tier 1** (LinkedIn Photos) - 12 containers
```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier1.yml \
  -f docker-compose.multilogin.yml \
  up -d
```
**Added:** worker-tier1, multilogin

**Use Case:** Full enrichment with LinkedIn photo scraping

---

### **With Tier Splitting** (Scalable) - 13+ containers
```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier-workers.yml \
  -f docker-compose.multilogin.yml \
  up -d --scale worker-tier234=8
```
**Added:** worker-tier1, worker-tier234 (scaled to 8), multilogin

**Use Case:** High-throughput enrichment with horizontal scaling

---

### **With Foundation** (CV Parsing) - 15 containers
```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.foundation.yml \
  up -d
```
**Added:** worker-document, worker-embedding

**Use Case:** Candidate platform with CV parsing + vector search

---

### **Full Production** (All Features) - 23+ containers
```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier-workers.yml \
  -f docker-compose.multilogin.yml \
  -f docker-compose.foundation.yml \
  --profile paid \
  --profile llm \
  --profile observability \
  up -d --scale worker-tier234=8
```
**All containers active**

**Use Case:** Enterprise deployment with full observability

---

## 🧠 Key Architectural Decisions

### **1. Queue Splitting (`WORKER_QUEUE_MODE=per_tier`)**
- **Problem:** Heavy Tier 1 jobs block lightweight Tier 2-4 jobs
- **Solution:** Separate queues (`tier1`, `tier234`) with dedicated workers
- **Benefit:** Horizontal scaling for API enrichers, isolated resource management

### **2. Dual-Write Pattern**
- **Token Blacklist:** Redis (fast lookup) + Postgres (durability)
- **Suppression List:** Redis (cache) + Postgres (source of truth)
- **Benefit:** Speed + reliability + audit trail

### **3. Graceful Degradation**
- **Missing Sidecars:** Return empty fragments instead of crashing
- **Missing LLM:** Fall back to heuristic stub
- **Missing R2:** Fall back to local `.asset-cache/`
- **Benefit:** Platform stays functional even with missing dependencies

### **4. Profile-Based Opt-In**
- **Free Services:** Always on (social-analyzer, gmaps, email-verifier)
- **Paid Services:** `--profile paid` (reacher, scrapoxy)
- **Observability:** `--profile observability` (langfuse, glitchtip)
- **Benefit:** Zero-cost free tier, pay only for what you use

### **5. Host Network for Tier 1**
- **Problem:** Multilogin binds Selenium to `127.0.0.1` only
- **Solution:** Both worker-tier1 and multilogin use `network_mode: host`
- **Trade-off:** Cannot scale Tier 1 workers (port conflicts)
- **Benefit:** Works on bare Linux without TCP proxy hacks

---

## 📊 Container Resource Usage

| Container | CPU | Memory | Disk | Notes |
|-----------|-----|--------|------|-------|
| postgres | 1-2 | 512MB-2GB | 10GB+ | Grows with data |
| redis | 0.5 | 256MB | 1GB | Append-only file |
| api | 1 | 512MB | - | Per replica |
| worker | 1 | 512MB-1GB | - | Depends on enrichers |
| worker-tier1 | 2 | 2GB | 5GB | Heavy browser automation |
| worker-tier234 | 0.5 | 256MB | - | Lightweight, scalable |
| multilogin | 2 | 2GB | 2GB | Stealth browser |
| social-analyzer | 0.5 | 256MB | - | Node.js sidecar |
| google-maps-scraper | 1 | 512MB | 2GB | Playwright browser |
| worker-document | 2 | 1GB | 5GB | PDF parsing |
| worker-embedding | 1 | 512MB | - | OpenAI API calls |
| litellm | 0.5 | 256MB | - | Proxy only |
| langfuse | 1 | 512MB | - | Dashboard |
| glitchtip-web | 1 | 512MB | - | Error tracking UI |

**Total (Minimal):** ~4-8 CPU, 4-8GB RAM
**Total (Full):** ~15-25 CPU, 15-30GB RAM

---

## 🚀 Quick Reference Commands

### **Start Minimal Production**
```bash
cd backend/docker
docker compose \
  --env-file ../.env.production \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  up -d
```

### **Start with Tier 1 (Linux)**
```bash
cd backend/docker
docker compose \
  --env-file ../.env.production \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier1.yml \
  -f docker-compose.multilogin.yml \
  up -d
```

### **Start with Tier Splitting (Scalable)**
```bash
cd backend/docker
docker compose \
  --env-file ../.env.production \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier-workers.yml \
  -f docker-compose.multilogin.yml \
  up -d --scale worker-tier234=8
```

### **Start Full Stack (All Profiles)**
```bash
cd backend/docker
docker compose \
  --env-file ../.env.production \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier-workers.yml \
  -f docker-compose.multilogin.yml \
  -f docker-compose.foundation.yml \
  --profile paid \
  --profile llm \
  --profile observability \
  up -d --scale worker-tier234=8
```

### **View Logs**
```bash
# All containers
docker compose logs -f

# Specific container
docker compose logs -f worker-tier1

# API only
docker compose logs -f api
```

### **Check Health**
```bash
docker compose ps
```

### **Stop All**
```bash
docker compose down
```

### **Stop and Remove Volumes**
```bash
docker compose down -v
```

---

## 🔍 Troubleshooting

### **Container Won't Start**
```bash
# Check logs
docker compose logs <container-name>

# Check health
docker inspect <container-name> | grep -A 20 Health
```

### **Tier 1 Worker Can't Reach Multilogin**
```bash
# Verify both use host network
docker inspect worker-tier1 | grep NetworkMode
docker inspect hyrepath-multilogin | grep NetworkMode

# Test Selenium port
curl -v http://127.0.0.1:35001  # Replace with actual port
```

### **Worker Can't Reach Sidecars**
```bash
# From worker container
docker exec -it <worker-container> curl http://social-analyzer:9005/get_settings
```

### **Redis Connection Failed**
```bash
# Test from host
redis-cli -h 127.0.0.1 -p 6379 ping

# Test from container
docker exec -it <container> redis-cli -h redis -p 6379 ping
```

---

## 📚 Related Documentation

- **Architecture:** `backend/docs/ARCHITECTURE.md`
- **Docker Networking:** `backend/docker/NETWORKING.md`
- **Deployment:** `backend/docker/README-DEPLOYMENT.md`
- **Tier 1 Testing:** `backend/docs/TESTING_TIER1.md`
- **Troubleshooting:** `docs/TROUBLESHOOTING.md`
- **ADR 0008:** Host network decision (`docs/adr/0008-tier1-linux-host-network.md`)

---

**Last Updated:** 2026-08-05
**Verified Against:** `stage` branch commit `f5515cc`
