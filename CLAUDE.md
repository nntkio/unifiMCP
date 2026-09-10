# UnifiMCP

This is an MCP (Model Context Protocol) server for Ubiquiti UniFi network devices.

## Project Overview

UnifiMCP provides an interface for AI assistants to interact with UniFi network infrastructure, allowing for network monitoring, device management, and configuration tasks.

## Tech Stack

- **Language**: Python 3.13+
- **MCP Framework**: mcp (Python SDK)
- **Package Manager**: uv (recommended) or pip

## Development Setup

```bash
# Create virtual environment
uv venv

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
uv pip install -e ".[dev]"
```

## Project Structure

```
src/
  unifi_mcp/
    __init__.py         # Package initialization
    tokens.py           # Shared SQLite store: accounts, bearer tokens, usage log
    admin/               # Token-admin web service (Starlette + Jinja2)
      __init__.py         # Console-script entry point (unifi-mcp-admin)
      app.py              # Routes: login, accounts (+ delete user), tokens, usage log
      auth.py             # Root-credential check + CSRF helpers
      templates/          # base.html shell + login/admin/tokens/usage pages
      static/             # admin.css, admin.js, favicon, self-hosted fonts
    server/              # MCP server, split by domain
      __init__.py         # Tool registry, dispatch (list_tools/call_tool), client lifecycle, main
      _http.py             # Streamable HTTP transport: bearer auth + usage-log middleware
      _schema.py           # ToolSpec dataclass + shared property schema constants
      _formatting.py        # Formatting helpers shared across domains (bytes, uptime, client lines)
      _devices.py            # Device tool handlers/formatters + cmd/devmgr commands
      _clients.py             # Client tool handlers/formatters + cmd/stamgr commands
      _sites.py                 # Site tool handlers/formatters + SDN status
      _networks.py               # Network config CRUD tool handlers/formatters
      _firewall.py                # Legacy firewall rules + zone-based policies/zones/zone matrix
      _<domain>.py                # One file per additional domain (see below), same shape
    unifi_client/        # UniFi API client, split by domain
      __init__.py         # Re-exports UniFiClient and exception types
      _base.py             # Connection lifecycle, auth, request plumbing
      client.py             # UniFiClient (composes the mixins below)
      _devices.py            # Device inventory + cmd/devmgr commands
      _clients.py             # Connected-client inventory + cmd/stamgr commands
      _sites.py                # Site inventory, health, and SDN status
      _networks.py              # Network configuration CRUD
      _firewall.py               # Legacy firewall rules + zone-based policies/zones/zone matrix
      _<domain>.py                # One file per additional domain (see below), same shape
    resources/           # MCP resources definitions
tests/
  test_tokens_store.py        # TokenStore: accounts, tokens, usage log
  test_admin_app.py           # Token-admin routes and rendered pages
  test_server_http.py         # HTTP transport: auth + usage-log middleware
  test_server_registry.py     # list_tools/call_tool dispatch + client lifecycle
  test_server_formatting.py   # Shared formatting helpers
  test_server_<domain>.py     # Server tests, split by the same domains as server/
  test_client_<domain>.py     # Client tests, split by the same domains as unifi_client/
docs/
  *.md               # Documentation files
```

Additional domains beyond the original 5 (each following the same
`unifi_client/_<domain>.py` + `server/_<domain>.py` + matching test-file
pattern): firewall groups, legacy traffic rules, traffic routes, QoS rules,
NAT rules, port forwarding, static routes, WLANs, port profiles, RADIUS
profiles, WAN SLA profiles, WLAN rate profiles, network objects, and
object-oriented network configs.

Adding a new UniFi API domain (e.g. a new REST resource)? Add a `_<domain>.py`
mixin under `unifi_client/`, mix it into `UniFiClient` in `unifi_client/client.py`,
add a matching `server/_<domain>.py` (handlers + formatters + a `<DOMAIN>_TOOLS`
list of `ToolSpec`s) wired into `TOOLS` in `server/__init__.py`, and add matching
`tests/test_client_<domain>.py` / `tests/test_server_<domain>.py` files.

## Code Style

- Follow PEP 8 guidelines
- Use type hints for all function signatures
- Use `ruff` for linting and formatting
- Run `ruff check .` and `ruff format .` before committing

## Testing

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=src
```

## Environment Variables

The following environment variables are used:

- `UNIFI_HOST`: UniFi Controller host URL
- `UNIFI_USERNAME`: UniFi Controller username
- `UNIFI_PASSWORD`: UniFi Controller password
- `UNIFI_SITE`: UniFi site name (default: "default")
- `UNIFI_VERIFY_SSL`: Whether to verify SSL certificates (default: "true")

## Branching Strategy

- `fix/` - Use for bug fixes (e.g., `fix/login-error`, `fix/api-timeout`)
- `feature/` - Use for new features (e.g., `feature/device-list`, `feature/client-stats`)

## Git Commit Guidelines

- Before any commit, run all tests (`pytest`) and fix any failures
- Changes to `.md` files can be committed directly to the current branch
- For any other file changes, please ask the user before committing
- All new markdown files should be added to the `docs/` directory
