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

## Org-wide ceiling (closes the follow-up flagged above)

Per-caller keys (`_org_scoped_id`) prevent one recruiter from starving another, but they do
**not** cap an org's *total* traffic — ten recruiters at the same org, each individually under
their own per-caller limit, could still collectively hammer the API far past what a single-org
plan is meant to allow. This section specs the follow-up flagged in the "Ambiguities resolved"
entry below (now resolved, not deferred): a **second**, additional Redis key checked *in addition
to*, not instead of, the existing per-caller `_org_scoped_id` key.

Add a second helper, next to `_org_scoped_id`:

```python
def _org_ceiling_id(org_id: UUID | None) -> str:
    """Org-wide ceiling key — one bucket per org, shared across every recruiter at
    that org, checked alongside (not instead of) _org_scoped_id's per-caller bucket.
    org_id=None (direct candidates, no org) never hits this ceiling at all — there
    is no "org" to cap traffic for; only _org_scoped_id's per-caller limit applies
    to them, unchanged from the base retrofit above."""
    return f"org_ceiling:{org_id}"
```

Each retrofitted `enforce_*` function performs **two** checks when `org_id is not None`: the
existing per-caller check against `f"{scope}:{_org_scoped_id(authorization, org_id)}"`, and a new
check against `f"{scope}:{_org_ceiling_id(org_id)}"` — both must pass; either one tripping is a
429. This mirrors the existing multi-scope pattern already used elsewhere in this file for
compound limits (check `check_rate_limit()`'s call signature for whether it already supports
checking more than one key per call, or whether this requires two sequential
`check_rate_limit()` calls per `enforce_*` function — follow whichever shape that function's
current signature actually supports rather than assuming).

The org-wide ceiling's numeric limit is read from `OrganizationSubscription.plan_tier`
(`post-tenancy-features/01-billing-stripe-integration.md`'s model — `"free"|"starter"|"growth"|
"enterprise"`), mapped to a requests-per-minute ceiling via a small lookup (implementer's choice
of exact per-tier numbers, but document them in the PR description; a reasonable starting point
is free=60, starter=300, growth=1000, enterprise=5000 req/min, adjustable later without a code
change if moved into config). **This creates a soft dependency on the billing chunk**, which is
dispatched much later than `machine-1` per the root README's merge order (`post-tenancy-features`
only starts after the `post-tenancy-retrofit` hard gate). Resolve this the same way
`machine-1-tenancy-core/05-org-invite-flow.md` resolves its own soft dependency on billing: if
`OrganizationSubscription` doesn't exist yet (table not present, or no row for this org), default
every org to a flat fallback ceiling via a new config value, following the exact same settings-
field convention already used elsewhere in this file for `enable_org_cors_origins`:

```python
# Tenancy (docs/adr/0018-tenancy-model.md): org-wide rate-limit ceiling (req/min)
# used when OrganizationSubscription (post-tenancy-features/01-billing-stripe-
# integration.md) doesn't exist yet for an org, or billing is disabled. Applies
# per-org, shared across every recruiter at that org (see _org_ceiling_id).
default_org_rate_limit_per_minute: int = Field(
    default=300, alias="DEFAULT_ORG_RATE_LIMIT_PER_MINUTE"
)
```

## Ambiguities resolved

- **Should the org-level rate limit be a *separate*, additional ceiling (one per org, on top of
  each recruiter's existing per-user ceiling) rather than just changing the key format?** Yes —
  resolved above, not deferred. The key-format change alone (folding `org_id` into the existing
  key) already prevents one org's total traffic from being invisible to any per-tenant
  accounting (keys are grouped by org prefix in Redis, useful for future per-org dashboards), but
  it does not, by itself, cap total org traffic — that gap is what the "Org-wide ceiling" section
  above closes with a second, additive Redis key.

## Do not touch

- Do not change scope keys for `compliance` or `auth` (unauthenticated, per-IP scopes).
- Do not touch `backend/app/modules/opt_out/` or `backend/app/modules/dsar/` routers themselves —
  only `rate_limit.py`'s scope-key format changes, router wiring (which dependency each route
  uses) stays as-is.
- Do not add a reverse-proxy/gateway container to `backend/docker/docker-compose.yml` in this
  chunk (see the ADR's Decision §5 — explicitly out of scope).
- Do not import `backend/app/modules/billing/` directly if it does not exist yet at
  implementation time (see the soft-dependency note above) — guard the `OrganizationSubscription`
  lookup so its absence degrades to `default_org_rate_limit_per_minute`, it does not raise an
  `ImportError` or otherwise break rate-limiting for every org.

## Verification

- Existing rate-limit tests (locate under `backend/tests/` — likely a
  `test_rate_limit*.py` file; confirm exact path before assuming) must still pass.
- Add a test asserting two different `org_id` values produce independent rate-limit buckets for
  the same underlying bearer token/client id (i.e. exhausting Org A's budget does not affect
  Org B's).
- Add a test asserting `enable_org_cors_origins=False` (default) leaves CORS behavior byte-for-
  byte identical to before this chunk (regression safety for existing single-tenant deployments).
- Add a test asserting one org's **total** traffic across multiple recruiters cannot exceed the
  org ceiling even though each recruiter is individually under their own per-caller limit — e.g.
  three different recruiters at the same org, each making requests comfortably under their own
  per-caller ceiling, collectively trip the shared `_org_ceiling_id` bucket and the next request
  (from any of the three) gets a 429, while a fourth recruiter at a *different* org is unaffected.
- Add a test asserting the fallback path: with no `OrganizationSubscription` row for an org, the
  org ceiling enforced is exactly `default_org_rate_limit_per_minute`, not unlimited and not a
  hard failure.
