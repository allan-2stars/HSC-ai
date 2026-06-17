"""writing_review_workflow — reviews table, versioned feedback, append-only trigger

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-17 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'writing_reviews',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('submission_id', sa.String(36), nullable=False),
        sa.Column('reviewer_admin_id', sa.String(36), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('review_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['submission_id'], ['writing_submissions.id']),
        sa.ForeignKeyConstraint(['reviewer_admin_id'], ['admin_profiles.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('submission_id', name='uq_writing_review_submission'),
    )
    op.create_index('ix_writing_reviews_submission_id', 'writing_reviews', ['submission_id'])
    op.create_index('ix_writing_reviews_reviewer_admin_id', 'writing_reviews', ['reviewer_admin_id'])
    op.create_index('ix_writing_reviews_status', 'writing_reviews', ['status'])

    op.create_table(
        'writing_feedback',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('review_id', sa.String(36), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('overall_comment', sa.Text(), nullable=False),
        sa.Column('dimensions', sa.JSON(), nullable=True),
        sa.Column('created_by_admin_id', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['review_id'], ['writing_reviews.id']),
        sa.ForeignKeyConstraint(['created_by_admin_id'], ['admin_profiles.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('review_id', 'version', name='uq_writing_feedback_review_version'),
    )
    op.create_index('ix_writing_feedback_review_id', 'writing_feedback', ['review_id'])

    # Append-only enforcement: feedback rows may be inserted but never modified
    # or removed. This protects the feedback audit trail at the database level.
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_writing_feedback_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'writing_feedback is append-only';
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_writing_feedback_append_only
        BEFORE UPDATE OR DELETE ON writing_feedback
        FOR EACH ROW EXECUTE FUNCTION prevent_writing_feedback_mutation()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_writing_feedback_append_only ON writing_feedback")
    op.execute("DROP FUNCTION IF EXISTS prevent_writing_feedback_mutation()")
    op.drop_index('ix_writing_feedback_review_id', table_name='writing_feedback')
    op.drop_table('writing_feedback')
    op.drop_index('ix_writing_reviews_status', table_name='writing_reviews')
    op.drop_index('ix_writing_reviews_reviewer_admin_id', table_name='writing_reviews')
    op.drop_index('ix_writing_reviews_submission_id', table_name='writing_reviews')
    op.drop_table('writing_reviews')
