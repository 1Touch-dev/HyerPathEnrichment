"""Add is_internal flag to jobs table

Revision ID: 005_add_is_internal_flag
Revises: 004_add_parent_child_job_fields
Create Date: 2026-07-28 15:45:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005_add_is_internal_flag'
down_revision: Union[str, Sequence[str], None] = '004_add_parent_child_job_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from alembic import context

    bind = context.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'

    if is_sqlite:
        # SQLite: use batch operations
        with op.batch_alter_table('jobs', schema=None) as batch_op:
            batch_op.add_column(sa.Column('is_internal', sa.Boolean(), nullable=False, server_default='0'))
            batch_op.create_index('ix_jobs_is_internal', ['is_internal'])
    else:
        # Postgres: use regular operations
        op.add_column('jobs', sa.Column('is_internal', sa.Boolean(), nullable=False, server_default='false'))
        op.create_index('ix_jobs_is_internal', 'jobs', ['is_internal'])

    # Backfill existing child jobs (those with parent_job_id) as internal
    # This works for both SQLite and Postgres
    connection = op.get_bind()
    connection.execute(
        sa.text("UPDATE jobs SET is_internal = true WHERE parent_job_id IS NOT NULL")
    )


def downgrade() -> None:
    from alembic import context

    bind = context.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'

    if is_sqlite:
        # SQLite: use batch operations
        with op.batch_alter_table('jobs', schema=None) as batch_op:
            batch_op.drop_index('ix_jobs_is_internal')
            batch_op.drop_column('is_internal')
    else:
        # Postgres: use regular operations
        op.drop_index('ix_jobs_is_internal', table_name='jobs')
        op.drop_column('jobs', 'is_internal')
