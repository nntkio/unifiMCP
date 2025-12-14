# UniFi MCP Server

An MCP (Model Context Protocol) server for Ubiquiti UniFi network devices. This allows AI assistants to interact with UniFi network infrastructure for monitoring, device management, and configuration tasks.

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
