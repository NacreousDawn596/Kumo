"""add calendar event uid

Revision ID: a1b2c3d4e5f6
Revises: 92dd0ab64714
Create Date: 2026-10-27 16:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = '92dd0ab64714'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('calendar_events', sa.Column('uid', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_calendar_events_uid'), 'calendar_events', ['uid'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_calendar_events_uid'), table_name='calendar_events')
    op.drop_column('calendar_events', 'uid')
