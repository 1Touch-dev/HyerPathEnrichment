# AZI-11: Bacckend

Project name: HyerEnrichment
currently the entire codebase in the attach repository is of frontend your task is separating frontend and backend into seprate folders, currently as said ealier the project only contain frontend code you need to add entire suitable backend code in backend folder&#x20;

Master Build Prompt — Hyrepath Enrichment

You are a senior Staff-level Python backend engineer, DevOps engineer, OSINT engineer, and software architect.

Your task is to build an entire production-ready project called **Hyrepath Enrichment**.

This is **not** a prototype.
This is **not** an MVP.
Build production-quality code from the beginning.

***

# Mission

Build a self-hosted enrichment platform that accepts one customer-supplied identifier and returns a unified enrichment dossier.

Supported identifiers:

* email
* LinkedIn URL
* username
* company
* job search query
* local business query

The service must orchestrate multiple enrichment engines, merge their outputs, score confidence, deduplicate identities, cache assets, store dossiers, expose REST APIs, and support asynchronous jobs.

The architecture must closely follow the supplied specification while improving engineering quality where appropriate.

***

# Core Principles

Always prioritize:

* clean architecture
* modularity
* testability
* observability
* async performance
* extensibility
* production readiness

Never write monolithic files.

Never put business logic inside API routes.

Every enrichment source must be implemented as an independent plugin/module.

Every component should be replaceable.

***

# Tech Stack

Backend

* Python 3.12+
* FastAPI
* Pydantic v2
* SQLAlchemy 2 async
* Alembic
* httpx
* asyncio
* aioboto3
* Redis
* RQ
* PostgreSQL
* uv package manager

Quality

* Ruff
* mypy
* pytest
* pytest-asyncio
* pre-commit

Infrastructure

* Docker
* Docker Compose

Documentation

* OpenAPI
* Markdown docs

***

# High-Level Architecture

Build the following layers.

```
API

↓

Authentication

↓

Request Validation

↓

Job Queue

↓

Worker

↓

Pipeline Orchestrator

↓

Tier Modules

↓

Merge Engine

↓

Confidence Engine

↓

LLM Disambiguation

↓

Storage

↓

API Response

```

Business logic must never exist inside routes.

Routes call services.

Services call orchestrator.

Orchestrator calls enrichers.

***

# Project Structure

Create a clean architecture.

```
app/

config/

api/

routes/

services/

workers/

storage/

repositories/

models/

schemas/

enrichers/

tier1/

tier2/

tier3/

tier4/

llm/

security/

middleware/

utils/

clients/

tests/

docker/

docs/

scripts/

```

Keep modules small.

One responsibility per file.

***

# Data Model

Design normalized tables plus JSONB storage.

Required tables:

users (future)

api\_keys

jobs

dossiers

audit\_logs

suppression\_list

cached\_assets

llm\_traces

pipeline\_runs

pipeline\_errors

job\_results

Every dossier should also exist as JSONB.

***

# Authentication

Implement:

Bearer token authentication.

Middleware should validate API\_TOKEN.

Unauthorized requests return 401.

***

# API

Implement:

POST /enrich

GET /enrich/{id}

POST /enrich/sync

POST /api/opt-out

GET /api/opt-out/check

GET /health

GET /ready

GET /metrics

Generate OpenAPI automatically.

***

# Enrichment Pipeline

The orchestrator receives:

```
email

linkedin_url

username

company

business

job_search

requested tiers

```

Pipeline order:

1.

Validate request

↓

1.

Normalize identifiers

↓

1.

Suppression check

↓

1.

Create Job

↓

1.

Dispatch requested tiers

↓

1.

Merge outputs

↓

1.

Confidence scoring

↓

1.

LLM disambiguation

↓

1.

Persist dossier

↓

1.

Return job id

***

# Tier 1

Implement LinkedIn Photo enrichment.

Technology

* Playwright
* Multilogin X
* linkedin\_scraper

Workflow

Receive LinkedIn URL

↓

Launch browser over CDP

↓

Open profile

↓

Extract profile image only

↓

