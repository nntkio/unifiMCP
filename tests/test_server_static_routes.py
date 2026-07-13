"""Tests for static route CRUD tools."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.server._static_routes import (
    STATIC_ROUTE_TOOLS,
    _handle_create_static_route,
    _handle_delete_static_route,
    _handle_get_static_routes,
    _handle_update_static_route,
    format_static_routes,
)


class TestStaticRouteHandlers:
    """Tests for static route tool handlers."""

    @pytest.mark.asyncio
    async def test_handle_get_static_routes(self) -> None:
        """Test _handle_get_static_routes."""
        mock_client = AsyncMock()
        mock_client.get_static_routes = AsyncMock(
            return_value=[{"name": "VPN", "static-route_network": "10.0.0.0/24"}]
        )

        result = await _handle_get_static_routes(mock_client, {})

        assert "VPN" in result
        mock_client.get_static_routes.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_handle_create_static_route(self) -> None:
        """Test _handle_create_static_route."""
        mock_client = AsyncMock()
        mock_client.create_static_route = AsyncMock(
            return_value={"_id": "route1", "name": "VPN"}
        )

        result = await _handle_create_static_route(
            mock_client,
            {"route": {"name": "VPN", "static-route_network": "10.0.0.0/24"}},
        )

        assert "VPN" in result
        assert "created" in result
        mock_client.create_static_route.assert_called_once_with(
            {"name": "VPN", "static-route_network": "10.0.0.0/24"}
        )

    @pytest.mark.asyncio
    async def test_handle_update_static_route(self) -> None:
        """Test _handle_update_static_route."""
        mock_client = AsyncMock()
        mock_client.update_static_route = AsyncMock()

        result = await _handle_update_static_route(
            mock_client,
            {"route_id": "route1", "route": {"name": "VPN", "enabled": False}},
        )

        assert "route1" in result
        assert "updated" in result
        mock_client.update_static_route.assert_called_once_with(
            "route1", {"name": "VPN", "enabled": False}
        )

    @pytest.mark.asyncio
    async def test_handle_delete_static_route(self) -> None:
        """Test _handle_delete_static_route."""
        mock_client = AsyncMock()
        mock_client.delete_static_route = AsyncMock()

        result = await _handle_delete_static_route(mock_client, {"route_id": "route1"})

        assert "route1" in result
        assert "deleted" in result
        mock_client.delete_static_route.assert_called_once_with("route1")


class TestFormatStaticRoutes:
    """Tests for format_static_routes."""

    def test_format_static_routes_empty(self) -> None:
        """Test formatting empty static route list."""
        result = format_static_routes([])
        assert result == "No static routes configured."

    def test_format_static_routes_with_data(self) -> None:
        """Test formatting static route list."""
        routes = [
            {
                "name": "VPN",
                "static-route_network": "10.0.0.0/24",
                "static-route_nexthop": "192.168.1.1",
                "enabled": True,
            }
        ]
        result = format_static_routes(routes)
        assert "VPN" in result
        assert "10.0.0.0/24" in result
        assert "192.168.1.1" in result
        assert "Enabled" in result


class TestStaticRouteTools:
    """Tests for STATIC_ROUTE_TOOLS."""

    def test_tool_names(self) -> None:
        """Test that all expected static route tools are registered."""
        names = {tool.name for tool in STATIC_ROUTE_TOOLS}
        assert names == {
            "get_static_routes",
            "create_static_route",
            "update_static_route",
            "delete_static_route",
        }
