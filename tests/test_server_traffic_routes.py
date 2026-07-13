"""Tests for traffic route CRUD tools."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.server._traffic_routes import (
    TRAFFIC_ROUTE_TOOLS,
    _handle_create_traffic_route,
    _handle_delete_traffic_route,
    _handle_get_traffic_routes,
    _handle_update_traffic_route,
    format_traffic_routes,
)


class TestTrafficRouteHandlers:
    """Tests for traffic route handler functions."""

    @pytest.mark.asyncio
    async def test_handle_get_traffic_routes(self) -> None:
        """Test _handle_get_traffic_routes."""
        mock_client = AsyncMock()
        mock_client.get_traffic_routes = AsyncMock(
            return_value=[
                {"_id": "route1", "description": "VPN Route", "enabled": True}
            ]
        )

        result = await _handle_get_traffic_routes(mock_client, {})

        assert "VPN Route" in result
        mock_client.get_traffic_routes.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_handle_create_traffic_route(self) -> None:
        """Test _handle_create_traffic_route."""
        mock_client = AsyncMock()
        mock_client.create_traffic_route = AsyncMock(
            return_value={"_id": "route1", "description": "VPN Route"}
        )

        result = await _handle_create_traffic_route(
            mock_client, {"route": {"description": "VPN Route", "enabled": True}}
        )

        assert "VPN Route" in result
        mock_client.create_traffic_route.assert_called_once_with(
            {"description": "VPN Route", "enabled": True}
        )

    @pytest.mark.asyncio
    async def test_handle_update_traffic_route(self) -> None:
        """Test _handle_update_traffic_route."""
        mock_client = AsyncMock()
        mock_client.update_traffic_route = AsyncMock()

        result = await _handle_update_traffic_route(
            mock_client,
            {"route_id": "route1", "route": {"description": "VPN Route"}},
        )

        assert "updated" in result
        mock_client.update_traffic_route.assert_called_once_with(
            "route1", {"description": "VPN Route"}
        )

    @pytest.mark.asyncio
    async def test_handle_delete_traffic_route(self) -> None:
        """Test _handle_delete_traffic_route."""
        mock_client = AsyncMock()
        mock_client.delete_traffic_route = AsyncMock()

        result = await _handle_delete_traffic_route(mock_client, {"route_id": "route1"})

        assert "deleted" in result
        mock_client.delete_traffic_route.assert_called_once_with("route1")


class TestFormatTrafficRoutes:
    """Tests for format_traffic_routes."""

    def test_format_traffic_routes_empty(self) -> None:
        """Test formatting empty traffic route list."""
        result = format_traffic_routes([])
        assert result == "No traffic routes configured."

    def test_format_traffic_routes_with_data(self) -> None:
        """Test formatting traffic route list."""
        routes = [
            {"_id": "route1", "description": "VPN Route", "enabled": True},
            {"_id": "route2", "description": "Backup WAN Route", "enabled": False},
        ]
        result = format_traffic_routes(routes)
        assert "VPN Route" in result
        assert "Backup WAN Route" in result
        assert "Enabled" in result
        assert "Disabled" in result


class TestTrafficRouteTools:
    """Tests for TRAFFIC_ROUTE_TOOLS."""

    def test_contains_expected_tool_names(self) -> None:
        """Test that all expected tools are registered."""
        names = {tool.name for tool in TRAFFIC_ROUTE_TOOLS}
        assert names == {
            "get_traffic_routes",
            "create_traffic_route",
            "update_traffic_route",
            "delete_traffic_route",
        }
