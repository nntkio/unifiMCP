"""Tests for UniFi client site inventory and health methods."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.unifi_client import UniFiClient


class TestUniFiClientSites:
    """Tests for site management methods."""

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
    async def test_get_site_health(self, mock_client: UniFiClient) -> None:
        """Test get_site_health method."""
        mock_client._request.return_value = [
            {"subsystem": "wan", "status": "ok"},
            {"subsystem": "wlan", "status": "ok"},
        ]

        result = await mock_client.get_site_health()

        assert len(result) == 2
        mock_client._request.assert_called_once_with("GET", "/api/s/{site}/stat/health")
