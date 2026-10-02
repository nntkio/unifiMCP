# Claude Connector: Public Endpoint and OAuth Layer — Design

_Date: 2026-09-11. Branch: `feature/oauth-connector`._

Builds on the HTTP transport (`2026-07-13-http-transport-design.md`) and
token-admin specs (`2026-07-13-token-admin-design.md`,
`2026-09-09-token-admin-ui-usage-log-design.md`). Those shipped a Streamable
HTTP endpoint protected by static bearer tokens minted in the admin UI, and
a LAN-only deployment behind nginx-proxy-manager.

This spec adds what Claude Desktop, claude.ai, and Claude mobile need to
use that endpoint through **Settings → Connectors → Add custom connector**:

- **Part A** — publish `https://unifi-mcp.seeg.io/mcp` to the internet
  without opening inbound ports. Deployment work on the NAS; no code.
- **Part B** — an OAuth 2.1 authorization server built over the existing
  token store, using the server-side auth helpers that ship in the pinned
  `mcp` SDK (1.28.1, `mcp.server.auth`). Code in this repo.
- **Part C** — the resulting steps a user follows in Claude.

## Why both parts are needed

Anthropic's connector documentation (2026-09) establishes:

- Custom connectors are brokered through the user's Claude account. The MCP
  server is contacted from Anthropic's egress range (`160.79.104.0/21`),
  not from the user's machine, so it must be reachable over public HTTPS.
  Today `unifi-mcp.seeg.io` resolves only on the LAN resolver.
- The Add-custom-connector dialog offers OAuth sign-in (Dynamic Client
  Registration or Client ID Metadata Document), "No sign-in", or, for
  organisations in a limited beta, fixed request headers. The request-header
  beta is not available here, so the server has to speak OAuth.
- The OAuth contract Claude checks: a `401` on the MCP URL carrying
  `WWW-Authenticate: Bearer resource_metadata="…"`; RFC 9728 protected
  resource metadata whose `resource` equals the URL typed into Claude;
  RFC 8414 authorization-server metadata advertising S256 PKCE and a
  registration endpoint; `/register` accepting JSON; `/token` accepting
  form-encoded bodies; refresh tokens that rotate; redirect URI
  `https://claude.ai/api/mcp/auth_callback`; every endpoint answering
  within 10 seconds.

## Goals

1. A Claude user adds `https://unifi-mcp.seeg.io/mcp` as a custom
   connector, chooses "Sign in now", and signs in with an ordinary
   token-admin account (username + password). Root cannot sign in there,
   consistent with root being unable to own tokens.
2. The access token Claude receives **is a row in the existing `tokens`
   table**, so it appears in the admin UI under the account that
   authorised it, can be revoked there, and every call is attributed in the
   usage log exactly as static tokens are today.
3. Revoking the token in the admin UI ends the connector session: the next
   refresh fails with `invalid_grant` and Claude asks the user to sign in
   again.
4. `unifi-mcp-admin` (port 8766) stays LAN-only. Only the MCP service is
   published.
5. With `MCP_PUBLIC_URL` unset, behaviour is byte-for-byte what it is
   today apart from a plain `WWW-Authenticate: Bearer` header on 401s.

## Non-goals

- Claude Code OAuth. Claude Code identifies itself with a Client ID
  Metadata Document and a loopback redirect on a random port; SDK 1.28's
  client model matches redirect URIs exactly and does not fetch CIMD
  documents. Claude Code keeps using `claude mcp add --transport http
  --header "Authorization: Bearer …"`, which continues to work unchanged.
- Scopes, multiple resources, OpenID Connect, or a consent screen separate
  from login. One resource, one permission level, login doubles as consent.
- TLS in the application. Cloudflare terminates it (Part A).

---

## Part A — Publishing the endpoint

### A.1 Current state

