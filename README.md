# Kumo

The unified engineering workspace for students and collaborative learning
communities. Communication, knowledge, files, planning, and study tools in one
connected environment — not a collection of unrelated products in tabs.

Everything a student needs to communicate, organize knowledge, plan work,
study engineering, and collaborate lives in one connected workspace.

## What's here

- **Notes & pages** — a block editor with templates, nested hierarchy, internal
  links, backlinks, Markdown, and LaTeX (KaTeX).
- **Knowledge graph** — a navigable, authorization-aware graph of real links.
- **Vault** — private/group file storage, secure sharing, comments.
- **Tasks, projects, calendar** — deadlines and events linked to notes, files,
  and study rooms.
- **CalDAV** — bidirectional sync with Apple Calendar / Thunderbird / GNOME
  Calendar via Radicale, with the app database as the single source of truth.
- **Messaging & groups** — realtime chat, reactions, presence, roles.
- **Collaboration** — live whiteboards and a collaborative PDF annotation
  workspace.
- **Study rooms** — sessions that tie documents, whiteboards, and chat together.

## Stack

- **Frontend**: React (JS), Vite, React Router, TanStack Query, Zustand,
  Lucide, KaTeX, react-markdown, PDF.js, d3-force.
- **Backend**: FastAPI, SQLAlchemy 2.x, PostgreSQL, Alembic, Argon2id.
- **Realtime**: WebSocket (presence/events); WebRTC for peer audio.
- **CalDAV**: Radicale with a custom storage backend bound to the app database.

## Quick start (development)

Prerequisites: Node 20+, Python 3.12+, `uv`.

```sh
# Backend (uses PostgreSQL via DATABASE_URL; see .env.example)
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxies /api to :8000)
```

For local development without PostgreSQL you can still use SQLite by setting
`DATABASE_URL=sqlite:///./data/kumo.db`.

Sign in with your **SchoolApp** account (identity verified via the deployed
Cloudflare Worker — see `infra/schoolapp-worker/`). Local email/password auth
remains available on the backend API for development.

## Production (Docker Compose)

```sh
cp .env.example .env      # set SECRET_KEY, origins, COOKIE_SECURE=true
docker compose up -d --build
```

The whole app is served on **http://localhost:5480** (frontend + API + WebSocket
behind one nginx reverse proxy).

### CalDAV clients

Connect an external calendar client with your Kumo email/password:

- Server URL: `https://your-host/caldav/` (or `http://localhost:5480/caldav/`)
- Username: your Kumo email or username
- Password: your Kumo password

The client auto-discovers your calendar via `/.well-known/caldav`. Events you
create or edit in the app appear in the client, and vice versa.

## Tests

```sh
cd backend && uv run pytest
cd frontend && npm run build
```

## Documentation

- `docs/API.md` — endpoint reference.
- `docs/SECURITY.md` — threat model and hardening.
- `docs/CONCURRENCY.md` — ~100 concurrent users, conflict handling, scale-out path.
- `docs/DEPLOYMENT_NIXOS.md` — NixOS deployment.
- `docs/BACKUP_RECOVERY.md` — backup/restore.
- `docs/IMPLEMENTATION_STATUS.md` — honest status of what works vs. what's
  incomplete.

## License

Proprietary (all rights reserved).
