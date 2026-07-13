"""WLAN rate profile CRUD tools."""

from typing import Any

from unifi_mcp.server._schema import ToolSpec
from unifi_mcp.unifi_client import UniFiClient

_WLAN_RATE_PROFILE_ID_PROPERTY = {
    "type": "string",
    "description": (
        "WLAN rate profile ID (`_id`), as returned by get_wlan_rate_profiles"
    ),
}

_WLAN_RATE_PROFILE_PROPERTY = {
    "type": "object",
    "description": (
        "WLAN rate profile fields (e.g. `name`, and per-band minimum data "
        "rate and management frame rate settings)"
    ),
}


# Tool handlers
async def _handle_get_wlan_rate_profiles(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    return format_wlan_rate_profiles(await client.get_wlan_rate_profiles())


async def _handle_create_wlan_rate_profile(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    profile = arguments.get("profile", {})
    created = await client.create_wlan_rate_profile(profile)
    name = created.get("name", created.get("_id", "new WLAN rate profile"))
    return f"WLAN rate profile '{name}' has been created."


async def _handle_update_wlan_rate_profile(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    profile_id = arguments.get("profile_id", "")
    profile = arguments.get("profile", {})
    await client.update_wlan_rate_profile(profile_id, profile)
    return f"WLAN rate profile {profile_id} has been updated."


async def _handle_delete_wlan_rate_profile(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    profile_id = arguments.get("profile_id", "")
    await client.delete_wlan_rate_profile(profile_id)
    return f"WLAN rate profile {profile_id} has been deleted."


# Formatting helpers
def format_wlan_rate_profiles(profiles: list[dict[str, Any]]) -> str:
    """Format WLAN rate profile list for display."""
    if not profiles:
        return "No WLAN rate profiles configured."

    lines = [f"Found {len(profiles)} WLAN rate profile(s):\n"]

    for profile in profiles:
        name = profile.get("name", "Unknown")
        lines.append(f"- {name}")

    return "\n".join(lines)


WLAN_RATE_PROFILE_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="get_wlan_rate_profiles",
        description="Get all WLAN rate profiles for the current site",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=_handle_get_wlan_rate_profiles,
    ),
    ToolSpec(
        name="create_wlan_rate_profile",
        description="Create a new WLAN rate profile",
        input_schema={
            "type": "object",
            "properties": {"profile": _WLAN_RATE_PROFILE_PROPERTY},
            "required": ["profile"],
        },
        handler=_handle_create_wlan_rate_profile,
    ),
    ToolSpec(
        name="update_wlan_rate_profile",
        description="Update an existing WLAN rate profile",
        input_schema={
            "type": "object",
            "properties": {
                "profile_id": _WLAN_RATE_PROFILE_ID_PROPERTY,
                "profile": _WLAN_RATE_PROFILE_PROPERTY,
            },
            "required": ["profile_id", "profile"],
        },
        handler=_handle_update_wlan_rate_profile,
    ),
    ToolSpec(
        name="delete_wlan_rate_profile",
        description="Delete a WLAN rate profile by its profile ID",
        input_schema={
            "type": "object",
            "properties": {"profile_id": _WLAN_RATE_PROFILE_ID_PROPERTY},
            "required": ["profile_id"],
        },
        handler=_handle_delete_wlan_rate_profile,
    ),
]
