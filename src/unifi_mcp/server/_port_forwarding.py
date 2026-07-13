"""Port forwarding rule CRUD tools."""

from typing import Any

from unifi_mcp.server._schema import ToolSpec
from unifi_mcp.unifi_client import UniFiClient

_PORT_FORWARD_ID_PROPERTY = {
    "type": "string",
    "description": ("Port forward rule ID (`_id`), as returned by get_port_forwards"),
}

_PORT_FORWARD_PROPERTY = {
    "type": "object",
    "description": (
        "Port forward rule fields (e.g. `name`, `fwd`, `fwd_port`, `dst_port`, "
        "`src`, `proto`, `enabled`)"
    ),
}


# Tool handlers
async def _handle_get_port_forwards(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    return format_port_forwards(await client.get_port_forwards())


async def _handle_create_port_forward(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    forward = arguments.get("forward", {})
    created = await client.create_port_forward(forward)
    name = created.get("name", created.get("_id", "new port forward"))
    return f"Port forward '{name}' has been created."


async def _handle_update_port_forward(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    forward_id = arguments.get("forward_id", "")
    forward = arguments.get("forward", {})
    await client.update_port_forward(forward_id, forward)
    return f"Port forward {forward_id} has been updated."


async def _handle_delete_port_forward(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    forward_id = arguments.get("forward_id", "")
    await client.delete_port_forward(forward_id)
    return f"Port forward {forward_id} has been deleted."


# Formatting helpers
def format_port_forwards(forwards: list[dict[str, Any]]) -> str:
    """Format port forwarding rule list for display."""
    if not forwards:
        return "No port forwarding rules configured."

    lines = [f"Found {len(forwards)} port forwarding rule(s):\n"]

    for fwd in forwards:
        name = fwd.get("name", "Unknown")
        dst_ip = fwd.get("fwd", "N/A")
        dst_port = fwd.get("fwd_port", "N/A")
        enabled = fwd.get("enabled", True)
        status = "Enabled" if enabled else "Disabled"

        lines.append(f"- {name}")
        lines.append(f"  Destination: {dst_ip}:{dst_port}")
        lines.append(f"  Status: {status}")
        lines.append("")

    return "\n".join(lines)


PORT_FORWARDING_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="get_port_forwards",
        description="Get all port forwarding rules for the current site",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=_handle_get_port_forwards,
    ),
    ToolSpec(
        name="create_port_forward",
        description="Create a new port forwarding rule",
        input_schema={
            "type": "object",
            "properties": {"forward": _PORT_FORWARD_PROPERTY},
            "required": ["forward"],
        },
        handler=_handle_create_port_forward,
    ),
    ToolSpec(
        name="update_port_forward",
        description="Update an existing port forwarding rule",
        input_schema={
            "type": "object",
            "properties": {
                "forward_id": _PORT_FORWARD_ID_PROPERTY,
                "forward": _PORT_FORWARD_PROPERTY,
            },
            "required": ["forward_id", "forward"],
        },
        handler=_handle_update_port_forward,
    ),
    ToolSpec(
        name="delete_port_forward",
        description="Delete a port forwarding rule by its rule ID",
        input_schema={
            "type": "object",
            "properties": {"forward_id": _PORT_FORWARD_ID_PROPERTY},
            "required": ["forward_id"],
        },
        handler=_handle_delete_port_forward,
    ),
]
