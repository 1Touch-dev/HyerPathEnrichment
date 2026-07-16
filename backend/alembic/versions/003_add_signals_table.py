"""Add signals table for persisted change notifications.

Revision ID: 003_add_signals_table
Revises: 002_promote_json_to_jsonb
Create Date: 2026-07-16
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_add_signals_table"
down_revision: Union[str, Sequence[str], None] = "002_promote_json_to_jsonb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "signals",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("watch_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("signal_timestamp", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("signals")