`unifi-mcp.seeg.io` is served by nginx-proxy-manager at `172.16.25.190`
(TLS via Let's Encrypt DNS-01 against the Cloudflare zone), forwarding to
the NAS at `172.16.25.50:8765`. The name exists only in the LAN resolver;
the public `seeg.io` zone, hosted on Cloudflare, has no record for it.

### A.2 Cloudflare Tunnel (chosen)

The zone already lives on Cloudflare, so a Tunnel needs no DNS migration,
no inbound port, no public IP, and gets Cloudflare's WAF for free.

1. **Create the tunnel.** Zero Trust dashboard → Networks → Tunnels →
   Create a tunnel → Cloudflared → name `unifi-mcp`. Copy the connector
   token.
2. **Run `cloudflared` next to the MCP service.** A third service is added
   to `deploy/docker-compose.qnap.yml` and the Container Station variant:

   ```yaml
   cloudflared:
     image: cloudflare/cloudflared:latest
     container_name: unifi-mcp-tunnel
     command: tunnel --no-autoupdate run --token ${CLOUDFLARE_TUNNEL_TOKEN}
     depends_on:
       - unifi-mcp
     restart: unless-stopped
   ```

   `CLOUDFLARE_TUNNEL_TOKEN` is added to `deploy/qnap.env.example`. The
   service publishes no ports; it only dials out to Cloudflare. The
   repo-root `docker-compose.yml` (local development) does not get it.
3. **Publish the hostname.** In the tunnel's Public Hostname tab: subdomain
   `unifi-mcp`, domain `seeg.io`, path empty, service type **HTTP**, URL
   `unifi-mcp:8765` (the compose service name; both containers share the
   default network). Cloudflare creates a proxied CNAME for the name. If
   a record for `unifi-mcp.seeg.io` already exists in the zone, delete it
   first; the tunnel will not overwrite it.
4. **Set `MCP_PUBLIC_URL=https://unifi-mcp.seeg.io`** in `qnap.env` and
   restart the stack (Part B reads it).
5. **Leave the LAN path alone.** The LAN resolver still points the same
   name at nginx-proxy-manager, so LAN clients (Claude Code with a static
   token) keep their direct route. Both routes present the same hostname,
   so the OAuth metadata URLs are identical whichever way a request
   arrives.

Cloudflare specifics worth knowing: the proxy passes Server-Sent Events
through unbuffered, and its 100-second origin timeout applies to the time
to first byte, which for MCP responses is immediate. `X-Forwarded-For`
carries the real client IP, so the usage log will show Anthropic's address
for connector calls and the `cloudflared` container as the direct peer.

### A.3 Optional hardening: WAF allowlist

Security → WAF → Custom rules → create rule, action **Block**:

```
(http.host eq "unifi-mcp.seeg.io"
  and not ip.src in {160.79.104.0/21}
  and not http.request.uri.path in {"/authorize" "/oauth/login"})
```

`/authorize` and `/oauth/login` must stay open to any address: they are
visited by the **user's browser**, which claude.ai redirects there during
sign-in. Everything else (`/mcp`, `/token`, `/register`, `/.well-known/…`)
is only ever called by Anthropic's servers. Anthropic publishes its range at
platform.claude.com/docs/en/api/ip-addresses; if it changes, this rule is
what breaks. Skipping the rule is acceptable: every other path still
requires a valid token or a valid login.

### A.4 Alternatives considered

- **Port-forward 443 to nginx-proxy-manager and add a public A record.**
  Exposes every proxy host on that nginx to the internet, needs a static
  IP or dynamic DNS, and offers no WAF. Rejected.
- **Tailscale Funnel.** Works, but adds a second agent on the NAS purely
  for this, and the zone is already on Cloudflare. Rejected.

### A.5 Verification (from a network that is not the LAN, e.g. a phone on
cellular)

```bash
curl -si https://unifi-mcp.seeg.io/healthz                  # 200 ok
curl -si -X POST https://unifi-mcp.seeg.io/mcp              # 401 + WWW-Authenticate: Bearer resource_metadata="…"
curl -s  https://unifi-mcp.seeg.io/.well-known/oauth-protected-resource/mcp | jq .resource
                                                            # "https://unifi-mcp.seeg.io/mcp"
curl -s  https://unifi-mcp.seeg.io/.well-known/oauth-authorization-server | jq .registration_endpoint
                                                            # "https://unifi-mcp.seeg.io/register"
curl -si https://unifi-mcp-admin.seeg.io/login              # must NOT resolve / connect from outside
```

---

## Part B — OAuth layer

### B.1 Flow

