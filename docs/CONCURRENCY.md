# Concurrency & scaling (target: ~100 concurrent users)

Kumo's production database is PostgreSQL. The backend keeps a thin SQLite
fallback for local development and tests, but all deployed instances and the
concurrency guarantees below assume PostgreSQL.

## Database

- **PostgreSQL** with a connection pool (`pool_size=10`, `max_overflow=30`,
  `pool_pre_ping`) handles concurrent readers and writers without the
  single-writer limitation of SQLite.
- The models and Alembic migrations are portable across both backends; only the
  engine construction (`app/core/database.py`) and pragmas are backend-specific.
- For local dev/tests, `DATABASE_URL=sqlite:///./data/kumo.db` still works
  (WAL + `busy_timeout` + `NullPool`), but it is not the production path.

Verified by `tests/test_concurrency.py`, which runs 100 concurrent users sending
messages and drawing on a shared whiteboard and asserts nothing is lost.

## Conflict-free collaboration

- **Whiteboard** (`whiteboard_operations`): the sequence number is a
  server-assigned `INTEGER PRIMARY KEY AUTOINCREMENT`. Clients never supply an
  ordering, so concurrent ops get a total order and distinct-element edits
  always merge. The snapshot is rebuilt deterministically from that log.
- **Messages**: append-only rows with server-generated IDs — no conflicts.
- **Pages** (`pages.version`): optimistic concurrency. The client sends the
  `version` it loaded; if the page changed underneath it, the server returns
  `409` and the editor shows a merge warning instead of silently clobbering.
- **Files**: owner-scoped; transfer/unlink are single-owner actions checked
  server-side.

## Realtime (WebSocket)

The WebSocket `ConnectionManager` is **in-process**. This is correct and
conflict-free for a **single worker** (one uvicorn process), which comfortably
serves 100 concurrent async connections. See the worker note below.

### Scaling beyond one instance

1. **Database**: PostgreSQL already runs as its own service and scales
   independently (replicas, PgBouncer, etc.).
2. **Realtime**: replace the in-process `ConnectionManager` with a shared
   pub/sub bus (Redis). Each worker publishes events to Redis and subscribes for
   rooms it hosts; presence becomes a Redis-managed set. The event envelope and
   room-authorization logic (`app/realtime/`) stay unchanged — only the
   transport behind `manager.broadcast` changes.

Until then, run with a single worker. The default Docker CMD already does
`uvicorn ... --workers 1`.

## Load test

```sh
cd backend && uv run pytest tests/test_concurrency.py -q
```

It registers 100 users, then fires 100 concurrent message sends and 100
concurrent whiteboard draws through the real ASGI app (httpx ASGITransport +
`asyncio.gather`), asserting every write succeeds and no element/message is lost.
