# API documentation

Interactive OpenAPI docs are served at `/api/docs` and the schema at
`/api/openapi.json` when the backend is running. This page summarizes the
resource groups and key behaviors.

## Auth (`/api/auth`)

- `POST /auth/register` — create account (local provider), sets session cookies.
- `POST /auth/login` — sign in, sets session cookies.
- `POST /auth/refresh` — rotate refresh token.
- `POST /auth/logout` — revoke current session.
- `GET /auth/me` — current user.
- `POST /auth/ws-ticket` — mint 30s WebSocket ticket.
- `GET /auth/provider` — active provider.
- `POST /auth/schoolapp/start` / `/assert` — SchoolApp boundary (501 until configured).

All session cookies are HttpOnly; normal API requests carry them automatically
(same-origin) or use `Authorization: Bearer <access-token>`.

## Users (`/api/users`)

- `GET /users/me`, `PATCH /users/me` — profile.
- `GET /users/search?q=` — search users.
- `GET /users/{id}` — public profile.

## Pages & knowledge (`/api/pages`, `/api/knowledge`)

- `POST /pages`, `GET /pages`, `GET /pages/{id}`, `PATCH /pages/{id}`,
  `DELETE /pages/{id}` — CRUD (delete = archive).
- `PUT /pages/{id}/blocks` — full block list upsert (stable IDs, soft-delete).
- `POST /pages/{id}/links`, `GET /pages/{id}/backlinks`.
- `GET /knowledge/graph` — authorization-filtered graph.
- `GET /knowledge/search?q=&kind=&limit=` — cross-resource search.

## Vault (`/api/vault`)

- `GET /vault/files`, `POST /vault/files` (multipart), `GET /vault/files/{id}`,
  `PATCH /vault/files/{id}`, `DELETE /vault/files/{id}`.
- `GET /vault/files/{id}/content` (download), `/preview` (inline).
- `POST /vault/files/{id}/shares`, `GET|POST /vault/files/{id}/comments`.

## Planning (`/api/tasks`, `/api/projects`, `/api/calendar`)

- Tasks: `GET/POST /tasks`, `GET/PATCH/DELETE /tasks/{id}`.
- Projects: `GET/POST /projects`, `GET/PATCH /projects/{id}`.
- Calendar: `GET/POST /calendar` (`?start=&end=`), `GET/PATCH/DELETE
  /calendar/{id}`, `POST /calendar/{id}/respond`.

## Communication (`/api/conversations`, `/api/messages`)

- `GET /conversations`, `POST /conversations/direct`.
- `GET/POST /conversations/{id}/messages`, `PATCH/DELETE /messages/{id}`,
  `POST /messages/{id}/reactions`, `POST /conversations/{id}/read`.

## Groups (`/api/groups`)

- `GET/POST /groups`, `GET/PATCH/DELETE /groups/{id}`, invitations, role
  changes, `POST /groups/{id}/leave`.

## Collaboration (`/api/sessions`, `/api/whiteboards`, `/api/annotations`)

- Sessions: `GET/POST /sessions`, `GET/PATCH /sessions/{id}`,
  `POST /sessions/{id}/join`, `POST /sessions/{id}/resources`.
- Whiteboards: `GET/POST /whiteboards`, `GET /whiteboards/{id}`,
  `POST /whiteboards/{id}/operations` (operation log).
- Annotations: `GET/POST /annotations/files/{file_id}`,
  `PATCH/DELETE /annotations/{id}`.

## Realtime (`/api/ws`)

WebSocket with `?token=<ticket>`. Messages:

- `{"type":"subscribe","rooms":["conversation:<id>", ...]}` → `subscribed` ack.
- `{"type":"event","room":"...","event":{"type":"...","data":{...}}}` → relayed
  to other authorized room members.
- `{"type":"ping"}` → `pong`.

## Notifications & settings

- `GET /notifications`, `POST /notifications/{id}/read`, `POST /notifications/read-all`.
- `GET /settings`, `PUT /settings/{key}`.
- `GET /calls/config` — media provider config.

## Pagination & conventions

- `limit` (default 50, max 200) and `offset` query params on collection routes.
- All timestamps are ISO-8601 UTC.
- Errors return `{"detail": "..."}` with appropriate status codes; authorization
  failures return `404` (not `403`) for resources the caller must not know exist.
