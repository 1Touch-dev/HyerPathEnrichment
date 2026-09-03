"""Focused migration checks for the privileged-operation contract foundation."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.modules.admin.models import (
    AdminAuditLog,
    ImpersonationSession,
    PrivilegedIdempotencyRecord,
)
from app.modules.staff_invites.models import StaffInvite
from app.modules.staff_invites.schemas import StaffInviteCreate
from tests.migration_helpers import (
    alembic_config,
    drop_all_user_tables,
    postgres_test_url,
    sqlite_file_url,
    sync_engine_for,
    upgrade_head,
)


@pytest.fixture
def sqlite_url(tmp_path: Path) -> str:
    return sqlite_file_url(tmp_path / "privileged-contract.db")


def _db_uuid(dialect_name: str):
    value = uuid4()
    return value if dialect_name == "postgresql" else str(value)


def _insert_user(conn, email: str):
    user_id = _db_uuid(conn.dialect.name)
    conn.execute(
        text(
            """
            INSERT INTO users (
                id, email, hashed_password, first_name, last_name,
                is_verified, is_active, is_superuser, created_at, updated_at
            ) VALUES (
                :id, :email, NULL, 'Contract', 'User',
                :verified, :active, :superuser, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """
        ),
        {
            "id": user_id,
            "email": email,
            "verified": True,
            "active": True,
            "superuser": False,
        },
    )
    return user_id


def _upgrade_populated_062(url: str) -> dict[str, object]:
    command.upgrade(alembic_config(url), "062_widen_auth_secret_fields")
    engine = sync_engine_for(url)
    now = datetime.now(UTC)
    values: dict[str, object] = {}
    try:
        with engine.begin() as conn:
            recruiter_role_id = conn.execute(
                text("SELECT id FROM roles WHERE name = 'recruiter'")
            ).scalar_one()
            rows = [
                (
                    "safe",
                    "safe@example.com",
                    "safe-token",
                    "recruiter",
                    now + timedelta(days=1),
                    now,
                ),
                (
                    "unsafe",
                    "unsafe@example.com",
                    "unsafe-token",
                    "team_owner",
                    now + timedelta(days=1),
                    now,
                ),
                (
                    "expired",
                    "expired@example.com",
                    "expired-token",
                    "recruiter",
                    now - timedelta(days=1),
                    now - timedelta(days=2),
                ),
                (
                    "duplicate_old",
                    "duplicate@example.com",
                    "duplicate-old-token",
                    "recruiter",
                    now + timedelta(days=1),
                    now - timedelta(hours=1),
                ),
                (
                    "duplicate_new",
                    "DUPLICATE@example.com",
                    "duplicate-new-token",
                    "recruiter",
                    now + timedelta(days=1),
                    now,
                ),
            ]
            for key, email, token, role_name, expires_at, created_at in rows:
                invite_id = _db_uuid(conn.dialect.name)
                values[key] = invite_id
                conn.execute(
                    text(
                        """
                        INSERT INTO staff_invites (
                            id, email, token, role_name, invited_by,
                            expires_at, accepted_at, created_at
                        ) VALUES (
                            :id, :email, :token, :role_name, NULL,
                            :expires_at, NULL, :created_at
                        )
                        """
                    ),
                    {
                        "id": invite_id,
                        "email": email,
                        "token": token,
                        "role_name": role_name,
                        "expires_at": expires_at,
                        "created_at": created_at,
                    },
                )
            values["recruiter_role_id"] = recruiter_role_id
    finally:
        engine.dispose()
    command.upgrade(alembic_config(url), "head")
    return values


def test_privileged_contract_schema_and_roundtrip_sqlite(sqlite_url: str) -> None:
    upgrade_head(sqlite_url)
    engine = sync_engine_for(sqlite_url)
    try:
        with engine.connect() as conn:
            inspector = inspect(conn)
            audit_columns = {column["name"] for column in inspector.get_columns("admin_audit_logs")}
            session_columns = {
                column["name"] for column in inspector.get_columns("impersonation_sessions")
            }
            invite_columns = {column["name"] for column in inspector.get_columns("staff_invites")}
            idempotency_columns = {
                column["name"] for column in inspector.get_columns("privileged_idempotency_records")
            }
            assert {
                "request_id",
                "outcome",
                "impersonation_session_id",
            } <= audit_columns
            assert {
                "scope",
                "revoked_at",
                "revoked_by",
                "revocation_reason",
            } <= session_columns
            assert {
                "token_digest",
                "role_id",
                "revoked_at",
                "accepted_by_user_id",
            } <= invite_columns
            assert {
                "caller_user_id",
                "operation",
                "idempotency_key",
                "request_hash",
                "response_status",
                "response_body",
                "request_id",
                "created_at",
                "completed_at",
                "expires_at",
            } <= idempotency_columns
    finally:
        engine.dispose()

    command.downgrade(
        alembic_config(sqlite_url),
        "062_widen_auth_secret_fields",
    )
    command.upgrade(alembic_config(sqlite_url), "head")


def test_populated_062_invite_backfill_and_invalidation_sqlite(
    sqlite_url: str,
) -> None:
    values = _upgrade_populated_062(sqlite_url)
    engine = sync_engine_for(sqlite_url)
    try:
        with engine.begin() as conn:
            rows = {
                row.id: row
                for row in conn.execute(
                    text(
                        "SELECT id, token, token_digest, role_name, role_id, revoked_at "
                        "FROM staff_invites"
                    )
                ).mappings()
            }
            safe = rows[values["safe"]]
            # Safe active plaintext remains only for hardened schema recovery.
            assert safe.token == "safe-token"
            assert safe.token_digest == hashlib.sha256(b"safe-token").hexdigest()
            assert safe.role_id == values["recruiter_role_id"]
            assert safe.revoked_at is None

            unsafe = rows[values["unsafe"]]
            assert unsafe.token_digest == hashlib.sha256(b"unsafe-token").hexdigest()
            assert unsafe.token is None
            assert unsafe.role_id is None
            assert unsafe.revoked_at is not None

            assert rows[values["expired"]].revoked_at is not None
            assert rows[values["expired"]].token == "expired-token"
            assert rows[values["duplicate_old"]].revoked_at is not None
            assert rows[values["duplicate_old"]].token is None
            assert rows[values["duplicate_new"]].revoked_at is None

            with pytest.raises(IntegrityError), conn.begin_nested():
                conn.execute(
                    text(
                        """
                        INSERT INTO staff_invites (
                            id, email, token, token_digest, role_name, role_id,
                            invited_by, expires_at, accepted_at, revoked_at,
                            accepted_by_user_id, created_at
                        ) VALUES (
                            :id, 'duplicate@example.com', NULL, :digest,
                            'recruiter', :role_id, NULL, :expires_at,
                            NULL, NULL, NULL, CURRENT_TIMESTAMP
                        )
                        """
                    ),
                    {
                        "id": _db_uuid(conn.dialect.name),
                        "digest": "c" * 64,
                        "role_id": values["recruiter_role_id"],
                        "expires_at": datetime.now(UTC) + timedelta(days=1),
                    },
                )
    finally:
        engine.dispose()


def test_hardened_foreign_keys_preserve_evidence(sqlite_url: str) -> None:
    upgrade_head(sqlite_url)
    engine = sync_engine_for(sqlite_url)
    try:
        with engine.connect() as conn:
            inspector = inspect(conn)
            audit_actor_fk = next(
                fk
                for fk in inspector.get_foreign_keys("admin_audit_logs")
                if fk["constrained_columns"] == ["actor_user_id"]
            )
            session_fks = {
                tuple(fk["constrained_columns"]): fk
                for fk in inspector.get_foreign_keys("impersonation_sessions")
            }
            assert audit_actor_fk["options"]["ondelete"].upper() == "RESTRICT"
            assert session_fks[("admin_user_id",)]["options"]["ondelete"].upper() == "RESTRICT"
            assert session_fks[("target_user_id",)]["options"]["ondelete"].upper() == "RESTRICT"
    finally:
        engine.dispose()


def test_privileged_idempotency_unique_caller_operation_key(
    sqlite_url: str,
) -> None:
    upgrade_head(sqlite_url)
    engine = sync_engine_for(sqlite_url)
    try:
        with engine.begin() as conn:
            user_id = _insert_user(conn, f"{uuid4()}@example.com")
            statement = text(
                """
                INSERT INTO privileged_idempotency_records (
                    id, caller_user_id, operation, idempotency_key,
                    request_hash, response_status, response_body, request_id,
                    created_at, completed_at, expires_at
                ) VALUES (
                    :id, :caller_user_id, 'roles.update', 'same-key',
                    :request_hash, NULL, NULL, :request_id,
                    CURRENT_TIMESTAMP, NULL, :expires_at
                )
                """
            )
            common = {
                "caller_user_id": user_id,
                "request_hash": "a" * 64,
                "expires_at": datetime.now(UTC) + timedelta(days=1),
            }
            conn.execute(
                statement,
                {
                    **common,
                    "id": _db_uuid(conn.dialect.name),
                    "request_id": "req-one",
                },
            )
            with pytest.raises(IntegrityError), conn.begin_nested():
                conn.execute(
                    statement,
                    {
                        **common,
                        "id": _db_uuid(conn.dialect.name),
                        "request_id": "req-two",
                    },
                )
    finally:
        engine.dispose()


def test_audit_evidence_blocks_destructive_downgrade(sqlite_url: str) -> None:
    upgrade_head(sqlite_url)
    engine = sync_engine_for(sqlite_url)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO admin_audit_logs (
                        id, actor_user_id, impersonated_by, action, target_type,
                        target_id, before, after, ip_address, captured_by,
                        request_id, outcome, impersonation_session_id, created_at
                    ) VALUES (
                        :id, NULL, NULL, 'roles.updated', 'role', NULL,
                        NULL, NULL, NULL, 'explicit',
                        'req-contract-test', 'succeeded', NULL, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {"id": str(uuid4())},
            )
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match="retained evidence"):
        command.downgrade(
            alembic_config(sqlite_url),
            "062_widen_auth_secret_fields",
        )


def test_impersonation_revocation_blocks_destructive_downgrade(
    sqlite_url: str,
) -> None:
    command.upgrade(
        alembic_config(sqlite_url),
        "064_impersonation_session_hardening",
    )
    engine = sync_engine_for(sqlite_url)
    try:
        with engine.begin() as conn:
            admin_id = _insert_user(conn, "imp-admin@example.com")
            target_id = _insert_user(conn, "imp-target@example.com")
            conn.execute(
                text(
                    """
                    INSERT INTO impersonation_sessions (
                        id, admin_user_id, target_user_id, token_jti, reason,
                        started_at, ended_at, expires_at, scope, revoked_at,
                        revoked_by, revocation_reason
                    ) VALUES (
                        :id, :admin_id, :target_id, 'revoked-jti', NULL,
                        CURRENT_TIMESTAMP, NULL, :expires_at, 'view_only',
                        CURRENT_TIMESTAMP, :admin_id, 'manual'
                    )
                    """
                ),
                {
                    "id": _db_uuid(conn.dialect.name),
                    "admin_id": admin_id,
                    "target_id": target_id,
                    "expires_at": datetime.now(UTC) + timedelta(minutes=5),
                },
            )
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match="revocation"):
        command.downgrade(
            alembic_config(sqlite_url),
            "063_admin_audit_contract",
        )


def test_invite_revocation_blocks_destructive_downgrade(sqlite_url: str) -> None:
    _upgrade_populated_062(sqlite_url)
    with pytest.raises(RuntimeError, match="revocation"):
        command.downgrade(
            alembic_config(sqlite_url),
            "064_impersonation_session_hardening",
        )


def test_idempotency_evidence_blocks_destructive_downgrade(
    sqlite_url: str,
) -> None:
    upgrade_head(sqlite_url)
    engine = sync_engine_for(sqlite_url)
    try:
        with engine.begin() as conn:
            caller_id = _insert_user(conn, "idem-guard@example.com")
            conn.execute(
                text(
                    """
                    INSERT INTO privileged_idempotency_records (
                        id, caller_user_id, operation, idempotency_key,
                        request_hash, response_status, response_body, request_id,
                        created_at, completed_at, expires_at
                    ) VALUES (
                        :id, :caller_id, 'roles.update', 'guard-key',
                        :request_hash, 200, '{}', 'req-guard',
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :expires_at
                    )
                    """
                ),
                {
                    "id": _db_uuid(conn.dialect.name),
                    "caller_id": caller_id,
                    "request_hash": "b" * 64,
                    "expires_at": datetime.now(UTC) + timedelta(days=1),
                },
            )
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match="must be retained"):
        command.downgrade(
            alembic_config(sqlite_url),
            "065_staff_invite_security",
        )


def test_models_match_privileged_contract_columns() -> None:
    assert {"request_id", "outcome", "impersonation_session_id"} <= set(
        AdminAuditLog.__table__.c.keys()
    )
    assert {"scope", "revoked_at", "revoked_by", "revocation_reason"} <= set(
        ImpersonationSession.__table__.c.keys()
    )
    assert {
        "caller_user_id",
        "operation",
        "idempotency_key",
        "request_hash",
        "response_body",
        "request_id",
        "expires_at",
    } <= set(PrivilegedIdempotencyRecord.__table__.c.keys())
    assert {
        "token_digest",
        "role_id",
        "revoked_at",
        "accepted_by_user_id",
    } <= set(StaffInvite.__table__.c.keys())


def test_staff_invite_contract_is_recruiter_only() -> None:
    assert (
        StaffInviteCreate(
            email="recruiter@example.com",
            confirmation_email="recruiter@example.com",
            mfa_code="123456",
        ).role_name
        == "recruiter"
    )
    with pytest.raises(ValueError):
        StaffInviteCreate(
            email="owner@example.com",
            role_name="team_owner",
            confirmation_email="owner@example.com",
            mfa_code="123456",
        )


def test_invite_rollback_contract_never_allows_old_binary_traffic() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    adr_0015 = (repo_root / "docs/adr/0015-admin-module-rbac-audit-mfa.md").read_text(
        encoding="utf-8"
    )
    adr_0021 = (repo_root / "docs/adr/0021-privileged-operation-controls.md").read_text(
        encoding="utf-8"
    )
    architecture = (repo_root / "backend/docs/ARCHITECTURE.md").read_text(encoding="utf-8")
    combined = f"{adr_0015}\n{adr_0021}\n{architecture}".lower()

    assert "pre-hardening/old api binary must never serve" in combined
    assert "never start a pre-hardening/old api binary" in combined
    assert "creation, lookup, or redemption" in combined
    assert "if no verified compatible artifact exists" in combined
    assert "keep api/invite paths stopped" in combined
    assert "except as an explicit rollback" not in combined
    assert "rollback to the old api binary" not in combined


@pytest.mark.postgres
def test_privileged_contract_populated_upgrade_postgres() -> None:
    url = postgres_test_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    drop_all_user_tables(url)
    values = _upgrade_populated_062(url)
    engine = sync_engine_for(url)
    try:
        with engine.begin() as conn:
            unsafe = (
                conn.execute(
                    text(
                        "SELECT token, role_id, revoked_at, token_digest FROM staff_invites "
                        "WHERE id = :id"
                    ),
                    {"id": values["unsafe"]},
                )
                .mappings()
                .one()
            )
            assert unsafe.token is None
            assert unsafe.role_id is None
            assert unsafe.revoked_at is not None
            assert unsafe.token_digest == hashlib.sha256(b"unsafe-token").hexdigest()
            safe_token = conn.execute(
                text("SELECT token FROM staff_invites WHERE id = :id"),
                {"id": values["safe"]},
            ).scalar_one()
            assert safe_token == "safe-token"

            actor_id = _insert_user(conn, "retained-actor@example.com")
            conn.execute(
                text(
                    """
                    INSERT INTO admin_audit_logs (
                        id, actor_user_id, impersonated_by, action, target_type,
                        target_id, before, after, ip_address, captured_by,
                        request_id, outcome, impersonation_session_id, created_at
                    ) VALUES (
                        :id, :actor_id, NULL, 'roles.updated', 'role', NULL,
                        NULL, NULL, NULL, 'explicit',
                        'req-pg-fk', 'succeeded', NULL, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {"id": _db_uuid(conn.dialect.name), "actor_id": actor_id},
            )
            with pytest.raises(IntegrityError), conn.begin_nested():
                conn.execute(
                    text("DELETE FROM users WHERE id = :actor_id"),
                    {"actor_id": actor_id},
                )
    finally:
        engine.dispose()


@pytest.mark.postgres
def test_postgres_downgrade_refuses_retained_063_through_066_evidence() -> None:
    url = postgres_test_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")

    # 063: request-correlated audit evidence.
    drop_all_user_tables(url)
    upgrade_head(url)
    engine = sync_engine_for(url)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO admin_audit_logs (
                        id, action, target_type, captured_by,
                        request_id, outcome, created_at
                    ) VALUES (
                        :id, 'roles.updated', 'role', 'explicit',
                        'req-pg-063', 'succeeded', CURRENT_TIMESTAMP
                    )
                    """
                ),
                {"id": _db_uuid(conn.dialect.name)},
            )
    finally:
        engine.dispose()
    with pytest.raises(RuntimeError, match="retained evidence"):
        command.downgrade(alembic_config(url), "062_widen_auth_secret_fields")

    # 064: revocation evidence.
    drop_all_user_tables(url)
    command.upgrade(alembic_config(url), "064_impersonation_session_hardening")
    engine = sync_engine_for(url)
    try:
        with engine.begin() as conn:
            admin_id = _insert_user(conn, "pg-064-admin@example.com")
            target_id = _insert_user(conn, "pg-064-target@example.com")
            conn.execute(
                text(
                    """
                    INSERT INTO impersonation_sessions (
                        id, admin_user_id, target_user_id, token_jti,
                        started_at, expires_at, scope, revoked_at,
                        revoked_by, revocation_reason
                    ) VALUES (
                        :id, :admin_id, :target_id, 'pg-revoked-jti',
                        CURRENT_TIMESTAMP, :expires_at, 'view_only',
                        CURRENT_TIMESTAMP, :admin_id, 'manual'
                    )
                    """
                ),
                {
                    "id": _db_uuid(conn.dialect.name),
                    "admin_id": admin_id,
                    "target_id": target_id,
                    "expires_at": datetime.now(UTC) + timedelta(minutes=5),
                },
            )
    finally:
        engine.dispose()
    with pytest.raises(RuntimeError, match="revocation"):
        command.downgrade(alembic_config(url), "063_admin_audit_contract")

    # 065: invalidated invite evidence.
    drop_all_user_tables(url)
    _upgrade_populated_062(url)
    with pytest.raises(RuntimeError, match="revocation"):
        command.downgrade(
            alembic_config(url),
            "064_impersonation_session_hardening",
        )

    # 066: privileged replay evidence.
    drop_all_user_tables(url)
    upgrade_head(url)
    engine = sync_engine_for(url)
    try:
        with engine.begin() as conn:
            caller_id = _insert_user(conn, "pg-066-caller@example.com")
            conn.execute(
                text(
                    """
                    INSERT INTO privileged_idempotency_records (
                        id, caller_user_id, operation, idempotency_key,
                        request_hash, response_status, response_body, request_id,
                        created_at, completed_at, expires_at
                    ) VALUES (
                        :id, :caller_id, 'roles.update', 'pg-guard-key',
                        :request_hash, 200, '{}'::jsonb, 'req-pg-066',
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :expires_at
                    )
                    """
                ),
                {
                    "id": _db_uuid(conn.dialect.name),
                    "caller_id": caller_id,
                    "request_hash": "d" * 64,
                    "expires_at": datetime.now(UTC) + timedelta(days=1),
                },
            )
    finally:
        engine.dispose()
    with pytest.raises(RuntimeError, match="must be retained"):
        command.downgrade(
            alembic_config(url),
            "065_staff_invite_security",
        )
