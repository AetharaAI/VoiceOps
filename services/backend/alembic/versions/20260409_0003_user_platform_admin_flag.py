"""Add users.is_platform_admin flag

Revision ID: 20260409_0003
Revises: 20260320_0002
Create Date: 2026-04-09
"""

from alembic import op
import sqlalchemy as sa


revision = '20260409_0003'
down_revision = '20260320_0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('is_platform_admin', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )
    op.execute(
        """
        UPDATE users
        SET is_platform_admin = true
        WHERE id = (
            SELECT id
            FROM users
            ORDER BY created_at ASC, id ASC
            LIMIT 1
        )
        """
    )


def downgrade() -> None:
    op.drop_column('users', 'is_platform_admin')