Upload image to Cloudflare R2

↓

Store CDN URL

↓

Return metadata

Never scrape unnecessary profile content.

***

# Tier 2

Username Discovery

Run in parallel:

Sherlock

Maigret

Social Analyzer

Each module returns:

```
platform

username

profile_url

confidence

metadata

```

Merge all results.

Deduplicate.

Compute confidence.

Return ordered list.

***

# Tier 3

Deep OSINT

Implement modules:

GitRecon

theHarvester

Email Sleuth

Reacher

AfterShip Email Verifier

Mailchecker

CrossLinked

Capabilities:

GitHub commit emails

public names

organizations

corporate email guessing

SMTP verification

disposable email detection

coworker discovery

Everything should be modular.

***

# Tier 4

Job Intelligence

Implement JobSpy integration.

Accept:

query

location

remote

experience

Return jobs from multiple providers.

Business Intelligence

Implement Google Maps Scraper.

Return

address

website

rating

phone

business metadata

***

# Merge Engine

Create dedicated merge service.

Responsibilities:

merge identities

deduplicate

merge emails

merge usernames

merge organizations

merge jobs

merge businesses

produce final dossier

No duplicate entries.

***

# Confidence Engine

Every result receives confidence.

Sources include:

tool confidence

cross-source agreement

identifier similarity

domain match

username similarity

email match

GitHub match

LLM confirmation

Weighted scoring.

Expose configuration.

***

# LLM Disambiguation

Use LiteLLM.

Only process entries below threshold.

Prompt:

Determine if two identities belong to the same individual.

Return:

yes/no

confidence

reason

Reject responses below threshold.

Log everything to Langfuse.

***

# Storage

Implement repositories.

Postgres

Redis

Cloudflare R2

Never access databases directly from routes.

***

# Queue

Redis + RQ.

Workers process one dossier.

Retry policy.

Timeouts.

Dead letter queue.

Failure logging.

***

# Sidecars

Support HTTP communication with:

Social Analyzer

Reacher

Google Maps Scraper

Changedetection

Future sidecars should require zero orchestrator changes.

Use client abstraction.

***

# Configuration

Everything environment driven.

Create Config class.

Support validation.

No hardcoded secrets.

Generate:

.env.example

***

# Logging

Structured JSON logs.

Request IDs.

Job IDs.

Pipeline IDs.

Tier timing.

Failure reasons.

***

# Monitoring

Expose:

Prometheus metrics

health endpoint

readiness endpoint

pipeline latency

queue depth

tier latency

worker statistics

***

# Caching

Redis caching.

Cache:

LinkedIn photos

username lookups

GitHub results

business lookups

job lookups

Respect configurable TTLs.

***

# Error Handling

Create domain exceptions.

Examples:

TierUnavailable

RateLimited

ProviderTimeout

ProviderFailure

SuppressedIdentifier

AuthenticationFailure

ValidationFailure

Convert exceptions into consistent API responses.

***

# Rate Limiting

Implement:

per API key

per IP

per endpoint

Redis-backed.

***

# Security

Input validation

Secret management

Request size limits

CORS

Security headers

Audit logging

No secret leakage.

***

# Compliance

Implement suppression list.

Hash identifiers.

Pipeline must check suppression before any enrichment.

Return empty dossier for suppressed identifiers.

Support GDPR/LGPD/CCPA workflows.

***

# Testing

Implement:

unit tests

integration tests

API tests

worker tests

repository tests

mock sidecars

pipeline tests

confidence engine tests

merge engine tests

Minimum target:

90% coverage.

***

# CI/CD

Provide GitHub Actions.

Run:

ruff

mypy

pytest

docker build

lint

coverage

***

# Docker

Create production Dockerfiles.

Compose should include:

API

Worker

Redis

Postgres

Social Analyzer

Reacher

Google Maps Scraper

Langfuse

LiteLLM

Changedetection

Support local development.

***

# Documentation

Generate:

README

Architecture

API Reference

Deployment Guide

Environment Variables

Development Guide

Contribution Guide

Troubleshooting

***

# Coding Standards

Use:

