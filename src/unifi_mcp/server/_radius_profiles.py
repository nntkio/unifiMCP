"""RADIUS profile CRUD tools."""

from typing import Any

from unifi_mcp.server._schema import ToolSpec
from unifi_mcp.unifi_client import UniFiClient

_RADIUS_PROFILE_ID_PROPERTY = {
    "type": "string",
    "description": "RADIUS profile ID (`_id`), as returned by get_radius_profiles",
}

_RADIUS_PROFILE_PROPERTY = {
    "type": "object",
    "description": (
        "RADIUS profile fields (e.g. `name`, `x_auth_server`, `x_auth_port`, "
        "`x_secret` (the RADIUS shared secret), `x_acct_server`, "
        "`x_acct_port`)"
    ),
}


# Tool handlers
async def _handle_get_radius_profiles(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    return format_radius_profiles(await client.get_radius_profiles())


async def _handle_create_radius_profile(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    profile = arguments.get("profile", {})
    created = await client.create_radius_profile(profile)
    name = created.get("name", created.get("_id", "new RADIUS profile"))
    return f"RADIUS profile '{name}' has been created."


async def _handle_update_radius_profile(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    profile_id = arguments.get("profile_id", "")
    profile = arguments.get("profile", {})
    await client.update_radius_profile(profile_id, profile)
    return f"RADIUS profile {profile_id} has been updated."


async def _handle_delete_radius_profile(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    profile_id = arguments.get("profile_id", "")
    await client.delete_radius_profile(profile_id)
    return f"RADIUS profile {profile_id} has been deleted."


# Formatting helpers
def format_radius_profiles(profiles: list[dict[str, Any]]) -> str:
    """Format RADIUS profile list for display.

    Only the profile name is shown; secret fields (e.g. `x_secret`) are
    intentionally omitted so they are never echoed back in tool output.
    """
    if not profiles:
        return "No RADIUS profiles configured."

    lines = [f"Found {len(profiles)} RADIUS profile(s):\n"]

    for profile in profiles:
        name = profile.get("name", "Unknown")
        lines.append(f"- {name}")

    return "\n".join(lines)


RADIUS_PROFILE_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="get_radius_profiles",
        description="Get all RADIUS profiles for the current site",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=_handle_get_radius_profiles,
    ),
    ToolSpec(
        name="create_radius_profile",
        description="Create a new RADIUS profile",
        input_schema={
            "type": "object",
            "properties": {"profile": _RADIUS_PROFILE_PROPERTY},
            "required": ["profile"],
        },
        handler=_handle_create_radius_profile,
    ),
    ToolSpec(
        name="update_radius_profile",
        description="Update an existing RADIUS profile",
        input_schema={
            "type": "object",
            "properties": {
                "profile_id": _RADIUS_PROFILE_ID_PROPERTY,
                "profile": _RADIUS_PROFILE_PROPERTY,
            },
            "required": ["profile_id", "profile"],
        },
        handler=_handle_update_radius_profile,
    ),
    ToolSpec(
        name="delete_radius_profile",
        description="Delete a RADIUS profile by its profile ID",
        input_schema={
            "type": "object",
            "properties": {"profile_id": _RADIUS_PROFILE_ID_PROPERTY},
            "required": ["profile_id"],
        },
        handler=_handle_delete_radius_profile,
    ),
]
