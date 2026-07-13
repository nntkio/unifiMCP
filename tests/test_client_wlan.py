"""Tests for UniFi client WLAN configuration CRUD."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.unifi_client._wlan import _WlanMixin


class TestUniFiClientWlan:
    """Tests for WLAN configuration methods."""

    @pytest.fixture
    def mock_client(self) -> _WlanMixin:
        """Create a mock client for testing."""
        client = _WlanMixin()
        client._request = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_get_wlans(self, mock_client: _WlanMixin) -> None:
        """Test get_wlans method."""
        mock_client._request.return_value = [{"_id": "wlan1", "name": "Home"}]

        result = await mock_client.get_wlans()

        assert result == [{"_id": "wlan1", "name": "Home"}]
        mock_client._request.assert_called_once_with(
            "GET", "/api/s/{site}/rest/wlanconf"
        )

    @pytest.mark.asyncio
    async def test_create_wlan(self, mock_client: _WlanMixin) -> None:
        """Test create_wlan method."""
        mock_client._request.return_value = [{"_id": "wlan1", "name": "Home"}]

        result = await mock_client.create_wlan(
            {"name": "Home", "security": "wpapsk", "x_passphrase": "supersecret"}
        )

        assert result == {"_id": "wlan1", "name": "Home"}
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/rest/wlanconf",
            json={"name": "Home", "security": "wpapsk", "x_passphrase": "supersecret"},
        )

    @pytest.mark.asyncio
    async def test_update_wlan(self, mock_client: _WlanMixin) -> None:
        """Test update_wlan method."""
        mock_client._request.return_value = []

        result = await mock_client.update_wlan(
            "wlan1", {"_id": "wlan1", "name": "Home", "vlan": 10}
        )

        assert result is True
        mock_client._request.assert_called_once_with(
            "PUT",
            "/api/s/{site}/rest/wlanconf/wlan1",
            json={"_id": "wlan1", "name": "Home", "vlan": 10},
        )

    @pytest.mark.asyncio
    async def test_delete_wlan(self, mock_client: _WlanMixin) -> None:
        """Test delete_wlan method."""
        mock_client._request.return_value = []

        result = await mock_client.delete_wlan("wlan1")

        assert result is True
        mock_client._request.assert_called_once_with(
            "DELETE", "/api/s/{site}/rest/wlanconf/wlan1"
        )
