"""content_quality_review

Revision ID: c1f3e8a7b2d4
Revises: 4a60f9fbe0c7
Create Date: 2026-06-14 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c1f3e8a7b2d4'
down_revision: Union[str, None] = '4a60f9fbe0c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'question_quality_reviews',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('question_id', sa.String(36), nullable=False),
        sa.Column('reviewer_admin_id', sa.String(36), nullable=True),
        sa.Column('correctness_score', sa.SmallInteger(), nullable=False, server_default='3'),
        sa.Column('outcome_alignment_score', sa.SmallInteger(), nullable=False, server_default='3'),
        sa.Column('difficulty_score', sa.SmallInteger(), nullable=False, server_default='3'),
        sa.Column('explanation_score', sa.SmallInteger(), nullable=False, server_default='3'),
        sa.Column('overall_score', sa.SmallInteger(), nullable=False, server_default='3'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ['question_id'], ['questions.id'],
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['reviewer_admin_id'], ['admin_profiles.id'],
            ondelete='SET NULL',
        ),
        sa.CheckConstraint(
            'correctness_score BETWEEN 1 AND 5',
            name='ck_quality_correctness_range',
        ),
        sa.CheckConstraint(
            'outcome_alignment_score BETWEEN 1 AND 5',
            name='ck_quality_outcome_alignment_range',
        ),
        sa.CheckConstraint(
            'difficulty_score BETWEEN 1 AND 5',
            name='ck_quality_difficulty_range',
        ),
        sa.CheckConstraint(
            'explanation_score BETWEEN 1 AND 5',
            name='ck_quality_explanation_range',
        ),
        sa.CheckConstraint(
            'overall_score BETWEEN 1 AND 5',
            name='ck_quality_overall_range',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_question_quality_reviews_question_id'), 'question_quality_reviews', ['question_id'])
    op.create_index(op.f('ix_question_quality_reviews_reviewer_admin_id'), 'question_quality_reviews', ['reviewer_admin_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_question_quality_reviews_reviewer_admin_id'), table_name='question_quality_reviews')
    op.drop_index(op.f('ix_question_quality_reviews_question_id'), table_name='question_quality_reviews')
    op.drop_table('question_quality_reviews')
