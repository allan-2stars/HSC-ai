"""score_suggestions

Revision ID: a8b9c0d1e2f3
Revises: a7b8c9d0e1f2
Create Date: 2026-06-19 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a8b9c0d1e2f3'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'writing_score_suggestions',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('review_id', sa.String(36), nullable=False),
        sa.Column('rubric_version_id', sa.String(36), nullable=False),
        sa.Column('dimension_version_id', sa.String(36), nullable=False),
        sa.Column('suggested_rating', sa.Integer(), nullable=True),
        sa.Column('suggested_comment', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('provider', sa.String(32), nullable=False),
        sa.Column('model', sa.String(64), nullable=False),
        sa.Column('prompt_version', sa.String(32), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('generated_by_admin_id', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['review_id'], ['writing_reviews.id']),
        sa.ForeignKeyConstraint(['rubric_version_id'], ['writing_rubric_versions.id']),
        sa.ForeignKeyConstraint(['dimension_version_id'], ['writing_rubric_dimension_versions.id']),
        sa.ForeignKeyConstraint(['generated_by_admin_id'], ['admin_profiles.id']),
        sa.CheckConstraint(
            "suggested_rating IS NULL OR (suggested_rating >= 1 AND suggested_rating <= 5)",
            name="ck_score_suggestion_rating_range",
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_score_suggestions_review_id', 'writing_score_suggestions', ['review_id'])
    op.create_index('ix_score_suggestions_status', 'writing_score_suggestions', ['status'])
    op.create_index('ix_score_suggestions_rvid', 'writing_score_suggestions', ['rubric_version_id'])
    op.create_index('ix_score_suggestions_dvid', 'writing_score_suggestions', ['dimension_version_id'])


def downgrade() -> None:
    op.drop_index('ix_score_suggestions_dvid', table_name='writing_score_suggestions')
    op.drop_index('ix_score_suggestions_rvid', table_name='writing_score_suggestions')
    op.drop_index('ix_score_suggestions_status', table_name='writing_score_suggestions')
    op.drop_index('ix_score_suggestions_review_id', table_name='writing_score_suggestions')
    op.drop_table('writing_score_suggestions')
