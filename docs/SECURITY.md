# Security documentation

## Threat model

Kumo treats all client input as untrusted: notes, Markdown, messages, filenames,
comments, page titles, uploaded files, and event payloads. Authorization is
enforced on the backend for every protected operation. Private content is
denied by default.

## Authentication

- Passwords hashed with **Argon2id** (`argon2-cffi`).
- Access tokens are short-lived (default 15 min), HMAC-signed, and issued as
  HttpOnly cookies (or `Authorization: Bearer` for API/tests).
- Refresh tokens are 256-bit random values stored only as SHA-256 hashes, with
  **rotation on refresh** and reuse detection via revocation.
- Cookies: `HttpOnly`, `SameSite=lax` (configurable), `Secure` in production.
- WebSocket connections authenticate with a 30-second one-time ticket minted by
  `POST /api/auth/ws-ticket` (avoids exposing the HttpOnly access cookie).
- Provider identity (SchoolApp) is verified server-side; the frontend never
  supplies a username as proof of identity.

## Authorization

- `app/security/authz.py` provides deny-by-default checks for files, pages,
  groups, and study-session membership. Permission levels are ordered
  (`view < download < comment < annotate < collaborate < edit < manage`).
- Every route resolves the current user from the signed access token, never
  from a client-supplied ID.
- Sharing changes are re-checked live; removing a member revokes access on the
  next protected request and on WebSocket relays.
- Backlinks, search, and graph all filter out resources the requester cannot
  access (no existence/title leakage).

## File security

- Uploads are streamed with size + quota limits; storage uses generated IDs with
  traversal-safe path resolution (sharded, `resolve()` stays within root).
- Complex formats (PDF, SVG, office docs) are treated as untrusted and never
  executed; active content is never served inline on the trusted origin.
- Downloads/previews require the `download`/`view` permission respectively.

## XSS & rich content

- React escaping is used everywhere; Markdown rendering passes through
  `rehype-sanitize` before `react-markdown`.
- No arbitrary user code is executed (formula fields are not implemented).

## SSRF

- No unrestricted URL previews, remote image proxies, or server-side importers.
  If added, they must enforce destination validation, private-network blocking,
  and redirect validation.

## API hardening

- CORS is allow-listed (CORS is not authorization).
- CSRF: state-changing requests use cookie auth; `SameSite=lax` mitigates
  cross-site POSTs (consider explicit CSRF tokens if moving to `SameSite=none`).
- SQLAlchemy parameterized queries only (no SQL injection); request size and
  rate limits are configured via the reverse proxy.

## Known limitations (do not rely on)

- Single-instance in-process WebSocket manager; scale-out needs a shared bus.
- Group audio requires an SFU (LiveKit) that is not yet deployed.
- Browser push notifications not implemented.

## Security testing

Run `uv run pytest` in `backend/`. The suite covers forged-session handling,
unauthorized file/message access, cross-group leakage, removed-member access,
and third-party denial. These tests passing does **not** mean the system is
secure — they are a subset of the required adversarial testing.
