    # RULE.md — Development Rules

Rules for humans and agents writing code in this repo. Read **before** implementing.

**Scope:** entire project (`frontend/` + `backend/`).  
**Pair with:** `backend/docs/ARCHITECTURE.md` (what exists), `AGENTS.md` (session behavior).

---

## Before writing any code

1. Search the repo for an existing function, type, component, or pattern
2. Read the **Agent quick reference** in `backend/docs/ARCHITECTURE.md` if touching backend code
3. Check **Implementation status** — do not build on features that are scaffold-only
4. Keep the change as small as the task allows — no drive-by refactors

---

## Reuse first — do not reinvent

### Backend

| Need | Use this | Do not |
|------|----------|--------|
| Settings / env | `get_settings()` in `core/config.py` | Hardcode tokens, URLs, thresholds |
| DB session | `get_db_session()` in `database/session.py` (shim: `storage/db.py`) | Create engines or sessions ad hoc |
| Start enrichment | `EnrichmentService` / module routers | Put merge, suppression Redis keys, or enricher dispatch in routes |
| Run enrichment | `Pipeline` in `enrichers/pipeline.py` | A second orchestrator in workers or services |
| Job persistence | `JobRepository` in `modules/enrichment/repository.py` | Ad-hoc SQLAlchemy updates in routes |
| Identifier hash | `hash_identifier()` in `compliance/identifiers.py` | Inline `hashlib.sha256` elsewhere |
| Suppression check | `compliance/suppression.py` | Duplicate opt-out Redis/SQL logic in Pipeline or routes |
| Dossier merge | `enrichers/merge.py` (Pipeline only) | Merge enricher output in routes, services, or enrichers |
| Asset upload | `R2StorageClient` in `storage/r2.py` | Write files outside the storage client |
| Domain contracts | `domain/` (`Dossier`, `EnrichmentRequest`, enums) | Recreate a global `models.py` dumping ground |
| Redis connection | `infrastructure/redis.py` | One god-object RedisCache for queue + photos + suppression |

### Enrichers

- **One provider per file** — `linkedin_photo.py` → `LinkedInPhotoEnricher`
- **Extend `Enricher` in `base.py`** — only override `validate`, `run`, and hooks you need
- **Return partial dicts** — keys like `photo`, `handles`, `emails`, `sources`; not a full `Dossier`
- **Check `enrichers/` before adding** — if a tool is already wrapped, extend it; do not add a second wrapper
- **Tier registration** — add enrichers only in `enrichers/registry.py`; only `Pipeline` consumes the registry

### Layer ownership

| Component | Owns |
|-----------|------|
| `domain/` | Shared business contracts (`Dossier`, `EnrichmentRequest`, enums) — no imports from modules/workers/clients/ORM |
| `modules/` | API-facing use cases (routers, services, feature ORM, HTTP schemas) |
| `enrichers/pipeline.py` | Enrichment execution (suppression decision, dispatch, merge, disambiguate) |
| `enrichers/merge.py` | Deterministic dossier assembly only |
| `enrichers/disambiguate.py` | LLM keep/drop policy (not the LLM HTTP client) |
| `workers/` | Background execution adapter + RQ; must not import module routers/services |
| `compliance/` | Identifier hashing, suppression impl, purge, audit, DSAR processing + compliance ORM |
| `clients/` | Thin external communication |
| `integrations/` | Complex platform implementations (LinkedIn, browser, Multilogin) |
| `infrastructure/` | Shared technical connections (Redis factory) |
| `storage/` | R2, photo cache API, filesystem |
| `database/` | SQLAlchemy `Base` / session |

### Allowed / forbidden imports

**Allowed:** `modules` → domain, enrichers, module repositories, `workers.queue`, compliance; `workers/tasks` → domain, `enrichers.pipeline`, `modules/*/repository`, compliance; `enrichers` → domain, clients, integrations, storage, compliance.

**Forbidden:** `workers/tasks` → `modules/*/service|router|dependencies`; `enrichers` → modules or workers; `domain` → modules, workers, clients, ORM; `clients` → `Dossier` / business orchestration; `merge` → LLM client.

### Frontend

| Need | Use this | Do not |
|------|----------|--------|
| Shared types | `frontend/src/lib/types.ts` (UI camelCase) + `frontend/src/lib/generated/` (OpenAPI wire types) | Duplicate `Dossier` / `EnrichmentInput` shapes inline |
| API mapping | `frontend/src/lib/api-adapter.ts` | Map snake_case ↔ camelCase in components |
| Utilities | `frontend/src/lib/utils.ts` | Copy small helpers into components |
| UI components | `frontend/components/` | Rebuild intake, pipeline, or dossier UI from scratch |

---

## No redundant code

