"""UniFi API client for communicating with UniFi Controller.

The client's functionality is split by domain into mixins (`_devices.py`,
`_clients.py`, `_sites.py`, `_networks.py`, `_firewall.py`) combined with
connection/request plumbing (`_base.py`) into the public `UniFiClient` in
`client.py`.
"""

from unifi_mcp.unifi_client._base import (
    UniFiAuthenticationError,
    UniFiConnectionError,
    UniFiError,
)
from unifi_mcp.unifi_client.client import UniFiClient

__all__ = [
    "UniFiAuthenticationError",
    "UniFiClient",
    "UniFiConnectionError",
    "UniFiError",
]
