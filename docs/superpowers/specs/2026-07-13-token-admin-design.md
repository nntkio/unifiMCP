# Token Admin Service: SQLite-backed Bearer Token Management

## Context

The HTTP transport spec (`docs/superpowers/specs/2026-07-13-http-transport-design.md`,
not yet implemented) originally proposed a single static `MCP_HTTP_AUTH_TOKEN`
env var for bearer auth on the MCP Streamable HTTP endpoint. That's too rigid
for a household with multiple trusted people, each needing their own
revocable, expiring token for their own MCP clients.

This spec adds a small admin service that lets people log in, create
bearer tokens with an expiry, and revoke them — backed by a shared SQLite
file that the MCP server also reads to validate tokens. **This supersedes the
static-token design in the HTTP transport spec**, which is amended alongside
this spec (see "Amendment to the HTTP transport spec" below).

## Goals

- A root admin (credentials from env vars, no DB row) who can create
  accounts for other trusted people and view/revoke any token — but who
  cannot itself hold a token (it has no `accounts` row to own one).
- Regular accounts (created by root) that can log in and create/view/revoke
  only their own tokens.
- Tokens have a label, an expiry (preset duration or custom date), and can be
  revoked before expiry.
- The MCP server (separate process/container) validates bearer tokens
  against the same data without a network call.

## Non-goals

- No self-registration — root provisions every account.
- No password reset flow / email — root resets a user's password directly
  (regenerates `password_hash`) if needed.
- No per-token scoping (e.g. read-only vs full control) — a valid token
  grants the same access any authenticated MCP client gets today.
- No rate-limiting on `/login` — conscious choice for a home-LAN trust
  level, not an oversight.
- No DB migration framework — schema is created with
  `CREATE TABLE IF NOT EXISTS` on startup, acceptable for this scale.

## Architecture

New subpackage `src/unifi_mcp/admin/`:

```text
admin/
  __init__.py     # console-script entry point (main()) — builds the Starlette
                    app, runs uvicorn using ADMIN_HTTP_HOST/ADMIN_HTTP_PORT
  app.py           # routes/handlers, session + CSRF wiring
  auth.py           # argon2 password hashing, root-vs-account login check
  templates/         # Jinja2: login.html, tokens.html, admin.html
```

New shared module `src/unifi_mcp/tokens.py` — a `TokenStore` class wrapping
the SQLite file (opened in WAL mode so the admin service's writes don't
block the MCP server's reads):

- `create_account(username, password) -> account_id`
- `verify_account_password(username, password) -> account_id | None`
- `create_token(owner_id, label, expires_at) -> raw_token` (returned once,
  never stored)
- `list_tokens(owner_id=None)` — all tokens if `owner_id` is `None` (root's
  view), else just that owner's
- `revoke_token(token_id, requesting_owner_id)` — raises if the requester
  doesn't own the token (root bypasses this check in `app.py` before
  calling it)
- `validate(raw_token) -> bool` — hash lookup + `revoked_at IS NULL` +
  `expires_at IS NULL OR expires_at > now`

`server/_http.py`'s auth middleware (from the transport spec) calls
`TokenStore.validate(raw_token)` instead of comparing to a static string.

