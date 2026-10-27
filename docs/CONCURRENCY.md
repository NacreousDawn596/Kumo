# Concurrency & scaling (target: ~100 concurrent users)

Kumo is built for a single-application-instance deployment serving roughly 100
concurrent users with no data-loss conflicts. This document explains the
architecture, the guarantees, and the path to scale beyond that.

## Database: SQLite hardened for concurrent writes

- **WAL mode** (`journal_mode=WAL`): concurrent readers + one writer, no
  read/write blocking.
- **`synchronous=NORMAL`**: durable under WAL, faster than FULL.
- **`busy_timeout=10000`**: concurrent writers *queue* instead of erroring with
  "database is locked".
- **`NullPool`**: each operation opens a fresh connection. SQLite connections
  are cheap and this avoids cross-thread pool races (a `QueuePool` with
  `pool_size` causes session re-entrancy errors under 100 concurrent writers).
- **Short transactions**: every route commits and releases the write lock
  quickly; transient presence/typing/cursors are never written to the DB.

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

Two things are required to run multiple workers/instances:

1. **Database**: point `DATABASE_URL` at PostgreSQL. SQLAlchemy/Alembic models
   are portable; only the SQLite-specific pragmas and the `NullPool` branch are
   SQLite-specific. Migrations already use batch mode.
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
