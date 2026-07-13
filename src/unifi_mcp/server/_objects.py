"""Network object (address/port group) CRUD tools."""

from typing import Any

from unifi_mcp.server._schema import ToolSpec
from unifi_mcp.unifi_client import UniFiClient

_OBJECT_ID_PROPERTY = {
    "type": "string",
    "description": "Network object ID (`_id`), as returned by get_objects",
}

_OBJECT_PROPERTY = {
    "type": "object",
    "description": (
        "Network object fields (e.g. `name`, `object_type`). Network objects "
        "are the address/port groups used by the object-oriented network "
        "config model, distinct from legacy firewall groups"
    ),
}


# Tool handlers
async def _handle_get_objects(client: UniFiClient, arguments: dict[str, Any]) -> str:
    return format_objects(await client.get_objects())


async def _handle_create_object(client: UniFiClient, arguments: dict[str, Any]) -> str:
    obj = arguments.get("object", {})
    created = await client.create_object(obj)
    name = created.get("name", created.get("_id", "new object"))
    return f"Network object '{name}' has been created."


async def _handle_update_object(client: UniFiClient, arguments: dict[str, Any]) -> str:
    object_id = arguments.get("object_id", "")
    obj = arguments.get("object", {})
    await client.update_object(object_id, obj)
    return f"Network object {object_id} has been updated."


async def _handle_delete_object(client: UniFiClient, arguments: dict[str, Any]) -> str:
    object_id = arguments.get("object_id", "")
    await client.delete_object(object_id)
    return f"Network object {object_id} has been deleted."


# Formatting helpers
def format_objects(objects: list[dict[str, Any]]) -> str:
    """Format network object list for display."""
    if not objects:
        return "No network objects configured."

    lines = [f"Found {len(objects)} network object(s):\n"]

    for obj in objects:
        name = obj.get("name", "Unknown")
        object_type = obj.get("object_type")

        if object_type:
            lines.append(f"- {name} ({object_type})")
        else:
            lines.append(f"- {name}")

    return "\n".join(lines)


OBJECT_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="get_objects",
        description="Get all network objects (address/port groups) for the current site",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=_handle_get_objects,
    ),
    ToolSpec(
        name="create_object",
        description="Create a new network object (address/port group)",
        input_schema={
            "type": "object",
            "properties": {"object": _OBJECT_PROPERTY},
            "required": ["object"],
        },
        handler=_handle_create_object,
    ),
    ToolSpec(
        name="update_object",
        description="Update an existing network object",
        input_schema={
            "type": "object",
            "properties": {
                "object_id": _OBJECT_ID_PROPERTY,
                "object": _OBJECT_PROPERTY,
            },
            "required": ["object_id", "object"],
        },
        handler=_handle_update_object,
    ),
    ToolSpec(
        name="delete_object",
        description="Delete a network object by its object ID",
        input_schema={
            "type": "object",
            "properties": {"object_id": _OBJECT_ID_PROPERTY},
            "required": ["object_id"],
        },
        handler=_handle_delete_object,
    ),
]
