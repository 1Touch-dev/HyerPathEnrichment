"""Add digest, role, revocation, and redemption identity to staff invites.

Revision ID: 065_staff_invite_security
Revises: 064_impersonation_session_hardening
Create Date: 2026-09-03
"""

import hashlib
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "065_staff_invite_security"
down_revision: str | Sequence[str] | None = "064_impersonation_session_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_type() -> sa.types.TypeEngine:
    if op.get_bind().dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def _create_foreign_keys() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("staff_invites") as batch_op:
            batch_op.create_foreign_key(
                "fk_staff_invites_role_id_roles",
                "roles",
                ["role_id"],
                ["id"],
                ondelete="RESTRICT",
            )
            batch_op.create_foreign_key(
                "fk_staff_invites_accepted_by_user_id_users",
                "users",
                ["accepted_by_user_id"],
                ["id"],
                ondelete="RESTRICT",
            )
        return

    op.create_foreign_key(
        "fk_staff_invites_role_id_roles",
        "staff_invites",
        "roles",
        ["role_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_staff_invites_accepted_by_user_id_users",
        "staff_invites",
        "users",
        ["accepted_by_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def _drop_foreign_keys() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("staff_invites") as batch_op:
            batch_op.drop_constraint(
                "fk_staff_invites_accepted_by_user_id_users",
                type_="foreignkey",
            )
            batch_op.drop_constraint(
                "fk_staff_invites_role_id_roles",
                type_="foreignkey",
            )
        return

    op.drop_constraint(
        "fk_staff_invites_accepted_by_user_id_users",
        "staff_invites",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_staff_invites_role_id_roles",
        "staff_invites",
        type_="foreignkey",
    )


def _set_token_nullable(*, nullable: bool) -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("staff_invites") as batch_op:
            batch_op.alter_column(
                "token",
                existing_type=sa.String(64),
                existing_nullable=not nullable,
                nullable=nullable,
            )
        return
    op.alter_column(
        "staff_invites",
        "token",
        existing_type=sa.String(64),
        existing_nullable=not nullable,
        nullable=nullable,
    )


def upgrade() -> None:
    uuid_type = _uuid_type()
    op.add_column(
        "staff_invites",
        sa.Column("token_digest", sa.String(64), nullable=True),
    )
    op.add_column(
        "staff_invites",
        sa.Column("role_id", uuid_type, nullable=True),
    )
    op.add_column(
        "staff_invites",
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "staff_invites",
        sa.Column("accepted_by_user_id", uuid_type, nullable=True),
    )
    _create_foreign_keys()

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, token FROM staff_invites")).all()
    for invite_id, token in rows:
        bind.execute(
            sa.text("UPDATE staff_invites SET token_digest = :digest WHERE id = :id"),
            {
                "digest": hashlib.sha256(token.encode("utf-8")).hexdigest(),
                "id": invite_id,
            },
        )
    _set_token_nullable(nullable=True)

    recruiter_role_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM roles WHERE name = 'recruiter'")
    ).scalar_one()
    if recruiter_role_count != 1:
        raise RuntimeError("Cannot migrate staff invites without exactly one seeded recruiter role")

    bind.execute(
        sa.text(
            "UPDATE staff_invites SET role_id = "
            "(SELECT roles.id FROM roles WHERE roles.name = 'recruiter') "
            "WHERE role_name = 'recruiter'"
        )
    )
    # Unsafe historical grants are retained as evidence but made unredeemable.
    # Never translate admin/support/team_owner strings into live role IDs.
    bind.execute(
        sa.text(
            "UPDATE staff_invites SET revoked_at = COALESCE(created_at, CURRENT_TIMESTAMP) "
            "WHERE revoked_at IS NULL "
            "AND (role_name <> 'recruiter' OR role_id IS NULL)"
        )
    )
    # Expired rows must not occupy the partial active-email key after upgrade.
    bind.execute(
        sa.text(
            "UPDATE staff_invites SET revoked_at = expires_at "
            "WHERE accepted_at IS NULL AND revoked_at IS NULL "
            "AND expires_at < CURRENT_TIMESTAMP"
        )
    )
    # If historical data contains duplicate active recruiter invites, retain
    # every row but revoke all except the newest before adding uniqueness.
    bind.execute(
        sa.text(
            "UPDATE staff_invites SET revoked_at = COALESCE(created_at, CURRENT_TIMESTAMP) "
            "WHERE id IN ("
            "SELECT id FROM ("
            "SELECT id, ROW_NUMBER() OVER ("
            "PARTITION BY lower(email) ORDER BY created_at DESC, id DESC"
            ") AS invite_rank FROM staff_invites "
            "WHERE accepted_at IS NULL AND revoked_at IS NULL"
            ") AS ranked_invites WHERE invite_rank > 1"
            ")"
        )
    )
    # Maintenance-window expand: retain safe active plaintext only for
    # restored-schema recovery by a separately verified artifact that keeps
    # the hardened invite implementation. This never permits a pre-hardening
    # binary. Clear rows vulnerable code could otherwise redeem unsafely
    # (invalid roles or superseded duplicate actives). Accepted/expired safe
    # rows are handled by acknowledged post-drain cleanup, not migration.
    bind.execute(
        sa.text(
            "UPDATE staff_invites SET token = NULL "
            "WHERE role_name <> 'recruiter' OR role_id IS NULL "
            "OR (revoked_at IS NOT NULL AND accepted_at IS NULL "
            "AND expires_at >= CURRENT_TIMESTAMP)"
        )
    )

    op.create_index(
        "ix_staff_invites_token_digest",
        "staff_invites",
        ["token_digest"],
        unique=True,
    )
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX uq_staff_invites_active_email "
            "ON staff_invites (lower(email)) "
            "WHERE accepted_at IS NULL AND revoked_at IS NULL"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    evidence_count = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM staff_invites "
            "WHERE revoked_at IS NOT NULL OR accepted_by_user_id IS NOT NULL"
        )
    ).scalar_one()
    if evidence_count:
        raise RuntimeError(
            "Cannot downgrade 065_staff_invite_security: "
            "revocation or redemption identity evidence exists"
        )
    missing_plaintext_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM staff_invites WHERE token IS NULL")
    ).scalar_one()
    if missing_plaintext_count:
        raise RuntimeError(
            "Cannot downgrade 065_staff_invite_security: plaintext invite "
            "credentials were intentionally discarded"
        )

    op.drop_index("uq_staff_invites_active_email", table_name="staff_invites")
    op.drop_index("ix_staff_invites_token_digest", table_name="staff_invites")
    _drop_foreign_keys()
    _set_token_nullable(nullable=False)
    op.drop_column("staff_invites", "accepted_by_user_id")
    op.drop_column("staff_invites", "revoked_at")
    op.drop_column("staff_invites", "role_id")
    op.drop_column("staff_invites", "token_digest")
