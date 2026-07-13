"""MCP server implementation for UniFi.

Tool handlers, schemas, and formatters are split by domain (`_devices.py`,
`_clients.py`, `_sites.py`, `_networks.py`, `_firewall.py`); this module
assembles their `ToolSpec` lists into the tool registry and owns the shared
client lifecycle and MCP dispatch (`list_tools`, `call_tool`, `main`).
"""

import asyncio
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from unifi_mcp.server._clients import CLIENT_TOOLS, format_clients
from unifi_mcp.server._devices import (
    DEVICE_TOOLS,
    format_device_activity,
    format_devices,
)
from unifi_mcp.server._firewall import FIREWALL_TOOLS, format_firewall_rules
from unifi_mcp.server._formatting import format_bytes, format_uptime
from unifi_mcp.server._networks import NETWORK_TOOLS, format_networks
from unifi_mcp.server._schema import ToolSpec
from unifi_mcp.server._sites import SITE_TOOLS, format_health, format_sites
from unifi_mcp.unifi_client import (
    UniFiAuthenticationError,
    UniFiClient,
    UniFiConnectionError,
    UniFiError,
)

__all__ = [
    "call_tool",
    "format_bytes",
    "format_clients",
    "format_device_activity",
    "format_devices",
    "format_firewall_rules",
    "format_health",
    "format_networks",
    "format_sites",
    "format_uptime",
    "list_tools",
    "main",
]

# Create the MCP server instance
server = Server("unifi-mcp")

# A single authenticated client is reused across tool calls instead of
# logging in and out on every call; _request() re-logs-in once on a 401
# if the session has expired.
_client: UniFiClient | None = None
_client_lock = asyncio.Lock()


async def _get_client() -> UniFiClient:
    """Get the shared authenticated UniFi client, connecting it on first use."""
    global _client
    async with _client_lock:
        if _client is None:
            _client = await UniFiClient().connect()
    return _client


async def _close_client() -> None:
    """Close the shared UniFi client, if one was ever opened."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None


TOOLS: list[ToolSpec] = [
    *DEVICE_TOOLS,
    *CLIENT_TOOLS,
    *SITE_TOOLS,
    *NETWORK_TOOLS,
    *FIREWALL_TOOLS,
]

_TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available UniFi MCP tools."""
    return [
        Tool(name=t.name, description=t.description, inputSchema=t.input_schema)
        for t in TOOLS
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls.

    Args:
        name: The name of the tool to call.
        arguments: The arguments to pass to the tool.

    Returns:
        List of text content with the result.
    """
    tool = _TOOLS_BY_NAME.get(name)
    if tool is None:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    try:
        client = await _get_client()
        text = await tool.handler(client, arguments)
        return [TextContent(type="text", text=text)]
    except UniFiAuthenticationError as e:
        return [
            TextContent(
                type="text",
                text=f"Authentication failed: {e}. Check UNIFI_USERNAME and UNIFI_PASSWORD.",
            )
        ]
    except UniFiConnectionError as e:
        return [
            TextContent(
                type="text",
                text=f"Connection failed: {e}. Check UNIFI_HOST and network connectivity.",
            )
        ]
    except UniFiError as e:
        return [TextContent(type="text", text=f"Error: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Unexpected error: {e}")]


def main() -> None:
    """Run the MCP server."""

    async def run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            try:
                await server.run(
                    read_stream,
                    write_stream,
                    server.create_initialization_options(),
                )
            finally:
                await _close_client()

    asyncio.run(run())


if __name__ == "__main__":
    main()
