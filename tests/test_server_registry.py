"""Tests for the MCP tool registry, dispatch, and shared client lifecycle."""

from unittest.mock import AsyncMock, patch

import pytest

from unifi_mcp import server as server_module
from unifi_mcp.server import call_tool, list_tools


class TestListTools:
    """Tests for list_tools function."""

    @pytest.mark.asyncio
    async def test_list_tools_returns_all_tools(self) -> None:
        """Test that list_tools returns all expected tools."""
        tools = await list_tools()

        tool_names = [t.name for t in tools]
        assert "get_devices" in tool_names
        assert "restart_device" in tool_names
        assert "adopt_device" in tool_names
        assert "force_provision_device" in tool_names
        assert "upgrade_device" in tool_names
        assert "power_cycle_port" in tool_names
        assert "set_device_locate" in tool_names
        assert "unset_device_locate" in tool_names
        assert "get_clients" in tool_names
        assert "block_client" in tool_names
        assert "unblock_client" in tool_names
        assert "disconnect_client" in tool_names
        assert "forget_client" in tool_names
        assert "authorize_guest" in tool_names
        assert "unauthorize_guest" in tool_names
        assert "get_sites" in tool_names
        assert "get_site_health" in tool_names
        assert "get_networks" in tool_names
        assert "create_network" in tool_names
        assert "update_network" in tool_names
        assert "delete_network" in tool_names
        assert "get_device_activity" in tool_names
        assert "get_firewall_rules" in tool_names
        assert "enable_firewall_rule" in tool_names
        assert "disable_firewall_rule" in tool_names
        assert "create_firewall_rule" in tool_names
        assert "delete_firewall_rule" in tool_names
        assert "enable_firewall_policy" in tool_names
        assert "disable_firewall_policy" in tool_names
        assert "create_firewall_policy" in tool_names
        assert "batch_update_firewall_policies" in tool_names
        assert "batch_delete_firewall_policies" in tool_names

    @pytest.mark.asyncio
    async def test_tools_have_descriptions(self) -> None:
        """Test that all tools have descriptions."""
        tools = await list_tools()

        for tool in tools:
            assert tool.description
            assert len(tool.description) > 10


class TestCallTool:
    """Tests for call_tool dispatch mechanics not specific to any tool domain."""

    @pytest.mark.asyncio
    async def test_call_unknown_tool(self) -> None:
        """Test calling an unknown tool."""
        result = await call_tool("unknown_tool", {})

        assert len(result) == 1
        assert "Unknown tool" in result[0].text


class TestClientLifecycle:
    """Tests for the shared client's connect-once/reuse/close behavior."""

    def teardown_method(self) -> None:
        """Ensure the module-level singleton doesn't leak into other tests."""
        server_module._client = None

    @pytest.mark.asyncio
    async def test_get_client_reuses_connection(self) -> None:
        """Test that repeated _get_client() calls connect only once."""
        with patch("unifi_mcp.server.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_client_class.return_value.connect = AsyncMock(
                return_value=mock_instance
            )

            first = await server_module._get_client()
            second = await server_module._get_client()

            assert first is second
            mock_client_class.return_value.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_client_resets_singleton(self) -> None:
        """Test that _close_client() closes the connection and clears state."""
        with patch("unifi_mcp.server.UniFiClient") as mock_client_class:
            mock_instance = AsyncMock()
            mock_client_class.return_value.connect = AsyncMock(
                return_value=mock_instance
            )

            await server_module._get_client()
            await server_module._close_client()

            mock_instance.close.assert_called_once()
            assert server_module._client is None
