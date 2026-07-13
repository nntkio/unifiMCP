"""QoS (Quality of Service) rule tools."""

from typing import Any

from unifi_mcp.server._schema import ToolSpec
from unifi_mcp.unifi_client import UniFiClient

_QOS_RULE_ID_PROPERTY = {
    "type": "string",
    "description": "QoS rule ID (`_id`), as returned by get_qos_rules",
}

_QOS_RULE_PROPERTY = {
    "type": "object",
    "description": ("QoS rule fields (e.g. `name`, `enabled`, `bandwidth_limit`)"),
}


# Tool handlers
async def _handle_get_qos_rules(client: UniFiClient, arguments: dict[str, Any]) -> str:
    rules = await client.get_qos_rules()
    return format_qos_rules(rules)


async def _handle_create_qos_rule(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    rule = arguments.get("rule", {})
    created = await client.create_qos_rule(rule)
    name = created.get("name", created.get("_id", "new rule"))
    return f"QoS rule '{name}' has been created."


async def _handle_update_qos_rule(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    rule_id = arguments.get("rule_id", "")
    rule = arguments.get("rule", {})
    await client.update_qos_rule(rule_id, rule)
    return f"QoS rule {rule_id} has been updated."


async def _handle_delete_qos_rule(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    rule_id = arguments.get("rule_id", "")
    await client.delete_qos_rule(rule_id)
    return f"QoS rule {rule_id} has been deleted."


async def _handle_batch_update_qos_rules(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    rules = arguments.get("rules", [])
    await client.batch_update_qos_rules(rules)
    plural = "" if len(rules) == 1 else "s"
    return f"Updated {len(rules)} QoS rule{plural}."


# Formatting helpers
def format_qos_rules(rules: list[dict[str, Any]]) -> str:
    """Format QoS rule list for display."""
    if not rules:
        return "No QoS rules configured."

    lines = [f"Found {len(rules)} QoS rule(s):\n"]

    for rule in rules:
        name = rule.get("name", "Unnamed")
        status = "Enabled" if rule.get("enabled", False) else "Disabled"
        rule_id = rule.get("_id", "N/A")

        lines.append(f"- {name}")
        lines.append(f"  Status: {status}")
        lines.append(f"  ID: {rule_id}")
        lines.append("")

    return "\n".join(lines)


QOS_RULE_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="get_qos_rules",
        description="Get all QoS (Quality of Service) rules for the current site",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=_handle_get_qos_rules,
    ),
    ToolSpec(
        name="create_qos_rule",
        description="Create a new QoS rule",
        input_schema={
            "type": "object",
            "properties": {"rule": _QOS_RULE_PROPERTY},
            "required": ["rule"],
        },
        handler=_handle_create_qos_rule,
    ),
    ToolSpec(
        name="update_qos_rule",
        description="Update an existing QoS rule by its rule ID",
        input_schema={
            "type": "object",
            "properties": {
                "rule_id": _QOS_RULE_ID_PROPERTY,
                "rule": _QOS_RULE_PROPERTY,
            },
            "required": ["rule_id", "rule"],
        },
        handler=_handle_update_qos_rule,
    ),
    ToolSpec(
        name="delete_qos_rule",
        description="Delete a QoS rule by its rule ID",
        input_schema={
            "type": "object",
            "properties": {"rule_id": _QOS_RULE_ID_PROPERTY},
            "required": ["rule_id"],
        },
        handler=_handle_delete_qos_rule,
    ),
    ToolSpec(
        name="batch_update_qos_rules",
        description="Bulk-update QoS rules",
        input_schema={
            "type": "object",
            "properties": {
                "rules": {
                    "type": "array",
                    "items": _QOS_RULE_PROPERTY,
                    "description": "Full QoS rule objects to update, each including `_id`",
                }
            },
            "required": ["rules"],
        },
        handler=_handle_batch_update_qos_rules,
    ),
]
