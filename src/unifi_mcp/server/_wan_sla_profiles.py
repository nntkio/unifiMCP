"""WAN SLA profile CRUD tools."""

from typing import Any

from unifi_mcp.server._schema import ToolSpec
from unifi_mcp.unifi_client import UniFiClient

_WAN_SLA_PROFILE_ID_PROPERTY = {
    "type": "string",
    "description": ("WAN SLA profile ID (`_id`), as returned by get_wan_sla_profiles"),
}

_WAN_SLA_PROFILE_PROPERTY = {
    "type": "object",
    "description": (
        "WAN SLA profile fields (e.g. `name`, `type`, `wan_networks_group`)"
    ),
}


# Tool handlers
async def _handle_get_wan_sla_profiles(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    return format_wan_sla_profiles(await client.get_wan_sla_profiles())


async def _handle_create_wan_sla_profile(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    profile = arguments.get("profile", {})
    created = await client.create_wan_sla_profile(profile)
    name = created.get("name", created.get("_id", "new WAN SLA profile"))
    return f"WAN SLA profile '{name}' has been created."


async def _handle_update_wan_sla_profile(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    profile_id = arguments.get("profile_id", "")
    profile = arguments.get("profile", {})
    await client.update_wan_sla_profile(profile_id, profile)
    return f"WAN SLA profile {profile_id} has been updated."


async def _handle_delete_wan_sla_profile(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    profile_id = arguments.get("profile_id", "")
    await client.delete_wan_sla_profile(profile_id)
    return f"WAN SLA profile {profile_id} has been deleted."


# Formatting helpers
def format_wan_sla_profiles(profiles: list[dict[str, Any]]) -> str:
    """Format WAN SLA profile list for display."""
    if not profiles:
        return "No WAN SLA profiles configured."

    lines = [f"Found {len(profiles)} WAN SLA profile(s):\n"]

    for profile in profiles:
        name = profile.get("name", "Unknown")
        lines.append(f"- {name}")

    return "\n".join(lines)


WAN_SLA_PROFILE_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="get_wan_sla_profiles",
        description="Get all WAN SLA profiles for the current site",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=_handle_get_wan_sla_profiles,
    ),
    ToolSpec(
        name="create_wan_sla_profile",
        description="Create a new WAN SLA profile",
        input_schema={
            "type": "object",
            "properties": {"profile": _WAN_SLA_PROFILE_PROPERTY},
            "required": ["profile"],
        },
        handler=_handle_create_wan_sla_profile,
    ),
    ToolSpec(
        name="update_wan_sla_profile",
        description="Update an existing WAN SLA profile",
        input_schema={
            "type": "object",
            "properties": {
                "profile_id": _WAN_SLA_PROFILE_ID_PROPERTY,
                "profile": _WAN_SLA_PROFILE_PROPERTY,
            },
            "required": ["profile_id", "profile"],
        },
        handler=_handle_update_wan_sla_profile,
    ),
    ToolSpec(
        name="delete_wan_sla_profile",
        description="Delete a WAN SLA profile by its profile ID",
        input_schema={
            "type": "object",
            "properties": {"profile_id": _WAN_SLA_PROFILE_ID_PROPERTY},
            "required": ["profile_id"],
        },
        handler=_handle_delete_wan_sla_profile,
    ),
]
