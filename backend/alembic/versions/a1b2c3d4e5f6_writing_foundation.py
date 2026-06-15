"""writing_foundation

Revision ID: a1b2c3d4e5f6
Revises: f8a9b0c1d2e3
Create Date: 2026-06-16 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f8a9b0c1d2e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'writing_tasks',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('word_limit', sa.Integer(), nullable=True),
        sa.Column('recommended_time_minutes', sa.Integer(), nullable=True),
        sa.Column('subject_id', sa.String(36), nullable=False),
        sa.Column('exam_type_id', sa.String(36), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('created_by_admin_id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id']),
        sa.ForeignKeyConstraint(['exam_type_id'], ['exam_types.id']),
        sa.ForeignKeyConstraint(['created_by_admin_id'], ['admin_profiles.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_writing_tasks_subject_id', 'writing_tasks', ['subject_id'])
    op.create_index('ix_writing_tasks_exam_type_id', 'writing_tasks', ['exam_type_id'])
    op.create_index('ix_writing_tasks_status', 'writing_tasks', ['status'])

    op.create_table(
        'writing_submissions',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('writing_task_id', sa.String(36), nullable=False),
        sa.Column('student_id', sa.String(36), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('word_count', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['writing_task_id'], ['writing_tasks.id']),
        sa.ForeignKeyConstraint(['student_id'], ['student_profiles.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_writing_submissions_writing_task_id', 'writing_submissions', ['writing_task_id'])
    op.create_index('ix_writing_submissions_student_id', 'writing_submissions', ['student_id'])
    op.create_index('ix_writing_submissions_status', 'writing_submissions', ['status'])


def downgrade() -> None:
    op.drop_index('ix_writing_submissions_status', table_name='writing_submissions')
    op.drop_index('ix_writing_submissions_student_id', table_name='writing_submissions')
    op.drop_index('ix_writing_submissions_writing_task_id', table_name='writing_submissions')
    op.drop_table('writing_submissions')
    op.drop_index('ix_writing_tasks_status', table_name='writing_tasks')
    op.drop_index('ix_writing_tasks_exam_type_id', table_name='writing_tasks')
    op.drop_index('ix_writing_tasks_subject_id', table_name='writing_tasks')
    op.drop_table('writing_tasks')
