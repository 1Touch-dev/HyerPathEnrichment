"""Regression tests for generated auth JTI and sealed MFA storage widths."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from sqlalchemy import inspect, text

from alembic import command
from app.auth.models import LoggedOutToken, User
from app.auth.router import create_access_token
from app.core.secret_box import open_secret, seal_secret
from app.modules.admin.mfa import enroll_mfa
from tests.migration_helpers import (
    alembic_config,
    drop_all_user_tables,
    postgres_test_url,
    sqlite_file_url,
    sync_engine_for,
)

REV_BEFORE = "061_team_owner_full_desk_grants"
REV_THIS = "062_widen_auth_secret_fields"
TOKEN_JTI_WIDTH = 128
MFA_SECRET_WIDTH = 255
OLD_WIDTH = 64


@pytest.fixture
def sqlite_url(tmp_path: Path) -> str:
    return sqlite_file_url(tmp_path / "auth_storage_widths.db")


def _column_width(url: str, table: str, column: str) -> int | None:
    engine = sync_engine_for(url)
    try:
        with engine.connect() as conn:
            columns = {item["name"]: item for item in inspect(conn).get_columns(table)}
            return columns[column]["type"].length
    finally:
        engine.dispose()


def _generated_values() -> tuple[str, str, str]:
    raw_mfa_secret = pyotp.random_base32()
    sealed_mfa_secret = seal_secret(raw_mfa_secret)
    _token, token_jti = create_access_token(str(uuid4()), "width-test@example.com")
    return raw_mfa_secret, sealed_mfa_secret, token_jti


def _insert_auth_values(url: str, *, mfa_secret: str, token_jti: str) -> None:
    user_id = str(uuid4())
    now = datetime.now(UTC)
    engine = sync_engine_for(url)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO users (
                        id, email, first_name, last_name, is_verified, is_active,
                        is_superuser, mfa_secret, created_at, updated_at
                    )
                    VALUES (
                        :id, :email, :first_name, :last_name, :is_verified, :is_active,
                        :is_superuser, :mfa_secret, :created_at, :updated_at
                    )
                    """
                ),
                {
                    "id": user_id,
                    "email": f"width-{uuid4().hex}@example.com",
                    "first_name": "Width",
                    "last_name": "Test",
                    "is_verified": True,
                    "is_active": True,
                    "is_superuser": False,
                    "mfa_secret": mfa_secret,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            conn.execute(
                text(
                    """
                    INSERT INTO logged_out_tokens (
                        user_id, token_jti, logged_out_at, expires_at
                    )
                    VALUES (:user_id, :token_jti, :logged_out_at, :expires_at)
                    """
                ),
                {
                    "user_id": user_id,
                    "token_jti": token_jti,
                    "logged_out_at": now,
                    "expires_at": now + timedelta(hours=1),
                },
            )
    finally:
        engine.dispose()


def _clear_oversized_values(url: str) -> None:
    engine = sync_engine_for(url)
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM logged_out_tokens WHERE length(token_jti) > 64"))
            conn.execute(
                text(
                    "UPDATE users SET mfa_secret = NULL "
                    "WHERE mfa_secret IS NOT NULL AND length(mfa_secret) > 64"
                )
            )
    finally:
        engine.dispose()


def _assert_migration_round_trip(url: str) -> None:
    command.upgrade(alembic_config(url), REV_BEFORE)
    assert _column_width(url, "logged_out_tokens", "token_jti") == OLD_WIDTH
    assert _column_width(url, "users", "mfa_secret") == OLD_WIDTH

    command.upgrade(alembic_config(url), REV_THIS)
    assert _column_width(url, "logged_out_tokens", "token_jti") == TOKEN_JTI_WIDTH
    assert _column_width(url, "users", "mfa_secret") == MFA_SECRET_WIDTH

    _raw_secret, sealed_secret, token_jti = _generated_values()
    _insert_auth_values(url, mfa_secret=sealed_secret, token_jti=token_jti)

    with pytest.raises(
        RuntimeError,
        match=(
            r"1 logged_out_tokens\.token_jti value\(s\) and "
            r"1 users\.mfa_secret value\(s\) exceed 64 characters"
        ),
    ):
        command.downgrade(alembic_config(url), REV_BEFORE)

    _clear_oversized_values(url)
    command.downgrade(alembic_config(url), REV_BEFORE)
    assert _column_width(url, "logged_out_tokens", "token_jti") == OLD_WIDTH
    assert _column_width(url, "users", "mfa_secret") == OLD_WIDTH

    command.upgrade(alembic_config(url), REV_THIS)
    assert _column_width(url, "logged_out_tokens", "token_jti") == TOKEN_JTI_WIDTH
    assert _column_width(url, "users", "mfa_secret") == MFA_SECRET_WIDTH


def test_models_match_widened_schema() -> None:
    assert LoggedOutToken.__table__.c.token_jti.type.length == TOKEN_JTI_WIDTH
    assert User.__table__.c.mfa_secret.type.length == MFA_SECRET_WIDTH


def test_generated_values_fit_widened_columns() -> None:
    raw_secret, sealed_secret, token_jti = _generated_values()
    assert len(token_jti) == 69
    assert OLD_WIDTH < len(token_jti) <= TOKEN_JTI_WIDTH
    assert len(raw_secret) == 32
    assert OLD_WIDTH < len(sealed_secret) <= MFA_SECRET_WIDTH
    assert open_secret(sealed_secret) == raw_secret


async def test_runtime_persists_generated_auth_values(db_session) -> None:
    user = User(
        id=uuid4(),
        email=f"runtime-width-{uuid4().hex}@example.com",
        first_name="Runtime",
        last_name="Width",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    enrollment = await enroll_mfa(db_session, user)
    _token, token_jti = create_access_token(str(user.id), user.email)
    db_session.add(
        LoggedOutToken(
            user_id=user.id,
            token_jti=token_jti,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    await db_session.commit()
    await db_session.refresh(user)

    assert user.mfa_secret is not None
    assert len(user.mfa_secret) <= MFA_SECRET_WIDTH
    assert open_secret(user.mfa_secret) == enrollment.secret
    assert len(token_jti) <= TOKEN_JTI_WIDTH


def test_sqlite_migration_round_trip_and_safe_downgrade(sqlite_url: str) -> None:
    _assert_migration_round_trip(sqlite_url)


@pytest.mark.postgres
def test_postgres_migration_round_trip_and_safe_downgrade() -> None:
    url = postgres_test_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    drop_all_user_tables(url)
    _assert_migration_round_trip(url)
