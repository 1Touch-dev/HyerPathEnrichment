"""Create brands table, users.signup_brand_id, and recruiter_candidate_assignments
(Decision: docs/adr/0019-tenancy-model.md).

Revision ID: 052_create_brands_and_candidate_assignments
Revises: 051_merge_machine2_parallel_track_heads
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "052_create_brands_and_candidate_assignments"
down_revision: str | Sequence[str] | None = "051_merge_machine2_parallel_track_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def _json_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB
    return sa.JSON


def upgrade() -> None:
    bind = op.get_bind()
    uuid_type = _uuid_type()

    op.create_table(
        "brands",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("custom_domain", sa.String(255), nullable=True),
        sa.Column("chatbot_config", _json_type(), nullable=True),
        sa.Column("landing_page_tier_config", _json_type(), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    # Inline FKs/unique indexes (not a post-hoc op.create_unique_constraint/
    # create_foreign_key ALTER) — SQLite has no ALTER-based constraint support
    # even for a table just created in this same migration; unique indexes and
    # column-level sa.ForeignKey(...) work natively on both dialects. Matches
    # the existing convention in 027_portfolio_profiles.py.
    op.create_index("ix_brands_slug", "brands", ["slug"], unique=True)

    # users already exists (created in an earlier migration) — SQLite has no
    # ALTER-based constraint support, so adding a column with an inline FK
    # requires batch mode (recreate-table) there, matching the existing
    # pattern in 046_admin_seed_module4_permissions.py. Postgres supports the
    # direct ALTER.
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.add_column(sa.Column("signup_brand_id", uuid_type, nullable=True))
            batch_op.create_index("ix_users_signup_brand_id", ["signup_brand_id"])
            batch_op.create_foreign_key(
                "fk_users_signup_brand_id_brands",
                "brands",
                ["signup_brand_id"],
                ["id"],
                ondelete="SET NULL",
            )
    else:
        op.add_column("users", sa.Column("signup_brand_id", uuid_type, nullable=True))
        op.create_index("ix_users_signup_brand_id", "users", ["signup_brand_id"])
        op.create_foreign_key(
            "fk_users_signup_brand_id_brands",
            "users",
            "brands",
            ["signup_brand_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.create_table(
        "recruiter_candidate_assignments",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "recruiter_user_id",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_rca_recruiter_user_id_users"),
            nullable=False,
        ),
        sa.Column(
            "candidate_user_id",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_rca_candidate_user_id_users"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_recruiter_candidate_assignments_recruiter_user_id",
        "recruiter_candidate_assignments",
        ["recruiter_user_id"],
    )
    op.create_index(
        "ix_recruiter_candidate_assignments_candidate_user_id",
        "recruiter_candidate_assignments",
        ["candidate_user_id"],
    )
    op.create_index(
        "uq_recruiter_candidate_assignment",
        "recruiter_candidate_assignments",
        ["recruiter_user_id", "candidate_user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("recruiter_candidate_assignments")

    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if is_sqlite:
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.drop_index("ix_users_signup_brand_id")
            batch_op.drop_constraint("fk_users_signup_brand_id_brands", type_="foreignkey")
            batch_op.drop_column("signup_brand_id")
    else:
        op.drop_index("ix_users_signup_brand_id", table_name="users")
        op.drop_constraint("fk_users_signup_brand_id_brands", "users", type_="foreignkey")
        op.drop_column("users", "signup_brand_id")

    op.drop_index("ix_brands_slug", table_name="brands")
    op.drop_table("brands")
