# Machine 1, Chunk 4 — CORS and Rate-Limit Retrofit

## Depends on

Chunk `02`'s `Organization.custom_origin` column and chunk `03`'s `org_id` JWT claim /
`request.state.org_id`.

## Files to edit

- `backend/app/main.py`
- `backend/app/dependencies/rate_limit.py`
- `backend/app/core/config.py`

## Ground truth: current state (verified 2026-08-22, corrects the original research note)

The original research for this effort described CORS as a single static origin with no
allow-list concept. **That has since changed** (already merged to `master-complete-foundation`
ahead of this ADR): `backend/app/main.py` (around lines 65-79) now reads:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["*"],
    max_age=600,
)
```

where `settings.cors_allowed_origins` (`backend/app/core/config.py`, property, ~line 322-328) is:

```python
CORS_ALLOWED_ORIGINS: str = Field(default="", alias="CORS_ALLOWED_ORIGINS")

@property
def cors_allowed_origins(self) -> list[str]:
    """Parsed CORS allowlist, falling back to FRONTEND_URL (or localhost) when unset."""
    origins = [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]
    if origins:
        return origins
    return [self.FRONTEND_URL] if self.FRONTEND_URL else ["http://localhost:3000"]
```

**Before implementing, re-read the current `backend/app/main.py` and `config.py` to confirm this
still matches** — this chunk assumes the above shape. What is *still* missing, and what this
chunk actually adds, is: (a) no per-tenant/per-org origin concept — `CORS_ALLOWED_ORIGINS` is one
global static list, not looked up per-org from the `organizations.custom_origin` column added in
chunk `02`; (b) no `org_id` dimension in any rate-limit scope key.

## CORS retrofit — dynamic per-org origin

`CORSMiddleware` is configured once at app startup with a static `allow_origins` list — it
cannot look up a database value per-request out of the box. Two supported approaches; use
approach (a) unless the reviewer/implementer has a strong reason to prefer (b):

**(a) Static allow-list stays the source of truth; org custom origins are added to it at startup
via a periodic/one-time sync, not a live per-request DB lookup.** Add a helper function in
`backend/app/main.py` (or a new small module `backend/app/core/cors.py` if `main.py` is getting
crowded — check current file length/conventions before deciding):

```python
async def _resolve_cors_origins(settings: Settings) -> list[str]:
    """Static CORS_ALLOWED_ORIGINS plus every active org's custom_origin, deduplicated.

    Called once at startup (see app/core/lifespan.py), not per-request — CORSMiddleware
    does not support per-request origin resolution, and a live DB query per preflight
    would add latency to every OPTIONS request. Orgs that add a custom_origin after
    this app process started need a restart (or a future admin-triggered reload) to
    take effect — this tradeoff is acceptable because custom-domain changes are rare,
    admin-initiated events, not something end users trigger.
    """
    origins = set(settings.cors_allowed_origins)
    async with get_db_session_context() as db:  # match the existing session-context helper used in app/core/lifespan.py
        result = await db.execute(
            select(Organization.custom_origin).where(
                Organization.custom_origin.is_not(None), Organization.is_active.is_(True)
            )
        )
        origins.update(row[0] for row in result.all() if row[0])
    return sorted(origins)
```

Wire this into `backend/app/core/lifespan.py`'s existing startup sequence (check that file for
how it already handles startup DB access, e.g. running migrations checks or warming caches — use
the same session-acquisition pattern, don't invent a new one) and pass the resolved list into
`app.add_middleware(CORSMiddleware, allow_origins=resolved_origins, ...)` in `main.py` instead of
`settings.cors_allowed_origins` directly.

**(b) Alternative (only if (a) proves infeasible given how `main.py`/`lifespan.py` structures
startup):** a custom ASGI middleware that replaces `CORSMiddleware` and does an
origin-in-allow-list check per-request against a cached (Redis, TTL ~60s) set of origins refreshed
lazily. This is more invasive (replaces a well-tested Starlette middleware with hand-rolled
logic) — only take this path if (a) is genuinely blocked, and document why in the PR.

Whichever approach is used, add a config flag following the exact existing bool-flag convention
(`backend/app/core/config.py`, see `enable_tier1`, `outreach_enabled`):

```python
# Tenancy (docs/adr/0018-tenancy-model.md): include active orgs' custom_origin values
# in the CORS allow-list at startup, in addition to CORS_ALLOWED_ORIGINS/FRONTEND_URL.
# Default False so existing single-tenant deployments are unaffected until opted in.
enable_org_cors_origins: bool = Field(default=False, alias="ENABLE_ORG_CORS_ORIGINS")
```

## Rate-limit retrofit — `org_id` dimension

Current scopes in `backend/app/dependencies/rate_limit.py` are keyed by `_client_id()` (sha256 of
the bearer token) or `_host_client_id()` (sha256 of the IP) — **no tenant dimension exists in any
scope key today.** This is still true as of 2026-08-22 (re-verify at implementation time).

Add a new helper, next to `_client_id`/`_host_client_id` (after line 23):

```python
def _org_scoped_id(authorization: str | None, org_id: UUID | None) -> str:
    """Per-org, per-caller id — an abusive recruiter at Org A doesn't consume Org B's
    budget, and an org with many recruiters gets one shared per-org ceiling in
    addition to each recruiter's own per-caller ceiling."""
    client = _client_id(authorization)
    return f"{org_id or 'noorg'}:{client}"
