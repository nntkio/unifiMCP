"""MCP tools for UniFi client management."""

from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

from unifi_mcp.unifi_client import UniFiClient, UniFiError


def register_client_tools(server: Server) -> None:
    """Register client management tools with the MCP server.

    Args:
        server: The MCP server instance.
    """

    @server.list_tools()
    async def list_client_tools() -> list[Tool]:
        """List available client tools."""
        return [
            Tool(
                name="get_clients",
                description="Get all currently connected clients on the UniFi network",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "include_offline": {
                            "type": "boolean",
                            "description": "Include offline/historical clients",
                            "default": False,
                        }
                    },
                    "required": [],
                },
            ),
            Tool(
                name="block_client",
                description="Block a client from accessing the network",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "mac": {
                            "type": "string",
                            "description": "MAC address of the client to block",
                        }
                    },
                    "required": ["mac"],
                },
            ),
            Tool(
                name="unblock_client",
                description="Unblock a previously blocked client",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "mac": {
                            "type": "string",
                            "description": "MAC address of the client to unblock",
                        }
                    },
                    "required": ["mac"],
                },
            ),
            Tool(
                name="disconnect_client",
                description="Force disconnect a client from the network",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "mac": {
                            "type": "string",
                            "description": "MAC address of the client to disconnect",
                        }
                    },
                    "required": ["mac"],
                },
            ),
        ]


async def get_clients(include_offline: bool = False) -> list[TextContent]:
    """Get connected clients.

    Args:
        include_offline: Whether to include offline clients.

    Returns:
        List of text content with client information.
    """
    try:
        async with UniFiClient() as client:
            if include_offline:
                clients = await client.get_all_clients()
            else:
                clients = await client.get_clients()

            if not clients:
                return [TextContent(type="text", text="No clients found.")]

            result = format_clients(clients)
            return [TextContent(type="text", text=result)]
    except UniFiError as e:
        return [TextContent(type="text", text=f"Error: {e}")]


async def block_client(mac: str) -> list[TextContent]:
    """Block a client from the network.

    Args:
        mac: MAC address of the client.

    Returns:
        List of text content with result.
    """
    try:
        async with UniFiClient() as client:
            await client.block_client(mac)
            return [
                TextContent(
                    type="text",
                    text=f"Client {mac} has been blocked from the network.",
                )
            ]
    except UniFiError as e:
        return [TextContent(type="text", text=f"Error: {e}")]


async def unblock_client(mac: str) -> list[TextContent]:
    """Unblock a client.

    Args:
        mac: MAC address of the client.

    Returns:
        List of text content with result.
    """
    try:
        async with UniFiClient() as client:
            await client.unblock_client(mac)
            return [
                TextContent(
                    type="text",
                    text=f"Client {mac} has been unblocked.",
                )
            ]
    except UniFiError as e:
        return [TextContent(type="text", text=f"Error: {e}")]


async def disconnect_client(mac: str) -> list[TextContent]:
    """Disconnect a client.

    Args:
        mac: MAC address of the client.

    Returns:
        List of text content with result.
    """
    try:
        async with UniFiClient() as client:
            await client.disconnect_client(mac)
            return [
                TextContent(
                    type="text",
                    text=f"Client {mac} has been disconnected.",
                )
            ]
    except UniFiError as e:
        return [TextContent(type="text", text=f"Error: {e}")]


def format_clients(clients: list[dict[str, Any]]) -> str:
    """Format client list for display.

    Args:
        clients: List of client dictionaries.

    Returns:
        Formatted string representation.
    """
    lines = [f"Found {len(clients)} client(s):\n"]

    for c in clients:
        hostname = c.get("hostname") or c.get("name") or "Unknown"
        mac = c.get("mac", "Unknown")
        ip = c.get("ip", "N/A")
        is_wired = c.get("is_wired", False)
        conn_type = "Wired" if is_wired else "Wireless"

        # Network info
        network = c.get("network", "N/A")
        essid = c.get("essid", "")

        # Traffic stats
        tx_bytes = c.get("tx_bytes", 0)
        rx_bytes = c.get("rx_bytes", 0)

        lines.append(f"- {hostname}")
        lines.append(f"  MAC: {mac}")
        lines.append(f"  IP: {ip}")
        lines.append(f"  Connection: {conn_type}")
        if essid:
            lines.append(f"  SSID: {essid}")
        if network != "N/A":
            lines.append(f"  Network: {network}")
        lines.append(
            f"  Traffic: TX {format_bytes(tx_bytes)} / RX {format_bytes(rx_bytes)}"
        )
        lines.append("")

    return "\n".join(lines)


def format_bytes(bytes_val: int) -> str:
    """Format bytes to human-readable format.

    Args:
        bytes_val: Number of bytes.

    Returns:
        Human-readable string.
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} PB"
