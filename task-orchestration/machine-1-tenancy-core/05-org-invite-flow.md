# Machine 1, Chunk 5 — Org Invite Flow

## Depends on

Chunk `03`'s `org_id` JWT claim, `OrgScopedUser`/`require_org_member` dependency
(`backend/app/auth/dependencies.py`), and chunk `02`'s `Organization` model and
`backend/app/modules/orgs/` module (`models.py`, `schemas.py`, `repository.py` all already
exist). Soft dependency on `machine-2-parallel-tracks/04-rbac-admin-platform.md`'s
`agency_owner`/`agency_recruiter` system roles (seeded by that chunk's migration) — **do not
block on `04` landing first**, same "do not block" pattern chunk `06`
(`machine-2-parallel-tracks/06-linkedin-outreach-send.md`) already uses for its own soft
dependency on `04`'s RBAC CRUD surface. If `04` has not merged yet at implementation time, the
`role_name` field on an invite is still stored (a plain string), it just cannot be validated
against a real `Role` row yet — validate against `Role.name` existing in `admin_roles` only when
that table already has rows for `agency_owner`/`agency_recruiter`; otherwise accept the string
as-is and let acceptance fail at role-assignment time with a clear error, rather than blocking
invite creation on a track this chunk does not own.

## Ground truth (verified 2026-08-22, corrects the informal "POST /api/auth/signup" framing)

The actual signup endpoint is `backend/app/auth/router.py`'s `register()` function, mounted at
`POST /auth/register` (router prefix `/auth`, see `router = APIRouter(prefix="/auth", ...)` at
line 49), not `/api/auth/signup`. It takes `UserCreate` (`backend/app/auth/schemas.py` lines
36-42: `email`, `password`, `first_name`, `last_name` — no `org_id`/`invite_token` field today).
This chunk edits that real endpoint/schema; any reference elsewhere in this doc set to
"`POST /api/auth/signup`" should be read as this actual route.

## Files to create

- `backend/alembic/versions/047_org_invites.py` (migration-number caveat: this is at least the
  fifth track in this doc set wanting `047` — `machine-1/02`, `machine-2/02`, `machine-2/03`,
  `machine-2/04` all also write a `047_*` file, and this chunk is dispatched after `03` (see
  "Merge order" in the root `README.md`), so by the time this chunk is implemented `machine-1`'s
  own `02` and `03` migrations should already have landed at real numbers. **Re-run
  `python -m alembic heads` from `backend/` immediately before writing this migration** and use
  the real next number and real `down_revision` — do not assume `047` is free.)

## Files to edit

- `backend/app/auth/router.py`
- `backend/app/modules/orgs/models.py`
- `backend/app/modules/orgs/schemas.py`
- `backend/app/modules/orgs/repository.py`

(All four already exist per chunk `02` and chunk `03`'s edits — this chunk adds to them, it does
not create the `orgs` module.)

## `backend/app/modules/orgs/models.py` — new `OrganizationInvite` model

Add, in the same file as `Organization` (chunk `02`):

```python
import secrets
from datetime import timedelta

from sqlalchemy import ForeignKey, Text


class OrganizationInvite(Base):
    """A pending invitation for an email address to join an Organization with a
    specific role. See machine-1-tenancy-core/05-org-invite-flow.md for the
    accept/expiry/seat-enforcement rules that govern this table."""

    __tablename__ = "organization_invites"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # secrets.token_urlsafe(32): cryptographically random, URL-safe, ~43 chars —
    # not a sequential id or anything derivable from org_id/email, since this token
    # is the entire bearer-credential for GET /api/orgs/invites/{token} (public,
    # unauthenticated) and for redeeming org membership at signup.
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    # The role to assign on acceptance. References Role.name from
    # machine-2-parallel-tracks/04-rbac-admin-platform.md's seeded agency_owner/
    # agency_recruiter rows — stored as a plain string, not a FK to admin_roles.id,
    # because this module (orgs) does not import from the admin module (see chunk
    # 02's file boundary) and because 04 may not have landed yet when this chunk is
    # implemented (same "do not block on 04" pattern chunk 06 already uses).
    role_name: Mapped[str] = mapped_column(String(64), nullable=False, default="agency_recruiter")
    invited_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # 7 days, matching common B2B SaaS invite-expiry convention (long enough to
    # survive a slow-to-respond invitee's weekend, short enough that a stale invite
    # doesn't sit as a live, unaccounted-for seat-reservation indefinitely).
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC) + timedelta(days=7),
        nullable=False,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
```

`invited_by`'s FK uses `ondelete="SET NULL"` (not `CASCADE`) — deleting the inviting user's
account must not cascade-delete a still-pending invite for someone else; the invite should
survive with `invited_by=None` and remain acceptable. Note this is the *opposite* choice from
`org_id`'s `ondelete="CASCADE"` (deleting the whole org legitimately voids all its pending
invites).

