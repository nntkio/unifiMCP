# HTTP/SSE (Streamable HTTP) Transport for UnifiMCP

## Context

UnifiMCP currently only speaks MCP over stdio (`src/unifi_mcp/server/__init__.py`,
`mcp.server.stdio.stdio_server`), which is invoked as a local subprocess by an
MCP client (e.g. Claude Desktop). The repo already has a `Dockerfile` and
`docker-compose.yml` for containerized deployment, built around stdio
(`stdin_open`/`tty`).

We are deploying UnifiMCP to a QNAP Container Station host (`172.16.25.50`) as
a persistent background service. For that to be useful to remote/network MCP
clients, the server needs a network transport in addition to stdio.

The installed MCP Python SDK is `mcp==1.28.1`, which supports both the legacy
SSE transport and the current **Streamable HTTP** transport
(`mcp.server.streamable_http_manager.StreamableHTTPSessionManager`). Streamable
HTTP is the SDK's recommended transport going forward.

## Goals

- Add a Streamable HTTP transport, selectable at runtime, without breaking the
  existing stdio behavior used by local/Claude Desktop setups.
- Protect the network transport with per-user, revocable, expiring bearer
  tokens, since UnifiMCP's tools can mutate live network state (restart
  devices, change firewall rules, block clients). Token issuance and
  validation are specified separately in
  `docs/superpowers/specs/2026-07-13-token-admin-design.md`; this spec only
  covers how the HTTP transport *checks* a presented token.
- Update the Docker deployment (`Dockerfile`/`docker-compose.yml`) to run in
  HTTP mode on the QNAP.
- Cover the new code with tests consistent with the existing test style.

## Non-goals

- No reverse proxy / TLS termination (nginx-proxy-manager) in this pass — the
  service is exposed directly on the LAN IP for now. Can be fronted by NPM
  later without further code changes.
- No full OAuth resource-server flow (the SDK's `mcp.server.auth` machinery)
  — a shared SQLite-backed token store (see the token-admin spec) is
  sufficient for a home LAN deployment.
- No changes to tool behavior, formatting, or the UniFi client — this is
  purely a transport-layer addition.

## Architecture

New module: `src/unifi_mcp/server/_http.py`

- Wraps the existing `server` (`mcp.server.Server` instance, already created
  in `server/__init__.py`) in a Starlette ASGI app.
- Uses `StreamableHTTPSessionManager(app=server)` to handle the MCP protocol
  over HTTP, mounted at `POST/GET /mcp`.
- Adds a plain `GET /healthz` route (not part of the MCP protocol) that
  returns `200 OK` with no auth required — used by Docker's healthcheck.
- Adds a small Starlette middleware, `BearerAuthMiddleware`, that:
  - Passes `/healthz` through unauthenticated.
  - For all other paths, requires an `Authorization: Bearer <token>` header
    and validates it via `TokenStore.validate(raw_token)` (from
    `unifi_mcp.tokens`, shared with the admin service — see the token-admin
    spec). Returns `401` on a missing header or a token that fails
    validation (unknown, revoked, or expired).
  - If the token DB file is missing or unreadable, fails closed: every
    request is treated as unauthenticated (`401`), never fails open.
- Exposes `run_http(mcp_server: Server, on_shutdown: Callable[[], Awaitable[None]]) -> None`,
  which builds the app, wires `on_shutdown` into the Starlette `lifespan`
  shutdown phase, and runs it via `uvicorn.run(...)` using host/port from
  config.

`server/__init__.py` changes:

- `main()` reads `MCP_TRANSPORT` env var (default `"stdio"`).
  - `"stdio"` → existing behavior, unchanged.
  - `"http"` → calls `_http.run_http(server, _close_client)`.
- No changes to `list_tools`/`call_tool`/tool dispatch — transport-agnostic
  already.

## Configuration

New environment variables (documented in `.env.example`):

```bash
MCP_TRANSPORT=stdio          # stdio (default) | http
MCP_HTTP_HOST=0.0.0.0
MCP_HTTP_PORT=8765
TOKEN_DB_PATH=/data/tokens.db  # shared with the admin service; see token-admin spec
```

Existing stdio-based deployments (e.g. local Claude Desktop configs) are
unaffected since `MCP_TRANSPORT` defaults to `stdio`.

## Error handling & security

- Missing/invalid/expired/revoked bearer token → `401 Unauthorized`,
  rejected by the middleware before the request reaches the MCP session
  manager. Validation logic (hash lookup, expiry, revocation) lives in
  `TokenStore` (token-admin spec), not duplicated here.
- `/healthz` is exempt from auth so Docker's healthcheck (which doesn't send
  a token) keeps working.
