"""Connected-client inventory and `cmd/stamgr` control tools."""

from typing import Any

from unifi_mcp.server._formatting import _format_client_lines
from unifi_mcp.server._schema import _MAC_PROPERTY, ToolSpec
from unifi_mcp.unifi_client import UniFiClient


# Tool handlers
async def _handle_get_clients(client: UniFiClient, arguments: dict[str, Any]) -> str:
    if arguments.get("include_offline", False):
        clients = await client.get_all_clients()
    else:
        clients = await client.get_clients()
    return format_clients(clients)


async def _handle_block_client(client: UniFiClient, arguments: dict[str, Any]) -> str:
    mac = arguments.get("mac", "")
    await client.block_client(mac)
    return f"Client {mac} has been blocked from the network."


async def _handle_unblock_client(client: UniFiClient, arguments: dict[str, Any]) -> str:
    mac = arguments.get("mac", "")
    await client.unblock_client(mac)
    return f"Client {mac} has been unblocked."


async def _handle_disconnect_client(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    mac = arguments.get("mac", "")
    await client.disconnect_client(mac)
    return f"Client {mac} has been disconnected."


async def _handle_forget_client(client: UniFiClient, arguments: dict[str, Any]) -> str:
    mac = arguments.get("mac", "")
    await client.forget_client(mac)
    return f"Client {mac} has been forgotten by the controller."


async def _handle_authorize_guest(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    mac = arguments.get("mac", "")
    minutes = arguments.get("minutes")
    await client.authorize_guest(mac, minutes)
    return f"Client {mac} has been authorized via the guest portal."


async def _handle_unauthorize_guest(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    mac = arguments.get("mac", "")
    await client.unauthorize_guest(mac)
    return f"Client {mac}'s guest portal authorization has been revoked."


# Formatting helpers
def format_clients(clients: list[dict[str, Any]]) -> str:
    """Format client list for display."""
    if not clients:
        return "No clients found."

    lines = [f"Found {len(clients)} client(s):\n"]
    for client in clients:
        lines.extend(_format_client_lines(client))

    return "\n".join(lines)


CLIENT_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="get_clients",
        description="Get all currently connected clients on the UniFi network",
        input_schema={
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
        handler=_handle_get_clients,
    ),
    ToolSpec(
        name="block_client",
        description="Block a client from accessing the network",
        input_schema={
            "type": "object",
            "properties": {"mac": _MAC_PROPERTY},
            "required": ["mac"],
        },
        handler=_handle_block_client,
    ),
    ToolSpec(
        name="unblock_client",
        description="Unblock a previously blocked client",
        input_schema={
            "type": "object",
            "properties": {"mac": _MAC_PROPERTY},
            "required": ["mac"],
        },
        handler=_handle_unblock_client,
    ),
    ToolSpec(
        name="disconnect_client",
        description="Force disconnect a client from the network",
        input_schema={
            "type": "object",
            "properties": {"mac": _MAC_PROPERTY},
            "required": ["mac"],
        },
        handler=_handle_disconnect_client,
    ),
    ToolSpec(
        name="forget_client",
        description="Remove a client from the controller's known-clients list",
        input_schema={
            "type": "object",
            "properties": {"mac": _MAC_PROPERTY},
            "required": ["mac"],
        },
        handler=_handle_forget_client,
    ),
    ToolSpec(
        name="authorize_guest",
        description="Authorize a client through the guest portal",
        input_schema={
            "type": "object",
            "properties": {
                "mac": _MAC_PROPERTY,
                "minutes": {
                    "type": "integer",
                    "description": "Session length in minutes before authorization expires",
                },
            },
            "required": ["mac"],
        },
        handler=_handle_authorize_guest,
    ),
    ToolSpec(
        name="unauthorize_guest",
        description="Revoke a client's guest portal authorization",
        input_schema={
            "type": "object",
            "properties": {"mac": _MAC_PROPERTY},
            "required": ["mac"],
        },
        handler=_handle_unauthorize_guest,
    ),
]
