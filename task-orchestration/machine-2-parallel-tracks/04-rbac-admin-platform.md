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

## Files to create

- `backend/app/modules/admin/roles_service.py`
- `backend/alembic/versions/047_seed_system_roles.py` (migration-number caveat: see
  `03-outreach-strategy-dimension.md`'s identical note — three tracks in this doc set want `047`;
  re-run `python -m alembic heads` before writing this file and use the real next number)

## Files to edit

- `backend/app/modules/admin/roles_router.py`
- `backend/app/modules/admin/schemas.py`
- `backend/app/modules/admin/repository.py`

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

## Do not touch

- `backend/app/modules/admin/models.py` — no new columns/tables; this chunk only adds rows via
  migration and new service/router functions, it does not change the `Role`/`Permission`/
  `RolePermission` schema itself.
- `backend/app/modules/admin/service.py`'s existing `assign_role` — read for the audit-call
  pattern, not edited.
- Do not create `backend/app/modules/orgs/` — that module does not exist yet for this track (see
  Goal section); do not reference `Organization` anywhere in this chunk's code.
- `backend/app/modules/admin/permissions.py` — `require_permission`/`user_has_permission` are
  reused as-is, not modified.

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
