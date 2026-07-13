"""Site inventory and health tools."""

from typing import Any

from unifi_mcp.server._schema import ToolSpec
from unifi_mcp.unifi_client import UniFiClient


# Tool handlers
async def _handle_get_sites(client: UniFiClient, arguments: dict[str, Any]) -> str:
    return format_sites(await client.get_sites())


async def _handle_get_site_health(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    return format_health(await client.get_site_health())


# Formatting helpers
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


# Subsystem-specific health fields: (json field, label, default) per subsystem type.
_SUBSYSTEM_HEALTH_FIELDS: dict[str, list[tuple[str, str, Any]]] = {
    "wan": [("gw_mac", "Gateway", "N/A")],
    "wlan": [
        ("num_ap", "Access Points", 0),
        ("num_user", "Wireless Clients", 0),
    ],
    "lan": [
        ("num_sw", "Switches", 0),
        ("num_user", "Wired Clients", 0),
    ],
}


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

        for field, label, default in _SUBSYSTEM_HEALTH_FIELDS.get(subsys_name, []):
            lines.append(f"  {label}: {subsystem.get(field, default)}")

        lines.append("")

    return "\n".join(lines)


SITE_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="get_sites",
        description="Get all UniFi sites configured on the controller",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=_handle_get_sites,
    ),
    ToolSpec(
        name="get_site_health",
        description="Get health status for the current site",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=_handle_get_site_health,
    ),
]
