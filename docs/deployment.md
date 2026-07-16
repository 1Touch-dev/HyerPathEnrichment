# Production deployment — enrich.hyrepath.io

Operator runbook for Hyrepath Enrichment (Task 86–89). Architecture reference: [`backend/docs/ARCHITECTURE.md`](../backend/docs/ARCHITECTURE.md).

## Topology (v1)

```
Internet → Cloudflare (TLS) → Tunnel or reverse proxy → api:8000
                              ├─ worker (RQ)
                              ├─ postgres
                              ├─ redis
                              └─ free sidecars (social-analyzer, google-maps-scraper, email-verifier)
```

**Tier 1 (LinkedIn photo):** Multilogin X runs on a **Windows host**. Use [`backend/docker/docker-compose.tier1.yml`](../backend/docker/docker-compose.tier1.yml) with `WORKER_ENV_FILE` and `MULTILOGIN_HOST_IP` pointing at the MLX machine.

## Compose files

```bash
cd backend/docker
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file ../.env.production up -d --build
```

## Required environment

| Variable | Purpose |
|----------|---------|
| `APP_ENV` | `production` |
| `API_TOKEN` | Bearer token |
| `DATABASE_URL` | Shared Postgres for api + worker |
| `REDIS_URL` | Queue + rate limits |
| `R2_*` | Photo cache when Tier 1 enabled |

## Deploy steps

1. Provision Linux VPS; install Docker.
2. Clone repo; copy production secrets (not in git).
3. `docker compose … up -d --build`
4. Cloudflare Tunnel → `http://127.0.0.1:8000`; DNS `enrich.hyrepath.io`
5. `BASE_URL=https://enrich.hyrepath.io API_TOKEN=<prod> bash backend/scripts/prod_acceptance.sh`

## Acceptance (Tasks 86–88)

- `GET /health` → 200
- Authenticated `/enrich/sync`
- `POST /api/opt-out` public (not 401)
- Async `/enrich` + poll `completed`

See [`backend/docs/evidence/prod-deploy-86.md`](../backend/docs/evidence/prod-deploy-86.md).
