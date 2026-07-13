"""NAT rules CRUD tools."""

from typing import Any

from unifi_mcp.server._schema import ToolSpec
from unifi_mcp.unifi_client import UniFiClient

_NAT_RULE_ID_PROPERTY = {
    "type": "string",
    "description": "NAT rule ID (`_id`), as returned by get_nat_rules",
}

_NAT_RULE_PROPERTY = {
    "type": "object",
    "description": (
        "NAT rule fields (e.g. `name`, `enabled`, `type`, `source`, `destination`)"
    ),
}


# Tool handlers
async def _handle_get_nat_rules(client: UniFiClient, arguments: dict[str, Any]) -> str:
    return format_nat_rules(await client.get_nat_rules())


async def _handle_create_nat_rule(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    rule = arguments.get("rule", {})
    created = await client.create_nat_rule(rule)
    name = created.get("name", created.get("_id", "new NAT rule"))
    return f"NAT rule '{name}' has been created."


async def _handle_update_nat_rule(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    rule_id = arguments.get("rule_id", "")
    rule = arguments.get("rule", {})
    await client.update_nat_rule(rule_id, rule)
    return f"NAT rule {rule_id} has been updated."


async def _handle_delete_nat_rule(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    rule_id = arguments.get("rule_id", "")
    await client.delete_nat_rule(rule_id)
    return f"NAT rule {rule_id} has been deleted."


# Formatting helpers
def format_nat_rules(rules: list[dict[str, Any]]) -> str:
    """Format NAT rule list for display."""
    if not rules:
        return "No NAT rules configured."

    lines = [f"Found {len(rules)} NAT rule(s):\n"]

    for rule in rules:
        name = rule.get("name", "Unknown")
        enabled = rule.get("enabled", True)
        status = "Enabled" if enabled else "Disabled"

        lines.append(f"- {name}")
        lines.append(f"  Status: {status}")
        lines.append("")

    return "\n".join(lines)


NAT_RULE_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="get_nat_rules",
        description="Get all NAT rules for the current site",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=_handle_get_nat_rules,
    ),
    ToolSpec(
        name="create_nat_rule",
        description="Create a new NAT rule",
        input_schema={
            "type": "object",
            "properties": {"rule": _NAT_RULE_PROPERTY},
            "required": ["rule"],
        },
        handler=_handle_create_nat_rule,
    ),
    ToolSpec(
        name="update_nat_rule",
        description="Update an existing NAT rule",
        input_schema={
            "type": "object",
            "properties": {
                "rule_id": _NAT_RULE_ID_PROPERTY,
                "rule": _NAT_RULE_PROPERTY,
            },
            "required": ["rule_id", "rule"],
        },
        handler=_handle_update_nat_rule,
    ),
    ToolSpec(
        name="delete_nat_rule",
        description="Delete a NAT rule by its rule ID",
        input_schema={
            "type": "object",
            "properties": {"rule_id": _NAT_RULE_ID_PROPERTY},
            "required": ["rule_id"],
        },
        handler=_handle_delete_nat_rule,
    ),
]
