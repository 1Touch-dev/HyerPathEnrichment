# Post-Tenancy Features, Chunk 3 — Brand Deactivation

## Depends on

`machine-1-tenancy-core`'s `Brand` model (`is_active` column — see
`machine-1-tenancy-core/02-schema-and-migration.md`). `post-tenancy-features/01-billing-stripe-
integration.md` is **not** a dependency of this chunk — billing in this model is candidate-level
(`UserSubscription`), not brand-level, so deactivating a brand has no billing side effect to
sequence against.

## Goal (shrunk from the pre-pivot "org offboarding and deletion" scope)

A `Brand` never owned candidates in this model — there is one shared candidate/recruiter pool,
independent of any brand, and `candidates.signup_brand_id` is a presentation-only, nullable
pointer to which storefront a candidate happened to sign up through, never a data-isolation
boundary or an ownership record. That means **deactivating (or ever removing) a brand has no
cascading effect on candidates, recruiters, or their data at all.** There is no candidate PII to
anonymize, no user rows to delete, no session revocation to perform, and no staged grace-period/
hard-delete/redaction pipeline to build — all of that machinery existed in the prior design only
because organizations *owned* their users' data; brands do not.

This chunk is therefore just: **an admin action that turns a brand's public presentation off.**
Deactivating a brand:

- Sets `Brand.is_active = False`.
- Takes the brand's public landing page (`/b/{slug}` and any `/b/{slug}/{tier}` sub-pages, per
  `post-tenancy-features/02-brand-landing-pages.md`) offline — `get_public_brand` already 404s on
  `is_active=False` per that chunk's spec, so this is a natural consequence of the flag, not new
  logic this chunk must add.
- Does **not** touch any candidate, recruiter, `signup_brand_id` value, job match, outreach
  message, document, or portfolio row. A candidate whose `signup_brand_id` points at a since-
  deactivated brand keeps 100% of their own data and platform access unchanged — `signup_brand_id`
  is a historical breadcrumb, not a live dependency.
- Is reversible at any time (re-activate by flipping the flag back) — there is no grace period,
  no staged pipeline, and no irreversible step anywhere in this chunk's scope, because there is
  nothing destructive being staged toward in the first place.

If a future need arises to actually delete a `Brand` row outright (not just deactivate it), that
is a separate, much smaller follow-up than this doc's pre-pivot version implied: since nothing
else references `brands.id` except `candidates.signup_brand_id` (nullable, `ON DELETE SET NULL`
per `machine-1-tenancy-core/02`), a hard delete of a `Brand` row is a single-table operation with
no cross-domain cascade to design. That follow-up is explicitly out of scope for this chunk — see
"Do not touch" below.

## Files to create

- `backend/app/modules/orgs/deactivation_service.py`
- `backend/app/modules/orgs/deactivation_router.py`

No new model, no new migration, and no ADR is needed for this chunk. `Brand.is_active` already
exists as a column (per `machine-1-tenancy-core/02-schema-and-migration.md`'s field list); this
chunk only adds the admin-facing action that flips it, plus its audit logging. There is no
tombstone/audit-trail table to create either — see "Audit trail" below for why an existing
mechanism covers this instead of a new one.

## Files to edit

- `backend/app/main.py` — register `deactivation_router.py` (or fold its two routes into
  whichever admin router already exposes brand list/detail management, if one exists by
  implementation time — check `machine-2-parallel-tracks/04-rbac-admin-platform.md`'s CRUD
  surface first; document which was chosen in the PR, matching how the pre-pivot version of this
  file made the same call for org-management admin actions).

## `backend/app/modules/orgs/deactivation_service.py`

```python
async def deactivate_brand(
    db: AsyncSession, *, brand_id: UUID, actor_id: UUID, reason: str | None
) -> Brand:
    """Turn a brand's public presentation off. No cascading effect on candidates,
    recruiters, or any of their data — a Brand is presentation-only, never a data
    owner, in this model. Fully reversible via reactivate_brand below."""
    brand = await repository.get_brand_by_id(db, brand_id)
    if brand is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")

    brand.is_active = False
    await db.commit()
    await _log_brand_action(db, brand_id=brand_id, actor_id=actor_id, action="deactivate", detail=reason)
    return brand


async def reactivate_brand(db: AsyncSession, *, brand_id: UUID, actor_id: UUID) -> Brand:
    """Undo. No grace period, no staged pipeline — there is nothing irreversible
    to have committed to in the first place, so re-activation is always available."""
    brand = await repository.get_brand_by_id(db, brand_id)
    if brand is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")

    brand.is_active = True
    await db.commit()
    await _log_brand_action(db, brand_id=brand_id, actor_id=actor_id, action="reactivate", detail=None)
    return brand
```

## `backend/app/modules/orgs/deactivation_router.py`

```python
router = APIRouter(prefix="/api/orgs", tags=["brand-lifecycle"])

@router.post("/{brand_id}/deactivate", status_code=status.HTTP_200_OK)
async def deactivate_brand_route(
    brand_id: UUID,
    body: DeactivateBrandRequest,  # {"reason": str | None}
    user: User = Depends(require_permission("brands", "delete")),
    db: AsyncSession = Depends(get_db_session),
) -> BrandResponse: ...

@router.post("/{brand_id}/reactivate", status_code=status.HTTP_200_OK)
async def reactivate_brand_route(
    brand_id: UUID,
    user: User = Depends(require_permission("brands", "delete")),
    db: AsyncSession = Depends(get_db_session),
) -> BrandResponse: ...
```

Only two routes — there is no third "hard-delete" route in this chunk's minimum scope (see
"Goal" above on why a future hard-delete of the `Brand` row itself, if ever needed, is a separate,
much smaller follow-up than deactivation). Gate both behind the same `("brands", "delete")`
resource:action pair the pre-pivot version used for org deletion — reuse the permission name
rather than inventing a new one, since the underlying admin capability ("can retire a brand") is
conceptually the same even though the mechanics shrank.

