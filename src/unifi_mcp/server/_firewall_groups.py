"""Firewall group CRUD tools."""

from typing import Any

from unifi_mcp.server._schema import ToolSpec
from unifi_mcp.unifi_client import UniFiClient

_GROUP_ID_PROPERTY = {
    "type": "string",
    "description": "Firewall group ID (`_id`), as returned by get_firewall_groups",
}

_GROUP_PROPERTY = {
    "type": "object",
    "description": (
        "Firewall group fields (e.g. `name`, `group_type`, `group_members`)"
    ),
}


# Tool handlers
async def _handle_get_firewall_groups(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    return format_firewall_groups(await client.get_firewall_groups())


async def _handle_create_firewall_group(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    group = arguments.get("group", {})
    created = await client.create_firewall_group(group)
    name = created.get("name", created.get("_id", "new firewall group"))
    return f"Firewall group '{name}' has been created."


async def _handle_update_firewall_group(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    group_id = arguments.get("group_id", "")
    group = arguments.get("group", {})
    await client.update_firewall_group(group_id, group)
    return f"Firewall group {group_id} has been updated."


async def _handle_delete_firewall_group(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    group_id = arguments.get("group_id", "")
    await client.delete_firewall_group(group_id)
    return f"Firewall group {group_id} has been deleted."


# Formatting helpers
def format_firewall_groups(groups: list[dict[str, Any]]) -> str:
    """Format firewall group list for display."""
    if not groups:
        return "No firewall groups configured."

    lines = [f"Found {len(groups)} firewall group(s):\n"]

    for group in groups:
        name = group.get("name", "Unknown")
        group_type = group.get("group_type", "unknown")
        members = group.get("group_members", [])

        lines.append(f"- {name}")
        lines.append(f"  Type: {group_type}")
        lines.append(f"  Members: {len(members)}")
        lines.append("")

    return "\n".join(lines)


FIREWALL_GROUP_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="get_firewall_groups",
        description="Get all firewall groups for the current site",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=_handle_get_firewall_groups,
    ),
    ToolSpec(
        name="create_firewall_group",
        description=(
            "Create a new firewall group (e.g. an IP, port, or MAC address group)"
        ),
        input_schema={
            "type": "object",
            "properties": {"group": _GROUP_PROPERTY},
            "required": ["group"],
        },
        handler=_handle_create_firewall_group,
    ),
    ToolSpec(
        name="update_firewall_group",
        description="Update an existing firewall group",
        input_schema={
            "type": "object",
            "properties": {
                "group_id": _GROUP_ID_PROPERTY,
                "group": _GROUP_PROPERTY,
            },
            "required": ["group_id", "group"],
        },
        handler=_handle_update_firewall_group,
    ),
    ToolSpec(
        name="delete_firewall_group",
        description="Delete a firewall group by its group ID",
        input_schema={
            "type": "object",
            "properties": {"group_id": _GROUP_ID_PROPERTY},
            "required": ["group_id"],
        },
        handler=_handle_delete_firewall_group,
    ),
]
