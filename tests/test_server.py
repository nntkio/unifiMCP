"""Tests for MCP server."""

from unittest.mock import AsyncMock, patch

import pytest

from unifi_mcp.server import (
    call_tool,
    format_bytes,
    format_clients,
    format_device_activity,
    format_devices,
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
        assert "get_clients" in tool_names
        assert "block_client" in tool_names
        assert "unblock_client" in tool_names
        assert "disconnect_client" in tool_names
        assert "get_sites" in tool_names
        assert "get_site_health" in tool_names
        assert "get_networks" in tool_names
        assert "get_device_activity" in tool_names

    @pytest.mark.asyncio
    async def test_tools_have_descriptions(self) -> None:
        """Test that all tools have descriptions."""
        tools = await list_tools()

        for tool in tools:
            assert tool.description
            assert len(tool.description) > 10


class TestCallTool:
    """Tests for call_tool function."""

    @pytest.mark.asyncio
    async def test_call_unknown_tool(self) -> None:
        """Test calling an unknown tool."""
        with patch("unifi_mcp.server.UniFiClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_class.return_value.__aexit__ = AsyncMock()

            result = await call_tool("unknown_tool", {})

            assert len(result) == 1
            assert "Unknown tool" in result[0].text

    @pytest.mark.asyncio
    async def test_call_get_devices(self) -> None:
        """Test calling get_devices tool."""
        with patch("unifi_mcp.server.UniFiClient") as mock_client_class:
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
            mock_client_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_class.return_value.__aexit__ = AsyncMock()

            result = await call_tool("get_devices", {})

            assert len(result) == 1
            assert "Living Room AP" in result[0].text
            assert "aa:bb:cc:dd:ee:ff" in result[0].text

    @pytest.mark.asyncio
    async def test_call_get_clients(self) -> None:
        """Test calling get_clients tool."""
        with patch("unifi_mcp.server.UniFiClient") as mock_client_class:
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
            mock_client_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_class.return_value.__aexit__ = AsyncMock()

            result = await call_tool("get_clients", {})

            assert len(result) == 1
            assert "my-laptop" in result[0].text
            assert "192.168.1.100" in result[0].text

    @pytest.mark.asyncio
    async def test_call_block_client(self) -> None:
        """Test calling block_client tool."""
        with patch("unifi_mcp.server.UniFiClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.block_client = AsyncMock()
            mock_client_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_class.return_value.__aexit__ = AsyncMock()

            result = await call_tool("block_client", {"mac": "aa:bb:cc:dd:ee:ff"})

            assert len(result) == 1
            assert "blocked" in result[0].text
            mock_client.block_client.assert_called_once_with("aa:bb:cc:dd:ee:ff")

    @pytest.mark.asyncio
    async def test_call_get_device_activity(self) -> None:
        """Test calling get_device_activity tool."""
        with patch("unifi_mcp.server.UniFiClient") as mock_client_class:
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
            mock_client_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_class.return_value.__aexit__ = AsyncMock()

            result = await call_tool(
                "get_device_activity", {"mac": "aa:bb:cc:dd:ee:ff"}
            )

            assert len(result) == 1
            assert "Living Room AP" in result[0].text
            assert "laptop" in result[0].text
            assert "Connected Clients: 1" in result[0].text


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
