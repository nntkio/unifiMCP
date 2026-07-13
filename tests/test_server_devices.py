"""Tests for device inventory, cmd/devmgr, and device activity tools."""

from unittest.mock import AsyncMock, patch

import pytest

from unifi_mcp.server import call_tool, format_device_activity, format_devices


class TestCallToolDevices:
    """Tests for device-related call_tool dispatch."""

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


class TestFormatDevices:
    """Tests for format_devices and format_device_activity."""

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
