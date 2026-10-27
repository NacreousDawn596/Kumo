# Kumo — Features

**Kumo** is a unified engineering workspace for students and collaborative
learning communities. It brings communication, notes, knowledge management,
files, tasks, calendar, databases, and collaborative study tools into one
connected environment.

This document is a **detailed, factual inventory** of what the application
actually does today. It is written for two audiences:

- **PR reviewers** — to understand scope, architecture, and security posture.
- **Stakeholders / pitch decks** — to see the full feature set at a glance.

Everything under **"Implemented"** is real and running. A precise
**"Not yet implemented"** section at the end states exactly what is missing, so
nothing is overstated.

---

## Contents

1. [Identity & authentication](#1-identity--authentication)
2. [Home](#2-home)
3. [Notes & knowledge](#3-notes--knowledge)
4. [Vault (files)](#4-vault-files)
5. [Tasks, projects & calendar](#5-tasks-projects--calendar)
6. [Communication](#6-communication)
7. [Study rooms & collaboration](#7-study-rooms--collaboration)
8. [Structured databases](#8-structured-databases)
9. [Chemistry](#9-chemistry)
10. [Search & navigation](#10-search--navigation)
11. [Notifications](#11-notifications)
12. [Settings & personalization](#12-settings--personalization)
13. [Design system](#13-design-system)
14. [Platform & operations](#14-platform--operations)
15. [Security](#15-security)
16. [API surface](#16-api-surface)
17. [Testing](#17-testing)
18. [Not yet implemented](#18-not-yet-implemented)

---

## 1. Identity & authentication

**Sign-in methods**

- **SchoolApp single sign-on (primary).** A deployed Cloudflare Worker verifies
  the student's SchoolApp identity through `schoolapp.js` and returns a
  **short-lived (120 s), audience-restricted, HMAC-SHA256-signed assertion**.
  The backend verifies the signature, issuer (`schoolapp-worker`), audience
  (`kumo`), and expiry. The student's SchoolApp password is used once, never
  logged, and never stored.
- **Local email/password accounts.** Backend-only (Argon2id hashing) for
  development, tests, and the mock-user seeder. Not shown in the sign-in UI.

**Session model**

- **Access tokens** — short-lived (15 min), HMAC-signed, carried in an HttpOnly
  cookie (or `Authorization: Bearer` for API/tests).
- **Refresh tokens** — 256-bit random values, stored only as SHA-256 hashes,
  **rotated on every refresh**, revocable server-side, with reuse detection.
- **Cookies** — `HttpOnly`, `SameSite=Lax` (configurable), `Secure` in
  production.
- **Logout** and **revoke-all-sessions**.
- **WebSocket authentication** — realtime sockets authenticate with a one-time
  30-second ticket (so the HttpOnly access cookie is never exposed to JS).

**Profiles**

- Editable: display name, bio, study interests, time zone, theme, language.
- **Profile photo upload** — PNG/JPEG/WebP/GIF (2 MB max), stored in the
  storage layer and served from `/api/users/{id}/avatar`; the previous photo is
  cleaned up automatically.
- Stable internal IDs and unique normalized usernames.

---

## 2. Home

A personal working surface, driven entirely by real data:

- Contextual greeting (first name + time-of-day) and today's date.
- **Today's schedule**, **tasks requiring attention**, **recent notes**,
  **recent documents**, **active study rooms**, and **recent conversations**.
- A **first-use introduction** ("set up your workspace") that disappears once
  the user has any content.
- **Actionable empty states** — each empty section states what it is and offers
  one relevant action (e.g. "Nothing scheduled for today" → "Add event").
- Header actions: **New note** (primary) and **New task**.

---

## 3. Notes & knowledge

### Pages

A block-based editor with a distraction-free writing surface.

**Block types (9):**

| Block | Notes |
|-------|-------|
| Paragraph | — |
| Heading | Renders large/bold |
| Bulleted list | — |
| Numbered list | — |
| Checklist (todo) | With checkbox |
| Quote | — |
| Code block | Monospace, preserved whitespace |
| Divider | Horizontal rule |
| Equation | **LaTeX**, rendered with KaTeX |

**Editing behavior**

- Blocks have stable IDs and are saved individually; the page is never saved
  destructively on every keystroke.
- **Autosave** is debounced and flushes on **blur** and on **navigation /
  unmount / beforeunload**, so edits are not lost when leaving a page.
- Keyboard: Enter inserts a block, Backspace on an empty block deletes it, a
  per-block menu switches the block type.
- Markdown rendering supports GFM tables, task lists, and math; rendered output
  is passed through `rehype-sanitize` (untrusted content is never raw HTML).

**Templates (5)** — seed a page with a structured block layout:

- Lecture notes
- Course page
- Meeting notes
- Lab report
- Study-session notes

**Hierarchy & links**

- Nested pages (parent/child), breadcrumbs, and quick navigation.
- **Internal links** between pages use stable IDs — renaming a page never
  breaks inbound links.
- **Backlinks** — every page lists the other pages that link to it (respecting
  access controls; private pages never leak their existence through backlinks).
- Page permissions are private by default with explicit sharing.

### Knowledge graph

- An interactive, **authorization-aware** graph of real `page → page` links.
- Pan/zoom, click a node to open the page, and a depth limit to keep large
  graphs readable.
- Backed by persisted relationships, not decorative random data.

---

## 4. Vault (files)

- **Upload** (streamed, size-limited to 50 MB/file), **download**, and **inline
  preview** for PDF, images, and text/Markdown/CSV.
- Grid presentation with file metadata (size, date, type).
- **Storage quota: 500 MB per user**, counting owned files *and* files linked
  (shared) to you, with a live usage meter.

**Sharing & permissions (7 graded levels)**

`view` → `download` → `comment` → `annotate` → `collaborate` → `edit` → `manage`

- Share with **individual users**, **groups**, or **study sessions**.
- **Public / private links** — any file can be toggled public with an
  unguessable 128-bit token (`/public/files/{token}`); public access is
  read-only and revocable.
- **Comments** on files (with optional page/anchor).
- **Ownership transfer** — hand a file to another student; edits, comments,
  versions, and annotations are all preserved (only the owner changes).
- **Unlink** a file shared with you to free quota without deleting the
  underlying file.

**Storage** — binary contents live in a dedicated persistent storage layer
(traversal-safe, sharded paths) separate from the database; the storage
interface is designed so an S3-compatible backend can replace local files later.

---

## 5. Tasks, projects & calendar

### Tasks

- Title, description, status (`todo` / `in_progress` / `done` / `cancelled`),
  priority, due date, start date, assignee, project, and group.
- List view grouped by status, with completion states.
- Task deadlines also appear **on the calendar**.

### Projects

- Lightweight workspaces with name, description, and a member list.
- Each project has its own page with its **task list** (add, toggle done).

### Calendar

- **Four views: month, week, day, agenda**, with a view switcher and
  prev/today/next navigation.
- Events: title, description, start/end, all-day, time zone, location,
  participants (with accept/decline/tentative responses), and an optional
  study-session link.
- **Task deadlines** are overlaid on their due dates.
- **Recurring events** — RFC 5545 RRULE strings (e.g. `FREQ=WEEKLY;BYDAY=MO`)
  are validated and expanded across the calendar.
- **ICS export** — download the user's events as a standards-compliant `.ics`.
- **ICS import** — upload a `.ics` file; `VEVENT` blocks (SUMMARY, DTSTART,
  DTEND, DESCRIPTION, LOCATION, RRULE) are parsed and imported as events.

---

## 6. Communication

### Messaging

- **Direct messages** and **group conversations**.
- Message history with pagination, **editing**, **deletion**, **replies**, and
  **reactions** (a hover "+" opens an emoji picker; reactions are grouped by
  emoji with counts).
- **Link previews** — attach a page/file/task to a message via a searchable
  picker; the message renders a preview card linking to the resource.
- **Unread counters** and **read receipts**.
- **Realtime** delivery over WebSocket — sent messages appear to other
  participants immediately (the send endpoint also broadcasts a room event).

### 1:1 audio calls

- Peer-to-peer **WebRTC** with WebSocket signaling.
- Call, accept, **mute/unmute**, and hang up — directly from a conversation.
- **STUN + optional TURN** — ICE servers are fetched from `/api/calls/config`,
  which includes TURN credentials when configured (a `coturn` service is
  provided in Docker Compose).
- No call recording.

### Groups

- Name, description, and **5 roles**: `owner`, `admin`, `moderator`,
  `member`, `viewer`.
- Membership management, group vault, and **group chat** (group membership and
  conversation membership are kept in sync automatically).
- **Invitations** — invite a user directly, or generate a **shareable invite
  link**; join requests go through an **approve/reject** flow with a full UI.

### Group audio (SFU)

- A **LiveKit** adapter is wired: a token endpoint mints signed LiveKit access
  tokens, and a Docker service + config are provided.
- **In-room group calls** — the study-room page has a "Join group call" button
  that uses `livekit-client` to connect to the SFU, publish the microphone, and
  subscribe to other participants (with live participant count and mute/leave
  controls). The LiveKit server runs as a default Docker service, so this works
  out of the box with `docker compose up`.

---

## 7. Study rooms & collaboration

### Study rooms

- A session ties together **participants**, **whiteboards**, and **linked
  documents**; each room has its own view.
- **Invite links** for rooms; members can join directly.

### Whiteboards

An infinite, collaborative canvas.

- **Tools (8):** Select (V), Pan (H), Pen (P), Eraser (E), Rectangle (R),
  Arrow (A), Text (T), and **Chemistry** (C — place atoms, draw bonds).
- **Undo / Redo** with buttons and `Ctrl+Z` / `Ctrl+Y` (plus `Ctrl+Shift+Z`).
- Keyboard tool shortcuts and `Delete`/`Escape` for selection.
- **Conflict-free concurrency** — every operation gets a server-assigned
  monotonic sequence, so concurrent edits merge without collision; the canvas
  is rebuilt deterministically from the operation log.
- Pan (drag) and zoom (scroll).

### Collaborative PDF

- **PDF.js** rendering with a **separate annotation layer** — the source PDF is
  never modified.
- Tools: **pen**, **highlighter**, **eraser**, with **undo/redo** and keyboard
  shortcuts.
- Annotations are persisted per-page with normalized coordinates, so they stay
  aligned across zoom levels and devices.

---

## 8. Structured databases

Collections of typed records (Notion-style), for courses, assignments, research
papers, and lab data.

- **Property types (11):** `title`, `text`, `number`, `checkbox`, `select`,
  `multi_select`, `date`, `person`, `url`, `relation`, `formula`.
- **Four views** — **table** (inline cell editing), **board** (Kanban columns
  grouped by a `select` property, with per-column "new" actions), **gallery**
  (record cards showing the title plus a few properties), and **calendar**
  (records with a `date` property appear on a month grid).
- Add/delete rows and properties.
- **Formula properties** — a safe, constrained expression evaluator that
  references other properties by name. Supports arithmetic, comparison,
  `if`/`else` expressions, and functions (`abs`, `round`, `min`, `max`, `sum`,
  `len`, `sqrt`, `floor`, `ceil`). Parsing uses a whitelisted `ast` — arbitrary
  code, imports, and attribute access are **rejected**.

---

## 9. Chemistry

A molecular tool powered by **RDKit** (server-side cheminformatics).

- **SMILES input** with an example gallery (ethanol, benzene, caffeine, acetic
  acid, glucose, ammonium).
- **2D molecular sketcher** — drag-to-place atoms (C/N/O/S/P/F/Cl/H) and draw
  bonds by dragging atom-to-atom (click again to cycle single→double→triple).
  The drawing is converted to a V2000 molfile and verified by RDKit.
- **Chemical verification** — invalid SMILES or drawn structures are rejected;
  the molecular **formula**, **molecular weight**, **formal charge**, and
  heavy-atom/bond counts are computed and shown.
- **3D structure viewer** (Three.js):
  - Atoms rendered as spheres with **CPK colors** (C grey, O red, N blue, H
    white, S yellow, P orange, halogens green/brown/purple, metals per Jmol).
  - **Single / double / triple bonds** as parallel cylinders.
  - **Drag to rotate, scroll to zoom, and a spin toggle.**
- 3D coordinates are generated by RDKit (ETKDG embedding + MMFF force-field
  optimization), not fabricated.
- A basic atom/bond drawing tool also lives in the whiteboard.

---

## 10. Search & navigation

- **Global search** across **pages, files, tasks, groups, and people** — with
  access control applied before results are returned.
- **Command palette** (`Ctrl/Cmd + K`): search plus quick actions (create
  note/task/event, start a session, open the knowledge graph, settings, …).
- **Quick capture** (from the sidebar) for a note, task, or calendar event.

---

## 11. Notifications

- **In-app notification center** — list, unread badge, mark-read, mark-all-read.
- **Browser push notifications** — a service worker + VAPID subscription flow
  with a Settings toggle, and delivery wired into message sends (best-effort
  Web Push to the other participants). Requires VAPID keys to be configured.

---

## 12. Settings & personalization

Categorized settings navigation with five sections:

| Section | Controls |
|---------|----------|
| **Appearance** | Theme mode (light / dark / system); 8 accent colors; corner-radius slider (50–200%); text-size slider (85–140%). All live-previewed and persisted. |
| **Notifications** | Browser-push toggle. |
| **Profile** | Display name, bio, time zone. |
| **Storage** | Quota usage meter (owned + linked bytes). |
| **Account** | Signed-in identity, sign out. |

---

## 13. Design system

A token-driven design system implemented in CSS custom properties:

- **Themes** — light and dark, each with distinct neutral surfaces, borders,
  and text contrast (the dark theme is a deliberate design, not an inversion).
- **8 accent colors** — purple `#7c2bb4`, blue `#2563eb`, indigo `#4f46e5`,
  teal `#0d9488`, green `#16a34a`, orange `#ea580c`, rose `#e11d48`, cyan
  `#0891b2` — each rendered in light and dark (16 combinations). Derived tones
  (hover, text, soft background) are computed with `color-mix`.
- **Corner radius** and **text size** are user-adjustable and scale globally
  via CSS variables.
- System font stack; semantic type scale; 4-px spacing scale; semantic
  status colors (success/warning/error/info); `prefers-reduced-motion`
  respected.
- Responsive: persistent sidebar on desktop, a drawer + compact top bar on
  mobile, with safe-area handling.

---

## 14. Platform & operations

- **Stack** — React 18 (Vite) frontend; **FastAPI + SQLAlchemy 2.x + Alembic**
  backend; **PostgreSQL** in production (SQLite fallback for local dev/tests);
  psycopg v3 driver.
- **Frontend libs** — React Router, TanStack Query, Zustand, Lucide icons,
  KaTeX, react-markdown, PDF.js, d3-force, Three.js, `livekit-client`.
- **Backend libs** — Argon2id (`argon2-cffi`), `cryptography`, `python-multipart`,
  `aiofiles`, `pywebpush`, `python-dateutil` (RRULE), `rdkit`.
- **Docker Compose** — PostgreSQL + backend + nginx serving the whole app on a
  **single port (5480)**, plus **LiveKit** (group-audio SFU) and **coturn**
  (TURN relay) as default services; health checks and persistent volumes.
  Group audio, TURN, and Web Push are wired end-to-end so `docker compose up`
  enables them out of the box (with dev credentials; see `.env.example` for
  production values).
- **Backups** — documented `pg_dump` + file-storage procedure.
- **NixOS** — deployment instructions provided.
- **Concurrency** — validated for ~100 concurrent users: PostgreSQL connection
  pooling, server-sequenced whiteboard operations, and a 100-user stress test
  in the suite.
- **Migrations** — portable Alembic migrations (work on both SQLite and
  PostgreSQL).

---

## 15. Security

- **Authentication** — Argon2id hashing; rotating, hashed refresh tokens;
  signed short-lived access tokens; HttpOnly/SameSite cookies; WebSocket
  tickets; HMAC-verified SchoolApp assertions with issuer/audience/expiry
  checks.
- **Authorization** — deny-by-default on every protected route; graded
  permissions for files/pages; resources the caller must not know exist return
  `404` (no existence leak). Re-checked live, so revoked access takes effect
  immediately (including WebSocket relays).
- **Files** — streamed uploads with size/quota limits; traversal-safe, sharded
  storage paths; uploaded content is never executed or served as active
  content.
- **Rich content** — Markdown sanitization (`rehype-sanitize`); formula
  evaluation sandboxed via `ast`; no arbitrary user code execution.
- **WebSockets** — authenticated connections, room-level authorization
  re-checked on every event, payload size limits.
- **API** — parameterized queries (no SQL injection); narrow CORS allow-list;
  request size limits; no raw exceptions leaked to clients.
- **No logging** of message bodies, file contents, passwords, or tokens.

---

## 16. API surface

The backend exposes a modular REST API under `/api` (interactive OpenAPI docs
at `/api/docs`):

- `/auth` — register, login, refresh, logout, me, SchoolApp assert, WS ticket.
- `/users` — profile read/update, user search, storage usage, avatar upload
  and serving.
- `/pages` — page CRUD, block upsert, links, backlinks.
- `/knowledge` — graph, search.
- `/vault/files` — upload/download/preview, share, transfer, unlink,
  make-public/private, comments. Plus unauthenticated `/public/files/{token}`.
- `/tasks`, `/projects`, `/calendar` (events + recurrence + ICS export/import).
- `/conversations`, `/messages`, `/groups` (invite links, join, approval).
- `/sessions` (study rooms + invite links).
- `/whiteboards` (operation log).
- `/annotations` (PDF annotation layer).
- `/databases` (properties, records, formula).
- `/chemistry/molecule` (SMILES → 3D structure) and `/chemistry/sketch`
  (V2000 molfile from the 2D sketcher → 3D structure).
- `/notifications` (in-app + push subscription + VAPID key).
- `/settings`, `/calls` (config + LiveKit token).
- `/api/ws` — WebSocket realtime (conversation/group/session/whiteboard/file
  rooms).

All collection routes are paginated (`limit`/`offset`); timestamps are UTC
ISO-8601.

---

## 17. Testing

- **Backend** — 30 pytest tests covering authentication, session rotation,
  authorization boundaries (IDOR, cross-group leakage, removed-member access),
  storage quota/transfer/unlink, public-file share/revoke, group invite-link
  approval, people search, SchoolApp assertion verification, chemistry
  sketcher, ICS import, avatar upload, and a **100-user concurrency stress
  test** (messages + whiteboard).
- **Frontend** — production build (`npm run build`) verified; end-to-end flows
  exercised in a real headless browser (SchoolApp sign-in, note autosave,
  calendar, whiteboard draw/undo/redo, PDF annotate, chemistry 3D viewer).

---

## 18. Not yet implemented

Stated precisely so reviewers are not misled:

- **CalDAV (two-way sync)** — ICS **import and export** both exist, but there
  is no CalDAV protocol server for live two-way sync with external calendar
  apps.
- **Message attachments** (files/images) — not present; only link previews are
  supported.
- **No call recording** in 1:1 or group calls.