```
Claude (Anthropic egress)                     unifi-mcp (8765)
  POST /mcp (no token) ───────────────────▶  401, WWW-Authenticate: Bearer
                                              resource_metadata="…/.well-known/oauth-protected-resource/mcp"
  GET /.well-known/oauth-protected-resource/mcp ──▶ {resource, authorization_servers:[origin]}
  GET /.well-known/oauth-authorization-server ────▶ {authorization_endpoint, token_endpoint,
                                                     registration_endpoint, code_challenge_methods_supported:["S256"], …}
  POST /register (JSON, public client) ──────▶  {client_id, redirect_uris:[claude.ai callback], …}

User's browser
  GET /authorize?client_id&redirect_uri&code_challenge&state&resource
        ──────────────────────────────────▶  SDK validates client + redirect_uri, provider stores an
                                              authorization row (txn) ─▶ redirect to /oauth/login?txn=…
  GET /oauth/login?txn=… ─────────────────▶  login/consent page (client name, redirect host)
  POST /oauth/login (txn, username, password) ─▶ verify account password ─▶ code bound to txn
                                              ─▶ 303 https://claude.ai/api/mcp/auth_callback?code&state

Claude
  POST /token (form: authorization_code, code, code_verifier, client_id, redirect_uri)
        ──────────────────────────────────▶  SDK checks PKCE ─▶ provider mints a tokens row
                                              (label "OAuth · <client name>", expires in 1 h) and a
                                              refresh token ─▶ {access_token, refresh_token, expires_in:3600}
  POST /mcp  Authorization: Bearer <access> ─▶ existing BearerAuthMiddleware + usage log, unchanged
  POST /token (form: refresh_token) ─────────▶  same tokens row gets a new secret and expiry (rotate in
                                              place), old refresh token deleted, new one issued
```

### B.2 Configuration

One new variable, read only in HTTP mode:

| Variable | Description | Default |
|---|---|---|
| `MCP_PUBLIC_URL` | Public origin of the MCP service as Claude reaches it, scheme and host only, e.g. `https://unifi-mcp.seeg.io`. Enables the OAuth endpoints and the `resource_metadata` pointer on 401s. Must equal the connector URL entered in Claude minus `/mcp`. | unset (OAuth disabled) |

Validation at startup: must parse as an absolute `http(s)` URL with no
path, query, or fragment; otherwise the service exits with a clear error.
`http://` is accepted for local testing only.

Documented in `.env.example`, `deploy/qnap.env.example`, both Container
Station compose files, README, and the usage guide.

### B.3 Endpoints (all served by the MCP service on 8765)

| Path | Source | Notes |
|---|---|---|
| `GET /.well-known/oauth-protected-resource/mcp` | SDK `create_protected_resource_routes` | `resource` = `MCP_PUBLIC_URL + /mcp`, `authorization_servers` = `[MCP_PUBLIC_URL]`. |
| `GET /.well-known/oauth-protected-resource` | alias, same document | Claude's documented fallback probe. |
| `GET /.well-known/oauth-authorization-server` | SDK `build_metadata` + one override | `token_endpoint_auth_methods_supported` gains `"none"`: Claude registers as a public client, and CIMD selection requires it. |
| `GET|POST /authorize` | SDK `AuthorizationHandler` | Validates client, redirect URI, PKCE method; calls the provider, which returns `/oauth/login?txn=…`. |
| `GET /oauth/login` | this repo | Login + consent page. |
| `POST /oauth/login` | this repo | Verifies credentials, issues the code, redirects to the client. A **Cancel** button redirects with `error=access_denied` and the original `state`. |
| `POST /register` | SDK `RegistrationHandler` | DCR enabled, no scopes, no secret expiry. |
| `POST /token` | SDK `TokenHandler` | Form-encoded; PKCE verified by the SDK. |
| `POST /revoke` | SDK `RevocationHandler` | Revokes the tokens row and deletes its refresh token. |

The SDK's route paths are fixed relative to the issuer, so the issuer is
the bare origin and no `/oauth/` prefix is used for the SDK-owned routes.
Only the login page lives under `/oauth/`.

### B.4 Storage (`tokens.py`)

Three tables, created by the existing `_SCHEMA` script so both services
share them:

