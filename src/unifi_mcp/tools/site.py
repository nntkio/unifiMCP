"""MCP tools for UniFi site management."""

from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

from unifi_mcp.unifi_client import UniFiClient, UniFiError


def register_site_tools(server: Server) -> None:
    """Register site management tools with the MCP server.

    Args:
        server: The MCP server instance.
    """

    @server.list_tools()
    async def list_site_tools() -> list[Tool]:
        """List available site tools."""
        return [
            Tool(
                name="get_sites",
                description="Get all UniFi sites configured on the controller",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            Tool(
                name="get_site_health",
                description="Get health status for the current site",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            Tool(
                name="get_networks",
                description="Get all network configurations for the current site",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
        ]


async def get_sites() -> list[TextContent]:
    """Get all sites.

    Returns:
        List of text content with site information.
    """
    try:
        async with UniFiClient() as client:
            sites = await client.get_sites()

            if not sites:
                return [TextContent(type="text", text="No sites found.")]

            result = format_sites(sites)
            return [TextContent(type="text", text=result)]
    except UniFiError as e:
        return [TextContent(type="text", text=f"Error: {e}")]


async def get_site_health() -> list[TextContent]:
    """Get site health.

    Returns:
        List of text content with health information.
    """
    try:
        async with UniFiClient() as client:
            health = await client.get_site_health()

            if not health:
                return [TextContent(type="text", text="No health data available.")]

            result = format_health(health)
            return [TextContent(type="text", text=result)]
    except UniFiError as e:
        return [TextContent(type="text", text=f"Error: {e}")]


async def get_networks() -> list[TextContent]:
    """Get network configurations.

    Returns:
        List of text content with network information.
    """
    try:
        async with UniFiClient() as client:
            networks = await client.get_networks()

            if not networks:
                return [TextContent(type="text", text="No networks configured.")]

            result = format_networks(networks)
            return [TextContent(type="text", text=result)]
    except UniFiError as e:
        return [TextContent(type="text", text=f"Error: {e}")]


def format_sites(sites: list[dict[str, Any]]) -> str:
    """Format site list for display.

    Args:
        sites: List of site dictionaries.

    Returns:
        Formatted string representation.
    """
    lines = [f"Found {len(sites)} site(s):\n"]

    for site in sites:
        name = site.get("name", "Unknown")
        desc = site.get("desc", name)
        site_id = site.get("_id", "N/A")

        lines.append(f"- {desc}")
        lines.append(f"  Name: {name}")
        lines.append(f"  ID: {site_id}")
        lines.append("")

    return "\n".join(lines)


def format_health(health: list[dict[str, Any]]) -> str:
    """Format health data for display.

    Args:
        health: List of health metric dictionaries.

    Returns:
        Formatted string representation.
    """
    lines = ["Site Health Status:\n"]

    for subsystem in health:
        subsys_name = subsystem.get("subsystem", "Unknown")
        status = subsystem.get("status", "unknown")

        lines.append(f"- {subsys_name.upper()}")
        lines.append(f"  Status: {status}")

        # Add subsystem-specific info
        if subsys_name == "wan":
            gateways = subsystem.get("gw_mac", "N/A")
            lines.append(f"  Gateway: {gateways}")
        elif subsys_name == "wlan":
            num_ap = subsystem.get("num_ap", 0)
            num_user = subsystem.get("num_user", 0)
            lines.append(f"  Access Points: {num_ap}")
            lines.append(f"  Wireless Clients: {num_user}")
        elif subsys_name == "lan":
            num_sw = subsystem.get("num_sw", 0)
            num_user = subsystem.get("num_user", 0)
            lines.append(f"  Switches: {num_sw}")
            lines.append(f"  Wired Clients: {num_user}")

        lines.append("")

    return "\n".join(lines)


def format_networks(networks: list[dict[str, Any]]) -> str:
    """Format network list for display.

    Args:
        networks: List of network configuration dictionaries.

    Returns:
        Formatted string representation.
    """
    lines = [f"Found {len(networks)} network(s):\n"]

    for net in networks:
        name = net.get("name", "Unknown")
        purpose = net.get("purpose", "unknown")
        vlan = net.get("vlan", "N/A")
        subnet = net.get("ip_subnet", "N/A")
        enabled = net.get("enabled", True)
        status = "Enabled" if enabled else "Disabled"

        lines.append(f"- {name}")
        lines.append(f"  Purpose: {purpose}")
        lines.append(f"  VLAN: {vlan}")
        lines.append(f"  Subnet: {subnet}")
        lines.append(f"  Status: {status}")
        lines.append("")

    return "\n".join(lines)