Both `unifi-mcp` and `unifi-mcp-admin` run from the **same Docker image**
(one dependency tree, one build) as separate Compose services with
different `command:`, sharing a named volume for the SQLite file. This
gives process isolation (a crash in one doesn't affect the other) without
maintaining two images.

## Data model

```sql
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE tokens (
    id INTEGER PRIMARY KEY,
    owner_id INTEGER NOT NULL REFERENCES accounts(id),
    label TEXT NOT NULL,
    token_hash TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT,          -- NULL = never expires
    revoked_at TEXT           -- NULL = active
);
```

There is no `is_admin` column and no root row: root's identity comes solely
from `ROOT_ADMIN_USERNAME`/`ROOT_ADMIN_PASSWORD` env vars, checked before
falling back to the `accounts` table. Because `tokens.owner_id` is a
foreign key into `accounts`, it is structurally impossible for a token to be
owned by root — enforced by the schema, not a business-logic check that
could have a bug.

The raw token (`secrets.token_urlsafe(32)`) is shown to the user exactly
once, on the creation response page, with a "copy it now" warning — only
its SHA-256 hash is ever persisted.

## Auth & sessions

- Root login: `POST /login` checks `ROOT_ADMIN_USERNAME`/`ROOT_ADMIN_PASSWORD`
  env vars first; on match, session gets `role: "root"`.
- Regular login: falls back to `TokenStore.verify_account_password`; on
  match, session gets `user_id: <id>`.
- Passwords hashed with `argon2-cffi`.
- Sessions are signed cookies via Starlette's `SessionMiddleware`
  (`itsdangerous`, already a transitive `starlette` dependency), keyed by
  `ADMIN_SESSION_SECRET`.
- CSRF: a per-session token embedded in every state-changing form and
  checked on POST (hand-rolled — Starlette has no built-in CSRF
  middleware).

## Routes

- `GET/POST /login`, `POST /logout`
- Root, after login → `GET /admin`:
  - Create accounts (`POST /admin/accounts`: username + temp password)
  - View all tokens across all users (owner column shown)
  - Revoke any token (`POST /admin/tokens/{id}/revoke`)
- Regular user, after login → `GET /tokens`:
  - Create a token (`POST /tokens`: label + expiry — preset dropdown
    [30/90/365 days, never] or a custom date)
  - View only their own tokens
  - Revoke only their own tokens (`POST /tokens/{id}/revoke`)
- Route guards: root-only routes require `session.get("role") == "root"`;
  user routes require `session.get("user_id")` and, on revoke, that
  `token.owner_id == session["user_id"]`.

## Error handling

- Wrong/missing credentials on `/login` → re-render the form with a generic
  "invalid username or password" (no distinction between "no such user" and
  "wrong password", to avoid username enumeration).
- Revoking a token you don't own (regular user) → `403`.
- Missing/invalid CSRF token on a POST → `403`.
- `TokenStore` opens the SQLite file in WAL mode; if the file/volume is
  unwritable at startup, both services fail fast (crash) rather than
  silently running without persistence.

## Configuration

New environment variables:

```bash
ROOT_ADMIN_USERNAME=root
ROOT_ADMIN_PASSWORD=                # required; admin service refuses to start without it
ADMIN_SESSION_SECRET=               # required; signs session cookies
TOKEN_DB_PATH=/data/tokens.db
ADMIN_HTTP_HOST=0.0.0.0
ADMIN_HTTP_PORT=8766
```

## Dependencies

Add to `pyproject.toml`:

- `argon2-cffi` (password hashing)
- `jinja2` (server-rendered templates; already a `starlette` extra but not
  guaranteed installed — declare explicitly since we import it directly)

(`starlette`, `uvicorn` already added by the HTTP transport spec.)

## Docker changes

`docker-compose.yml`:

- New service `unifi-mcp-admin`: same `image: unifi-mcp:latest`,
  `command: ["unifi-mcp-admin"]`, `ports: ["8766:8766"]`, mounts
  `unifi-mcp-data:/data`, `env_file: .env`.
- `unifi-mcp` service also mounts `unifi-mcp-data:/data` (read access for
  `TokenStore.validate`).
- New named volume `unifi-mcp-data`.

## Testing

- `tests/test_tokens_store.py` — `TokenStore` against a tmp SQLite file:
  create/verify account, create/validate/expire/revoke token, structural
  guarantee that root can't own a token (no account row to reference).
- `tests/test_admin_app.py` — Starlette `TestClient`: root login via env
  vars, regular login via DB, token create/list/revoke, cross-user revoke
  is rejected (403), missing CSRF token is rejected (403), root sees all
  tokens and a regular user sees only their own.

## Amendment to the HTTP transport spec

`docs/superpowers/specs/2026-07-13-http-transport-design.md` is updated
in place:

- **Configuration**: remove `MCP_HTTP_AUTH_TOKEN`; add `TOKEN_DB_PATH`.
- **Architecture / Error handling & security**: `BearerAuthMiddleware` calls
  `TokenStore.validate(raw_token)` (imported from `unifi_mcp.tokens`)
  instead of comparing to a static string. Behavior when the DB file is
  missing/unreadable: fail closed (treat as invalid token, return `401`),
  not fail open.
- **Docker changes**: add the shared `unifi-mcp-data` volume mount to the
  `unifi-mcp` service.
- **Dependencies**: note that `unifi_mcp.tokens` (this spec) is now a
  dependency of `server/_http.py`.

## Rollout

1. Implement `unifi_mcp/tokens.py` (`TokenStore`) and its tests.
2. Implement `unifi_mcp/admin/` (app, auth, templates) and its tests.
3. Amend `server/_http.py`'s auth middleware to use `TokenStore.validate`.
4. Add `argon2-cffi`/`jinja2` deps, new console-script entry point, update
   `.env.example`.
5. Update `docker-compose.yml` (new service, shared volume).
6. Run `pytest`, `ruff check . && ruff format .`.
7. Deploy to QNAP alongside the HTTP transport work: set
   `ROOT_ADMIN_USERNAME`/`ROOT_ADMIN_PASSWORD`/`ADMIN_SESSION_SECRET` in the
   QNAP `.env`, `docker compose build && docker compose up -d`.
8. Verify: log in as root at `http://172.16.25.50:8766/admin`, create a
   test account, log in as that account, create a token, then confirm it
   authenticates against `http://172.16.25.50:8765/mcp`.
