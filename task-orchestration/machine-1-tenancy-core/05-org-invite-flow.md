# Machine 1, Chunk 5 — Staff Invite Flow

## Depends on

Soft dependency on `machine-2-parallel-tracks/04-rbac-admin-platform.md`'s `team_owner`/
`recruiter` system roles (renamed from `agency_owner`/`agency_recruiter` — see that chunk; roles
are seeded by its migration) — **do not block on `04` landing first**, same "do not block"
pattern `machine-2-parallel-tracks/06-linkedin-outreach-send.md` already uses for its own soft
dependency on `04`'s RBAC CRUD surface. If `04` has not merged yet at implementation time, the
`role_name` field on an invite is still stored (a plain string), it just cannot be validated
against a real `Role` row yet — validate against `Role.name` existing in `admin_roles` only when
that table already has rows for `team_owner`/`recruiter`/`intern`; otherwise accept the string
as-is and let acceptance fail at role-assignment time with a clear error, rather than blocking
invite creation on a track this chunk does not own.

No dependency on `Brand`, `02-schema-and-migration.md`, or any brand/org concept at all — staff
onboarding in this model is not scoped to a storefront. A recruiter or intern invited through this
flow can immediately work the entire shared candidate pool, regardless of which brand(s) exist or
which one (if any) is mentioned in the invite email's copy.

## Ground truth (verified 2026-08-22, corrects the informal "POST /api/auth/signup" framing)

The actual signup endpoint is `backend/app/auth/router.py`'s `register()` function, mounted at
`POST /auth/register` (router prefix `/auth`, see `router = APIRouter(prefix="/auth", ...)` at
line 49), not `/api/auth/signup`. It takes `UserCreate` (`backend/app/auth/schemas.py` lines
36-42: `email`, `password`, `first_name`, `last_name` — no `invite_token` field today). This
chunk edits that real endpoint/schema; any reference elsewhere in this doc set to
"`POST /api/auth/signup`" should be read as this actual route.

## Files to create

- `backend/app/modules/staff_invites/__init__.py`
- `backend/app/modules/staff_invites/models.py`
- `backend/app/modules/staff_invites/schemas.py`
- `backend/app/modules/staff_invites/repository.py`
- `backend/app/modules/staff_invites/router.py`
- `backend/alembic/versions/048_staff_invites.py` (migration-number caveat: this doc set already
  has several tracks wanting `047` — `machine-1/02`, `machine-2/02`, `machine-2/03`,
  `machine-2/04` — and `machine-1/02` now owns `047` outright (see that chunk). **Re-run
  `python -m alembic heads` from `backend/` immediately before writing this migration** and use
  the real next number and real `down_revision` — do not assume `048` is free.)

## Files to edit

- `backend/app/auth/router.py`
- `backend/app/auth/schemas.py`

## `backend/app/modules/staff_invites/models.py` — `StaffInvite`

This is a standalone module, not part of the old `orgs`/new `brands` module — a staff invite has
no organizational container to belong to, so there is no natural home for it inside `brands`.

```python
"""ORM model for staff (recruiter/intern) onboarding invites. See
machine-1-tenancy-core/05-org-invite-flow.md for the accept/expiry rules that govern
this table. Unlike the superseded org-invite design, there is no seat/org membership
concept here at all — an accepted invite just gets a role assigned on the one shared
users table, nothing more."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class StaffInvite(Base):
    """A pending invitation for an email address to join as staff (recruiter/intern/
    team_owner) with a specific role. No org/brand association — see this chunk's
    file for why."""

    __tablename__ = "staff_invites"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # secrets.token_urlsafe(32): cryptographically random, URL-safe, ~43 chars — not
    # a sequential id or anything derivable from email, since this token is the
    # entire bearer-credential for GET /api/staff-invites/{token} (public,
    # unauthenticated) and for redeeming staff status at signup.
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    # The role to assign on acceptance. References Role.name from
    # machine-2-parallel-tracks/04-rbac-admin-platform.md's seeded team_owner/
    # recruiter rows (and, once machine-2-parallel-tracks/12-linkedin-sourcing-
    # intern-multilogin.md lands, an intern role) — stored as a plain string, not a
    # FK to admin_roles.id, because this module does not import from the admin
    # module and because 04 may not have landed yet when this chunk is implemented
    # (same "do not block on 04" pattern chunk 06 already uses).
    role_name: Mapped[str] = mapped_column(String(64), nullable=False, default="recruiter")
    invited_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # 7 days, matching common B2B SaaS invite-expiry convention (long enough to
    # survive a slow-to-respond invitee's weekend, short enough that a stale invite
    # doesn't sit around indefinitely).
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

`invited_by`'s FK uses `ondelete="SET NULL"` — deleting the inviting user's account must not
cascade-delete a still-pending invite for someone else; the invite should survive with
`invited_by=None` and remain acceptable.

## `backend/app/modules/staff_invites/schemas.py`

```python
class StaffInviteCreate(BaseModel):
    email: EmailStr
    role_name: str = Field(default="recruiter", max_length=64)


class StaffInviteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    role_name: str
    expires_at: datetime
    accepted_at: datetime | None


class PublicStaffInviteResponse(BaseModel):
    """Response for GET /api/staff-invites/{token} — unauthenticated, so this must
    leak nothing beyond what a pending-signup UI genuinely needs to display."""

    invited_by_name: str | None
    role_name: str
    email: str
    expires_at: datetime
```

## `backend/app/modules/staff_invites/repository.py`

```python
async def get_invite_by_token(db: AsyncSession, token: str) -> StaffInvite | None: ...

async def get_pending_invite_for_email(db: AsyncSession, email: str) -> StaffInvite | None:
    """Pending (accepted_at IS NULL) and unexpired invite for this email, if any.
    Backs the resend-upsert edge case below — do not create a second row for the
    same still-pending, unexpired email."""
    ...

async def create_invite(
    db: AsyncSession, *, email: str, role_name: str, invited_by: UUID
) -> StaffInvite:
    invite = StaffInvite(
        id=uuid4(), email=email, role_name=role_name,
        invited_by=invited_by, token=secrets.token_urlsafe(32),
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return invite
```

No `count_active_members`/`count_pending_invites`-style functions exist in this rewrite — the
superseded design's per-org seat counting has no equivalent here. There is no seat ceiling of any
kind on staff onboarding; anyone with `("users", "write")` permission can invite as many staff as
they want.

## `backend/app/modules/staff_invites/router.py`

```python
router = APIRouter(prefix="/api", tags=["staff-invites"])


@router.post(
    "/staff-invites",
    response_model=StaffInviteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invite(
    body: StaffInviteCreate,
    user: User = Depends(require_permission("users", "write")),  # reuse existing admin permission pattern (04-rbac-admin-platform.md)
    db: AsyncSession = Depends(get_db_session),
) -> StaffInviteResponse:
    # Resend-upsert edge case: reuse a still-pending, unexpired invite for the same
    # email instead of creating a duplicate row.
    existing = await repository.get_pending_invite_for_email(db, body.email)
    if existing:
        return StaffInviteResponse.model_validate(existing)

    invite = await repository.create_invite(
        db, email=body.email, role_name=body.role_name, invited_by=user.id,
    )
    return StaffInviteResponse.model_validate(invite)


@router.get("/staff-invites/{token}", response_model=PublicStaffInviteResponse)
async def get_invite(token: str, db: AsyncSession = Depends(get_db_session)) -> PublicStaffInviteResponse:
    invite = await repository.get_invite_by_token(db, token)
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
    if invite.accepted_at is not None:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invite already accepted")
    if invite.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invite has expired")
    inviter = await auth_repository.get_user_by_id(db, invite.invited_by) if invite.invited_by else None
    return PublicStaffInviteResponse(
        invited_by_name=f"{inviter.first_name} {inviter.last_name}" if inviter else None,
        role_name=invite.role_name,
        email=invite.email,
        expires_at=invite.expires_at,
    )
```

Use `404` for "no such token" and `410 Gone` for "existed but is now unusable" (expired or
accepted) — distinct from a plain 404 so a pending-signup UI can show "this invite already used"
rather than "invite not found," a materially different message for the invitee. Register this
router the same way every other module's router is registered in `backend/app/main.py` (find the
existing `app.include_router(...)` block and follow its exact pattern).

## `POST /auth/register` edit (the real endpoint — see "Ground truth" above)

Add `invite_token: str | None = None` to `UserCreate` (`backend/app/auth/schemas.py`).

In `register()` (`backend/app/auth/router.py`, current body at lines 127-183), after the
existing "email already registered" check and before `db.add(user)`, add invite resolution:

```python
    invite: StaffInvite | None = None
    invite_warning: str | None = None
    if user_data.invite_token:
        invite = await staff_invites_repository.get_invite_by_token(db, user_data.invite_token)
        if invite is None or invite.accepted_at is not None or invite.expires_at < datetime.now(UTC):
            # Ambiguities resolved: an invalid/expired token does NOT hard-fail
            # signup — the user still gets a normal candidate account, and the
            # response carries a warning instead. A dead invite link should not be
            # a dead-end for someone who was genuinely trying to sign up; staff
            # status can always be granted later by an admin action, but losing the
            # signup entirely over a stale link is a worse user experience than a
            # degraded one.
            invite = None
            invite_warning = "Your invite link is invalid or has expired; your account was created without staff access."
```

Unlike the superseded design, accepting a valid invite does **not** set anything on the `User`
row at signup time beyond the normal fields — there is no `org_id` to assign, since staff and
candidates are the same `users` table with no organizational partition. After `db.add(user)` /
`await db.commit()` / `await db.refresh(user)` (existing lines 156-158), if `invite` is not
`None`: assign the role (call whichever role-assignment function
`machine-2-parallel-tracks/04-rbac-admin-platform.md`'s `roles_service.py` exposes, e.g.
`assign_role(db, actor_id=invite.invited_by, user_id=user.id, role_name=invite.role_name)` — if
`04` has not landed yet at implementation time, skip role assignment and log a warning instead of
raising, consistent with the "do not block on `04`" dependency posture above), and set
`invite.accepted_at = datetime.now(UTC)` then `await db.commit()`.

`MessageResponse` (the existing return type) does not currently carry a warning field — extend
it (or introduce a sibling response, e.g. `RegisterResponse(MessageResponse)` with an optional
`warning: str | None = None` field) to surface `invite_warning` to the caller without breaking
existing callers that only read `.message`. Document which approach was taken in the PR
description; either is acceptable as long as `invite_warning is None` produces byte-identical
JSON to today's `MessageResponse` (regression safety for existing signup clients).

## Ambiguities resolved

- **Invalid/expired invite token: hard-fail signup, or fall back to normal signup?** Fall back
  (see code block above) — decided explicitly, not left as an implementer's choice. A broken
  invite link must not block account creation entirely.
- **Resending an invite to the same still-pending, unexpired email:** upsert (return the existing
  row, do not create a second one) — see `get_pending_invite_for_email` above. A resend to an
  *expired* or *already-accepted* invite's email address, by contrast, *does* create a new row
  (the old one is functionally dead and does not block a fresh invite).
- **Is there any seat limit, plan-tier gate, or billing check on staff invites?** No — this is the
  single biggest simplification versus the superseded design. Billing in this product is
  candidate-level (`UserSubscription`, per `post-tenancy-features/01-billing-stripe-
  integration.md`), not staff-seat-level, so there is nothing for staff invitation to check
  against. Any staff member with `("users", "write")` permission can invite as many recruiters or
  interns as the business needs.
- **What role does an invite default to?** `recruiter` — the common case. `team_owner` and
  `intern` (once `machine-2-parallel-tracks/12-linkedin-sourcing-intern-multilogin.md` seeds that
  role) are set explicitly via `role_name` on invite creation.

## Do not touch

- SSO/domain-based auto-join (e.g. "anyone with an `@acme.com` email is auto-added as staff") —
  explicitly out of scope; v1 is invite-only per this doc. Do not add any email-domain matching
  logic anywhere in this chunk.
- Any seat count, plan tier, or billing lookup — there is no seat concept in this design at all;
  do not reintroduce one.
- `backend/app/modules/brands/`'s `Brand` model — not referenced, not modified by this chunk.
- `machine-2-parallel-tracks/04-rbac-admin-platform.md`'s `roles_service.py`/`roles_router.py` —
  read-only reference for the role-assignment call, not edited by this chunk.
- `backend/app/auth/dependencies.py` — no changes; this chunk introduces no new auth dependency.

## Verification

- Token expiry: an invite past `expires_at` is rejected by both `GET /api/staff-invites/{token}`
  (410) and by `POST /auth/register` (falls back to normal signup with a warning, does not raise).
- Duplicate-invite-to-same-email edge case: calling `create_invite` twice for the same email while
  the first invite is still pending and unexpired returns the **same** invite row both times
  (assert on `id` equality), not two rows — add this as an explicit test, not just an implied side
  effect of the upsert logic.
- Accepting an invite assigns the correct role: register with a valid `invite_token`, assert the
  expected role was assigned to the created user (or, if `04` hasn't landed, that a warning was
  logged and signup still succeeded).
- Invalid token falls back to normal signup without hard failure: register with a garbage/expired
  `invite_token`, assert `201 Created` and a non-empty `warning` in the response.
- No seat/billing check exists anywhere in this flow: assert invite creation and acceptance both
  succeed regardless of how many staff already exist or whether any `UserSubscription` row exists
  for anyone — there is nothing in this chunk's code that could even perform such a check.
