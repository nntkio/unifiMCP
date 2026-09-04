"""MCP server implementation for UniFi.

Tool handlers, schemas, and formatters are split by domain (`_devices.py`,
`_clients.py`, `_sites.py`, `_networks.py`, `_firewall.py`); this module
assembles their `ToolSpec` lists into the tool registry and owns the shared
client lifecycle and MCP dispatch (`list_tools`, `call_tool`, `main`).
"""

import asyncio
import os
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
from unifi_mcp.server._firewall import (
    FIREWALL_TOOLS,
    format_firewall_rules,
    format_firewall_zone_matrix,
    format_firewall_zones,
)
from unifi_mcp.server._firewall_groups import (
    FIREWALL_GROUP_TOOLS,
    format_firewall_groups,
)
from unifi_mcp.server._formatting import format_bytes, format_uptime
from unifi_mcp.server._nat_rules import NAT_RULE_TOOLS, format_nat_rules
from unifi_mcp.server._networks import NETWORK_TOOLS, format_networks
from unifi_mcp.server._objects import OBJECT_TOOLS, format_objects
from unifi_mcp.server._oo_network_configs import (
    OO_NETWORK_CONFIG_TOOLS,
    format_oo_network_configs,
)
from unifi_mcp.server._port_forwarding import (
    PORT_FORWARDING_TOOLS,
    format_port_forwards,
)
from unifi_mcp.server._port_profiles import PORT_PROFILE_TOOLS, format_port_profiles
from unifi_mcp.server._qos_rules import QOS_RULE_TOOLS, format_qos_rules
from unifi_mcp.server._radius_profiles import (
    RADIUS_PROFILE_TOOLS,
    format_radius_profiles,
)
from unifi_mcp.server._schema import ToolSpec
from unifi_mcp.server._sites import (
    SITE_TOOLS,
    format_health,
    format_sdn_status,
    format_sites,
)
from unifi_mcp.server._static_routes import STATIC_ROUTE_TOOLS, format_static_routes
from unifi_mcp.server._traffic_routes import TRAFFIC_ROUTE_TOOLS, format_traffic_routes
from unifi_mcp.server._traffic_rules import TRAFFIC_RULE_TOOLS, format_traffic_rules
from unifi_mcp.server._wan_sla_profiles import (
    WAN_SLA_PROFILE_TOOLS,
    format_wan_sla_profiles,
)
from unifi_mcp.server._wlan import WLAN_TOOLS, format_wlans
from unifi_mcp.server._wlan_rate_profiles import (
    WLAN_RATE_PROFILE_TOOLS,
    format_wlan_rate_profiles,
)
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
    "format_firewall_groups",
    "format_firewall_rules",
    "format_firewall_zone_matrix",
    "format_firewall_zones",
    "format_health",
    "format_nat_rules",
    "format_networks",
    "format_objects",
    "format_oo_network_configs",
    "format_port_forwards",
    "format_port_profiles",
    "format_qos_rules",
    "format_radius_profiles",
    "format_sdn_status",
    "format_sites",
    "format_static_routes",
    "format_traffic_routes",
    "format_traffic_rules",
    "format_uptime",
    "format_wan_sla_profiles",
    "format_wlan_rate_profiles",
    "format_wlans",
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
    *FIREWALL_GROUP_TOOLS,
    *TRAFFIC_RULE_TOOLS,
    *TRAFFIC_ROUTE_TOOLS,
    *QOS_RULE_TOOLS,
    *NAT_RULE_TOOLS,
    *PORT_FORWARDING_TOOLS,
    *STATIC_ROUTE_TOOLS,
    *WLAN_TOOLS,
    *PORT_PROFILE_TOOLS,
    *RADIUS_PROFILE_TOOLS,
    *WAN_SLA_PROFILE_TOOLS,
    *WLAN_RATE_PROFILE_TOOLS,
    *OBJECT_TOOLS,
    *OO_NETWORK_CONFIG_TOOLS,
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
    """Run the MCP server using the transport selected by MCP_TRANSPORT."""
    if os.environ.get("MCP_TRANSPORT", "stdio") == "http":
        from unifi_mcp.server._http import run_http

        run_http(server, _close_client)
        return

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
