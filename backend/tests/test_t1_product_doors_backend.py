"""Independent T1 HTTP checks for auth cookies, errors, and impersonation."""

from __future__ import annotations

from datetime import UTC, datetime
from http.cookies import SimpleCookie
from uuid import uuid4

import pyotp
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user_from_cookie, require_verified_user
from app.auth.jwt_tokens import decode_access_token
from app.auth.models import User
from app.auth.password import hash_password
from app.core.config import get_settings
from app.main import app

PASSWORD = "SecurePass123!"


@pytest.fixture(autouse=True)
def _use_real_cookie_auth() -> None:
    app.dependency_overrides.pop(get_current_user_from_cookie, None)
    app.dependency_overrides.pop(require_verified_user, None)
    yield


async def _create_user(db: AsyncSession, **overrides: object) -> User:
    user_id = uuid4()
    values: dict[str, object] = {
        "id": user_id,
        "email": f"t1-{user_id.hex}@example.com",
        "hashed_password": hash_password(PASSWORD),
        "first_name": "T1",
        "last_name": "User",
        "is_active": True,
        "is_verified": True,
    }
    values.update(overrides)
    user = User(**values)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _response_cookies(response) -> dict[str, object]:
    parsed: dict[str, object] = {}
    for header in response.headers.get_list("set-cookie"):
        cookie = SimpleCookie()
        cookie.load(header)
        parsed.update(cookie)
    return parsed


def _assert_auth_cookies(response) -> tuple[str, str]:
    cookies = _response_cookies(response)
    assert set(cookies) == {"access_token", "refresh_token"}

    access = cookies["access_token"]
    refresh = cookies["refresh_token"]
    assert access["httponly"] is True
    assert access["path"] == "/"
    assert access["samesite"].lower() == "lax"
    assert refresh["httponly"] is True
    assert refresh["path"] == "/"
    assert refresh["samesite"].lower() == "strict"
    return access.value, refresh.value


@pytest.mark.asyncio
async def test_login_and_refresh_issue_both_scoped_auth_cookies(db: AsyncSession) -> None:
    user = await _create_user(db)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post(
            "/auth/login",
            json={"email": user.email, "password": PASSWORD},
        )
        assert login.status_code == 200
        login_access, login_refresh = _assert_auth_cookies(login)

        refresh = await client.post("/auth/refresh")
        assert refresh.status_code == 200
        refresh_access, refresh_refresh = _assert_auth_cookies(refresh)

    assert refresh_access != login_access
    assert refresh_refresh != login_refresh


@pytest.mark.asyncio
async def test_staff_and_permission_denials_have_exact_structured_403s(
    db: AsyncSession,
) -> None:
    candidate = await _create_user(db)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post(
            "/auth/login",
            json={"email": candidate.email, "password": PASSWORD},
        )
        assert login.status_code == 200

        staff_denial = await client.get("/enrich")
        permission_denial = await client.post(
            f"/api/admin/impersonation/start/{uuid4()}",
            json={"reason": "T1 authorization check", "mfa_code": None},
        )

    assert staff_denial.status_code == 403
    assert staff_denial.json() == {
        "success": False,
        "error": {
            "code": "FORBIDDEN",
            "message": "Staff access required",
            "details": None,
            "status_code": 403,
        },
        "meta": None,
    }
    assert permission_denial.status_code == 403
    assert permission_denial.json() == {
        "success": False,
        "error": {
            "code": "FORBIDDEN",
            "message": "Missing permission: impersonation:start",
            "details": None,
            "status_code": 403,
        },
        "meta": None,
    }


@pytest.mark.asyncio
async def test_impersonation_start_status_end_http_lifecycle(db: AsyncSession) -> None:
    secret = pyotp.random_base32()
    admin = await _create_user(
        db,
        is_superuser=True,
        mfa_enabled=True,
        mfa_secret=secret,
        mfa_enrolled_at=datetime.now(UTC),
    )
    candidate = await _create_user(db)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post(
            "/auth/login",
            json={"email": admin.email, "password": PASSWORD},
        )
        assert login.status_code == 200

        start = await client.post(
            f"/api/admin/impersonation/start/{candidate.id}",
            json={
                "reason": "T1 impersonation lifecycle",
                "mfa_code": pyotp.TOTP(secret).now(),
            },
            headers={"Idempotency-Key": "t1-impersonation-start"},
        )
        assert start.status_code == 200
        assert start.json()["data"]["target_user_id"] == str(candidate.id)
        assert "access_token" in _response_cookies(start)

        status = await client.get("/api/admin/impersonation/status")
        assert status.status_code == 200
        assert status.json()["data"] == {
            "is_impersonating": True,
            "admin_user_id": str(admin.id),
            "admin_email": admin.email,
            "target_user_id": str(candidate.id),
            "expires_at": status.json()["data"]["expires_at"],
        }

        end = await client.post(
            "/api/admin/impersonation/end",
            headers={"Idempotency-Key": "t1-impersonation-end"},
        )
        assert end.status_code == 204
        assert end.content == b""

        restored_access = _response_cookies(end)["access_token"].value
        assert restored_access
        restored_claims = decode_access_token(restored_access, get_settings().SECRET_KEY)
        assert restored_claims["sub"] == str(admin.id)
        assert restored_claims["email"] == admin.email
        assert restored_claims["jti"]
        assert restored_claims["exp"] > restored_claims["iat"]
        assert "imp" not in restored_claims

        ended_status = await client.get("/api/admin/impersonation/status")
        assert ended_status.status_code == 200
        assert ended_status.json()["data"] == {
            "is_impersonating": False,
            "admin_user_id": None,
            "admin_email": None,
            "target_user_id": None,
            "expires_at": None,
        }
