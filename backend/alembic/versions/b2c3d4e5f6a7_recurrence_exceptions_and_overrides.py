"""recurrence exceptions and calendar event overrides

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-27 17:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('calendar_events', sa.Column('exdates', sa.Text(), nullable=True))
    op.add_column('calendar_events', sa.Column('rdates', sa.Text(), nullable=True))

    op.create_table(
        'calendar_event_overrides',
        sa.Column('event_id', sa.String(length=32), nullable=False),
        sa.Column('recurrence_id', sa.DateTime(timezone=True), nullable=False),
        sa.Column('start_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('cancelled', sa.Boolean(), nullable=False),
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['calendar_events.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_calendar_event_overrides_event_id'), 'calendar_event_overrides', ['event_id'], unique=False)
    op.create_index(op.f('ix_calendar_event_overrides_recurrence_id'), 'calendar_event_overrides', ['recurrence_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_calendar_event_overrides_recurrence_id'), table_name='calendar_event_overrides')
    op.drop_index(op.f('ix_calendar_event_overrides_event_id'), table_name='calendar_event_overrides')
    op.drop_table('calendar_event_overrides')
    op.drop_column('calendar_events', 'rdates')
    op.drop_column('calendar_events', 'exdates')
