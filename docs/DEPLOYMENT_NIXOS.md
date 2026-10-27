# NixOS deployment

Kumo deploys as three containers (PostgreSQL + FastAPI backend + nginx frontend)
via Docker Compose, with the database and file storage on persistent local
volumes.

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
# POSTGRES_PASSWORD, FRONTEND_ORIGIN=https://your.domain,
# ALLOWED_ORIGINS=https://your.domain
```

## Build and start

```sh
docker compose up -d --build
```

The whole app (frontend + API + WebSocket) is served on a single port, **5480**
(`http://localhost:5480`). nginx serves the built frontend and proxies `/api/*`
(including WebSocket) to the backend. Put an HTTPS reverse proxy (Caddy/nginx)
in front for production.

## Persistent storage

- `kumo-pgdata` — PostgreSQL data (`/var/lib/postgresql/data`).
- `kumo-data` — uploaded file contents (`/app/data/storage`).

On NixOS, Docker named volumes live under `/var/lib/docker`; keep these on a
suitable local filesystem.

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
# Database dump (PostgreSQL)
docker compose exec -T postgres pg_dump -U kumo kumo > kumo-$(date +%F).sql

# File storage
docker run --rm -v kumo_kumo-data:/data -v $PWD:/backup alpine \
  tar czf /backup/kumo-storage-$(date +%F).tar.gz -C /data storage
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
