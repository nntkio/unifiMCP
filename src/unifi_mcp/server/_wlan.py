"""WLAN (Wi-Fi network) configuration CRUD tools."""

from typing import Any

from unifi_mcp.server._schema import ToolSpec
from unifi_mcp.unifi_client import UniFiClient

_WLAN_ID_PROPERTY = {
    "type": "string",
    "description": "WLAN configuration ID (`_id`), as returned by get_wlans",
}

_WLAN_PROPERTY = {
    "type": "object",
    "description": (
        "WLAN configuration fields (e.g. `name` (the SSID), `security`, "
        "`x_passphrase` (the WPA passphrase), `vlan`, `is_guest`, `enabled`)"
    ),
}


# Tool handlers
async def _handle_get_wlans(client: UniFiClient, arguments: dict[str, Any]) -> str:
    return format_wlans(await client.get_wlans())


async def _handle_create_wlan(client: UniFiClient, arguments: dict[str, Any]) -> str:
    wlan = arguments.get("wlan", {})
    created = await client.create_wlan(wlan)
    name = created.get("name", created.get("_id", "new WLAN"))
    return f"WLAN '{name}' has been created."


async def _handle_update_wlan(client: UniFiClient, arguments: dict[str, Any]) -> str:
    wlan_id = arguments.get("wlan_id", "")
    wlan = arguments.get("wlan", {})
    await client.update_wlan(wlan_id, wlan)
    return f"WLAN {wlan_id} has been updated."


async def _handle_delete_wlan(client: UniFiClient, arguments: dict[str, Any]) -> str:
    wlan_id = arguments.get("wlan_id", "")
    await client.delete_wlan(wlan_id)
    return f"WLAN {wlan_id} has been deleted."


# Formatting helpers
def format_wlans(wlans: list[dict[str, Any]]) -> str:
    """Format WLAN list for display.

    The WPA passphrase (`x_passphrase`) is deliberately never included in
    the output, even if present in the input dictionaries.
    """
    if not wlans:
        return "No WLANs configured."

    lines = [f"Found {len(wlans)} WLAN(s):\n"]

    for wlan in wlans:
        name = wlan.get("name", "Unknown")
        enabled = wlan.get("enabled", True)
        status = "Enabled" if enabled else "Disabled"

        lines.append(f"- {name}")
        lines.append(f"  Status: {status}")
        lines.append("")

    return "\n".join(lines)


WLAN_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="get_wlans",
        description="Get all WLAN (Wi-Fi network) configurations for the current site",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=_handle_get_wlans,
    ),
    ToolSpec(
        name="create_wlan",
        description="Create a new WLAN (Wi-Fi network) configuration",
        input_schema={
            "type": "object",
            "properties": {"wlan": _WLAN_PROPERTY},
            "required": ["wlan"],
        },
        handler=_handle_create_wlan,
    ),
    ToolSpec(
        name="update_wlan",
        description="Update an existing WLAN (Wi-Fi network) configuration",
        input_schema={
            "type": "object",
            "properties": {
                "wlan_id": _WLAN_ID_PROPERTY,
                "wlan": _WLAN_PROPERTY,
            },
            "required": ["wlan_id", "wlan"],
        },
        handler=_handle_update_wlan,
    ),
    ToolSpec(
        name="delete_wlan",
        description="Delete a WLAN (Wi-Fi network) configuration by its WLAN ID",
        input_schema={
            "type": "object",
            "properties": {"wlan_id": _WLAN_ID_PROPERTY},
            "required": ["wlan_id"],
        },
        handler=_handle_delete_wlan,
    ),
]
