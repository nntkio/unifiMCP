"""Tests for WLAN configuration CRUD tools."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.server._wlan import (
    WLAN_TOOLS,
    _handle_create_wlan,
    _handle_delete_wlan,
    _handle_get_wlans,
    _handle_update_wlan,
    format_wlans,
)


class TestHandleWlan:
    """Tests for WLAN tool handlers."""

    @pytest.mark.asyncio
    async def test_handle_get_wlans(self) -> None:
        """Test _handle_get_wlans."""
        mock_client = AsyncMock()
        mock_client.get_wlans = AsyncMock(
            return_value=[{"name": "Home", "enabled": True}]
        )

        result = await _handle_get_wlans(mock_client, {})

        assert "Home" in result
        mock_client.get_wlans.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_handle_create_wlan(self) -> None:
        """Test _handle_create_wlan."""
        mock_client = AsyncMock()
        mock_client.create_wlan = AsyncMock(
            return_value={"_id": "wlan1", "name": "Home"}
        )

        result = await _handle_create_wlan(
            mock_client,
            {"wlan": {"name": "Home", "security": "wpapsk", "x_passphrase": "secret"}},
        )

        assert "Home" in result
        assert "secret" not in result
        mock_client.create_wlan.assert_called_once_with(
            {"name": "Home", "security": "wpapsk", "x_passphrase": "secret"}
        )

    @pytest.mark.asyncio
    async def test_handle_update_wlan(self) -> None:
        """Test _handle_update_wlan."""
        mock_client = AsyncMock()
        mock_client.update_wlan = AsyncMock()

        result = await _handle_update_wlan(
            mock_client,
            {"wlan_id": "wlan1", "wlan": {"name": "Home", "x_passphrase": "secret"}},
        )

        assert "updated" in result
        assert "secret" not in result
        mock_client.update_wlan.assert_called_once_with(
            "wlan1", {"name": "Home", "x_passphrase": "secret"}
        )

    @pytest.mark.asyncio
    async def test_handle_delete_wlan(self) -> None:
        """Test _handle_delete_wlan."""
        mock_client = AsyncMock()
        mock_client.delete_wlan = AsyncMock()

        result = await _handle_delete_wlan(mock_client, {"wlan_id": "wlan1"})

        assert "deleted" in result
        mock_client.delete_wlan.assert_called_once_with("wlan1")


class TestFormatWlans:
    """Tests for format_wlans."""

    def test_format_wlans_empty(self) -> None:
        """Test formatting empty WLAN list."""
        result = format_wlans([])
        assert result == "No WLANs configured."

    def test_format_wlans_with_data(self) -> None:
        """Test formatting WLAN list."""
        wlans = [{"name": "Home", "enabled": True}]
        result = format_wlans(wlans)
        assert "Home" in result
        assert "Enabled" in result

    def test_format_wlans_never_leaks_passphrase(self) -> None:
        """Test that the WPA passphrase never appears in formatted output."""
        wlans = [
            {
                "name": "Home",
                "enabled": True,
                "x_passphrase": "supersecret123",
            }
        ]
        result = format_wlans(wlans)
        assert "supersecret123" not in result


class TestWlanTools:
    """Tests for WLAN_TOOLS registration."""

    def test_wlan_tools_names(self) -> None:
        """Test that WLAN_TOOLS contains all expected tool names."""
        names = {tool.name for tool in WLAN_TOOLS}
        assert names == {
            "get_wlans",
            "create_wlan",
            "update_wlan",
            "delete_wlan",
        }
