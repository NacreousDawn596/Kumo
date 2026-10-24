"""set 500mb storage quota

Revision ID: b14f6706c054
Revises: 0314efe1d4d0
Create Date: 2026-10-24 20:38:50.691187
"""

from alembic import op
import sqlalchemy as sa


revision = 'b14f6706c054'
down_revision = '0314efe1d4d0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE users SET storage_quota_bytes = 524288000 "
        "WHERE storage_quota_bytes = 1073741824"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE users SET storage_quota_bytes = 1073741824 "
        "WHERE storage_quota_bytes = 524288000"
    )
