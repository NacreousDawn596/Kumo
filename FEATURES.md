# Kumo — Features

Kumo is a unified engineering workspace: communication, notes, files, tasks,
calendar, and collaborative study tools in one connected environment. This
document is a factual inventory of what the application does today — organized
so PR reviewers and stakeholders can evaluate it quickly.

Everything listed under **"Included"** is implemented and running. A short
**"Not yet implemented"** section at the end states honestly what is not there,
so no one has to guess.

---

## 1. Identity & authentication

**Included**

- **SchoolApp single sign-on** — the primary sign-in. A deployed Cloudflare
  Worker verifies the student's SchoolApp identity (via `schoolapp.js`) and
  returns a short-lived (120s), HMAC-signed assertion that the backend
  verifies. The student's SchoolApp password is used once and never stored.
- **Local email/password accounts** — available on the backend API
  (Argon2id hashing) for development and testing; not exposed in the UI.
- **Rotating refresh sessions** — refresh tokens are random, stored only as
  SHA-256 hashes, rotated on each refresh, and revocable server-side. Access
  tokens are short-lived and signed.
- **HttpOnly / SameSite cookies**, `Secure` in production.
- **Logout** and **revoke-all-sessions**.
- **WebSocket auth** — realtime connections authenticate via a one-time 30s
  ticket, not the HttpOnly cookie.

**Profiles** — display name, bio, study interests, time zone, theme, language.

---

## 2. Home

- Contextual greeting (name + time-of-day) and today's date.
- **Today's schedule**, **tasks**, **recent notes**, **recent documents**,
  **study rooms**, and **recent conversations** — all from real data.
- A first-use "set up your workspace" introduction that disappears once the
  user has content.
- Actionable empty states (e.g. "Nothing scheduled for today" → "Add event").

---

## 3. Notes & knowledge

**Pages** — a block-based editor with a calm writing surface.

- Block types: paragraph, heading, bulleted list, numbered list, checklist,
  quote, code block, divider, and **LaTeX equation** (KaTeX rendering).
- **Templates** — lecture notes, course page, meeting notes, lab report, and
  study-session notes (seed a page with a structured block layout).
