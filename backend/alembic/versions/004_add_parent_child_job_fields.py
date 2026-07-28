"""Add parent-child job relationship fields

Revision ID: 004_add_parent_child_job_fields
Revises: 64970cccdab8
Create Date: 2026-07-28 13:15:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from sqlalchemy.types import Text
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '004_add_parent_child_job_fields'
down_revision: Union[str, Sequence[str], None] = '64970cccdab8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from alembic import context

    bind = context.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'

    if is_sqlite:
        # SQLite: use batch operations
        with op.batch_alter_table('jobs', schema=None) as batch_op:
            batch_op.add_column(sa.Column('parent_job_id', sa.String(64), nullable=True))
            batch_op.add_column(sa.Column('child_job_ids', postgresql.JSONB(astext_type=Text()).with_variant(sa.JSON(), 'sqlite'), nullable=False, server_default='[]'))
            batch_op.add_column(sa.Column('tier_assignment', postgresql.JSONB(astext_type=Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True))
    else:
        # Postgres: use regular add_column
        op.add_column('jobs', sa.Column('parent_job_id', sa.String(64), nullable=True))
        op.add_column('jobs', sa.Column('child_job_ids', postgresql.JSONB(astext_type=Text()), nullable=False, server_default='[]'))
        op.add_column('jobs', sa.Column('tier_assignment', postgresql.JSONB(astext_type=Text()), nullable=True))


def downgrade() -> None:
    from alembic import context

    bind = context.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'

    if is_sqlite:
        # SQLite: use batch operations
        with op.batch_alter_table('jobs', schema=None) as batch_op:
            batch_op.drop_column('tier_assignment')
            batch_op.drop_column('child_job_ids')
            batch_op.drop_column('parent_job_id')
    else:
        # Postgres: use regular drop_column
        op.drop_column('jobs', 'tier_assignment')
        op.drop_column('jobs', 'child_job_ids')
        op.drop_column('jobs', 'parent_job_id')
