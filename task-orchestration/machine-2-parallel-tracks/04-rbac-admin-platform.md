# Machine 2, Track 4 — RBAC Admin Platform

## Goal

Today's RBAC (`backend/app/modules/admin/models.py`'s `Role`/`Permission`/`RolePermission`, ADR
0015, already shipped) only supports **reading** roles (`GET /api/admin/roles`,
`roles_router.py`) and **assigning an existing role to a user**
(`service.py`'s `assign_role`, lines 80-111). There is no way to create a new role, create a new
permission, or attach/detach a permission from a role — every role/permission row today only
exists because a migration seeded it directly. This track builds that missing CRUD layer and
seeds two new system roles for this platform's own internal team (`team_owner`, `recruiter` —
one shared operator/staff structure, not per-tenant agency accounts), **without** requiring
`Organization`/`org_id` to exist (this track is dispatched in parallel with
`machine-1-tenancy-core` and must not depend on it landing first — see `00-overview.md`).

### Confirmed by leadership (2026-08-26)

James was asked what "account management platform" means (this doc set's own README previously
tracked this as an open question — see item 7 of its old "Open questions" list, now resolved).
His answer, quoted verbatim: **"Account management (manual employee management and ai agent
supervision, of all job applications cvs eyes)."** This has two halves:

1. **Manual employee management** — already covered by this chunk's existing role/permission CRUD
   above (creating roles, attaching permissions, seeding `team_owner`/`recruiter`). No new work
   results from this half of the answer.
2. **AI-agent supervision** — genuinely new scope this chunk did not previously cover: an
   admin-facing audit/oversight view over autonomous AI actions taken on candidates' behalf. See
   "AI-agent supervision (audit/oversight view)" below for the scoped design.

## Files to create

- `backend/app/modules/admin/roles_service.py`
- `backend/alembic/versions/047_seed_system_roles.py` (migration-number caveat: see
  `03-outreach-strategy-dimension.md`'s identical note — three tracks in this doc set want `047`;
  re-run `python -m alembic heads` before writing this file and use the real next number)
- `backend/app/modules/admin/ai_supervision_service.py` (new — see "AI-agent supervision
  (audit/oversight view)" below; kept as its own service module rather than folded into
  `roles_service.py`, since it is a read-only aggregation view over other modules' tables, not a
  role/permission mutation, and does not share `roles_service.py`'s audit-log-every-mutation
  shape)
- `backend/app/modules/admin/ai_supervision_router.py` (new — see below; kept separate from
  `roles_router.py` for the same reason, and to avoid one router file growing two unrelated
  concerns)
- `backend/app/modules/admin/ai_supervision_schemas.py` (new — response models for the
  supervision list/detail endpoints below)

## Files to edit

- `backend/app/modules/admin/roles_router.py`
- `backend/app/modules/admin/schemas.py`
- `backend/app/modules/admin/repository.py`
- `backend/app/main.py` (register `ai_supervision_router` alongside the existing admin router
  registrations — verify the exact router-inclusion pattern already used for `roles_router`
  before adding a new one)

## `backend/app/modules/admin/repository.py` — new functions

Add, next to the existing `list_roles` (line 49):

```python
async def create_role(db: AsyncSession, *, name: str, description: str | None) -> Role:
    role = Role(id=uuid4(), name=name, description=description, is_system=False)
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return role


async def create_permission(
    db: AsyncSession, *, resource: str, action: str, description: str | None
) -> Permission:
    permission = Permission(id=uuid4(), resource=resource, action=action, description=description)
    db.add(permission)
    await db.commit()
    await db.refresh(permission)
    return permission


async def attach_permission(db: AsyncSession, *, role_id: UUID, permission_id: UUID) -> None:
    db.add(RolePermission(role_id=role_id, permission_id=permission_id))
    await db.commit()


async def detach_permission(db: AsyncSession, *, role_id: UUID, permission_id: UUID) -> None:
    await db.execute(
        delete(RolePermission).where(
            RolePermission.role_id == role_id, RolePermission.permission_id == permission_id
        )
    )
    await db.commit()


async def get_role_by_id(db: AsyncSession, role_id: UUID) -> Role | None:
    result = await db.execute(
        select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id)
    )
    return result.scalar_one_or_none()
```

