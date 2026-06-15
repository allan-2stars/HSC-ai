"""last_login_at_index

Revision ID: f8a9b0c1d2e3
Revises: e2d7f9a0b1c3
Create Date: 2026-06-15 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'f8a9b0c1d2e3'
down_revision: Union[str, None] = 'e2d7f9a0b1c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_users_last_login_at', 'users', ['last_login_at'])


def downgrade() -> None:
    op.drop_index('ix_users_last_login_at', table_name='users')
