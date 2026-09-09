# Token Admin UI Rebuild and Usage Log — Design

_Date: 2026-09-09. Branch: `feature/http-transport-token-admin`._

Builds on the July token-admin design
(`2026-07-13-token-admin-design.md`). That spec shipped the routes, session
handling, CSRF, and three unstyled Jinja pages. This spec covers three
additions requested on top:

1. A real interface for the admin service, using the layout vocabulary of
   the Dispatch Design System's Admin Panel template (sidebar rail, topbar,
   stat strip, bordered data tables, status chips) re-skinned with the
   seeg development website palette and type (orange on white, Space
   Grotesk + JetBrains Mono).
2. A root-only accounts view listing every user with the tokens created
   under them, where root can delete a user or revoke a token.
3. A usage log recording every MCP call made over the HTTP transport (who,
   from where, which tool, when, outcome), and a root-only screen that
   lists it with a filter on every column.

## 1. Visual system

Source references, in priority order:

- `~/projects/seeg-dev/website/DESIGN.md` and `src/styles/global.css` —
  tokens, type, spacing, shape, the logo mark.
- `~/projects/seeg-dev/dispatch/design-system/Dispatch Design System - v2`
  (`templates/admin/index.html`, `bespoke.css` `.adm-*` rules) — layout and
  component structure only. Its colours, serif face, and neon accent are
  **not** used.

Tokens (copied verbatim from the website):

| Token | Value | Use |
|---|---|---|
| `--bg` | `#F3F3F5` | page background |
| `--surface` | `#FFFFFF` | cards, table body |
| `--surface-subtle` | `#FCFCFD` | table header, inset panels |
| `--dark` / `--ink` | `#0E0E10` | sidebar band, text |
| `--muted` | `#52525A` | body copy |
| `--faint` | `#717179` | meta, eyebrows |
| `--line` | `#DFDFE3` | card and table borders |
| `--line-soft` | `#E8E8EB` | hairlines |
| `--accent` | `#E8590C` | primary button, active nav marker, eyebrow slash, status dots |
| `--accent-hover` | `#C7480A` | primary button hover |
| `--accent-deep` | `#9C3A0E` | orange text on light |
| `--accent-soft` | `#FFA470` | orange on the dark sidebar |
| `--ok` | `#2F9E44` | active status |
| `--err` | `#C0392B` | revoked status, errors, danger buttons |

