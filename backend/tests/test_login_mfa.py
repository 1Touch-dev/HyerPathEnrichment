"""Password sign-in must not issue a session until an enrolled TOTP code matches."""

from __future__ import annotations

from datetime import UTC, datetime
from http.cookies import SimpleCookie
from uuid import uuid4

import pyotp
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.password import hash_password
from app.main import app

PASSWORD = "SecurePass123!"


async def _create_user(db: AsyncSession, **overrides: object) -> User:
    user_id = uuid4()
    values: dict[str, object] = {
        "id": user_id,
        "email": f"mfa-login-{user_id.hex}@example.com",
        "hashed_password": hash_password(PASSWORD),
        "first_name": "Mfa",
        "last_name": "User",
        "is_active": True,
        "is_verified": True,
        "mfa_enabled": False,
    }
    values.update(overrides)
    user = User(**values)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _cookies(response) -> dict[str, object]:
    parsed: dict[str, object] = {}
    for header in response.headers.get_list("set-cookie"):
        cookie = SimpleCookie()
        cookie.load(header)
        parsed.update(cookie)
    return parsed


@pytest.mark.asyncio
async def test_login_without_mfa_still_issues_session(db: AsyncSession) -> None:
    user = await _create_user(db)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post(
            "/auth/login",
            json={"email": user.email, "password": PASSWORD},
        )

    assert login.status_code == 200
    body = login.json()["data"]
    assert body["mfa_required"] is False
    assert body["user"]["email"] == user.email
    names = set(_cookies(login))
    assert "access_token" in names
    assert "refresh_token" in names
    assert "mfa_login" not in names


@pytest.mark.asyncio
async def test_enrolled_mfa_blocks_session_until_valid_code(db: AsyncSession) -> None:
    secret = pyotp.random_base32()
    user = await _create_user(
        db,
        mfa_enabled=True,
        mfa_secret=secret,
        mfa_enrolled_at=datetime.now(UTC),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post(
            "/auth/login",
            json={"email": user.email, "password": PASSWORD},
        )
        assert login.status_code == 200
        body = login.json()["data"]
        assert body["mfa_required"] is True
        assert body["user"] is None
        cookies = _cookies(login)
        assert "access_token" not in cookies
        assert "refresh_token" not in cookies
        assert cookies["mfa_login"]["httponly"] is True

        rejected = await client.get(
            "/auth/me",
            cookies={"access_token": cookies["mfa_login"].value},
        )
        assert rejected.status_code == 401

        wrong_code = "000000" if pyotp.TOTP(secret).now() != "000000" else "111111"
        wrong = await client.post("/auth/login/mfa", json={"code": wrong_code})
        assert wrong.status_code == 401
        assert "access_token" not in _cookies(wrong)

        verified = await client.post(
            "/auth/login/mfa",
            json={"code": pyotp.TOTP(secret).now()},
        )

    assert verified.status_code == 200
    assert verified.json()["data"]["user"]["email"] == user.email
    session = _cookies(verified)
    assert "access_token" in session
    assert "refresh_token" in session
    assert session["mfa_login"].value == ""
