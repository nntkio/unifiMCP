"""Public UniFi API client, composed from per-domain mixins."""

from unifi_mcp.unifi_client._base import _BaseClient
from unifi_mcp.unifi_client._clients import _ClientMixin
from unifi_mcp.unifi_client._devices import _DeviceMixin
from unifi_mcp.unifi_client._firewall import _FirewallMixin
from unifi_mcp.unifi_client._networks import _NetworkMixin
from unifi_mcp.unifi_client._sites import _SiteMixin


class UniFiClient(
    _DeviceMixin,
    _ClientMixin,
    _SiteMixin,
    _NetworkMixin,
    _FirewallMixin,
    _BaseClient,
):
    """Client for interacting with UniFi Controller API.

    Combines domain-specific mixins (devices, clients, sites, networks,
    firewall) with `_BaseClient`'s connection/session/request plumbing into
    a single flat interface, e.g. `client.get_devices()`,
    `client.block_client(mac)`.
    """
