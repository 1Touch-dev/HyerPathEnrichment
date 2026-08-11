"""Rename auth_audit_logs.metadata to extra_data

Revision ID: 019_rename_audit_log_metadata
Revises: 018_add_attempt_metadata
Create Date: 2026-08-08

"""

from collections.abc import Sequence

from alembic import op

revision: str = "019_rename_audit_log_metadata"
down_revision: str | Sequence[str] | None = "018_add_attempt_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Rename metadata column to extra_data to match the ORM model.

    ``metadata`` is a reserved attribute name on SQLAlchemy declarative
    models, so the ORM model uses ``extra_data`` while the original
    migration (006) created the column as ``metadata``. Align the schema.
    """
    with op.batch_alter_table("auth_audit_logs") as batch_op:
        batch_op.alter_column("metadata", new_column_name="extra_data")


def downgrade() -> None:
    """Revert extra_data column back to metadata."""
    with op.batch_alter_table("auth_audit_logs") as batch_op:
        batch_op.alter_column("extra_data", new_column_name="metadata")
