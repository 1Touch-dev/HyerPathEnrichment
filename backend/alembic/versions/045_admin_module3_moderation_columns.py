"""Add Module 3 moderation columns (Admin Module — interview questions and
practice audio moderation).

Revision ID: 045_admin_module3_moderation_columns
Revises: 044_merge_admin_and_module4_heads
Create Date: 2026-08-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "045_admin_module3_moderation_columns"
down_revision: str | Sequence[str] | None = "044_merge_admin_and_module4_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def _add_moderation_columns(table_name: str, fk_name: str) -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    uuid_type = _uuid_type()

    # SQLite has no native ALTER TABLE ADD CONSTRAINT/ADD FOREIGN KEY support —
    # batch mode (recreate-table) is required there for the moderated_by FK,
    # matching the existing pattern in 040_phase2_moderation_columns.py.
    # Postgres supports these ALTERs directly.
    if is_sqlite:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "moderation_status", sa.String(20), nullable=False, server_default="active"
                )
            )
            batch_op.add_column(sa.Column("moderated_by", uuid_type, nullable=True))
            batch_op.add_column(
                sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True)
            )
            batch_op.create_foreign_key(
                fk_name, "users", ["moderated_by"], ["id"], ondelete="SET NULL"
            )
    else:
        op.add_column(
            table_name,
            sa.Column("moderation_status", sa.String(20), nullable=False, server_default="active"),
        )
        op.add_column(table_name, sa.Column("moderated_by", uuid_type, nullable=True))
        op.add_column(
            table_name, sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True)
        )
        op.create_foreign_key(
            fk_name,
            table_name,
            "users",
            ["moderated_by"],
            ["id"],
            ondelete="SET NULL",
        )


def _drop_moderation_columns(table_name: str, fk_name: str) -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if is_sqlite:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.drop_constraint(fk_name, type_="foreignkey")
            batch_op.drop_column("moderated_at")
            batch_op.drop_column("moderated_by")
            batch_op.drop_column("moderation_status")
    else:
        op.drop_constraint(fk_name, table_name, type_="foreignkey")
        op.drop_column(table_name, "moderated_at")
        op.drop_column(table_name, "moderated_by")
        op.drop_column(table_name, "moderation_status")


def upgrade() -> None:
    _add_moderation_columns("interview_questions", "fk_interview_questions_moderated_by")
    _add_moderation_columns(
        "practice_audio_recordings", "fk_practice_audio_recordings_moderated_by"
    )


def downgrade() -> None:
    _drop_moderation_columns(
        "practice_audio_recordings", "fk_practice_audio_recordings_moderated_by"
    )
    _drop_moderation_columns("interview_questions", "fk_interview_questions_moderated_by")
