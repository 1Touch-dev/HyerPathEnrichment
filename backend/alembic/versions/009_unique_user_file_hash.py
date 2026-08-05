"""Add unique constraint on user_id + file_hash for document deduplication

Revision ID: 009_unique_user_file_hash
Revises: 008_candidate_documents
Create Date: 2026-08-05 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '009_unique_user_file_hash'
down_revision: Union[str, None] = '008_candidate_documents'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add unique constraint and composite index on (user_id, file_hash)."""
    # Create unique constraint
    op.create_unique_constraint(
        'uq_candidate_documents_user_file',
        'candidate_documents',
        ['user_id', 'file_hash']
    )

    # Create composite index for faster lookups (redundant with unique constraint but explicit)
    op.create_index(
        'idx_candidate_documents_user_file',
        'candidate_documents',
        ['user_id', 'file_hash']
    )


def downgrade() -> None:
    """Remove unique constraint and composite index."""
    op.drop_index('idx_candidate_documents_user_file', table_name='candidate_documents')
    op.drop_constraint('uq_candidate_documents_user_file', 'candidate_documents', type_='unique')
