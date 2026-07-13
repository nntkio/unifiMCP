"""Tests for MCP server."""

from unittest.mock import AsyncMock, patch

import pytest

from unifi_mcp import server as server_module
from unifi_mcp.server import (
    call_tool,
    format_bytes,
    format_clients,
    format_device_activity,
    format_devices,
    format_firewall_rules,
    format_health,
    format_networks,
    format_sites,
    format_uptime,
    list_tools,
)


class TestListTools:
    """Tests for list_tools function."""

    @pytest.mark.asyncio
    async def test_list_tools_returns_all_tools(self) -> None:
        """Test that list_tools returns all expected tools."""
        tools = await list_tools()

        tool_names = [t.name for t in tools]
        assert "get_devices" in tool_names
        assert "restart_device" in tool_names
        assert "adopt_device" in tool_names
        assert "force_provision_device" in tool_names
        assert "upgrade_device" in tool_names
        assert "power_cycle_port" in tool_names
        assert "set_device_locate" in tool_names
        assert "unset_device_locate" in tool_names
        assert "get_clients" in tool_names
        assert "block_client" in tool_names
        assert "unblock_client" in tool_names
        assert "disconnect_client" in tool_names
        assert "forget_client" in tool_names
        assert "authorize_guest" in tool_names
        assert "unauthorize_guest" in tool_names
        assert "get_sites" in tool_names
        assert "get_site_health" in tool_names
        assert "get_networks" in tool_names
        assert "create_network" in tool_names
        assert "update_network" in tool_names
        assert "delete_network" in tool_names
        assert "get_device_activity" in tool_names
        assert "get_firewall_rules" in tool_names
        assert "enable_firewall_rule" in tool_names
        assert "disable_firewall_rule" in tool_names
        assert "create_firewall_rule" in tool_names
        assert "delete_firewall_rule" in tool_names
        assert "enable_firewall_policy" in tool_names
        assert "disable_firewall_policy" in tool_names
        assert "create_firewall_policy" in tool_names
        assert "batch_update_firewall_policies" in tool_names
        assert "batch_delete_firewall_policies" in tool_names

    @pytest.mark.asyncio
    async def test_tools_have_descriptions(self) -> None:
        """Test that all tools have descriptions."""
        tools = await list_tools()

        for tool in tools:
            assert tool.description
            assert len(tool.description) > 10


