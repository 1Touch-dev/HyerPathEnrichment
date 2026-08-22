# Post-Tenancy Retrofit, Chunk 3 — Admin Tenant Scoping

## Depends on

`machine-1-tenancy-core` fully merged. Parallel-safe with `01` and `02`. If
`machine-2-parallel-tracks/04-rbac-admin-platform.md` has also merged by this point, its
`agency_owner`/`agency_recruiter` roles and `roles:write`-gated CRUD endpoints already exist —
this chunk makes them tenant-*aware*, it does not create them (they were created without any
`org_id` dependency, by design — see that file's Goal section).

## Goal

Two distinct concerns, both real:

1. **Admin's own moderation/audit surfaces must not leak cross-org data** to an `agency_owner`/
   `agency_recruiter`-scoped admin — e.g. an agency's review-queue view must only show flagged
   resources belonging to that agency's own candidates/jobs/outreach, not every org's.
2. **Platform superusers (`is_superuser=True`) must keep seeing everything, unscoped** — the
   existing `require_superuser`/`user_has_permission`'s `is_superuser` short-circuit (
   `backend/app/modules/admin/permissions.py` lines 19-23) already gives superusers an
   org-independent view by construction; this chunk must not accidentally break that by adding a
   blanket `org_id` filter that even superusers get subjected to.

## Files to edit

- `backend/app/modules/admin/permissions.py`
- `backend/app/modules/admin/repository.py`
- `backend/app/modules/admin/review_queue_router.py` (and whichever domain-specific admin
  routers — `outreach_router.py`, `documents_router.py`, `portfolio_router.py`,
  `job_postings_router.py`, `job_swipe_router.py` — actually filter lists of resources; read each
  before assuming which ones need the change, since some (e.g. `flags_router.py`,
  `health_router.py`, `analytics_router.py`) are platform-wide by nature and should **not** be
  org-scoped)
- New migration adding `org_id` to `admin_review_queue` (denormalized copy, or resolved via join
  to the underlying resource's own now-org_id'd table — see below) and, if a non-superuser
  "agency admin" role should only manage users within their own org,
  `backend/app/modules/admin/users_router.py` / `service.py`.

## Design decision this chunk must make explicitly (flag in PR if genuinely ambiguous)

`AdminReviewQueueItem` (`backend/app/modules/admin/models.py` lines 148-172) is **deliberately
decoupled** from domain ORM models today — its own docstring says resolution of the underlying
resource is done via raw SQL in `review_queue_router.py`, specifically to keep the admin module
decoupled from job_matching/documents/portfolio/outreach models. Adding an `org_id` filter here
has two options:

- **(a) Denormalize:** add `org_id` directly onto `AdminReviewQueueItem`, populated at flag-
  creation time (`backend/app/modules/admin/moderation_flagging.py`'s `flag_if_needed` — thread
  the flagging resource's `org_id` through to this call). Fast to query, but the review-queue
  module now has an implicit dependency on every domain module's `org_id` column existing and
  being passed through correctly.
- **(b) Resolve at query time:** keep `AdminReviewQueueItem` schema-decoupled as today, and have
  `review_queue_router.py`'s existing raw-SQL resolution step also fetch the resource's `org_id`
  from its own table and filter in application code (not SQL) before returning results to a
  non-superuser caller.

**Prefer (a)** — it matches this module's existing "flag at write time" pattern (`flag_if_needed`
already writes several fields at flag-creation time rather than resolving them lazily), and
avoids N+1 cross-module queries in the hot admin-review-queue list path. Only fall back to (b) if
implementing (a) turns out to require `moderation_flagging.py` to import from four other modules
in a way that creates real circular-import problems — document that finding in the PR if so.

## `backend/app/modules/admin/permissions.py` retrofit

Add a **new**, additive dependency — do not modify `require_permission`/`user_has_permission`'s
existing behavior, since those are also relied on by `machine-2/04-rbac-admin-platform.md`'s new
CRUD endpoints and must keep working identically for platform-superuser use:

```python
def require_permission_scoped_to_org(resource: str, action: str) -> Callable[..., Any]:
    """Like require_permission, but additionally returns the caller's org_id for the
    route to use as a query filter. Superusers get org_id=None (meaning "no filter,
    see everything") even if they happen to have an org_id set on their own User row —
    superuser status always means unscoped access, by design (Decision 1)."""

    async def _check(user: VerifiedUser, db: AsyncSession = Depends(get_db_session)) -> tuple[User, UUID | None]:
        if not await user_has_permission(db, user, resource, action):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing permission: {resource}:{action}")
        scoping_org_id = None if user.is_superuser else user.org_id
        return user, scoping_org_id

    return _check
```

Retrofit each domain-specific admin router's list/detail endpoints to use this instead of plain
`require_permission`, and pass the returned `org_id` through to the repository call, following
the identical no-op-when-None pattern from `post-tenancy-retrofit/01`.

## `backend/app/modules/admin/users_router.py` / `service.py`

Decide (and document the decision in the PR): should a non-superuser `agency_owner` be able to
see/manage users **outside** their own org via the existing `list_users_paginated`/
`update_user_status`/`assign_role` admin endpoints? **Default to no** — an agency's own admin
role should only manage its own org's recruiters, not the platform's entire user base. Retrofit
`list_users_paginated` with the same optional `org_id` filter pattern; `update_user_status`/
`assign_role` (single-user mutations) must re-check the target user's `org_id` matches the
caller's scoping `org_id` (or the caller is a superuser) before allowing the mutation — this is
the single-row "owned lookup" pitfall called out in `01`'s file, applying here too.

## Do not touch

- `backend/app/modules/admin/mfa.py`, `mfa_router.py`, `impersonation.py`,
  `impersonation_router.py`, `audit.py`, `audit_router.py`, `health.py`, `health_router.py`,
  `flags_router.py`, `analytics.py`, `analytics_router.py`, `cache.py`, `pagination.py` —
  platform-wide admin concerns, not org-scoped in this chunk. (Impersonation in particular stays
  superuser-gated regardless of org, per existing design — do not add org scoping to who can be
  impersonated.)
- `backend/app/modules/admin/models.py`'s `Role`/`Permission`/`RolePermission` schema — RBAC
  itself is not org-scoped in this repo's design (a role's *permission grants* are global; only
  the *data a role's holder can see* becomes org-scoped, via this chunk's query-filter retrofit,
  not via making roles themselves per-org objects). Do not add `org_id` to `Role`.

## Verification

- Two orgs, each with an `agency_owner`: assert neither can see the other's flagged review-queue
  items, users, or domain-specific admin list endpoints.
- Assert a superuser (`is_superuser=True`, `org_id=None` or set — test both) sees all orgs'
  data unfiltered through every retrofitted endpoint — this is the regression most likely to slip
  through if `require_permission_scoped_to_org`'s superuser short-circuit is implemented
  incorrectly.
- Assert `update_user_status`/`assign_role` 404 (not 403 — don't leak existence) when a non-
  superuser agency admin targets a user outside their org.
