# SchoolApp identity worker

A Cloudflare Worker that verifies a student's SchoolApp identity using
[schoolapp.js](https://github.com/NacreousDawn596/schoolapp.js) and returns a
short-lived, HMAC-signed assertion that the Kumo backend can verify.

## Flow

1. The Kumo frontend shows **Continue with SchoolApp**.
2. The user enters their SchoolApp email + password in the Kumo sign-in screen.
3. The frontend calls `POST /verify` on this worker with `{ email, password }`.
4. The worker logs in to SchoolApp via `schoolapp.js`, retrieves the stable
   student code (`Code`) and full name, and returns a 120-second HMAC-signed
   assertion.
5. The frontend posts the assertion to Kumo's `POST /api/auth/schoolapp/assert`,
   which verifies the signature/issuer/audience/expiry and issues a Kumo session.

The SchoolApp password is used once, never logged or stored, and travels only
over TLS between this worker and the SchoolApp server.

## Security

- **Shared secret**: the worker signs assertions with `SCHOOLAPP_WORKER_SECRET`;
  the Kumo backend verifies with the same value (`SCHOOLAPP_WORKER_SECRET`).
  They must match and be a long random string (`openssl rand -hex 32`).
- **Short-lived + audience-restricted**: 120s TTL, `iss=schoolapp-worker`,
  `aud=kumo`, expiry checked server-side.
- **Rate limiting**: 10 requests/minute per IP (in-memory).
- **No credential logging**: errors are sanitized; passwords never appear in logs.
- **CORS**: restricted to the configured `ALLOWED_ORIGIN`.

## Deploy

```sh
cd infra/schoolapp-worker
npm install

# Set the shared secret (must match the backend's SCHOOLAPP_WORKER_SECRET)
npx wrangler secret put SCHOOLAPP_WORKER_SECRET

# Configure the Kumo frontend origin (CORS)
npx wrangler secret put ALLOWED_ORIGIN
# e.g. https://kumo.example.com

npx wrangler deploy
```

Then set `SCHOOLAPP_WORKER_SECRET` on the backend (`.env`) to the same value,
and point the frontend at the worker URL via `VITE_SCHOOLAPP_WORKER_URL`.

## Endpoints

- `GET /health` — liveness.
- `POST /verify` — `{ email, password }` → `{ assertion, sub, name }` on success,
  `401` on bad credentials, `429` when rate-limited.

## Note on provider capabilities

SchoolApp (ENSA Moulay Ismail) does not expose an OAuth/OIDC authorization
flow — `schoolapp.js` authenticates with the student's email + password and
scrapes the portal. As a result, the SchoolApp password must pass through this
worker once. This is documented as a known limitation; it mirrors the SchoolApp
web login and the password is never persisted.
