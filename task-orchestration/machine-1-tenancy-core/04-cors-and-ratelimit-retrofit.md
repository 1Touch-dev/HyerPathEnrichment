# Machine 1, Chunk 4 — CORS Retrofit (Per-Brand Domain)

## Depends on

Chunk `02`'s `Brand.custom_domain` column. No dependency on any JWT claim — chunk `03` is
superseded (see that file's stub), so there is no `org_id`/`brand_id` claim or
`request.state.org_id` to depend on here.

## Files to edit

- `backend/app/main.py`
- `backend/app/core/config.py`

`backend/app/dependencies/rate_limit.py` is **not edited by this chunk** — see "Rate limiting:
no changes" below for why the original org-wide-ceiling scope of this file no longer applies.

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
chunk actually adds, is: no per-brand custom-domain concept — `CORS_ALLOWED_ORIGINS` is one
global static list, not looked up per-brand from the `brands.custom_domain` column added in
chunk `02`. This retrofit remains genuinely useful — multiple real brand domains exist for this
product — even though the original "org-wide rate-limit ceiling" half of this chunk's original
scope has been removed (see below).

## CORS retrofit — dynamic per-brand domain

`CORSMiddleware` is configured once at app startup with a static `allow_origins` list — it
cannot look up a database value per-request out of the box. Two supported approaches; use
approach (a) unless the reviewer/implementer has a strong reason to prefer (b):

**(a) Static allow-list stays the source of truth; brand custom domains are added to it at
startup via a periodic/one-time sync, not a live per-request DB lookup.** Add a helper function
in `backend/app/main.py` (or a new small module `backend/app/core/cors.py` if `main.py` is
getting crowded — check current file length/conventions before deciding):

```python
async def _resolve_cors_origins(settings: Settings) -> list[str]:
    """Static CORS_ALLOWED_ORIGINS plus every active brand's custom_domain,
    deduplicated. Called once at startup (see app/core/lifespan.py), not
    per-request — CORSMiddleware does not support per-request origin resolution,
    and a live DB query per preflight would add latency to every OPTIONS request.
    Brands that add a custom_domain after this app process started need a restart
    (or a future admin-triggered reload) to take effect — this tradeoff is
    acceptable because custom-domain changes are rare, admin-initiated events, not
    something end users trigger. This is a pure presentation/routing concern — it
    has no bearing on data access (docs/adr/0018-tenancy-model.md)."""
    origins = set(settings.cors_allowed_origins)
    async with get_db_session_context() as db:  # match the existing session-context helper used in app/core/lifespan.py
        result = await db.execute(
            select(Brand.custom_domain).where(
                Brand.custom_domain.is_not(None), Brand.is_active.is_(True)
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
# Brand (docs/adr/0018-tenancy-model.md): include active brands' custom_domain
# values in the CORS allow-list at startup, in addition to
# CORS_ALLOWED_ORIGINS/FRONTEND_URL. Default False so existing deployments are
# unaffected until opted in. Purely a routing/presentation concern — Brand never
# gates data access, so this flag has no security implication beyond "which
# origins may make credentialed requests," identical in kind to the existing
# CORS_ALLOWED_ORIGINS behavior it extends.
enable_brand_cors_origins: bool = Field(default=False, alias="ENABLE_BRAND_CORS_ORIGINS")
```

## Rate limiting: no changes (scope removed)

The original version of this chunk also retrofitted `backend/app/dependencies/rate_limit.py` with
an `org_id` dimension on every scope key, plus a second, org-wide ceiling bucket keyed off
`OrganizationSubscription.plan_tier` seats. **Both are removed from this chunk's scope, not
reworked into a brand-flavored equivalent:**

- The per-caller `org_id` dimension depended on chunk `03`'s JWT `org_id` claim, which no longer
  exists (see `03-auth-org-id-claim.md`'s stub) — there is no tenant identity on a request for a
  rate-limit key to dimension by, and none is needed, since rate limiting's purpose (protect the
  API from any single abusive caller/IP) is unrelated to which brand storefront a candidate
  signed up through.
- The org-wide ceiling existed to cap a whole *agency's* aggregate traffic, proportional to its
  paid seat count — a concept that only made sense under the isolated-tenant/seat-billing model
  this doc set has moved away from. Billing is now candidate-level
  (`post-tenancy-features/01-billing-stripe-integration.md`'s `UserSubscription`), not
  seat-based, so there is no seat count to derive a ceiling from, and no "agency" whose aggregate
  traffic needs a shared ceiling in the first place — every recruiter is staff on the same one
  shared pool, not a tenant's employee.

Rate limiting therefore stays exactly as it is today: scopes keyed by `_client_id()` (sha256 of
the bearer token) or `_host_client_id()` (sha256 of the IP), with no brand/org dimension of any
kind. If a future need emerges for a *staff-wide* traffic ceiling (e.g. capping total recruiter
API usage regardless of brand), that is a new, separate chunk to write when that need is
concrete — not something this chunk should speculatively half-build.

## Ambiguities resolved

- **Should CORS retrofit and rate-limit retrofit still be one chunk, given rate-limit's scope
  shrank to nothing?** Kept as one file (this file) rather than splitting, since the file is
  still small and the "why rate-limit has no changes" explanation is short — splitting it into
  its own near-empty file would add doc-set overhead for no real benefit. The filename
  (`04-cors-and-ratelimit-retrofit.md`) is unchanged for the same reason other files in this doc
  set keep their original numbering/names even after their scope shifts (see `00-overview.md`'s
  and `03-auth-org-id-claim.md`'s notes on this convention).

## Do not touch

- Do not touch `backend/app/dependencies/rate_limit.py` at all in this chunk — see "Rate
  limiting: no changes" above.
- Do not touch `backend/app/modules/opt_out/` or `backend/app/modules/dsar/` routers.
- Do not add a reverse-proxy/gateway container to `backend/docker/docker-compose.yml` in this
  chunk (see the ADR's Decision §5 — explicitly out of scope).
- Do not import `backend/app/modules/billing/` anywhere in this chunk — there is no billing
  dependency left in this chunk's scope at all.

## Verification

- Add a test asserting `enable_brand_cors_origins=False` (default) leaves CORS behavior
  byte-for-byte identical to before this chunk (regression safety for existing deployments).
- Add a test asserting that with `enable_brand_cors_origins=True` and one active `Brand` row with
  a non-null `custom_domain`, that domain appears in the resolved CORS allow-list at startup, and
  a second `Brand` row with `custom_domain=None` contributes nothing.
- Add a test asserting an **inactive** brand's (`is_active=False`) `custom_domain` is excluded
  from the resolved allow-list even if non-null.
- Existing rate-limit tests (locate under `backend/tests/` — likely a `test_rate_limit*.py`
  file) must still pass completely unmodified — this chunk makes no code changes there, so this
  is a pure regression check, not new test-writing work.
