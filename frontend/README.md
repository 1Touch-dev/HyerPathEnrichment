# Hyrepath Enrichment — Frontend

Next.js 14 console and marketing UI with a thin BFF layer (Option D).

## Architecture

- **Browser** → same-origin `/api/*` (BFF)
- **BFF** → FastAPI with `BACKEND_API_TOKEN` (server-only)
- **Integrations** (curl, ATS) → FastAPI direct with Bearer token

## Routes

| Route                           | Purpose             |
| ------------------------------- | ------------------- |
| `/`                             | Marketing hub       |
| `/recruiters`, `/candidates`, … | Audience landings   |
| `/app`                          | Enrichment console  |
| `/app/history`                  | Job list            |
| `/app/jobs/[id]`                | Job detail + poll   |
| `/opt-out`                      | Public opt-out form |

## Local dev

```bash
cp .env.example .env.local
npm install
npm run dev
```

| Service | URL                   |
| ------- | --------------------- |
| Next.js | http://localhost:3000 |
| FastAPI | http://localhost:8000 |

`BACKEND_API_TOKEN` must match `API_TOKEN` in `backend/.env`.

## Scripts

- `npm run dev` — development server
- `npm run build` — production build
- `npm run typecheck` — TypeScript check
- `npm run lint` — ESLint

See [SMOKE.md](./SMOKE.md) for manual acceptance checks.
