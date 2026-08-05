# Knowledge Transfer Document - HyerEnrichment

**Last Updated:** August 5, 2026
**Document Owner:** Development Team
**Purpose:** Comprehensive onboarding guide for new team members

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Project Setup](#3-project-setup)
4. [Docker Setup](#4-docker-setup)
5. [Branch Strategy](#5-branch-strategy)
6. [Common Docker Problems & Fixes](#6-common-docker-problems--fixes)
7. [Multilogin Setup & Issues](#7-multilogin-setup--issues)
8. [Testing Strategy](#8-testing-strategy)
9. [CI/CD Pipeline](#9-cicd-pipeline)
10. [Data Flow for Endpoints](#10-data-flow-for-endpoints)
11. [Pipeline Data Flow](#11-pipeline-data-flow)
12. [Common Issues & Fixes](#12-common-issues--fixes)
13. [Environment Files](#13-environment-files)
14. [Docker Network Configuration](#14-docker-network-configuration)
15. [What Has Been Built](#15-what-has-been-built)
16. [What We're Currently Building](#16-what-were-currently-building)
17. [What We Need to Build](#17-what-we-need-to-build)
18. [Additional Resources](#18-additional-resources)
19. [Quick Command Reference](#19-quick-command-reference)

---

## 1. Project Overview

### 1.1 What is HyerEnrichment?

HyerEnrichment is a **self-hosted people and company enrichment platform**. It takes one or more identifiers and returns a unified "dossier" assembled from open-source OSINT tools.

**Input Identifiers:**
- Email address
- LinkedIn URL
- Username
- Company name
- Business query
- Job search criteria

**Output Dossier May Include:**
- LinkedIn profile photo (cached to object storage)
- Cross-site social handles (GitHub, X, Reddit, thousands more)
- Public commit emails and GitHub metadata
- Guessed and SMTP-verified corporate emails
- Coworkers at the same company
- Open job posts across multiple boards
- Local business information (address, phone, rating)

**Key Principles:**
- **Customer Ownership:** You own the code and the data
- **Self-Hosted:** Everything runs on your infrastructure
- **Privacy-First:** Opt-out is permanent and enforced globally
- **Public Data Only:** No private sources, face recognition, or bulk scraping
- **Customer-Supplied Identifiers:** No unsolicited people-finding

For detailed product overview, see [`README.md`](README.md).

### 1.2 What Has Been Built

**Backend (Python + FastAPI):**
- ✅ FastAPI API with Bearer token auth (migrating to cookie-based OAuth)
- ✅ Async job queue via Redis + RQ
- ✅ Sync enrichment path (`POST /enrich/sync`)
- ✅ Job polling (`GET /enrich/{id}`)
- ✅ 11 enricher modules across 4 tiers
- ✅ Provider layer for free/paid mode switches
- ✅ Pipeline orchestrator with merge + confidence scoring
- ✅ LLM disambiguation for low-confidence handles
- ✅ Opt-out/suppression system (SQL + Redis dual-write)
- ✅ Rate limiting per API token (Redis)
- ✅ Health, readiness, Prometheus metrics endpoints
- ✅ Change-detection webhook consumer
- ✅ Docker Compose infrastructure (API, worker, Postgres, Redis, sidecars)
- ✅ Database migrations via Alembic
- ✅ SQLite local dev / Postgres in Docker

**Frontend (Next.js + React):**
- ✅ Identifier intake form (email, LinkedIn, username, company, business, job search)
- ✅ Tier selection (tier1–tier4)
- ✅ Pipeline visualization
- ✅ Merged dossier presentation
- ✅ Next.js API route proxying to backend
- ✅ Job history and status tracking
- ✅ Public opt-out form

**Infrastructure:**
- ✅ Multi-stage Docker builds
- ✅ PostgreSQL with pgvector extension
- ✅ Redis for queue, cache, and rate limiting
- ✅ Isolated AGPL sidecars (social-analyzer, google-maps-scraper)
- ✅ Compose healthchecks
- ✅ Hybrid networking (bridge + host for Tier 1)

See [`CHANGELOG.md`](CHANGELOG.md) for detailed release history.

### 1.3 What We're Currently Building

**Foundation Week 1:**
- 🔄 Document processing pipeline
- 🔄 Embedding workers with cost monitoring
- 🔄 Vector search with pgvector
- 🔄 Semantic chunking strategy

**Authentication Enhancements:**
- 🔄 Cookie-based OAuth with FastAPI-Users (ADR 0009)
- 🔄 Email verification flow (24h expiry)
- 🔄 Token blacklist (Redis + PostgreSQL dual-write)
- 🔄 Google OAuth integration

**Testing Infrastructure:**
- 🔄 Canary test sets (20-profile QA)
- 🔄 Fake sidecars for CI
- 🔄 Load testing harness with k6

See [`FOUNDATION_WEEK1_FINAL_COMPLETE.md`](FOUNDATION_WEEK1_FINAL_COMPLETE.md) for current sprint details.

### 1.4 What We Need to Build

**Priority Next Slices:**

1. **Unauthenticated Opt-Out** - Remove Bearer auth requirement for GDPR/LGPD compliance routes
2. **Real R2 Uploads** - Wire `aioboto3` to Cloudflare R2 (currently using local cache fallback)
3. **Tier 1 Production Hardening** - Multilogin profile pool, rate limits, session reuse
4. **Frontend Async Polling** - Replace `/enrich/sync` with `/enrich` + poll for long-running jobs
5. **LLM Prompt Tuning** - Real disambiguation prompts + Langfuse cost dashboards
6. **Sidecar Contract Verification** - Validate gitrecon JSON, social-analyzer, GMaps endpoints against live deployments
7. **Integration Tests in CI** - Fake sidecars via compose override for automated E2E

**Infrastructure Improvements:**
- Automated backups (Postgres + Redis)
- Advanced monitoring (Grafana dashboards)
- Alerting rules (Prometheus + PagerDuty)
- Log aggregation (ELK or Loki)

**Feature Enhancements:**
- Bulk enrichment API
- Webhook notifications for job completion
- Data export (CSV, JSON)
- Advanced search/filtering
- User dashboard improvements

See **Implementation status** in [`backend/docs/ARCHITECTURE.md`](backend/docs/ARCHITECTURE.md) for the authoritative feature matrix.

---

## 2. Architecture

### 2.1 High-Level System Design

```mermaid
graph TB
    Client[Client: Frontend/ATS/curl]
    API[FastAPI API :8000]
    RedisQueue[Redis + RQ Queue]
    Worker[RQ Worker]
    Orchestrator[Pipeline Orchestrator]
    Postgres[(PostgreSQL)]
    Redis[(Redis)]
    R2[R2 / Local Cache]

    subgraph Enrichers[Enrichers - 4 Tiers]
        Tier1[Tier 1: LinkedIn Photo]
        Tier2[Tier 2: Sherlock, Maigret, Social Analyzer]
        Tier3[Tier 3: GitRecon, Email Tools]
        Tier4[Tier 4: JobSpy, GMaps]
    end

    subgraph Sidecars[Isolated Sidecars]
        SocialAnalyzer[social-analyzer]
        GMaps[google-maps-scraper]
        EmailVerifier[email-verifier]
        Reacher[reacher - optional]
    end

    Client -->|HTTP + Bearer| API
    API -->|Async: enqueue| RedisQueue
    API -->|Sync: inline| Orchestrator
    RedisQueue -->|dequeue| Worker
    Worker --> Orchestrator
    Orchestrator --> Enrichers
    Orchestrator -->|Store jobs| Postgres
    Orchestrator -->|Rate limits| Redis
    Orchestrator -->|Suppression cache| Redis
    Tier1 -->|Upload photos| R2
    Tier2 --> Sidecars
    Tier3 --> Sidecars
    Tier4 --> Sidecars
```

**Component Roles:**

| Component | Port | Role |
|-----------|------|------|
| FastAPI API | 8000 | HTTP surface, auth, rate limits, request/response |
| RQ Worker | - | Background job execution |
| PostgreSQL | 5432 | Job + suppression persistence |
| Redis | 6379 | Queue, suppression cache, rate limits |
| Pipeline Orchestrator | - | Suppression check, tier dispatch, merge, confidence scoring |

For detailed architecture, see [`backend/docs/ARCHITECTURE.md`](backend/docs/ARCHITECTURE.md).

### 2.2 Technology Stack

**Backend:**
- **Python 3.12+** - Core language
- **FastAPI** - Async web framework
- **SQLAlchemy 2** - Async ORM
- **PostgreSQL** (production) / **SQLite** (local dev)
- **Redis** - Queue, cache, rate limits
- **RQ** (Redis Queue) - Async job queue
- **Alembic** - Database migrations
- **Playwright** - Browser automation (Tier 1)
- **Pydantic** - Data validation

**Frontend:**
- **Next.js 14** - React framework
- **React** - UI library
- **TypeScript** - Type safety
- **TanStack Query** - Data fetching
- **Tailwind CSS** - Styling

**Infrastructure:**
- **Docker + Docker Compose** - Containerization
- **Cloudflare R2** - Object storage
- **Prometheus** - Metrics
- **GlitchTip/Sentry** - Error tracking
- **Langfuse** - LLM observability (optional)

### 2.3 Enrichment Tiers

#### Tier 1: LinkedIn Photo (Browser-based)

**Tools:** `joeyism/linkedin_scraper` + Playwright + Multilogin X

**Integration:** Stealth browser via `BrowserProvider`; photo uploaded to R2 or local cache

**Key Points:**
- Gated by `ENABLE_TIER1=false` by default (hardest to run free)
- One browser session per profile - no bulk scraping
- Multilogin X stealth browser available via `BROWSER_MODE=multilogin`
- Requires special network configuration (see [Section 14](#14-docker-network-configuration))

**Rate Limits:**
- ~20-25 profile views/day per Multilogin profile
- Configurable via `MULTILOGIN_DAILY_VIEW_LIMIT`

See [`backend/docs/TESTING_TIER1.md`](backend/docs/TESTING_TIER1.md) for setup details.

#### Tier 2: Cross-site Username Hunt (No Browser)

Runs in parallel when `tier2` is requested:

| Module | Upstream | Confidence Base | Description |
|--------|----------|-----------------|-------------|
| `sherlock.py` | `sherlock-project/sherlock` (MIT) | 0.75 | Fast username search across 300+ sites |
| `maigret.py` | `soxoj/maigret` (MIT) | 0.85 | Deeper username search with metadata |
| `social_analyzer.py` | `qeeqbox/social-analyzer` (AGPL) | NLP scoring | AI-powered social media analysis via sidecar |

**Confidence Threshold:** Handles below **0.7** confidence go to the LLM disambiguator.

#### Tier 3: Deep OSINT (GitHub + Email + Company)

| Module | Upstream | Role |
|--------|----------|------|
| `gitrecon.py` | `GONZOsint/gitrecon` | Commit emails, names, orgs from GitHub |
| `theharvester.py` | `laramies/theHarvester` | Company-wide email harvest |
| `email_discover.py` | `buyukakyuz/email-sleuth` | Pattern-guess corporate emails |
| `email_verify.py` | Reacher + AfterShip + mailchecker | SMTP verify, catch-all detection, disposable blocklist |
| `crosslinked.py` | `m8sec/CrossLinked` | Coworker enumeration without LinkedIn login |

**Two-Phase Email Verification:**
1. **Basic** (AfterShip sidecar) - Syntax + MX + disposable check
2. **SMTP** (Reacher sidecar) - Full SMTP verification (optional, paid)

#### Tier 4: Job Match + Local Business

| Module | Upstream | Role |
|--------|----------|------|
| `jobspy.py` | `speedyapply/JobSpy` | Multi-board job pull (LinkedIn, Indeed, Glassdoor, Google Jobs, ZipRecruiter) |
| `local_business.py` | `gosom/google-maps-scraper` | Address, phone, website, rating via sidecar |

**JobSpy Boards:** Scrapes 5 boards concurrently. ZipRecruiter often returns 403 (bot detection).

**LLM Job Query Optimization:** When `LLM_MODE=litellm`, uses Gemini 2.5 Flash to generate board-specific optimized queries.

### 2.4 Data Flow Overview

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant Redis
    participant Worker
    participant Pipeline
    participant Enrichers
    participant DB

    alt Async Path: POST /enrich
        Client->>API: EnrichmentRequest + Bearer token
        API->>API: Rate limit check (Redis)
        API->>DB: Create job (status=queued)
        API->>Redis: enqueue_enrichment(job_id)
        API-->>Client: 202 Accepted {id, status: queued}
        Redis->>Worker: Dequeue job
        Worker->>Pipeline: execute_job(job_id)
    else Sync Path: POST /enrich/sync
        Client->>API: EnrichmentRequest + Bearer token
        API->>API: Rate limit check (Redis)
        API->>Pipeline: run(request) inline
    end

    Pipeline->>Pipeline: Suppression check (Redis → SQL)
    alt Suppressed
        Pipeline->>DB: status=suppressed, empty dossier
    else Not Suppressed
        Pipeline->>Enrichers: Dispatch tiers in parallel
        Enrichers-->>Pipeline: Partial dicts (photo, handles, emails)
        Pipeline->>Pipeline: Merge + confidence + LLM pass
        Pipeline->>DB: status=completed, dossier JSON
    end

    Client->>API: GET /enrich/{job_id}
    API->>DB: Fetch job
    API-->>Client: {id, status, dossier}
```

**Key Points:**
- Async and sync paths converge at `Pipeline.run()`
- Suppression check happens **before** any enricher dispatch
- Enrichers run in parallel per tier
- Cross-process polling works when API + worker share Postgres

---

## 3. Project Setup

### 3.1 Prerequisites

**Required:**
- **Python 3.12+** - Creates `backend/.venv` (required on PEP 668 / externally-managed systems)
- **Node.js 18+** - For frontend
- **Docker + Docker Compose** - Recommended for full stack
- **GNU Make** - For convenience targets
- **Git** - Version control

**For Authentication (Recommended):**
- SendGrid account (for email verification)
- Google Cloud project with OAuth credentials (optional, for social login)
- Strong `SECRET_KEY` (generate: `openssl rand -hex 32`)

**Optional:**
- Redis (for async queue, rate limits, auth token blacklist)
- PostgreSQL (for auth tables and job storage in Docker; SQLite for local dev)

### 3.2 Clone and Initial Setup

```bash
# Clone repository
git clone <repository-url>
cd HyerEnrichment

# Backend setup (creates .env, venv, installs dependencies)
make setup

# Start Docker stack (Postgres, Redis, API, worker, sidecars)
make up

# Health check
make smoke
```

**What `make setup` does:**
1. Copies `backend/.env.example` → `backend/.env` (if missing)
2. Creates Python virtual environment at `backend/.venv`
3. Installs backend with dev dependencies: `pip install -e "backend[dev]"`
4. Installs `requests` library
5. Installs pre-commit hooks

See [`Makefile`](Makefile) for all available targets.

### 3.3 Environment Configuration

Copy `backend/.env.example` → `backend/.env` and configure:

**Critical Variables:**

```bash
# API Authentication
API_TOKEN=change-me                    # Bearer token (legacy, will be replaced)
SECRET_KEY=                            # REQUIRED for auth - 256-bit (openssl rand -hex 32)

# Database
DATABASE_URL=sqlite+aiosqlite:///./hyrepath.db    # Local dev (SQLite)
# DATABASE_URL=postgresql+asyncpg://hyrepath:password@postgres:5432/hyrepath  # Docker/Production

# Redis
REDIS_URL=redis://localhost:6379/0    # Queue, cache, rate limits

# Email (for verification)
SENDGRID_API_KEY=                      # SendGrid API key
SENDGRID_FROM_EMAIL=                   # Sender email address
FRONTEND_URL=http://localhost:3000     # For email verification links

# Object Storage
R2_ACCOUNT_ID=                         # Cloudflare R2 account ID
R2_ACCESS_KEY_ID=                      # R2 access key
R2_SECRET_ACCESS_KEY=                  # R2 secret key
R2_BUCKET=hyrepath-assets              # Bucket name
R2_PUBLIC_BASE_URL=https://cdn.example.com  # CDN base for cached photos
```

**Optional - Google OAuth:**
```bash
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GOOGLE_OAUTH_REDIRECT_URL=http://localhost:3000/callback/google
```

See [`backend/.env.example`](backend/.env.example) for the complete list with descriptions.

**Important:** `.env` files are gitignored. Never commit secrets!

### 3.4 Running Locally

#### Backend (SQLite - Simplest)

```bash
cd backend

# Terminal 1: API
uvicorn app.main:app --reload

# Terminal 2: RQ worker (required for async /enrich)
python -m app.workers.rq_worker
```

**Endpoints:**
- API: `http://localhost:8000`
- Interactive docs: `http://localhost:8000/docs`

#### Backend (Docker - Recommended)

```bash
# Start full stack
make up

# Or manually:
cd backend/docker
docker compose up --build -d api worker redis postgres social-analyzer google-maps-scraper

# Check health
curl http://localhost:8000/health

# Test sync enrichment
curl -X POST http://localhost:8000/enrich/sync \
  -H "Authorization: Bearer change-me" \
  -H "Content-Type: application/json" \
  -d '{"username": "jane-doe", "requested_tiers": ["tier2"]}'
```

#### Frontend

```bash
cd frontend
cp .env.example .env.local

# Edit .env.local:
# BACKEND_API_URL=http://localhost:8000
# BACKEND_API_TOKEN=change-me

npm install
npm run dev
```

**UI:** `http://localhost:3000`

#### Running Both (Full Stack)

```bash
# Terminal 1: Backend (Docker)
make up

# Terminal 2: Frontend (Node)
cd frontend && npm run dev
```

---

## 4. Docker Setup

### 4.1 Docker Compose Files

The project uses multiple Docker Compose files for different environments and configurations:

| File | Purpose | Usage |
|------|---------|-------|
| [`docker-compose.yml`](backend/docker/docker-compose.yml) | Base services (API, worker, postgres, redis, sidecars) | Default stack |
| [`docker-compose.prod.yml`](backend/docker/docker-compose.prod.yml) | Production overrides (port bindings, replicas) | Production deployment |
| [`docker-compose.tier1.yml`](backend/docker/docker-compose.tier1.yml) | Tier 1 worker with Multilogin secrets | When LinkedIn photo scraping needed |
| [`docker-compose.tier-workers.yml`](backend/docker/docker-compose.tier-workers.yml) | Separate tier workers (tier1, tier234) | Horizontal scaling |
| [`docker-compose.multilogin.yml`](backend/docker/docker-compose.multilogin.yml) | Linux containerized Multilogin | Production Tier 1 on Linux |
| [`docker-compose.fake-sidecars.yml`](backend/docker/docker-compose.fake-sidecars.yml) | Fake sidecars for testing | CI/CD integration tests |
| [`docker-compose.loadtest.yml`](backend/docker/docker-compose.loadtest.yml) | Load testing configuration | Performance testing |
| [`docker-compose.staging.yml`](backend/docker/docker-compose.staging.yml) | Staging environment overrides | Staging deployment |
| [`docker-compose.foundation.yml`](backend/docker/docker-compose.foundation.yml) | Foundation Week 1 services (document, embedding workers) | Document processing features |

### 4.2 Dockerfiles

| Dockerfile | Purpose | Key Features |
|------------|---------|--------------|
| [`Dockerfile.api`](backend/docker/Dockerfile.api) | FastAPI API container | Python 3.12, uvicorn, app code |
| [`Dockerfile.worker`](backend/docker/Dockerfile.worker) | RQ worker container | Includes Chromium, enricher CLIs |
| [`Dockerfile.postgres`](backend/docker/Dockerfile.postgres) | PostgreSQL with pgvector | Vector extension for embeddings |
| [`Dockerfile.social-analyzer`](backend/docker/Dockerfile.social-analyzer) | AGPL social analyzer sidecar | Isolated AGPL code |
| [`Dockerfile.google-maps-scraper`](backend/docker/Dockerfile.google-maps-scraper) | Google Maps scraper sidecar | Playwright 1.57.0 driver |
| [`Dockerfile.email-verifier`](backend/docker/Dockerfile.email-verifier) | AfterShip email verification | Basic email validation |
| [`Dockerfile.multilogin`](backend/docker/Dockerfile.multilogin) | Multilogin X container (Linux) | Stealth browser for Tier 1 |
| [`Dockerfile.worker-document`](backend/docker/Dockerfile.worker-document) | Document processing worker | Foundation Week 1 |
| [`Dockerfile.worker-embedding`](backend/docker/Dockerfile.worker-embedding) | Embedding worker | Foundation Week 1 |

### 4.3 Starting Different Stacks

#### Free Stack (Default)

```bash
cd backend/docker
docker compose up --build -d api worker redis postgres social-analyzer google-maps-scraper

# Or using Makefile:
make up
```

**Services Included:**
- API (FastAPI)
- Worker (RQ)
- PostgreSQL (with pgvector)
- Redis (queue, cache, rate limits)
- social-analyzer (Tier 2)
- google-maps-scraper (Tier 4)
- email-verifier (Tier 3 basic)

#### With Tier 1 (LinkedIn Photo)

**Requirements:**
- Multilogin X running on host
- LinkedIn bot credentials
- R2 credentials (or local cache)

```bash
cd backend/docker

# Load secrets from backend/.env
docker compose -f docker-compose.yml -f docker-compose.tier1.yml up -d

# Or specify custom env file:
docker compose --env-file /path/to/tier1-secrets.env \
  -f docker-compose.yml \
  -f docker-compose.tier1.yml \
  up -d
```

**Note:** Tier 1 requires special network configuration. See [Section 7](#7-multilogin-setup--issues) and [Section 14](#14-docker-network-configuration).

#### Production with Scaled Workers

```bash
cd backend/docker

docker compose --env-file ../.env.production \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier-workers.yml \
  up -d --scale worker-tier234=6
```

**Configuration:**
- `worker-tier1`: 1 instance (cannot scale due to host network)
- `worker-tier234`: 6 instances (scalable, bridge network)

See [`README-DEPLOYMENT.md`](backend/docker/README-DEPLOYMENT.md) for production deployment guide.

#### For Load Testing

```bash
cd backend/docker

docker compose -f docker-compose.yml \
  -f docker-compose.fake-sidecars.yml \
  -f docker-compose.loadtest.yml \
  up -d

# Run load test
make load-test
```

### 4.4 Building Images

```bash
# Build all services
cd backend/docker
docker compose build

# Build specific service
docker compose build api

# Build without cache (clean rebuild)
docker compose build --no-cache worker

# Build with BuildKit disabled (for compatibility)
DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 docker compose build
```

### 4.5 Common Docker Commands

```bash
# View running containers
docker compose ps

# View logs
docker compose logs -f api              # Follow API logs
docker compose logs --tail 100 worker   # Last 100 lines from worker

# Restart services
docker compose restart api worker

# Stop all services
docker compose down

# Stop and remove volumes (WARNING: deletes data)
docker compose down -v

# Execute command in container
docker compose exec api python -c "import sys; print(sys.version)"
docker compose exec worker redis-cli -h redis ping

# Scale workers
docker compose up -d --scale worker-tier234=8
```

### 4.6 Docker Compose Profiles (Paid & Optional Services)

The project uses Docker Compose profiles to organize optional services. **Profiles allow you to start only the services you need** without cluttering the free/default stack.

#### Available Profiles

| Profile | Services Included | Purpose | Default On? |
|---------|------------------|---------|-------------|
| `paid` | reacher, scrapoxy | Paid external services | ❌ No |
| `llm` | litellm, ollama | LLM disambiguation | ❌ No |
| `observability` | langfuse, glitchtip-web, glitchtip-worker, changedetection | Monitoring & observability | ❌ No |

**Default Stack (No Profile):** API, worker, postgres, redis, social-analyzer, google-maps-scraper, email-verifier

#### Starting Services with Profiles

**Single Profile:**
```bash
cd backend/docker

# LLM services only
docker compose --env-file ../.env --profile llm up -d

# Observability services only
docker compose --env-file ../.env --profile observability up -d

# Paid services only
docker compose --env-file ../.env --profile paid up -d
```

**Multiple Profiles:**
```bash
# LLM + Observability
docker compose --env-file ../.env \
  --profile llm \
  --profile observability \
  up -d

# All optional services (full stack)
docker compose --env-file ../.env \
  --profile paid \
  --profile llm \
  --profile observability \
  up -d
```

**Production with All Services:**
```bash
cd backend/docker

docker compose --env-file ../.env.production \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier-workers.yml \
  --profile paid \
  --profile llm \
  --profile observability \
  up -d --scale worker-tier234=6
```

#### Profile Services Detail

**Paid Profile Services:**

| Service | Port | Purpose | Configuration Required |
|---------|------|---------|------------------------|
| `reacher` | 8080 | SMTP email verification (Tier 3) | `REACHER_URL`, `REACHER_FROM_EMAIL` |
| `scrapoxy` | 8888 | Rotating proxy pool | `PROXY_MODE=scrapoxy`, `SCRAPOXY_*` |

**LLM Profile Services:**

| Service | Port | Purpose | Configuration Required |
|---------|------|---------|------------------------|
| `litellm` | 4000 | LLM proxy with fallback chain | `LLM_MODE=litellm`, `LITELLM_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY` |
| `ollama` | 11434 | Local LLM inference | `LLM_MODE=ollama`, `OLLAMA_MODEL` |

**Observability Profile Services:**

| Service | Port | Purpose | Configuration Required |
|---------|------|---------|------------------------|
| `langfuse` | 3000 | LLM observability & tracing | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` |
| `glitchtip-web` | 8001 | Error tracking UI (Sentry-compatible) | `SENTRY_DSN`, `GLITCHTIP_SECRET_KEY` |
| `glitchtip-worker` | - | GlitchTip background worker | Same as glitchtip-web |
| `changedetection` | 5000 | Company change monitoring | `CHANGEDETECTION_API_KEY`, `CHANGEDETECTION_URL` |

### 4.7 Complete Production Setup with All Services

This section shows how to set up a **full production environment** with all optional services enabled.

#### Step 1: Prepare Environment File

Create `backend/.env.production` with all required variables:

```bash
# Copy example and edit
cp backend/.env.example backend/.env.production
```

**Required for All Services:**
```bash
# Core
APP_ENV=production
SECRET_KEY=<strong-32-byte-key>
API_TOKEN=<production-api-token>

# Database & Cache
DATABASE_URL=postgresql+asyncpg://hyrepath:${POSTGRES_PASSWORD}@postgres:5432/hyrepath
POSTGRES_PASSWORD=<strong-password>
REDIS_URL=redis://redis:6379/0

# Object Storage (R2)
R2_ACCOUNT_ID=<cloudflare-account-id>
R2_ACCESS_KEY_ID=<r2-access-key>
R2_SECRET_ACCESS_KEY=<r2-secret-key>
R2_BUCKET=hyrepath-assets
R2_PUBLIC_BASE_URL=https://cdn.yourdomain.com

# Authentication
SENDGRID_API_KEY=<sendgrid-key>
SENDGRID_FROM_EMAIL=noreply@yourdomain.com
FRONTEND_URL=https://app.yourdomain.com
COOKIE_SECURE=true
COOKIE_DOMAIN=.yourdomain.com

# Tier 1 (if using)
ENABLE_TIER1=true
BROWSER_MODE=multilogin
MULTILOGIN_EMAIL=<multilogin-account>
MULTILOGIN_PASSWORD=<multilogin-password>
MULTILOGIN_FOLDER_ID=<folder-id>
MULTILOGIN_WORKSPACE_ID=<workspace-id>
LINKEDIN_BOT_EMAIL=<bot-email>
LINKEDIN_BOT_PASSWORD=<bot-password>

# Paid Services
PROXY_MODE=scrapoxy  # or 'paid'
SCRAPOXY_API_URL=http://scrapoxy:8888
SCRAPOXY_USERNAME=<username>
SCRAPOXY_PASSWORD=<password>
REACHER_URL=http://reacher:8080
REACHER_FROM_EMAIL=verify@yourdomain.com
EMAIL_VERIFY_LEVEL=smtp

# LLM Services
LLM_MODE=litellm
LITELLM_API_BASE=http://litellm:4000
LITELLM_API_KEY=<litellm-key>
LITELLM_MODEL=gpt-4o-mini
LITELLM_FALLBACKS=gemini-2.0-flash-exp,claude-3-5-haiku-20241022
OPENAI_API_KEY=<openai-key>  # For litellm container
GEMINI_API_KEY=<gemini-key>  # For litellm container
DISAMBIGUATION_THRESHOLD=0.7

# Observability
SENTRY_DSN=<glitchtip-or-sentry-dsn>
SENTRY_ENVIRONMENT=production
GLITCHTIP_PUBLIC_URL=https://errors.yourdomain.com
GLITCHTIP_SECRET_KEY=<django-secret-key>
LANGFUSE_PUBLIC_KEY=<langfuse-public>
LANGFUSE_SECRET_KEY=<langfuse-secret>
LANGFUSE_HOST=http://langfuse:3000
CHANGEDETECTION_URL=http://changedetection:5000
CHANGEDETECTION_API_KEY=<changedetection-key>
NOTIFY_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Rate Limits
MAX_SYNC_REQUESTS_PER_MINUTE=10
MAX_ASYNC_REQUESTS_PER_MINUTE=30
MAX_COMPLIANCE_REQUESTS_PER_MINUTE=20

# Worker Scaling
WORKER_TIER234_COUNT=6
WORKER_STARTUP_DELAY=10
```

#### Step 2: Start Complete Production Stack

**Testing/Development (1 worker each):**

```bash
cd backend/docker

# Build and start EVERYTHING - all compose files, all profiles, all services
# Includes containerized Multilogin X
# Default: 1 worker-tier1 + 1 worker-tier234 (no scaling)
docker compose --env-file ../.env.production \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier1.yml \
  -f docker-compose.tier-workers.yml \
  -f docker-compose.multilogin.yml \
  -f docker-compose.foundation.yml \
  --profile paid \
  --profile llm \
  --profile observability \
  up -d --build

# What this does:
# 1. Loads production environment variables
# 2. Uses base services (docker-compose.yml)
# 3. Applies production overrides (docker-compose.prod.yml)
# 4. Adds Tier 1 worker (docker-compose.tier1.yml) - 1 instance
# 5. Adds tier workers (docker-compose.tier-workers.yml) - 1 worker-tier234
# 6. Adds Multilogin container (docker-compose.multilogin.yml)
# 7. Adds Foundation Week 1 workers (docker-compose.foundation.yml)
# 8. Enables paid services profile (reacher, scrapoxy)
# 9. Enables LLM services profile (litellm, ollama)
# 10. Enables observability profile (langfuse, glitchtip, changedetection)
# 11. Builds all images fresh (--build)
# 12. Runs in background (-d)
```

**Production (Scaled Workers):**

```bash
cd backend/docker

# Same as above, but scale tier234 workers for production load
docker compose --env-file ../.env.production \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier1.yml \
  -f docker-compose.tier-workers.yml \
  -f docker-compose.multilogin.yml \
  -f docker-compose.foundation.yml \
  --profile paid \
  --profile llm \
  --profile observability \
  up -d --build --scale worker-tier234=6

# Scales to: 1 worker-tier1 + 6 worker-tier234 instances
```

**Quick Production Variants:**

```bash
# Without Tier 1 (no Multilogin/LinkedIn)
docker compose --env-file ../.env.production \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier-workers.yml \
  --profile paid \
  --profile llm \
  --profile observability \
  up -d --build --scale worker-tier234=8

# Without Foundation Week 1 (if not needed)
docker compose --env-file ../.env.production \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier-workers.yml \
  --profile paid \
  --profile llm \
  --profile observability \
  up -d --build --scale worker-tier234=6

# Minimal production (no optional profiles)
docker compose --env-file ../.env.production \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier-workers.yml \
  up -d --build --scale worker-tier234=6

# Or use the production script (recommended for Linux)
bash ../scripts/start_production.sh \
  --env-file ../.env.production \
  --with-tier1 \
  --with-observability \
  --with-llm
```

**Stop Everything:**

```bash
cd backend/docker

# Stop and remove all containers (keeps data volumes)
docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier1.yml \
  -f docker-compose.tier-workers.yml \
  -f docker-compose.foundation.yml \
  --profile paid \
  --profile llm \
  --profile observability \
  down

# Stop and remove everything including volumes (WARNING: deletes data)
docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier1.yml \
  -f docker-compose.tier-workers.yml \
  -f docker-compose.foundation.yml \
  --profile paid \
  --profile llm \
  --profile observability \
  down -v
```

**Rebuild Without Cache:**

```bash
cd backend/docker

# Force clean rebuild of all images
docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier1.yml \
  -f docker-compose.tier-workers.yml \
  -f docker-compose.foundation.yml \
  build --no-cache

# Then start
docker compose --env-file ../.env.production \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier1.yml \
  -f docker-compose.tier-workers.yml \
  -f docker-compose.foundation.yml \
  --profile paid \
  --profile llm \
  --profile observability \
  up -d --scale worker-tier234=6
```

#### Step 3: Verify All Services

```bash
# Check all containers are running
docker compose ps

# Health checks
curl http://localhost:8000/health          # API
curl http://localhost:8000/ready           # Readiness
curl http://localhost:4000/health          # LiteLLM
curl http://localhost:8001/                # GlitchTip UI
curl http://localhost:3000/api/public/health  # Langfuse
curl http://localhost:5000/                # Changedetection

# Check worker logs
docker compose logs -f worker-tier234

# Verify Redis
docker compose exec redis redis-cli ping

# Verify Postgres
docker compose exec postgres psql -U hyrepath -d hyrepath -c "SELECT 1;"
```

#### Step 4: Configure Observability Services

**GlitchTip Setup:**
1. Open `http://localhost:8001`
2. Create organization and project
3. Copy DSN to `SENTRY_DSN` in `.env.production`
4. Restart API/worker: `docker compose restart api worker`

**Langfuse Setup:**
1. Open `http://localhost:3000`
2. Create account and project
3. Copy public/secret keys to `.env.production`
4. Restart API/worker to enable tracing

**Changedetection Setup:**
1. Open `http://localhost:5000`
2. Set API key in settings
3. Create watches: `python scripts/setup_changedetection_watches.py create <url>`

#### Step 5: Production Smoke Test

```bash
# Run comprehensive smoke test
BASE_URL=http://localhost:8000 \
API_TOKEN="$API_TOKEN" \
make smoke-prod

# Or manually test each tier
curl -X POST http://localhost:8000/enrich/sync \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "torvalds",
    "requested_tiers": ["tier2", "tier3", "tier4"]
  }'
```

### 4.8 Cost Implications of Paid Services

**Monthly Cost Estimates (USD):**

| Service | Type | Estimated Cost | Notes |
|---------|------|----------------|-------|
| **Multilogin** (Tier 1) | Subscription | $99-299/month | Based on plan (Solo/Team/Scale) |
| **Reacher** (Email SMTP) | Self-hosted | $0 (free) | Uses your SMTP relay |
| **Scrapoxy** (Proxy Pool) | Subscription + Proxies | $50-500/month | Depends on proxy provider + volume |
| **LiteLLM** (LLM Proxy) | Pass-through | Variable | Charges from OpenAI/Gemini/Anthropic |
| **OpenAI API** | Per-token | $0.50-50/month | GPT-4o-mini: ~$0.15/1M tokens |
| **Google Gemini** | Per-token | $0.25-25/month | Gemini 2.0 Flash: ~$0.075/1M tokens |
| **Cloudflare R2** | Storage | $0-5/month | $0.015/GB storage, $0.36/million Class A ops |
| **Langfuse** | Self-hosted | $0 (free) | Open source, self-hosted in Docker |
| **GlitchTip** | Self-hosted | $0 (free) | Open source, self-hosted in Docker |
| **Changedetection** | Self-hosted | $0 (free) | Open source, self-hosted in Docker |

**Free Alternative Stack:**
- **Total Cost:** $0/month (excluding hosting)
- Tier 1: Disabled (`ENABLE_TIER1=false`)
- Email Verify: Basic only (syntax + MX, no SMTP)
- Proxy: Direct (no proxy pool)
- LLM: Stub (heuristic, no AI) or Ollama (local)
- Observability: Optional (enable if needed)

**Minimal Paid Stack:**
- **Total Cost:** ~$50-100/month
- Multilogin Solo: $99/month (for Tier 1)
- LLM: Pay-as-you-go (OpenAI GPT-4o-mini: ~$5-20/month for typical usage)
- R2: ~$2-5/month (for photo storage)
- Proxies: Optional (add $50-200/month if needed)

**Full Production Stack:**
- **Total Cost:** ~$200-800/month
- Multilogin Team: $199/month
- Scrapoxy + Proxies: $100-500/month (depending on volume)
- LLM APIs: $20-100/month (with fallback chain)
- R2: $5-10/month
- Observability: $0 (self-hosted)

**Cost Optimization Tips:**
1. **Start with free tier** - Validate product-market fit first
2. **Use Gemini 2.0 Flash** - Cheaper than GPT-4o-mini (~50% less)
3. **Enable Tier 1 selectively** - Only for high-value enrichments
4. **Cache aggressively** - Photo cache saves R2 costs
5. **Rate limit appropriately** - Prevents runaway API costs
6. **Use Ollama for development** - Free local LLM for testing
7. **Monitor with Langfuse** - Track LLM costs in real-time

For detailed networking configuration, see [Section 14](#14-docker-network-configuration).

---

## 5. Branch Strategy

### 5.1 Branch Naming Conventions

The project follows a structured branch naming pattern:

| Prefix | Purpose | Example |
|--------|---------|---------|
| `main` / `master` | Production-ready code | `main` |
| `stage` | Staging environment | `stage` |
| `feat/` | New features | `feat/tier1-multilogin-canary` |
| `fix/` | Bug fixes | `fix/redis-localhost-port` |
| `chore/` | Maintenance, cleanup | `chore/dependency-audit` |
| `docs/` | Documentation updates | `docs/user-guide` |
| `agent-*/` | Agent/subagent work | `agent-1/document-worker` |
| `refactor/` | Code refactoring | `refactor/modular-backend` |
| `test/` | Testing improvements | `test/integration-verify` |

### 5.2 Key Branches and Their Purpose

**Main Branches:**
- `main` / `master` - Production branch, always deployable
- `stage` - Staging environment for pre-production testing

**Active Feature Branches:**
- `feat/auth` - Cookie-based authentication system
- `feat/tier1-multilogin-canary` - Tier 1 LinkedIn features
- `feat/canary-20-run-score` - Canary testing infrastructure
- `feat/changedetection-notify` - Change detection webhook
- `feat/signals-product-flow` - Signals UI flow

**Foundation Week 1:**
- `agent-1/document-worker` - Document processing worker
- `agent-2/embedding-worker` - Embedding worker
- `agent-3/chunking-cv` - Semantic chunking
- `agent-4/docker-pgvector` - pgvector integration
- `agent-5/api-integration` - API integration

**Documentation:**
- `docs/devplan` - Development planning
- `docs/legal-linkedin-scraping` - Legal documentation
- `docs/user-guide` - End-user guide

### 5.3 Why Branches Are Separate

**Feature Isolation:**
- Each branch represents a cohesive unit of work
- Prevents conflicts during parallel development
- Allows independent testing before merge

**Staged Rollouts:**
- Features can be tested in isolation
- Partial features don't break main
- Easy to revert if issues found

**Code Review:**
- Clear scope for each PR
- Easier to review focused changes
- Better understanding of intent

**Parallel Work:**
- Multiple team members can work simultaneously
- Agent/subagent work doesn't interfere
- Foundation Week 1 agents work independently

### 5.4 Workflow

The project follows a **branch + PR workflow** defined in [`.cursor/rules/git-branch-pr-workflow.mdc`](.cursor/rules/git-branch-pr-workflow.mdc):

1. **Create Branch:** From latest `main` for new work
2. **Make Changes:** Implement on feature branch only
3. **Commit:** Clear message following repo style
4. **Push:** Push branch to remote
5. **Open PR:** Use `gh pr create` with template
6. **Review:** Wait for review and CI to pass
7. **Merge:** User reviews and merges (never auto-merge)

**Hard Stops:**
- Never merge PRs automatically
- Never push directly to `main`/`master`
- Never add co-authors without explicit request
- Do not amend commits already pushed

See [`RULE.md`](RULE.md) for development rules.

---

## 6. Common Docker Problems & Fixes

### 6.1 Port Already in Use

**Problem:** `Bind for 0.0.0.0:8000 failed: port is already allocated`

**Solution:**
```bash
# Windows: Find process using port
netstat -ano | findstr :8000

# Kill process
taskkill /PID <PID> /F

# Or change port in docker-compose.yml
```

### 6.2 Database Connection Refused

**Problem:** `could not translate host name "postgres" to address`

**Diagnosis:** Worker is on host network but trying to use service name, or Postgres not running.

**Solution:**
```bash
# Check postgres is running
docker ps | grep postgres

# Restart postgres
docker compose restart postgres

# Check connection from API
docker compose exec api python -c "from app.database.session import get_db_session; print('OK')"

# Verify DATABASE_URL is correct for network mode
docker compose exec api env | grep DATABASE_URL
```

### 6.3 Worker Cannot Reach Multilogin (Tier 1)

**Problem:** `Connection refused to http://127.0.0.1:9222`

**Root Cause:** Multilogin binds Selenium to `127.0.0.1` only (host loopback). Docker bridge containers can't reach it.

**Solution:**

**Windows/WSL2:**
```bash
# Run worker NATIVELY on host, not in Docker
cd backend
python -m app.workers.rq_worker
```

**Linux Production:**
```bash
# Use host network mode for both Multilogin and worker
docker compose -f docker-compose.yml -f docker-compose.tier1.yml up -d
# Both share the host's 127.0.0.1
```

See [Section 7](#7-multilogin-setup--issues) and [`docs/DEV_SETUP_WSL.md`](docs/DEV_SETUP_WSL.md).

### 6.4 Redis Connection Timeout

**Problem:** `redis.exceptions.ConnectionError: Error connecting to Redis`

**Solution:**
```bash
# Check Redis is running
docker ps | grep redis

# Test connectivity
docker compose exec api python -c "import redis; r = redis.from_url('redis://redis:6379'); print(r.ping())"

# Restart Redis
docker compose restart redis

# Check logs for errors
docker compose logs redis
```

### 6.5 Docker Network Issues

**Problem:** Services can't communicate

**Solution:**
```bash
# Verify services are on same network
docker network ls
docker network inspect <network-name>

# Use service names, not localhost
# Good: DATABASE_URL=postgresql://...@postgres:5432/db
# Bad: DATABASE_URL=postgresql://...@localhost:5432/db

# Exception: Tier 1 worker uses host network, needs 127.0.0.1
```

See [`backend/docker/NETWORKING.md`](backend/docker/NETWORKING.md) for detailed network architecture.

### 6.6 Build Cache Issues

**Problem:** Old code running after changes

**Solution:**
```bash
# Rebuild without cache
docker compose build --no-cache

# Or specific service
docker compose build --no-cache worker

# Then restart
docker compose up -d
```

### 6.7 Volume Permission Issues

**Problem:** Permission denied errors in containers

**Solution:**
```bash
# Check volume permissions
docker compose exec postgres ls -la /var/lib/postgresql/data

# Reset permissions (WARNING: stops service)
docker compose down
docker volume rm <volume-name>
docker compose up -d
```

For more troubleshooting, see [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

---

## 7. Multilogin Setup & Issues

### 7.1 What is Multilogin

**Multilogin X** is a stealth browser platform used for Tier 1 (LinkedIn photo scraping). It provides:
- Anti-fingerprinting protection
- Profile management with persistent sessions
- Selenium Remote debug port for automation

**Why Needed:** LinkedIn aggressively blocks automated scraping. Multilogin provides browser fingerprint randomization to avoid detection.

**Key Limitation:** Multilogin binds its Selenium debug port to `127.0.0.1` (localhost) only for security. This creates networking challenges in Docker.

### 7.2 Prerequisites

**Environment Variables:**
```bash
# Multilogin Account
MULTILOGIN_EMAIL=your-email@example.com
MULTILOGIN_PASSWORD=your-password

# Profile Pool
MULTILOGIN_FOLDER_ID=abc123def456          # Folder containing profiles
MULTILOGIN_WORKSPACE_ID=workspace-uuid     # For multi-workspace accounts
MULTILOGIN_PROFILE_ID=                     # Optional: fixed profile for testing

# Multilogin Endpoints
MULTILOGIN_LAUNCHER_URL=https://127.0.0.1:45001/api/v2
MULTILOGIN_SELENIUM_HOST=http://127.0.0.1  # Host-native; http://launcher.mlx.yt for Docker

# LinkedIn Bot Account (for profile login)
LINKEDIN_BOT_EMAIL=bot@example.com
LINKEDIN_BOT_PASSWORD=bot-password

# Rate Limits
MULTILOGIN_DAILY_VIEW_LIMIT=22             # Max profiles per day (default: 22)
MULTILOGIN_PROFILE_COOLDOWN_SECONDS=86400  # Cooldown after captcha (24h)
```

**Software Requirements:**
- Multilogin X application installed and running
- Chromium/Chrome (included with Multilogin)

### 7.3 Common Connection Issues

#### Issue: Cannot Connect to Launcher

**Symptom:**
```
ERROR: Connection to https://127.0.0.1:45001 failed
```

**Diagnosis:**
```bash
# Windows: Test from PowerShell
curl.exe -sk https://127.0.0.1:45001/api/v2/

# Should return non-000 status (often 404 is OK, means launcher is running)
```

**Fix:**
- Ensure Multilogin X app is running
- Check launcher is on port 45001 (default)
- Verify no firewall blocking localhost:45001

#### Issue: Worker Can't Reach Selenium Port

**Symptom:**
```
ERROR: Connection refused to http://127.0.0.1:9222
selenium.common.exceptions.WebDriverException
```

**Root Cause:** Docker bridge network container cannot reach host's `127.0.0.1`.

**Fix (Windows/WSL2):**
```bash
# Run worker NATIVELY on host
cd backend
ENABLE_TIER1=true \
BROWSER_MODE=multilogin \
MULTILOGIN_SELENIUM_HOST=http://127.0.0.1 \
python -m app.workers.rq_worker
```

**Fix (Linux Production):**
```bash
# Use host network mode
docker compose -f docker-compose.yml -f docker-compose.tier1.yml up -d
```

See [`docs/DEV_SETUP_WSL.md`](docs/DEV_SETUP_WSL.md) for detailed WSL2 setup.

#### Issue: Profile Pool Exhausted

**Symptom:**
```
ERROR: Profile pool exhausted - MULTILOGIN_DAILY_VIEW_LIMIT reached
```

**Solution:**
```bash
# Check current usage
python backend/scripts/probe_tier1.py --pool-status

# Option 1: Wait for 24h cooldown
# Option 2: Increase limit if you have more profiles
# backend/.env:
# MULTILOGIN_DAILY_VIEW_LIMIT=50

# Option 3: Use Tier 2-4 (free) without LinkedIn
curl -X POST http://localhost:8000/enrich \
  -H "Authorization: Bearer change-me" \
  -d '{"username":"torvalds","requested_tiers":["tier2","tier3","tier4"]}'
```

### 7.4 Windows/WSL2 vs Linux Setup

**Windows/WSL2 (Development):**
- Multilogin runs on Windows host
- Worker runs natively in WSL (not Docker)
- Uses shared Windows/WSL loopback
- Requires systemd enabled in WSL for Docker
- See [`docs/DEV_SETUP_WSL.md`](docs/DEV_SETUP_WSL.md)

**Linux Production:**
- Multilogin container with `network_mode: host`
- Worker container with `network_mode: host`
- Both share Linux host loopback
- See ADR 0008: [`docs/adr/0008-tier1-linux-host-network.md`](docs/adr/0008-tier1-linux-host-network.md)

### 7.5 Testing Tier 1

```bash
# Prerequisites check
python backend/scripts/probe_tier1.py --prereqs

# Connection test
python backend/scripts/probe_tier1.py --connect-test

# Scrape test (replace with real URL)
python backend/scripts/probe_tier1.py --scrape \
  --linkedin-url https://www.linkedin.com/in/satyanadella

# Full canary set (20 profiles)
python backend/scripts/run_canary_score.py --tier tier1 --json
```

See [`backend/docs/TESTING_TIER1.md`](backend/docs/TESTING_TIER1.md) for complete testing checklist.

---

## 8. Testing Strategy

### 8.1 Test Types

#### Unit Tests
```bash
cd backend
pytest tests -m "not postgres" -q --cov=app --cov-report=term-missing

# Specific test file
pytest tests/test_pipeline_shape.py -v

# With coverage floor (78% minimum)
pytest tests -m "not postgres" --cov=app --cov-fail-under=78
```

#### Shape Tests
```bash
# Verify enrichers return valid dossier fragments
pytest tests/test_pipeline_shape.py -v

# Test that sync skips Tier 1
pytest tests/test_pipeline_shape.py -v -k "sync_skips_tier1"
```

#### Smoke Test
```bash
# Local stack
make smoke

# Or manually
python backend/scripts/smoke_test.py

# Production
BASE_URL=https://enrich.hyrepath.io API_TOKEN="$PROD_TOKEN" make smoke-prod
```

#### Integration Tests
```bash
# Docker Compose E2E
bash backend/scripts/e2e_compose_test.sh

# Full-path E2E (CI mode)
make e2e-full-path
# Or: python backend/scripts/e2e_full_path_runner.py --ci
```

#### Real-World Tests
```bash
# Strict validation against live sidecars
python backend/scripts/e2e_realworld_strict.py

# With specific tiers
python backend/scripts/e2e_realworld_strict.py --tiers tier2,tier3
```

#### Load Tests
```bash
# k6 load test with fake sidecars
make load-test

# Full profile
LOAD_PROFILE=full make load-test

# Manual
python backend/scripts/run_load_test.py
```

### 8.2 Tier-Specific Testing

#### Tier 2-4 Testing

```bash
cd backend

# Prerequisites check (CLI tools, env vars)
python scripts/probe_enrichers.py --prereqs

# Isolation test (each enricher separately)
python scripts/probe_enrichers.py

# Specific enricher
python scripts/probe_enrichers.py --only sherlock,maigret

# JSON output
python scripts/probe_enrichers.py --json

# Full E2E scripts
bash scripts/e2e_tier2.sh  # Sherlock + Maigret + Social Analyzer
bash scripts/e2e_tier3.sh  # GitRecon + Email tools
```

See [`backend/docs/TESTING_TIER234.md`](backend/docs/TESTING_TIER234.md) for layer-by-layer testing guide.

#### Tier 1 Testing

```bash
cd backend

# Prerequisites
python scripts/probe_tier1.py --prereqs

# Connection test
python scripts/probe_tier1.py --connect-test

# Scrape test
python scripts/probe_tier1.py --scrape --linkedin-url <url>

# Pool status
python scripts/probe_tier1.py --pool-status

# 20-profile canary set
python scripts/run_canary_score.py --tier tier1 --json
```

See [`backend/docs/TESTING_TIER1.md`](backend/docs/TESTING_TIER1.md) for complete checklist.

### 8.3 Frontend Tests

```bash
cd frontend

# Type check
npm run typecheck

# Lint
npm run lint

# Build
npm run build

# Format check
npm run format:check
```

### 8.4 CI Parity

Run the same checks as CI locally:

```bash
# All CI checks
make lint         # Ruff + mypy + frontend typecheck
make test         # Pytest with coverage
make audit        # Dependency security audit
make pre-commit   # All pre-commit hooks

# Individual checks
make audit-python    # Python dependencies only
make audit-frontend  # npm audit only
make verify-adrs     # ADR structure validation
```

---

## 9. CI/CD Pipeline

### 9.1 CI Workflow

The CI pipeline is defined in [`.github/workflows/ci.yml`](.github/workflows/ci.yml):

```mermaid
graph TB
    Push[Push to main / PR] --> Parallel{Run in Parallel}

    Parallel --> DependencyAudit[Dependency Audit]
    Parallel --> PreCommit[Pre-commit Hooks]
    Parallel --> LintTest[Lint & Test]
    Parallel --> FrontendContract[Frontend Contract]

    DependencyAudit --> |pip-audit + npm audit| Done1[✓]
    PreCommit --> |Ruff format + Prettier| Done2[✓]
    LintTest --> |Ruff + mypy + pytest| Done3[✓]
    FrontendContract --> |OpenAPI gen + typecheck| Done4[✓]

    Done1 & Done2 & Done3 & Done4 --> DockerSmoke[Docker Smoke Test]
    DockerSmoke --> |make up + make smoke| Success[✅ CI Pass]
```

### 9.2 Pipeline Stages

#### 1. Dependency Audit
```yaml
- pip-audit (backend dev + enrichers)
- npm audit (frontend high/critical)
- Ignores: PYSEC-2026-1604 (known non-issue)
```

#### 2. Pre-commit Hooks
```yaml
- Ruff format (backend)
- Prettier (frontend)
- Trailing whitespace
- End-of-file fixer
```

#### 3. Lint & Test
```yaml
- Ruff check (linter)
- Ruff format --check
- mypy (type checker)
- pytest with coverage (78% minimum)
- ADR structure verification
```

#### 4. Frontend Contract
```yaml
- Export OpenAPI from backend
- Generate TypeScript types
- Verify no drift (openapi:check)
- Frontend format check
- Frontend typecheck
```

#### 5. Docker Smoke
```yaml
- make setup && make up
- Wait for /health (60s timeout)
- make smoke (full smoke test)
- make down (cleanup)
```

### 9.3 CI Rules and Gates

**Coverage Gate:**
- Minimum 78% line coverage for `backend/app/`
- Configured in `backend/pyproject.toml`
- CI fails if coverage drops below threshold

**No Live External Calls:**
- All enrichers mocked in tests
- No real API keys in CI
- Fake sidecars for integration tests

**Test Markers:**
```python
@pytest.mark.postgres  # Requires Postgres (skipped in CI)
# Default: SQLite tests only
```

**Frontend Contract:**
- OpenAPI schema must be up-to-date
- Generated types committed to repo
- CI fails on drift

### 9.4 Deployment Workflow

**Production Deployment:**
```bash
# Via production script
bash backend/scripts/start_production.sh --env-file .env.production

# With Tier 1
bash backend/scripts/start_production.sh --with-tier1

# With Linux Multilogin
bash backend/scripts/start_production.sh --with-linux-mlx
```

**Deployment Steps:**
1. Merge PR to `main` (after CI pass)
2. Pull latest on production server
3. Run deployment script
4. Run production smoke test
5. Monitor metrics and logs

See [`docs/deployment.md`](docs/deployment.md) for CD workflow details.

---

## 10. Data Flow for Endpoints

### 10.1 POST /enrich (Async)

**Step-by-Step Flow:**

1. **Request hits** `app/modules/enrichment/router.py`
2. **Authentication:** `verify_token` dependency checks Bearer token
3. **Rate Limit Check:** Redis fixed-window counter (30 req/min per token default)
4. **Validation:** `EnrichmentRequest` ensures at least one identifier present
5. **Job Creation:** `JobRepository.create()` persists job with `status=queued`
6. **Enqueue:** `queue.enqueue_enrichment(job_id)` pushes to Redis RQ queue
7. **Return 202:** `{"id": "job_abc", "status": "queued", "dossier": {}}`
8. **Worker Dequeue:** RQ worker picks up job from Redis
9. **Execute:** `Pipeline.run()` via `app/workers/tasks.py`
10. **Suppression Check:** Redis SISMEMBER → SQL fallback
11. **Enrichers Dispatch:** Parallel execution per tier (asyncio.gather)
12. **Merge:** `enrichers/merge.py` assembles unified dossier
13. **Confidence Scoring:** LLM disambiguation for handles < 0.7
14. **Persist:** Job updated to `status=completed`, dossier JSON stored
15. **Client Polls:** `GET /enrich/{id}` until status is `completed`

**Key Points:**
- Works only when API + worker share same Postgres
- Redis unavailable → job marked `failed`, returns 503
- Suppressed identifiers → empty dossier, status `suppressed`

### 10.2 POST /enrich/sync (Synchronous)

**Step-by-Step Flow:**

1. **Request hits** `app/modules/enrichment/router.py`
2. **Authentication:** Bearer token check
3. **Rate Limit Check:** Redis (10 req/min per token default)
4. **Validation:** At least one identifier required
5. **Execute Inline:** `Pipeline.run()` executes in API process
6. **Same Pipeline:** Suppression → Dispatch → Merge → Score
7. **Return 200:** Complete dossier with `status=completed`
8. **No Job Persistence:** (optional, can be added)

**Key Points:**
- No Redis queue involved
- **Tier 1 always skipped** even if `tier1` in `requested_tiers`
- Suitable for fast tiers (2-4)
- Blocks HTTP connection until complete

### 10.3 POST /api/opt-out

**Suppression Flow:**

1. **Request:** Public endpoint (IP rate-limited, 20 req/min)
2. **Hash Identifier:** SHA-256(`identifier`) via `compliance/identifiers.py`
3. **SQL Write:** Insert to `suppression_list` table (durable record)
4. **Redis Cache:** `SADD suppression:hashes <hash>` (fast lookup)
5. **Purge Jobs:** Delete matching jobs from `jobs` table
6. **Purge Photos:** Remove from photo cache
7. **Purge R2:** Delete from object storage (if R2 configured)
8. **Audit Log:** Write to `audit_logs` table
9. **Return 202:** `{"status": "accepted"}`

**Key Points:**
- SQL is source of truth, Redis is cache
- No TTL on suppression hashes (permanent)
- Suppression check: Redis first → SQL fallback → Redis backfill

### 10.4 POST /api/dsar

**Data Subject Access Request Flow:**

1. **Request:** Requires authenticated + verified user (ADR 0009)
2. **Validation:** `request_type` = `access` or `deletion`
3. **Create DSAR:** Insert to `dsar_requests` table
4. **If Access:**
   - Query all data for identifier
   - Return summary (counts, no PII)
5. **If Deletion:**
   - Trigger suppression flow (same as opt-out)
   - Purge jobs, photos, R2 objects
6. **Return 201:** DSAR ID for polling
7. **Poll:** `GET /api/dsar/{id}` until processed

**Key Points:**
- DSAR requires auth (unlike opt-out)
- Access returns summary only, not full dossiers
- Deletion is irreversible

---

## 11. Pipeline Data Flow

### 11.1 Pipeline Execution Diagram

```mermaid
graph TB
    Request[EnrichmentRequest] --> RateLimit{Rate Limit Check}
    RateLimit -->|429 Over Limit| Reject[Return 429]
    RateLimit -->|OK| Suppression{Suppression Check}

    Suppression -->|Redis SISMEMBER| RedisCheck{In Cache?}
    RedisCheck -->|Yes| Suppressed[Return Empty Dossier]
    RedisCheck -->|No| SQLCheck{Check SQL}
    SQLCheck -->|Found| Backfill[Backfill Redis]
    Backfill --> Suppressed
    SQLCheck -->|Not Found| Dispatch[Dispatch Enrichers]

    Dispatch --> TierDispatch{Requested Tiers}

    TierDispatch -->|tier1| Tier1[LinkedIn Photo]
    TierDispatch -->|tier2| Tier2[Sherlock + Maigret + Social Analyzer]
    TierDispatch -->|tier3| Tier3[GitRecon + Email Tools]
    TierDispatch -->|tier4| Tier4[JobSpy + GMaps]

    Tier1 -->|Partial Dict| Merge
    Tier2 -->|Partial Dicts| Merge
    Tier3 -->|Partial Dicts| Merge
    Tier4 -->|Partial Dicts| Merge

    Merge[Merge Partials] --> Confidence[Confidence Scoring]
    Confidence --> LLMCheck{Handles < 0.7?}
    LLMCheck -->|Yes| LLM[LLM Disambiguation]
    LLMCheck -->|No| Persist
    LLM --> Persist[Persist to Postgres]

    Persist --> Complete[Return Dossier]
```

### 11.2 Enricher Lifecycle

Each enricher follows this lifecycle:

1. **Validate:** Check if required identifier present (skip if missing)
2. **Initialize:** Setup resources (browser, HTTP client, etc.)
3. **Run:** Execute enrichment (subprocess/library/sidecar call)
4. **Normalize:** Convert raw output to standard format
5. **Score:** Assign confidence (0.0-1.0)
6. **Cleanup:** Release resources (in `finally` block)
7. **Return:** Partial dict with keys like `photo`, `handles`, `emails`

**Graceful Degradation:**
- Missing tool/sidecar → returns `{}` (empty partial)
- Never crashes the pipeline
- Missing enricher = missing source in `dossier.sources`

### 11.3 Merge Logic

**File:** [`backend/app/enrichers/merge.py`](backend/app/enrichers/merge.py)

**Merge Rules:**
- **Photo:** Take first non-empty
- **Handles:** Dedupe on `(platform, username)`, keep higher confidence
- **Emails:** Dedupe by value
- **Verified Emails:** Prefer SMTP-verified over basic
- **GitHub:** Merge metadata, sum commit counts
- **Coworkers:** Dedupe by email
- **Jobs:** Dedupe by `(title, company)`
- **Business:** Take first non-empty

**Confidence Calculation:**
```python
# Handle confidence from multiple enrichers
if same_handle_from_2_sources:
    confidence = max(conf1, conf2)  # Take higher
if same_handle_from_3+_sources:
    confidence = min(0.95, avg + 0.1)  # Boost for consensus
```

### 11.4 LLM Disambiguation

**Trigger:** Any handle with confidence < `DISAMBIGUATION_THRESHOLD` (default 0.7)

**File:** [`backend/app/enrichers/disambiguate.py`](backend/app/enrichers/disambiguate.py)

**LLM Client:** [`backend/app/clients/llm.py`](backend/app/clients/llm.py)

**Mode Selection (`LLM_MODE`):**
- `stub` (default): Heuristic string match, no network calls
- `ollama`: Local model via Ollama sidecar
- `litellm`: LiteLLM proxy with fallback chain

**Disambiguation Flow:**
1. Walk handles below threshold
2. Call `llm.compare(target_identity, handle_evidence)`
3. If match: boost confidence = `max(original, llm_confidence)`
4. If no match: drop handle
5. Keep only handles ≥ 0.7

**Tracing:** All LLM calls traced in Langfuse (when `LANGFUSE_*` configured)

---

## 12. Common Issues & Fixes

### 12.1 Jobs Stuck in "queued" Status

**Symptom:** `GET /enrich/{id}` shows `status=queued` indefinitely

**Diagnosis:**
```bash
# Check worker is running
docker ps | grep worker

# Check worker logs
docker compose logs worker --tail 100

# Check Redis connectivity from worker
docker compose exec worker redis-cli -u $REDIS_URL ping

# Check RQ queue status
docker compose exec worker python -c "
from app.workers.queue import q
print(f'Queued: {len(q)}, Failed: {len(q.failed_job_registry)}')
"
```

**Common Causes:**
1. Worker not running
2. Redis disconnected
3. Worker crashed during startup
4. Job in failed_job_registry

**Fix:**
```bash
# Restart worker
docker compose restart worker

# If still stuck, check failed jobs
docker compose exec worker rq info --url $REDIS_URL

# Clear failed jobs (CAUTION: loses error info)
docker compose exec worker python -c "
from app.workers.queue import q
q.failed_job_registry.cleanup(0)
"
```

### 12.2 Empty Dossier Fields

**Symptom:** Dossier has `null` or `[]` for expected fields

**Diagnosis:**
```bash
# Check which enrichers ran
curl http://localhost:8000/enrich/{job_id} | jq '.dossier.sources'

# Expected output: ["sherlock", "maigret", "gitrecon", ...]
# Missing source = that enricher returned {}

# Probe missing enricher
docker compose exec worker python scripts/probe_enrichers.py --only sherlock

# Check sidecar connectivity
docker compose exec worker curl -fsS http://social-analyzer:9005/get_settings
```

**Common Causes:**
1. Username doesn't exist on those platforms (normal)
2. Enricher CLI timed out
3. Sidecar unreachable
4. API rate limited (GitHub, LinkedIn)
5. Tool not installed in worker container

**Fix:**
```bash
# Verify enricher prerequisites
docker compose exec worker python scripts/probe_enrichers.py --prereqs

# Check tool installation
docker compose exec worker which sherlock maigret

# For GitHub rate limits, set GITHUB_TOKEN
# backend/.env:
# GITHUB_TOKEN=ghp_...
```

### 12.3 Rate Limit 429 Errors

**Symptom:** `HTTP 429 Too Many Requests`

**Cause:** Exceeded rate limits (default: 30 async/min, 10 sync/min per token)

**Diagnosis:**
```bash
# Check current rate limit config
grep MAX_.*_REQUESTS_PER_MINUTE backend/.env

# Check Redis for rate limit keys
docker compose exec redis redis-cli --scan --pattern "ratelimit:*"
```

**Fix:**
```bash
# Option 1: Slow down client requests
# Implement exponential backoff: 1s, 2s, 4s, 8s...

# Option 2: Increase limits (temporarily)
# backend/.env:
# MAX_ASYNC_REQUESTS_PER_MINUTE=60
# MAX_SYNC_REQUESTS_PER_MINUTE=20

# Restart API
docker compose restart api
```

**Best Practice:** Implement retry with exponential backoff on client side.

### 12.4 Multilogin Connection Failed

**Symptom:** Tier 1 jobs fail with connection errors

**See [Section 7](#7-multilogin-setup--issues) for detailed troubleshooting.**

Quick checks:
```bash
# Verify Multilogin running
curl -sk https://127.0.0.1:45001/api/v2/

# Check worker network mode
docker inspect <worker-container> | grep NetworkMode

# Verify environment variables
docker compose exec worker env | grep MULTILOGIN
```

### 12.5 Alembic Migration Failed

**Symptom:** API won't start, migration errors in logs

**PREFERRED FIX: Restore from backup** (never downgrade in production)

**Diagnosis:**
```bash
# Check current Alembic version
docker compose exec api python -c "
from alembic.config import Config
from alembic import script
from alembic.runtime.migration import MigrationContext
from app.database.engine import engine
cfg = Config('alembic.ini')
script_dir = script.ScriptDirectory.from_config(cfg)
with engine.connect() as conn:
    context = MigrationContext.configure(conn)
    print(f'Current: {context.get_current_revision()}')
    print(f'Head: {script_dir.get_current_head()}')
"

# View migration logs
docker compose logs api | grep alembic
```

**Recovery:**
```bash
# Stop services
docker compose down

# Restore Postgres from backup
docker run --rm -v postgres_data:/data -v $(pwd):/backup \
  postgres:15-alpine sh -c "cd /data && tar xvf /backup/postgres-backup.tar"

# Restart
docker compose up -d
```

### 12.6 Quick Diagnostic Commands

```bash
# Health checks
curl http://localhost:8000/health      # Liveness
curl http://localhost:8000/ready       # Readiness

# Database connectivity
docker compose exec api psql $DATABASE_URL -c "SELECT 1"

# Redis connectivity
docker compose exec api redis-cli -u $REDIS_URL ping

# View logs
docker compose logs -f api worker

# Queue inspection
docker compose exec worker python -c "
from app.workers.queue import q
print(f'Queued: {len(q)}')
print(f'Failed: {len(q.failed_job_registry)}')
"

# Enricher isolation test
docker compose exec worker python scripts/probe_enrichers.py
```

For comprehensive troubleshooting, see [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

---

## 13. Environment Files

### 13.1 Environment File Structure

**Location:** `backend/.env` (gitignored)

**Template:** [`backend/.env.example`](backend/.env.example)

**Docker Usage:**
```bash
# Load from default location
docker compose --env-file backend/.env up

# Load from custom location
docker compose --env-file /path/to/.env.production up

# Worker-specific secrets (Tier 1)
export WORKER_ENV_FILE=/path/to/tier1-secrets.env
docker compose -f docker-compose.tier1.yml up
```

### 13.2 Critical Production Variables

**Authentication & Security:**
```bash
SECRET_KEY=                           # REQUIRED: 256-bit key (openssl rand -hex 32)
JWT_ALGORITHM=HS256                   # JWT signing algorithm
ACCESS_TOKEN_EXPIRE_MINUTES=15        # Access token lifetime
REFRESH_TOKEN_EXPIRE_DAYS=7           # Refresh token lifetime
COOKIE_SECURE=true                    # HTTPS-only cookies (production)
COOKIE_DOMAIN=.yourdomain.com         # Cookie domain
```

**Database & Cache:**
```bash
DATABASE_URL=postgresql+asyncpg://hyrepath:${POSTGRES_PASSWORD}@postgres:5432/hyrepath
REDIS_URL=redis://redis:6379/0
DB_POOL_SIZE=10                       # SQLAlchemy pool size
DB_MAX_OVERFLOW=20                    # Max overflow connections
```

**Object Storage:**
```bash
R2_ACCOUNT_ID=                        # Cloudflare R2 account
R2_ACCESS_KEY_ID=                     # R2 access key
R2_SECRET_ACCESS_KEY=                 # R2 secret key
R2_BUCKET=hyrepath-assets             # Bucket name
R2_PUBLIC_BASE_URL=https://cdn.example.com  # CDN base URL
```

**Rate Limits:**
```bash
MAX_SYNC_REQUESTS_PER_MINUTE=10       # Sync endpoint limit per token
MAX_ASYNC_REQUESTS_PER_MINUTE=30      # Async endpoint limit per token
MAX_COMPLIANCE_REQUESTS_PER_MINUTE=20 # Opt-out/DSAR limit per IP
```

**Email Service:**
```bash
SENDGRID_API_KEY=                     # SendGrid API key
SENDGRID_FROM_EMAIL=noreply@yourdomain.com
FRONTEND_URL=https://app.yourdomain.com
```

**Tier 1 (LinkedIn):**
```bash
ENABLE_TIER1=true                     # Enable Tier 1 (worker only)
BROWSER_MODE=multilogin               # Browser backend
MULTILOGIN_EMAIL=                     # Multilogin account
MULTILOGIN_PASSWORD=                  # Multilogin password
MULTILOGIN_FOLDER_ID=                 # Profile folder ID
MULTILOGIN_WORKSPACE_ID=              # Workspace ID
MULTILOGIN_DAILY_VIEW_LIMIT=22        # Max views per profile per day
LINKEDIN_BOT_EMAIL=                   # Bot account email
LINKEDIN_BOT_PASSWORD=                # Bot account password
```

### 13.3 Worker-Specific Overrides

**Tier 1 Worker (host network):**
```bash
# docker-compose.tier1.yml overrides these:
DATABASE_URL=postgresql+asyncpg://...@127.0.0.1:5432/...
REDIS_URL=redis://127.0.0.1:6379/0
MULTILOGIN_SELENIUM_HOST=http://127.0.0.1
```

**Why:** Host network mode requires `127.0.0.1` instead of service names.

### 13.4 Environment Validation

```bash
# Validate before starting
cd backend
bash scripts/validate_env.sh

# Check specific variables
docker compose exec api env | grep -E '(DATABASE_URL|REDIS_URL|SECRET_KEY)'
```

**Production Checklist:**
- [ ] `SECRET_KEY` is strong (32+ bytes)
- [ ] `COOKIE_SECURE=true` (HTTPS only)
- [ ] `DATABASE_URL` points to production Postgres
- [ ] `R2_*` credentials configured
- [ ] `SENDGRID_API_KEY` set
- [ ] Rate limits appropriate for expected load
- [ ] `APP_ENV=production`

---

## 14. Docker Network Configuration

### 14.1 Hybrid Networking Architecture

The project uses **hybrid networking** (see [`backend/docker/NETWORKING.md`](backend/docker/NETWORKING.md)):

- **Bridge Network (Default):** Most services
- **Host Network (Tier 1 Only):** Worker + Multilogin

```mermaid
graph TB
    subgraph BridgeNetwork[Bridge Network - Default]
        API[API :8000]
        Worker234[Tier 2-4 Workers]
        Postgres[(Postgres :5432)]
        Redis[(Redis :6379)]
        Sidecars[Sidecars]

        API -->|postgres:5432| Postgres
        API -->|redis:6379| Redis
        Worker234 -->|postgres:5432| Postgres
        Worker234 -->|redis:6379| Redis
        Worker234 --> Sidecars
    end

    subgraph HostNetwork[Host Network - Tier 1 Only]
        Worker1[Tier 1 Worker]
        Multilogin[Multilogin Container]

        Worker1 -->|127.0.0.1| Multilogin
        Worker1 -->|127.0.0.1:5432| PostgresHost[Postgres via Host]
        Worker1 -->|127.0.0.1:6379| RedisHost[Redis via Host]
    end
```

### 14.2 Bridge Network (Default)

**Used By:** API, Tier 2-4 workers, Postgres, Redis, all sidecars

**Benefits:**
- Automatic DNS resolution (`postgres:5432`)
- Horizontally scalable (no port conflicts)
- Network namespace isolation
- Easy service discovery

**Configuration:**
```yaml
# docker-compose.yml (default, no network_mode specified)
services:
  api:
    # Uses bridge network by default
    environment:
      DATABASE_URL: postgresql://...@postgres:5432/db
      REDIS_URL: redis://redis:6379/0
```

**Service Resolution:**
```bash
# Inside bridge network containers
DATABASE_URL=postgresql+asyncpg://hyrepath:password@postgres:5432/hyrepath
REDIS_URL=redis://redis:6379/0
EMAIL_VERIFIER_URL=http://email-verifier:8080
SOCIAL_ANALYZER_URL=http://social-analyzer:9005
```

### 14.3 Host Network (Tier 1 Only)

**Used By:** Tier 1 worker, Multilogin container (Linux)

**Why Required:** Multilogin binds Selenium to `127.0.0.1` only. Worker must share host loopback to reach it.

**Configuration:**
```yaml
# docker-compose.tier-workers.yml
services:
  worker-tier1:
    network_mode: host
    environment:
      DATABASE_URL: postgresql://...@127.0.0.1:5432/db  # Note: 127.0.0.1, not postgres
      REDIS_URL: redis://127.0.0.1:6379/0
      MULTILOGIN_SELENIUM_HOST: http://127.0.0.1
```

**Limitation:** Cannot scale (port conflicts). Only 1 Tier 1 worker per host.

### 14.4 Service Discovery Examples

**Bridge Network Container:**
```bash
# Can use service names
curl http://social-analyzer:9005/get_settings
curl http://google-maps-scraper:8080/api/docs
psql postgresql://user:pass@postgres:5432/db
```

**Host Network Container (Tier 1):**
```bash
# Must use 127.0.0.1
curl http://127.0.0.1:9005/get_settings  # Fails - wrong network
psql postgresql://user:pass@127.0.0.1:5432/db  # Works
```

### 14.5 Troubleshooting Network Issues

**Problem: "could not translate host name 'postgres'"**

**Diagnosis:** Service on host network trying to use bridge service name.

**Fix:** Ensure Tier 1 worker overrides URLs with `127.0.0.1`.

**Problem: Tier 1 cannot reach Multilogin**

**Diagnosis:** Network mode mismatch.

**Fix:**
```bash
# Verify both use host network
docker inspect worker-tier1 | grep NetworkMode
docker inspect multilogin | grep NetworkMode
# Both should show: "NetworkMode": "host"
```

**Problem: Cannot scale Tier 1 workers**

**Diagnosis:** Host network mode = shared ports.

**Workaround:** Run on multiple physical/virtual machines.

For complete network architecture, see [`backend/docker/NETWORKING.md`](backend/docker/NETWORKING.md).

---

## 15. What Has Been Built

### 15.1 Backend Features (Complete)

**API & Authentication:**
- ✅ FastAPI HTTP server with Bearer token auth
- ✅ Cookie-based authentication with FastAPI-Users (ADR 0009)
- ✅ Email verification flow (24h expiry)
- ✅ Google OAuth integration
- ✅ Token blacklist (Redis + PostgreSQL dual-write)
- ✅ Rate limiting per API token (Redis fixed-window)
- ✅ CORS configuration

**Enrichment Pipeline:**
- ✅ Async job queue (Redis + RQ)
- ✅ Sync enrichment path (`POST /enrich/sync`)
- ✅ Job polling (`GET /enrich/{id}`)
- ✅ Pipeline orchestrator (`app/enrichers/pipeline.py`)
- ✅ 11 enricher modules across 4 tiers
- ✅ Provider layer for free/paid mode switches
- ✅ Merge logic with confidence scoring
- ✅ LLM disambiguation (stub/ollama/litellm)
- ✅ Graceful degradation (enrichers return empty on failure)

**Compliance & Privacy:**
- ✅ Opt-out/suppression system (SQL + Redis dual-write)
- ✅ DSAR flow (access + deletion)
- ✅ Data erasure (jobs, photos, R2 objects)
- ✅ Audit logs (5-year retention)
- ✅ Authentication audit logs

**Storage & Infrastructure:**
- ✅ PostgreSQL with pgvector extension
- ✅ SQLite for local development
- ✅ Database migrations via Alembic
- ✅ Redis for queue, cache, rate limits
- ✅ R2 photo cache (with local fallback)
- ✅ Photo cache by LinkedIn slug

**Observability:**
- ✅ Health, readiness, Prometheus metrics endpoints
- ✅ Structured JSON logging (stdlib)
- ✅ GlitchTip/Sentry integration
- ✅ Langfuse LLM tracing (optional)

**Docker & Deployment:**
- ✅ Multi-stage Docker builds (API, Worker, Postgres, Sidecars)
- ✅ Docker Compose orchestration
- ✅ Compose healthchecks
- ✅ Hybrid networking (bridge + host)
- ✅ Tier-specific workers
- ✅ Sequential worker startup (rate limit friendly)

**Testing:**
- ✅ Unit tests (pytest, 78% coverage gate)
- ✅ Shape tests (enricher output validation)
- ✅ Integration tests (E2E compose)
- ✅ Fake sidecars for CI
- ✅ Load testing harness (k6)
- ✅ Smoke tests

### 15.2 Frontend Features (Complete)

**Core UI:**
- ✅ Enrichment intake form (email, LinkedIn, username, company, business, job)
- ✅ Tier selection (tier1-tier4)
- ✅ Pipeline visualization
- ✅ Merged dossier presentation
- ✅ Job history and status tracking
- ✅ Public opt-out form

**Authentication:**
- ✅ Login/register pages
- ✅ Email verification flow
- ✅ Google OAuth integration
- ✅ Protected routes
- ✅ Session management

**API Integration:**
- ✅ Next.js API routes (BFF pattern)
- ✅ OpenAPI-generated TypeScript types
- ✅ TanStack Query for data fetching
- ✅ SSE for job completion notifications

**UI/UX:**
- ✅ Tailwind CSS styling
- ✅ Responsive design
- ✅ Dark mode support
- ✅ Loading states
- ✅ Error handling

### 15.3 Infrastructure (Complete)

**Sidecars (Isolated AGPL):**
- ✅ social-analyzer (Tier 2 NLP scoring)
- ✅ google-maps-scraper (Tier 4 business info)
- ✅ email-verifier (Tier 3 basic validation)
- ✅ reacher (Tier 3 SMTP - optional)
- ✅ litellm (LLM proxy - optional)
- ✅ ollama (Local LLM - optional)
- ✅ langfuse (LLM observability - optional)
- ✅ glitchtip (Error tracking - optional)
- ✅ changedetection (Change signals - optional)

**Development Tools:**
- ✅ Makefile with common targets
- ✅ Pre-commit hooks (Ruff, Prettier)
- ✅ GitHub Actions CI/CD
- ✅ Dependency security audits
- ✅ ADR verification script

**Documentation:**
- ✅ Architecture documentation
- ✅ Testing guides (Tier 1, Tier 2-4)
- ✅ Troubleshooting guide
- ✅ Deployment guide
- ✅ Network architecture guide
- ✅ 12 Architecture Decision Records (ADRs)
- ✅ This KT document!

See [`CHANGELOG.md`](CHANGELOG.md) for detailed release history.

---

## 16. What We're Currently Building

### 16.1 Foundation Week 1 Features

**Document Processing Pipeline:**
- 🔄 Document worker for CV/resume parsing
- 🔄 Text extraction and cleaning
- 🔄 Metadata extraction (experience, education, skills)
- 🔄 Integration with enrichment pipeline

**Embedding Workers:**
- 🔄 Embedding worker with cost monitoring
- 🔄 Vector generation via OpenAI/local models
- 🔄 Cost tracking and alerting
- 🔄 Batch processing optimization

**Vector Search:**
- 🔄 pgvector extension integration
- 🔄 Vector similarity search
- 🔄 Semantic search endpoints
- 🔄 Index optimization

**Semantic Chunking:**
- 🔄 Intelligent document chunking strategy
- 🔄 Context-aware splitting
- 🔄 Chunk overlap management
- 🔄 Quality metrics

See [`FOUNDATION_WEEK1_FINAL_COMPLETE.md`](FOUNDATION_WEEK1_FINAL_COMPLETE.md) for sprint details.

### 16.2 Authentication Enhancements

**Cookie-Based OAuth (ADR 0009):**
- 🔄 FastAPI-Users integration
- 🔄 httpOnly secure cookies
- 🔄 Refresh token rotation
- 🔄 Token blacklist (Redis + Postgres)

**Email Verification:**
- 🔄 SendGrid integration
- 🔄 Verification link generation
- 🔄 24h expiry tokens
- 🔄 Resend verification email

**Google OAuth:**
- 🔄 OAuth 2.0 flow
- 🔄 Callback handler
- 🔄 User profile sync
- 🔄 Account linking

**Access Control:**
- 🔄 Unverified user restrictions
- 🔄 Verified-only endpoints
- 🔄 Security audit logging

### 16.3 Testing Infrastructure

**Canary Test Sets:**
- 🔄 20-profile QA sets per tier
- 🔄 Automated scoring
- 🔄 Regression detection
- 🔄 Performance baselines

**Fake Sidecars:**
- 🔄 Mock sidecar implementations
- 🔄 CI/CD integration
- 🔄 Deterministic responses
- 🔄 Fast test execution

**Load Testing:**
- 🔄 k6 scenario definitions
- 🔄 Elevated rate limits for testing
- 🔄 Concurrent user simulation
- 🔄 Performance reporting

---

## 17. What We Need to Build

### 17.1 Priority Next Slices

**1. Unauthenticated Opt-Out**
- Remove Bearer auth requirement for `/api/opt-out`
- Public form accessible without API key
- IP rate-limiting only
- GDPR/LGPD/CCPA compliance
- See [`backend/docs/LEGAL.md`](backend/docs/LEGAL.md)

**2. Real R2 Uploads**
- Wire `aioboto3` to Cloudflare R2
- Currently using local `.asset-cache/` fallback
- Implement PutObject + HeadObject verify
- CDN URL generation
- Graceful fallback on R2 errors

**3. Tier 1 Production Hardening**
- Multilogin profile pool management
- Session reuse optimization
- Rate limit tuning (22 views/day default)
- Cooldown after captcha/auth failures
- Profile health monitoring
- See [`backend/docs/TESTING_TIER1.md`](backend/docs/TESTING_TIER1.md)

**4. Frontend Async Polling**
- Replace `/enrich/sync` with `/enrich` + poll
- Better UX for long-running jobs
- SSE progress updates
- Toast notifications on completion
- Job history improvements

**5. LLM Prompt Tuning**
- Real disambiguation prompts (not stubs)
- Few-shot examples
- Langfuse cost dashboards
- Model comparison (GPT vs Gemini vs Claude)
- Fallback chain optimization

**6. Sidecar Contract Verification**
- Validate gitrecon JSON schema
- Test social-analyzer endpoints against live
- GMaps scraper contract tests
- Error handling for malformed responses
- Versioning strategy

**7. Integration Tests in CI**
- GitHub Actions workflow
- Fake sidecars via compose override
- Automated E2E in PR checks
- Performance regression detection

### 17.2 Infrastructure Improvements

**Automated Backups:**
- Postgres daily backups
- Redis snapshot strategy
- R2 backup bucket
- Restore procedures
- Backup verification

**Advanced Monitoring:**
- Grafana dashboards
- Prometheus alert rules
- Service health metrics
- Business metrics (jobs/day, success rate)
- Cost tracking

**Alerting:**
- PagerDuty integration
- Slack webhooks
- Email alerts
- Severity levels
- On-call rotations

**Log Aggregation:**
- ELK stack or Loki
- Centralized logging
- Log retention policies
- Search and analysis
- Audit trail compliance

**CI Performance:**
- Parallel test execution
- Docker layer caching
- Incremental builds
- Test result caching

### 17.3 Feature Enhancements

**Bulk Enrichment API:**
- Batch endpoint (`POST /enrich/bulk`)
- CSV/JSON import
- Progress tracking
- Result export
- Rate limit considerations

**Webhook Notifications:**
- Job completion webhooks
- Configurable per user
- Retry logic
- Signature verification
- Payload customization

**Data Export:**
- CSV export endpoint
- JSON export with pagination
- Full dossier download
- Scheduled exports
- Format customization

**Advanced Search:**
- Filter by tier, status, date
- Full-text search in dossiers
- Tag system
- Saved searches
- Search API

**User Dashboard:**
- Usage statistics
- Cost breakdown
- API key management
- Team management
- Audit log viewer

### 17.4 Technical Debt

**Code Quality:**
- Increase test coverage to 85%
- Add integration tests for all enrichers
- Refactor large modules
- Type hint completion
- Documentation gaps

**Performance:**
- Database query optimization
- Redis connection pooling
- Async operation improvements
- Caching strategy refinement

**Security:**
- Dependency updates
- Security scan automation
- Secrets rotation
- API rate limit tuning
- Input validation hardening

See **Implementation status** in [`backend/docs/ARCHITECTURE.md`](backend/docs/ARCHITECTURE.md) for authoritative feature matrix.

---

## 18. Additional Resources

### 18.1 Key Documentation

**Project Overview:**
- [`README.md`](README.md) - Main project overview, features, setup
- [`CHANGELOG.md`](CHANGELOG.md) - Ticket-level release notes
- [`RULE.md`](RULE.md) - Development rules (reuse, architecture, safety)
- [`AGENTS.md`](AGENTS.md) - Agent session behavior and memory

**Architecture & Design:**
- [`backend/docs/ARCHITECTURE.md`](backend/docs/ARCHITECTURE.md) - Detailed backend architecture
- [`docs/FOUNDATION_ARCHITECTURE.md`](docs/FOUNDATION_ARCHITECTURE.md) - Foundation Week 1 architecture
- [`docs/architecture-plan-azi-10-hyre-enrichment.md`](docs/architecture-plan-azi-10-hyre-enrichment.md) - Original architecture plan
- [`docs/architecture-plan-azi-11-backend-separation.md`](docs/architecture-plan-azi-11-backend-separation.md) - Backend separation plan

**Architecture Decision Records:**
- [`docs/adr/README.md`](docs/adr/README.md) - ADR index and guidelines
- [`docs/adr/0001-async-redis-rq.md`](docs/adr/0001-async-redis-rq.md) - Async job execution
- [`docs/adr/0002-sqlite-local-postgres-docker.md`](docs/adr/0002-sqlite-local-postgres-docker.md) - Database strategy
- [`docs/adr/0003-pipeline-enricher-model.md`](docs/adr/0003-pipeline-enricher-model.md) - Pipeline model
- [`docs/adr/0008-tier1-linux-host-network.md`](docs/adr/0008-tier1-linux-host-network.md) - Tier 1 networking
- [`docs/adr/0009-cookie-oauth-authentication.md`](docs/adr/0009-cookie-oauth-authentication.md) - Cookie-based auth

**Testing & Operations:**
- [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) - Common issues and fixes
- [`backend/docs/TESTING_TIER1.md`](backend/docs/TESTING_TIER1.md) - Tier 1 testing checklist
- [`backend/docs/TESTING_TIER234.md`](backend/docs/TESTING_TIER234.md) - Tier 2-4 testing guide
- [`backend/docs/LOAD_TESTING.md`](backend/docs/LOAD_TESTING.md) - Load testing guide
- [`docs/OPS.md`](docs/OPS.md) - Operations runbook
- [`docs/ALERTING.md`](docs/ALERTING.md) - Alerting configuration
- [`docs/PROD_SMOKE.md`](docs/PROD_SMOKE.md) - Production smoke tests
- [`docs/PROD_ACCEPTANCE.md`](docs/PROD_ACCEPTANCE.md) - Acceptance test suite

**Setup & Deployment:**
- [`docs/DEV_SETUP_WSL.md`](docs/DEV_SETUP_WSL.md) - Windows/WSL2 setup guide
- [`docs/deployment.md`](docs/deployment.md) - Deployment workflow
- [`docs/BACKUP_RESTORE.md`](docs/BACKUP_RESTORE.md) - Backup and restore procedures
- [`backend/docker/README-DEPLOYMENT.md`](backend/docker/README-DEPLOYMENT.md) - Production deployment
- [`backend/docker/NETWORKING.md`](backend/docker/NETWORKING.md) - Docker networking architecture

**Compliance & Legal:**
- [`backend/docs/LEGAL.md`](backend/docs/LEGAL.md) - Legal posture and source limits
- [`docs/SECURITY_HARDENING.md`](docs/SECURITY_HARDENING.md) - Security best practices

**Integration & API:**
- [`docs/integrations/README.md`](docs/integrations/README.md) - Integration guide
- [`docs/integrations/python.md`](docs/integrations/python.md) - Python client examples
- [`docs/integrations/nodejs.md`](docs/integrations/nodejs.md) - Node.js client examples
- [`docs/integrations/webhooks.md`](docs/integrations/webhooks.md) - Webhook integration
- [`docs/integrations/bulk-processing.md`](docs/integrations/bulk-processing.md) - Bulk processing
- [`docs/integrations/common-errors.md`](docs/integrations/common-errors.md) - Common integration errors

**User Documentation:**
- [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) - End-user guide
- [`docs/google-oauth-setup.md`](docs/google-oauth-setup.md) - Google OAuth setup
- [`docs/authentication-guide.md`](docs/authentication-guide.md) - Authentication guide

### 18.2 Important Configuration Files

**Environment:**
- [`backend/.env.example`](backend/.env.example) - All environment variables documented
- [`frontend/.env.example`](frontend/.env.example) - Frontend configuration

**Build & Deployment:**
- [`Makefile`](Makefile) - Common development commands
- [`backend/pyproject.toml`](backend/pyproject.toml) - Python package configuration
- [`frontend/package.json`](frontend/package.json) - Frontend dependencies
- [`.github/workflows/ci.yml`](.github/workflows/ci.yml) - CI pipeline
- [`.github/pull_request_template.md`](.github/pull_request_template.md) - PR template

**Docker:**
- All compose files in [`backend/docker/`](backend/docker/)
- All Dockerfiles in [`backend/docker/`](backend/docker/)
- [`backend/docker/docker-compose.yml`](backend/docker/docker-compose.yml) - Base services
- [`backend/docker/docker-compose.prod.yml`](backend/docker/docker-compose.prod.yml) - Production

**Database:**
- [`backend/alembic/`](backend/alembic/) - Database migrations
- [`backend/alembic/README`](backend/alembic/README) - Alembic usage

### 18.3 Useful Scripts

**Testing:**
```bash
backend/scripts/smoke_test.py              # Health check
backend/scripts/probe_enrichers.py         # Test enrichers in isolation
backend/scripts/probe_tier1.py             # Tier 1 specific tests
backend/scripts/e2e_compose_test.sh        # Docker E2E
backend/scripts/e2e_realworld_strict.py    # Real-world validation
backend/scripts/run_load_test.py           # k6 load test harness
backend/scripts/run_canary_score.py        # 20-profile QA
```

**Maintenance:**
```bash
backend/scripts/validate_env.sh            # Environment validation
backend/scripts/purge_audit_logs.py        # Audit log cleanup (5-year retention)
backend/scripts/verify_adrs.py             # ADR structure validation
scripts/dependency_audit.sh                # Security audit
```

**Ops:**
```bash
backend/scripts/start_production.sh        # Production deployment
backend/docker/rebuild-postgres.sh         # Rebuild Postgres volume
backend/docker/run_real_infrastructure_tests.sh  # Infrastructure tests
```

**Probes:**
```bash
backend/scripts/probe_social_analyzer.sh   # Social analyzer health
backend/scripts/probe_gmaps.sh             # Google Maps scraper health
backend/scripts/probe_reacher.sh           # Reacher health
```

### 18.4 Support & Community

**Getting Help:**
1. Check [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) first
2. Search existing issues on GitHub
3. Review relevant ADR for design rationale
4. Ask in team chat with context

**Reporting Bugs:**
1. Check if already reported
2. Provide minimal reproduction
3. Include logs and environment
4. Tag with appropriate tier (`[Tier N]` prefix)

**Contributing:**
1. Read [`RULE.md`](RULE.md) before coding
2. Follow branch naming conventions
3. Write tests for new features
4. Update documentation
5. Follow PR template

---

## 19. Quick Command Reference

### 19.1 Setup Commands

```bash
# Initial setup
make setup              # Create .env, venv, install dependencies
make up                 # Start Docker stack
make down               # Stop Docker stack
make smoke              # Health check

# Manual setup
cd backend
cp .env.example .env
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pip install requests
```

### 19.2 Development Commands

```bash
# Testing
make test               # Run pytest with coverage
make smoke              # Smoke test
make boundary-checks    # Compliance boundary tests
make load-test          # k6 load test
make integration-e2e    # Full-stack E2E
make e2e-full-path      # Full-path E2E (CI mode)

# Code quality
make lint               # Ruff + mypy + frontend typecheck
make format             # Format backend + frontend
make pre-commit         # Run all pre-commit hooks
make audit              # Dependency security audit
make audit-python       # Python audit only
make audit-frontend     # Frontend audit only
make verify-adrs        # Validate ADRs
```

### 19.3 Database Commands

```bash
# Migrations
make migrate            # Apply Alembic migrations
alembic revision -m "Add new table"  # Create migration
alembic upgrade head    # Apply all migrations
alembic downgrade -1    # Rollback one migration (dev only)
alembic current         # Show current revision
alembic history         # Show migration history

# Database access
docker compose exec postgres psql -U hyrepath -d hyrepath
# Or using DATABASE_URL
docker compose exec api psql $DATABASE_URL -c "SELECT COUNT(*) FROM jobs;"
```

### 19.4 Docker Commands

```bash
# Service management
docker compose ps                        # List services
docker compose logs -f api               # Follow API logs
docker compose logs --tail 100 worker    # Last 100 lines
docker compose restart api worker        # Restart services
docker compose exec api bash             # Shell in API container

# Building
docker compose build                     # Build all
docker compose build --no-cache worker   # Clean rebuild
DOCKER_BUILDKIT=0 docker compose build   # Without BuildKit

# Scaling
docker compose up -d --scale worker-tier234=6  # Scale workers

# Cleanup
docker compose down                      # Stop and remove containers
docker compose down -v                   # Also remove volumes
docker system prune -a                   # Clean all unused Docker data
```

### 19.5 Testing Commands

```bash
# Backend tests
cd backend
pytest tests -v                          # All tests
pytest tests -m "not postgres"           # Skip Postgres tests
pytest tests/test_pipeline_shape.py -v   # Specific test file
pytest tests -k "test_sherlock"          # Run tests matching pattern

# Enricher tests
python scripts/probe_enrichers.py                    # All enrichers
python scripts/probe_enrichers.py --only sherlock    # Specific enricher
python scripts/probe_enrichers.py --prereqs          # Prerequisites check
python scripts/probe_enrichers.py --json             # JSON output

# E2E tests
bash scripts/e2e_compose_test.sh         # Docker E2E
bash scripts/e2e_tier2.sh                # Tier 2 E2E
bash scripts/e2e_tier3.sh                # Tier 3 E2E
python scripts/e2e_realworld_strict.py   # Real-world validation

# Frontend tests
cd frontend
npm run typecheck                        # TypeScript check
npm run lint                             # ESLint
npm run build                            # Production build
```

### 19.6 Production Commands

```bash
# Deployment
bash backend/scripts/start_production.sh --env-file .env.production
bash backend/scripts/start_production.sh --with-tier1
bash backend/scripts/start_production.sh --with-linux-mlx

# Production smoke
BASE_URL=https://enrich.hyrepath.io API_TOKEN="$PROD_TOKEN" make smoke-prod

# Monitoring
docker compose logs -f --tail=100        # All logs
curl https://enrich.hyrepath.io/health   # Health check
curl https://enrich.hyrepath.io/metrics  # Prometheus metrics

# Backups
bash backend/scripts/backup_postgres.sh  # Manual backup
bash backend/scripts/restore_postgres.sh <backup-file>  # Restore
```

### 19.7 Diagnostic Commands

```bash
# Health checks
curl http://localhost:8000/health        # Liveness
curl http://localhost:8000/ready         # Readiness
curl http://localhost:8000/metrics       # Prometheus metrics

# Database
docker compose exec api psql $DATABASE_URL -c "SELECT 1;"
docker compose exec postgres psql -U hyrepath -c "\l"  # List databases

# Redis
docker compose exec redis redis-cli ping
docker compose exec redis redis-cli INFO
docker compose exec redis redis-cli --scan --pattern "ratelimit:*"

# Queue
docker compose exec worker python -c "
from app.workers.queue import q
print(f'Queued: {len(q)}, Failed: {len(q.failed_job_registry)}')
"

# Network
docker network ls
docker network inspect <network-name>
docker compose exec api ping postgres
```

### 19.8 Git Commands

```bash
# Branch management
git checkout -b feat/new-feature          # Create feature branch
git checkout main                         # Switch to main
git pull origin main                      # Update main
git branch -d feat/old-feature            # Delete merged branch

# Committing
git add .
git commit -m "feat: add new enricher"    # Follow conventional commits
git push -u origin feat/new-feature       # Push new branch

# Pull requests
gh pr create --title "Add new enricher" --body "..."
gh pr list                                # List PRs
gh pr view 123                            # View PR details
```

### 19.9 Complete Backend Deployment (One Command)

**Testing/Development (1 worker each):**

```bash
cd backend/docker

# BUILD AND START EVERYTHING (all compose files + all profiles)
# Includes containerized Multilogin X
# Default: 1 worker-tier1 + 1 worker-tier234 (no scaling for testing)
docker compose --env-file ../.env.production \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier1.yml \
  -f docker-compose.tier-workers.yml \
  -f docker-compose.multilogin.yml \
  -f docker-compose.foundation.yml \
  --profile paid \
  --profile llm \
  --profile observability \
  up -d --build
```

**Production (Scaled):**

```bash
# Same command but scale tier234 workers for production load
docker compose --env-file ../.env.production \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier1.yml \
  -f docker-compose.tier-workers.yml \
  -f docker-compose.multilogin.yml \
  -f docker-compose.foundation.yml \
  --profile paid \
  --profile llm \
  --profile observability \
  up -d --build --scale worker-tier234=6
```

**What This Includes:**
- ✅ API, Worker, Postgres, Redis
- ✅ All free sidecars (social-analyzer, gmaps, email-verifier)
- ✅ Tier 1 worker (network_mode: host)
- ✅ Multilogin container (network_mode: host)
- ✅ Tier 234 worker (default 1, or scaled with --scale)
- ✅ Foundation Week 1 workers (document, embedding)
- ✅ Paid services (reacher, scrapoxy)
- ✅ LLM services (litellm, ollama)
- ✅ Observability (langfuse, glitchtip, changedetection)

**Note:** Multilogin container requires `network_mode: host` (Linux only). Both Multilogin and Tier 1 worker share host's 127.0.0.1 loopback.

**Stop Everything:**
```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier1.yml \
  -f docker-compose.tier-workers.yml \
  -f docker-compose.foundation.yml \
  --profile paid \
  --profile llm \
  --profile observability \
  down
```

**View All Running Services:**
```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.tier1.yml \
  -f docker-compose.tier-workers.yml \
  -f docker-compose.foundation.yml \
  ps
```

---

## Appendix: Glossary

**Dossier:** The unified enrichment result containing all data about a person/company

**Enricher:** A module that extracts data from one specific OSINT tool

**Pipeline:** The orchestrator that runs enrichers and merges results

**Tier:** A category of enrichers (1=LinkedIn, 2=username hunt, 3=deep OSINT, 4=job/business)

**Suppression:** Opt-out mechanism that blocks enrichment for specific identifiers

**Sidecar:** An isolated Docker service for AGPL tools (no direct code import)

**Provider:** A configurable backend (free vs paid) for browser, proxy, LLM, etc.

**LLM Disambiguation:** AI-powered verification of uncertain social handles

**Confidence Score:** 0.0-1.0 score indicating reliability of enrichment data

**DSAR:** Data Subject Access Request (GDPR/LGPD/CCPA compliance)

**ADR:** Architecture Decision Record (documents why we chose X over Y)

**Multilogin:** Stealth browser platform for LinkedIn scraping (Tier 1)

**Bridge Network:** Docker networking mode with service discovery (default)

**Host Network:** Docker networking mode sharing host's network (Tier 1 only)

---

## Document Maintenance

**Update Frequency:** Monthly or after major changes

**Reviewers:** Development team leads

**Approval:** Tech lead sign-off required

**Version History:**
- v1.0 (Aug 5, 2026) - Initial comprehensive KT document

**Feedback:** Submit corrections via PR or team chat

---

**End of Knowledge Transfer Document**

For questions or clarifications, contact the development team or refer to the [Additional Resources](#18-additional-resources) section above.