- **Do not duplicate validation** — backend: `EnrichmentRequest` in `domain/`; frontend: form validation only for UX, not business rules
- **Do not duplicate merge logic** — all dossier assembly stays in `enrichers/merge.py`
- **Do not duplicate API field mapping** — all backend ↔ frontend naming goes through `api-adapter.ts`
- **Do not add thin wrappers** — if a one-liner helper is used once, inline it
- **Do not copy-paste enricher patterns** — extract shared behavior into `base.py` or a small shared module only when used by 2+ enrichers
- **Do not add unused abstractions** — no factories, base classes, or config layers "for later"

---

## Architecture rules

### Backend

- **Routes are thin** — auth, parse request, call module service, return response
- **One enrichment engine** — sync and async both converge on `Pipeline.run()`; workers are adapters only
- **Suppression before dispatch** — Pipeline decides effect; `compliance/suppression.py` owns Redis/SQL dual-write
- **ORM lives with its owner** — enrichment jobs in `modules/enrichment/models.py`; compliance tables in `compliance/models.py`; never recreate a global `app/models.py` dumping ground
- **AGPL tools in sidecars only** — `social-analyzer`, Reacher, etc. are called over HTTP; never import AGPL code into `app/`
- **No browser work in routes** — Playwright / Multilogin stays in Tier 1 enrichers / integrations
- **Async end-to-end** — DB, storage, enrichers, and route handlers are `async`; no `run_until_complete` in request paths
- **Tier registration in one place** — `enrichers/registry.py` only
- **Schema changes via Alembic only** — never reintroduce `_migrate_schema` or durable `create_all`; new columns/indexes = new revision under `backend/alembic/versions/`; Alembic stays at repo-level `backend/alembic/`

### Frontend

- **Components display; lib handles data** — fetching and mapping live in `src/lib/`, not scattered in JSX
- **Keep types in sync** — backend wire contract: run `cd frontend && npm run openapi:export && npm run openapi:gen` after changing Pydantic models in `backend/app/domain/` or module response models; commit `frontend/openapi/openapi.json` and `frontend/src/lib/generated/openapi.ts`. Update `types.ts` and `api-adapter.ts` when UI camelCase shapes change.
- **No direct backend shape in UI** — components consume frontend `Dossier`, not snake_case payloads

### Cross-cutting

- **Trust code over docs when they disagree** — then update the doc in the same PR if the code is correct
- **Scaffold vs target** — label new work clearly; do not pretend queue, Postgres, or real enrichers exist if they do not yet

---

## Change scope

- **Fix only what the task needs** — no unrelated formatting, renames, or "while I'm here" edits
- **One concern per change** — new enricher ≠ refactor orchestrator ≠ frontend redesign in one PR unless explicitly asked
- **Match existing style** — naming, imports, file layout, comment density in the file you are editing
- **Prefer extending over rewriting** — add to existing modules before creating parallel ones

---

## Testing rules

### Backend

- **New enricher → extend `tests/test_pipeline_shape.py`** — assert valid partial dossier dict keys and types
- **New route behavior → API test** — status code, auth, response shape
- **No live external calls in CI** — mock subprocess, HTTP sidecars, and third-party APIs
- **Run:** `cd backend && pytest tests`

### Frontend

- **Type changes → run** `npm run typecheck` from `frontend/`
- **UI changes → run** `npm run lint` and `npm run build` when touching routes or shared components

---

## Safety and compliance

- **Never log raw identifiers** (email, LinkedIn URL, username) — use job IDs or hashed values
- **Never commit secrets** — `.env` stays gitignored; update `.env.example` with placeholders only
- **Do not weaken opt-out** — no bypass of suppression checks for sync, debug, or "fast" paths
- **Public data only** — no private sources, face recognition, or bulk scraping (see `backend/docs/ARCHITECTURE.md` product boundaries)
- **Customer-supplied identifiers only** — do not add "discover people" flows

---

## Code quality

- **Python:** follow `ruff` / `pyproject.toml`; fix lint before finishing
- **TypeScript:** no `any` unless mapping unknown backend metadata; prefer existing types
- **Imports:** stdlib → third-party → local; no unused imports
- **Comments:** only for non-obvious business logic — not for self-explanatory code
- **Errors:** return structured API errors; do not swallow exceptions silently in enrichers (log + return empty partial payload or re-raise per existing pattern in the file)

---

## When to break a rule

Sometimes the right fix violates a rule. When that happens:

1. **Say why** in the PR or a short code comment (`# NOTE: ...`)
2. **Keep the exception local** — do not rewrite the whole module to match the exception
3. **Update docs** if the exception becomes the new pattern

---

## Quick checklist (before opening a PR)

- [ ] Searched for existing code to reuse
- [ ] No duplicate validation, merge, hash, or API mapping logic
- [ ] Backend types and frontend types stay aligned (if dossier/API changed)
- [ ] Tests or typecheck run for the area changed
- [ ] No secrets, raw PII in logs, or opt-out bypass
- [ ] `backend/docs/ARCHITECTURE.md` **Implementation status** updated if scaffold changed
