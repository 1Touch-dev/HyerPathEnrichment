"""Create baseline schema (jobs, suppression, audit, dsar, photo_cache).

Document columns are JSONB on Postgres and JSON on SQLite via with_variant.

Revision ID: 001_baseline_schema
Revises:
Create Date: 2026-07-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "001_baseline_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JsonDoc = JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("request_payload", JsonDoc, nullable=False),
        sa.Column("dossier_payload", JsonDoc, nullable=False),
        sa.Column("identifier_hashes", JsonDoc, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "suppression_list",
        sa.Column("identifier_hash", sa.String(length=128), primary_key=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("identifier_hash", sa.String(length=128), nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=True),
        sa.Column("details", JsonDoc, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "dsar_requests",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("identifier_hash", sa.String(length=128), nullable=False),
        sa.Column("request_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("details", JsonDoc, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "photo_cache",
        sa.Column("slug_hash", sa.String(length=64), primary_key=True),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("asset_key", sa.String(length=512), nullable=False),
        sa.Column("asset_url", sa.String(length=1024), nullable=False),
        sa.Column("extraction_method", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("photo_cache")
    op.drop_table("dsar_requests")
    op.drop_table("audit_logs")
    op.drop_table("suppression_list")
    op.drop_table("jobs")
