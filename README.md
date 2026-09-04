# UniFi MCP Server

An MCP (Model Context Protocol) server for Ubiquiti UniFi network devices. This allows AI assistants to interact with UniFi network infrastructure for monitoring, device management, and configuration tasks.

> For the full configuration and usage guide — including how to connect this
> to Claude Code and Claude Desktop, a complete tool reference, and
> troubleshooting — see [`docs/usage-guide.md`](docs/usage-guide.md).

## Installation

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/nntkio/unifiMCP.git
cd unifiMCP

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your UniFi controller details

# Build and run with Docker Compose
docker compose up -d
```

Credentials are only ever supplied at container **run time** (via `.env`,
loaded through `env_file` in `docker-compose.yml`) — they are never passed as
build arguments or baked into the image, so the image is safe to share or
push to a registry without leaking your controller password.

### Option 2: Local Installation

```bash
# Clone the repository
git clone https://github.com/nntkio/unifiMCP.git
cd unifiMCP

# Create virtual environment
uv venv

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
uv pip install -e ".[dev]"
```

## Configuration

### Environment Variables

Configure the following environment variables before running the server:

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `UNIFI_HOST` | UniFi Controller URL (e.g., `https://192.168.1.1`) | - | Yes |
| `UNIFI_USERNAME` | UniFi Controller username | - | Yes |
| `UNIFI_PASSWORD` | UniFi Controller password | - | Yes |
| `UNIFI_SITE` | UniFi site name | `default` | No |
| `UNIFI_VERIFY_SSL` | Verify SSL certificates (`true`/`false`) | `true` | No |
| `UNIFI_IS_UNIFI_OS` | Using UniFi OS device like UDM/UDM Pro (`true`/`false`) | `false` | No |

### Example Configuration

```bash
# Standard Controller (port 8443)
export UNIFI_HOST="https://192.168.1.1:8443"
export UNIFI_USERNAME="admin"
export UNIFI_PASSWORD="your-password"
export UNIFI_SITE="default"
export UNIFI_VERIFY_SSL="false"
export UNIFI_IS_UNIFI_OS="false"

# UniFi OS Device (UDM/UDM Pro - port 443)
export UNIFI_HOST="https://192.168.1.1"
export UNIFI_USERNAME="admin"
export UNIFI_PASSWORD="your-password"
export UNIFI_SITE="default"
export UNIFI_VERIFY_SSL="false"
export UNIFI_IS_UNIFI_OS="true"
```

## Usage

### Running the Server

**With Docker:**
```bash
# Using Docker Compose (recommended)
docker compose up -d

# Or run directly with Docker
docker run -it --rm \
  -e UNIFI_HOST="https://192.168.1.1" \
  -e UNIFI_USERNAME="admin" \
  -e UNIFI_PASSWORD="your-password" \
  -e UNIFI_VERIFY_SSL="false" \
  -e UNIFI_IS_UNIFI_OS="true" \
  unifi-mcp:latest
```

**Without Docker:**
```bash
unifi-mcp
```

### Claude Desktop Configuration

Add to your Claude Desktop config file (`~/.config/claude/claude_desktop_config.json` on Linux or `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

**Local installation:**
```json
{
  "mcpServers": {
    "unifi": {
      "command": "/path/to/unifiMCP/.venv/bin/unifi-mcp",
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

**With Docker:**
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

## Available Tools

| Tool | Description |
|------|-------------|
| `get_devices` | List all network devices (APs, switches, gateways) |
| `restart_device` | Restart a device by MAC address |
| `get_clients` | List connected clients |
| `block_client` | Block a client from the network |
| `unblock_client` | Unblock a previously blocked client |
| `disconnect_client` | Force disconnect a client |
| `get_sites` | List all configured sites |
| `get_site_health` | Get health status for the current site |
| `get_networks` | List network configurations |
| `get_device_activity` | Get activity for a specific device (connected clients, traffic) |

## Running as a Network Service (HTTP Transport)

By default the server speaks MCP over stdio (a local subprocess). It can
also run as a persistent Streamable HTTP service — e.g. for a Docker/QNAP
deployment reachable over the LAN — by setting `MCP_TRANSPORT=http`.

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_TRANSPORT` | `stdio` or `http` | `stdio` |
| `MCP_HTTP_HOST` | Bind host (HTTP mode only) | `0.0.0.0` |
| `MCP_HTTP_PORT` | Bind port (HTTP mode only) | `8765` |
| `TOKEN_DB_PATH` | Path to the shared SQLite token database (HTTP mode only) | `/data/tokens.db` |

In HTTP mode, the server exposes:
- `POST/GET /mcp` — the MCP Streamable HTTP endpoint, requires
  `Authorization: Bearer <token>`
- `GET /healthz` — unauthenticated health check, used by Docker's healthcheck

Tokens aren't configured directly — they're created through the separate
**token-admin service** (`unifi-mcp-admin`, included in `docker-compose.yml`).
See its section below for how to log in and mint a token.

An MCP client pointed at a remote Streamable HTTP server (instead of
spawning a local subprocess) typically needs a URL and a bearer token,
e.g.:

```json
{
  "mcpServers": {
    "unifi": {
      "url": "http://172.16.25.50:8765/mcp",
      "headers": {
        "Authorization": "Bearer <token from the token-admin service>"
      }
    }
  }
}
```

(Check your specific MCP client's documentation for its exact remote-server
config format — the shape above is illustrative.)

## Token Admin Service

`unifi-mcp-admin` is a small web UI for creating and revoking the bearer
tokens the HTTP transport above requires. It shares a SQLite database
(`TOKEN_DB_PATH`) with the `unifi-mcp` service via a Docker volume.

| Variable | Description | Default |
|----------|-------------|---------|
| `ROOT_ADMIN_USERNAME` | Root admin login username | `root` |
| `ROOT_ADMIN_PASSWORD` | Root admin login password (required) | - |
| `ADMIN_SESSION_SECRET` | Signs session cookies (required) | - |
| `ADMIN_HTTP_HOST` | Bind host | `0.0.0.0` |
| `ADMIN_HTTP_PORT` | Bind port | `8766` |

Root has no account of its own to hold a token — it exists only to create
accounts for trusted people at `http://<host>:8766/admin`. Each person then
logs in at `http://<host>:8766/login` to create, view, and revoke their own
tokens at `/tokens`. A newly created token is shown exactly once — copy it
immediately, since only its hash is stored.

```bash
docker compose up -d
# then, in a browser:
#   http://<host>:8766/login   (log in as root, create an account)
#   http://<host>:8766/login   (log in as that account, create a token)
```

## Development

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=src

# Lint and format
ruff check .
ruff format .
```

## License

MIT
