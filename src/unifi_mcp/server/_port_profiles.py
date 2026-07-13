"""Port profile CRUD tools."""

from typing import Any

from unifi_mcp.server._schema import ToolSpec
from unifi_mcp.unifi_client import UniFiClient

_PORT_PROFILE_ID_PROPERTY = {
    "type": "string",
    "description": "Port profile ID (`_id`), as returned by get_port_profiles",
}

_PORT_PROFILE_PROPERTY = {
    "type": "object",
    "description": (
        "Port profile fields (e.g. `name`, `poe_mode`, "
        "`native_networkconf_id`, `tagged_networkconf_ids`, `isolation`)"
    ),
}


# Tool handlers
async def _handle_get_port_profiles(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    return format_port_profiles(await client.get_port_profiles())


async def _handle_create_port_profile(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    profile = arguments.get("profile", {})
    created = await client.create_port_profile(profile)
    name = created.get("name", created.get("_id", "new port profile"))
    return f"Port profile '{name}' has been created."


async def _handle_update_port_profile(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    profile_id = arguments.get("profile_id", "")
    profile = arguments.get("profile", {})
    await client.update_port_profile(profile_id, profile)
    return f"Port profile {profile_id} has been updated."


async def _handle_delete_port_profile(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    profile_id = arguments.get("profile_id", "")
    await client.delete_port_profile(profile_id)
    return f"Port profile {profile_id} has been deleted."


# Formatting helpers
def format_port_profiles(profiles: list[dict[str, Any]]) -> str:
    """Format port profile list for display."""
    if not profiles:
        return "No port profiles configured."

    lines = [f"Found {len(profiles)} port profile(s):\n"]

    for profile in profiles:
        name = profile.get("name", "Unknown")
        lines.append(f"- {name}")

        poe_mode = profile.get("poe_mode")
        if poe_mode is not None:
            lines.append(f"  PoE mode: {poe_mode}")

        native_vlan = profile.get("native_networkconf_id")
        if native_vlan is not None:
            lines.append(f"  Native VLAN: {native_vlan}")

        lines.append("")

    return "\n".join(lines)


PORT_PROFILE_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="get_port_profiles",
        description="Get all port profiles for the current site",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=_handle_get_port_profiles,
    ),
    ToolSpec(
        name="create_port_profile",
        description="Create a new port profile",
        input_schema={
            "type": "object",
            "properties": {"profile": _PORT_PROFILE_PROPERTY},
            "required": ["profile"],
        },
        handler=_handle_create_port_profile,
    ),
    ToolSpec(
        name="update_port_profile",
        description="Update an existing port profile",
        input_schema={
            "type": "object",
            "properties": {
                "profile_id": _PORT_PROFILE_ID_PROPERTY,
                "profile": _PORT_PROFILE_PROPERTY,
            },
            "required": ["profile_id", "profile"],
        },
        handler=_handle_update_port_profile,
    ),
    ToolSpec(
        name="delete_port_profile",
        description="Delete a port profile by its port profile ID",
        input_schema={
            "type": "object",
            "properties": {"profile_id": _PORT_PROFILE_ID_PROPERTY},
            "required": ["profile_id"],
        },
        handler=_handle_delete_port_profile,
    ),
]