- Nested page hierarchy (parent/child) and quick navigation.
- **Internal links** between pages (stable IDs — renaming doesn't break links)
  and an automatic **backlinks** list on each page.
- Autosave (debounced) that flushes on blur and on navigation, so edits are
  not lost when leaving a page.
- Markdown rendering with GFM tables, math, and a sanitization pipeline
  (`rehype-sanitize`) — untrusted content is never rendered as raw HTML.

**Knowledge graph** — an interactive, authorization-aware graph of real page
links (pan/zoom, click-to-open), plus a global search.

---

## 4. Vault (files)

- Upload (streamed, size-limited), download, and inline preview (PDF, images,
  text/Markdown/CSV).
- Grid presentation with file metadata.
- **Sharing** with individual users, groups, and study sessions, with graded
  permissions (view / download / comment / annotate / collaborate / manage).
- **Public / private sharing** — any file can be toggled public with an
  unguessable share link (`/public/files/{token}`); read-only and revocable.
- **Comments** on files.
- **Ownership transfer** — hand a file to another student; edits, comments,
  versions, and annotations are preserved (only the owner changes).
- **Unlink** a file shared with you to free quota without deleting it.
- **Storage quota** — 500 MB per user, counting owned files *and* linked files,
  with a live usage meter.

---

## 5. Tasks, projects & calendar

- **Tasks** — title, description, status, priority, due date, assignee, and
  project/group association; list view with completion states.
- **Projects** — project workspaces with their own task list.
- **Calendar** — **month / week / day / agenda** views; events and **task
  deadlines** overlaid; event creation, participants, and responses; events
  can link to a study session.
- **Recurring events** — RFC 5545 RRULE strings (e.g. `FREQ=WEEKLY;BYDAY=MO`)
  are expanded across the calendar.
- **ICS export** — download the user's events as an `.ics` file.

---

## 6. Communication

- **Direct messages** and **group conversations**.
- Message history with pagination, editing, deletion, replies, and reactions.
- Unread counters and read receipts.
- **Realtime** delivery over WebSocket (presence + message events) — messages
  appear to other participants immediately.
- **1:1 audio calls** — peer-to-peer WebRTC with WebSocket signaling (call,
  accept, mute, hang up) directly from a conversation.
- **Groups** — name/description, owner/admin/moderator/member/viewer roles,
  membership management, group vault, and group chat (membership stays in sync
  with the group conversation).
- **Invitations** — invite by user, or generate a **shareable invite link**;
  join-requests go through an **approve/reject** flow (with a full UI).

---

## 7. Study rooms & collaboration

- **Study rooms** — a session ties together participants, whiteboards, and
  linked documents; each room has its own view.
- **Whiteboards** — infinite canvas with pen, rectangle, arrow, text, eraser,
  select, pan, and a **chemistry drawing tool** (place atoms + draw bonds);
  **undo/redo** (Ctrl+Z / Ctrl+Y) and keyboard tool shortcuts. Operations use a
  server-assigned sequence so concurrent edits merge without conflict.
- **Collaborative PDF** — PDF.js rendering with a separate annotation layer
  (pen, highlighter, eraser, undo/redo); the source PDF stays immutable.
- **Invite links** for study rooms.

---

## 8. Search & navigation

- **Global search** across pages, files, tasks, groups, **and people**
  (users), respecting access controls.
- **Command palette** (Ctrl/Cmd + K) for search and quick actions (create
  note/task/event, open graph, start a session, settings, …).
- **Quick capture** from the sidebar for a note, task, or calendar event.

---

## 9. Notifications

- In-app notification center (list, unread badge, mark-read / mark-all-read).
- **Browser push notifications** — service worker + VAPID subscription, with a
  toggle in Settings (requires VAPID keys on the server to actually deliver).

---

## 10. Structured databases

- **Databases** — collections of typed records with configurable properties
  (text, number, checkbox, select, date, URL, relation, formula).
- **Table view** with inline cell editing, add/delete rows and properties.
- **Formula properties** — a safe, constrained expression evaluator
  (`score * 0.3`, `max(a, b)`, …) that references other properties; arbitrary
  code, imports, and attribute access are rejected.

---

## 11. Chemistry

- **SMILES input** with a gallery of example molecules (ethanol, benzene,
  caffeine, glucose, …).
- **Chemical verification** via RDKit — invalid SMILES are rejected; the
  formula, molecular weight, and formal charges are computed and shown.
- **3D structure viewer** (Three.js) — atoms colored with **CPK colors**,
  single/double/triple bonds, drag-to-rotate, scroll-to-zoom, and a **spin**
  toggle.
- A chemistry drawing tool in the whiteboard (place atoms, draw bonds).

---

## 12. Settings & personalization

- **Appearance** — light / dark / system theme; **8 accent colors**
  (purple, blue, indigo, teal, green, orange, rose, cyan), each rendered in
  light and dark (16 combinations); **corner-radius** and **text-size**
  sliders, applied live and persisted.
- **Notifications** — browser-push toggle.
- **Profile**, **Storage** (quota usage), and **Account** (sign-out).

---

## 13. Platform & operations
- **Stack** — React (Vite) frontend; FastAPI + SQLAlchemy 2.x + Alembic
  backend; PostgreSQL in production (SQLite fallback for local dev/tests).
- **Docker Compose** — PostgreSQL + backend + nginx serving the whole app on a
  single port (5480); health checks and persistent volumes; optional **LiveKit**
  service for group audio.
- **Backups** — documented `pg_dump` + file-storage procedure.
- **NixOS** deployment instructions.
- **Concurrency** — validated for ~100 concurrent users (PostgreSQL connection
  pooling; conflict-free whiteboard ops; a 100-user stress test in the suite).

---

## 14. Security (summary)

- Server-enforced authorization on every protected route (deny-by-default);
  `404` for resources the caller must not know exist.
- Traversal-safe file storage, size/quota limits, and no execution of uploads.
- Markdown sanitization; parameterized queries; narrow CORS; safe formula
  evaluation.
- WebSocket room authorization re-checked on every relay.

---

## Not yet implemented

Stated plainly so reviewers aren't misled:

- **Group audio media** — the LiveKit SFU is wired (token endpoint + Docker
  service + config) and 1:1 WebRTC calls work, but group-call *media* needs the
  LiveKit server deployed and a `livekit-client` join flow in the frontend.
- **Browser push delivery** — the subscription flow and service worker are in
  place; actually *sending* pushes requires VAPID keys to be configured.
- **CalDAV (two-way sync)** — only ICS *export* is implemented; there is no
  CalDAV server or import.
- **Database board/gallery views** — only the table view is implemented.
- **Chemical-structure *sketching*** — the chemistry tool draws atoms and
  bonds and verifies SMILES via RDKit, but there is no 2D sketcher with
  drag-to-place bonds in the 3D viewer (the whiteboard has a basic atom/bond
  tool).