## `backend/app/modules/orgs/schemas.py` additions

```python
class OrganizationInviteCreate(BaseModel):
    email: EmailStr
    role_name: str = Field(default="agency_recruiter", max_length=64)


class OrganizationInviteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    org_id: UUID
    email: str
    role_name: str
    expires_at: datetime
    accepted_at: datetime | None


class PublicInviteResponse(BaseModel):
    """Response for GET /api/orgs/invites/{token} — unauthenticated, so this must
    leak nothing beyond what a pending-signup UI genuinely needs to display."""

    org_name: str
    invited_by_name: str | None
    email: str
    expires_at: datetime
```

## `backend/app/modules/orgs/repository.py` additions

```python
async def get_invite_by_token(db: AsyncSession, token: str) -> OrganizationInvite | None: ...

async def get_pending_invite_for_email(
    db: AsyncSession, org_id: UUID, email: str
) -> OrganizationInvite | None:
    """Pending (accepted_at IS NULL) and unexpired invite for this (org_id, email)
    pair, if any. Backs the resend-upsert edge case below — do not create a second
    row for the same still-pending, unexpired email."""
    ...

async def count_active_members(db: AsyncSession, org_id: UUID) -> int:
    """COUNT(*) of users.org_id == org_id (active org members). Used by the seat
    check below alongside count_pending_invites."""
    ...

async def count_pending_invites(db: AsyncSession, org_id: UUID) -> int:
    """COUNT(*) of organization_invites where org_id matches, accepted_at IS NULL,
    expires_at > now(). An expired-but-not-yet-accepted invite does not consume a
    seat — it is functionally dead."""
    ...

async def create_invite(
    db: AsyncSession, *, org_id: UUID, email: str, role_name: str, invited_by: UUID
) -> OrganizationInvite:
    invite = OrganizationInvite(
        id=uuid4(), org_id=org_id, email=email, role_name=role_name,
        invited_by=invited_by, token=secrets.token_urlsafe(32),
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return invite
```

## `POST /api/orgs/{org_id}/invites`

Add to a router in the `orgs` module (this chunk creates the router file if chunk `04`'s
`machine-2-parallel-tracks/04-rbac-admin-platform.md`'s admin org-management router has not yet
been added there — if it has, add this endpoint to that existing file instead of creating a
parallel one; check at implementation time which is true and document the choice taken):

```python
@router.post(
    "/orgs/{org_id}/invites",
    response_model=OrganizationInviteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invite(
    org_id: UUID,
    body: OrganizationInviteCreate,
    user: User = Depends(require_permission("users", "write")),  # reuse existing admin permission pattern (04-rbac-admin-platform.md)
    db: AsyncSession = Depends(get_db_session),
) -> OrganizationInviteResponse:
    # Resend-upsert edge case: reuse a still-pending, unexpired invite for the same
    # email instead of creating a duplicate seat-consuming row.
    existing = await repository.get_pending_invite_for_email(db, org_id, body.email)
    if existing:
        return OrganizationInviteResponse.model_validate(existing)

    # Seat enforcement (closes gap 6): fail closed on revenue-bearing limits.
    subscription = await billing_repository.get_subscription_for_org(db, org_id)
    if subscription is not None:
        active_members = await repository.count_active_members(db, org_id)
        pending_invites = await repository.count_pending_invites(db, org_id)
        if active_members + pending_invites + 1 > subscription.seats_included:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="This organization has reached its seat limit for the current plan",
            )
    # subscription is None (no OrganizationSubscription row at all — e.g.
    # enable_billing=False, or a free tier that never created one): skip the check.
    # Fail open only for the *absence* of a billing relationship, not for a
    # present-but-exceeded one — see "Ambiguities resolved" below.

    invite = await repository.create_invite(
        db, org_id=org_id, email=body.email, role_name=body.role_name, invited_by=user.id,
    )
    return OrganizationInviteResponse.model_validate(invite)
```

