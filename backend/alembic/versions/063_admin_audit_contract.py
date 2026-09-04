"""Harden the admin audit storage contract.

Revision ID: 063_admin_audit_contract
Revises: 062_widen_auth_secret_fields
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "063_admin_audit_contract"
down_revision: str | Sequence[str] | None = "062_widen_auth_secret_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FK_NAMING = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


def _uuid_type() -> sa.types.TypeEngine:
    if op.get_bind().dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def _replace_actor_fk(*, ondelete: str) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("admin_audit_logs", naming_convention=_FK_NAMING) as batch_op:
            batch_op.drop_constraint("fk_admin_audit_logs_actor_user_id_users", type_="foreignkey")
            batch_op.create_foreign_key(
                "fk_admin_audit_logs_actor_user_id_users",
                "users",
                ["actor_user_id"],
                ["id"],
                ondelete=ondelete,
            )
        return

    actor_fk = next(
        fk
        for fk in sa.inspect(bind).get_foreign_keys("admin_audit_logs")
        if fk["constrained_columns"] == ["actor_user_id"]
    )
    op.drop_constraint(actor_fk["name"], "admin_audit_logs", type_="foreignkey")
    op.create_foreign_key(
        "fk_admin_audit_logs_actor_user_id_users",
        "admin_audit_logs",
        "users",
        ["actor_user_id"],
        ["id"],
        ondelete=ondelete,
    )


def _create_session_fk() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("admin_audit_logs") as batch_op:
            batch_op.create_foreign_key(
                "fk_admin_audit_logs_impersonation_session_id",
                "impersonation_sessions",
                ["impersonation_session_id"],
                ["id"],
                ondelete="RESTRICT",
            )
        return
    op.create_foreign_key(
        "fk_admin_audit_logs_impersonation_session_id",
        "admin_audit_logs",
        "impersonation_sessions",
        ["impersonation_session_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def _drop_session_fk() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("admin_audit_logs") as batch_op:
            batch_op.drop_constraint(
                "fk_admin_audit_logs_impersonation_session_id",
                type_="foreignkey",
            )
        return
    op.drop_constraint(
        "fk_admin_audit_logs_impersonation_session_id",
        "admin_audit_logs",
        type_="foreignkey",
    )


def upgrade() -> None:
    uuid_type = _uuid_type()
    op.add_column(
        "admin_audit_logs",
        sa.Column("request_id", sa.String(128), nullable=True),
    )
    op.add_column(
        "admin_audit_logs",
        sa.Column("outcome", sa.String(16), nullable=True),
    )
    op.add_column(
        "admin_audit_logs",
        sa.Column("impersonation_session_id", uuid_type, nullable=True),
    )
    op.create_index(
        "ix_admin_audit_logs_request_id",
        "admin_audit_logs",
        ["request_id"],
    )
    op.create_index(
        "ix_admin_audit_logs_outcome",
        "admin_audit_logs",
        ["outcome"],
    )
    _create_session_fk()
    _replace_actor_fk(ondelete="RESTRICT")


def downgrade() -> None:
    bind = op.get_bind()
    evidence_count = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM admin_audit_logs "
            "WHERE request_id IS NOT NULL OR outcome IS NOT NULL "
            "OR impersonation_session_id IS NOT NULL"
        )
    ).scalar_one()
    if evidence_count:
        raise RuntimeError(
            "Cannot downgrade 063_admin_audit_contract: "
            "audit contract fields contain retained evidence"
        )

    _replace_actor_fk(ondelete="SET NULL")
    _drop_session_fk()
    op.drop_index("ix_admin_audit_logs_outcome", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_request_id", table_name="admin_audit_logs")
    op.drop_column("admin_audit_logs", "impersonation_session_id")
    op.drop_column("admin_audit_logs", "outcome")
    op.drop_column("admin_audit_logs", "request_id")
