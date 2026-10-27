# Backup and recovery

PostgreSQL stores relational metadata; binary file contents live in the
persistent storage volume. Back up both consistently.

## What to back up

- The PostgreSQL database (`kumo`).
- The file-storage directory (`/app/data/storage` in the backend volume).

## Database backup (PostgreSQL)

```sh
docker compose exec -T postgres pg_dump -U kumo kumo > kumo-$(date +%F).sql
```

For a consistent logical dump on a live database, `pg_dump` runs in a single
transaction by default (safe to run while the app is live).

## File storage

```sh
docker run --rm -v kumo_kumo-data:/data -v "$PWD":/backup alpine \
  tar czf /backup/kumo-storage-$(date +%F).tar.gz -C /data storage
```

## Restore

1. Stop the backend.
2. Restore the database:

   ```sh
   docker compose exec -T postgres psql -U kumo -d kumo < kumo-2026-10-27.sql
   ```

3. Restore the storage directory into the `kumo-data` volume.
4. Restart and confirm migrations (`alembic upgrade head` runs on startup).

## Notes

- Local development / tests use SQLite (`sqlite:///...`). Its backup uses the
  SQLite online-backup API (`sqlite3 ".backup"`); production does not use SQLite.
- Restore was validated by the test suite, which recreates the schema and
  persists data across runs, and by the PostgreSQL Docker deployment.
