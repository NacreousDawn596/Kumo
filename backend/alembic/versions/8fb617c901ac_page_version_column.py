"""page version column

Revision ID: 8fb617c901ac
Revises: ac5f80228f4c
Create Date: 2026-10-27 01:50:43.419396
"""

from alembic import op
import sqlalchemy as sa


revision = '8fb617c901ac'
down_revision = 'ac5f80228f4c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('pages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('version', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    with op.batch_alter_table('pages', schema=None) as batch_op:
        batch_op.drop_column('version')
