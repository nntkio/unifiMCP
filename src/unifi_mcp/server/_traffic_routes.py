"""Traffic route (policy-based routing) CRUD tools."""

from typing import Any

from unifi_mcp.server._schema import ToolSpec
from unifi_mcp.unifi_client import UniFiClient

_ROUTE_ID_PROPERTY = {
    "type": "string",
    "description": "Traffic route ID (`_id`), as returned by get_traffic_routes",
}

_TRAFFIC_ROUTE_PROPERTY = {
    "type": "object",
    "description": (
        "Traffic route fields (e.g. `description`, `enabled`, "
        "`matching_target`, `network_id`, `target_devices`)"
    ),
}


# Tool handlers
async def _handle_get_traffic_routes(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    return format_traffic_routes(await client.get_traffic_routes())


async def _handle_create_traffic_route(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    route = arguments.get("route", {})
    created = await client.create_traffic_route(route)
    name = created.get("description", created.get("_id", "new traffic route"))
    return f"Traffic route '{name}' has been created."


async def _handle_update_traffic_route(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    route_id = arguments.get("route_id", "")
    route = arguments.get("route", {})
    await client.update_traffic_route(route_id, route)
    return f"Traffic route {route_id} has been updated."


async def _handle_delete_traffic_route(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    route_id = arguments.get("route_id", "")
    await client.delete_traffic_route(route_id)
    return f"Traffic route {route_id} has been deleted."


# Formatting helpers
def format_traffic_routes(routes: list[dict[str, Any]]) -> str:
    """Format traffic route list for display."""
    if not routes:
        return "No traffic routes configured."

    lines = [f"Found {len(routes)} traffic route(s):\n"]

    for route in routes:
        name = route.get("description", "Unknown")
        enabled = route.get("enabled", True)
        status = "Enabled" if enabled else "Disabled"

        lines.append(f"- {name}")
        lines.append(f"  Status: {status}")
        lines.append("")

    return "\n".join(lines)


TRAFFIC_ROUTE_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="get_traffic_routes",
        description="Get all traffic routes (policy-based routing) for the current site",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=_handle_get_traffic_routes,
    ),
    ToolSpec(
        name="create_traffic_route",
        description=(
            "Create a new traffic route (e.g. to route specific traffic over "
            "a VPN or secondary WAN)"
        ),
        input_schema={
            "type": "object",
            "properties": {"route": _TRAFFIC_ROUTE_PROPERTY},
            "required": ["route"],
        },
        handler=_handle_create_traffic_route,
    ),
    ToolSpec(
        name="update_traffic_route",
        description="Update an existing traffic route",
        input_schema={
            "type": "object",
            "properties": {
                "route_id": _ROUTE_ID_PROPERTY,
                "route": _TRAFFIC_ROUTE_PROPERTY,
            },
            "required": ["route_id", "route"],
        },
        handler=_handle_update_traffic_route,
    ),
    ToolSpec(
        name="delete_traffic_route",
        description="Delete a traffic route by its route ID",
        input_schema={
            "type": "object",
            "properties": {"route_id": _ROUTE_ID_PROPERTY},
            "required": ["route_id"],
        },
        handler=_handle_delete_traffic_route,
    ),
]