type hints everywhere

async everywhere possible

dependency injection

repository pattern

service layer

SOLID principles

DRY

KISS

No duplicated code.

No giant functions.

No giant classes.

***

# Output Schema

Final dossier should resemble:

```
{
    "photo": {...},
    "handles": [],
    "emails": [],
    "verified_emails": [],
    "github": {},
    "coworkers": [],
    "jobs": [],
    "business": {},
    "confidence": {},
    "sources": [],
    "metadata": {}
}

```

Design schema for future expansion.

***

# Extensibility

Every enrichment provider should implement a common interface:

```
Enricher

initialize()

validate()

run()

normalize()

score()

cleanup()

```

Adding a new provider should require:

* one new module
* one registration entry

Nothing else.

***

# Code Quality Expectations

Generate production-grade code.

Avoid placeholders whenever practical.

Include meaningful comments only where they explain intent.

Use descriptive naming.

Keep functions focused.

Prefer composition over inheritance.

Avoid tight coupling.

***

# Final Deliverable

Produce a fully working repository that includes:

* production-ready FastAPI application
* asynchronous enrichment pipeline
* Redis job queue
* PostgreSQL persistence
* Cloudflare R2 integration
* LiteLLM integration
* Langfuse integration
* Dockerized deployment
* CI/CD workflows
* comprehensive tests
* complete documentation
* modular architecture
* clean code
* future-proof extension points

The resulting repository should be maintainable by a professional engineering team, capable of scaling to additional enrichment providers, and suitable for both self-hosted and SaaS deployments without major architectural changes.

Below is the backend folder structure&#x20;

hyrepath-enrichment/
├── app/
│   ├── main.py                    # FastAPI entrypoint
│   ├── config.py                  # Env-driven settings
│   ├── models.py                  # Pydantic + SQLAlchemy schemas
│   ├── multilogin.py              # Multilogin API client
│   ├── llm\_router.py              # LiteLLM disambiguation
│   ├── enrichers/
│   │   ├── base.py                # Enricher protocol
│   │   ├── linkedin\_photo.py      # Tier 1
│   │   ├── sherlock.py            # Tier 2
│   │   ├── maigret.py             # Tier 2
│   │   ├── social\_analyzer.py     # Tier 2 (HTTP to sidecar)
│   │   ├── gitrecon.py            # Tier 3
│   │   ├── theharvester.py        # Tier 3
│   │   ├── email\_discover.py      # Tier 3 (email-sleuth)
│   │   ├── email\_verify.py        # Tier 3 (Reacher + AfterShip)
│   │   ├── crosslinked.py         # Tier 3 (coworkers)
│   │   ├── jobspy.py              # Tier 4
│   │   └── local\_business.py      # Tier 4
│   ├── routes/
│   │   ├── enrich.py              # POST /enrich, GET /enrich/{id}, /enrich/sync
│   │   ├── health.py              # GET /health
│   │   └── opt\_out.py             # POST /api/opt-out (LGPD/GDPR/CCPA)
│   ├── storage/
│   │   ├── r2.py                  # Cloudflare R2 client
│   │   └── db.py                  # SQLAlchemy async session
│   └── workers/
│       └── runner.py              # Pipeline orchestrator
├── docker/
│   ├── Dockerfile.api
│   ├── Dockerfile.worker
│   └── docker-compose.yml         # 9 services (api, worker, pg, redis, 5 sidecars)
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DEVPLAN.md
│   └── LEGAL.md
├── scripts/
│   ├── create\_session.py
│   └── smoke\_test.py
├── tests/
│   └── test\_pipeline\_shape.py
├── .env.example
├── Makefile
├── pyproject.toml
├── README.md
└── DEVELOPER\_GUIDE.md             # ← this file

the above pasted path diagram consist backend code in app folder but i want them in the backend folder so remember it and make changes based on this preference &#x20;
At the end we need entire frontend and backend codes properly generated for the project required

this is the repo you need to work on: [https://github.com/AzizBohraKyma/HyerEnrichment.git](https://github.com/AzizBohraKyma/HyerEnrichment.git)
