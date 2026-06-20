"""disputes_reopen

Revision ID: a9b0c1d2e3f4
Revises: a8b9c0d1e2f3
Create Date: 2026-06-19 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a9b0c1d2e3f4'
down_revision: Union[str, None] = 'a8b9c0d1e2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Disputes table
    op.create_table(
        'writing_review_disputes',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('review_id', sa.String(36), nullable=False),
        sa.Column('raised_by_user_id', sa.String(36), nullable=True),
        sa.Column('raised_by_role', sa.String(16), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('admin_response', sa.Text(), nullable=True),
        sa.Column('resolved_by_admin_id', sa.String(36), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['review_id'], ['writing_reviews.id']),
        sa.ForeignKeyConstraint(['raised_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['resolved_by_admin_id'], ['admin_profiles.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_disputes_review_id', 'writing_review_disputes', ['review_id'])
    op.create_index('ix_disputes_status', 'writing_review_disputes', ['status'])

    # 2. Publication version snapshots
    op.create_table(
        'writing_review_publication_versions',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('review_id', sa.String(36), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('rubric_version_id', sa.String(36), nullable=True),
        sa.Column('feedback_id', sa.String(36), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('published_by_admin_id', sa.String(36), nullable=True),
        sa.Column('snapshot_json', sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(['review_id'], ['writing_reviews.id']),
        sa.ForeignKeyConstraint(['rubric_version_id'], ['writing_rubric_versions.id']),
        sa.ForeignKeyConstraint(['feedback_id'], ['writing_feedback.id']),
        sa.ForeignKeyConstraint(['published_by_admin_id'], ['admin_profiles.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_pub_versions_review_id', 'writing_review_publication_versions', ['review_id'])


def downgrade() -> None:
    op.drop_index('ix_pub_versions_review_id', table_name='writing_review_publication_versions')
    op.drop_table('writing_review_publication_versions')
    op.drop_index('ix_disputes_status', table_name='writing_review_disputes')
    op.drop_index('ix_disputes_review_id', table_name='writing_review_disputes')
    op.drop_table('writing_review_disputes')
    # Cannot remove enum value from PostgreSQL — leave 'reopened' in place
