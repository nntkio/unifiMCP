"""Tests for UniFi client device inventory and `cmd/devmgr` commands."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.unifi_client import UniFiClient


class TestUniFiClientDevices:
    """Tests for device management methods."""

    @pytest.fixture
    def mock_client(self) -> UniFiClient:
        """Create a mock client for testing."""
        client = UniFiClient(
            host="https://unifi.local",
            username="admin",
            password="pass",
        )
        client._request = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_get_devices(self, mock_client: UniFiClient) -> None:
        """Test get_devices method."""
        mock_client._request.return_value = [{"name": "AP1"}, {"name": "SW1"}]

        result = await mock_client.get_devices()

        assert len(result) == 2
        mock_client._request.assert_called_once_with("GET", "/api/s/{site}/stat/device")

    @pytest.mark.asyncio
    async def test_restart_device(self, mock_client: UniFiClient) -> None:
        """Test restart_device method."""
        mock_client._request.return_value = []

        result = await mock_client.restart_device("AA:BB:CC:DD:EE:FF")

        assert result is True
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/cmd/devmgr",
            json={"cmd": "restart", "mac": "aa:bb:cc:dd:ee:ff"},
        )

    @pytest.mark.asyncio
    async def test_adopt_device(self, mock_client: UniFiClient) -> None:
        """Test adopt_device method."""
        mock_client._request.return_value = []

        result = await mock_client.adopt_device("AA:BB:CC:DD:EE:FF")

        assert result is True
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/cmd/devmgr",
            json={"cmd": "adopt", "mac": "aa:bb:cc:dd:ee:ff"},
        )

    @pytest.mark.asyncio
    async def test_force_provision_device(self, mock_client: UniFiClient) -> None:
        """Test force_provision_device method."""
        mock_client._request.return_value = []

        result = await mock_client.force_provision_device("AA:BB:CC:DD:EE:FF")

        assert result is True
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/cmd/devmgr",
            json={"cmd": "force-provision", "mac": "aa:bb:cc:dd:ee:ff"},
        )

    @pytest.mark.asyncio
    async def test_upgrade_device(self, mock_client: UniFiClient) -> None:
        """Test upgrade_device method."""
        mock_client._request.return_value = []

        result = await mock_client.upgrade_device("AA:BB:CC:DD:EE:FF")

        assert result is True
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/cmd/devmgr",
            json={"cmd": "upgrade", "mac": "aa:bb:cc:dd:ee:ff"},
        )

    @pytest.mark.asyncio
    async def test_power_cycle_port(self, mock_client: UniFiClient) -> None:
        """Test power_cycle_port method."""
        mock_client._request.return_value = []

        result = await mock_client.power_cycle_port("AA:BB:CC:DD:EE:FF", 3)

        assert result is True
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/cmd/devmgr",
            json={"cmd": "power-cycle", "mac": "aa:bb:cc:dd:ee:ff", "port_idx": 3},
        )

    @pytest.mark.asyncio
    async def test_set_device_locate(self, mock_client: UniFiClient) -> None:
        """Test set_device_locate method."""
        mock_client._request.return_value = []

        result = await mock_client.set_device_locate("AA:BB:CC:DD:EE:FF")

        assert result is True
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/cmd/devmgr",
            json={"cmd": "set-locate", "mac": "aa:bb:cc:dd:ee:ff"},
        )

    @pytest.mark.asyncio
    async def test_unset_device_locate(self, mock_client: UniFiClient) -> None:
        """Test unset_device_locate method."""
        mock_client._request.return_value = []

        result = await mock_client.unset_device_locate("AA:BB:CC:DD:EE:FF")

        assert result is True
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/cmd/devmgr",
            json={"cmd": "unset-locate", "mac": "aa:bb:cc:dd:ee:ff"},
        )