## Audit trail: reuse existing admin audit logging, no new table

The pre-pivot version of this chunk introduced a standalone `OrgDeletionEvent` tombstone table
specifically because a hard-delete would remove the `Organization` row itself, and an FK-based
audit log can't reference a row that no longer exists. **That constraint doesn't apply here** —
deactivation never deletes the `Brand` row, so there is always a live row for an audit entry to
reference. Use whatever general-purpose admin audit-logging mechanism this repo already has
(`backend/app/modules/admin/audit.py` — read its current shape before assuming a specific function
signature) for `_log_brand_action` above, rather than creating a second, brand-specific audit
table that duplicates a capability the admin module already provides. If `audit.py`'s existing
logger requires a resource type it doesn't yet recognize, add `"brand"` to whatever enum/literal
type gates that (a small, additive change), not a parallel logging system.

## Ambiguities resolved

- **Should deactivating a brand revoke sessions for anyone?** No — there is no one to revoke.
  Recruiters and candidates are never scoped to a brand (no `users.org_id`-equivalent access
  gate exists in this model at all — see `machine-1-tenancy-core/00-overview.md`'s framing), so
  there are no brand-scoped sessions for a deactivation to invalidate.
- **Should this chunk stop billing for anyone?** No — billing is per-candidate
  (`UserSubscription`), not per-brand; a candidate who signed up through a brand keeps their own
  subscription status regardless of that brand's `is_active` value.
- **Does this chunk need a grace period before some later irreversible step?** No — deactivation
  is the only action in scope, and it is fully reversible at any time; there is no later
  irreversible step this chunk stages toward.
- **What happens to `candidates.signup_brand_id` when a brand is deactivated (or, in a future
  hard-delete follow-up, removed entirely)?** Nothing, by design — deactivation never touches it.
  If a brand row is ever hard-deleted in a future follow-up, the existing `ON DELETE SET NULL` FK
  behavior (per `machine-1-tenancy-core/02-schema-and-migration.md`) already handles it correctly
  without any application code: the candidate's `signup_brand_id` simply becomes `NULL`, and
  nothing about their platform access changes, because nothing was ever gated on that column.

## Do not touch

- `backend/app/modules/documents/`, `backend/app/modules/portfolio/`,
  `backend/app/modules/job_matching/`, `backend/app/modules/outreach/`,
  `backend/app/auth/` (`User` rows) — none of these are touched by brand deactivation. If a PR
  implementing this chunk finds itself editing any file under these paths, that is a sign of
  scope creep back toward the pre-pivot cascading-deletion design; stop and re-read the "Goal"
  section above.
- `backend/app/modules/billing/` — no interaction; billing is candidate-level and has no brand
  dependency (see `post-tenancy-features/01-billing-stripe-integration.md`).
- Do not build a hard-delete-the-`Brand`-row endpoint, staged grace period, PII anonymization
  pipeline, or Stripe redaction step in this chunk — all of that belonged to the pre-pivot
  "organizations own their data" model and has no analogue here. If an actual brand hard-delete
  is later needed, it is a small, separate follow-up (see "Goal" above), not part of this chunk.
- Do not seed `("brands", "delete")` onto any candidate-facing or brand-storefront-staff role —
  this remains a platform-admin action, same restriction the pre-pivot design applied to org
  deletion, even though the blast radius of the action itself is now much smaller.

## Verification

- Test: `deactivate_brand` sets `Brand.is_active = False` and logs an audit entry; a subsequent
  `GET /api/orgs/public/{slug}` for that brand 404s (per
  `post-tenancy-features/02-brand-landing-pages.md`'s existing `is_active` check — this is a
  regression check that the two chunks compose correctly, not new logic in either).
- Test: `reactivate_brand` reverses this (`is_active = True`), and the brand's public landing page
  becomes reachable again immediately, with no grace-period wait.
- Test: deactivating a brand does not change the row count, content, or accessibility of any
  candidate's data, `UserSubscription`, job match, outreach message, document, or portfolio —
  assert this explicitly for at least one candidate whose `signup_brand_id` points at the
  deactivated brand (the case most likely to tempt an incorrect cascading-delete regression).
- Test: `require_permission("brands", "delete")` is not granted to any non-superuser role by the
  seeded RBAC data (assert a non-superuser gets 403 on both endpoints).
