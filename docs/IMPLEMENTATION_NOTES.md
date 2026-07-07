# Implementation Notes — AZI-11

## Summary

This Scribe pass finalizes the **documentation and release handoff** for the AZI-11 repository split.

The codebase now presents the project as two clearly separated parts:

- **frontend at the repo root**
- **backend in `backend/`**

This matches the requested preference that backend code live in a dedicated backend folder rather than at the top level.

## What is implemented

### Frontend

The frontend remains in the existing root-level Next.js structure:

- `app/`
- `components/`
- `src/`

It continues to provide the enrichment intake flow, pipeline UI, and dossier presentation.

### Backend

The backend implementation exists under `backend/` and includes:

- `backend/app/main.py`
  - FastAPI entrypoint
  - bearer-token auth guard
  - route registration
- `backend/app/routes/`
  - enrichment routes
  - health route
  - opt-out routes
- `backend/app/workers/runner.py`
  - pipeline orchestrator
  - enrichment dispatch
  - merge/confidence flow
- `backend/app/enrichers/`
  - provider modules for LinkedIn photo, username discovery, OSINT, jobs, and business lookup
- `backend/app/storage/`
  - DB and asset storage abstractions
- `backend/docker/`
  - API/worker Dockerfiles and compose file
- `backend/tests/`
  - API/pipeline shape validation

## Documentation updates made in this pass

- rewrote the root `README.md` to describe the repo as a split frontend/backend project
- added AZI-11 release notes to `CHANGELOG.md`
- updated this implementation note to focus on backend-folder delivery and deployment handoff

## Release-readiness assessment

Documentation is now aligned with the implemented repository state.

Ready for automated PR completion:

- implementation commit exists: `feat(azi-11): implement Bacckend`
- frontend/backend separation is reflected in top-level docs
- backend run/setup instructions are documented
- backend-specific docs remain available under `backend/README.md` and `backend/docs/`

## Explicit handoff for deployment/PR completion

Use this repo as:

- a root-level frontend app for UI review and build steps
- a separate backend service rooted in `backend/`

Recommended operator entrypoints:

### Frontend

```bash
npm install
npm run dev
```

### Backend

```bash
cd backend
pip install -e .
uvicorn app.main:app --reload
pytest tests
```

## Scribe notes

- No application source files were changed.
- No frontend code, backend Python code, package manifests, or runtime logic were modified in this pass.
- Only markdown/documentation artifacts were updated.