class TestCallTool:
    """Tests for call_tool function.

    call_tool() fetches its UniFiClient via the shared `_get_client()`
    accessor (a persistent, lazily-connected client reused across calls)
    rather than opening a new connection per call, so tests patch
    `_get_client` directly instead of the `UniFiClient` class.
    """

    @pytest.mark.asyncio
    async def test_call_unknown_tool(self) -> None:
        """Test calling an unknown tool."""
        result = await call_tool("unknown_tool", {})

        assert len(result) == 1
        assert "Unknown tool" in result[0].text

    @pytest.mark.asyncio
    async def test_call_get_devices(self) -> None:
        """Test calling get_devices tool."""
        mock_client = AsyncMock()
        mock_client.get_devices = AsyncMock(
            return_value=[
                {
                    "name": "Living Room AP",
                    "mac": "aa:bb:cc:dd:ee:ff",
                    "model": "UAP-AC-Pro",
                    "type": "uap",
                    "state": 1,
                    "ip": "192.168.1.10",
                    "version": "6.0.0",
                }
            ]
        )
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool("get_devices", {})

        assert len(result) == 1
        assert "Living Room AP" in result[0].text
        assert "aa:bb:cc:dd:ee:ff" in result[0].text

    @pytest.mark.asyncio
    async def test_call_get_clients(self) -> None:
        """Test calling get_clients tool."""
        mock_client = AsyncMock()
        mock_client.get_clients = AsyncMock(
            return_value=[
                {
                    "hostname": "my-laptop",
                    "mac": "11:22:33:44:55:66",
                    "ip": "192.168.1.100",
                    "is_wired": False,
                    "essid": "MyNetwork",
                    "tx_bytes": 1024000,
                    "rx_bytes": 2048000,
                }
            ]
        )
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool("get_clients", {})

        assert len(result) == 1
        assert "my-laptop" in result[0].text
        assert "192.168.1.100" in result[0].text

    @pytest.mark.asyncio
    async def test_call_adopt_device(self) -> None:
        """Test calling adopt_device tool."""
        mock_client = AsyncMock()
        mock_client.adopt_device = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool("adopt_device", {"mac": "aa:bb:cc:dd:ee:ff"})

        assert len(result) == 1
        assert "Adopt" in result[0].text
        mock_client.adopt_device.assert_called_once_with("aa:bb:cc:dd:ee:ff")

    @pytest.mark.asyncio
    async def test_call_force_provision_device(self) -> None:
        """Test calling force_provision_device tool."""
        mock_client = AsyncMock()
        mock_client.force_provision_device = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool(
                "force_provision_device", {"mac": "aa:bb:cc:dd:ee:ff"}
            )

        assert len(result) == 1
        assert "Force-provision" in result[0].text
        mock_client.force_provision_device.assert_called_once_with("aa:bb:cc:dd:ee:ff")

    @pytest.mark.asyncio
    async def test_call_upgrade_device(self) -> None:
        """Test calling upgrade_device tool."""
        mock_client = AsyncMock()
        mock_client.upgrade_device = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool("upgrade_device", {"mac": "aa:bb:cc:dd:ee:ff"})

        assert len(result) == 1
        assert "Upgrade" in result[0].text
        mock_client.upgrade_device.assert_called_once_with("aa:bb:cc:dd:ee:ff")

    @pytest.mark.asyncio
    async def test_call_power_cycle_port(self) -> None:
        """Test calling power_cycle_port tool."""
        mock_client = AsyncMock()
        mock_client.power_cycle_port = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool(
                "power_cycle_port", {"mac": "aa:bb:cc:dd:ee:ff", "port_idx": 3}
            )

        assert len(result) == 1
        assert "Power-cycle" in result[0].text
        mock_client.power_cycle_port.assert_called_once_with("aa:bb:cc:dd:ee:ff", 3)

    @pytest.mark.asyncio
    async def test_call_set_device_locate(self) -> None:
        """Test calling set_device_locate tool."""
        mock_client = AsyncMock()
        mock_client.set_device_locate = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool("set_device_locate", {"mac": "aa:bb:cc:dd:ee:ff"})

        assert len(result) == 1
        assert "Locate LED enabled" in result[0].text
        mock_client.set_device_locate.assert_called_once_with("aa:bb:cc:dd:ee:ff")

    @pytest.mark.asyncio
    async def test_call_unset_device_locate(self) -> None:
        """Test calling unset_device_locate tool."""
        mock_client = AsyncMock()
        mock_client.unset_device_locate = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool(
                "unset_device_locate", {"mac": "aa:bb:cc:dd:ee:ff"}
            )

        assert len(result) == 1
        assert "Locate LED disabled" in result[0].text
        mock_client.unset_device_locate.assert_called_once_with("aa:bb:cc:dd:ee:ff")

    @pytest.mark.asyncio
    async def test_call_block_client(self) -> None:
        """Test calling block_client tool."""
        mock_client = AsyncMock()
        mock_client.block_client = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool("block_client", {"mac": "aa:bb:cc:dd:ee:ff"})

        assert len(result) == 1
        assert "blocked" in result[0].text
        mock_client.block_client.assert_called_once_with("aa:bb:cc:dd:ee:ff")

    @pytest.mark.asyncio
    async def test_call_forget_client(self) -> None:
        """Test calling forget_client tool."""
        mock_client = AsyncMock()
        mock_client.forget_client = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool("forget_client", {"mac": "aa:bb:cc:dd:ee:ff"})

        assert len(result) == 1
        assert "forgotten" in result[0].text
        mock_client.forget_client.assert_called_once_with("aa:bb:cc:dd:ee:ff")

    @pytest.mark.asyncio
    async def test_call_authorize_guest(self) -> None:
        """Test calling authorize_guest tool."""
        mock_client = AsyncMock()
        mock_client.authorize_guest = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool(
                "authorize_guest", {"mac": "aa:bb:cc:dd:ee:ff", "minutes": 60}
            )

        assert len(result) == 1
        assert "authorized" in result[0].text
        mock_client.authorize_guest.assert_called_once_with("aa:bb:cc:dd:ee:ff", 60)

    @pytest.mark.asyncio
    async def test_call_unauthorize_guest(self) -> None:
        """Test calling unauthorize_guest tool."""
        mock_client = AsyncMock()
        mock_client.unauthorize_guest = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool("unauthorize_guest", {"mac": "aa:bb:cc:dd:ee:ff"})

        assert len(result) == 1
        assert "revoked" in result[0].text
        mock_client.unauthorize_guest.assert_called_once_with("aa:bb:cc:dd:ee:ff")

    @pytest.mark.asyncio
    async def test_call_create_network(self) -> None:
        """Test calling create_network tool."""
        mock_client = AsyncMock()
        mock_client.create_network = AsyncMock(
            return_value={"_id": "net1", "name": "IoT"}
        )
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool(
                "create_network", {"network": {"name": "IoT", "vlan": 20}}
            )

        assert len(result) == 1
        assert "IoT" in result[0].text
        mock_client.create_network.assert_called_once_with({"name": "IoT", "vlan": 20})

    @pytest.mark.asyncio
    async def test_call_update_network(self) -> None:
        """Test calling update_network tool."""
        mock_client = AsyncMock()
        mock_client.update_network = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool(
                "update_network",
                {"network_id": "net1", "network": {"name": "IoT", "vlan": 21}},
            )

        assert len(result) == 1
        assert "updated" in result[0].text
        mock_client.update_network.assert_called_once_with(
            "net1", {"name": "IoT", "vlan": 21}
        )

    @pytest.mark.asyncio
    async def test_call_delete_network(self) -> None:
        """Test calling delete_network tool."""
        mock_client = AsyncMock()
        mock_client.delete_network = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool("delete_network", {"network_id": "net1"})

        assert len(result) == 1
        assert "deleted" in result[0].text
        mock_client.delete_network.assert_called_once_with("net1")

    @pytest.mark.asyncio
    async def test_call_get_device_activity(self) -> None:
        """Test calling get_device_activity tool."""
        mock_client = AsyncMock()
        mock_client.get_device_activity = AsyncMock(
            return_value={
                "device": {
                    "name": "Living Room AP",
                    "mac": "aa:bb:cc:dd:ee:ff",
                    "model": "UAP-AC-Pro",
                    "type": "uap",
                    "state": 1,
                },
                "clients": [
                    {
                        "hostname": "laptop",
                        "mac": "11:22:33:44:55:66",
                        "ip": "192.168.1.50",
                        "is_wired": False,
                        "essid": "MyNetwork",
                        "tx_bytes": 1024,
                        "rx_bytes": 2048,
                    }
                ],
                "client_count": 1,
                "total_tx_bytes": 1024,
                "total_rx_bytes": 2048,
            }
        )
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool(
                "get_device_activity", {"mac": "aa:bb:cc:dd:ee:ff"}
            )

        assert len(result) == 1
        assert "Living Room AP" in result[0].text
        assert "laptop" in result[0].text
        assert "Connected Clients: 1" in result[0].text

    @pytest.mark.asyncio
    async def test_call_get_firewall_rules(self) -> None:
        """Test calling get_firewall_rules tool merges legacy rules and zone-based policies."""
        mock_client = AsyncMock()
        mock_client.get_firewall_rules = AsyncMock(
            return_value=[
                {
                    "_id": "rule1",
                    "name": "Block WAN",
                    "ruleset": "WAN_IN",
                    "action": "drop",
                    "enabled": True,
                }
            ]
        )
        mock_client.get_firewall_policies = AsyncMock(
            return_value=[
                {
                    "_id": "policy1",
                    "name": "Block Guest to LAN",
                    "action": "BLOCK",
                    "enabled": False,
                    "predefined": False,
                }
            ]
        )
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool("get_firewall_rules", {})

        assert len(result) == 1
        assert "Block WAN" in result[0].text
        assert "Active" in result[0].text
        assert "Block Guest to LAN" in result[0].text
        assert "Inactive" in result[0].text

    @pytest.mark.asyncio
    async def test_call_enable_firewall_rule(self) -> None:
        """Test calling enable_firewall_rule tool."""
        mock_client = AsyncMock()
        mock_client.set_firewall_rule_enabled = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool("enable_firewall_rule", {"rule_id": "rule1"})

        assert len(result) == 1
        assert "enabled" in result[0].text
        mock_client.set_firewall_rule_enabled.assert_called_once_with("rule1", True)

    @pytest.mark.asyncio
    async def test_call_disable_firewall_rule(self) -> None:
        """Test calling disable_firewall_rule tool."""
        mock_client = AsyncMock()
        mock_client.set_firewall_rule_enabled = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool("disable_firewall_rule", {"rule_id": "rule1"})

        assert len(result) == 1
        assert "disabled" in result[0].text
        mock_client.set_firewall_rule_enabled.assert_called_once_with("rule1", False)

    @pytest.mark.asyncio
    async def test_call_create_firewall_rule(self) -> None:
        """Test calling create_firewall_rule tool."""
        mock_client = AsyncMock()
        mock_client.create_firewall_rule = AsyncMock(
            return_value={"_id": "rule1", "name": "Block WAN"}
        )
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool(
                "create_firewall_rule",
                {"rule": {"name": "Block WAN", "ruleset": "WAN_IN"}},
            )

        assert len(result) == 1
        assert "Block WAN" in result[0].text
        mock_client.create_firewall_rule.assert_called_once_with(
            {"name": "Block WAN", "ruleset": "WAN_IN"}
        )

    @pytest.mark.asyncio
    async def test_call_delete_firewall_rule(self) -> None:
        """Test calling delete_firewall_rule tool."""
        mock_client = AsyncMock()
        mock_client.delete_firewall_rule = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool("delete_firewall_rule", {"rule_id": "rule1"})

        assert len(result) == 1
        assert "deleted" in result[0].text
        mock_client.delete_firewall_rule.assert_called_once_with("rule1")

    @pytest.mark.asyncio
    async def test_call_enable_firewall_policy(self) -> None:
        """Test calling enable_firewall_policy tool."""
        mock_client = AsyncMock()
        mock_client.set_firewall_policy_enabled = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool("enable_firewall_policy", {"policy_id": "policy1"})

        assert len(result) == 1
        assert "enabled" in result[0].text
        mock_client.set_firewall_policy_enabled.assert_called_once_with("policy1", True)

    @pytest.mark.asyncio
    async def test_call_disable_firewall_policy(self) -> None:
        """Test calling disable_firewall_policy tool."""
        mock_client = AsyncMock()
        mock_client.set_firewall_policy_enabled = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool(
                "disable_firewall_policy", {"policy_id": "policy1"}
            )

        assert len(result) == 1
        assert "disabled" in result[0].text
        mock_client.set_firewall_policy_enabled.assert_called_once_with(
            "policy1", False
        )

    @pytest.mark.asyncio
    async def test_call_create_firewall_policy(self) -> None:
        """Test calling create_firewall_policy tool."""
        mock_client = AsyncMock()
        mock_client.create_firewall_policy = AsyncMock(
            return_value={"_id": "policy1", "name": "Block Guest to LAN"}
        )
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool(
                "create_firewall_policy",
                {"policy": {"name": "Block Guest to LAN", "action": "BLOCK"}},
            )

        assert len(result) == 1
        assert "Block Guest to LAN" in result[0].text
        mock_client.create_firewall_policy.assert_called_once_with(
            {"name": "Block Guest to LAN", "action": "BLOCK"}
        )

    @pytest.mark.asyncio
    async def test_call_batch_update_firewall_policies(self) -> None:
        """Test calling batch_update_firewall_policies tool."""
        mock_client = AsyncMock()
        mock_client.batch_update_firewall_policies = AsyncMock()
        policies = [{"_id": "policy1", "enabled": False}]
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool(
                "batch_update_firewall_policies", {"policies": policies}
            )

        assert len(result) == 1
        assert "Updated 1" in result[0].text
        mock_client.batch_update_firewall_policies.assert_called_once_with(policies)

    @pytest.mark.asyncio
    async def test_call_batch_delete_firewall_policies(self) -> None:
        """Test calling batch_delete_firewall_policies tool."""
        mock_client = AsyncMock()
        mock_client.batch_delete_firewall_policies = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool(
                "batch_delete_firewall_policies", {"policy_ids": ["policy1"]}
            )

        assert len(result) == 1
        assert "Deleted 1" in result[0].text
        mock_client.batch_delete_firewall_policies.assert_called_once_with(["policy1"])