`billing_repository.get_subscription_for_org` is a read-only import from
`post-tenancy-features/01-billing-stripe-integration.md`'s
`backend/app/modules/billing/repository.py` — **this creates a real cross-track dependency**:
this chunk's seat-enforcement code path only executes correctly once `post-tenancy-features/01`
has landed. Per the root `README.md`'s merge order, `post-tenancy-features/01` merges long after
`machine-1` (it needs the `post-tenancy-retrofit/04` hard gate to pass first), so at the time
`05` itself is implemented and merged, `OrganizationSubscription` almost certainly does not exist
yet. **Resolve this the same way chunk `03` resolved its own forward-reference to invite-based
signup**: implement the seat-check function so it degrades safely (treat "billing module import
fails / table doesn't exist" identically to "`subscription is None`" — skip the check, do not
raise) until `post-tenancy-features/01` actually lands, then a small follow-up PR (or
`post-tenancy-features/01` itself, if implemented after this chunk) wires the real import. Flag
this exact sequencing note in the PR description so a reviewer doesn't mistake it for a forgotten
import.

## `GET /api/orgs/invites/{token}`

Public, unauthenticated (no `CurrentUser`/`VerifiedUser` dependency — mirrors
`post-tenancy-features/02-brand-landing-pages.md`'s `get_public_organization` pattern: no auth
dependency, 404 on missing):

```python
@router.get("/orgs/invites/{token}", response_model=PublicInviteResponse)
async def get_invite(token: str, db: AsyncSession = Depends(get_db_session)) -> PublicInviteResponse:
    invite = await repository.get_invite_by_token(db, token)
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
    if invite.accepted_at is not None:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invite already accepted")
    if invite.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invite has expired")
    org = await orgs_repository.get_organization_by_id(db, invite.org_id)
    inviter = await auth_repository.get_user_by_id(db, invite.invited_by) if invite.invited_by else None
    return PublicInviteResponse(
        org_name=org.name,
        invited_by_name=f"{inviter.first_name} {inviter.last_name}" if inviter else None,
        email=invite.email,
        expires_at=invite.expires_at,
    )
```

Use `404` for "no such token" and `410 Gone` for "existed but is now unusable" (expired or
accepted) — distinct from a plain 404 so a pending-signup UI can show "this invite already used"
rather than "invite not found," a materially different message for the invitee.

## `POST /auth/register` edit (the real endpoint — see "Ground truth" above)

Add `invite_token: str | None = None` to `UserCreate` (`backend/app/auth/schemas.py`).

In `register()` (`backend/app/auth/router.py`, current body at lines 127-183), after the
existing "email already registered" check and before `db.add(user)`, add invite resolution:

```python
    invite: OrganizationInvite | None = None
    invite_warning: str | None = None
    if user_data.invite_token:
        invite = await orgs_repository.get_invite_by_token(db, user_data.invite_token)
        if invite is None or invite.accepted_at is not None or invite.expires_at < datetime.now(UTC):
            # Ambiguities resolved: an invalid/expired token does NOT hard-fail
            # signup — the user still gets an account (org_id=None, normal
            # direct-candidate signup), and the response carries a warning
            # instead. A dead invite link should not be a dead-end for someone
            # who was genuinely trying to sign up; org membership can always be
            # granted later by an admin action, but losing the signup entirely
            # over a stale link is a worse user experience than a degraded one.
            invite = None
            invite_warning = "Your invite link is invalid or has expired; your account was created without an organization."
```

