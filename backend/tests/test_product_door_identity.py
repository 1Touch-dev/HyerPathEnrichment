"""Focused tests for the identity contract used by product doors."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user_from_cookie, require_verified_user
from app.auth.models import User
from app.auth.password import hash_password
from app.main import app
from app.modules.admin.models import Permission, Role, RolePermission

PASSWORD = "SecurePass123!"
IDENTITY_FIELDS = ("role_id", "role_name", "permissions", "is_superuser")


@pytest.fixture(autouse=True)
def _use_real_cookie_auth() -> None:
    app.dependency_overrides.pop(get_current_user_from_cookie, None)
    app.dependency_overrides.pop(require_verified_user, None)
    yield


async def _create_user(
    db: AsyncSession,
    *,
    role: Role | None = None,
    is_superuser: bool = False,
) -> User:
    user = User(
        email=f"product-door-{uuid4().hex}@example.com",
        hashed_password=hash_password(PASSWORD),
        first_name="Product",
        last_name="Door",
        is_verified=True,
        is_active=True,
        is_superuser=is_superuser,
        role_id=role.id if role is not None else None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _identity_round_trip(user: User) -> tuple[dict, dict, dict]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post(
            "/auth/login",
            json={"email": user.email, "password": PASSWORD},
        )
        assert login.status_code == 200

        refresh = await client.post("/auth/refresh")
        assert refresh.status_code == 200

        me = await client.get("/auth/me")
        assert me.status_code == 200

    return login.json()["user"], refresh.json()["user"], me.json()


@pytest.mark.asyncio
async def test_login_refresh_and_me_return_identical_stable_role_identity(
    db: AsyncSession,
) -> None:
    suffix = uuid4().hex
    role = Role(name=f"identity-role-{suffix}", description="Identity test role")
    permissions = [
        Permission(resource=f"z-resource-{suffix}", action="write"),
        Permission(resource=f"a-resource-{suffix}", action="read"),
    ]
    db.add_all([role, *permissions])
    await db.flush()
    db.add_all(
        [RolePermission(role_id=role.id, permission_id=permission.id) for permission in permissions]
    )
    await db.commit()

    user = await _create_user(db, role=role)
    login_user, refresh_user, me_user = await _identity_round_trip(user)

    expected_permissions = [
        {"resource": f"a-resource-{suffix}", "action": "read"},
        {"resource": f"z-resource-{suffix}", "action": "write"},
    ]
    for identity in (login_user, refresh_user, me_user):
        assert identity["role_id"] == str(role.id)
        assert identity["role_name"] == role.name
        assert identity["permissions"] == expected_permissions
        assert len(identity["permissions"]) == len(
            {(item["resource"], item["action"]) for item in identity["permissions"]}
        )

    assert {field: login_user[field] for field in IDENTITY_FIELDS} == {
        field: refresh_user[field] for field in IDENTITY_FIELDS
    }
    assert {field: login_user[field] for field in IDENTITY_FIELDS} == {
        field: me_user[field] for field in IDENTITY_FIELDS
    }


@pytest.mark.parametrize("is_superuser", [False, True])
@pytest.mark.asyncio
async def test_roleless_identity_is_empty_and_preserves_superuser(
    db: AsyncSession,
    is_superuser: bool,
) -> None:
    user = await _create_user(db, is_superuser=is_superuser)
    login_user, refresh_user, me_user = await _identity_round_trip(user)

    for identity in (login_user, refresh_user, me_user):
        assert identity["role_id"] is None
        assert identity["role_name"] is None
        assert identity["permissions"] == []
        assert identity["is_superuser"] is is_superuser
