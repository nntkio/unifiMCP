"""MCP tools for UniFi device management."""

from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

from unifi_mcp.unifi_client import UniFiClient, UniFiError


def register_device_tools(server: Server) -> None:
    """Register device management tools with the MCP server.

    Args:
        server: The MCP server instance.
    """

    @server.list_tools()
    async def list_device_tools() -> list[Tool]:
        """List available device tools."""
        return [
            Tool(
                name="get_devices",
                description="Get all UniFi network devices (access points, switches, gateways)",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            Tool(
                name="restart_device",
                description="Restart a UniFi network device by its MAC address",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "mac": {
                            "type": "string",
                            "description": "MAC address of the device to restart (e.g., '00:11:22:33:44:55')",
                        }
                    },
                    "required": ["mac"],
                },
            ),
        ]


async def get_devices() -> list[TextContent]:
    """Get all UniFi network devices.

    Returns:
        List of text content with device information.
    """
    try:
        async with UniFiClient() as client:
            devices = await client.get_devices()

            if not devices:
                return [TextContent(type="text", text="No devices found.")]

            # Format device information
            result = format_devices(devices)
            return [TextContent(type="text", text=result)]
    except UniFiError as e:
        return [TextContent(type="text", text=f"Error: {e}")]


async def restart_device(mac: str) -> list[TextContent]:
    """Restart a UniFi network device.

    Args:
        mac: MAC address of the device.

    Returns:
        List of text content with result.
    """
    try:
        async with UniFiClient() as client:
            await client.restart_device(mac)
            return [
                TextContent(
                    type="text",
                    text=f"Restart command sent to device {mac}",
                )
            ]
    except UniFiError as e:
        return [TextContent(type="text", text=f"Error: {e}")]


def format_devices(devices: list[dict[str, Any]]) -> str:
    """Format device list for display.

    Args:
        devices: List of device dictionaries.

    Returns:
        Formatted string representation.
    """
    lines = [f"Found {len(devices)} device(s):\n"]

    for device in devices:
        name = device.get("name", "Unknown")
        mac = device.get("mac", "Unknown")
        model = device.get("model", "Unknown")
        device_type = device.get("type", "Unknown")
        state = device.get("state", 0)
        state_str = "Online" if state == 1 else "Offline"
        ip = device.get("ip", "N/A")
        version = device.get("version", "N/A")

        lines.append(f"- {name}")
        lines.append(f"  MAC: {mac}")
        lines.append(f"  Model: {model} ({device_type})")
        lines.append(f"  Status: {state_str}")
        lines.append(f"  IP: {ip}")
        lines.append(f"  Firmware: {version}")
        lines.append("")

    return "\n".join(lines)