Type: Space Grotesk for everything (titles tracked `-0.02` to `-0.03em`),
JetBrains Mono for eyebrows, table headers, token strings, IPs, timestamps,
always uppercase and letter-spaced when used as a label. Both fonts are
self-hosted (the two `woff2` files copied from the website's `public/fonts`)
so the admin has no external fetches at all.

Shape: cards 20px radius, buttons 10px, pills 999px, 1px borders and no
resting shadows. Orange appears at most once per block. Light theme only,
matching the website; the Dispatch dark toggle is dropped.

Layout: the Dispatch admin shell. A 248px dark sidebar (logo mark, product
eyebrow, nav, signed-in identity, log out) beside a light main column with a
sticky topbar (mono eyebrow, page title, contextual action). Below 820px the
sidebar becomes a top strip with the nav inline.

Components (class prefix `adm-`, names kept from the Dispatch template so
the mapping stays obvious): `adm-shell`, `adm-sidebar`, `adm-nav-item`,
`adm-topbar`, `adm-page-tag`, `adm-page-title`, `adm-stats`/`adm-stat`,
`adm-card`, `adm-table-wrap`/`adm-table`, `adm-badge` (`active`, `expired`,
`revoked`), `adm-btn` (`primary`, `ghost`, `danger`, `sm`), `adm-field`,
`adm-label`, `adm-input`, `adm-select`, `adm-alert` (`error`, `success`),
`adm-empty`, `adm-filter-row`, `adm-pager`, `adm-reveal` (new-token panel).

## 2. Pages

All pages are server-rendered Jinja templates extending `base.html`. They
work with JavaScript disabled; `admin.js` only adds copy-to-clipboard for a
revealed token, show/hide of the custom-date field, and submit-on-change for
the usage filter selects.

### Login (`/login`)

Full-viewport dark background, centred white card: logo mark and "seeg"
wordmark, mono eyebrow "UNIFI MCP · TOKEN ADMIN", title "Sign in", username
and password fields, orange primary button. Errors render as an inline
`adm-alert error` inside the card.

### Accounts (`/admin`, root only)

Sidebar nav: **Accounts**, **Usage**. Stat strip: accounts, active tokens,
expiring within 30 days, revoked.

"Create an account" card: username, temporary password, primary button.

"Accounts and tokens" table, grouped by user. Each account renders a group
row (username, created date, token count, **Delete user** danger button)
followed by one row per token (label, created, expires, status chip,
**Revoke** ghost button on active tokens). An account with no tokens shows a
single muted "No tokens yet" row. Delete user is a POST form with a
`confirm()` prompt in JS and a CSRF token; deleting removes the account and
all its tokens in one transaction. Usage-log rows are unaffected because
they store the username and label as text, not foreign keys.

### Usage (`/admin/usage`, root only)

Stat strip: calls today, calls last 7 days, distinct callers last 7 days,
distinct IPs last 7 days.

Table columns: Time, User, Token, IP, Forwarded for, Method, Tool, Status,
Duration. A filter row sits directly under the header with one control per
column: date-time `from`/`to` inputs under Time, distinct-value selects for
User, Token, Method, Tool, and Status, text inputs for IP and Forwarded
for, and a min-duration number input. Filters are a GET form; every control
maps to a query parameter, they combine with AND, and a "Clear" link resets
them. Rows are newest first, 50 per page, with a pager that preserves the
active filters.

### My tokens (`/tokens`, account users)

Sidebar nav: **My tokens**. When a token has just been created an
`adm-reveal` panel shows it in mono with a copy button and the "copy it
now, it will not be shown again" warning (existing test asserts on that
phrase). "Create a token" card: label, expiry select, custom date. Then the
own-tokens table with label, created, expires, status chip, Revoke.

## 3. Data model changes (`unifi_mcp/tokens.py`)

New table, created by the same `CREATE TABLE IF NOT EXISTS` script so
existing databases upgrade in place on next start:

```sql
CREATE TABLE IF NOT EXISTS usage_log (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,              -- ISO 8601 UTC
    token_id INTEGER,              -- no FK on purpose: survives deletes
    token_label TEXT NOT NULL,
    owner_id INTEGER,
    owner_username TEXT NOT NULL,
    ip TEXT NOT NULL,              -- best-effort caller IP (see §4)
    remote_addr TEXT NOT NULL,     -- direct TCP peer
    forwarded_for TEXT,            -- raw X-Forwarded-For header
    user_agent TEXT,
    method TEXT,                   -- JSON-RPC method, e.g. tools/call
    tool TEXT,                     -- params.name when method is tools/call
    status INTEGER NOT NULL,       -- HTTP status returned
    duration_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS usage_log_ts ON usage_log (ts);
```

New `TokenStore` API:

- `resolve(raw_token) -> TokenRecord | None` — the record for a valid,
  unexpired, unrevoked token. `validate` becomes `resolve(...) is not None`.
- `list_accounts() -> list[AccountRecord]` with `id`, `username`,
  `created_at`, `token_count`, `active_token_count`, ordered by username.
- `delete_account(account_id)` — deletes the account's tokens then the
  account in one transaction; raises `AccountNotFoundError` if absent.
- `log_usage(UsageEntry)` — inserts one row. Never raises to the caller;
  a `sqlite3.Error` is logged at warning level and swallowed, because a
  logging failure must not break an MCP call.
- `list_usage(filters: UsageFilter, limit, offset) -> list[UsageRecord]` and
  `count_usage(filters) -> int`. `UsageFilter` fields: `since`, `until`,
  `owner_username`, `token_label`, `ip` (substring), `forwarded_for`
  (substring), `method`, `tool`, `status`, `min_duration_ms`. Every field is
  optional; set fields combine with AND.
