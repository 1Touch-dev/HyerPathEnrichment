# Frontend smoke checklist

Run with backend at `http://localhost:8000` and `BACKEND_API_TOKEN` matching `backend/.env`.

## Setup

```bash
cd frontend
cp .env.example .env.local
# set BACKEND_API_URL and BACKEND_API_TOKEN
npm run dev
```

## Checks

1. **Health** — Console header shows green "API online" when backend is up.
2. **Async enrich** — `/osint` → Full (async) → tier checkboxes (default tier2+tier3) → submit → job polls until completed.
3. **Sync enrich** — Quick (sync) → tier1 checkbox disabled → submit without tier1 → dossier returns once.
4. **Use-case tiers** — `/recruiters` (etc.) CTA → `/osint?tiers=…` pre-checks audience tiers; toggles still work.
5. **Job detail** — `/osint/jobs/{id}` loads on refresh; polls if still running.
6. **Queue and history** — `/osint/jobs` lists jobs (requires backend `GET /enrich`).
7. **Opt-out** — `/opt-out` → submit → success message.
8. **Marketing** — `/`, `/recruiters`, … `/journalists` render; CTAs link to `/osint?tiers=...`.
9. **Build** — `npm run build` and `npm run typecheck` pass.

## Integration E2E (live backend)

Requires backend at `http://localhost:8000` with `BACKEND_API_TOKEN=change-me` (or matching `backend/.env`).

```bash
# From repo root — starts api, worker, redis, postgres and runs tests
make integration-e2e
# or
bash scripts/fullstack_e2e.sh
# Windows
.\scripts\fullstack_e2e.ps1
```

With backend already running:

```bash
cd frontend
npm run test:integration
```

Integration specs live in `e2e/integration/` and use `FRONTEND_USE_MOCKS=false`. Queue/history assertions require backend `GET /enrich` (see `feat/enrich-job-list` PR).

## Architecture

- Browser calls `/api/*` only (BFF).
- `BACKEND_API_TOKEN` is server-only — never `NEXT_PUBLIC_*`.
- Field mapping lives in `src/lib/api-adapter.ts` only.
