"""Tests for port forwarding rule CRUD tools."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.server._port_forwarding import (
    PORT_FORWARDING_TOOLS,
    _handle_create_port_forward,
    _handle_delete_port_forward,
    _handle_get_port_forwards,
    _handle_update_port_forward,
    format_port_forwards,
)


class TestPortForwardingHandlers:
    """Tests for port forwarding tool handlers."""

    @pytest.mark.asyncio
    async def test_handle_get_port_forwards(self) -> None:
        """Test _handle_get_port_forwards handler."""
        mock_client = AsyncMock()
        mock_client.get_port_forwards = AsyncMock(
            return_value=[
                {
                    "name": "Web Server",
                    "fwd": "192.168.1.10",
                    "fwd_port": "80",
                    "enabled": True,
                }
            ]
        )

        result = await _handle_get_port_forwards(mock_client, {})

        assert "Web Server" in result
        mock_client.get_port_forwards.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_handle_create_port_forward(self) -> None:
        """Test _handle_create_port_forward handler."""
        mock_client = AsyncMock()
        mock_client.create_port_forward = AsyncMock(
            return_value={"_id": "fwd1", "name": "Web Server"}
        )

        result = await _handle_create_port_forward(
            mock_client,
            {"forward": {"name": "Web Server", "fwd": "192.168.1.10"}},
        )

        assert "Web Server" in result
        assert "created" in result
        mock_client.create_port_forward.assert_called_once_with(
            {"name": "Web Server", "fwd": "192.168.1.10"}
        )

    @pytest.mark.asyncio
    async def test_handle_update_port_forward(self) -> None:
        """Test _handle_update_port_forward handler."""
        mock_client = AsyncMock()
        mock_client.update_port_forward = AsyncMock()

        result = await _handle_update_port_forward(
            mock_client,
            {"forward_id": "fwd1", "forward": {"name": "Web Server"}},
        )

        assert "fwd1" in result
        assert "updated" in result
        mock_client.update_port_forward.assert_called_once_with(
            "fwd1", {"name": "Web Server"}
        )

    @pytest.mark.asyncio
    async def test_handle_delete_port_forward(self) -> None:
        """Test _handle_delete_port_forward handler."""
        mock_client = AsyncMock()
        mock_client.delete_port_forward = AsyncMock()

        result = await _handle_delete_port_forward(mock_client, {"forward_id": "fwd1"})

        assert "fwd1" in result
        assert "deleted" in result
        mock_client.delete_port_forward.assert_called_once_with("fwd1")


class TestFormatPortForwards:
    """Tests for format_port_forwards."""

    def test_format_port_forwards_empty(self) -> None:
        """Test formatting empty port forward list."""
        result = format_port_forwards([])
        assert result == "No port forwarding rules configured."

    def test_format_port_forwards_with_data(self) -> None:
        """Test formatting port forward list."""
        forwards = [
            {
                "name": "Web Server",
                "fwd": "192.168.1.10",
                "fwd_port": "80",
                "enabled": True,
            }
        ]
        result = format_port_forwards(forwards)
        assert "Web Server" in result
        assert "192.168.1.10" in result
        assert "80" in result
        assert "Enabled" in result


class TestPortForwardingTools:
    """Tests for PORT_FORWARDING_TOOLS."""

    def test_tool_names(self) -> None:
        """Test that all expected tools are present."""
        names = {tool.name for tool in PORT_FORWARDING_TOOLS}
        assert names == {
            "get_port_forwards",
            "create_port_forward",
            "update_port_forward",
            "delete_port_forward",
        }