```sql
CREATE TABLE IF NOT EXISTS oauth_clients (
    client_id   TEXT PRIMARY KEY,
    client_json TEXT NOT NULL,          -- OAuthClientInformationFull, as registered
    created_at  TEXT NOT NULL
);

-- One row per authorisation attempt, from /authorize until the code is
-- exchanged (row deleted) or it expires (10 minutes).
CREATE TABLE IF NOT EXISTS oauth_authorizations (
    id                     TEXT PRIMARY KEY,   -- unguessable txn id used in the login URL
    client_id              TEXT NOT NULL REFERENCES oauth_clients(client_id) ON DELETE CASCADE,
    redirect_uri           TEXT NOT NULL,
    redirect_uri_explicit  INTEGER NOT NULL,
    code_challenge         TEXT NOT NULL,
    state                  TEXT,
    scope                  TEXT NOT NULL DEFAULT '',
    resource               TEXT,
    created_at             TEXT NOT NULL,
    expires_at             TEXT NOT NULL,
    attempts               INTEGER NOT NULL DEFAULT 0,
    owner_id               INTEGER REFERENCES accounts(id) ON DELETE CASCADE,  -- set on successful login
    code_hash              TEXT UNIQUE                                          -- set on successful login
);

CREATE TABLE IF NOT EXISTS oauth_refresh_tokens (
    token_hash        TEXT PRIMARY KEY,
    token_id          INTEGER NOT NULL REFERENCES tokens(id) ON DELETE CASCADE,
    client_id         TEXT NOT NULL,
    scope             TEXT NOT NULL DEFAULT '',
    grant_expires_at  TEXT NOT NULL,     -- absolute; inherited on rotation
    created_at        TEXT NOT NULL
);
```

Codes and refresh tokens are stored as SHA-256 hashes like bearer tokens.
Foreign keys are already enforced (`PRAGMA foreign_keys=ON`), so deleting an
account (root, admin UI) cascades through its tokens to their refresh
tokens, and its pending authorisations.

New `TokenStore` methods (all synchronous, same style as the existing ones):

- `get_token(token_id) -> TokenRecord | None`
- `rotate_token(token_id, expires_at) -> str` — new secret on the same row.
- `save_oauth_client(client_id, client_json)`, `get_oauth_client(client_id) -> str | None`
- `create_authorization(client_id, redirect_uri, redirect_uri_explicit, code_challenge, state, scope, resource, expires_at) -> txn_id`
- `get_authorization(txn_id) -> AuthorizationRecord | None` — None when missing or expired; expired rows are deleted opportunistically here.
- `fail_authorization_attempt(txn_id) -> int` — increments `attempts`, returns attempts remaining; deletes the row when the cap is hit.
- `complete_authorization(txn_id, owner_id) -> str` — stores `owner_id` and a fresh code, returns the raw code.
- `consume_authorization_code(raw_code) -> AuthorizationRecord | None` — single use: returns and deletes.
- `delete_authorization(txn_id)` — Cancel.
- `create_refresh_token(token_id, client_id, scope, grant_expires_at) -> str`
- `get_refresh_token(raw) -> RefreshRecord | None` — joins the tokens row so the caller can see `revoked_at` and `owner_id`.
- `delete_refresh_token(raw)`
- `revoke_token_by_value(raw)` — for `/revoke`.

### B.5 Provider (`server/_oauth.py`)

`TokenStoreOAuthProvider` implements the SDK's
`OAuthAuthorizationServerProvider` protocol with the SDK's own
`AuthorizationCode`, `RefreshToken`, and `AccessToken` models (their
`subject` field carries the account id as a string):

| Protocol method | Behaviour |
|---|---|
| `get_client` / `register_client` | JSON round-trip through `oauth_clients`. |
| `authorize(client, params)` | Insert an `oauth_authorizations` row, return `/oauth/login?txn=<id>`. |
| `load_authorization_code(client, code)` | `consume_authorization_code`; None unless the row belongs to `client` and has an `owner_id`. Consuming before PKCE is checked makes every code strictly single-use. |
| `exchange_authorization_code(client, code)` | `create_token(owner_id, label, now+1h)`, `create_refresh_token(…, grant_expires_at=now+30d)`; return `OAuthToken(expires_in=3600, refresh_token=…)`. |
| `load_refresh_token(client, raw)` | None if unknown, wrong client, grant expired, or the tokens row is revoked or deleted. |
| `exchange_refresh_token(client, rt, scopes)` | `rotate_token(rt.token_id, now+1h)`; delete the old refresh row; insert a new one with the same `grant_expires_at`; return both. |
| `load_access_token(raw)` | `resolve(raw)` mapped to `AccessToken`. Present for protocol completeness and `/revoke`; the MCP path keeps using the existing middleware. |
| `revoke_token(token)` | Revoke the tokens row and delete its refresh row. |

