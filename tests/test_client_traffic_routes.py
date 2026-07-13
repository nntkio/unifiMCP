"""Tests for UniFi client traffic route CRUD."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.unifi_client._traffic_routes import _TrafficRouteMixin


class TestUniFiClientTrafficRoutes:
    """Tests for traffic route methods."""

    @pytest.fixture
    def mock_client(self) -> _TrafficRouteMixin:
        """Create a mock client for testing."""
        client = _TrafficRouteMixin()
        client._request_v2 = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_get_traffic_routes(self, mock_client: _TrafficRouteMixin) -> None:
        """Test get_traffic_routes method."""
        mock_client._request_v2.return_value = [
            {"_id": "route1", "description": "VPN Route"}
        ]

        result = await mock_client.get_traffic_routes()

        assert result == [{"_id": "route1", "description": "VPN Route"}]
        mock_client._request_v2.assert_called_once_with("GET", "/trafficroutes")

    @pytest.mark.asyncio
    async def test_create_traffic_route(self, mock_client: _TrafficRouteMixin) -> None:
        """Test create_traffic_route method."""
        mock_client._request_v2.return_value = [
            {"_id": "route1", "description": "VPN Route"}
        ]

        result = await mock_client.create_traffic_route(
            {"description": "VPN Route", "enabled": True}
        )

        assert result == {"_id": "route1", "description": "VPN Route"}
        mock_client._request_v2.assert_called_once_with(
            "POST",
            "/trafficroutes",
            json={"description": "VPN Route", "enabled": True},
        )

    @pytest.mark.asyncio
    async def test_update_traffic_route(self, mock_client: _TrafficRouteMixin) -> None:
        """Test update_traffic_route method."""
        mock_client._request_v2.return_value = []

        result = await mock_client.update_traffic_route(
            "route1", {"_id": "route1", "description": "VPN Route", "enabled": False}
        )

        assert result is True
        mock_client._request_v2.assert_called_once_with(
            "PUT",
            "/trafficroutes/route1",
            json={"_id": "route1", "description": "VPN Route", "enabled": False},
        )

    @pytest.mark.asyncio
    async def test_delete_traffic_route(self, mock_client: _TrafficRouteMixin) -> None:
        """Test delete_traffic_route method."""
        mock_client._request_v2.return_value = []

        result = await mock_client.delete_traffic_route("route1")

        assert result is True
        mock_client._request_v2.assert_called_once_with(
            "DELETE", "/trafficroutes/route1"
        )
