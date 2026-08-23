# Post-Tenancy Features, Chunk 3 — Org Offboarding and Deletion

## Depends on

`post-tenancy-retrofit/04-tenant-isolation-test-suite.md` green on real Postgres (same gate as
`post-tenancy-features/01` and `02`). `post-tenancy-features/01-billing-stripe-integration.md`
(needs `OrganizationSubscription`/Stripe customer linkage — this chunk's Stripe-redaction step
and "do not delete financial records" step both act on rows `01` creates).

## Goal

Machine-1's ADR (`docs/adr/0018-tenancy-model.md`) and schema chunk
(`machine-1-tenancy-core/02-schema-and-migration.md`) establish `Organization.is_active` as a
real, already-existing column, but no chunk in this doc set ever specs the **admin action** that
flips it, what happens to that org's users/sessions/billing when it does, or what "actually
delete an org's data" means at all. This chunk closes that gap with a staged deletion model:
soft-delete → grace period → hard-delete/anonymize → Stripe redaction → audit trail. Each stage
is a distinct, separately-triggerable step, not one irreversible action.

## Files to create

- `backend/app/modules/orgs/offboarding_service.py`
- `backend/app/modules/orgs/offboarding_router.py`
- `backend/app/modules/orgs/offboarding_models.py` (the tombstone/audit-trail table — kept
  separate from `models.py`'s `Organization`/`OrganizationInvite` since this is a distinct,
  append-only audit concern, not a core tenancy model; mirrors how `machine-1-tenancy-core/02`
  itself keeps `orgs/models.py` focused on the core `Organization` shape rather than growing
  every future org-lifecycle concern into the same file)
- `backend/alembic/versions/0XX_org_offboarding.py` (real number TBD — re-run
  `python -m alembic heads` from `backend/` immediately before writing this file; by the time
  this chunk is implemented, `machine-1`'s and `post-tenancy-retrofit`'s migrations should all
  already be numbered, so the head should be relatively stable, but the caveat still applies —
  `post-tenancy-features/01` and `02` may be implemented in parallel with this chunk and also
  want a migration)
