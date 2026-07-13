"""Tests for UniFi client network configuration CRUD."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.unifi_client import UniFiClient


class TestUniFiClientNetworks:
    """Tests for network configuration methods."""

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
    async def test_create_network(self, mock_client: UniFiClient) -> None:
        """Test create_network method."""
        mock_client._request.return_value = [{"_id": "net1", "name": "IoT"}]

        result = await mock_client.create_network({"name": "IoT", "vlan": 20})

        assert result == {"_id": "net1", "name": "IoT"}
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/rest/networkconf",
            json={"name": "IoT", "vlan": 20},
        )

    @pytest.mark.asyncio
    async def test_update_network(self, mock_client: UniFiClient) -> None:
        """Test update_network method."""
        mock_client._request.return_value = []

        result = await mock_client.update_network(
            "net1", {"_id": "net1", "name": "IoT", "vlan": 21}
        )

        assert result is True
        mock_client._request.assert_called_once_with(
            "PUT",
            "/api/s/{site}/rest/networkconf/net1",
            json={"_id": "net1", "name": "IoT", "vlan": 21},
        )

    @pytest.mark.asyncio
    async def test_delete_network(self, mock_client: UniFiClient) -> None:
        """Test delete_network method."""
        mock_client._request.return_value = []

        result = await mock_client.delete_network("net1")

        assert result is True
        mock_client._request.assert_called_once_with(
            "DELETE", "/api/s/{site}/rest/networkconf/net1"
        )