Token label: `"OAuth · " + client_name` from the registration, falling
back to the first eight characters of `client_id`. Rotating in place keeps
`tokens.id`, `label`, and `created_at` stable, so the admin UI shows one
row per connector sign-in rather than one per hourly refresh, and the usage
log attributes every call to that row.

### B.6 Login and consent page

Rendered by the MCP service with Jinja2 (already a dependency) from
`server/templates/oauth_login.html` and `oauth_error.html`, self-contained
with inline CSS in the admin palette (orange on white); no static route,
no JavaScript, no external fetches.

The page shows: the client's registered name ("Claude"), the host it will
be redirected to (`claude.ai`, per the MCP spec's requirement to display
the redirect target), a sentence stating that signing in grants that
client full access to this UniFi MCP server until the token is revoked in
the admin UI, username and password fields, **Sign in** and **Cancel**.

Rules:

- `txn` unknown or expired → 400 page "This sign-in link has expired.
  Start again from Claude."
- Wrong credentials → same page with "Invalid username or password"
  (no account enumeration). After 5 failures the authorisation row is
  deleted and the page says to start again from Claude; a brute force has
  to redo DCR + `/authorize` for every 5 guesses on top of argon2's cost.
- Root's env-var credentials are never accepted here; `verify_account_password`
  only knows database accounts.
- No separate CSRF token: the txn id is unguessable, single-use, and
  expires in 10 minutes, and OAuth `state` protects the client side.

### B.7 Changes to `_http.py`

- `BearerAuthMiddleware` applies only to paths under `/mcp` (today: every
  path except `/healthz`; the two rules coincide for existing routes). It
  takes an optional `resource_metadata_url` and emits, on 401:
  - no credentials: `WWW-Authenticate: Bearer resource_metadata="…"`
  - invalid credentials: `WWW-Authenticate: Bearer error="invalid_token", resource_metadata="…"`
  - without `MCP_PUBLIC_URL`: `WWW-Authenticate: Bearer` (no parameters).
- `build_app(mcp_server, token_store, on_shutdown, public_url=None)`
  appends the Part B routes when `public_url` is set. `run_http` reads and
  validates `MCP_PUBLIC_URL`.
- `NormalizeMcpPath` and `UsageLogMiddleware` are untouched; OAuth
  endpoints are not usage-logged.

### B.8 Lifetimes and security posture

| Item | Value | Rationale |
|---|---|---|
| Authorisation (login link) | 10 min, single use | Short window for the txn URL. |
| Login attempts per authorisation | 5 | Defeats online guessing without a global rate limiter. |
| Access token | 1 h, rotated in place on refresh | Bounds the value of a leaked token; Claude refreshes proactively 5 min before expiry. |
| Refresh token | Rotated on every use; grant expires 30 days after sign-in | OAuth 2.1 public-client rule; forces a fresh login monthly for a credential that can rewrite firewall rules. |
| Client registrations | Never expire | Claude registers a new client per fresh connection; rows are small. |

Constants in `_oauth.py`; not configurable in this iteration.

### B.9 Files

| File | Change |
|---|---|
| `src/unifi_mcp/tokens.py` | Three tables, `AuthorizationRecord`, `RefreshRecord`, methods in B.4. |
| `src/unifi_mcp/server/_oauth.py` | New: constants, `TokenStoreOAuthProvider`, login handlers, `build_oauth_routes(store, public_url) -> list[Route]`. |
| `src/unifi_mcp/server/templates/oauth_login.html`, `oauth_error.html` | New. |
| `src/unifi_mcp/server/_http.py` | B.7. |
| `.env.example`, `deploy/qnap.env.example`, `deploy/docker-compose.qnap.yml`, `deploy/docker-compose.container-station.yml` | `MCP_PUBLIC_URL`; `cloudflared` service and `CLOUDFLARE_TUNNEL_TOKEN` in the deploy files. |
| `README.md`, `docs/usage-guide.md`, `docs/qnap-deployment.md` | Part A procedure, `MCP_PUBLIC_URL`, Part C steps, Claude Code note. |
| `CLAUDE.md` | `_oauth.py` and `templates/` in the structure listing. |
| `tests/test_tokens_store.py` | New store methods, cascade on account delete. |
| `tests/test_server_http.py` | 401 header shapes; non-`/mcp` paths bypass bearer auth. |
| `tests/test_server_oauth.py` | New: full flow (B.10). |