```

This changes existing scope key **format**, not scope **names** — e.g.
`enforce_sync_rate_limit`'s key goes from `f"sync:{_client_id(authorization)}"` to
`f"sync:{_org_scoped_id(authorization, org_id)}"`. Retrofit only the scopes that are
tenant-relevant: `sync`, `async`, `documents`, `job_matching`, `outreach_send`,
`job_matching_apply`, and the `admin_*` scopes (all currently keyed by `_client_id`). Do **not**
retrofit `compliance` or `auth` (currently keyed by `_host_client_id`, i.e. per-IP,
unauthenticated-caller scopes — these have no user/org context to key on, and retrofitting them
is out of scope for this chunk). Read `org_id` the same way `require_org_member` does — inject it
via a new small dependency:

```python
async def _current_org_id(
    authorization: str | None = Header(default=None),
    request: Request = None,
) -> UUID | None:
    return getattr(request.state, "org_id", None)
```

(Exact wiring depends on whether `request.state.org_id` — set in chunk `03` — is reliably
populated before rate-limit dependencies run in FastAPI's dependency-resolution order; if
ordering is a problem, decode the `org_id` claim directly inside the rate-limit dependency instead
of relying on `request.state`, following the same `jwt.decode(...)` call already used in
`get_current_user_from_cookie` — check whichever approach is more consistent with how
`_client_id` already re-parses the raw `Authorization` header rather than relying on another
dependency's side effect.)

Update every retrofitted `enforce_*` function's signature to accept `org_id` via this dependency
and pass it into `_org_scoped_id`.

## Ambiguities resolved

- **Should the org-level rate limit be a *separate*, additional ceiling (one per org, on top of
  each recruiter's existing per-user ceiling) rather than just changing the key format?** Out of
  scope for this chunk as specified — the key-format change alone (folding `org_id` into the
  existing key) already prevents one org's total traffic from being invisible to any per-tenant
  accounting, since keys are now grouped by org prefix in Redis (useful for future per-org
  dashboards), but it does **not** add a new distinct ceiling. If a genuine "org quota" ceiling
  (e.g. "this agency's plan allows 500 req/min total") is wanted, that is a follow-up task, not
  part of this chunk — flag it in the PR description rather than silently adding it.

## Do not touch

- Do not change scope keys for `compliance` or `auth` (unauthenticated, per-IP scopes).
- Do not touch `backend/app/modules/opt_out/` or `backend/app/modules/dsar/` routers themselves —
  only `rate_limit.py`'s scope-key format changes, router wiring (which dependency each route
  uses) stays as-is.
- Do not add a reverse-proxy/gateway container to `backend/docker/docker-compose.yml` in this
  chunk (see the ADR's Decision §5 — explicitly out of scope).

## Verification

- Existing rate-limit tests (locate under `backend/tests/` — likely a
  `test_rate_limit*.py` file; confirm exact path before assuming) must still pass.
- Add a test asserting two different `org_id` values produce independent rate-limit buckets for
  the same underlying bearer token/client id (i.e. exhausting Org A's budget does not affect
  Org B's).
- Add a test asserting `enable_org_cors_origins=False` (default) leaves CORS behavior byte-for-
  byte identical to before this chunk (regression safety for existing single-tenant deployments).