Then, when constructing `user = User(...)`, set `org_id=invite.org_id if invite else None`.
After `db.add(user)` / `await db.commit()` / `await db.refresh(user)` (existing lines
156-158), if `invite` is not `None`: assign the role (call whichever role-assignment function
chunk `04`'s `roles_service.py` exposes, e.g. `assign_role(db, actor_id=invite.invited_by,
user_id=user.id, role_name=invite.role_name)` — if `04` has not landed yet at implementation
time, skip role assignment and log a warning instead of raising, consistent with the "do not
block on `04`" dependency posture above), and set `invite.accepted_at = datetime.now(UTC)` then
`await db.commit()`.

`MessageResponse` (the existing return type) does not currently carry a warning field — extend
it (or introduce a sibling response, e.g. `RegisterResponse(MessageResponse)` with an optional
`warning: str | None = None` field) to surface `invite_warning` to the caller without breaking
existing callers that only read `.message`. Document which approach was taken in the PR
description; either is acceptable as long as `invite_warning is None` produces byte-identical
JSON to today's `MessageResponse` (regression safety for existing signup clients).

## Ambiguities resolved

- **Invalid/expired invite token: hard-fail signup, or fall back to normal signup?** Fall back
  (see code block above) — decided explicitly, not left as an implementer's choice, per the task
  brief's instruction. A broken invite link must not block account creation entirely.
- **Resending an invite to the same still-pending, unexpired email:** upsert (return the existing
  row, do not create a second one) — see `get_pending_invite_for_email` above. A resend to an
  *expired* or *already-accepted* invite's email address, by contrast, *does* create a new row
  (the old one is functionally dead and does not block a fresh invite).
- **Billing relationship absent vs. present-but-exceeded:** skip the seat check only when no
  `OrganizationSubscription` row exists at all for the org (billing disabled, or a free tier that
  never provisioned one) — fail open only for that absence. If a subscription row exists and its
  seat count is exceeded, always reject with 402, regardless of `plan_tier` — "fail closed on
  revenue-bearing limits."
- **Where does the seat check's `+1` come from?** It accounts for the invite being created right
  now (the seat it would consume once accepted), on top of already-active members and already-
  pending invites — so the check is "would accepting this invite push us over," not "are we
  already over."

## Do not touch

- SSO/domain-based auto-join (e.g. "anyone with an `@acme.com` email is auto-added to Acme's
  org") — explicitly out of scope; v1 is invite-only per this doc. Do not add any email-domain
  matching logic anywhere in this chunk.
- `backend/app/modules/orgs/models.py`'s existing `Organization` class — read/reference only, not
  modified beyond adding the new `OrganizationInvite` class alongside it.
- `machine-2-parallel-tracks/04-rbac-admin-platform.md`'s `roles_service.py`/`roles_router.py` —
  read-only reference for the role-assignment call, not edited by this chunk.
- `post-tenancy-features/01-billing-stripe-integration.md`'s `OrganizationSubscription`
  model/table — read-only reference (see the cross-track dependency note above), not modified.
- `backend/app/auth/dependencies.py` — no changes; `require_org_member`/`OrgScopedUser` are
  reused as-is from chunk `03`, not modified.

## Verification

- Token expiry: an invite past `expires_at` is rejected by both `GET /api/orgs/invites/{token}`
  (410) and by `POST /auth/register` (falls back to normal signup with a warning, does not raise).
- Duplicate-invite-to-same-email edge case: calling `create_invite` twice for the same
  `(org_id, email)` while the first invite is still pending and unexpired returns the **same**
  invite row both times (assert on `id` equality), not two rows — add this as an explicit test,
  not just an implied side effect of the upsert logic.
- Seat-limit-exceeded returns 402: seed an `OrganizationSubscription` with `seats_included=1` and
  one existing active member, then assert the next invite attempt 402s; assert it succeeds again
  after either raising `seats_included` or the existing member being removed.
- Seat check skip: assert invite creation succeeds (no 402, regardless of member count) when no
  `OrganizationSubscription` row exists for the org at all.
- Accepting an invite sets both `User.org_id` and the correct role: register with a valid
  `invite_token`, assert the created user's `org_id` matches the invite's `org_id` and that the
  expected role was assigned (or, if `04` hasn't landed, that a warning was logged and signup
  still succeeded with the correct `org_id`).
- Invalid token falls back to normal signup without hard failure: register with a garbage/expired
  `invite_token`, assert `201 Created`, `org_id IS NULL` on the created user, and a non-empty
  `warning` in the response.
