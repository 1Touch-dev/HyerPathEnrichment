# Hyrepath Enrichment Backend

FastAPI backend for asynchronous and synchronous enrichment dossier generation.

## Run locally

Local dev uses SQLite by default (see `.env.example`) — no Postgres needed.

```bash
uvicorn app.main:app --reload --app-dir backend
```

## Run with Docker Compose (Postgres + Redis)

API and worker share one Postgres instance so async `POST /enrich` jobs can be
polled across processes. Job data survives restarts via the `postgres_data` volume.

```bash
cd backend/docker
docker compose up --build api worker redis postgres
```

Then:

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/enrich \
  -H "Authorization: Bearer change-me" \
  -H "Content-Type: application/json" \
  -d '{"username": "jane-doe"}'
# poll with the returned job id until status is "completed"
curl http://localhost:8000/enrich/<job_id> -H "Authorization: Bearer change-me"
```

## Test

```bash
pytest backend/tests
```
