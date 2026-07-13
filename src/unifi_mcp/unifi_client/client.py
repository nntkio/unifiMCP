"""Public UniFi API client, composed from per-domain mixins."""

from unifi_mcp.unifi_client._base import _BaseClient
from unifi_mcp.unifi_client._clients import _ClientMixin
from unifi_mcp.unifi_client._devices import _DeviceMixin
from unifi_mcp.unifi_client._firewall import _FirewallMixin
from unifi_mcp.unifi_client._firewall_groups import _FirewallGroupMixin
from unifi_mcp.unifi_client._nat_rules import _NatRuleMixin
from unifi_mcp.unifi_client._networks import _NetworkMixin
from unifi_mcp.unifi_client._objects import _NetworkObjectMixin
from unifi_mcp.unifi_client._oo_network_configs import _OONetworkConfigMixin
from unifi_mcp.unifi_client._port_forwarding import _PortForwardingMixin
from unifi_mcp.unifi_client._port_profiles import _PortProfileMixin
from unifi_mcp.unifi_client._qos_rules import _QosRuleMixin
from unifi_mcp.unifi_client._radius_profiles import _RadiusProfileMixin
from unifi_mcp.unifi_client._sites import _SiteMixin
from unifi_mcp.unifi_client._static_routes import _StaticRouteMixin
from unifi_mcp.unifi_client._traffic_routes import _TrafficRouteMixin
from unifi_mcp.unifi_client._traffic_rules import _TrafficRuleMixin
from unifi_mcp.unifi_client._wan_sla_profiles import _WanSlaProfileMixin
from unifi_mcp.unifi_client._wlan import _WlanMixin
from unifi_mcp.unifi_client._wlan_rate_profiles import _WlanRateProfileMixin


class UniFiClient(
    _DeviceMixin,
    _ClientMixin,
    _SiteMixin,
    _NetworkMixin,
    _FirewallMixin,
    _FirewallGroupMixin,
    _TrafficRuleMixin,
    _TrafficRouteMixin,
    _QosRuleMixin,
    _NatRuleMixin,
    _PortForwardingMixin,
    _StaticRouteMixin,
    _WlanMixin,
    _PortProfileMixin,
    _RadiusProfileMixin,
    _WanSlaProfileMixin,
    _WlanRateProfileMixin,
    _NetworkObjectMixin,
    _OONetworkConfigMixin,
    _BaseClient,
):
    """Client for interacting with UniFi Controller API.

    Combines domain-specific mixins (devices, clients, sites, networks,
    firewall, firewall groups, traffic rules/routes, QoS rules, NAT rules,
    port forwarding, static routes, WLANs, port/RADIUS/WAN-SLA/WLAN-rate
    profiles, network objects, and object-oriented network configs) with
    `_BaseClient`'s connection/session/request plumbing into a single flat
    interface, e.g. `client.get_devices()`, `client.block_client(mac)`.
    """
