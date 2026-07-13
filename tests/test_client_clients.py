"""Tests for UniFi client connected-client inventory and `cmd/stamgr` commands."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.unifi_client import UniFiClient


class TestUniFiClientClients:
    """Tests for client management methods."""

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
    async def test_get_clients(self, mock_client: UniFiClient) -> None:
        """Test get_clients method."""
        mock_client._request.return_value = [{"hostname": "laptop"}]

        result = await mock_client.get_clients()

        assert len(result) == 1
        mock_client._request.assert_called_once_with("GET", "/api/s/{site}/stat/sta")

    @pytest.mark.asyncio
    async def test_block_client(self, mock_client: UniFiClient) -> None:
        """Test block_client method."""
        mock_client._request.return_value = []

        result = await mock_client.block_client("AA:BB:CC:DD:EE:FF")

        assert result is True
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/cmd/stamgr",
            json={"cmd": "block-sta", "mac": "aa:bb:cc:dd:ee:ff"},
        )

    @pytest.mark.asyncio
    async def test_forget_client(self, mock_client: UniFiClient) -> None:
        """Test forget_client method."""
        mock_client._request.return_value = []

        result = await mock_client.forget_client("AA:BB:CC:DD:EE:FF")

        assert result is True
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/cmd/stamgr",
            json={"cmd": "forget-sta", "macs": ["aa:bb:cc:dd:ee:ff"]},
        )

    @pytest.mark.asyncio
    async def test_authorize_guest(self, mock_client: UniFiClient) -> None:
        """Test authorize_guest method without a session length."""
        mock_client._request.return_value = []

        result = await mock_client.authorize_guest("AA:BB:CC:DD:EE:FF")

        assert result is True
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/cmd/stamgr",
            json={"cmd": "authorize-guest", "mac": "aa:bb:cc:dd:ee:ff"},
        )

    @pytest.mark.asyncio
    async def test_authorize_guest_with_minutes(self, mock_client: UniFiClient) -> None:
        """Test authorize_guest method with a session length."""
        mock_client._request.return_value = []

        result = await mock_client.authorize_guest("AA:BB:CC:DD:EE:FF", minutes=60)

        assert result is True
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/cmd/stamgr",
            json={
                "cmd": "authorize-guest",
                "mac": "aa:bb:cc:dd:ee:ff",
                "minutes": 60,
            },
        )

    @pytest.mark.asyncio
    async def test_unauthorize_guest(self, mock_client: UniFiClient) -> None:
        """Test unauthorize_guest method."""
        mock_client._request.return_value = []

        result = await mock_client.unauthorize_guest("AA:BB:CC:DD:EE:FF")

        assert result is True
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/cmd/stamgr",
            json={"cmd": "unauthorize-guest", "mac": "aa:bb:cc:dd:ee:ff"},
        )
