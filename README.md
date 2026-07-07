# HyerEnrichment

HyerEnrichment is now structured as a **split frontend + backend repository** for **AZI-11 — Bacckend**.

This repo contains:

- a **Next.js frontend** at the repository root for the enrichment experience UI
- a **Python/FastAPI backend** under `backend/` for enrichment APIs, orchestration, and backend deployment scaffolding

The goal of this ticket was to preserve the existing frontend while placing the backend implementation in a dedicated `backend/` folder, matching the requested project layout.

## What was built for AZI-11

### Frontend

The existing frontend remains at the repo root and provides:

- identifier intake for email, LinkedIn URL, username, company, business query, and job search
- tier selection for `tier1` through `tier4`
- pipeline visualization
- merged dossier presentation

### Backend

The backend now lives under `backend/` and includes:

- FastAPI application entrypoint in `backend/app/main.py`
- authenticated enrichment routes:
  - `POST /enrich`
  - `GET /enrich/{id}`
  - `POST /enrich/sync`
  - `POST /api/opt-out`
  - `GET /api/opt-out/check`
  - `GET /health`
- a pipeline orchestrator in `backend/app/workers/runner.py`
- modular enrichers in `backend/app/enrichers/`
- storage abstractions in `backend/app/storage/`
- Docker assets in `backend/docker/`
- backend tests in `backend/tests/`
- backend environment template in `backend/.env.example`

## Repository structure

```text
app/                    # Next.js frontend app router
components/             # frontend UI components
src/                    # frontend utilities/types/mock data
backend/
  app/                  # FastAPI backend package
  docker/               # backend Dockerfiles and compose
  docs/                 # backend architecture docs
  scripts/              # backend helper scripts
  tests/                # backend tests
  .env.example
  pyproject.toml
  README.md
docs/                   # ticket/handoff documentation
README.md
CHANGELOG.md
```

## Frontend setup

Install frontend dependencies from the repo root:

```bash
npm install
```

Run the frontend locally:

```bash
npm run dev
```

Frontend default URL:

```text
http://localhost:3000
```

## Backend setup

Install backend dependencies from the backend folder:

```bash
cd backend
pip install -e .
```

Or, if using the project’s preferred Python workflow, install with your chosen isolated environment tooling before running the app.

Run the backend locally:

```bash
cd backend
uvicorn app.main:app --reload
```

Backend default URL:

```text
http://localhost:8000
```

## Backend environment

Use `backend/.env.example` as the starting point. The backend currently expects configuration such as:

- `API_TOKEN`
- `DATABASE_URL`
- `REDIS_URL`
- `R2_BUCKET`
- `R2_PUBLIC_BASE_URL`

## Verification

Frontend scripts from repo root:

```bash
npm run build
npm run lint
npm run typecheck
```

Backend checks from `backend/`:

```bash
pytest tests
```

## Release readiness notes

This branch is documentation-ready for automated PR completion and reflects the implemented AZI-11 repo layout:

- frontend remains isolated at the repo root
- backend is placed under `backend/` as requested
- backend routes, orchestrator, enrichers, Docker assets, and tests are present
- top-level docs now describe the split architecture accurately

## Related docs

- `backend/README.md` — backend-only run and test notes
- `backend/docs/ARCHITECTURE.md` — backend architecture summary
- `docs/IMPLEMENTATION_NOTES.md` — AZI-11 handoff notes
- `CHANGELOG.md` — ticket-level release notes
