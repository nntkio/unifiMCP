"""MCP server implementation for UniFi."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from unifi_mcp.unifi_client import (
    UniFiAuthenticationError,
    UniFiClient,
    UniFiConnectionError,
    UniFiError,
)

# Create the MCP server instance
server = Server("unifi-mcp")

# A single authenticated client is reused across tool calls instead of
# logging in and out on every call; _request() re-logs-in once on a 401
# if the session has expired.
_client: UniFiClient | None = None
_client_lock = asyncio.Lock()


async def _get_client() -> UniFiClient:
    """Get the shared authenticated UniFi client, connecting it on first use."""
    global _client
    async with _client_lock:
        if _client is None:
            _client = await UniFiClient().connect()
    return _client


async def _close_client() -> None:
    """Close the shared UniFi client, if one was ever opened."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None


# Tool handlers
async def _handle_get_devices(client: UniFiClient, arguments: dict[str, Any]) -> str:
    return format_devices(await client.get_devices())


async def _handle_restart_device(client: UniFiClient, arguments: dict[str, Any]) -> str:
    mac = arguments.get("mac", "")
    await client.restart_device(mac)
    return f"Restart command sent to device {mac}"


async def _handle_adopt_device(client: UniFiClient, arguments: dict[str, Any]) -> str:
    mac = arguments.get("mac", "")
    await client.adopt_device(mac)
    return f"Adopt command sent to device {mac}"


