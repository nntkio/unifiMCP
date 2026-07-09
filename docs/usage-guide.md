# UnifiMCP: Configuration and Usage Guide

This is the complete guide to installing, configuring, running, and connecting
the UnifiMCP server to Claude. For the raw UniFi Controller HTTP API that this
project wraps, see [`unifi-api.md`](./unifi-api.md).

## Overview

UnifiMCP is an MCP (Model Context Protocol) server that exposes UniFi network
controller operations — listing devices/clients, blocking/restarting things,
reading site health — as tools an AI assistant can call. It talks to your
UniFi Controller (self-hosted or a UniFi OS console like a UDM/UDM Pro) over
its local HTTP API and speaks MCP over stdio to the assistant.

## Prerequisites

- A reachable UniFi Controller (self-hosted software controller, or a UniFi
  OS console such as UDM, UDM Pro, or UCG Max) and an account with
  administrator access to it.
- Either Docker + Docker Compose, **or** Python 3.13+ with
  [`uv`](https://docs.astral.sh/uv/) for a local install.
- Claude Code and/or Claude Desktop, to connect to the running server.

## 1. Installation

### Option A: Docker (recommended)

```bash
git clone https://github.com/nntkio/unifiMCP.git
cd unifiMCP
cp .env.example .env
# edit .env with your controller URL and credentials — see Configuration below
docker compose build
```

Credentials are only ever supplied at container **run time**, via `.env`
(loaded through `env_file` in `docker-compose.yml`). They are never passed as
Docker build arguments and never baked into the image layers, so the built
image is safe to share, archive, or push to a registry.

### Option B: Local (uv)

```bash
git clone https://github.com/nntkio/unifiMCP.git
cd unifiMCP
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

This installs the `unifi-mcp` console script into `.venv/bin/unifi-mcp`,
which is the executable you'll point Claude at.

## 2. Configuration

All configuration is via environment variables (or a `.env` file, copied
from `.env.example`):

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

## 3. Running the server

You generally don't need to run the server by hand — Claude Code / Claude
Desktop launch it as a subprocess when you connect it (see Section 4). These
commands are for testing it standalone.

**Docker Compose:**
```bash
docker compose up -d
docker compose logs -f   # follow logs
docker compose down      # stop
```

**Docker, one-off:**
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

The server speaks newline-delimited JSON-RPC 2.0 over stdin/stdout (the MCP
stdio transport) — it will look like it's hanging, since it's waiting for a
client to send it requests. That's expected; Ctrl-C to stop it.

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

## 5. Available tools

| Tool | Parameters | Description |
|------|------------|-------------|
| `get_devices` | — | List all network devices (access points, switches, gateways) — name, MAC, model, online/offline status, IP, firmware version. |
| `restart_device` | `mac` (required) | Restart a device by MAC address. |
| `get_clients` | `include_offline` (bool, optional, default `false`) | List currently connected clients; pass `include_offline: true` to include historical/offline clients too. |
| `block_client` | `mac` (required) | Block a client from the network. |
| `unblock_client` | `mac` (required) | Unblock a previously blocked client. |
| `disconnect_client` | `mac` (required) | Force-disconnect a currently connected client. |
| `get_sites` | — | List all sites configured on the controller. |
| `get_site_health` | — | Get health status (WAN/WLAN/LAN subsystems) for the current site. |
| `get_networks` | — | List network (VLAN) configurations for the current site. |
| `get_device_activity` | `mac` (required) | Get a device's connected clients and aggregate traffic (AP or switch). |

`UNIFI_SITE` (from your config) determines which site these operate against;
there's no per-call site override.

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

## 7. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `Authentication failed: ...` | Wrong `UNIFI_USERNAME`/`UNIFI_PASSWORD`, or the account lacks controller access. |
| `Connection failed: ...` | Wrong `UNIFI_HOST`, controller unreachable from where the server runs (check Docker networking — use `host.docker.internal` if the controller is on the host's LAN and the container can't reach it directly), or a firewall block. |
| SSL certificate errors | Set `UNIFI_VERIFY_SSL=false` for self-signed controller certificates. |
| Tools don't show up in Claude Code after `claude mcp add` | Restart the Claude Code session — newly added MCP servers aren't loaded into an already-running session. |
| Login works via browser but not here | Confirm `UNIFI_IS_UNIFI_OS` matches your controller type — UniFi OS consoles (UDM/UDM Pro/UCG Max) use a different login endpoint and URL prefix than a software controller. |

## 8. Development

See [`CLAUDE.md`](../CLAUDE.md) for the test/lint workflow (`pytest`,
`ruff check .`, `ruff format .`) and branching conventions. See
[`unifi-api.md`](./unifi-api.md) for the underlying UniFi Controller HTTP API
reference (endpoints, auth, response format, WebSocket events) that
`unifi_client.py` wraps.
