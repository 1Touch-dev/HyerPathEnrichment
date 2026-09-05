"""Add FK from question_attempts.question_id to interview_questions, and
personalization columns to interview_questions.

Revision ID: 036_question_attempt_fk_and_personalization
Revises: 032_portfolio_item_image_url
Create Date: 2026-08-14

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "036_question_attempt_fk_and_personalization"
down_revision: str | Sequence[str] | None = "032_portfolio_item_image_url"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add FK constraint on question_attempts.question_id and personalization columns."""
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)

    # Existing rows with a question_id that does not exist in interview_questions
    # (possible today, since nothing enforced it) must be nulled out first, or
    # the FK creation below will fail on any environment with real data.
    op.execute(
        """
        UPDATE question_attempts
        SET question_id = NULL
        WHERE question_id IS NOT NULL
          AND question_id NOT IN (SELECT id FROM interview_questions)
        """
    )
    with op.batch_alter_table("question_attempts") as batch_op:
        batch_op.create_foreign_key(
            "fk_question_attempts_question_id",
            "interview_questions",
            ["question_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # Personalization columns (phase2_module3.md Decision 1). Batch mode is
    # required here too: SQLite cannot ALTER-add a column with an inline FK
    # constraint outside of the copy-and-move batch strategy.
    with op.batch_alter_table("interview_questions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "personalized_for_user_id",
                uuid_type,
                sa.ForeignKey(
                    "users.id",
                    ondelete="CASCADE",
                    name="fk_interview_questions_personalized_for_user_id",
                ),
                nullable=True,
            )
        )
        batch_op.add_column(
            # Short summary of skills/role used to generate this question, for audit.
            sa.Column("generation_context", sa.Text(), nullable=True)
        )
        batch_op.create_index(
            "ix_interview_questions_personalized_for_user_id",
            ["personalized_for_user_id"],
        )


def downgrade() -> None:
    """Remove personalization columns and the question_attempts FK constraint."""
    with op.batch_alter_table("interview_questions") as batch_op:
        batch_op.drop_index("ix_interview_questions_personalized_for_user_id")
        batch_op.drop_column("generation_context")
        batch_op.drop_column("personalized_for_user_id")
    with op.batch_alter_table("question_attempts") as batch_op:
        batch_op.drop_constraint("fk_question_attempts_question_id", type_="foreignkey")
    # NOTE: batch mode above; downgrade of the personalized_for_user_id FK is
    # implicit in dropping the column via batch_alter_table, so no separate
    # drop_constraint is needed for fk_interview_questions_personalized_for_user_id.