(Import `delete` from `sqlalchemy` at the top of the file if not already imported; confirm
exact existing import style before adding.)

## `backend/app/modules/admin/roles_service.py`

Business-logic wrapper following the exact pattern of `service.py`'s `assign_role` (audit-log
every mutation via the existing `record_admin_action`/audit helper — check `service.py`'s
`assign_role` for the exact audit call signature and reuse it identically, do not invent a
different audit-logging call):

```python
async def create_role(
    db: AsyncSession, *, actor_id: UUID, name: str, description: str | None
) -> Role:
    """Create a new (non-system) role. Cannot create is_system=True roles via this
    path — system roles only come from migrations, per Role.is_system's docstring
    intent in models.py."""
    role = await repository.create_role(db, name=name, description=description)
    await record_admin_action(
        db, actor_id=actor_id, action="role.create", target_type="role", target_id=str(role.id),
        before=None, after={"name": role.name, "description": role.description},
    )
    return role


async def attach_permission_to_role(
    db: AsyncSession, *, actor_id: UUID, role_id: UUID, permission_id: UUID
) -> None:
    role = await repository.get_role_by_id(db, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System roles' permissions cannot be modified at runtime",
        )
    await repository.attach_permission(db, role_id=role_id, permission_id=permission_id)
    await record_admin_action(
        db, actor_id=actor_id, action="role.attach_permission", target_type="role",
        target_id=str(role_id), before=None, after={"permission_id": str(permission_id)},
    )
```

Locate the exact `record_admin_action` (or equivalently-named) helper by reading `service.py`'s
`assign_role` implementation in full before writing this — match its exact call signature,
including whatever `before`/`after` shape convention it already uses; do not guess at the
signature from this doc alone.

`is_system` guard rationale: the two seeded system roles this chunk adds
(`team_owner`, `recruiter` — see migration below) must not be mutable at runtime through
this new CRUD surface, since their permission sets are a deliberate product decision, not a
per-deployment customization — mirrors how `Role.is_system`'s existing docstring already
distinguishes system roles from ad-hoc ones.

## `backend/app/modules/admin/schemas.py`

Add request models:

```python
class CreateRoleRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=1000)


class AttachPermissionRequest(BaseModel):
    permission_id: UUID
```

## `backend/app/modules/admin/roles_router.py`

Add, gated by `require_permission("roles", "write")` (new resource:action pair — see migration
below for seeding it) rather than `require_superuser_strict`, so this becomes a genuinely
delegable admin capability, not superuser-only:

```python
@router.post("", response_model=RoleWithPermissionsResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    body: CreateRoleRequest,
    user: User = Depends(require_permission("roles", "write")),
    db: AsyncSession = Depends(get_db_session),
) -> RoleWithPermissionsResponse: ...

@router.post("/{role_id}/permissions", status_code=status.HTTP_204_NO_CONTENT)
async def attach_permission(
    role_id: UUID,
    body: AttachPermissionRequest,
    user: User = Depends(require_permission("roles", "write")),
    db: AsyncSession = Depends(get_db_session),
) -> None: ...

@router.delete("/{role_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def detach_permission(
    role_id: UUID,
    permission_id: UUID,
    user: User = Depends(require_permission("roles", "write")),
    db: AsyncSession = Depends(get_db_session),
) -> None: ...
```

## Migration: `047_seed_system_roles.py`

Follow the exact seeding pattern in `046_admin_seed_module4_permissions.py` (uuid4-generated ids,
raw `op.bulk_insert`/`op.execute` inserts — read that file in full before writing this one to
copy its exact insert mechanics). Seed:

