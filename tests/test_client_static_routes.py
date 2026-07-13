"""Tests for UniFi client static route CRUD."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.unifi_client._static_routes import _StaticRouteMixin


class TestUniFiClientStaticRoutes:
    """Tests for static route methods."""

    @pytest.fixture
    def mock_client(self) -> _StaticRouteMixin:
        """Create a mock client for testing."""
        client = _StaticRouteMixin()
        client._request = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_get_static_routes(self, mock_client: _StaticRouteMixin) -> None:
        """Test get_static_routes method."""
        mock_client._request.return_value = [{"_id": "route1", "name": "VPN"}]

        result = await mock_client.get_static_routes()

        assert result == [{"_id": "route1", "name": "VPN"}]
        mock_client._request.assert_called_once_with(
            "GET", "/api/s/{site}/rest/routing"
        )

    @pytest.mark.asyncio
    async def test_create_static_route(self, mock_client: _StaticRouteMixin) -> None:
        """Test create_static_route method."""
        mock_client._request.return_value = [{"_id": "route1", "name": "VPN"}]

        result = await mock_client.create_static_route(
            {"name": "VPN", "static-route_network": "10.0.0.0/24"}
        )

        assert result == {"_id": "route1", "name": "VPN"}
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/rest/routing",
            json={"name": "VPN", "static-route_network": "10.0.0.0/24"},
        )

    @pytest.mark.asyncio
    async def test_create_static_route_empty_response(
        self, mock_client: _StaticRouteMixin
    ) -> None:
        """Test create_static_route method with an empty response."""
        mock_client._request.return_value = []

        result = await mock_client.create_static_route({"name": "VPN"})

        assert result == {}

    @pytest.mark.asyncio
    async def test_update_static_route(self, mock_client: _StaticRouteMixin) -> None:
        """Test update_static_route method."""
        mock_client._request.return_value = []

        result = await mock_client.update_static_route(
            "route1", {"_id": "route1", "name": "VPN", "enabled": False}
        )

        assert result is True
        mock_client._request.assert_called_once_with(
            "PUT",
            "/api/s/{site}/rest/routing/route1",
            json={"_id": "route1", "name": "VPN", "enabled": False},
        )

    @pytest.mark.asyncio
    async def test_delete_static_route(self, mock_client: _StaticRouteMixin) -> None:
        """Test delete_static_route method."""
        mock_client._request.return_value = []

        result = await mock_client.delete_static_route("route1")

        assert result is True
        mock_client._request.assert_called_once_with(
            "DELETE", "/api/s/{site}/rest/routing/route1"
        )
