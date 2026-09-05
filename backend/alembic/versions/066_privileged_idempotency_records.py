"""Create the privileged-operation idempotency ledger.

Revision ID: 066_privileged_idempotency_records
Revises: 065_staff_invite_security
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "066_privileged_idempotency_records"
down_revision: str | Sequence[str] | None = "065_staff_invite_security"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_type() -> sa.types.TypeEngine:
    if op.get_bind().dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def _json_type() -> sa.types.TypeEngine:
    if op.get_bind().dialect.name == "postgresql":
        return postgresql.JSONB()
    return sa.JSON()


def upgrade() -> None:
    uuid_type = _uuid_type()
    op.create_table(
        "privileged_idempotency_records",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "caller_user_id",
            uuid_type,
            sa.ForeignKey(
                "users.id",
                name="fk_privileged_idempotency_records_caller_user_id_users",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("operation", sa.String(128), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", _json_type(), nullable=True),
        sa.Column("request_id", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "caller_user_id",
            "operation",
            "idempotency_key",
            name="uq_privileged_idempotency_caller_operation_key",
        ),
    )
    op.create_index(
        "ix_privileged_idempotency_records_request_id",
        "privileged_idempotency_records",
        ["request_id"],
    )
    op.create_index(
        "ix_privileged_idempotency_records_expires_at",
        "privileged_idempotency_records",
        ["expires_at"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    record_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM privileged_idempotency_records")
    ).scalar_one()
    if record_count:
        raise RuntimeError(
            "Cannot downgrade 066_privileged_idempotency_records: "
            "privileged-operation records must be retained"
        )

    op.drop_index(
        "ix_privileged_idempotency_records_expires_at",
        table_name="privileged_idempotency_records",
    )
    op.drop_index(
        "ix_privileged_idempotency_records_request_id",
        table_name="privileged_idempotency_records",
    )
    op.drop_table("privileged_idempotency_records")
