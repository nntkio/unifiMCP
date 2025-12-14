"""MCP tools for UniFi operations."""

from unifi_mcp.tools.clients import (
    block_client,
    disconnect_client,
    get_clients,
    unblock_client,
)
from unifi_mcp.tools.devices import get_devices, restart_device
from unifi_mcp.tools.site import get_networks, get_site_health, get_sites

__all__ = [
    # Device tools
    "get_devices",
    "restart_device",
    # Client tools
    "get_clients",
    "block_client",
    "unblock_client",
    "disconnect_client",
    # Site tools
    "get_sites",
    "get_site_health",
    "get_networks",
]
