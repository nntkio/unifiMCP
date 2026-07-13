"""Tests for UniFi client object-oriented network configuration CRUD."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.unifi_client._oo_network_configs import _OONetworkConfigMixin


class TestOONetworkConfigMixin:
    """Tests for object-oriented network configuration methods."""

    @pytest.fixture
    def mock_client(self) -> _OONetworkConfigMixin:
        """Create a mixin instance with a mocked `_request_v2` for testing."""
        client = _OONetworkConfigMixin()
        client._request_v2 = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_get_oo_network_configs(
        self, mock_client: _OONetworkConfigMixin
    ) -> None:
        """Test get_oo_network_configs uses the plural list endpoint."""
        mock_client._request_v2.return_value = [{"_id": "cfg1", "name": "IoT"}]

        result = await mock_client.get_oo_network_configs()

        assert result == [{"_id": "cfg1", "name": "IoT"}]
        mock_client._request_v2.assert_called_once_with(
            "GET", "/object-oriented-network-configs"
        )

    @pytest.mark.asyncio
    async def test_create_oo_network_config(
        self, mock_client: _OONetworkConfigMixin
    ) -> None:
        """Test create_oo_network_config uses the singular write endpoint."""
        mock_client._request_v2.return_value = [{"_id": "cfg1", "name": "IoT"}]

        result = await mock_client.create_oo_network_config({"name": "IoT", "vlan": 20})

        assert result == {"_id": "cfg1", "name": "IoT"}
        mock_client._request_v2.assert_called_once_with(
            "POST",
            "/object-oriented-network-config",
            json={"name": "IoT", "vlan": 20},
        )

    @pytest.mark.asyncio
    async def test_update_oo_network_config(
        self, mock_client: _OONetworkConfigMixin
    ) -> None:
        """Test update_oo_network_config uses the singular write endpoint."""
        mock_client._request_v2.return_value = []

        result = await mock_client.update_oo_network_config(
            "cfg1", {"_id": "cfg1", "name": "IoT", "vlan": 21}
        )

        assert result is True
        mock_client._request_v2.assert_called_once_with(
            "PUT",
            "/object-oriented-network-config/cfg1",
            json={"_id": "cfg1", "name": "IoT", "vlan": 21},
        )

    @pytest.mark.asyncio
    async def test_delete_oo_network_config(
        self, mock_client: _OONetworkConfigMixin
    ) -> None:
        """Test delete_oo_network_config uses the singular write endpoint."""
        mock_client._request_v2.return_value = []

        result = await mock_client.delete_oo_network_config("cfg1")

        assert result is True
        mock_client._request_v2.assert_called_once_with(
            "DELETE", "/object-oriented-network-config/cfg1"
        )
