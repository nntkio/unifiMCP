# UnifiMCP

This is an MCP (Model Context Protocol) server for Ubiquiti UniFi network devices.

## Project Overview

UnifiMCP provides an interface for AI assistants to interact with UniFi network infrastructure, allowing for network monitoring, device management, and configuration tasks.

## Tech Stack

- **Language**: Python 3.10+ (please use the latest stable version of Python)
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
    __init__.py      # Package initialization
    server.py        # MCP server implementation
    unifi_client.py  # UniFi API client
    tools/           # MCP tools definitions
    resources/       # MCP resources definitions
tests/
  test_*.py          # Test files
```

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

## Git Commit Guidelines

- Changes to `.md` files can be committed directly to the current branch
- For any other file changes, please ask the user before committing
