# Implementation status

An honest record of what is implemented and verified versus what remains
incomplete. A feature is only "done" when its functionality actually works, not
because a UI element, route, or table exists.

## Verified working

- **Authentication** — local email/password (Argon2id), rotating refresh
  sessions, short-lived signed access tokens, HttpOnly/SameSite cookies, logout
  and session revocation. SchoolApp sign-in flows through a Cloudflare Worker
  that verifies identity via `schoolapp.js` and returns a short-lived
  HMAC-signed assertion the backend verifies (see below).
- **Profiles** — read/update display name, bio, timezone; user search.
- **Pages & notes** — block-based pages, templates, nested hierarchy, block
  create/update/delete (soft-delete, stable IDs, debounced persistence),
  internal links, backlinks, markdown + KaTeX rendering.
- **Knowledge** — authorization-aware graph from real `page_links`, global
  search across pages/files/tasks/groups with access control.
- **Vault** — streaming uploads, download/preview, permissions (owner/group/
  user/session shares), comments, storage quota (500 MB), traversal-safe
  storage, **ownership transfer** (preserves edits/comments/versions/
  annotations), and **unlink** of shared files.
- **Storage accounting** — personal storage counts owned + linked (shared
  directly to you) files; monitoring via `GET /users/me/storage` and UI meter.
- **Tasks / projects / calendar** — typed tasks with status, projects, calendar
  events with participants and study-room linking.
- **Messaging & groups** — direct and group conversations, reactions, reads,
  groups with roles, group chat.
- **Realtime** — WebSocket layer (ticket auth, room authorization, presence,
  event relay) verified against a live server; message events broadcast on send.
- **Collaboration** — whiteboards (operation log + snapshot replay) and PDF
  annotations (separate persistent layer) with per-resource authorization.
- **Frontend** — design system, responsive shell, command palette, quick
  capture, all core pages, realtime chat, PDF render + annotate, whiteboard,
  storage meter + transfer/unlink UI, SchoolApp sign-in dialog.
- **Tests** — backend auth/authorization boundaries, storage/transfer/unlink,
  SchoolApp assertion verification, and a full end-to-end workflow all pass.
- **Build** — production frontend build succeeds; worker bundles with
  `wrangler deploy --dry-run`; Docker/NixOS config present.

## Implemented but not yet exercised in production

- **SchoolApp sign-in (live)** — the Cloudflare Worker is written and bundles
  correctly; it verifies SchoolApp credentials via `schoolapp.js` and signs an
  assertion the backend verifies (round-trip tested cross-language). It has
  **not** been deployed or live-tested against the SchoolApp server, because
  (a) this dev environment cannot reach `schoolapp.ensam-umi.ac.ma` (the
  connection times out — the server appears to restrict non-Moroccan/academic
  networks), and (b) no Cloudflare credentials were available to run
  `wrangler deploy`.
- Realtime across **multiple backend instances** (single-instance in-process
  connection manager; needs a shared pub/sub bus — e.g. Redis — for >1 worker).
- **Group audio** via SFU (LiveKit adapter stubbed; one-to-one is peer WebRTC
  with STUN; no TURN configured).

## Not implemented (documented, not faked)

- **SchoolApp data sync** beyond identity (grades/attendance import into Kumo).
- **Formula fields** in databases (typed properties/relations exist).
- **Recurrence rules** for tasks/events (schema field present only).
- **Browser push notifications** (in-app notification center exists).
- **External calendar sync** (CalDAV/iCal) — adapter not built.
- **Chemical structure editor** — no library evaluation done; math (LaTeX) and
  basic annotation are present.
- **TURN** server — not configured; STUN only.

See `docs/SECURITY.md` for the threat model and `docs/BACKUP_RECOVERY.md` for
backup/restore.
