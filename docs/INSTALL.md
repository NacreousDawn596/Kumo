# Installation & Setup

This guide walks you through installing and running **Kumo** — the unified
engineering workspace — on a fresh machine, either with Docker Compose
(recommended) or in local development mode.

---

## Prerequisites

| Dependency | Version | Notes |
|------------|---------|-------|
| Node.js | 20+ | frontend build |
| Python | 3.12+ | backend + scripts |
| [`uv`](https://docs.astral.sh/uv/) | latest | Python package/dependency manager |
| Docker + Compose | recent | recommended deployment path |
| `openssl` | any | generating secrets |

---

## 1. Clone the repository

```sh
git clone https://github.com/NacreousDawn596/Kumo.git
cd Kumo
```

---

## 2. Configure the environment

All secrets and runtime settings live in a single `.env` file, which is
**gitignored** and never committed.

```sh
cp .env.example .env
```

Open `.env` and fill in the values. The important ones:

- `SECRET_KEY` — a long random string. Generate one with:
  ```sh
  openssl rand -hex 32
  ```
- `POSTGRES_PASSWORD` — the PostgreSQL password (Docker path only).
- `AUTH_PROVIDER` — `schoolapp` (SSO) or `local` (email/password).
- `SCHOOLAPP_WORKER_SECRET` — the HMAC secret shared with the SchoolApp
  identity worker (SSO only).
- `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` — Web Push keys. Generate with:
  ```sh
  python -c "from py_vapid import Vapid01; print(Vapid01().generate())"
  ```
- `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` — group-audio SFU credentials.
- `TURN_USERNAME` / `TURN_CREDENTIAL` — WebRTC relay credentials.
- `COOKIE_SECURE` — set to `true` when serving over HTTPS.

> Every field is documented inline in `.env.example`. Secrets must be
> `KEY=value` on a single line, with no spaces around `=`.

---

## 3. Generate the service configs

LiveKit and coturn read their configuration from files, but their credentials
must not be committed. `scripts/setup.sh` renders the committed templates into
the real (gitignored) config files using the values in your `.env`:

```sh
./scripts/setup.sh
```

This produces:

- `infra/livekit.yaml` ← `infra/livekit.yaml.example`
- `infra/turnserver.conf` ← `infra/turnserver.conf.example`

Re-run this script whenever you change the LiveKit or TURN credentials in `.env`.

---

## 4a. Run with Docker Compose (recommended)

```sh
docker compose up -d --build
```

This starts **PostgreSQL + backend + frontend + LiveKit + coturn + Radicale**
behind a single nginx reverse proxy at **http://localhost:5480**.

Useful commands:

```sh
docker compose ps           # service status
docker compose logs -f      # tail all logs
docker compose down         # stop (keeps data volumes)
docker compose down -v      # stop and delete data volumes
```

---

## 4b. Run in development

```sh
# Backend
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev          # http://localhost:5173 (proxies /api to :8000)
```

To avoid PostgreSQL during development, use SQLite:

```sh
export DATABASE_URL=sqlite:///./data/kumo.db
```

---

## 5. Set up SchoolApp SSO (optional)

Sign-in with the student identity provider requires deploying the Cloudflare
Worker in `infra/schoolapp-worker/`:

```sh
cd infra/schoolapp-worker
npm install
wrangler secret put SCHOOLAPP_WORKER_SECRET   # must match .env
wrangler deploy
```

Then set `VITE_SCHOOLAPP_WORKER_URL` in `.env` to the deployed worker URL and
rebuild the frontend. With `AUTH_PROVIDER=local`, email/password accounts work
out of the box with no worker.

---

## 6. Connect a CalDAV client

| Field | Value |
|-------|-------|
| **Server URL** | `https://your-host/caldav/` |
| **Username** | your Kumo email or username |
| **Password** | your Kumo password |

Discovery happens automatically via `/.well-known/caldav`. **SchoolApp users**
generate a password under **Settings → CalDAV** (the token rotates on every
login).

---

## 7. Verification

```sh
cd backend && uv run pytest      # test suite
cd frontend && npm run build     # production build
```

A healthy deployment responds on `http://localhost:5480` with the Kumo login
screen, and `docker compose ps` shows all six services `running`/`healthy`.

---

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| Group audio never connects | `LIVEKIT_API_KEY`/`SECRET` empty — re-run `./scripts/setup.sh` after filling `.env`. |
| One-to-one/group calls fail behind NAT | `TURN_CREDENTIAL` empty — fill `.env` and re-run `./scripts/setup.sh`. |
| `./scripts/setup.sh` errors | `.env` has spaces around `=` or a non-`KEY=value` line — check the format. |
| CalDAV 401 | Re-enter the CalDAV password (SchoolApp tokens rotate on login). |
| Postgres auth failure | `POSTGRES_PASSWORD` changed after the volume was created — re-create the volume (`docker compose down -v`). |

See [`DEPLOYMENT_NIXOS.md`](DEPLOYMENT_NIXOS.md) for a production NixOS
deployment, and [`SECURITY.md`](SECURITY.md) for the threat model.