- `usage_facets() -> UsageFacets` — distinct values of `owner_username`,
  `token_label`, `method`, `tool`, `status` for the filter selects.
- `usage_summary() -> UsageSummary` — the four stat-strip numbers.

## 4. Usage logging in the HTTP transport (`server/_http.py`)

Hook point: a new `UsageLogMiddleware` registered after
`BearerAuthMiddleware`. The auth middleware switches from `validate` to
`resolve` and stores the `TokenRecord` on `request.state.caller`.

The usage middleware logs every **POST** to the MCP path (each JSON-RPC
message is one POST; GET opens the server-to-client SSE stream and DELETE
ends a session, neither is a "call"). For each POST it:

1. Reads the body via `request.body()`. Starlette's `BaseHTTPMiddleware`
   caches a body read in `dispatch` and replays it to the downstream app,
   so the MCP session manager still receives it.
2. Parses JSON. A single object gives `method` and, when `method` is
   `tools/call`, `params.name` as `tool`. A batch (list) logs one row per
   message. Unparseable bodies log with `method` and `tool` null.
3. Determines `ip`: the first entry of `X-Forwarded-For` if present,
   otherwise `X-Real-IP`, otherwise `request.client.host`. `remote_addr`
   is always `request.client.host`. Both are stored so a proxied deployment
   keeps the proxy hop visible.
4. Times `call_next`, then inserts the row with the response status.
   For SSE responses the duration covers time-to-headers, which is what the
   transport exposes; the column is documented as such.

Unauthorized requests never reach this middleware, so they are not logged.
Contextvars were considered and rejected: the MCP session manager runs tool
handlers in a task group created at session start, so a per-request
contextvar does not reach `call_tool`. The middleware sees everything the
log needs without touching the MCP dispatch.

## 5. Admin app changes (`admin/app.py`)

- Mount `StaticFiles` at `/static` serving `admin/static/`.
- On login store `username` in the session alongside `user_id`/`role`, so
  the sidebar identity renders without a store lookup.
- Jinja filters: `short_date` (ISO string to `09 Sep 2026 14:05`), and
  `token_status` (`revoked` if `revoked_at`, `expired` if `expires_at` is
  past, else `active`).
- Routes added: `POST /admin/accounts/{account_id:int}/delete` (root,
  CSRF, 303 back to `/admin`; 404 when absent) and `GET /admin/usage`
  (root; parses query parameters into `UsageFilter`, page size 50).
- Every template receives `current_user` (`{"username", "role"}`) and
  `active_nav`.

## 6. Packaging and deployment

`static/` ships inside the wheel the same way `templates/` already does
(hatchling includes all files under `src/unifi_mcp`). No Dockerfile change.
No new environment variables. The usage log lives in the existing
`TOKEN_DB_PATH` database, so the Compose volume already covers it.

## 7. Testing

- `tests/test_tokens_store.py`: resolve, list_accounts counts,
  delete_account cascade and not-found, log/list/count usage with each
  filter, facets, summary.
- `tests/test_server_http.py`: a `tools/call` POST with a valid token
  writes a row carrying owner, label, tool, IP, forwarded-for, and status;
  an unauthorized POST writes nothing; a batch body writes one row per
  message; the downstream MCP initialize still succeeds after the body is
  read (regression guard for the body replay).
- `tests/test_admin_app.py`: static CSS served; shell shows the signed-in
  username; accounts page groups tokens under their owner and shows status
  chips; delete account removes it and its tokens, 404 for unknown id,
  403 for bad CSRF, redirect for non-root; usage page renders rows, applies
  each filter from the query string, and pages; all existing tests
  unchanged.
- Manual: run the admin locally against a seeded temp database and
  screenshot each page at desktop and narrow widths.

## 8. Out of scope

Per-user usage view for account holders, CSV export of the log, log
retention/pruning, dark theme, tool-result error detection (would require
parsing the SSE response stream).
