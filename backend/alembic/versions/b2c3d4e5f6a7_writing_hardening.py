"""writing_hardening — unique constraint + immutability trigger + content col

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-16 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    op.create_unique_constraint(
        'uq_writing_submission_task_student',
        'writing_submissions',
        ['writing_task_id', 'student_id'],
    )
    # Immutability trigger — create function first, then trigger (separate calls for asyncpg)
    # Deny-by-default: once a response is submitted, no column on the row may
    # change. Review/feedback data must live in a separate table, not mutate
    # the submitted response.
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_submitted_writing_update()
        RETURNS TRIGGER AS $$
        BEGIN
            IF OLD.status = 'submitted' THEN
                RAISE EXCEPTION 'Cannot modify a submitted writing response';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_writing_submission_immutable
        BEFORE UPDATE ON writing_submissions
        FOR EACH ROW EXECUTE FUNCTION prevent_submitted_writing_update()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_writing_submission_immutable ON writing_submissions")
    op.execute("DROP FUNCTION IF EXISTS prevent_submitted_writing_update()")
    op.drop_constraint(
        'uq_writing_submission_task_student',
        'writing_submissions',
        type_='unique',
    )
