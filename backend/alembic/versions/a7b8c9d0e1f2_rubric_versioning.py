"""rubric_versioning

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-19 00:00:00.000000

This migration is fully idempotent — each step checks whether the target object
already exists before creating/altering it so it can be safely re-run after a
partial failure.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    row = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_name = :t"
    ), {"t": name}).fetchone()
    return row is not None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    row = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.columns WHERE table_name = :t AND column_name = :c"
    ), {"t": table, "c": column}).fetchone()
    return row is not None


def _constraint_exists(name: str) -> bool:
    conn = op.get_bind()
    row = conn.execute(sa.text(
        "SELECT 1 FROM pg_constraint WHERE conname = :n"
    ), {"n": name}).fetchone()
    return row is not None


def upgrade() -> None:
    # 1. Rubric version tables
    if not _table_exists('writing_rubric_versions'):
        op.create_table(
            'writing_rubric_versions',
            sa.Column('id', sa.String(36), nullable=False),
            sa.Column('rubric_id', sa.String(36), nullable=False),
            sa.Column('version_number', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('active', sa.Boolean(), nullable=False),
            sa.Column('created_by_admin_id', sa.String(36), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(['rubric_id'], ['writing_rubrics.id']),
            sa.ForeignKeyConstraint(['created_by_admin_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_writing_rubric_versions_rubric_id', 'writing_rubric_versions', ['rubric_id'])
    else:
        # Table exists from a failed prior run. Fix the FK from admin_profiles → users.
        op.execute("ALTER TABLE writing_rubric_versions DROP CONSTRAINT IF EXISTS writing_rubric_versions_created_by_admin_id_fkey")
        op.execute("ALTER TABLE writing_rubric_versions ADD CONSTRAINT writing_rubric_versions_created_by_admin_id_fkey FOREIGN KEY (created_by_admin_id) REFERENCES users(id)")

    if not _table_exists('writing_rubric_dimension_versions'):
        op.create_table(
            'writing_rubric_dimension_versions',
            sa.Column('id', sa.String(36), nullable=False),
            sa.Column('rubric_version_id', sa.String(36), nullable=False),
            sa.Column('original_dimension_id', sa.String(36), nullable=True),
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('display_order', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['rubric_version_id'], ['writing_rubric_versions.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['original_dimension_id'], ['writing_rubric_dimensions.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_writing_rubric_dimversions_rvid', 'writing_rubric_dimension_versions', ['rubric_version_id'])
    else:
        # Fix FK constraint — drop old, re-add with SET NULL
        op.execute("ALTER TABLE writing_rubric_dimension_versions DROP CONSTRAINT IF EXISTS writing_rubric_dimension_versions_original_dimension_id_fkey")
        op.execute("ALTER TABLE writing_rubric_dimension_versions ADD CONSTRAINT writing_rubric_dimension_versions_original_dimension_id_fkey FOREIGN KEY (original_dimension_id) REFERENCES writing_rubric_dimensions(id) ON DELETE SET NULL")

    # 2. Add dimension_version_id column to review_scores (idempotent)
    if not _column_exists('writing_review_scores', 'dimension_version_id'):
        op.add_column('writing_review_scores', sa.Column('dimension_version_id', sa.String(36), nullable=True))
        op.create_index('ix_review_scores_dimversion_id', 'writing_review_scores', ['dimension_version_id'])
        op.create_foreign_key(
            'fk_review_scores_dimension_version',
            'writing_review_scores', 'writing_rubric_dimension_versions',
            ['dimension_version_id'], ['id'],
        )

    # 3. Drop old unique constraint, create new one with dimension_version_id
    if _constraint_exists('uq_review_score_review_dimension'):
        op.drop_constraint('uq_review_score_review_dimension', 'writing_review_scores', type_='unique')
    if not _constraint_exists('uq_review_score_review_dimversion'):
        op.create_unique_constraint('uq_review_score_review_dimversion', 'writing_review_scores', ['review_id', 'dimension_version_id'])

    # 4. Make dimension_id nullable (only if not already nullable)
    conn = op.get_bind()
    is_nullable = conn.execute(sa.text(
        "SELECT is_nullable FROM information_schema.columns "
        "WHERE table_name='writing_review_scores' AND column_name='dimension_id'"
    )).fetchone()
    if is_nullable and is_nullable[0] == 'NO':
        op.alter_column('writing_review_scores', 'dimension_id',
                        existing_type=sa.String(36), nullable=True)

    # 5. Add rubric_version_id to writing_reviews
    if not _column_exists('writing_reviews', 'rubric_version_id'):
        op.add_column('writing_reviews', sa.Column('rubric_version_id', sa.String(36), nullable=True))
        op.create_index('ix_writing_reviews_rubric_version_id', 'writing_reviews', ['rubric_version_id'])
        op.create_foreign_key(
            'fk_writing_reviews_rubric_version',
            'writing_reviews', 'writing_rubric_versions',
            ['rubric_version_id'], ['id'],
        )

    # 6. Backfill rubric versions for published reviews
    op.execute("""
        INSERT INTO writing_rubric_versions (id, rubric_id, version_number, title, active, created_at)
        SELECT gen_random_uuid(), r.id, 1, r.title, COALESCE(r.active, true), NOW()
        FROM writing_rubrics r
        WHERE EXISTS (
            SELECT 1 FROM writing_reviews rev
            JOIN writing_submissions s ON s.id = rev.submission_id
            JOIN writing_tasks t ON t.id = s.writing_task_id
            WHERE t.rubric_id = r.id AND rev.status = 'published'
        )
        AND NOT EXISTS (
            SELECT 1 FROM writing_rubric_versions rv WHERE rv.rubric_id = r.id
        )
    """)

    op.execute("""
        INSERT INTO writing_rubric_dimension_versions (id, rubric_version_id, original_dimension_id, name, description, display_order)
        SELECT gen_random_uuid(), rv.id, d.id, d.name, d.description, d.display_order
        FROM writing_rubric_dimensions d
        JOIN writing_rubric_versions rv ON rv.rubric_id = d.rubric_id
        WHERE NOT EXISTS (
            SELECT 1 FROM writing_rubric_dimension_versions dv
            WHERE dv.rubric_version_id = rv.id AND dv.original_dimension_id = d.id
        )
    """)

    op.execute("""
        UPDATE writing_reviews rev
        SET rubric_version_id = rv.id
        FROM writing_submissions s, writing_tasks t, writing_rubric_versions rv
        WHERE rev.submission_id = s.id
          AND s.writing_task_id = t.id
          AND t.rubric_id = rv.rubric_id
          AND rev.status = 'published'
          AND rev.rubric_version_id IS NULL
    """)

    op.execute("""
        UPDATE writing_review_scores sc
        SET dimension_version_id = dv.id
        FROM writing_rubric_dimension_versions dv
        JOIN writing_rubric_versions rv ON rv.id = dv.rubric_version_id
        JOIN writing_reviews rev ON rev.rubric_version_id = rv.id
        WHERE sc.review_id = rev.id
          AND sc.dimension_id = dv.original_dimension_id
          AND sc.dimension_version_id IS NULL
    """)


def downgrade() -> None:
    op.execute("UPDATE writing_review_scores SET dimension_version_id = NULL")
    op.execute("UPDATE writing_reviews SET rubric_version_id = NULL")

    if _constraint_exists('fk_review_scores_dimension_version'):
        op.drop_constraint('fk_review_scores_dimension_version', 'writing_review_scores', type_='foreignkey')
    if _column_exists('writing_review_scores', 'dimension_version_id'):
        op.drop_column('writing_review_scores', 'dimension_version_id')

    if _constraint_exists('uq_review_score_review_dimversion'):
        op.drop_constraint('uq_review_score_review_dimversion', 'writing_review_scores', type_='unique')
    if not _constraint_exists('uq_review_score_review_dimension'):
        op.create_unique_constraint('uq_review_score_review_dimension', 'writing_review_scores', ['review_id', 'dimension_id'])

    if _constraint_exists('fk_writing_reviews_rubric_version'):
        op.drop_constraint('fk_writing_reviews_rubric_version', 'writing_reviews', type_='foreignkey')
    if _column_exists('writing_reviews', 'rubric_version_id'):
        op.drop_column('writing_reviews', 'rubric_version_id')

    if _table_exists('writing_rubric_dimension_versions'):
        op.drop_table('writing_rubric_dimension_versions')
    if _table_exists('writing_rubric_versions'):
        op.drop_table('writing_rubric_versions')
