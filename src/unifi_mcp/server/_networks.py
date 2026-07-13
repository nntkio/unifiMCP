"""Network configuration CRUD tools."""

from typing import Any

from unifi_mcp.server._schema import ToolSpec
from unifi_mcp.unifi_client import UniFiClient

_NETWORK_ID_PROPERTY = {
    "type": "string",
    "description": "Network configuration ID (`_id`), as returned by get_networks",
}

_NETWORK_PROPERTY = {
    "type": "object",
    "description": (
        "Network configuration fields (e.g. `name`, `purpose`, `vlan`, "
        "`ip_subnet`, `enabled`)"
    ),
}


# Tool handlers
async def _handle_get_networks(client: UniFiClient, arguments: dict[str, Any]) -> str:
    return format_networks(await client.get_networks())


async def _handle_create_network(client: UniFiClient, arguments: dict[str, Any]) -> str:
    network = arguments.get("network", {})
    created = await client.create_network(network)
    name = created.get("name", created.get("_id", "new network"))
    return f"Network '{name}' has been created."


async def _handle_update_network(client: UniFiClient, arguments: dict[str, Any]) -> str:
    network_id = arguments.get("network_id", "")
    network = arguments.get("network", {})
    await client.update_network(network_id, network)
    return f"Network {network_id} has been updated."


async def _handle_delete_network(client: UniFiClient, arguments: dict[str, Any]) -> str:
    network_id = arguments.get("network_id", "")
    await client.delete_network(network_id)
    return f"Network {network_id} has been deleted."


# Formatting helpers
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


NETWORK_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="get_networks",
        description="Get all network configurations for the current site",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=_handle_get_networks,
    ),
    ToolSpec(
        name="create_network",
        description="Create a new network configuration (e.g. a VLAN)",
        input_schema={
            "type": "object",
            "properties": {"network": _NETWORK_PROPERTY},
            "required": ["network"],
        },
        handler=_handle_create_network,
    ),
    ToolSpec(
        name="update_network",
        description="Update an existing network configuration",
        input_schema={
            "type": "object",
            "properties": {
                "network_id": _NETWORK_ID_PROPERTY,
                "network": _NETWORK_PROPERTY,
            },
            "required": ["network_id", "network"],
        },
        handler=_handle_update_network,
    ),
    ToolSpec(
        name="delete_network",
        description="Delete a network configuration by its network ID",
        input_schema={
            "type": "object",
            "properties": {"network_id": _NETWORK_ID_PROPERTY},
            "required": ["network_id"],
        },
        handler=_handle_delete_network,
    ),
]
