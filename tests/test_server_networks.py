"""Tests for network configuration CRUD tools."""

from unittest.mock import AsyncMock, patch

import pytest

from unifi_mcp.server import call_tool, format_networks


class TestCallToolNetworks:
    """Tests for network-related call_tool dispatch."""

    @pytest.mark.asyncio
    async def test_call_create_network(self) -> None:
        """Test calling create_network tool."""
        mock_client = AsyncMock()
        mock_client.create_network = AsyncMock(
            return_value={"_id": "net1", "name": "IoT"}
        )
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool(
                "create_network", {"network": {"name": "IoT", "vlan": 20}}
            )

        assert len(result) == 1
        assert "IoT" in result[0].text
        mock_client.create_network.assert_called_once_with({"name": "IoT", "vlan": 20})

    @pytest.mark.asyncio
    async def test_call_update_network(self) -> None:
        """Test calling update_network tool."""
        mock_client = AsyncMock()
        mock_client.update_network = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool(
                "update_network",
                {"network_id": "net1", "network": {"name": "IoT", "vlan": 21}},
            )

        assert len(result) == 1
        assert "updated" in result[0].text
        mock_client.update_network.assert_called_once_with(
            "net1", {"name": "IoT", "vlan": 21}
        )

    @pytest.mark.asyncio
    async def test_call_delete_network(self) -> None:
        """Test calling delete_network tool."""
        mock_client = AsyncMock()
        mock_client.delete_network = AsyncMock()
        with patch("unifi_mcp.server._get_client", AsyncMock(return_value=mock_client)):
            result = await call_tool("delete_network", {"network_id": "net1"})

        assert len(result) == 1
        assert "deleted" in result[0].text
        mock_client.delete_network.assert_called_once_with("net1")


class TestFormatNetworks:
    """Tests for format_networks."""

    def test_format_networks_empty(self) -> None:
        """Test formatting empty network list."""
        result = format_networks([])
        assert result == "No networks configured."

    def test_format_networks_with_data(self) -> None:
        """Test formatting network list."""
        networks = [
            {
                "name": "LAN",
                "purpose": "corporate",
                "vlan": 1,
                "ip_subnet": "192.168.1.0/24",
                "enabled": True,
            }
        ]
        result = format_networks(networks)
        assert "LAN" in result
        assert "corporate" in result
        assert "192.168.1.0/24" in result
