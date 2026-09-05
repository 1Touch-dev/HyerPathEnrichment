"""Harden impersonation sessions for per-request validation and revocation.

Revision ID: 064_impersonation_session_hardening
Revises: 063_admin_audit_contract
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "064_impersonation_session_hardening"
down_revision: str | Sequence[str] | None = "063_admin_audit_contract"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FK_NAMING = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


def _uuid_type() -> sa.types.TypeEngine:
    if op.get_bind().dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def _replace_user_fks(*, hardened: bool) -> None:
    ondelete = "RESTRICT" if hardened else "CASCADE"
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(
            "impersonation_sessions", naming_convention=_FK_NAMING
        ) as batch_op:
            batch_op.drop_constraint(
                "fk_impersonation_sessions_admin_user_id_users",
                type_="foreignkey",
            )
            batch_op.drop_constraint(
                "fk_impersonation_sessions_target_user_id_users",
                type_="foreignkey",
            )
            if hardened:
                batch_op.create_foreign_key(
                    "fk_impersonation_sessions_revoked_by_users",
                    "users",
                    ["revoked_by"],
                    ["id"],
                    ondelete="RESTRICT",
                )
            else:
                batch_op.drop_constraint(
                    "fk_impersonation_sessions_revoked_by_users",
                    type_="foreignkey",
                )
            batch_op.create_foreign_key(
                "fk_impersonation_sessions_admin_user_id_users",
                "users",
                ["admin_user_id"],
                ["id"],
                ondelete=ondelete,
            )
            batch_op.create_foreign_key(
                "fk_impersonation_sessions_target_user_id_users",
                "users",
                ["target_user_id"],
                ["id"],
                ondelete=ondelete,
            )
        return

    foreign_keys = sa.inspect(bind).get_foreign_keys("impersonation_sessions")
    admin_fk = next(fk for fk in foreign_keys if fk["constrained_columns"] == ["admin_user_id"])
    target_fk = next(fk for fk in foreign_keys if fk["constrained_columns"] == ["target_user_id"])
    op.drop_constraint(admin_fk["name"], "impersonation_sessions", type_="foreignkey")
    op.drop_constraint(target_fk["name"], "impersonation_sessions", type_="foreignkey")
    if hardened:
        op.create_foreign_key(
            "fk_impersonation_sessions_revoked_by_users",
            "impersonation_sessions",
            "users",
            ["revoked_by"],
            ["id"],
            ondelete="RESTRICT",
        )
    else:
        op.drop_constraint(
            "fk_impersonation_sessions_revoked_by_users",
            "impersonation_sessions",
            type_="foreignkey",
        )
    op.create_foreign_key(
        "fk_impersonation_sessions_admin_user_id_users",
        "impersonation_sessions",
        "users",
        ["admin_user_id"],
        ["id"],
        ondelete=ondelete,
    )
    op.create_foreign_key(
        "fk_impersonation_sessions_target_user_id_users",
        "impersonation_sessions",
        "users",
        ["target_user_id"],
        ["id"],
        ondelete=ondelete,
    )


def upgrade() -> None:
    op.add_column(
        "impersonation_sessions",
        sa.Column(
            "scope",
            sa.String(16),
            nullable=False,
            server_default="view_only",
        ),
    )
    op.add_column(
        "impersonation_sessions",
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "impersonation_sessions",
        sa.Column("revoked_by", _uuid_type(), nullable=True),
    )
    op.add_column(
        "impersonation_sessions",
        sa.Column("revocation_reason", sa.Text(), nullable=True),
    )
    _replace_user_fks(hardened=True)
    op.create_index(
        "ix_impersonation_sessions_revoked_at",
        "impersonation_sessions",
        ["revoked_at"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    evidence_count = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM impersonation_sessions "
            "WHERE revoked_at IS NOT NULL OR revoked_by IS NOT NULL "
            "OR revocation_reason IS NOT NULL OR scope <> 'view_only'"
        )
    ).scalar_one()
    if evidence_count:
        raise RuntimeError(
            "Cannot downgrade 064_impersonation_session_hardening: "
            "revocation or non-default scope evidence exists"
        )

    op.drop_index(
        "ix_impersonation_sessions_revoked_at",
        table_name="impersonation_sessions",
    )
    _replace_user_fks(hardened=False)
    op.drop_column("impersonation_sessions", "revocation_reason")
    op.drop_column("impersonation_sessions", "revoked_by")
    op.drop_column("impersonation_sessions", "revoked_at")
    op.drop_column("impersonation_sessions", "scope")
