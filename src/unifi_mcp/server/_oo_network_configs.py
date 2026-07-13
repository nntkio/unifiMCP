"""Object-oriented network configuration CRUD tools."""

from typing import Any

from unifi_mcp.server._schema import ToolSpec
from unifi_mcp.unifi_client import UniFiClient

_OO_NETWORK_CONFIG_ID_PROPERTY = {
    "type": "string",
    "description": (
        "Object-oriented network configuration ID (`_id`), as returned by "
        "get_oo_network_configs"
    ),
}

_OO_NETWORK_CONFIG_PROPERTY = {
    "type": "object",
    "description": (
        "Object-oriented network configuration fields (e.g. `name`, "
        "`purpose`, `vlan`, `ip_subnet`, `enabled`)"
    ),
}


# Tool handlers
async def _handle_get_oo_network_configs(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    return format_oo_network_configs(await client.get_oo_network_configs())


async def _handle_create_oo_network_config(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    config = arguments.get("config", {})
    created = await client.create_oo_network_config(config)
    name = created.get("name", created.get("_id", "new config"))
    return f"Object-oriented network config '{name}' has been created."


async def _handle_update_oo_network_config(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    config_id = arguments.get("config_id", "")
    config = arguments.get("config", {})
    await client.update_oo_network_config(config_id, config)
    return f"Object-oriented network config {config_id} has been updated."


async def _handle_delete_oo_network_config(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    config_id = arguments.get("config_id", "")
    await client.delete_oo_network_config(config_id)
    return f"Object-oriented network config {config_id} has been deleted."


# Formatting helpers
def format_oo_network_configs(configs: list[dict[str, Any]]) -> str:
    """Format object-oriented network configuration list for display."""
    if not configs:
        return "No object-oriented network configurations configured."

    lines = [f"Found {len(configs)} object-oriented network configuration(s):\n"]

    for config in configs:
        name = config.get("name", "Unknown")
        lines.append(f"- {name}")

    return "\n".join(lines)


OO_NETWORK_CONFIG_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="get_oo_network_configs",
        description=(
            "Get all object-oriented network configurations for the current "
            "site (the newer object-oriented network config model)"
        ),
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=_handle_get_oo_network_configs,
    ),
    ToolSpec(
        name="create_oo_network_config",
        description=(
            "Create a new object-oriented network configuration (the newer "
            "object-oriented network config model)"
        ),
        input_schema={
            "type": "object",
            "properties": {"config": _OO_NETWORK_CONFIG_PROPERTY},
            "required": ["config"],
        },
        handler=_handle_create_oo_network_config,
    ),
    ToolSpec(
        name="update_oo_network_config",
        description=(
            "Update an existing object-oriented network configuration (the "
            "newer object-oriented network config model)"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "config_id": _OO_NETWORK_CONFIG_ID_PROPERTY,
                "config": _OO_NETWORK_CONFIG_PROPERTY,
            },
            "required": ["config_id", "config"],
        },
        handler=_handle_update_oo_network_config,
    ),
    ToolSpec(
        name="delete_oo_network_config",
        description=(
            "Delete an object-oriented network configuration by its config "
            "ID (the newer object-oriented network config model)"
        ),
        input_schema={
            "type": "object",
            "properties": {"config_id": _OO_NETWORK_CONFIG_ID_PROPERTY},
            "required": ["config_id"],
        },
        handler=_handle_delete_oo_network_config,
    ),
]
