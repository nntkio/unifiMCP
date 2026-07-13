"""Tests for object-oriented network configuration CRUD tools."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.server._oo_network_configs import (
    OO_NETWORK_CONFIG_TOOLS,
    _handle_create_oo_network_config,
    _handle_delete_oo_network_config,
    _handle_get_oo_network_configs,
    _handle_update_oo_network_config,
    format_oo_network_configs,
)


class TestOONetworkConfigHandlers:
    """Tests for object-oriented network config `_handle_*` functions."""

    @pytest.mark.asyncio
    async def test_handle_get_oo_network_configs(self) -> None:
        """Test _handle_get_oo_network_configs."""
        mock_client = AsyncMock()
        mock_client.get_oo_network_configs = AsyncMock(
            return_value=[{"_id": "cfg1", "name": "IoT"}]
        )

        result = await _handle_get_oo_network_configs(mock_client, {})

        assert "IoT" in result
        mock_client.get_oo_network_configs.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_handle_create_oo_network_config(self) -> None:
        """Test _handle_create_oo_network_config."""
        mock_client = AsyncMock()
        mock_client.create_oo_network_config = AsyncMock(
            return_value={"_id": "cfg1", "name": "IoT"}
        )

        result = await _handle_create_oo_network_config(
            mock_client, {"config": {"name": "IoT", "vlan": 20}}
        )

        assert "IoT" in result
        assert "created" in result
        mock_client.create_oo_network_config.assert_called_once_with(
            {"name": "IoT", "vlan": 20}
        )

    @pytest.mark.asyncio
    async def test_handle_update_oo_network_config(self) -> None:
        """Test _handle_update_oo_network_config."""
        mock_client = AsyncMock()
        mock_client.update_oo_network_config = AsyncMock()

        result = await _handle_update_oo_network_config(
            mock_client,
            {"config_id": "cfg1", "config": {"name": "IoT", "vlan": 21}},
        )

        assert "cfg1" in result
        assert "updated" in result
        mock_client.update_oo_network_config.assert_called_once_with(
            "cfg1", {"name": "IoT", "vlan": 21}
        )

    @pytest.mark.asyncio
    async def test_handle_delete_oo_network_config(self) -> None:
        """Test _handle_delete_oo_network_config."""
        mock_client = AsyncMock()
        mock_client.delete_oo_network_config = AsyncMock()

        result = await _handle_delete_oo_network_config(
            mock_client, {"config_id": "cfg1"}
        )

        assert "cfg1" in result
        assert "deleted" in result
        mock_client.delete_oo_network_config.assert_called_once_with("cfg1")


class TestFormatOONetworkConfigs:
    """Tests for format_oo_network_configs."""

    def test_format_oo_network_configs_empty(self) -> None:
        """Test formatting an empty config list."""
        result = format_oo_network_configs([])
        assert result == "No object-oriented network configurations configured."

    def test_format_oo_network_configs_with_data(self) -> None:
        """Test formatting a config list."""
        configs = [{"name": "IoT"}, {"name": "Guest"}]
        result = format_oo_network_configs(configs)
        assert "IoT" in result
        assert "Guest" in result
        assert "2" in result


class TestOONetworkConfigTools:
    """Tests for the OO_NETWORK_CONFIG_TOOLS registry."""

    def test_tool_names(self) -> None:
        """Test that all expected tools are present."""
        names = {tool.name for tool in OO_NETWORK_CONFIG_TOOLS}
        assert names == {
            "get_oo_network_configs",
            "create_oo_network_config",
            "update_oo_network_config",
            "delete_oo_network_config",
        }
