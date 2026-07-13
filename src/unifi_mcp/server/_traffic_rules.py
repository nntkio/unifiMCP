"""Legacy traffic rule tools."""

from typing import Any

from unifi_mcp.server._schema import ToolSpec
from unifi_mcp.unifi_client import UniFiClient

_RULE_ID_PROPERTY = {
    "type": "string",
    "description": "Traffic rule ID (`_id`), as returned by get_traffic_rules",
}

_TRAFFIC_RULE_PROPERTY = {
    "type": "object",
    "description": (
        "Traffic rule fields (e.g. `description`, `action`, `enabled`, "
        "`matching_target`)"
    ),
}


# Tool handlers
async def _handle_get_traffic_rules(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    return format_traffic_rules(await client.get_traffic_rules())


async def _handle_create_traffic_rule(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    rule = arguments.get("rule", {})
    created = await client.create_traffic_rule(rule)
    name = created.get("description", created.get("_id", "new rule"))
    return f"Traffic rule '{name}' has been created."


async def _handle_update_traffic_rule(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    rule_id = arguments.get("rule_id", "")
    rule = arguments.get("rule", {})
    await client.update_traffic_rule(rule_id, rule)
    return f"Traffic rule {rule_id} has been updated."


async def _handle_delete_traffic_rule(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    rule_id = arguments.get("rule_id", "")
    await client.delete_traffic_rule(rule_id)
    return f"Traffic rule {rule_id} has been deleted."


async def _handle_enable_traffic_rule(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    rule_id = arguments.get("rule_id", "")
    await client.set_traffic_rule_enabled(rule_id, True)
    return f"Traffic rule {rule_id} has been enabled."


async def _handle_disable_traffic_rule(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    rule_id = arguments.get("rule_id", "")
    await client.set_traffic_rule_enabled(rule_id, False)
    return f"Traffic rule {rule_id} has been disabled."


# Formatting helpers
def format_traffic_rules(rules: list[dict[str, Any]]) -> str:
    """Format traffic rule list for display."""
    if not rules:
        return "No traffic rules configured."

    lines = [f"Found {len(rules)} traffic rule(s):\n"]

    for rule in rules:
        name = rule.get("description", rule.get("_id", "Unnamed"))
        action = rule.get("action", "N/A").upper()
        enabled = rule.get("enabled", False)
        status = "Enabled" if enabled else "Disabled"

        lines.append(f"- {name}")
        lines.append(f"  Action: {action}")
        lines.append(f"  Status: {status}")
        lines.append("")

    return "\n".join(lines)


TRAFFIC_RULE_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="get_traffic_rules",
        description="Get all traffic rules for the current site",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=_handle_get_traffic_rules,
    ),
    ToolSpec(
        name="create_traffic_rule",
        description="Create a new traffic rule",
        input_schema={
            "type": "object",
            "properties": {"rule": _TRAFFIC_RULE_PROPERTY},
            "required": ["rule"],
        },
        handler=_handle_create_traffic_rule,
    ),
    ToolSpec(
        name="update_traffic_rule",
        description="Update an existing traffic rule",
        input_schema={
            "type": "object",
            "properties": {
                "rule_id": _RULE_ID_PROPERTY,
                "rule": _TRAFFIC_RULE_PROPERTY,
            },
            "required": ["rule_id", "rule"],
        },
        handler=_handle_update_traffic_rule,
    ),
    ToolSpec(
        name="delete_traffic_rule",
        description="Delete a traffic rule by its rule ID",
        input_schema={
            "type": "object",
            "properties": {"rule_id": _RULE_ID_PROPERTY},
            "required": ["rule_id"],
        },
        handler=_handle_delete_traffic_rule,
    ),
    ToolSpec(
        name="enable_traffic_rule",
        description="Enable (activate) a traffic rule by its rule ID",
        input_schema={
            "type": "object",
            "properties": {"rule_id": _RULE_ID_PROPERTY},
            "required": ["rule_id"],
        },
        handler=_handle_enable_traffic_rule,
    ),
    ToolSpec(
        name="disable_traffic_rule",
        description="Disable (deactivate) a traffic rule by its rule ID",
        input_schema={
            "type": "object",
            "properties": {"rule_id": _RULE_ID_PROPERTY},
            "required": ["rule_id"],
        },
        handler=_handle_disable_traffic_rule,
    ),
]