### B.10 Testing

`tests/test_server_oauth.py` drives the real Starlette app with
`TestClient` and a temporary `TokenStore`, `public_url="http://testserver"`,
following the same fixtures as `test_server_http.py`:

1. Both metadata documents: `resource`, `authorization_servers`,
   `code_challenge_methods_supported == ["S256"]`, `"none"` in
   `token_endpoint_auth_methods_supported`, `registration_endpoint`.
2. DCR with `token_endpoint_auth_method: "none"` returns a client without a
   secret.
3. Happy path: `/authorize` → redirect to `/oauth/login?txn=` → page names the
   client and `claude.ai` → wrong password re-renders with the error →
   correct password 303s to the redirect URI with `code` and the original
   `state` → `/token` with the matching `code_verifier` returns an access
   and refresh token → `POST /mcp` with that access token is not 401 →
   the admin-side `list_tokens` shows one row with the OAuth label.
4. Code is single use; wrong `code_verifier` fails with `invalid_grant`
   and burns the code.
5. Refresh: old access token rejected, new one accepted, old refresh token
   rejected, `tokens.id` unchanged.
6. `store.revoke_token(id)` → refresh fails with `invalid_grant`.
7. Grant expiry (monkeypatched clock) → refresh fails with `invalid_grant`.
8. Cancel → redirect carries `error=access_denied` and `state`; txn gone.
9. Expired/unknown txn → 400; sixth failed attempt → 400 and row deleted.
10. `public_url=None` → none of the OAuth routes exist and 401 carries a
    bare `Bearer` challenge.
11. Deleting the account cascades: refresh row gone, refresh fails.

### B.11 Documentation

- README: `MCP_PUBLIC_URL` in the transport table; a short "Claude
  Desktop and claude.ai (custom connector)" subsection under "Running as
  a network service" pointing at the guides.
- `docs/qnap-deployment.md`: new section "Publishing the MCP endpoint with
  a Cloudflare Tunnel" (A.2–A.5), written against Cloudflare's current
  docs at implementation time.
- `docs/usage-guide.md`: replace the `mcp-remote` bridge paragraph with
  Part C; keep the Claude Code static-token instructions and add the
  non-goal note.

---

## Part C — Connecting from Claude (after A and B are deployed)

1. Claude Desktop (or claude.ai): Settings → Connectors → **Add custom
   connector**.
2. Name: `UniFi`. URL: `https://unifi-mcp.seeg.io/mcp`. Claude probes the
   URL and marks OAuth as detected.
3. Authentication **Sign in now**, OAuth client **Register
   automatically**. Add.
4. Click **Connect**. A browser tab opens the login page served by the
   MCP service; sign in with a token-admin account (not root). The tab
   returns to Claude.
5. Enable the connector per chat from the "+" menu. Individual tools can
   be blocked under Customize → Connectors.
6. To end the session: revoke the "OAuth · Claude" token in the admin UI,
   or remove the connector in Claude. Auth settings cannot be edited after
   adding; remove and re-add to change them.

## Decisions made without a live answer

These were judgement calls; any can be changed before implementation:

- Access token 1 h / grant 30 days / login link 10 min / 5 attempts.
- Rotate the access token **in place** rather than issuing a new tokens
  row per refresh, to keep one admin-UI row per sign-in.
- Login page is served by the MCP service (public), not by the admin
  service (which stays private). Inline CSS rather than mounting the
  admin's static files.
- The `cloudflared` container goes in the deploy compose files only.
- WAF allowlist is documented as optional, not required.
- Claude Code OAuth explicitly out of scope.
