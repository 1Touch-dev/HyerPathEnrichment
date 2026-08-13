"""Add user_id to DSAR requests

Revision ID: 007_add_user_id_to_dsar
Revises: 006_add_user_authentication
Create Date: 2026-07-31 19:30:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007_add_user_id_to_dsar"
down_revision: str | Sequence[str] | None = "006_add_user_authentication"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from alembic import context

    bind = context.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    # Add user_id column to dsar_requests table
    if is_sqlite:
        with op.batch_alter_table("dsar_requests", schema=None) as batch_op:
            batch_op.add_column(sa.Column("user_id", sa.String(36), nullable=True))
            batch_op.create_foreign_key(
                "fk_dsar_requests_user_id", "users", ["user_id"], ["id"], ondelete="CASCADE"
            )
            batch_op.create_index("ix_dsar_requests_user_id", ["user_id"])
    else:
        op.add_column(
            "dsar_requests", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True)
        )
        op.create_foreign_key(
            "fk_dsar_requests_user_id",
            "dsar_requests",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index("ix_dsar_requests_user_id", "dsar_requests", ["user_id"])


def downgrade() -> None:
    from alembic import context

    bind = context.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    # Remove user_id from dsar_requests table
    if is_sqlite:
        with op.batch_alter_table("dsar_requests", schema=None) as batch_op:
            batch_op.drop_index("ix_dsar_requests_user_id")
            batch_op.drop_constraint("fk_dsar_requests_user_id", type_="foreignkey")
            batch_op.drop_column("user_id")
    else:
        op.drop_index("ix_dsar_requests_user_id", table_name="dsar_requests")
        op.drop_constraint("fk_dsar_requests_user_id", "dsar_requests", type_="foreignkey")
        op.drop_column("dsar_requests", "user_id")
