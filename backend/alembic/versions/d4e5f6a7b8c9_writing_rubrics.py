"""writing_rubrics — rubric templates, dimensions, review scores, task.rubric_id

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-17 19:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'writing_rubrics',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('framework_id', sa.String(36), nullable=True),
        sa.Column('subject_id', sa.String(36), nullable=True),
        sa.Column('exam_type_id', sa.String(36), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['framework_id'], ['curriculum_frameworks.id']),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id']),
        sa.ForeignKeyConstraint(['exam_type_id'], ['exam_types.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_writing_rubrics_framework_id', 'writing_rubrics', ['framework_id'])
    op.create_index('ix_writing_rubrics_subject_id', 'writing_rubrics', ['subject_id'])
    op.create_index('ix_writing_rubrics_exam_type_id', 'writing_rubrics', ['exam_type_id'])
    op.create_index('ix_writing_rubrics_active', 'writing_rubrics', ['active'])

    op.create_table(
        'writing_rubric_dimensions',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('rubric_id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['rubric_id'], ['writing_rubrics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_writing_rubric_dimensions_rubric_id', 'writing_rubric_dimensions', ['rubric_id'])

    op.create_table(
        'writing_review_scores',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('review_id', sa.String(36), nullable=False),
        sa.Column('dimension_id', sa.String(36), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['review_id'], ['writing_reviews.id']),
        sa.ForeignKeyConstraint(['dimension_id'], ['writing_rubric_dimensions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('review_id', 'dimension_id', name='uq_review_score_review_dimension'),
        sa.CheckConstraint('rating >= 1 AND rating <= 5', name='ck_review_score_rating_range'),
    )
    op.create_index('ix_writing_review_scores_review_id', 'writing_review_scores', ['review_id'])
    op.create_index('ix_writing_review_scores_dimension_id', 'writing_review_scores', ['dimension_id'])

    op.add_column('writing_tasks', sa.Column('rubric_id', sa.String(36), nullable=True))
    op.create_index('ix_writing_tasks_rubric_id', 'writing_tasks', ['rubric_id'])
    op.create_foreign_key(
        'fk_writing_tasks_rubric_id', 'writing_tasks', 'writing_rubrics', ['rubric_id'], ['id']
    )


def downgrade() -> None:
    op.drop_constraint('fk_writing_tasks_rubric_id', 'writing_tasks', type_='foreignkey')
    op.drop_index('ix_writing_tasks_rubric_id', table_name='writing_tasks')
    op.drop_column('writing_tasks', 'rubric_id')

    op.drop_index('ix_writing_review_scores_dimension_id', table_name='writing_review_scores')
    op.drop_index('ix_writing_review_scores_review_id', table_name='writing_review_scores')
    op.drop_table('writing_review_scores')

    op.drop_index('ix_writing_rubric_dimensions_rubric_id', table_name='writing_rubric_dimensions')
    op.drop_table('writing_rubric_dimensions')

    op.drop_index('ix_writing_rubrics_active', table_name='writing_rubrics')
    op.drop_index('ix_writing_rubrics_exam_type_id', table_name='writing_rubrics')
    op.drop_index('ix_writing_rubrics_subject_id', table_name='writing_rubrics')
    op.drop_index('ix_writing_rubrics_framework_id', table_name='writing_rubrics')
    op.drop_table('writing_rubrics')