class TestClientLifecycle:
    """Tests for the shared client's connect-once/reuse/close behavior."""

    def teardown_method(self) -> None:
        """Ensure the module-level singleton doesn't leak into other tests."""
        server_module._client = None

    @pytest.mark.asyncio
    async def test_get_client_reuses_connection(self) -> None:
        """Test that repeated _get_client() calls connect only once."""
        with patch("unifi_mcp.server.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_client_class.return_value.connect = AsyncMock(
                return_value=mock_instance
            )

            first = await server_module._get_client()
            second = await server_module._get_client()

            assert first is second
            mock_client_class.return_value.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_client_resets_singleton(self) -> None:
        """Test that _close_client() closes the connection and clears state."""
        with patch("unifi_mcp.server.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_client_class.return_value.connect = AsyncMock(
                return_value=mock_instance
            )

            await server_module._get_client()
            await server_module._close_client()

            mock_instance.close.assert_called_once()
            assert server_module._client is None


class TestFormatters:
    """Tests for formatting functions."""

    def test_format_bytes_bytes(self) -> None:
        """Test formatting bytes."""
        assert format_bytes(500) == "500.0 B"

    def test_format_bytes_kilobytes(self) -> None:
        """Test formatting kilobytes."""
        assert format_bytes(1536) == "1.5 KB"

    def test_format_bytes_megabytes(self) -> None:
        """Test formatting megabytes."""
        assert format_bytes(1572864) == "1.5 MB"

    def test_format_bytes_gigabytes(self) -> None:
        """Test formatting gigabytes."""
        assert format_bytes(1610612736) == "1.5 GB"

    def test_format_devices_empty(self) -> None:
        """Test formatting empty device list."""
        result = format_devices([])
        assert result == "No devices found."

    def test_format_devices_with_data(self) -> None:
        """Test formatting device list."""
        devices = [
            {
                "name": "AP1",
                "mac": "aa:bb:cc:dd:ee:ff",
                "model": "UAP-AC-Pro",
                "type": "uap",
                "state": 1,
                "ip": "192.168.1.10",
                "version": "6.0.0",
            }
        ]
        result = format_devices(devices)
        assert "AP1" in result
        assert "Online" in result
        assert "192.168.1.10" in result

    def test_format_clients_empty(self) -> None:
        """Test formatting empty client list."""
        result = format_clients([])
        assert result == "No clients found."

    def test_format_clients_with_data(self) -> None:
        """Test formatting client list."""
        clients = [
            {
                "hostname": "laptop",
                "mac": "11:22:33:44:55:66",
                "ip": "192.168.1.50",
                "is_wired": True,
                "tx_bytes": 1024,
                "rx_bytes": 2048,
            }
        ]
        result = format_clients(clients)
        assert "laptop" in result
        assert "Wired" in result
        assert "192.168.1.50" in result

    def test_format_sites_empty(self) -> None:
        """Test formatting empty site list."""
        result = format_sites([])
        assert result == "No sites found."

    def test_format_sites_with_data(self) -> None:
        """Test formatting site list."""
        sites = [{"name": "default", "desc": "Default Site", "_id": "abc123"}]
        result = format_sites(sites)
        assert "Default Site" in result
        assert "default" in result

    def test_format_health_empty(self) -> None:
        """Test formatting empty health data."""
        result = format_health([])
        assert result == "No health data available."

    def test_format_health_with_data(self) -> None:
        """Test formatting health data."""
        health = [
            {"subsystem": "wan", "status": "ok", "gw_mac": "aa:bb:cc:dd:ee:ff"},
            {"subsystem": "wlan", "status": "ok", "num_ap": 3, "num_user": 10},
        ]
        result = format_health(health)
        assert "WAN" in result
        assert "WLAN" in result
        assert "ok" in result
        assert "Access Points: 3" in result

    def test_format_networks_empty(self) -> None:
        """Test formatting empty network list."""
        result = format_networks([])
        assert result == "No networks configured."

    def test_format_networks_with_data(self) -> None:
        """Test formatting network list."""
        networks = [
            {
                "name": "LAN",
                "purpose": "corporate",
                "vlan": 1,
                "ip_subnet": "192.168.1.0/24",
                "enabled": True,
            }
        ]
        result = format_networks(networks)
        assert "LAN" in result
        assert "corporate" in result
        assert "192.168.1.0/24" in result

    def test_format_firewall_rules_empty(self) -> None:
        """Test formatting empty firewall rule/policy lists."""
        result = format_firewall_rules([], [])
        assert result == "No firewall rules or policies configured."

    def test_format_firewall_rules_with_data(self) -> None:
        """Test formatting legacy firewall rules."""
        rules = [
            {
                "_id": "rule1",
                "name": "Block WAN",
                "ruleset": "WAN_IN",
                "action": "drop",
                "enabled": True,
            },
            {
                "_id": "rule2",
                "name": "Allow LAN",
                "ruleset": "LAN_IN",
                "action": "accept",
                "enabled": False,
            },
        ]
        result = format_firewall_rules(rules, [])
        assert "Block WAN" in result
        assert "WAN_IN" in result
        assert "DROP" in result
        assert "Active" in result
        assert "Allow LAN" in result
        assert "Inactive" in result

    def test_format_firewall_rules_with_policies(self) -> None:
        """Test formatting zone-based firewall policies."""
        policies = [
            {
                "_id": "policy1",
                "name": "Block Guest to LAN",
                "action": "BLOCK",
                "enabled": True,
                "predefined": False,
            },
            {
                "_id": "policy2",
                "name": "Allow Established/Related",
                "action": "ALLOW",
                "enabled": True,
                "predefined": True,
            },
        ]
        result = format_firewall_rules([], policies)
        assert "Block Guest to LAN" in result
        assert "Zone Policy" in result
        assert "Allow Established/Related" in result
        assert "Yes" in result
        assert "No" in result

    def test_format_uptime_seconds(self) -> None:
        """Test formatting uptime in seconds."""
        assert format_uptime(45) == "45s"

    def test_format_uptime_minutes(self) -> None:
        """Test formatting uptime in minutes."""
        assert format_uptime(125) == "2m 5s"

    def test_format_uptime_hours(self) -> None:
        """Test formatting uptime in hours."""
        assert format_uptime(3665) == "1h 1m 5s"

    def test_format_uptime_days(self) -> None:
        """Test formatting uptime in days."""
        assert format_uptime(90065) == "1d 1h 1m 5s"

    def test_format_device_activity_no_device(self) -> None:
        """Test formatting device activity when device not found."""
        activity = {
            "device": None,
            "clients": [],
            "client_count": 0,
            "total_tx_bytes": 0,
            "total_rx_bytes": 0,
        }
        result = format_device_activity(activity)
        assert "Device: Not found" in result
        assert "Connected Clients: 0" in result

    def test_format_device_activity_with_clients(self) -> None:
        """Test formatting device activity with connected clients."""
        activity = {
            "device": {
                "name": "Office AP",
                "mac": "aa:bb:cc:dd:ee:ff",
                "model": "UAP-AC-Pro",
                "type": "uap",
                "state": 1,
            },
            "clients": [
                {
                    "hostname": "laptop",
                    "mac": "11:22:33:44:55:66",
                    "ip": "192.168.1.50",
                    "is_wired": False,
                    "essid": "MyNetwork",
                    "tx_bytes": 1024,
                    "rx_bytes": 2048,
                    "signal": -65,
                    "uptime": 3600,
                }
            ],
            "client_count": 1,
            "total_tx_bytes": 1024,
            "total_rx_bytes": 2048,
        }
        result = format_device_activity(activity)
        assert "Office AP" in result
        assert "Connected Clients: 1" in result
        assert "laptop" in result
        assert "Signal: -65 dBm" in result
        assert "1h" in result
