# NixOS deployment

Kumo deploys as two containers (FastAPI backend + nginx frontend) via Docker
Compose, with SQLite and file storage on persistent local volumes.

## Runtime prerequisites

```nix
{ config, pkgs, ... }:
{
  virtualisation.docker.enable = true;
  # Optional: podman with docker-compat
  # virtualisation.podman.enable = true;

  environment.systemPackages = with pkgs; [ docker-compose git ];
}
```

## Clone and configure

```sh
git clone <repo> /opt/kumo
cd /opt/kumo
cp .env.example .env
# Edit .env: set SECRET_KEY (openssl rand -hex 32), COOKIE_SECURE=true,
# FRONTEND_ORIGIN=https://your.domain, ALLOWED_ORIGINS=https://your.domain
```

## Build and start

```sh
docker compose up -d --build
```

The whole app (frontend + API + WebSocket) is served on a single port, **5480**
(`http://localhost:5480`). nginx serves the built frontend and proxies `/api/*`
(including WebSocket) to the backend. Put an HTTPS reverse proxy (Caddy/nginx)
in front for production. SQLite data persists in the `kumo-data` named volume.

## Persistent storage

The `kumo-data` volume holds both `/app/data/kumo.db` (SQLite) and
`/app/data/storage` (file contents). On NixOS, Docker named volumes live under
`/var/lib/docker`; keep this on a suitable local filesystem (SQLite needs
reliable local locking — do **not** put it on NFS or other network filesystems).

## Database migrations

Migrations run automatically at container start (`alembic upgrade head`).
To run manually:

```sh
docker compose exec backend uv run alembic upgrade head
```

## Updating

```sh
git pull
docker compose up -d --build
```

## Logs

```sh
docker compose logs -f backend
docker compose logs -f frontend
```

## Backup / restore

See `docs/BACKUP_RECOVERY.md`. Briefly:

```sh
docker compose exec backend sh -c 'python - <<PY
import sqlite3
src = sqlite3.connect("/data/kumo.db")
dst = sqlite3.connect("/tmp/kumo-backup.db")
src.backup(dst); dst.close(); src.close()
PY'
```

## Troubleshooting

- **401 on all API calls**: `SECRET_KEY` changed between restarts invalidates
  existing sessions. Re-login or keep the key stable.
- **Cookies not set over HTTPS**: set `COOKIE_SECURE=true`.
- **CORS errors**: add your frontend origin to `ALLOWED_ORIGINS`.
- **WebSocket drops**: ensure the reverse proxy forwards `Upgrade`/`Connection`
  headers (the bundled nginx config already does).

An optional NixOS module or flake may be added later; the above is a
complete, working baseline.