- `docs/adr/00XX-org-offboarding-and-data-retention.md` — **spec only, do not create the actual
  ADR file in this planning doc set.** Per `docs/adr/README.md`'s "When to add an ADR" criteria,
  a storage/retention policy decision (what gets hard-deleted vs. anonymized vs. retained, and
  for how long) is squarely a "storage" pattern change, mandatory not optional — this chunk's
  actual implementer creates the real ADR file (next free number, re-verified against
  `docs/adr/README.md`'s index at implementation time, same caveat as every other ADR reference
  in this doc set) as part of doing this chunk's work. This planning doc only lists it as a
  deliverable, matching exactly how `post-tenancy-features/01-billing-stripe-integration.md`
  already handles its own `docs/adr/00XX-billing-provider.md` requirement (see that file's "ADR
  requirement" section for the precedent this chunk follows).

## Files to edit

- `backend/app/modules/orgs/models.py` — add `deletion_requested_at` column to `Organization`.
- `backend/app/modules/admin/` — wherever org-management admin actions are exposed (check
  whether `machine-2-parallel-tracks/04-rbac-admin-platform.md`'s CRUD surface or a later
  org-management router already has an org list/detail endpoint by implementation time; add the
  offboarding trigger endpoints there if so, or register `offboarding_router.py` standalone in
  `backend/app/main.py` if no natural existing home exists — document which was chosen in the PR).
- `backend/app/main.py` — register `offboarding_router.py` (if not folded into an existing admin
  router per above).

## Staged deletion model

### Stage 1 — Soft-delete (admin action)

Reuses `Organization.is_active` (already exists per `machine-1-tenancy-core/02`) — this chunk
adds the **admin action** that sets it, since no earlier chunk specs one:

```python
async def soft_delete_organization(
    db: AsyncSession, *, org_id: UUID, actor_id: UUID, reason: str | None
) -> Organization:
    """Stage 1: is_active=False, deletion_requested_at=now(), revoke all sessions
    for this org's users, stop active billing. Reversible — see restore_organization
    below — until Stage 3 (hard-delete) actually runs."""
    org = await repository.get_organization_by_id(db, org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    org.is_active = False
    org.deletion_requested_at = datetime.now(UTC)

    # Session revocation: reuse the existing refresh-token revocation primitive
    # (backend/app/auth/refresh_tokens.py's revoke_token_family, already used by
    # the impersonation/logout paths per machine-1-tenancy-core/03's own reference
    # to that module) for every user with org_id == org_id — do not invent a new
    # session-invalidation mechanism.
    org_users = await auth_repository.list_users_by_org(db, org_id)
    for user in org_users:
        await revoke_all_refresh_tokens_for_user(db, user.id)

    # Stop active billing: cancel the Stripe subscription immediately (not at
    # period end) via post-tenancy-features/01's StripeClient, so the org is not
    # charged again after being deactivated. Do NOT delete the
    # OrganizationSubscription row here — Stage 3 handles financial-record
    # retention separately; this step only stops future charges.
    subscription = await billing_repository.get_subscription_for_org(db, org_id)
    if subscription and subscription.stripe_subscription_id:
        await StripeClient().cancel_subscription(subscription.stripe_subscription_id)
        subscription.status = "canceled"

    await db.commit()
    await _record_tombstone_event(db, org_id=org_id, actor_id=actor_id, stage="soft_delete", detail=reason)
    return org
```

`revoke_all_refresh_tokens_for_user` — verify the exact existing function name/signature in
`backend/app/auth/refresh_tokens.py` before implementing (this doc's other chunks, e.g.
`machine-1-tenancy-core/03`, reference `revoke_token_family`/`revoke_refresh_token` as the
existing primitives — use whichever of those, or a thin wrapper looping over a user's tokens,
actually matches that file's real current shape).

A superuser/admin can **restore** from Stage 1 within the grace period (`is_active=True`,
`deletion_requested_at=None`) — this is the "reversible" property that makes soft-delete safe to
trigger without a second confirmation step being this chunk's only safety net.

### Stage 2 — Grace period (30 days, configurable)

```python
# Org offboarding: days between an org's soft-delete (deletion_requested_at set)
# and the earliest a hard-delete may run. Matches this doc set's existing bool/
# int-flag convention (see enable_demand_intelligence, default_org_rate_limit_per_minute).
org_deletion_grace_period_days: int = Field(default=30, alias="ORG_DELETION_GRACE_PERIOD_DAYS")
```

A scheduled or admin-triggered hard-delete call **must** check
`org.deletion_requested_at is not None and (datetime.now(UTC) - org.deletion_requested_at).days
>= settings.org_deletion_grace_period_days` before proceeding — raise `HTTPException(409, ...)`
if the window hasn't elapsed yet, rather than silently no-op'ing (a 409 makes an admin's premature
hard-delete attempt an obvious, actionable error rather than a mysterious no-op).

### Stage 3 — Hard-delete: cascade-delete or anonymize per domain

**Candidate PII (documents/CV chat/portfolio): anonymize or hard-delete.** For each org's users'
rows in `backend/app/modules/documents/` (`CandidateDocument`, `CvChatSession`, `CvChatMessage`,
`CvFeedbackReport` — the same set `post-tenancy-retrofit/02-outreach-documents-portfolio-tenant-
scoping.md` retrofits with `org_id`) and `backend/app/modules/portfolio/`
(`PortfolioProfile`, `PortfolioItem`): hard-delete the rows outright (candidate documents/CV chat
have no independent business reason to be retained past account deletion — unlike financial
records below, there is no legal retention requirement pulling the other way). Cascade via each
table's existing FK `ondelete` behavior where already `CASCADE`-configured (check each model
before assuming; add an explicit delete step in `offboarding_service.py` for any table that isn't
already cascade-configured from `users`/`organizations`, rather than relying on an FK cascade that
may not exist).

**Financial records (`OrganizationSubscription`, `StripeWebhookEvent`): do NOT delete, only
redact PII fields.** Cite the reason inline in the code, not just this doc: invoices and tax
records must be retained per legal requirements (financial recordkeeping obligations typically
run 5-7 years depending on jurisdiction) even after the underlying account is deleted — deleting
`OrganizationSubscription` outright would destroy the org's own billing history, which the org
(or a tax authority, in an audit) may need to reference long after the account itself is gone.
"Redact PII fields" means: keep `plan_tier`, `status`, `current_period_end`, `seats_included`,
timestamps (all needed for financial reporting); the row already has no candidate-identifying
PII on it at all (per `post-tenancy-features/01`'s model, it only carries `org_id`, Stripe ids,
and plan/status metadata) — so in practice this step is closer to "leave as-is, do not delete"
than "scrub fields," but the step is specced explicitly so a future implementer doesn't assume
"delete everything for this org" silently includes billing rows too.

```python
async def hard_delete_organization(db: AsyncSession, *, org_id: UUID, actor_id: UUID) -> None:
    org = await repository.get_organization_by_id(db, org_id)
    if org is None or org.deletion_requested_at is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending deletion for this org")
    grace_elapsed = (datetime.now(UTC) - org.deletion_requested_at).days
    if grace_elapsed < get_settings().org_deletion_grace_period_days:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Grace period has not elapsed ({grace_elapsed}/{get_settings().org_deletion_grace_period_days} days)",
        )

    deleted_counts = await _cascade_delete_candidate_pii(db, org_id)  # documents, CV chat, portfolio
    # OrganizationSubscription / StripeWebhookEvent: explicitly NOT deleted here.

    await _redact_stripe_customer(db, org_id)  # Stage 4, below — must run before removing the org row
    await db.execute(delete(User).where(User.org_id == org_id))
    await db.execute(delete(Organization).where(Organization.id == org_id))
    await db.commit()

    await _record_tombstone_event(
        db, org_id=org_id, actor_id=actor_id, stage="hard_delete", detail=str(deleted_counts)
    )
```

### Stage 4 — Stripe redaction

Call Stripe's **Redaction Jobs API** on the `Customer` object — **cite this as a real,
Stripe-documented ordering constraint, not an assumption**: Stripe's Redaction Jobs API
explicitly requires that a `Customer` have no open disputes and no unresolved/open invoices, and
that any active subscription be canceled first, before a redaction job on that customer will
succeed — attempting redaction out of that order fails at Stripe's API level, not silently. This
is why Stage 1 (soft-delete) already cancels the subscription immediately rather than waiting for
Stage 3: by the time Stage 4 runs (inside Stage 3's hard-delete, per the code above), the
subscription has already been canceled for at least the grace-period duration, giving any
in-flight invoice/dispute time to resolve naturally before redaction is attempted.

```python
async def _redact_stripe_customer(db: AsyncSession, org_id: UUID) -> None:
    subscription = await billing_repository.get_subscription_for_org(db, org_id)
    if subscription is None or not subscription.stripe_customer_id:
        return  # no Stripe relationship ever existed for this org — nothing to redact
    await StripeClient().create_redaction_job(subscription.stripe_customer_id)
    # Fire-and-forget from this service's perspective: Stripe's redaction job runs
    # asynchronously on their side. If it fails (e.g. an invoice opened between
    # Stage 1's cancellation and now), Stripe's own dashboard/webhook surfaces that
    # failure for manual follow-up — this chunk does not build a retry loop for a
    # third-party async job, it only triggers it at the correct point in the sequence.
```

### Stage 5 — Audit trail (tombstone)

```python
"""backend/app/modules/orgs/offboarding_models.py"""

class OrgDeletionEvent(Base):
    """Append-only tombstone: what was deleted/redacted for an org, and when. This
    is the only durable record that an org ever existed, once Stage 3 removes the
    Organization row itself — do not add an FK from this table to organizations.id
    (the org row it references may no longer exist by the time this row is read)."""

    __tablename__ = "org_deletion_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(nullable=False, index=True)  # not a live FK — see docstring
    org_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)  # "soft_delete"|"hard_delete"|"stripe_redaction"
    actor_id: Mapped[UUID | None] = mapped_column(nullable=True)  # admin who triggered it; NULL for scheduled jobs
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
```

`org_id` is deliberately **not** a foreign key to `organizations.id` — a hard-delete tombstone
event for stage `"hard_delete"` is written in the same transaction that removes the `Organization`
row, and a later read of this table (e.g. an auditor asking "what happened to org X") must still
work after that row is gone. `org_name_snapshot` is captured at write time precisely because the
name won't be joinable later.

## `backend/app/modules/orgs/offboarding_router.py`

```python
router = APIRouter(prefix="/api/orgs", tags=["org-offboarding"])

@router.post("/{org_id}/deactivate", status_code=status.HTTP_200_OK)
async def deactivate_organization(
    org_id: UUID,
    body: DeactivateOrgRequest,  # {"reason": str | None}
    user: User = Depends(require_permission("orgs", "delete")),  # new resource:action pair, seed via this chunk's migration
    db: AsyncSession = Depends(get_db_session),
) -> OrganizationResponse: ...

@router.post("/{org_id}/restore", status_code=status.HTTP_200_OK)
async def restore_organization(
    org_id: UUID,
    user: User = Depends(require_permission("orgs", "delete")),
    db: AsyncSession = Depends(get_db_session),
) -> OrganizationResponse: ...  # only valid before Stage 3 has run

@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def hard_delete_organization_route(
    org_id: UUID,
    user: User = Depends(require_permission("orgs", "delete")),
    db: AsyncSession = Depends(get_db_session),
) -> None: ...
```

Gate all three behind `is_superuser` in practice, not merely `("orgs", "delete")` — check
`require_permission`'s existing superuser short-circuit (referenced in
`post-tenancy-retrofit/03-admin-tenant-scoping.md`) already covers this, but document explicitly
in the PR that org deletion is intended to be a platform-superuser action, not something an
`agency_owner` grants themselves via `04-rbac-admin-platform.md`'s role CRUD — do not seed
`("orgs", "delete")` onto either `agency_owner` or `agency_recruiter`'s permission set in this
chunk's migration; only a superuser should hold it.

## Ambiguities resolved

- **Should candidate documents/CV chat be anonymized (kept, PII stripped) or hard-deleted?**
  Hard-deleted — decided explicitly. Unlike financial records, there is no legal retention
  requirement pulling toward keeping a deleted candidate's CV/chat history around in any form,
  anonymized or not; keeping it "just in case" is a larger privacy liability than the value of
  retaining it, and the candidate (via the org's own deletion) has affirmatively exited.
- **Should `OrganizationSubscription`/`StripeWebhookEvent` rows be deleted along with everything
  else?** No — retained, PII-redaction-only (which in practice is a no-op given these tables carry
  no PII fields today; see Stage 3 above) — decided explicitly per legal invoice/tax-record
  retention requirements, not left as a follow-up question.
- **Is soft-delete (Stage 1) reversible?** Yes, until Stage 3 (hard-delete) actually runs —
  `restore_organization` is the explicit undo path; the grace period exists precisely to give an
  org a real window to reverse an accidental or reconsidered deletion request.

## Do not touch

- `backend/app/modules/documents/`, `backend/app/modules/portfolio/` model/service files
  themselves — this chunk calls existing delete operations against those tables from
  `offboarding_service.py`, it does not add new columns or change those modules' own CRUD logic.
- `backend/app/modules/billing/models.py`, `service.py` — read-only reference
  (`get_subscription_for_org`, `StripeClient.cancel_subscription`/`create_redaction_job` — the
  latter two are new `StripeClient` methods this chunk adds to
  `backend/app/integrations/stripe/client.py`, since `post-tenancy-features/01` didn't need
  cancellation/redaction for its own scope — confirm at implementation time whether `01` already
  added `cancel_subscription`/redaction methods by the time this chunk starts, and only add
  what's missing rather than duplicating).
- `backend/app/auth/refresh_tokens.py` — reused as-is (existing revocation primitives), not
  modified.
- Do not seed `("orgs", "delete")` onto any non-superuser role (see router section above).
- Do not build a scheduled/cron job that auto-triggers Stage 3 once the grace period elapses in
  this chunk's minimum scope — an admin-triggered hard-delete call (which itself enforces the
  grace-period check) satisfies this chunk's requirements; a fully automatic scheduled sweep is an
  acceptable, encouraged extension but not required, and if added must reuse the exact same
  `hard_delete_organization` function rather than duplicating its grace-period/ordering logic.

## Verification

- Test: `soft_delete_organization` sets `is_active=False`, `deletion_requested_at`, revokes every
  org user's refresh tokens (assert a previously-valid refresh token 401s afterward), and cancels
  an active Stripe subscription if one exists.
- Test: `restore_organization` reverses Stage 1 (`is_active=True`, `deletion_requested_at=None`)
  and a previously soft-deleted org's users can log in again.
- Test: `hard_delete_organization` called before the grace period elapses returns 409 and deletes
  nothing.
- Test: `hard_delete_organization` called after the grace period elapses removes
  `CandidateDocument`/`CvChatSession`/`PortfolioProfile` rows for that org's users, removes the
  `User` and `Organization` rows themselves, but leaves the `OrganizationSubscription` row intact
  (assert it's still queryable by `org_id` after the org itself is gone — since `org_id` isn't a
  live FK on that table either, per `post-tenancy-features/01`'s own model, this should already
  work, but assert it explicitly as a regression check).
- Test: `_redact_stripe_customer` is called with the org's `stripe_customer_id` exactly once, and
  only after the subscription's `status` is already `"canceled"` (ordering assertion, mocking
  `StripeClient.create_redaction_job` and asserting on call order relative to the cancellation
  that happened in Stage 1).
- Test: a `OrgDeletionEvent` row exists for both the soft-delete and hard-delete stages, with
  `org_name_snapshot` correctly captured, and remains readable via a direct query after the
  `Organization` row no longer exists.
- Test: `require_permission("orgs", "delete")` is not granted to `agency_owner`/`agency_recruiter`
  by the seeded RBAC data (assert a non-superuser org owner gets 403 on all three endpoints).
