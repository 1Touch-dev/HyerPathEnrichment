"""Widen generated auth JTI and encrypted MFA secret fields.

Revision ID: 062_widen_auth_secret_fields
Revises: 061_team_owner_full_desk_grants
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "062_widen_auth_secret_fields"
down_revision: str | Sequence[str] | None = "061_team_owner_full_desk_grants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_WIDTH = 64
TOKEN_JTI_WIDTH = 128
MFA_SECRET_WIDTH = 255


def _alter_widths(
    *,
    existing_token_jti_width: int,
    token_jti_width: int,
    existing_mfa_secret_width: int,
    mfa_secret_width: int,
) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("logged_out_tokens", schema=None) as batch_op:
            batch_op.alter_column(
                "token_jti",
                existing_type=sa.String(existing_token_jti_width),
                type_=sa.String(token_jti_width),
                existing_nullable=False,
            )
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.alter_column(
                "mfa_secret",
                existing_type=sa.String(existing_mfa_secret_width),
                type_=sa.String(mfa_secret_width),
                existing_nullable=True,
            )
        return

    op.alter_column(
        "logged_out_tokens",
        "token_jti",
        existing_type=sa.String(existing_token_jti_width),
        type_=sa.String(token_jti_width),
        existing_nullable=False,
    )
    op.alter_column(
        "users",
        "mfa_secret",
        existing_type=sa.String(existing_mfa_secret_width),
        type_=sa.String(mfa_secret_width),
        existing_nullable=True,
    )


def upgrade() -> None:
    _alter_widths(
        existing_token_jti_width=OLD_WIDTH,
        token_jti_width=TOKEN_JTI_WIDTH,
        existing_mfa_secret_width=OLD_WIDTH,
        mfa_secret_width=MFA_SECRET_WIDTH,
    )


def downgrade() -> None:
    bind = op.get_bind()
    oversized_jtis = bind.execute(
        sa.text("SELECT COUNT(*) FROM logged_out_tokens WHERE length(token_jti) > :old_width"),
        {"old_width": OLD_WIDTH},
    ).scalar_one()
    oversized_mfa_secrets = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM users "
            "WHERE mfa_secret IS NOT NULL AND length(mfa_secret) > :old_width"
        ),
        {"old_width": OLD_WIDTH},
    ).scalar_one()
    if oversized_jtis or oversized_mfa_secrets:
        raise RuntimeError(
            "Cannot downgrade 062_widen_auth_secret_fields to VARCHAR(64): "
            f"{oversized_jtis} logged_out_tokens.token_jti value(s) and "
            f"{oversized_mfa_secrets} users.mfa_secret value(s) exceed 64 characters"
        )

    _alter_widths(
        existing_token_jti_width=TOKEN_JTI_WIDTH,
        token_jti_width=OLD_WIDTH,
        existing_mfa_secret_width=MFA_SECRET_WIDTH,
        mfa_secret_width=OLD_WIDTH,
    )