async def _handle_force_provision_device(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    mac = arguments.get("mac", "")
    await client.force_provision_device(mac)
    return f"Force-provision command sent to device {mac}"


async def _handle_upgrade_device(client: UniFiClient, arguments: dict[str, Any]) -> str:
    mac = arguments.get("mac", "")
    await client.upgrade_device(mac)
    return f"Upgrade command sent to device {mac}"


async def _handle_power_cycle_port(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    mac = arguments.get("mac", "")
    port_idx = arguments.get("port_idx", 0)
    await client.power_cycle_port(mac, port_idx)
    return f"Power-cycle command sent to port {port_idx} on device {mac}"


async def _handle_set_device_locate(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    mac = arguments.get("mac", "")
    await client.set_device_locate(mac)
    return f"Locate LED enabled on device {mac}"


async def _handle_unset_device_locate(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    mac = arguments.get("mac", "")
    await client.unset_device_locate(mac)
    return f"Locate LED disabled on device {mac}"


async def _handle_get_clients(client: UniFiClient, arguments: dict[str, Any]) -> str:
    if arguments.get("include_offline", False):
        clients = await client.get_all_clients()
    else:
        clients = await client.get_clients()
    return format_clients(clients)


async def _handle_block_client(client: UniFiClient, arguments: dict[str, Any]) -> str:
    mac = arguments.get("mac", "")
    await client.block_client(mac)
    return f"Client {mac} has been blocked from the network."


async def _handle_unblock_client(client: UniFiClient, arguments: dict[str, Any]) -> str:
    mac = arguments.get("mac", "")
    await client.unblock_client(mac)
    return f"Client {mac} has been unblocked."


async def _handle_disconnect_client(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    mac = arguments.get("mac", "")
    await client.disconnect_client(mac)
    return f"Client {mac} has been disconnected."


async def _handle_forget_client(client: UniFiClient, arguments: dict[str, Any]) -> str:
    mac = arguments.get("mac", "")
    await client.forget_client(mac)
    return f"Client {mac} has been forgotten by the controller."


async def _handle_authorize_guest(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    mac = arguments.get("mac", "")
    minutes = arguments.get("minutes")
    await client.authorize_guest(mac, minutes)
    return f"Client {mac} has been authorized via the guest portal."


async def _handle_unauthorize_guest(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    mac = arguments.get("mac", "")
    await client.unauthorize_guest(mac)
    return f"Client {mac}'s guest portal authorization has been revoked."


async def _handle_get_sites(client: UniFiClient, arguments: dict[str, Any]) -> str:
    return format_sites(await client.get_sites())


async def _handle_get_site_health(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    return format_health(await client.get_site_health())


async def _handle_get_networks(client: UniFiClient, arguments: dict[str, Any]) -> str:
    return format_networks(await client.get_networks())


async def _handle_create_network(client: UniFiClient, arguments: dict[str, Any]) -> str:
    network = arguments.get("network", {})
    created = await client.create_network(network)
    name = created.get("name", created.get("_id", "new network"))
    return f"Network '{name}' has been created."


async def _handle_update_network(client: UniFiClient, arguments: dict[str, Any]) -> str:
    network_id = arguments.get("network_id", "")
    network = arguments.get("network", {})
    await client.update_network(network_id, network)
    return f"Network {network_id} has been updated."


async def _handle_delete_network(client: UniFiClient, arguments: dict[str, Any]) -> str:
    network_id = arguments.get("network_id", "")
    await client.delete_network(network_id)
    return f"Network {network_id} has been deleted."


async def _handle_get_device_activity(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    mac = arguments.get("mac", "")
    return format_device_activity(await client.get_device_activity(mac))


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


@dataclass(frozen=True)
class ToolSpec:
    """Declarative definition of an MCP tool: its schema and its handler."""

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[UniFiClient, dict[str, Any]], Awaitable[str]]


_MAC_PROPERTY = {
    "type": "string",
    "description": "MAC address of the target (e.g., '00:11:22:33:44:55')",
}

_RULE_ID_PROPERTY = {
    "type": "string",
    "description": "Legacy firewall rule ID (`_id`), as returned by get_firewall_rules",
}

_POLICY_ID_PROPERTY = {
    "type": "string",
    "description": "Zone-based firewall policy ID (`_id`), as returned by get_firewall_rules",
}

_NETWORK_ID_PROPERTY = {
    "type": "string",
    "description": "Network configuration ID (`_id`), as returned by get_networks",
}

_PORT_IDX_PROPERTY = {
    "type": "integer",
    "description": "Index of the switch port to power-cycle",
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

_NETWORK_PROPERTY = {
    "type": "object",
    "description": (
        "Network configuration fields (e.g. `name`, `purpose`, `vlan`, "
        "`ip_subnet`, `enabled`)"
    ),
}

TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="get_devices",
        description="Get all UniFi network devices (access points, switches, gateways)",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=_handle_get_devices,
    ),
    ToolSpec(
        name="restart_device",
        description="Restart a UniFi network device by its MAC address",
        input_schema={
            "type": "object",
            "properties": {"mac": _MAC_PROPERTY},
            "required": ["mac"],
        },
        handler=_handle_restart_device,
    ),
    ToolSpec(
        name="adopt_device",
        description="Adopt a pending UniFi device onto the controller",
        input_schema={
            "type": "object",
            "properties": {"mac": _MAC_PROPERTY},
            "required": ["mac"],
        },
        handler=_handle_adopt_device,
    ),
    ToolSpec(
        name="force_provision_device",
        description="Force a configuration push to a UniFi device",
        input_schema={
            "type": "object",
            "properties": {"mac": _MAC_PROPERTY},
            "required": ["mac"],
        },
        handler=_handle_force_provision_device,
    ),
    ToolSpec(
        name="upgrade_device",
        description="Trigger a firmware upgrade on a UniFi device",
        input_schema={
            "type": "object",
            "properties": {"mac": _MAC_PROPERTY},
            "required": ["mac"],
        },
        handler=_handle_upgrade_device,
    ),
    ToolSpec(
        name="power_cycle_port",
        description="Power-cycle a PoE port on a UniFi switch",
        input_schema={
            "type": "object",
            "properties": {"mac": _MAC_PROPERTY, "port_idx": _PORT_IDX_PROPERTY},
            "required": ["mac", "port_idx"],
        },
        handler=_handle_power_cycle_port,
    ),
    ToolSpec(
        name="set_device_locate",
        description="Flash a UniFi device's LED to help locate it physically",
        input_schema={
            "type": "object",
            "properties": {"mac": _MAC_PROPERTY},
            "required": ["mac"],
        },
        handler=_handle_set_device_locate,
    ),
    ToolSpec(
        name="unset_device_locate",
        description="Stop flashing a UniFi device's locate LED",
        input_schema={
            "type": "object",
            "properties": {"mac": _MAC_PROPERTY},
            "required": ["mac"],
        },
        handler=_handle_unset_device_locate,
    ),
    ToolSpec(
        name="get_clients",
        description="Get all currently connected clients on the UniFi network",
        input_schema={
            "type": "object",
            "properties": {
                "include_offline": {
                    "type": "boolean",
                    "description": "Include offline/historical clients",
                    "default": False,
                }
            },
            "required": [],
        },
        handler=_handle_get_clients,
    ),
    ToolSpec(
        name="block_client",
        description="Block a client from accessing the network",
        input_schema={
            "type": "object",
            "properties": {"mac": _MAC_PROPERTY},
            "required": ["mac"],
        },
        handler=_handle_block_client,
    ),
    ToolSpec(
        name="unblock_client",
        description="Unblock a previously blocked client",
        input_schema={
            "type": "object",
            "properties": {"mac": _MAC_PROPERTY},
            "required": ["mac"],
        },
        handler=_handle_unblock_client,
    ),
    ToolSpec(
        name="disconnect_client",
        description="Force disconnect a client from the network",
        input_schema={
            "type": "object",
            "properties": {"mac": _MAC_PROPERTY},
            "required": ["mac"],
        },
        handler=_handle_disconnect_client,
    ),
    ToolSpec(
        name="forget_client",
        description="Remove a client from the controller's known-clients list",
        input_schema={
            "type": "object",
            "properties": {"mac": _MAC_PROPERTY},
            "required": ["mac"],
        },
        handler=_handle_forget_client,
    ),
    ToolSpec(
        name="authorize_guest",
        description="Authorize a client through the guest portal",
        input_schema={
            "type": "object",
            "properties": {
                "mac": _MAC_PROPERTY,
                "minutes": {
                    "type": "integer",
                    "description": "Session length in minutes before authorization expires",
                },
            },
            "required": ["mac"],
        },
        handler=_handle_authorize_guest,
    ),
    ToolSpec(
        name="unauthorize_guest",
        description="Revoke a client's guest portal authorization",
        input_schema={
            "type": "object",
            "properties": {"mac": _MAC_PROPERTY},
            "required": ["mac"],
        },
        handler=_handle_unauthorize_guest,
    ),
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
    ToolSpec(
        name="get_networks",
        description="Get all network configurations for the current site",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=_handle_get_networks,
    ),
    ToolSpec(
        name="create_network",
        description="Create a new network configuration (e.g. a VLAN)",
        input_schema={
            "type": "object",
            "properties": {"network": _NETWORK_PROPERTY},
            "required": ["network"],
        },
        handler=_handle_create_network,
    ),
    ToolSpec(
        name="update_network",
        description="Update an existing network configuration",
        input_schema={
            "type": "object",
            "properties": {
                "network_id": _NETWORK_ID_PROPERTY,
                "network": _NETWORK_PROPERTY,
            },
            "required": ["network_id", "network"],
        },
        handler=_handle_update_network,
    ),
    ToolSpec(
        name="delete_network",
        description="Delete a network configuration by its network ID",
        input_schema={
            "type": "object",
            "properties": {"network_id": _NETWORK_ID_PROPERTY},
            "required": ["network_id"],
        },
        handler=_handle_delete_network,
    ),
    ToolSpec(
        name="get_device_activity",
        description="Get activity for a specific device including connected clients and their traffic",
        input_schema={
            "type": "object",
            "properties": {
                "mac": {
                    "type": "string",
                    "description": "MAC address of the device (AP or switch)",
                }
            },
            "required": ["mac"],
        },
        handler=_handle_get_device_activity,
    ),
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
]

_TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available UniFi MCP tools."""
    return [
        Tool(name=t.name, description=t.description, inputSchema=t.input_schema)
        for t in TOOLS
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls.

    Args:
        name: The name of the tool to call.
        arguments: The arguments to pass to the tool.

    Returns:
        List of text content with the result.
    """
    tool = _TOOLS_BY_NAME.get(name)
    if tool is None:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    try:
        client = await _get_client()
        text = await tool.handler(client, arguments)
        return [TextContent(type="text", text=text)]
    except UniFiAuthenticationError as e:
        return [
            TextContent(
                type="text",
                text=f"Authentication failed: {e}. Check UNIFI_USERNAME and UNIFI_PASSWORD.",
            )
        ]
    except UniFiConnectionError as e:
        return [
            TextContent(
                type="text",
                text=f"Connection failed: {e}. Check UNIFI_HOST and network connectivity.",
            )
        ]
    except UniFiError as e:
        return [TextContent(type="text", text=f"Error: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Unexpected error: {e}")]


# Formatting helpers
def _format_device_status_lines(
    device: dict[str, Any], indent: str = "  "
) -> list[str]:
    """Format the MAC/model/status lines shared by device summaries."""
    mac = device.get("mac", "Unknown")
    model = device.get("model", "Unknown")
    device_type = device.get("type", "Unknown")
    state_str = "Online" if device.get("state", 0) == 1 else "Offline"

    return [
        f"{indent}MAC: {mac}",
        f"{indent}Model: {model} ({device_type})",
        f"{indent}Status: {state_str}",
    ]


def _format_client_lines(
    client: dict[str, Any],
    bullet_indent: str = "",
    detail_indent: str = "  ",
    include_signal_uptime: bool = False,
) -> list[str]:
    """Format a single client's detail block, shared by client and activity views."""
    hostname = client.get("hostname") or client.get("name") or "Unknown"
    mac = client.get("mac", "Unknown")
    ip = client.get("ip", "N/A")
    conn_type = "Wired" if client.get("is_wired", False) else "Wireless"
    essid = client.get("essid", "")
    tx_bytes = client.get("tx_bytes", 0)
    rx_bytes = client.get("rx_bytes", 0)

    lines = [f"{bullet_indent}- {hostname}"]
    lines.append(f"{detail_indent}MAC: {mac}")
    lines.append(f"{detail_indent}IP: {ip}")
    lines.append(f"{detail_indent}Connection: {conn_type}")
    if essid:
        lines.append(f"{detail_indent}SSID: {essid}")
    if include_signal_uptime:
        signal = client.get("signal")
        uptime = client.get("uptime", 0)
        if signal is not None:
            lines.append(f"{detail_indent}Signal: {signal} dBm")
        if uptime > 0:
            lines.append(f"{detail_indent}Uptime: {format_uptime(uptime)}")
    lines.append(
        f"{detail_indent}Traffic: TX {format_bytes(tx_bytes)} / RX {format_bytes(rx_bytes)}"
    )
    lines.append("")
    return lines


def format_devices(devices: list[dict[str, Any]]) -> str:
    """Format device list for display."""
    if not devices:
        return "No devices found."

    lines = [f"Found {len(devices)} device(s):\n"]

    for device in devices:
        name = device.get("name", "Unknown")
        ip = device.get("ip", "N/A")
        version = device.get("version", "N/A")

        lines.append(f"- {name}")
        lines.extend(_format_device_status_lines(device))
        lines.append(f"  IP: {ip}")
        lines.append(f"  Firmware: {version}")
        lines.append("")

    return "\n".join(lines)


def format_clients(clients: list[dict[str, Any]]) -> str:
    """Format client list for display."""
    if not clients:
        return "No clients found."

    lines = [f"Found {len(clients)} client(s):\n"]
    for client in clients:
        lines.extend(_format_client_lines(client))

    return "\n".join(lines)


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


def format_networks(networks: list[dict[str, Any]]) -> str:
    """Format network list for display."""
    if not networks:
        return "No networks configured."

    lines = [f"Found {len(networks)} network(s):\n"]

    for net in networks:
        name = net.get("name", "Unknown")
        purpose = net.get("purpose", "unknown")
        vlan = net.get("vlan", "N/A")
        subnet = net.get("ip_subnet", "N/A")
        enabled = net.get("enabled", True)
        status = "Enabled" if enabled else "Disabled"

        lines.append(f"- {name}")
        lines.append(f"  Purpose: {purpose}")
        lines.append(f"  VLAN: {vlan}")
        lines.append(f"  Subnet: {subnet}")
        lines.append(f"  Status: {status}")
        lines.append("")

    return "\n".join(lines)


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


def format_bytes(bytes_val: int) -> str:
    """Format bytes to human-readable format."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} PB"


def format_device_activity(activity: dict[str, Any]) -> str:
    """Format device activity for display."""
    lines = []

    device = activity.get("device")
    clients = activity.get("clients", [])
    client_count = activity.get("client_count", 0)
    total_tx = activity.get("total_tx_bytes", 0)
    total_rx = activity.get("total_rx_bytes", 0)

    # Device info
    if device:
        name = device.get("name", "Unknown")
        lines.append(f"Device: {name}")
        lines.extend(_format_device_status_lines(device))
        lines.append("")
    else:
        lines.append("Device: Not found")
        lines.append("")

    # Summary
    lines.append(f"Connected Clients: {client_count}")
    lines.append(
        f"Total Traffic: TX {format_bytes(total_tx)} / RX {format_bytes(total_rx)}"
    )
    lines.append("")

    # Client details
    if clients:
        lines.append("Client Activity:")
        for client in clients:
            lines.extend(
                _format_client_lines(
                    client,
                    bullet_indent="  ",
                    detail_indent="    ",
                    include_signal_uptime=True,
                )
            )
    else:
        lines.append("No clients currently connected to this device.")

    return "\n".join(lines)


def format_uptime(seconds: int) -> str:
    """Format uptime in seconds to human-readable format."""
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")

    return " ".join(parts)


def main() -> None:
    """Run the MCP server."""

    async def run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            try:
                await server.run(
                    read_stream,
                    write_stream,
                    server.create_initialization_options(),
                )
            finally:
                await _close_client()

    asyncio.run(run())


if __name__ == "__main__":
    main()
