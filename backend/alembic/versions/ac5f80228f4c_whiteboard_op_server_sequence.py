"""whiteboard op server sequence

Revision ID: ac5f80228f4c
Revises: b14f6706c054
Create Date: 2026-10-27 01:37:52.819195
"""

from alembic import op

revision = 'ac5f80228f4c'
down_revision = 'b14f6706c054'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rebuild whiteboard_operations so `seq` is a server-assigned autoincrement
    # primary key (conflict-free total order) and the string `id` is dropped.
    # Existing rows are preserved in true insertion order (rowid) and renumbered.
    op.execute("""
        CREATE TABLE whiteboard_operations_new (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            whiteboard_id VARCHAR(32) NOT NULL,
            user_id VARCHAR(32) NOT NULL,
            op_type VARCHAR(32) NOT NULL,
            payload_json TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            FOREIGN KEY(whiteboard_id) REFERENCES whiteboards (id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)
    op.execute("""
        INSERT INTO whiteboard_operations_new
            (whiteboard_id, user_id, op_type, payload_json, created_at)
        SELECT whiteboard_id, user_id, op_type, payload_json, created_at
        FROM whiteboard_operations
        ORDER BY rowid
    """)
    op.execute("DROP TABLE whiteboard_operations")
    op.execute("ALTER TABLE whiteboard_operations_new RENAME TO whiteboard_operations")
    op.execute(
        "CREATE INDEX ix_whiteboard_operations_whiteboard_id "
        "ON whiteboard_operations (whiteboard_id)"
    )
    op.execute(
        "CREATE INDEX ix_whiteboard_operations_user_id "
        "ON whiteboard_operations (user_id)"
    )


def downgrade() -> None:
    op.execute("""
        CREATE TABLE whiteboard_operations_old (
            id VARCHAR(32) PRIMARY KEY,
            whiteboard_id VARCHAR(32) NOT NULL,
            seq INTEGER NOT NULL,
            user_id VARCHAR(32) NOT NULL,
            op_type VARCHAR(32) NOT NULL,
            payload_json TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            FOREIGN KEY(whiteboard_id) REFERENCES whiteboards (id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)
    op.execute("""
        INSERT INTO whiteboard_operations_old
            (id, whiteboard_id, seq, user_id, op_type, payload_json, created_at)
        SELECT lower(hex(randomblob(16))), whiteboard_id, seq, user_id,
               op_type, payload_json, created_at
        FROM whiteboard_operations
    """)
    op.execute("DROP TABLE whiteboard_operations")
    op.execute("ALTER TABLE whiteboard_operations_old RENAME TO whiteboard_operations")
    op.execute(
        "CREATE INDEX ix_whiteboard_operations_whiteboard_id "
        "ON whiteboard_operations (whiteboard_id)"
    )
    op.execute(
        "CREATE INDEX ix_whiteboard_operations_user_id "
        "ON whiteboard_operations (user_id)"
    )
