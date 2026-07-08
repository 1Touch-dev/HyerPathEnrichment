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
| Settings / env | `get_settings()` in `config.py` | Hardcode tokens, URLs, thresholds |
| DB session | `get_db_session()` in `storage/db.py` | Create engines or sessions ad hoc |
| Orchestrator | `get_orchestrator(db)` in `services.py` | Instantiate `PipelineOrchestrator` in routes |
| Identifier hash | `PipelineOrchestrator._hash()` | Inline `hashlib.sha256` elsewhere |
| Suppression check | `_is_suppressed()` / `check_suppression()` | Duplicate opt-out logic in routes |
| Dossier merge | `_merge()` in `workers/runner.py` | Merge enricher output in routes or enrichers |
| Asset upload | `R2StorageClient` in `storage/r2.py` | Write files outside the storage client |
| Request validation | `EnrichmentRequest` in `models.py` | Re-validate identifiers in routes or enrichers |
| Response models | Pydantic models in `models.py` | Ad-hoc dicts in route handlers |

### Enrichers

- **One provider per file** — `linkedin_photo.py` → `LinkedInPhotoEnricher`
- **Extend `Enricher` in `base.py`** — only override `validate`, `run`, and hooks you need
- **Return partial dicts** — keys like `photo`, `handles`, `emails`, `sources`; not a full `Dossier`
- **Check `enrichers/` before adding** — if a tool is already wrapped, extend it; do not add a second wrapper

### Frontend

| Need | Use this | Do not |
|------|----------|--------|
| Shared types | `frontend/src/lib/types.ts` | Duplicate `Dossier` / `EnrichmentInput` shapes inline |
| API mapping | `frontend/src/lib/api-adapter.ts` | Map snake_case ↔ camelCase in components |
| Utilities | `frontend/src/lib/utils.ts` | Copy small helpers into components |
| UI components | `frontend/components/` | Rebuild intake, pipeline, or dossier UI from scratch |

---

## No redundant code

- **Do not duplicate validation** — backend: `EnrichmentRequest`; frontend: form validation only for UX, not business rules
- **Do not duplicate merge logic** — all dossier assembly stays in `runner.py` `_merge()`
- **Do not duplicate API field mapping** — all backend ↔ frontend naming goes through `api-adapter.ts`
- **Do not add thin wrappers** — if a one-liner helper is used once, inline it
- **Do not copy-paste enricher patterns** — extract shared behavior into `base.py` or a small shared module only when used by 2+ enrichers
- **Do not add unused abstractions** — no factories, base classes, or config layers "for later"

---

## Architecture rules

### Backend

- **Routes are thin** — auth, parse request, call orchestrator, return response
- **Suppression before dispatch** — any path that runs enrichers must check opt-out first
- **AGPL tools in sidecars only** — `social-analyzer`, Reacher, etc. are called over HTTP; never import AGPL code into `app/`
- **No browser work in routes** — Playwright / Multilogin stays in Tier 1 enrichers
- **Async end-to-end** — DB, storage, enrichers, and route handlers are `async`; no `run_until_complete` in request paths
- **Tier registration in one place** — add enrichers to `PipelineOrchestrator.__init__` in `runner.py`

### Frontend

- **Components display; lib handles data** — fetching and mapping live in `src/lib/`, not scattered in JSX
- **Keep types in sync** — if `Dossier` changes in `backend/app/models.py`, update `types.ts` and `api-adapter.ts` in the same change
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
- **Do not weaken opt-out** — no bypass of `_is_suppressed()` for sync, debug, or "fast" paths
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
