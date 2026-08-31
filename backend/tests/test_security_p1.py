"""P1 security: refresh-token hashing, MFA seal, cascade erase helpers."""

from __future__ import annotations

from uuid import uuid4

import pyotp
from sqlalchemy import select

from app.auth.models import RefreshToken, User
from app.auth.refresh_tokens import (
    create_refresh_token,
    hash_refresh_token,
    revoke_all_refresh_tokens,
    validate_refresh_token,
)
from app.core.secret_box import open_secret, seal_secret
from app.modules.admin.mfa import enroll_mfa, verify_mfa_code

# Mixed sync/async tests — do not apply asyncio mark to the whole module.


async def test_create_refresh_token_stores_hash_not_raw(db_session):
    user = User(
        id=uuid4(),
        email=f"p1-{uuid4().hex[:8]}@example.com",
        first_name="P1",
        last_name="Test",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    raw, row = await create_refresh_token(db_session, user.id)
    assert row.token == hash_refresh_token(raw)
    assert row.token != raw

    found, found_user = await validate_refresh_token(db_session, raw)
    assert found is not None
    assert found_user.id == user.id


async def test_dual_read_upgrades_legacy_plaintext_refresh_token(db_session):
    from datetime import UTC, datetime, timedelta

    user = User(
        id=uuid4(),
        email=f"p1-legacy-{uuid4().hex[:8]}@example.com",
        first_name="P1",
        last_name="Legacy",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    raw = "legacy-plaintext-refresh-token-value-xxxxxxxx"
    legacy = RefreshToken(
        token=raw,
        user_id=user.id,
        used=False,
        parent_token=None,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db_session.add(legacy)
    await db_session.commit()

    found, _ = await validate_refresh_token(db_session, raw)
    assert found is not None
    assert found.token == hash_refresh_token(raw)

    leftover = await db_session.execute(select(RefreshToken).where(RefreshToken.token == raw))
    assert leftover.scalar_one_or_none() is None


async def test_revoke_all_refresh_tokens(db_session):
    user = User(
        id=uuid4(),
        email=f"p1-revoke-{uuid4().hex[:8]}@example.com",
        first_name="P1",
        last_name="Revoke",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await create_refresh_token(db_session, user.id)
    await create_refresh_token(db_session, user.id)
    count = await revoke_all_refresh_tokens(db_session, user.id, reason="test")
    assert count == 2


async def test_mfa_secret_is_sealed_at_rest(db_session, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret-key-32-chars-min!!")
    from app.core.config import get_settings

    get_settings.cache_clear()

    user = User(
        id=uuid4(),
        email=f"p1-mfa-{uuid4().hex[:8]}@example.com",
        first_name="P1",
        last_name="Mfa",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    enroll = await enroll_mfa(db_session, user)
    await db_session.refresh(user)
    assert user.mfa_secret != enroll.secret
    assert open_secret(user.mfa_secret) == enroll.secret
    code = pyotp.TOTP(enroll.secret).now()
    assert verify_mfa_code(user, code) is True

    get_settings.cache_clear()


def test_seal_open_roundtrip():
    sealed = seal_secret("hello-secret")
    assert sealed != "hello-secret"
    assert open_secret(sealed) == "hello-secret"
    assert open_secret("legacy-plaintext") == "legacy-plaintext"
