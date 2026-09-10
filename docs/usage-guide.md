# UnifiMCP: Configuration and Usage Guide

This is the complete guide to installing, configuring, running, and connecting
the UnifiMCP server to Claude. For the raw UniFi Controller HTTP API that this
project wraps, see [`unifi-api.md`](./unifi-api.md). For deploying the network
service to a QNAP NAS behind a TLS reverse proxy, see
[`qnap-deployment.md`](./qnap-deployment.md).

## Overview

UnifiMCP is an MCP (Model Context Protocol) server that exposes UniFi network
controller operations as tools an AI assistant can call: devices, clients,
sites, networks and VLANs, firewall rules and zone policies, firewall groups,
traffic and QoS rules, traffic routes, NAT, port forwarding, static routes,
WLANs, port / RADIUS / WAN SLA / WLAN rate profiles, network objects, and
object-oriented network configs. That is 94 tools; the full list is in
[section 5](#5-available-tools).

It talks to your UniFi Controller (self-hosted, or a UniFi OS console such as
a UDM/UDM Pro) over its local HTTP API, and speaks MCP to the assistant in
one of two ways:

- **stdio** (the default): the MCP client starts `unifi-mcp` as a local
  subprocess and talks to it over stdin/stdout. This is how Claude Desktop
  and Claude Code normally use it, and what sections 3 and 4 cover.
- **HTTP** (`MCP_TRANSPORT=http`): a persistent Streamable HTTP service that
  several clients connect to over the network, protected by bearer tokens.
  See [section 9](#9-running-as-a-network-service).

## Prerequisites

- A reachable UniFi Controller (self-hosted software controller, or a UniFi
  OS console such as UDM, UDM Pro, or UCG Max) and an account with
  administrator access to it.
- Either Docker + Docker Compose, **or** Python 3.13+ with
  [`uv`](https://docs.astral.sh/uv/) for a local install.
- Claude Code and/or Claude Desktop, to connect to the running server.

## 1. Installation

### Option A: Local (uv)

```bash
git clone https://github.com/nntkio/unifiMCP.git
cd unifiMCP
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

This installs two console scripts into `.venv/bin/`:

- `unifi-mcp`: the server, and the executable you point Claude at.
- `unifi-mcp-admin`: the token-admin web UI. Only needed in HTTP mode.

### Option B: Docker

Build the image from source:

```bash
git clone https://github.com/nntkio/unifiMCP.git
cd unifiMCP
docker compose build        # produces unifi-mcp:latest
```

Or pull the prebuilt multi-arch image (linux/amd64 and linux/arm64) from
GitHub Container Registry, which is what the QNAP deployment files use:

```bash
docker pull ghcr.io/nntkio/unifi-mcp:latest
```

Either image serves both modes: `docker run -i ...` for a stdio server the
client launches (section 3), or `docker compose up -d` for the network
service (section 9).

Credentials are only ever supplied at container **run time**, via `.env`
(loaded through `env_file` in `docker-compose.yml`) or `-e` flags. They are
never passed as Docker build arguments and never baked into the image
layers, so the built image is safe to share, archive, or push to a registry.
The Dockerfile installs the exact versions recorded in `uv.lock`; `mcp` is
pinned below 2.0, whose server API is incompatible with this code.

## 2. Configuration

All configuration is via environment variables. `.env.example` documents
every one; copy it to `.env` and edit it. Exactly two things read `.env`:

- `docker-compose.yml`, through `env_file`, for both services.
- `scripts/run-mcp.sh`, the stdio launcher described in section 4.

Nothing else does. A plain `unifi-mcp` run, or a `claude mcp add` without
the wrapper script, needs the variables exported or passed explicitly.

### UniFi controller

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `UNIFI_HOST` | UniFi Controller URL (e.g. `https://192.168.1.1`) | — | Yes |
| `UNIFI_USERNAME` | Controller username | — | Yes |
| `UNIFI_PASSWORD` | Controller password | — | Yes |
| `UNIFI_SITE` | UniFi site name | `default` | No |
| `UNIFI_VERIFY_SSL` | Verify SSL certificates (`true`/`false`) | `true` | No |
| `UNIFI_IS_UNIFI_OS` | Controller is a UniFi OS device (UDM/UDM Pro/UCG Max) (`true`/`false`) | `false` | No |

Notes:
- Set `UNIFI_VERIFY_SSL=false` if your controller uses a self-signed
  certificate (the common case for local controllers).
- Set `UNIFI_IS_UNIFI_OS=true` only for UniFi OS consoles (UDM, UDM Pro, UCG
  Max) — these use a different login endpoint and URL prefix internally; see
  [`unifi-api.md`](./unifi-api.md) for why.

Example `.env` for a self-hosted software controller (port 8443):

```bash
UNIFI_HOST=https://192.168.1.1:8443
UNIFI_USERNAME=admin
UNIFI_PASSWORD=your-password
UNIFI_SITE=default
UNIFI_VERIFY_SSL=false
UNIFI_IS_UNIFI_OS=false
```

Example `.env` for a UniFi OS console (UDM/UDM Pro, port 443):

```bash
UNIFI_HOST=https://192.168.1.1
UNIFI_USERNAME=admin
UNIFI_PASSWORD=your-password
UNIFI_SITE=default
UNIFI_VERIFY_SSL=false
UNIFI_IS_UNIFI_OS=true
```

### Choosing a transport: `MCP_TRANSPORT`

`MCP_TRANSPORT` selects how the server talks to its MCP client:

| Value | What happens | When to use it |
|-------|--------------|----------------|
| `stdio` | MCP over stdin/stdout. The `MCP_HTTP_*` and `TOKEN_DB_PATH` settings are ignored. | The MCP client launches `unifi-mcp` itself as a subprocess: Claude Desktop, `claude mcp add`, `docker run -i`, or `scripts/run-mcp.sh`. |
| `http` | A persistent Streamable HTTP service on `MCP_HTTP_HOST:MCP_HTTP_PORT`, protected by bearer tokens from the token-admin service. | A long-running container or NAS on the LAN that several clients connect to. This is what `docker compose up -d` needs. |

When the variable is unset the server defaults to `stdio`.

`.env.example` sets `http`, because Docker Compose is its main consumer: a
container started in stdio mode has no stdin to talk to, so nothing can
reach it and its health check on port 8765 never passes. The same `.env`
still works for the stdio path, because `scripts/run-mcp.sh` forces
`MCP_TRANSPORT=stdio` after loading it.

### HTTP-mode variables

Only read when `MCP_TRANSPORT=http` (the first block) or by the
`unifi-mcp-admin` service (the second block).

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_HTTP_HOST` | Bind host. Keep `0.0.0.0` inside a container; a LAN address only works with host networking. | `0.0.0.0` |
| `MCP_HTTP_PORT` | Bind port | `8765` |
| `TOKEN_DB_PATH` | SQLite database shared with the token-admin service | `/data/tokens.db` |

| Variable | Description | Default |
|----------|-------------|---------|
| `ROOT_ADMIN_USERNAME` | Root login username for the admin UI | `root` |
| `ROOT_ADMIN_PASSWORD` | Root login password. **Required**; the service exits without it. | — |
| `ADMIN_SESSION_SECRET` | Signs session cookies. **Required**; the service exits without it. Generate with `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`. | — |
| `ADMIN_HTTP_HOST` | Bind host | `0.0.0.0` |
| `ADMIN_HTTP_PORT` | Bind port | `8766` |
| `TOKEN_DB_PATH` | Must be the same file the MCP server uses | `/data/tokens.db` |

## 3. Running the server (stdio)

You generally don't need to run the server by hand — Claude Code / Claude
Desktop launch it as a subprocess when you connect it (see section 4). These
commands are for testing it standalone.

**Docker, one-off** (the `-i` keeps stdin open, which stdio needs):
```bash
docker run -i --rm \
  -e UNIFI_HOST="https://192.168.1.1" \
  -e UNIFI_USERNAME="admin" \
  -e UNIFI_PASSWORD="your-password" \
  -e UNIFI_VERIFY_SSL="false" \
  -e UNIFI_IS_UNIFI_OS="true" \
  unifi-mcp:latest
```

**Local:**
```bash
source .venv/bin/activate
UNIFI_HOST=... UNIFI_USERNAME=... UNIFI_PASSWORD=... unifi-mcp
```

In stdio mode the server speaks newline-delimited JSON-RPC 2.0 over
stdin/stdout — it will look like it's hanging, since it's waiting for a
client to send it requests. That's expected; Ctrl-C to stop it.

`docker compose up -d` is **not** a stdio server. With the shipped
`.env.example` it starts the network service described in
[section 9](#9-running-as-a-network-service).

## 4. Connecting to Claude

### Claude Code

Register it as a local MCP server (credentials stay private to you, stored
outside the repo):

```bash
claude mcp add unifi \
  -e UNIFI_HOST=https://192.168.1.1 \
  -e UNIFI_USERNAME=admin \
  -e UNIFI_PASSWORD=your-password \
  -e UNIFI_VERIFY_SSL=false \
  -e UNIFI_IS_UNIFI_OS=true \
  -- /absolute/path/to/unifiMCP/.venv/bin/unifi-mcp
```

- Use the **absolute path** to the venv's `unifi-mcp` binary (local install),
  or `docker` as the command with `run -i --rm ... unifi-mcp:latest` as the
  args, if you'd rather run it containerized.
- `-s local` is the default scope — private to you, in this project only, and
  not committed to the repo. Use `-s project` instead if you want it recorded
  in `.mcp.json` and shared with teammates (do **not** put real credentials
  in a project-scoped/shared config).
- Restart your Claude Code session after adding a new MCP server — tools
  from servers registered mid-session aren't picked up until the session
  restarts.

Useful follow-up commands:
```bash
claude mcp list             # see all configured servers
claude mcp get unifi        # check connection status + resolved config
claude mcp remove unifi -s local   # remove it
```

### Claude Desktop

Add to your Claude Desktop config file
(`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS,
`~/.config/claude/claude_desktop_config.json` on Linux):

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

Or, to run it via Docker instead of a local venv:

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

Restart Claude Desktop after editing the config.

### Keeping credentials out of the client config

The examples above put `UNIFI_USERNAME`/`UNIFI_PASSWORD` directly in
`claude_desktop_config.json` (or in shell history via `claude mcp add -e`).
That file often gets synced, backed up, or screenshotted for troubleshooting,
so it's worth keeping secrets out of it. Instead, point the client at the
wrapper script that ships in the repo, `scripts/run-mcp.sh`, which loads
`.env` at launch:

```bash
#!/usr/bin/env bash
# Launches unifi-mcp with credentials loaded from .env, so secrets never
# need to be duplicated into an MCP client's config file.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$REPO_ROOT/.env"

if [[ -f "$ENV_FILE" ]]; then
  # Read as literal KEY=VALUE pairs rather than `source`-ing the file, since
  # sourcing treats values as shell code and mangles special characters
  # (e.g. a password containing $, !, or &).
  while IFS='=' read -r key value; do
    [[ -z "$key" || "$key" == \#* ]] && continue
    export "$key=$value"
  done < "$ENV_FILE"
fi

# This script exists to be launched by an MCP client as a subprocess, so it
# always speaks stdio, whatever .env says (the same file serves docker
# compose, where MCP_TRANSPORT=http is the right setting).
export MCP_TRANSPORT=stdio

exec "$REPO_ROOT/.venv/bin/unifi-mcp"
```

Make sure it is executable (`chmod +x scripts/run-mcp.sh`), then point your
client at it with no `env` block at all:

```json
{
  "mcpServers": {
    "unifi": {
      "command": "/absolute/path/to/unifiMCP/scripts/run-mcp.sh"
    }
  }
}
```

For Claude Code, the equivalent is:

```bash
claude mcp add unifi -- /absolute/path/to/unifiMCP/scripts/run-mcp.sh
```

Credentials then live in exactly one place — `.env`, which is gitignored and
should be `chmod 600` (`chmod 600 .env`) so only your user account can read
it — instead of being duplicated into the MCP client's config. Because the
script forces stdio, the same `.env` can keep `MCP_TRANSPORT=http` for
Docker Compose.

For stronger protection than a plaintext `.env` file (e.g. the password
shouldn't be readable by anything with filesystem access to the repo), add a
macOS Keychain lookup after the loop that reads `.env`, such as:

```bash
export UNIFI_PASSWORD="$(security find-generic-password -a "$USER" -s unifi-mcp -w)"
```

### Connecting to the network service

Once the HTTP service is running (section 9) and you have minted a token in
its admin UI, register it as a remote server instead of a local command.

Claude Code:

```bash
claude mcp add --transport http unifi http://<host>:8765/mcp \
  --header "Authorization: Bearer <token>"
```

That is equivalent to this entry in `.mcp.json` or the settings file:

```json
{
  "mcpServers": {
    "unifi": {
      "type": "http",
      "url": "http://<host>:8765/mcp",
      "headers": {
        "Authorization": "Bearer <token>"
      }
    }
  }
}
```

Claude Desktop's config file only launches local commands, so it cannot
send a bearer header to a remote URL by itself. Bridge it with the
`mcp-remote` package, which runs as a local stdio server and forwards to the
HTTP endpoint:

```json
{
  "mcpServers": {
    "unifi": {
      "command": "npx",
      "args": [
        "-y", "mcp-remote",
        "http://<host>:8765/mcp",
        "--header", "Authorization:${AUTH_HEADER}"
      ],
      "env": {
        "AUTH_HEADER": "Bearer <token>"
      }
    }
  }
}
```

Passing the header value through an environment variable, with no space
after the colon, is the form `mcp-remote` recommends because some Claude
Desktop builds mis-split arguments containing spaces. Check the `mcp-remote`
documentation for its current flags. Claude Desktop's Connectors settings
can also add remote servers, but that path is built around OAuth rather
than a static bearer token.

Behind a TLS reverse proxy, always use the `https://` URL. With HTTP-to-HTTPS
redirection on, an `http://` request gets a 301, and MCP clients generally
do not follow redirects on `POST`.

## 5. Available tools

`UNIFI_SITE` (from your config) determines which site every tool operates
against; there's no per-call site override. Mutating tools take effect on the
controller immediately.

Parameter conventions, which hold across every domain:

- `get_*` tools take no parameters (except `get_clients`).
- Device and client tools identify their target by `mac`.
- `update_*`, `delete_*`, `enable_*`, and `disable_*` tools take the
  resource's controller ID (`rule_id`, `network_id`, `profile_id`, and so
  on), as returned by the matching `get_*` tool.
- `create_*` and `update_*` tools take the resource as one object parameter
  (`rule`, `network`, `profile`, ...) holding the fields the UniFi
  controller API expects for that resource; see
  [`unifi-api.md`](./unifi-api.md).
- `batch_*` tools take an array.

Required parameters are marked with `*`.

| Domain | Tools | Parameters |
|--------|-------|------------|
| Devices | `get_devices` | none |
| | `restart_device`, `adopt_device`, `force_provision_device`, `upgrade_device`, `set_device_locate`, `unset_device_locate`, `get_device_activity` | `mac`* |
| | `power_cycle_port` | `mac`*, `port_idx`* (integer) |
| Clients | `get_clients` | `include_offline` (boolean, default `false`) |
| | `block_client`, `unblock_client`, `disconnect_client`, `forget_client`, `unauthorize_guest` | `mac`* |
| | `authorize_guest` | `mac`*, `minutes` (integer) |
| Sites | `get_sites`, `get_site_health`, `get_sdn_status` | none |
| Networks (VLANs) | `get_networks` | none |
| | `create_network` | `network`* |
| | `update_network` | `network_id`*, `network`* |
| | `delete_network` | `network_id`* |
| Firewall rules and zone policies | `get_firewall_rules`, `get_firewall_zones`, `get_firewall_zone_matrix` | none |
| | `create_firewall_rule` | `rule`* |
| | `enable_firewall_rule`, `disable_firewall_rule`, `delete_firewall_rule` | `rule_id`* |
| | `create_firewall_policy` | `policy`* |
| | `enable_firewall_policy`, `disable_firewall_policy` | `policy_id`* |
| | `batch_update_firewall_policies` | `policies`* (array of policy objects) |
| | `batch_delete_firewall_policies` | `policy_ids`* (array of IDs) |
| Firewall groups | `get_firewall_groups` | none |
| | `create_firewall_group` | `group`* |
| | `update_firewall_group` | `group_id`*, `group`* |
| | `delete_firewall_group` | `group_id`* |
| Traffic rules | `get_traffic_rules` | none |
| | `create_traffic_rule` | `rule`* |
| | `update_traffic_rule` | `rule_id`*, `rule`* |
| | `delete_traffic_rule`, `enable_traffic_rule`, `disable_traffic_rule` | `rule_id`* |
| Traffic routes (policy-based routing) | `get_traffic_routes` | none |
| | `create_traffic_route` | `route`* |
| | `update_traffic_route` | `route_id`*, `route`* |
| | `delete_traffic_route` | `route_id`* |
| QoS rules | `get_qos_rules` | none |
| | `create_qos_rule` | `rule`* |
| | `update_qos_rule` | `rule_id`*, `rule`* |
| | `delete_qos_rule` | `rule_id`* |
| | `batch_update_qos_rules` | `rules`* (array of rule objects) |
| NAT rules | `get_nat_rules` | none |
| | `create_nat_rule` | `rule`* |
| | `update_nat_rule` | `rule_id`*, `rule`* |
| | `delete_nat_rule` | `rule_id`* |
| Port forwarding | `get_port_forwards` | none |
| | `create_port_forward` | `forward`* |
| | `update_port_forward` | `forward_id`*, `forward`* |
| | `delete_port_forward` | `forward_id`* |
| Static routes | `get_static_routes` | none |
| | `create_static_route` | `route`* |
| | `update_static_route` | `route_id`*, `route`* |
| | `delete_static_route` | `route_id`* |
| WLANs (Wi-Fi networks) | `get_wlans` | none |
| | `create_wlan` | `wlan`* |
| | `update_wlan` | `wlan_id`*, `wlan`* |
| | `delete_wlan` | `wlan_id`* |
| Port profiles | `get_port_profiles` | none |
| | `create_port_profile` | `profile`* |
| | `update_port_profile` | `profile_id`*, `profile`* |
| | `delete_port_profile` | `profile_id`* |
| RADIUS profiles | `get_radius_profiles` | none |
| | `create_radius_profile` | `profile`* |
| | `update_radius_profile` | `profile_id`*, `profile`* |
| | `delete_radius_profile` | `profile_id`* |
| WAN SLA profiles | `get_wan_sla_profiles` | none |
| | `create_wan_sla_profile` | `profile`* |
| | `update_wan_sla_profile` | `profile_id`*, `profile`* |
| | `delete_wan_sla_profile` | `profile_id`* |
| WLAN rate profiles | `get_wlan_rate_profiles` | none |
| | `create_wlan_rate_profile` | `profile`* |
| | `update_wlan_rate_profile` | `profile_id`*, `profile`* |
| | `delete_wlan_rate_profile` | `profile_id`* |
| Network objects (address/port groups) | `get_objects` | none |
| | `create_object` | `object`* |
| | `update_object` | `object_id`*, `object`* |
| | `delete_object` | `object_id`* |
| Object-oriented network configs | `get_oo_network_configs` | none |
| | `create_oo_network_config` | `config`* |
| | `update_oo_network_config` | `config_id`*, `config`* |
| | `delete_oo_network_config` | `config_id`* |

Predefined zone-based firewall policies are read-only: the enable, disable,
batch-update, and batch-delete policy tools reject them.

## 6. How it behaves

- **Connection reuse:** the server authenticates once and reuses that
  session across all tool calls in the process's lifetime, instead of
  logging in and out per call. If the session expires, it transparently
  re-authenticates once and retries the request.
- **Error messages:** authentication failures and connectivity failures are
  reported with actionable text (check credentials vs. check `UNIFI_HOST`/
  network), distinct from other UniFi API errors.
- **Unknown tool calls** return a plain `Unknown tool: <name>` message rather
  than raising, and don't require a controller connection at all.
- **In HTTP mode**, every JSON-RPC message that passes bearer authentication
  is also written to the usage log the admin UI shows (section 9).

## 7. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `Authentication failed: ...` | Wrong `UNIFI_USERNAME`/`UNIFI_PASSWORD`, or the account lacks controller access. |
| `Connection failed: ...` | Wrong `UNIFI_HOST`, controller unreachable from where the server runs (check Docker networking — use `host.docker.internal` if the controller is on the host's LAN and the container can't reach it directly), or a firewall block. |
| SSL certificate errors | Set `UNIFI_VERIFY_SSL=false` for self-signed controller certificates. |
| Tools don't show up in Claude Code after `claude mcp add` | Restart the Claude Code session — newly added MCP servers aren't loaded into an already-running session. |
| Login works via browser but not here | Confirm `UNIFI_IS_UNIFI_OS` matches your controller type — UniFi OS consoles (UDM/UDM Pro/UCG Max) use a different login endpoint and URL prefix than a software controller. |
| Claude launches the server but it never answers, and `.env` is in use | `MCP_TRANSPORT=http` reached a client-launched server. Launch through `scripts/run-mcp.sh`, which forces stdio, or export `MCP_TRANSPORT=stdio`. |
| `docker compose up -d`: the `unifi-mcp` container is never healthy | `MCP_TRANSPORT` is `stdio` in `.env`. Set it to `http`; a container has no stdin for a stdio server to use. |
| `unifi-mcp-admin` exits with `KeyError: 'ADMIN_SESSION_SECRET'` or a `ROOT_ADMIN_PASSWORD` error | Both variables are required. Add them to `.env`. |
| Every request to `/mcp` returns `401` | Missing or wrong bearer token, the token was revoked or expired, or `TOKEN_DB_PATH` differs between the two services. |
| Requests to `/mcp` return `406 Not Acceptable` | The `Accept` header must list both `application/json` and `text/event-stream`. |
| The client connects to the HTTP service but hangs | A reverse proxy is buffering the SSE stream. Set `proxy_buffering off` on it; see [`qnap-deployment.md`](./qnap-deployment.md). Test the container's own port directly to confirm the proxy is at fault. |
| `uvicorn` fails to bind in the container | `MCP_HTTP_HOST` or `ADMIN_HTTP_HOST` is set to a LAN address the container does not own. Use `0.0.0.0`. |

## 8. Development

See [`CLAUDE.md`](../CLAUDE.md) for the test/lint workflow (`pytest`,
`ruff check .`, `ruff format .`), the per-domain package layout, the steps
for adding a new UniFi API domain, and branching conventions. See
[`unifi-api.md`](./unifi-api.md) for the underlying UniFi Controller HTTP API
reference (endpoints, auth, response format, WebSocket events) that the
`unifi_client/` package wraps.

## 9. Running as a network service

Instead of stdio, the server can run as a persistent Streamable HTTP
service that several people and machines share. Set `MCP_TRANSPORT=http`
(see [section 2](#choosing-a-transport-mcp_transport)); this is what the
repo's `docker-compose.yml` is for, and what `.env.example` is set up for.

Two containers run from the **same image**, separated only by their
`command:`:

| Service | Port | Purpose |
|---------|------|---------|
| `unifi-mcp` | 8765 | `POST`/`GET /mcp`, the MCP Streamable HTTP endpoint, requires `Authorization: Bearer <token>`. `GET /healthz`, unauthenticated, used by the Docker health check. |
| `unifi-mcp-admin` | 8766 | Web UI for creating accounts and minting or revoking bearer tokens. |

They share a Docker named volume (`unifi-mcp-data`) holding `tokens.db`:
accounts, token hashes, and the usage log. The admin service writes tokens
that the MCP server validates, with no network call between them.

### Quick start

```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(32))"   # paste into ADMIN_SESSION_SECRET
# edit .env: UniFi variables, ROOT_ADMIN_PASSWORD, ADMIN_SESSION_SECRET; keep MCP_TRANSPORT=http
docker compose up -d
docker compose logs -f
```

Then verify, before putting anything in front of it:

```bash
curl -i http://localhost:8765/healthz                                       # 200, body "ok"
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://localhost:8765/mcp   # 401
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8766/login         # 200
```

The second line must print `401`; anything else means bearer auth is not
running. The README's "Running as a network service" section continues from
here with a real `initialize` call and a list of the things that commonly go
wrong.

### Token admin service

Open `http://<host>:8766/login`.

**Root** is the identity in `ROOT_ADMIN_USERNAME` / `ROOT_ADMIN_PASSWORD`.
It exists only as environment variables, with no database row, so it can
never own a bearer token. Root sees two screens:

- **Accounts** (`/admin`): create accounts, and see every account with its
  tokens (label, created, expires, status). For any account root can
  **reset the password** (a dialog asks for the new temporary password; the
  old one stops working immediately and the account's tokens keep working),
  **delete the user** together with all of its tokens, or **revoke** any
  single token.
- **Usage** (`/admin/usage`): every call made to the MCP endpoint, with
  time (UTC), user, token, client IP, `X-Forwarded-For`, JSON-RPC method,
  tool name, HTTP status, and duration. Each column has its own filter and
  the list pages 50 rows at a time.

**Everyone else** logs in with the temporary password root gave them and
lands on **My tokens** (`/tokens`) to create, view, and revoke their own
tokens. Each token has a label and an optional expiry. A new token is shown
**exactly once**; only its SHA-256 hash is stored, so copy it immediately.
Account passwords are stored as argon2 hashes.

Then connect Claude as described in
[section 4](#connecting-to-the-network-service).

### Security notes

- Both services speak plain HTTP. TLS is expected to come from a reverse
  proxy in front; until you have one, admin passwords and freshly minted
  tokens cross the LAN in cleartext. Never port-forward 8765 or 8766 from
  the internet.
- A valid token grants everything the server can do, including restarting
  devices and rewriting firewall rules. There is no per-token scoping, so
  prefer short expiries.
- The token database lives only in the `unifi-mcp-data` volume. Deleting
  the volume invalidates every issued token and account.

### Upgrading

```bash
docker compose pull && docker compose up -d     # registry image
docker compose up -d --build                    # source build
```

Accounts and tokens survive, since they live in the volume rather than the
image.

### Deploying to a NAS

[`qnap-deployment.md`](./qnap-deployment.md) covers publishing the image
with `scripts/publish-image.sh`, the compose files in `deploy/`, the
Container Station UI path, verification, and the nginx settings a TLS
reverse proxy needs so it does not buffer the SSE stream.
