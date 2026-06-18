"""writing_feedback_drafts — AI draft feedback for writing reviews (M5.3)

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-18 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'writing_feedback_drafts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('review_id', sa.String(36), sa.ForeignKey('writing_reviews.id'), nullable=False),
        sa.Column('provider', sa.String(32), nullable=False),
        sa.Column('model', sa.String(64), nullable=False, server_default=''),
        sa.Column('prompt_version', sa.String(32), nullable=False),
        sa.Column('status', sa.String(16), nullable=False, server_default='generated'),
        sa.Column('draft_feedback_json', sa.JSON(), nullable=False),
        sa.Column('generated_by_admin_id', sa.String(36), sa.ForeignKey('admin_profiles.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_writing_feedback_drafts_review_id', 'writing_feedback_drafts', ['review_id'])
    op.create_index('ix_writing_feedback_drafts_status', 'writing_feedback_drafts', ['status'])


def downgrade() -> None:
    op.drop_index('ix_writing_feedback_drafts_status', table_name='writing_feedback_drafts')
    op.drop_index('ix_writing_feedback_drafts_review_id', table_name='writing_feedback_drafts')
    op.drop_table('writing_feedback_drafts')