- `_close_client()` (shared UniFi client cleanup) runs on Starlette `lifespan`
  shutdown — same guarantee stdio mode gets today via its `finally` block.
- Tool-call error handling (`call_tool`'s try/except returning `TextContent`
  errors) is unchanged — already transport-agnostic.
- If `MCP_HTTP_PORT` is already bound, `uvicorn.run` raises at startup and the
  container exits non-zero, surfaced by Docker's restart policy as a crash
  loop — correct failure mode, no silent bind failure.

## Dependencies

Add explicit dependencies in `pyproject.toml` (currently pulled in
transitively via `mcp`, but imported directly by `_http.py`):

- `starlette`
- `uvicorn`

`_http.py` also depends on `unifi_mcp.tokens.TokenStore` (implemented as
part of the token-admin spec).

## Docker changes

`docker-compose.yml`:

- Remove `stdin_open: true` / `tty: true` (no longer needed — nothing reads
  stdio in HTTP mode).
- Add `ports: ["8765:8765"]`.
- Add a `healthcheck` hitting `http://localhost:8765/healthz`.
- Mount the shared `unifi-mcp-data:/data` volume (read access for
  `TokenStore.validate`) — the volume itself and the `unifi-mcp-admin`
  service that writes to it are defined in the token-admin spec.

QNAP `.env` (not committed) sets `MCP_TRANSPORT=http` and
`TOKEN_DB_PATH=/data/tokens.db`. Local/dev `.env` stays on the `stdio`
default.

## Testing

New `tests/test_server_http.py`, following existing conventions
(`pytest.mark.asyncio`, Starlette `TestClient`):

- `BearerAuthMiddleware` rejects requests with missing, unknown, expired, or
  revoked tokens (`401`) — using a tmp `TokenStore` seeded directly, not a
  real admin-service round-trip.
- `BearerAuthMiddleware` allows requests with a valid token.
- `/healthz` succeeds unauthenticated even when the token store has entries.
- `main()` dispatches to `run_http` when `MCP_TRANSPORT=http`, and to the
  existing stdio path otherwise (mocked, same pattern as
  `tests/test_server_registry.py`).

## Documentation

`README.md` currently documents only the stdio/Claude-Desktop setup. Update it
to also cover HTTP mode:

- Note that `MCP_TRANSPORT` selects `stdio` (default) or `http`.
- Document `MCP_HTTP_HOST`, `MCP_HTTP_PORT`, `TOKEN_DB_PATH`, and link to the
  token-admin spec/docs for how to actually obtain a bearer token.
- Add a short "Running as a network service" section: how to start in HTTP
  mode, the `/mcp` and `/healthz` endpoints, and an example client config
  pointing at a remote Streamable HTTP URL instead of a local subprocess.
- Cross-reference `docs/usage-guide.md` where it currently states the server
  "speaks MCP over stdio to the assistant" — clarify that's the default, not
  the only option.

## Rollout

This spec depends on `unifi_mcp.tokens.TokenStore` existing (implemented as
part of `docs/superpowers/specs/2026-07-13-token-admin-design.md`) —
implement that spec's `TokenStore` first, or alongside this one.

1. Implement `_http.py`, wire `main()`, add deps, update `.env.example`.
2. Add tests; run `pytest` and `ruff check . && ruff format .`.
3. Update `docker-compose.yml`.
4. Deploy to QNAP: rsync repo to
   `/share/CACHEDEV2_DATA/container/unifi-mcp/`, copy `.env` with
   `MCP_TRANSPORT=http` and `TOKEN_DB_PATH=/data/tokens.db` set,
   `docker compose build && docker compose up -d`.
5. Verify `curl http://172.16.25.50:8765/healthz` and an authenticated MCP
   round-trip using a token minted through the admin service.
