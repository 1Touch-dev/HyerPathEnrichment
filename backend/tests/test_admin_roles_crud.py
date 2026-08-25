"""Role/permission CRUD: roles_service.create_role/attach_permission_to_role/
detach_permission_from_role, and the new POST /api/admin/roles router
endpoint gated by require_permission("roles", "write")
(machine-2-parallel-tracks/04-rbac-admin-platform.md)."""

from __future__ import annotations

import pytest

from tests.envelope_helpers import assert_error, assert_success

pytestmark = pytest.mark.asyncio


async def test_create_role_happy_path(db_session, superuser):
    from app.modules.admin import roles_service

    role = await roles_service.create_role(
        db_session, actor_id=superuser.id, name="test-role", description="a test role"
    )
    assert role.id is not None
    assert role.name == "test-role"
    assert role.description == "a test role"
    assert role.is_system is False


async def test_create_role_writes_audit_log(db_session, superuser):
    from sqlalchemy import select

    from app.modules.admin import roles_service
    from app.modules.admin.models import AdminAuditLog

    role = await roles_service.create_role(
        db_session, actor_id=superuser.id, name="audited-role", description=None
    )

    result = await db_session.execute(
        select(AdminAuditLog).where(
            AdminAuditLog.action == "role.create", AdminAuditLog.target_id == str(role.id)
        )
    )
    entry = result.scalar_one()
    assert entry.after["name"] == "audited-role"


async def test_attach_permission_to_role_happy_path(db_session, superuser):
    from app.modules.admin import repository, roles_service

    role = await repository.create_role(db_session, name="attach-target", description=None)
    permission = await repository.create_permission(
        db_session, resource="widgets", action="read", description=None
    )

    await roles_service.attach_permission_to_role(
        db_session, actor_id=superuser.id, role_id=role.id, permission_id=permission.id
    )

    refreshed = await repository.get_role_by_id(db_session, role.id)
    assert {p.id for p in refreshed.permissions} == {permission.id}


async def test_attach_permission_to_role_404_on_unknown_role(db_session, superuser):
    from uuid import uuid4

    from fastapi import HTTPException

    from app.modules.admin import repository, roles_service

    permission = await repository.create_permission(
        db_session, resource="widgets", action="write", description=None
    )

    with pytest.raises(HTTPException) as exc:
        await roles_service.attach_permission_to_role(
            db_session, actor_id=superuser.id, role_id=uuid4(), permission_id=permission.id
        )
    assert exc.value.status_code == 404


async def test_attach_permission_to_role_403_on_system_role(db_session, superuser):
    from uuid import uuid4

    from fastapi import HTTPException

    from app.modules.admin import repository, roles_service
    from app.modules.admin.models import Role

    system_role = Role(id=uuid4(), name="system-role-for-test", is_system=True)
    db_session.add(system_role)
    await db_session.commit()
    permission = await repository.create_permission(
        db_session, resource="widgets", action="moderate", description=None
    )

    with pytest.raises(HTTPException) as exc:
        await roles_service.attach_permission_to_role(
            db_session,
            actor_id=superuser.id,
            role_id=system_role.id,
            permission_id=permission.id,
        )
    assert exc.value.status_code == 403


async def test_detach_permission_from_role_happy_path(db_session, superuser):
    from app.modules.admin import repository, roles_service

    role = await repository.create_role(db_session, name="detach-target", description=None)
    permission = await repository.create_permission(
        db_session, resource="widgets", action="delete", description=None
    )
    await roles_service.attach_permission_to_role(
        db_session, actor_id=superuser.id, role_id=role.id, permission_id=permission.id
    )

    await roles_service.detach_permission_from_role(
        db_session, actor_id=superuser.id, role_id=role.id, permission_id=permission.id
    )

    refreshed = await repository.get_role_by_id(db_session, role.id)
    assert refreshed.permissions == []


async def test_detach_permission_from_role_404_on_unknown_role(db_session, superuser):
    from uuid import uuid4

    from fastapi import HTTPException

    from app.modules.admin import roles_service

    with pytest.raises(HTTPException) as exc:
        await roles_service.detach_permission_from_role(
            db_session, actor_id=superuser.id, role_id=uuid4(), permission_id=uuid4()
        )
    assert exc.value.status_code == 404


async def test_detach_permission_from_role_403_on_system_role(db_session, superuser):
    from uuid import uuid4

    from fastapi import HTTPException

    from app.modules.admin import roles_service
    from app.modules.admin.models import Role

    system_role = Role(id=uuid4(), name="system-role-for-detach-test", is_system=True)
    db_session.add(system_role)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await roles_service.detach_permission_from_role(
            db_session, actor_id=superuser.id, role_id=system_role.id, permission_id=uuid4()
        )
    assert exc.value.status_code == 403


async def test_create_role_router_requires_roles_write_permission(
    client, regular_user, auth_headers
):
    response = client.post(
        "/api/admin/roles",
        json={"name": "should-not-be-created", "description": None},
        headers=auth_headers(regular_user.id),
    )
    assert_error(response, 403)


async def test_create_role_router_succeeds_for_superuser(client, superuser, auth_headers):
    response = client.post(
        "/api/admin/roles",
        json={"name": "router-created-role", "description": "created via API"},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response, status=201)
    assert body["name"] == "router-created-role"
    assert body["is_system"] is False
    assert body["permissions"] == []
