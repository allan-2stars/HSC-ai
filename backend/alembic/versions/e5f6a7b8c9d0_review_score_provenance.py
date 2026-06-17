"""review_score_provenance — created_by_admin_id + source on writing_review_scores

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-17 20:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'writing_review_scores',
        sa.Column('created_by_admin_id', sa.String(36), nullable=True),
    )
    op.add_column(
        'writing_review_scores',
        sa.Column('source', sa.String(16), nullable=False, server_default='human'),
    )
    op.create_foreign_key(
        'fk_review_scores_created_by_admin',
        'writing_review_scores', 'admin_profiles',
        ['created_by_admin_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_review_scores_created_by_admin', 'writing_review_scores', type_='foreignkey')
    op.drop_column('writing_review_scores', 'source')
    op.drop_column('writing_review_scores', 'created_by_admin_id')
