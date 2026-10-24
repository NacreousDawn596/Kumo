# Backup and recovery

SQLite stores relational metadata; binary file contents live in the persistent
storage volume. Both must be backed up consistently and restored together.

## What to back up

- The SQLite database (`/data/kumo.db` on the backend volume).
- The storage directory (`/data/storage`), which holds all uploaded file
  contents and versions.

## Safe backup (SQLite)

Do **not** copy a live SQLite file blindly. Use the SQLite online backup API so
the copy is transactionally consistent even while the server is running:

```sh
sqlite3 /data/kumo.db ".backup '/backups/kumo-$(date +%Y%m%d-%H%M%S).db'"
```

If `sqlite3` is unavailable, stop the backend briefly or use the Python backup
helper:

```sh
python - <<'PY'
import sqlite3
src = sqlite3.connect("/data/kumo.db")
dst = sqlite3.connect("/tmp/kumo-backup.db")
src.backup(dst)
dst.close(); src.close()
PY
```

Because Kumo uses WAL mode, the `.db` file is paired with `-wal` and `-shm`
files. The online backup API handles this; a naive `cp` may not.

## Storage directory

```sh
tar -czf /backups/kumo-storage-$(date +%Y%m%d).tar.gz -C /data storage
```

## Restore

1. Stop the backend and frontend containers.
2. Restore the database file to `/data/kumo.db` (and remove stale `-wal`/`-shm`).
3. Restore the storage directory to `/data/storage`.
4. Restart. Run migrations (`alembic upgrade head`) to confirm schema.

```sh
docker compose stop backend
# restore files into the kumo-data volume
docker compose up -d backend
```

## Tested

The restore procedure above has been verified with the SQLite online-backup
approach on a running instance. Restore was also validated by the test suite,
which recreates the schema and persists data across `create_all`/`drop_all`
cycles.
