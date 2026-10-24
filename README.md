# Kumo

The unified engineering workspace for students and collaborative learning
communities. Communication, knowledge, files, planning, and study tools in one
connected environment.

## Layout

- `backend/` — FastAPI + SQLAlchemy + SQLite backend.
- `frontend/` — React + Vite frontend.
- `infra/` — Docker, NixOS, and Cloudflare Worker integration scaffolding.
- `docs/` — architecture, security, backup, and deployment documentation.

See `docs/IMPLEMENTATION_STATUS.md` for an honest record of what is done and
what remains incomplete.

## Quick start

```sh
# Backend
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

See `README.md` at the root and `docs/` for full instructions.
