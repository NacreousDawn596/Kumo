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
- **Projects** — lightweight project workspaces (API; see limitations).
- **Calendar** — month view with events and **task deadlines** overlaid on
  their due dates; event creation, participants, and responses; events can
  link to a study session.

---

## 6. Communication

- **Direct messages** and **group conversations**.
- Message history with pagination, editing, deletion, replies, and reactions.
- Unread counters and read receipts.
- **Realtime** delivery over WebSocket (presence + message events) — messages
  appear to other participants immediately.
- **Groups** — name/description, owner/admin/moderator/member/viewer roles,
  membership management, group vault, and group chat (membership stays in sync
  with the group conversation).
- **Invitations** — invite by user, or generate a **shareable invite link**;
  join-requests go through an **approve/reject** flow.

---

## 7. Study rooms & collaboration

- **Study rooms** — a session ties together participants, whiteboards, and
  linked documents; each room has its own view.
- **Whiteboards** — infinite canvas with pen, rectangle, arrow, text, eraser,
  select, and pan; **undo/redo** (Ctrl+Z / Ctrl+Y) and keyboard tool shortcuts.
  Operations use a server-assigned sequence so concurrent edits merge
  without conflict.
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

---

## 10. Settings & personalization

- **Appearance** — light / dark / system theme; **8 accent colors**
  (purple, blue, indigo, teal, green, orange, rose, cyan), each rendered in
  light and dark (16 combinations); **corner-radius** and **text-size**
  sliders, applied live and persisted.
- **Profile**, **Storage** (quota usage), and **Account** (sign-out).

---

## 11. Platform & operations

- **Stack** — React (Vite) frontend; FastAPI + SQLAlchemy 2.x + Alembic
  backend; PostgreSQL in production (SQLite fallback for local dev/tests).
- **Docker Compose** — PostgreSQL + backend + nginx serving the whole app on a
  single port (5480); health checks and persistent volumes.
- **Backups** — documented `pg_dump` + file-storage procedure.
- **NixOS** deployment instructions.
- **Concurrency** — validated for ~100 concurrent users (PostgreSQL connection
  pooling; conflict-free whiteboard ops; a 100-user stress test in the suite).

---

## 12. Security (summary)

- Server-enforced authorization on every protected route (deny-by-default);
  `404` for resources the caller must not know exist.
- Traversal-safe file storage, size/quota limits, and no execution of uploads.
- Markdown sanitization; parameterized queries; narrow CORS.
- WebSocket room authorization re-checked on every relay.

---

## Not yet implemented

Stated plainly so reviewers aren't misled:

- **Group audio** — 1:1 WebRTC signaling config exists, but there is no in-app
  call UI and no LiveKit SFU for group calls yet.
- **Browser push notifications** — the in-app center exists; OS push does not.
- **Structured databases / collections** — schema models exist, but there is
  no UI or API surface yet.
- **Week / day / agenda calendar views** — month view is implemented.
- **Formula fields**, **recurrence rules**, **CalDAV/ICS sync**, and a
  **chemical-structure editor** are not implemented.
- **Projects** — backend API exists; no dedicated frontend page yet.
- Group invite-link **copy/approve UI** is complete on the backend but not yet
  surfaced in the Groups page UI.
