"""Create country_demand_snapshots table and add country_iso2 column to
job_postings (Machine 2, Track 02 — country-demand intelligence).

Revision ID: 050_country_demand_intelligence
Revises: 047_seed_system_roles
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "050_country_demand_intelligence"
down_revision: str | Sequence[str] | None = "047_seed_system_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def upgrade() -> None:
    uuid_type = _uuid_type()

    op.create_table(
        "country_demand_snapshots",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("country_iso2", sa.String(2), nullable=False),
        sa.Column("role_bucket", sa.String(255), nullable=False),
        sa.Column("posting_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("remote_posting_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_salary_min", sa.Integer(), nullable=True),
        sa.Column("avg_salary_max", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        # Re-running the daily aggregation job for the same day must upsert, not
        # duplicate — see app.modules.demand_intelligence.repository.upsert_snapshot.
        # Declared inline (table doesn't exist yet in this migration) rather than via
        # a separate op.create_unique_constraint call, since SQLite requires batch
        # mode (table recreation) for ALTER-style constraint additions but not for
        # constraints declared as part of the initial CREATE TABLE.
        sa.UniqueConstraint(
            "snapshot_date",
            "country_iso2",
            "role_bucket",
            name="uq_country_demand_snapshots_date_country_role",
        ),
    )
    op.create_index(
        "ix_country_demand_snapshots_snapshot_date",
        "country_demand_snapshots",
        ["snapshot_date"],
    )
    op.create_index(
        "ix_country_demand_snapshots_country_iso2",
        "country_demand_snapshots",
        ["country_iso2"],
    )
    op.create_index(
        "ix_country_demand_snapshots_role_bucket",
        "country_demand_snapshots",
        ["role_bucket"],
    )

    # Additive-only column: derived at ingestion via app.enrichers.jobspy.country_to_iso2()
    # (see app/modules/job_matching/models.py's JobPosting.country_iso2 docstring). NULL
    # for postings scraped before this column existed or where country could not be
    # determined — not backfilled by this migration.
    op.add_column("job_postings", sa.Column("country_iso2", sa.String(2), nullable=True))
    op.create_index(
        "ix_job_postings_country_iso2",
        "job_postings",
        ["country_iso2"],
    )


def downgrade() -> None:
    op.drop_index("ix_job_postings_country_iso2", table_name="job_postings")
    op.drop_column("job_postings", "country_iso2")

    op.drop_index("ix_country_demand_snapshots_role_bucket", table_name="country_demand_snapshots")
    op.drop_index("ix_country_demand_snapshots_country_iso2", table_name="country_demand_snapshots")
    op.drop_index(
        "ix_country_demand_snapshots_snapshot_date", table_name="country_demand_snapshots"
    )
    op.drop_table("country_demand_snapshots")