1. A new `("roles", "write")` permission (the gate this chunk's new endpoints use).
2. Two new system roles: `team_owner` (`is_system=True`, full read/write across
   `users`, `outreach`, `documents`, `portfolio`, `job_postings`, `roles`) and
   `recruiter` (`is_system=True`, read/write on `outreach`, `documents`, `portfolio`,
   `job_postings`; read-only on `users`; no `roles` access at all).
3. `RolePermission` rows wiring each role to the resource:action pairs above, reusing whichever
   `Permission` rows already exist for those resources (query for existing rows by
   `(resource, action)` before inserting a duplicate — do not assume every pair needs a fresh
   `Permission` row; most already exist from earlier admin-module migrations, only genuinely new
   pairs like `("roles", "write")` need a new row).

These two role names reflect this platform's own internal team structure (one owner-level role
plus one recruiter-staff role) — they are **not** wired to `Organization`/`org_id` in this chunk
(that table doesn't exist yet when this track is dispatched). `post-tenancy-retrofit/03-admin-
tenant-scoping.md` is responsible for later making role-based checks tenant-aware (e.g. a
`recruiter` in org A must not see org B's data even though the role itself grants
`outreach:write` globally today).

## AI-agent supervision (audit/oversight view)

**Confirmed by leadership (2026-08-26) — see the note above.** Scoped at a level consistent with
this doc set's existing scope discipline (see `10-resume-tailoring.md`'s own explicit
"ephemeral, not a new persisted document type" and "no embedding/ranking/scoring logic" cuts, and
`03-outreach-strategy-dimension.md`'s "no automated reply-tracking/tone-drift-detection system"
cut) — this is **a list of what the AI did, who/what triggered it, and a way to drill into each
one.** It is explicitly **not** a full analytics platform (no dashboards, charts, aggregate
metrics, or alerting in this chunk).

**What counts as an "autonomous AI action" for this view:**

1. Every autonomous apply — `machine-2-parallel-tracks/09-recruiter-initiated-apply-and-
   suggest.md`'s `apply_for_candidate` when the candidate's `recruiter_action_mode ==
   "autonomous"` (the branch that writes directly to `JobMatch` without a
   `PendingRecruiterAction` row).
2. Every AI-drafted outreach message — `machine-2-parallel-tracks/03-outreach-strategy-
   dimension.md`'s `request_draft()`/`generate_outreach_draft_job`, i.e. every `OutreachMessage`
   row (drafting is always AI-performed in this codebase; there is no human-authored-message path
   to exclude).
3. Every AI-generated resume tailoring — `machine-2-parallel-tracks/10-resume-tailoring.md`'s
   `request_tailoring`/`tailor_resume_job`. **Named tension, resolved pragmatically:** `10`'s own
   Goal section is explicit that tailored output is never persisted (ephemeral, RQ-result-TTL
   only, "no `TailoredResume` model, no new migration, no new table anywhere in this chunk" — a
   release-blocking invariant for that chunk, verified by its own no-persistence regression
   test). This section does **not** ask `10` to persist the generated resume text itself — doing
   so would directly contradict that chunk's own settled, tested design. Instead, this view logs
   only *that a tailoring request happened* (who, when, target company/role), not the generated
   content — an admin auditing this row can see a tailoring event occurred but not "read back" the
   ephemeral output after its RQ TTL expires, which is a known, accepted limitation of this
   design, not an oversight.

**New table**, added by this chunk's migration (alongside the `roles`/`permissions`
seed — verify real next Alembic head, same caveat as `047_seed_system_roles.py` above):

```python
class AiActionAuditLog(Base):
    """Read-only audit trail of autonomous AI actions, for admin oversight (machine-2/04,
    confirmed by leadership 2026-08-26: "ai agent supervision, of all job applications
    cvs eyes"). Rows are written by the acting module itself at the point the action
    executes (see cross-references in 09/10/outreach's own files), never backfilled or
    reconstructed after the fact."""

    __tablename__ = "ai_action_audit_log"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    action_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # "autonomous_apply" | "outreach_draft" | "resume_tailoring"
    candidate_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # The recruiter whose action_mode/request triggered this (may be NULL for a
    # candidate-initiated action, e.g. the candidate's own resume-tailoring request
    # has no recruiter in the loop at all).
    triggered_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Loose FK-by-convention (no DB-level FK constraint, mirroring this module's
    # existing cross-module reference style for recruiter_actions/outreach ids) to
    # whichever row the acting module created for this event — a JobMatch.id for
    # autonomous_apply, an OutreachMessage.id for outreach_draft, or None for
    # resume_tailoring (nothing is persisted to point at, per the tension noted above).
    related_id: Mapped[UUID | None] = mapped_column(nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)  # short, human-readable
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
```

**Endpoints** (`ai_supervision_router.py`, gated by a new permission
`("ai_supervision", "read")` — seeded alongside `("roles", "write")` in this chunk's migration):

```
GET /api/admin/ai-actions              -> list, filterable by ?candidate_id=&recruiter_id=
                                           &action_type=&since=&until= (all optional; an admin
                                           may combine any subset)
GET /api/admin/ai-actions/{id}         -> drill into one action's full record
```

**Write-path (cross-referenced, not built in this chunk's own module).** This chunk does not
itself generate `AiActionAuditLog` rows — it only defines the table, the read endpoints, and the
permission gate. Each acting module writes its own row at the point the action executes:

- `machine-2-parallel-tracks/09-recruiter-initiated-apply-and-suggest.md`'s
  `apply_for_candidate` (autonomous branch only — the `approval_required` branch's
  `PendingRecruiterAction` is not itself an "AI action" yet; it becomes one, if desired, only once
  actually applied) must insert an `AiActionAuditLog` row (`action_type="autonomous_apply"`,
  `related_id=job_match_id`) immediately after writing `JobMatch.application_status`/`applied_at`.
- `machine-2-parallel-tracks/03-outreach-strategy-dimension.md`'s `generate_outreach_draft_job`
  must insert a row (`action_type="outreach_draft"`, `related_id=OutreachMessage.id`) after
  creating the drafted `OutreachMessage`.
- `machine-2-parallel-tracks/10-resume-tailoring.md`'s `tailor_resume_job` must insert a row
  (`action_type="resume_tailoring"`, `related_id=None`, `summary` carrying just
  `target_company`/`target_role` as text) after generating (not persisting) the tailored result.

Each of those three files gets a small cross-reference note (see this chunk's own "Do not touch"
below for the corollary: this chunk's PR does **not** itself edit `09`/`03`/`10`'s files to add
the write calls — that is each of those chunks' own follow-up, flagged here as a dependency this
chunk's PR description must call out explicitly, since `04` may land before or after `09`/`10` per
the README's merge-order notes, and either ordering is fine as long as the write calls land before
this chunk's endpoints are considered functionally complete).

## Do not touch

- `backend/app/modules/admin/models.py` — no changes to the existing `Role`/`Permission`/
  `RolePermission` schema itself (this chunk only adds rows to those tables via migration and new
  service/router functions). `AiActionAuditLog` is a genuinely new table, per "AI-agent
  supervision" above — add it to `models.py` (or a new `ai_supervision_models.py` alongside the
  new service/router/schemas files, implementer's choice, document whichever is picked) rather
  than reading this bullet as "no new tables at all in this chunk."
- `backend/app/modules/admin/service.py`'s existing `assign_role` — read for the audit-call
  pattern, not edited.
- Do not create `backend/app/modules/orgs/` — that module does not exist yet for this track (see
  Goal section); do not reference `Organization` anywhere in this chunk's code.
- `backend/app/modules/admin/permissions.py` — `require_permission`/`user_has_permission` are
  reused as-is, not modified.
- Do not build a full analytics platform for AI-agent supervision — no dashboards, charts,
  aggregate metrics/rates, or alerting in this chunk. See "AI-agent supervision (audit/oversight
  view)" above for the explicit scope ceiling ("a list ... and a way to drill into each one").
- Do not ask `10-resume-tailoring.md` to persist tailored-resume output to satisfy this chunk's
  audit trail — that would contradict `10`'s own settled, tested "never persisted" design; log
  only that the event happened, per the named tension above.
- This chunk's own PR does not edit `09-recruiter-initiated-apply-and-suggest.md`,
  `03-outreach-strategy-dimension.md`, or `10-resume-tailoring.md`'s files to add the
  `AiActionAuditLog` write calls — those are each file's own follow-up (see "Write-path" above);
  this chunk only builds the table, the read endpoints, and the permission gate.

## Verification

- Add tests for `roles_service.create_role`, `attach_permission_to_role`,
  `detach_permission_from_role` covering: happy path, 404 on unknown role, 403 on
  `is_system=True` role mutation attempt.
- Add a router-level test asserting `POST /api/admin/roles` 403s for a user lacking
  `roles:write` and 201s for one with it (or `is_superuser=True`, per `user_has_permission`'s
  existing superuser short-circuit).
- Run `python backend/scripts/verify_adrs.py`-equivalent migration check:
  `python -m alembic upgrade head` then `python -m alembic downgrade -1` then `upgrade head`
  again, confirming the seed migration's downgrade correctly removes only the rows it added
  (not any pre-existing `Permission` rows it merely referenced).
- Add tests for the AI-agent supervision endpoints: `GET /api/admin/ai-actions` 403s for a caller
  lacking `ai_supervision:read`; returns rows filtered correctly by each of
  `candidate_id`/`recruiter_id`/`action_type`/`since`/`until`, individually and combined; `GET
  /api/admin/ai-actions/{id}` 404s for an unknown id and returns the full row for a known one.
- Add a test seeding one `AiActionAuditLog` row per `action_type`
  (`"autonomous_apply"`/`"outreach_draft"`/`"resume_tailoring"`) and asserting the list endpoint
  returns all three with correct `action_type` values (this chunk tests the read surface against
  directly-seeded rows — it does not need to exercise `09`/`03`/`10`'s actual write-call code
  paths, since those calls are each of those chunks' own follow-up per "Write-path" above; a
  reviewer/tester for `09`/`03`/`10` should separately confirm each of those chunks' write calls
  land correctly once implemented).


## Frontend

**A read-only roles page already exists** — `frontend/app/app/admin/roles/page.tsx` (verified
against the real current tree). It calls `fetchRoles()` (`frontend/features/admin/api/client.ts`)
via `useQuery`, and renders each `Role` as a `Card` with its name, an "System" badge when
`isSystem`, and its `permissions` as a flat list of `resource:action` badges — read-only display,
no create/edit/attach controls of any kind. This chunk's frontend work is therefore **additive to
this existing page, not a new page**: add create-role/attach-permission UI controls to it, per
this chunk's own new backend endpoints (`POST /api/admin/roles`,
`POST/DELETE /api/admin/roles/{role_id}/permissions[/{permission_id}]`).

- Edit `frontend/app/app/admin/roles/page.tsx`: add a "Create role" button (top of the page,
  alongside the `<h1>`) opening a dialog with `name`/`description` fields, following the exact
  `Dialog`/`DialogContent`/`DialogFooter` composition pattern already used in
  `frontend/features/outreach/components/DraftOutreachDialog.tsx` (this codebase's established
  dialog-form idiom) rather than inventing a new modal pattern. On submit, call a new
  `createRole(body)` function (added to `frontend/features/admin/api/client.ts`, next to the
  existing `fetchRoles`) hitting `POST /api/admin/roles`, then invalidate `adminKeys.roles()` so
  the list refetches (mirrors `useDraftOutreach`'s existing `onSuccess: () =>
  queryClient.invalidateQueries(...)` pattern).
- For each non-system role's `Card` (`role.isSystem` false — system roles' permissions cannot be
  modified per this chunk's own `403` guard, so do not show attach/detach controls for
  `is_system=True` roles at all, not even disabled ones — the backend already 403s the attempt,
  but hiding the control entirely is a better UX than letting a user click into a guaranteed
  error), add an "Attach permission" control (a `<Select>` of available permissions not already
  attached, plus an "Add" button) and a small "×" remove affordance on each existing permission
  badge, wired to new `attachPermission(roleId, permissionId)`/`detachPermission(roleId,
  permissionId)` client functions calling this chunk's new endpoints.
- New client functions live in the same `frontend/features/admin/api/client.ts` file as the
  existing `fetchRoles`, following that file's existing fetch-wrapper conventions (check its
  current error-handling/envelope-unwrapping pattern and match it, rather than introducing a
  second HTTP-calling style in the same file).
- No new route/page file — `frontend/app/app/admin/roles/page.tsx` itself is edited in place.
