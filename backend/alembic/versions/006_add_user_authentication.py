"""Add user authentication and related tables

Revision ID: 006_add_user_authentication
Revises: 005_add_is_internal_flag
Create Date: 2026-07-31 19:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '006_add_user_authentication'
down_revision: Union[str, Sequence[str], None] = '005_add_is_internal_flag'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from alembic import context

    bind = context.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'

    # Create users table
    if is_sqlite:
        op.create_table(
            'users',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('email', sa.String(320), nullable=False),
            sa.Column('hashed_password', sa.String(1024), nullable=True),
            sa.Column('first_name', sa.String(100), nullable=False),
            sa.Column('last_name', sa.String(100), nullable=False),
            sa.Column('avatar_url', sa.String(1024), nullable=True),
            sa.Column('oauth_provider', sa.String(32), nullable=True),
            sa.Column('oauth_id', sa.String(255), nullable=True),
            sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
            sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('verification_token', sa.String(512), nullable=True),
            sa.Column('verification_sent_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        )
    else:
        op.create_table(
            'users',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('email', sa.String(320), nullable=False),
            sa.Column('hashed_password', sa.String(1024), nullable=True),
            sa.Column('first_name', sa.String(100), nullable=False),
            sa.Column('last_name', sa.String(100), nullable=False),
            sa.Column('avatar_url', sa.String(1024), nullable=True),
            sa.Column('oauth_provider', sa.String(32), nullable=True),
            sa.Column('oauth_id', sa.String(255), nullable=True),
            sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('verification_token', sa.String(512), nullable=True),
            sa.Column('verification_sent_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_deleted_at', 'users', ['deleted_at'])

    # Create oauth_accounts table
    if is_sqlite:
        op.create_table(
            'oauth_accounts',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('user_id', sa.String(36), nullable=False),
            sa.Column('oauth_name', sa.String(100), nullable=False),
            sa.Column('access_token', sa.String(1024), nullable=False),
            sa.Column('refresh_token', sa.String(1024), nullable=True),
            sa.Column('expires_at', sa.Integer(), nullable=True),
            sa.Column('account_id', sa.String(320), nullable=False),
            sa.Column('account_email', sa.String(320), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        )
    else:
        op.create_table(
            'oauth_accounts',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('oauth_name', sa.String(100), nullable=False),
            sa.Column('access_token', sa.String(1024), nullable=False),
            sa.Column('refresh_token', sa.String(1024), nullable=True),
            sa.Column('expires_at', sa.Integer(), nullable=True),
            sa.Column('account_id', sa.String(320), nullable=False),
            sa.Column('account_email', sa.String(320), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        )

    op.create_index('ix_oauth_accounts_user_id', 'oauth_accounts', ['user_id'])

    # Create refresh_tokens table
    op.create_table(
        'refresh_tokens',
        sa.Column('token', sa.String(512), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True) if not is_sqlite else sa.String(36), nullable=False),
        sa.Column('used', sa.Boolean(), nullable=False, server_default='0' if is_sqlite else 'false'),
        sa.Column('parent_token', sa.String(512), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id'])

    # Create token_blacklist table
    op.create_table(
        'token_blacklist',
        sa.Column('jti', sa.String(64), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True) if not is_sqlite else sa.String(36), nullable=False),
        sa.Column('token_type', sa.String(16), nullable=False),
        sa.Column('reason', sa.String(255), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_token_blacklist_user_id', 'token_blacklist', ['user_id'])

    # Create email_verification_tokens table
    op.create_table(
        'email_verification_tokens',
        sa.Column('token', sa.String(512), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True) if not is_sqlite else sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_email_verification_tokens_user_id', 'email_verification_tokens', ['user_id'])
    op.create_index('ix_email_verification_tokens_expires_at', 'email_verification_tokens', ['expires_at'])

    # Create logged_out_tokens table
    op.create_table(
        'logged_out_tokens',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True) if not is_sqlite else sa.String(36), nullable=False),
        sa.Column('token_jti', sa.String(64), nullable=False),
        sa.Column('logged_out_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_logged_out_tokens_user_id', 'logged_out_tokens', ['user_id'])
    op.create_index('ix_logged_out_tokens_token_jti', 'logged_out_tokens', ['token_jti'], unique=True)
    op.create_index('ix_logged_out_tokens_expires_at', 'logged_out_tokens', ['expires_at'])

    # Create auth_audit_logs table
    if is_sqlite:
        op.create_table(
            'auth_audit_logs',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('user_id', sa.String(36), nullable=True),
            sa.Column('event_type', sa.String(64), nullable=False),
            sa.Column('success', sa.Boolean(), nullable=False, server_default='1'),
            sa.Column('ip_address', sa.String(45), nullable=False),
            sa.Column('user_agent', sa.String(512), nullable=True),
            sa.Column('email_attempted', sa.String(320), nullable=True),
            sa.Column('failure_reason', sa.String(255), nullable=True),
            sa.Column('metadata', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        )
    else:
        op.create_table(
            'auth_audit_logs',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('event_type', sa.String(64), nullable=False),
            sa.Column('success', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('ip_address', sa.String(45), nullable=False),
            sa.Column('user_agent', sa.String(512), nullable=True),
            sa.Column('email_attempted', sa.String(320), nullable=True),
            sa.Column('failure_reason', sa.String(255), nullable=True),
            sa.Column('metadata', postgresql.JSONB(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        )

    op.create_index('ix_auth_audit_logs_user_id', 'auth_audit_logs', ['user_id'])
    op.create_index('ix_auth_audit_logs_event_type', 'auth_audit_logs', ['event_type'])
    op.create_index('ix_auth_audit_logs_ip_address', 'auth_audit_logs', ['ip_address'])
    op.create_index('ix_auth_audit_logs_created_at', 'auth_audit_logs', ['created_at'])

    # Add user_id column to jobs table
    if is_sqlite:
        with op.batch_alter_table('jobs', schema=None) as batch_op:
            batch_op.add_column(sa.Column('user_id', sa.String(36), nullable=True))
            batch_op.create_foreign_key('fk_jobs_user_id', 'users', ['user_id'], ['id'], ondelete='SET NULL')
            batch_op.create_index('ix_jobs_user_id', ['user_id'])
    else:
        op.add_column('jobs', sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key('fk_jobs_user_id', 'jobs', 'users', ['user_id'], ['id'], ondelete='SET NULL')
        op.create_index('ix_jobs_user_id', 'jobs', ['user_id'])


def downgrade() -> None:
    from alembic import context

    bind = context.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'

    # Remove user_id from jobs table
    if is_sqlite:
        with op.batch_alter_table('jobs', schema=None) as batch_op:
            batch_op.drop_index('ix_jobs_user_id')
            batch_op.drop_constraint('fk_jobs_user_id', type_='foreignkey')
            batch_op.drop_column('user_id')
    else:
        op.drop_index('ix_jobs_user_id', table_name='jobs')
        op.drop_constraint('fk_jobs_user_id', 'jobs', type_='foreignkey')
        op.drop_column('jobs', 'user_id')

    # Drop tables in reverse order
    op.drop_index('ix_auth_audit_logs_created_at', table_name='auth_audit_logs')
    op.drop_index('ix_auth_audit_logs_ip_address', table_name='auth_audit_logs')
    op.drop_index('ix_auth_audit_logs_event_type', table_name='auth_audit_logs')
    op.drop_index('ix_auth_audit_logs_user_id', table_name='auth_audit_logs')
    op.drop_table('auth_audit_logs')

    op.drop_index('ix_logged_out_tokens_expires_at', table_name='logged_out_tokens')
    op.drop_index('ix_logged_out_tokens_token_jti', table_name='logged_out_tokens')
    op.drop_index('ix_logged_out_tokens_user_id', table_name='logged_out_tokens')
    op.drop_table('logged_out_tokens')

    op.drop_index('ix_email_verification_tokens_expires_at', table_name='email_verification_tokens')
    op.drop_index('ix_email_verification_tokens_user_id', table_name='email_verification_tokens')
    op.drop_table('email_verification_tokens')

    op.drop_index('ix_token_blacklist_user_id', table_name='token_blacklist')
    op.drop_table('token_blacklist')

    op.drop_index('ix_refresh_tokens_user_id', table_name='refresh_tokens')
    op.drop_table('refresh_tokens')

    op.drop_index('ix_oauth_accounts_user_id', table_name='oauth_accounts')
    op.drop_table('oauth_accounts')

    op.drop_index('ix_users_deleted_at', table_name='users')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
