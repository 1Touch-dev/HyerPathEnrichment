# Evidence: Langfuse staging (Task 49)

**Branch:** `feat/langfuse-staging-49`  
**Date (UTC):** 2026-07-16

## Status: **BLOCKED** (Docker unavailable)

## Deliverables in repo

- `backend/scripts/e2e_langfuse.sh` — starts observability + llm profiles, runs `trace()` smoke
- `backend/docker/docker-compose.staging.yml` — `LANGFUSE_*` env passthrough

## Operator steps (when Docker available)

```powershell
# Set in backend/.env: LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LLM_MODE=litellm
bash backend/scripts/e2e_langfuse.sh
# Open http://localhost:3000 — confirm trace from e2e-langfuse-smoke
```

## Pass criteria

- Langfuse UI reachable on `:3000`
- `backend/.e2e-results/langfuse-report.json` → `exit_code: 0`
