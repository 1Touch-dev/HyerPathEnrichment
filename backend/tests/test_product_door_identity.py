"""Focused tests for the identity contract used by product doors."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
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
        assert len(login.headers.get_list("set-cookie")) == 2

        refresh = await client.post("/auth/refresh")
        assert refresh.status_code == 200
        assert len(refresh.headers.get_list("set-cookie")) == 2

        me = await client.get("/auth/me")
        assert me.status_code == 200

    login_body = login.json()
    refresh_body = refresh.json()
    me_body = me.json()

    assert set(login_body) == {"success", "data", "message", "meta"}
    assert set(login_body["data"]) == {"user", "message"}
    assert login_body["success"] is True
    assert login_body["data"]["message"] == "Login successful"
    assert set(refresh_body) == {"success", "data", "message", "meta"}
    assert set(refresh_body["data"]) == {"user", "message"}
    assert refresh_body["success"] is True
    assert refresh_body["data"]["message"] == "Token refreshed successfully"
    assert set(me_body) == {"success", "data", "message", "meta"}
    assert me_body["success"] is True

    return (
        login_body["data"]["user"],
        refresh_body["data"]["user"],
        me_body["data"],
    )


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


@pytest.mark.asyncio
async def test_migration_seeded_support_identity_across_all_auth_routes(
    db: AsyncSession,
) -> None:
    result = await db.execute(select(Role).where(Role.name == "support"))
    support_role = result.scalar_one()
    user = await _create_user(db, role=support_role)

    if db.get_bind().dialect.name == "sqlite":
        seeded_role_id = (
            await db.execute(text("SELECT id FROM roles WHERE name = 'support'"))
        ).scalar_one()
        stored_user_role_id = (
            await db.execute(
                text("SELECT role_id FROM users WHERE email = :email"),
                {"email": user.email},
            )
        ).scalar_one()
        assert "-" in seeded_role_id
        assert "-" not in stored_user_role_id

    login_user, refresh_user, me_user = await _identity_round_trip(user)
    expected_permissions = [
        {"resource": "applications", "action": "read"},
        {"resource": "audit_logs", "action": "read"},
        {"resource": "content_review", "action": "read"},
        {"resource": "documents", "action": "read"},
        {"resource": "interview_schedules", "action": "read"},
        {"resource": "job_postings", "action": "read"},
        {"resource": "job_swipe", "action": "read"},
        {"resource": "manual_job_entries", "action": "read"},
        {"resource": "outreach", "action": "read"},
        {"resource": "portfolio", "action": "read"},
        {"resource": "practice_audio", "action": "read"},
        {"resource": "questions", "action": "read"},
        {"resource": "system_health", "action": "read"},
        {"resource": "users", "action": "read"},
        {"resource": "users", "action": "suspend"},
    ]
    for identity in (login_user, refresh_user, me_user):
        assert identity["role_id"] == str(support_role.id)
        assert identity["role_name"] == "support"
        assert identity["permissions"] == expected_permissions
        assert identity["is_superuser"] is False


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
