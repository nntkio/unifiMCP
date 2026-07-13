"""Device inventory, `cmd/devmgr` lifecycle commands, and per-device activity tools."""

from typing import Any

from unifi_mcp.server._formatting import _format_client_lines, format_bytes
from unifi_mcp.server._schema import _MAC_PROPERTY, ToolSpec
from unifi_mcp.unifi_client import UniFiClient

_PORT_IDX_PROPERTY = {
    "type": "integer",
    "description": "Index of the switch port to power-cycle",
}


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


async def _handle_get_device_activity(
    client: UniFiClient, arguments: dict[str, Any]
) -> str:
    mac = arguments.get("mac", "")
    return format_device_activity(await client.get_device_activity(mac))


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


DEVICE_TOOLS: list[ToolSpec] = [
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
]
