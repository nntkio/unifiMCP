# UniFi MCP Server

An MCP (Model Context Protocol) server for Ubiquiti UniFi network devices. It
lets an AI assistant such as Claude inspect and manage a UniFi network:
devices, clients, sites, networks and VLANs, firewall rules and zone
policies, traffic and QoS rules, routing, NAT, port forwarding, WLANs, and
the various profile types. 94 tools in total; see
[Available tools](#available-tools).

It runs in one of two modes:

| Mode | How it runs | Use it for |
|------|-------------|------------|
| **stdio** (default) | The MCP client starts `unifi-mcp` as a local subprocess and talks to it over stdin/stdout. | Claude Desktop or Claude Code on your own machine. |
| **HTTP** (`MCP_TRANSPORT=http`) | A persistent Streamable HTTP service on port 8765, protected by bearer tokens that are minted in a companion web UI on port 8766. | A Docker host or NAS on the LAN, shared by several people or machines. |

Further reading:

- [docs/usage-guide.md](docs/usage-guide.md): Claude Code and Claude Desktop
  setup in depth, plus troubleshooting.
- [docs/qnap-deployment.md](docs/qnap-deployment.md): step-by-step QNAP
  Container Station deployment, including a TLS reverse proxy.
- [docs/unifi-api.md](docs/unifi-api.md): the UniFi Controller HTTP API this
  project wraps.

## Requirements

- A reachable UniFi Controller: either a self-hosted software controller or
  a UniFi OS console (UDM, UDM Pro, UCG Max), and an account with
  administrator access to it.
- For a local install: Python 3.13+ and [uv](https://docs.astral.sh/uv/).
- For a container: Docker with Compose.

## Installation

### Local (uv)

```bash
git clone https://github.com/nntkio/unifiMCP.git
cd unifiMCP
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

This installs two console scripts into `.venv/bin/`:

- `unifi-mcp`: the MCP server (stdio by default, HTTP with
  `MCP_TRANSPORT=http`).
- `unifi-mcp-admin`: the token-admin web UI. Only needed in HTTP mode.

### Docker

Build the image from source:

```bash
git clone https://github.com/nntkio/unifiMCP.git
cd unifiMCP
docker compose build          # produces unifi-mcp:latest
```

Or pull the prebuilt multi-arch image (linux/amd64 and linux/arm64) from
GitHub Container Registry, which is what the QNAP deployment files use:

```bash
docker pull ghcr.io/nntkio/unifi-mcp:latest
```

Credentials are only ever supplied at container **run time**, never as
build arguments, so the image contains no secrets and is safe to push to a
registry. The Dockerfile installs the exact versions recorded in `uv.lock`
(`mcp` is pinned below 2.0, whose server API is incompatible with this
code).

## Configuration

Everything is configured through environment variables. `.env.example`
lists every one with comments; copy it to `.env` when using Docker Compose.

Nothing loads `.env` automatically outside Docker Compose. For a local run,
export the variables yourself, or launch through `scripts/run-mcp.sh`, which
reads `.env`, forces stdio, and then starts `unifi-mcp` from the venv.

### UniFi controller

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `UNIFI_HOST` | Controller URL (e.g. `https://192.168.1.1`) | - | Yes |
| `UNIFI_USERNAME` | Controller username | - | Yes |
| `UNIFI_PASSWORD` | Controller password | - | Yes |
| `UNIFI_SITE` | Site name | `default` | No |
| `UNIFI_VERIFY_SSL` | Verify SSL certificates (`true`/`false`). Use `false` for the usual self-signed certificate. | `true` | No |
| `UNIFI_IS_UNIFI_OS` | `true` for a UniFi OS console (UDM, UDM Pro, UCG Max), which uses a different login endpoint and URL prefix. `false` for a software controller. | `false` | No |

```bash
# Self-hosted software controller (port 8443)
UNIFI_HOST=https://192.168.1.1:8443
UNIFI_USERNAME=admin
UNIFI_PASSWORD=your-password
UNIFI_SITE=default
UNIFI_VERIFY_SSL=false
UNIFI_IS_UNIFI_OS=false

# UniFi OS console (UDM / UDM Pro / UCG Max, port 443)
UNIFI_HOST=https://192.168.1.1
UNIFI_USERNAME=admin
UNIFI_PASSWORD=your-password
UNIFI_SITE=default
UNIFI_VERIFY_SSL=false
UNIFI_IS_UNIFI_OS=true
```

### MCP server transport

`MCP_TRANSPORT` selects how the server talks to its MCP client:

| Value | What happens | When to use it |
|-------|--------------|----------------|
| `stdio` | MCP over stdin/stdout. The `MCP_HTTP_*` and `TOKEN_DB_PATH` settings are ignored. | The MCP client launches `unifi-mcp` itself as a subprocess: Claude Desktop, `claude mcp add`, `docker run -i`, or `scripts/run-mcp.sh`. |
| `http` | A persistent Streamable HTTP service on `MCP_HTTP_HOST:MCP_HTTP_PORT`, protected by bearer tokens from the token-admin service. | A long-running container or NAS on the LAN that several clients connect to. This is what `docker compose up -d` needs. |

When the variable is unset the server defaults to `stdio`. `.env.example`
sets `http` because Docker Compose is its main consumer; a container
started in stdio mode has no stdin to talk to, so nothing can reach it and
its health check on port 8765 never passes. `scripts/run-mcp.sh` reads the
same `.env` but always forces `stdio`, so a client-launched server keeps
working with that file in place.

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_TRANSPORT` | `stdio` or `http`, as above | `stdio` (unset); `.env.example` sets `http` |
| `MCP_HTTP_HOST` | Bind host (HTTP mode only) | `0.0.0.0` |
| `MCP_HTTP_PORT` | Bind port (HTTP mode only) | `8765` |
| `TOKEN_DB_PATH` | SQLite database shared with the token-admin service (HTTP mode only) | `/data/tokens.db` |

### Token-admin service (HTTP mode only)

| Variable | Description | Default |
|----------|-------------|---------|
| `ROOT_ADMIN_USERNAME` | Root login username | `root` |
| `ROOT_ADMIN_PASSWORD` | Root login password. **Required.** | - |
| `ADMIN_SESSION_SECRET` | Signs session cookies. **Required.** Generate with `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` | - |
| `ADMIN_HTTP_HOST` | Bind host | `0.0.0.0` |
| `ADMIN_HTTP_PORT` | Bind port | `8766` |
| `TOKEN_DB_PATH` | Must point at the same file the MCP server uses | `/data/tokens.db` |

## Running over stdio (Claude Desktop, Claude Code)

You do not normally start the server yourself: the client launches it as a
subprocess whenever it needs it. To smoke-test the binary on its own:

```bash
export UNIFI_HOST=https://192.168.1.1 UNIFI_USERNAME=admin UNIFI_PASSWORD=your-password
export UNIFI_VERIFY_SSL=false UNIFI_IS_UNIFI_OS=true
unifi-mcp        # waits for MCP messages on stdin; Ctrl-C to stop
```

### Claude Code

```bash
claude mcp add unifi \
  -e UNIFI_HOST=https://192.168.1.1 \
  -e UNIFI_USERNAME=admin \
  -e UNIFI_PASSWORD=your-password \
  -e UNIFI_VERIFY_SSL=false \
  -e UNIFI_IS_UNIFI_OS=true \
  -- /absolute/path/to/unifiMCP/.venv/bin/unifi-mcp
```

Restart the Claude Code session afterwards; servers added mid-session are
not picked up until then. To keep the password out of the client config,
put the values in `.env` and point the command at
`/absolute/path/to/unifiMCP/scripts/run-mcp.sh` instead, with no `-e`
flags.

### Claude Desktop

Add to the Claude Desktop config file
(`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS,
`~/.config/claude/claude_desktop_config.json` on Linux), then restart
Claude Desktop.

Local install:

```json
{
  "mcpServers": {
    "unifi": {
      "command": "/absolute/path/to/unifiMCP/.venv/bin/unifi-mcp",
      "env": {
        "UNIFI_HOST": "https://192.168.1.1",
        "UNIFI_USERNAME": "admin",
        "UNIFI_PASSWORD": "your-password",
        "UNIFI_VERIFY_SSL": "false",
        "UNIFI_IS_UNIFI_OS": "true"
      }
    }
  }
}
```

Docker (the `-i` flag is what keeps stdin open for the stdio transport):

```json
{
  "mcpServers": {
    "unifi": {
      "command": "docker",
      "args": ["run", "-i", "--rm",
        "-e", "UNIFI_HOST=https://192.168.1.1",
        "-e", "UNIFI_USERNAME=admin",
        "-e", "UNIFI_PASSWORD=your-password",
        "-e", "UNIFI_VERIFY_SSL=false",
        "-e", "UNIFI_IS_UNIFI_OS=true",
        "unifi-mcp:latest"
      ]
    }
  }
}
```

## Running as a network service (HTTP)

In HTTP mode two containers run from the **same image**, separated only by
their `command:`:

| Service | Port | Purpose |
|---------|------|---------|
| `unifi-mcp` | 8765 | `POST`/`GET /mcp`: the MCP Streamable HTTP endpoint, requires `Authorization: Bearer <token>`. `GET /healthz`: unauthenticated health check used by Docker. |
| `unifi-mcp-admin` | 8766 | Web UI for creating accounts and minting or revoking bearer tokens. |

They share a Docker named volume (`unifi-mcp-data`) holding `tokens.db`:
accounts, token hashes, and the usage log. The admin service writes tokens
that the MCP server validates, with no network call between them.

### Step by step with Docker Compose

1. **Create `.env`** from the example and fill it in:

   ```bash
   cp .env.example .env
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"   # paste into ADMIN_SESSION_SECRET
   ```

   In `.env`, set the UniFi controller variables, and then:

   - Keep `MCP_TRANSPORT=http`, which the example file already sets. If it
     is changed to `stdio`, the `unifi-mcp` container starts a server that
     nothing can talk to, and its health check on port 8765 never passes.
   - `ROOT_ADMIN_PASSWORD` and `ADMIN_SESSION_SECRET`. Both are required;
     leave either one out and the `unifi-mcp-admin` container exits at
     startup.

2. **Start the stack:**

   ```bash
   docker compose up -d
   docker compose logs -f      # watch both services come up
   ```

3. **Verify the services directly**, before putting anything in front of
   them:

   ```bash
   curl -i http://localhost:8765/healthz                                          # 200, body "ok"
   curl -s -o /dev/null -w '%{http_code}\n' -X POST http://localhost:8765/mcp      # 401
   curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8766/login            # 200
   ```

   Anything other than `401` on the second line means bearer auth is not
   running. Stop and investigate: a valid token can restart devices and
   rewrite firewall rules.

4. **Mint a token** in the admin UI. See
   [Token admin service](#token-admin-service) below.

5. **Prove a real MCP call works:**

   ```bash
   TOKEN='<the token you just copied>'
   curl -sS -X POST http://localhost:8765/mcp \
     -H "Authorization: Bearer $TOKEN" \
     -H 'Accept: application/json, text/event-stream' \
     -H 'Content-Type: application/json' \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"1"}}}'
   ```

   Expect an SSE frame containing `"serverInfo":{"name":"unifi-mcp"`.

6. **Point an MCP client at it.** With Claude Code:

   ```bash
   claude mcp add --transport http unifi http://<host>:8765/mcp \
     --header "Authorization: Bearer <token>"
   ```

   Claude Desktop's config file only launches local commands, so it needs
   a small bridge to reach a remote URL with a bearer header; see the
   [usage guide](docs/usage-guide.md#connecting-to-the-network-service).
   Other clients that support remote Streamable HTTP servers need the same
   two pieces of information, typically in this shape (check your client's
   documentation for its exact format):

   ```json
   {
     "mcpServers": {
       "unifi": {
         "url": "http://<host>:8765/mcp",
         "headers": {
           "Authorization": "Bearer <token>"
         }
       }
     }
   }
   ```

### Things that bite

- **The `Accept` header must list both** `application/json` and
  `text/event-stream`. Omit either and the MCP SDK answers `406 Not
  Acceptable`, which is easy to misread as an auth failure.
- **`/mcp` and `/mcp/` both work.** The bare path is rewritten internally
  rather than redirected, because many clients refuse to follow a redirect
  on `POST`.
- **A reverse proxy must not buffer.** MCP responses are Server-Sent
  Events, and nginx buffers proxied responses by default, so the client
  connects and then hangs with no error anywhere. Set `proxy_buffering off`,
  `proxy_cache off`, and long read/send timeouts on the MCP host, and always
  give clients the `https://` URL once TLS is on. Full settings are in
  [docs/qnap-deployment.md](docs/qnap-deployment.md).
- **Both services speak plain HTTP.** TLS is expected to come from a reverse
  proxy in front. Until you have one, admin passwords and freshly minted
  tokens cross the LAN in cleartext. Never port-forward 8765 or 8766 from
  the internet.
- **A token grants everything the server can do**, including mutating
  operations. There is no per-token scoping, so prefer short expiries.
- **`TOKEN_DB_PATH` must match** between the two services, and the token
  database lives only in the `unifi-mcp-data` volume. Deleting the volume
  invalidates every issued token and account.
- **The Compose health check probes port 8765 inside the container.** If
  you change `MCP_HTTP_PORT`, update the `healthcheck` in the compose file
  to match.
- **Upgrading:** `docker compose pull && docker compose up -d` for the
  registry image, or `docker compose up -d --build` for a source build.
  Accounts and tokens survive, since they live in the volume rather than
  the image.

## Token admin service

`unifi-mcp-admin` is a small web UI, self-contained (fonts, stylesheet, and
script are served by the service itself, so it works on a LAN with no
internet access).

**Root** is the identity in `ROOT_ADMIN_USERNAME` / `ROOT_ADMIN_PASSWORD`.
It exists only as environment variables, with no database row, which is
what makes it structurally unable to own a bearer token. Signing in as root
opens two screens:

- **Accounts** (`/admin`): create accounts, and see every account with the
  tokens created under it (label, created, expires, status) plus totals for
  all, active, and revoked tokens. For any account root can:
  - **Reset password**: a dialog asks for the new temporary password. The
    old password stops working immediately; the account's existing tokens
    keep working. The dialog also works without JavaScript.
  - **Delete user**: removes the account and all of its tokens.
  - **Revoke** any single token.
- **Usage** (`/admin/usage`): a log of every call made to the MCP endpoint:
  time (UTC), user, token, client IP, `X-Forwarded-For`, JSON-RPC method,
  tool name, HTTP status, and duration. Each column has its own filter
  (combined with AND) and the list pages 50 rows at a time. The MCP service
  writes this log itself, one row per JSON-RPC message that passes bearer
  auth, into the same SQLite database, so it needs no extra configuration.
  Behind a reverse proxy the IP column shows the first `X-Forwarded-For`
  hop and the direct peer is stored as well.

**Everyone else** logs in at `http://<host>:8766/login` with the temporary
password root gave them and lands on **My tokens** (`/tokens`) to create,
view, and revoke their own tokens. Each token has a label and an optional
expiry. A newly created token is shown **exactly once**: only its SHA-256
hash is stored, so copy it immediately. Account passwords are stored as
argon2 hashes.

The typical first run:

```text
http://<host>:8766/login          log in as root, create an account for yourself
http://<host>:8766/login          log out, log back in as that account
http://<host>:8766/tokens         create a token, copy it
http://<host>:8766/admin/usage    later, as root: who called what, from where
```

## Deploying to a NAS (QNAP Container Station)

The full walkthrough, including verification steps and the nginx settings
for a TLS reverse proxy, is in
[docs/qnap-deployment.md](docs/qnap-deployment.md). The pieces involved:

- **`scripts/publish-image.sh`** builds the multi-arch image on a
  workstation and pushes it to `ghcr.io/nntkio/unifi-mcp`, tagged `latest`,
  the version from `pyproject.toml`, and `sha-<git sha>`. Pass one extra
  tag (`scripts/publish-image.sh rc1`) to add it alongside those, or
  `--local` to build for this machine only and load it into the local
  Docker daemon as `:local` without pushing. It needs Docker with buildx and
  the `gh` CLI logged in with the `write:packages` scope
  (`gh auth refresh -s write:packages`), or `GHCR_TOKEN` and `GHCR_USER`
  for a dedicated PAT. `IMAGE` and `PLATFORMS` override the destination and
  targets. If the default buildx builder cannot do both platforms the
  script creates one named `unifi-mcp-multiarch` for the build.
- **`deploy/docker-compose.qnap.yml`** pulls that image instead of
  building, and reads its settings from a sibling `qnap.env` (copy
  `deploy/qnap.env.example`). Use it when you can reach the NAS over SSH:

  ```bash
  docker compose -f docker-compose.qnap.yml --env-file qnap.env pull
  docker compose -f docker-compose.qnap.yml --env-file qnap.env up -d
  ```

- **`deploy/docker-compose.container-station.yml`** is the paste-ready
  variant for Container Station's "Create Application" box, which cannot
  see a sibling env file, so the settings are inlined under `environment:`.
  Replace every `<...>` placeholder. Note that Container Station stores
  these values in its application config, readable by anyone with NAS admin
  access.

`deploy/qnap.env` and any `deploy/*.local.yml` are ignored by git, so real
values kept next to the templates never get committed.

## Available tools

All tools operate on the site named by `UNIFI_SITE`; there is no per-call
site override. Mutating tools take effect on the controller immediately.

| Domain | Tools |
|--------|-------|
| Devices | `get_devices`, `get_device_activity`, `restart_device`, `adopt_device`, `force_provision_device`, `upgrade_device`, `power_cycle_port`, `set_device_locate`, `unset_device_locate` |
| Clients | `get_clients`, `block_client`, `unblock_client`, `disconnect_client`, `forget_client`, `authorize_guest`, `unauthorize_guest` |
| Sites | `get_sites`, `get_site_health`, `get_sdn_status` |
| Networks (VLANs) | `get_networks`, `create_network`, `update_network`, `delete_network` |
| Firewall rules and zone policies | `get_firewall_rules`, `create_firewall_rule`, `delete_firewall_rule`, `enable_firewall_rule`, `disable_firewall_rule`, `create_firewall_policy`, `enable_firewall_policy`, `disable_firewall_policy`, `batch_update_firewall_policies`, `batch_delete_firewall_policies`, `get_firewall_zones`, `get_firewall_zone_matrix` |
| Firewall groups | `get_firewall_groups`, `create_firewall_group`, `update_firewall_group`, `delete_firewall_group` |
| Traffic rules | `get_traffic_rules`, `create_traffic_rule`, `update_traffic_rule`, `delete_traffic_rule`, `enable_traffic_rule`, `disable_traffic_rule` |
| Traffic routes (policy-based routing) | `get_traffic_routes`, `create_traffic_route`, `update_traffic_route`, `delete_traffic_route` |
| QoS rules | `get_qos_rules`, `create_qos_rule`, `update_qos_rule`, `delete_qos_rule`, `batch_update_qos_rules` |
| NAT rules | `get_nat_rules`, `create_nat_rule`, `update_nat_rule`, `delete_nat_rule` |
| Port forwarding | `get_port_forwards`, `create_port_forward`, `update_port_forward`, `delete_port_forward` |
| Static routes | `get_static_routes`, `create_static_route`, `update_static_route`, `delete_static_route` |
| WLANs (Wi-Fi networks) | `get_wlans`, `create_wlan`, `update_wlan`, `delete_wlan` |
| Port profiles | `get_port_profiles`, `create_port_profile`, `update_port_profile`, `delete_port_profile` |
| RADIUS profiles | `get_radius_profiles`, `create_radius_profile`, `update_radius_profile`, `delete_radius_profile` |
| WAN SLA profiles | `get_wan_sla_profiles`, `create_wan_sla_profile`, `update_wan_sla_profile`, `delete_wan_sla_profile` |
| WLAN rate profiles | `get_wlan_rate_profiles`, `create_wlan_rate_profile`, `update_wlan_rate_profile`, `delete_wlan_rate_profile` |
| Network objects (address/port groups) | `get_objects`, `create_object`, `update_object`, `delete_object` |
| Object-oriented network configs | `get_oo_network_configs`, `create_oo_network_config`, `update_oo_network_config`, `delete_oo_network_config` |

Predefined zone-based firewall policies are read-only: the enable, disable,
batch-update, and batch-delete policy tools reject them. Each tool's
parameters are described in its MCP schema, which any client shows when it
lists the server's tools.

## Development

```bash
pytest                 # run tests
pytest --cov=src       # with coverage
ruff check .           # lint
ruff format .          # format
```

The package layout (one `unifi_client/_<domain>.py` mixin plus one
`server/_<domain>.py` tool module per UniFi API domain, with matching test
files) and the steps for adding a new domain are described in
[CLAUDE.md](CLAUDE.md).

## License

MIT
