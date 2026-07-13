"""Legacy firewall rule and zone-based firewall policy tools."""

import asyncio
from typing import Any

from unifi_mcp.server._schema import ToolSpec
from unifi_mcp.unifi_client import UniFiClient

_RULE_ID_PROPERTY = {
    "type": "string",
    "description": "Legacy firewall rule ID (`_id`), as returned by get_firewall_rules",
}

_POLICY_ID_PROPERTY = {
    "type": "string",
    "description": "Zone-based firewall policy ID (`_id`), as returned by get_firewall_rules",
}

_FIREWALL_RULE_PROPERTY = {
    "type": "object",
    "description": (
        "Legacy firewall rule fields (e.g. `name`, `ruleset`, `action`, "
        "`protocol`, `src_address`, `dst_address`, `enabled`)"
    ),
}

_FIREWALL_POLICY_PROPERTY = {
    "type": "object",
    "description": (
        "Zone-based firewall policy fields (e.g. `name`, `action`, "
        "`enabled`, `source`, `destination`)"
    ),
}


# Tool handlers
async def _handle_get_firewall_rules(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    rules, policies = await asyncio.gather(
        client.get_firewall_rules(), client.get_firewall_policies()
    )
    return format_firewall_rules(rules, policies)


async def _handle_enable_firewall_rule(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    rule_id = arguments.get("rule_id", "")
    await client.set_firewall_rule_enabled(rule_id, True)
    return f"Firewall rule {rule_id} has been enabled."


async def _handle_disable_firewall_rule(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    rule_id = arguments.get("rule_id", "")
    await client.set_firewall_rule_enabled(rule_id, False)
    return f"Firewall rule {rule_id} has been disabled."


async def _handle_create_firewall_rule(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    rule = arguments.get("rule", {})
    created = await client.create_firewall_rule(rule)
    name = created.get("name", created.get("_id", "new rule"))
    return f"Firewall rule '{name}' has been created."


async def _handle_delete_firewall_rule(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    rule_id = arguments.get("rule_id", "")
    await client.delete_firewall_rule(rule_id)
    return f"Firewall rule {rule_id} has been deleted."


async def _handle_enable_firewall_policy(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    policy_id = arguments.get("policy_id", "")
    await client.set_firewall_policy_enabled(policy_id, True)
    return f"Firewall policy {policy_id} has been enabled."


async def _handle_disable_firewall_policy(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    policy_id = arguments.get("policy_id", "")
    await client.set_firewall_policy_enabled(policy_id, False)
    return f"Firewall policy {policy_id} has been disabled."


async def _handle_create_firewall_policy(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    policy = arguments.get("policy", {})
    created = await client.create_firewall_policy(policy)
    name = created.get("name", created.get("_id", "new policy"))
    return f"Firewall policy '{name}' has been created."


async def _handle_batch_update_firewall_policies(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    policies = arguments.get("policies", [])
    await client.batch_update_firewall_policies(policies)
    plural = "y" if len(policies) == 1 else "ies"
    return f"Updated {len(policies)} firewall polic{plural}."


async def _handle_batch_delete_firewall_policies(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    policy_ids = arguments.get("policy_ids", [])
    await client.batch_delete_firewall_policies(policy_ids)
    plural = "y" if len(policy_ids) == 1 else "ies"
    return f"Deleted {len(policy_ids)} firewall polic{plural}."


async def _handle_get_firewall_zones(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    return format_firewall_zones(await client.get_firewall_zones())


async def _handle_get_firewall_zone_matrix(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    return format_firewall_zone_matrix(await client.get_firewall_zone_matrix())


# Formatting helpers
def format_firewall_rules(
    rules: list[dict[str, Any]], policies: list[dict[str, Any]]
) -> str:
    """Format legacy firewall rules and zone-based firewall policies as one Markdown grid."""
    if not rules and not policies:
        return "No firewall rules or policies configured."

    lines = [
        f"Found {len(rules)} legacy rule(s) and {len(policies)} zone-based "
        f"polic{'y' if len(policies) == 1 else 'ies'}:\n",
        "| Name | Type | Ruleset/Action | Status | Predefined | Rule ID |",
        "|------|------|----------------|--------|------------|---------|",
    ]

    for rule in rules:
        name = rule.get("name", "Unnamed")
        ruleset = rule.get("ruleset", "N/A")
        action = rule.get("action", "N/A").upper()
        status = "Active" if rule.get("enabled", False) else "Inactive"
        rule_id = rule.get("_id", "N/A")
        lines.append(
            f"| {name} | Legacy | {ruleset} / {action} | {status} | - | {rule_id} |"
        )

    for policy in policies:
        name = policy.get("name", "Unnamed")
        action = policy.get("action", "N/A").upper()
        status = "Active" if policy.get("enabled", False) else "Inactive"
        predefined = "Yes" if policy.get("predefined", False) else "No"
        policy_id = policy.get("_id", "N/A")
        lines.append(
            f"| {name} | Zone Policy | {action} | {status} | {predefined} | {policy_id} |"
        )

    return "\n".join(lines)


def format_firewall_zones(zones: list[dict[str, Any]]) -> str:
    """Format firewall zone list for display."""
    if not zones:
        return "No firewall zones configured."

    lines = [f"Found {len(zones)} firewall zone(s):\n"]
    for zone in zones:
        name = zone.get("name", "Unnamed")
        zone_id = zone.get("_id", "N/A")
        lines.append(f"- {name}")
        lines.append(f"  ID: {zone_id}")
        lines.append("")

    return "\n".join(lines)


def format_firewall_zone_matrix(matrix: list[dict[str, Any]]) -> str:
    """Format the firewall zone matrix for display."""
    if not matrix:
        return "No firewall zone matrix data available."

    lines = [
        "Firewall Zone Matrix:\n",
        "| From Zone | To Zone | Default Action |",
        "|-----------|---------|----------------|",
    ]
    for entry in matrix:
        from_zone = entry.get("from_zone_name", entry.get("from_zone_id", "N/A"))
        to_zone = entry.get("to_zone_name", entry.get("to_zone_id", "N/A"))
        action = entry.get("action", entry.get("default_action", "N/A"))
        lines.append(f"| {from_zone} | {to_zone} | {action} |")

    return "\n".join(lines)


FIREWALL_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="get_firewall_rules",
        description=(
            "Get all firewall rules for the current site - both legacy custom "
            "rules and zone-based firewall policies (including predefined "
            "ones) - with each rule's active/inactive status"
        ),
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=_handle_get_firewall_rules,
    ),
    ToolSpec(
        name="enable_firewall_rule",
        description="Enable (activate) a legacy firewall rule by its rule ID",
        input_schema={
            "type": "object",
            "properties": {"rule_id": _RULE_ID_PROPERTY},
            "required": ["rule_id"],
        },
        handler=_handle_enable_firewall_rule,
    ),
    ToolSpec(
        name="disable_firewall_rule",
        description="Disable (deactivate) a legacy firewall rule by its rule ID",
        input_schema={
            "type": "object",
            "properties": {"rule_id": _RULE_ID_PROPERTY},
            "required": ["rule_id"],
        },
        handler=_handle_disable_firewall_rule,
    ),
    ToolSpec(
        name="create_firewall_rule",
        description="Create a new legacy firewall rule",
        input_schema={
            "type": "object",
            "properties": {"rule": _FIREWALL_RULE_PROPERTY},
            "required": ["rule"],
        },
        handler=_handle_create_firewall_rule,
    ),
    ToolSpec(
        name="delete_firewall_rule",
        description="Delete a legacy firewall rule by its rule ID",
        input_schema={
            "type": "object",
            "properties": {"rule_id": _RULE_ID_PROPERTY},
            "required": ["rule_id"],
        },
        handler=_handle_delete_firewall_rule,
    ),
    ToolSpec(
        name="enable_firewall_policy",
        description=(
            "Enable (activate) a zone-based firewall policy by its policy ID "
            "(predefined policies can't be modified)"
        ),
        input_schema={
            "type": "object",
            "properties": {"policy_id": _POLICY_ID_PROPERTY},
            "required": ["policy_id"],
        },
        handler=_handle_enable_firewall_policy,
    ),
    ToolSpec(
        name="disable_firewall_policy",
        description=(
            "Disable (deactivate) a zone-based firewall policy by its policy ID "
            "(predefined policies can't be modified)"
        ),
        input_schema={
            "type": "object",
            "properties": {"policy_id": _POLICY_ID_PROPERTY},
            "required": ["policy_id"],
        },
        handler=_handle_disable_firewall_policy,
    ),
    ToolSpec(
        name="create_firewall_policy",
        description="Create a new zone-based firewall policy",
        input_schema={
            "type": "object",
            "properties": {"policy": _FIREWALL_POLICY_PROPERTY},
            "required": ["policy"],
        },
        handler=_handle_create_firewall_policy,
    ),
    ToolSpec(
        name="batch_update_firewall_policies",
        description=(
            "Bulk-update zone-based firewall policies (predefined policies "
            "can't be modified)"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "policies": {
                    "type": "array",
                    "items": _FIREWALL_POLICY_PROPERTY,
                    "description": "Full policy objects to update, each including `_id`",
                }
            },
            "required": ["policies"],
        },
        handler=_handle_batch_update_firewall_policies,
    ),
    ToolSpec(
        name="batch_delete_firewall_policies",
        description=(
            "Bulk-delete zone-based firewall policies by ID (predefined "
            "policies can't be deleted)"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "policy_ids": {
                    "type": "array",
                    "items": _POLICY_ID_PROPERTY,
                    "description": "Policy IDs (`_id`) to delete",
                }
            },
            "required": ["policy_ids"],
        },
        handler=_handle_batch_delete_firewall_policies,
    ),
    ToolSpec(
        name="get_firewall_zones",
        description="Get all firewall zones referenced by zone-based firewall policies",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=_handle_get_firewall_zones,
    ),
    ToolSpec(
        name="get_firewall_zone_matrix",
        description=(
            "Get the default allow/block posture between each pair of firewall zones"
        ),
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=_handle_get_firewall_zone_matrix,
    ),
]
