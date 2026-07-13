"""Static route CRUD tools."""

from typing import Any

from unifi_mcp.server._schema import ToolSpec
from unifi_mcp.unifi_client import UniFiClient

_STATIC_ROUTE_ID_PROPERTY = {
    "type": "string",
    "description": "Static route ID (`_id`), as returned by get_static_routes",
}

_STATIC_ROUTE_PROPERTY = {
    "type": "object",
    "description": (
        "Static route fields (e.g. `name`, `static-route_network`, "
        "`static-route_nexthop`, `static-route_type`, `enabled`)"
    ),
}


# Tool handlers
async def _handle_get_static_routes(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    return format_static_routes(await client.get_static_routes())


async def _handle_create_static_route(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    route = arguments.get("route", {})
    created = await client.create_static_route(route)
    name = created.get("name", created.get("_id", "new static route"))
    return f"Static route '{name}' has been created."


async def _handle_update_static_route(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    route_id = arguments.get("route_id", "")
    route = arguments.get("route", {})
    await client.update_static_route(route_id, route)
    return f"Static route {route_id} has been updated."


async def _handle_delete_static_route(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    route_id = arguments.get("route_id", "")
    await client.delete_static_route(route_id)
    return f"Static route {route_id} has been deleted."


# Formatting helpers
def format_static_routes(routes: list[dict[str, Any]]) -> str:
    """Format static route list for display."""
    if not routes:
        return "No static routes configured."

    lines = [f"Found {len(routes)} static route(s):\n"]

    for route in routes:
        name = route.get("name", "Unknown")
        subnet = route.get("static-route_network", "N/A")
        gateway = route.get("static-route_nexthop", "N/A")
        enabled = route.get("enabled", True)
        status = "Enabled" if enabled else "Disabled"

        lines.append(f"- {name}")
        lines.append(f"  Destination: {subnet}")
        lines.append(f"  Gateway: {gateway}")
        lines.append(f"  Status: {status}")
        lines.append("")

    return "\n".join(lines)


STATIC_ROUTE_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="get_static_routes",
        description="Get all static routes for the current site",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=_handle_get_static_routes,
    ),
    ToolSpec(
        name="create_static_route",
        description="Create a new static route",
        input_schema={
            "type": "object",
            "properties": {"route": _STATIC_ROUTE_PROPERTY},
            "required": ["route"],
        },
        handler=_handle_create_static_route,
    ),
    ToolSpec(
        name="update_static_route",
        description="Update an existing static route",
        input_schema={
            "type": "object",
            "properties": {
                "route_id": _STATIC_ROUTE_ID_PROPERTY,
                "route": _STATIC_ROUTE_PROPERTY,
            },
            "required": ["route_id", "route"],
        },
        handler=_handle_update_static_route,
    ),
    ToolSpec(
        name="delete_static_route",
        description="Delete a static route by its route ID",
        input_schema={
            "type": "object",
            "properties": {"route_id": _STATIC_ROUTE_ID_PROPERTY},
            "required": ["route_id"],
        },
        handler=_handle_delete_static_route,
    ),
]
