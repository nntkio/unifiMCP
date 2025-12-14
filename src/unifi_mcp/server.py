"""MCP server implementation for UniFi."""

import asyncio
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from unifi_mcp.unifi_client import UniFiClient, UniFiError

# Create the MCP server instance
server = Server("unifi-mcp")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available UniFi MCP tools."""
    return [
        # Device tools
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
        # Client tools
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
        # Site tools
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


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls.

    Args:
        name: The name of the tool to call.
        arguments: The arguments to pass to the tool.

    Returns:
        List of text content with the result.
    """
    try:
        async with UniFiClient() as client:
            match name:
                # Device tools
                case "get_devices":
                    devices = await client.get_devices()
                    return [TextContent(type="text", text=format_devices(devices))]

                case "restart_device":
                    mac = arguments.get("mac", "")
                    await client.restart_device(mac)
                    return [
                        TextContent(
                            type="text",
                            text=f"Restart command sent to device {mac}",
                        )
                    ]

                # Client tools
                case "get_clients":
                    include_offline = arguments.get("include_offline", False)
                    if include_offline:
                        clients = await client.get_all_clients()
                    else:
                        clients = await client.get_clients()
                    return [TextContent(type="text", text=format_clients(clients))]

                case "block_client":
                    mac = arguments.get("mac", "")
                    await client.block_client(mac)
                    return [
                        TextContent(
                            type="text",
                            text=f"Client {mac} has been blocked from the network.",
                        )
                    ]

                case "unblock_client":
                    mac = arguments.get("mac", "")
                    await client.unblock_client(mac)
                    return [
                        TextContent(
                            type="text",
                            text=f"Client {mac} has been unblocked.",
                        )
                    ]

                case "disconnect_client":
                    mac = arguments.get("mac", "")
                    await client.disconnect_client(mac)
                    return [
                        TextContent(
                            type="text",
                            text=f"Client {mac} has been disconnected.",
                        )
                    ]

                # Site tools
                case "get_sites":
                    sites = await client.get_sites()
                    return [TextContent(type="text", text=format_sites(sites))]

                case "get_site_health":
                    health = await client.get_site_health()
                    return [TextContent(type="text", text=format_health(health))]

                case "get_networks":
                    networks = await client.get_networks()
                    return [TextContent(type="text", text=format_networks(networks))]

                case _:
                    return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except UniFiError as e:
        return [TextContent(type="text", text=f"Error: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Unexpected error: {e}")]


# Formatting helpers
def format_devices(devices: list[dict[str, Any]]) -> str:
    """Format device list for display."""
    if not devices:
        return "No devices found."

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


def format_clients(clients: list[dict[str, Any]]) -> str:
    """Format client list for display."""
    if not clients:
        return "No clients found."

    lines = [f"Found {len(clients)} client(s):\n"]

    for c in clients:
        hostname = c.get("hostname") or c.get("name") or "Unknown"
        mac = c.get("mac", "Unknown")
        ip = c.get("ip", "N/A")
        is_wired = c.get("is_wired", False)
        conn_type = "Wired" if is_wired else "Wireless"
        essid = c.get("essid", "")
        tx_bytes = c.get("tx_bytes", 0)
        rx_bytes = c.get("rx_bytes", 0)

        lines.append(f"- {hostname}")
        lines.append(f"  MAC: {mac}")
        lines.append(f"  IP: {ip}")
        lines.append(f"  Connection: {conn_type}")
        if essid:
            lines.append(f"  SSID: {essid}")
        lines.append(
            f"  Traffic: TX {format_bytes(tx_bytes)} / RX {format_bytes(rx_bytes)}"
        )
        lines.append("")

    return "\n".join(lines)


def format_sites(sites: list[dict[str, Any]]) -> str:
    """Format site list for display."""
    if not sites:
        return "No sites found."

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
    """Format health data for display."""
    if not health:
        return "No health data available."

    lines = ["Site Health Status:\n"]

    for subsystem in health:
        subsys_name = subsystem.get("subsystem", "Unknown")
        status = subsystem.get("status", "unknown")

        lines.append(f"- {subsys_name.upper()}")
        lines.append(f"  Status: {status}")

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
    """Format network list for display."""
    if not networks:
        return "No networks configured."

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


def format_bytes(bytes_val: int) -> str:
    """Format bytes to human-readable format."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} PB"


def main() -> None:
    """Run the MCP server."""

    async def run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    asyncio.run(run())


if __name__ == "__main__":
    main()
