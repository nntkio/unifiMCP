"""Tests for WLAN rate profile CRUD tools."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.server._wlan_rate_profiles import (
    WLAN_RATE_PROFILE_TOOLS,
    _handle_create_wlan_rate_profile,
    _handle_delete_wlan_rate_profile,
    _handle_get_wlan_rate_profiles,
    _handle_update_wlan_rate_profile,
    format_wlan_rate_profiles,
)


class TestWlanRateProfileHandlers:
    """Tests for WLAN rate profile tool handlers."""

    @pytest.mark.asyncio
    async def test_handle_get_wlan_rate_profiles(self) -> None:
        """Test _handle_get_wlan_rate_profiles handler."""
        mock_client = AsyncMock()
        mock_client.get_wlan_rate_profiles = AsyncMock(
            return_value=[{"_id": "profile1", "name": "Default"}]
        )

        result = await _handle_get_wlan_rate_profiles(mock_client, {})

        assert "Default" in result
        mock_client.get_wlan_rate_profiles.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_handle_create_wlan_rate_profile(self) -> None:
        """Test _handle_create_wlan_rate_profile handler."""
        mock_client = AsyncMock()
        mock_client.create_wlan_rate_profile = AsyncMock(
            return_value={"_id": "profile1", "name": "IoT Rates"}
        )

        result = await _handle_create_wlan_rate_profile(
            mock_client, {"profile": {"name": "IoT Rates"}}
        )

        assert "IoT Rates" in result
        mock_client.create_wlan_rate_profile.assert_called_once_with(
            {"name": "IoT Rates"}
        )

    @pytest.mark.asyncio
    async def test_handle_update_wlan_rate_profile(self) -> None:
        """Test _handle_update_wlan_rate_profile handler."""
        mock_client = AsyncMock()
        mock_client.update_wlan_rate_profile = AsyncMock()

        result = await _handle_update_wlan_rate_profile(
            mock_client,
            {"profile_id": "profile1", "profile": {"name": "IoT Rates Updated"}},
        )

        assert "updated" in result
        mock_client.update_wlan_rate_profile.assert_called_once_with(
            "profile1", {"name": "IoT Rates Updated"}
        )

    @pytest.mark.asyncio
    async def test_handle_delete_wlan_rate_profile(self) -> None:
        """Test _handle_delete_wlan_rate_profile handler."""
        mock_client = AsyncMock()
        mock_client.delete_wlan_rate_profile = AsyncMock()

        result = await _handle_delete_wlan_rate_profile(
            mock_client, {"profile_id": "profile1"}
        )

        assert "deleted" in result
        mock_client.delete_wlan_rate_profile.assert_called_once_with("profile1")


class TestFormatWlanRateProfiles:
    """Tests for format_wlan_rate_profiles."""

    def test_format_wlan_rate_profiles_empty(self) -> None:
        """Test formatting empty WLAN rate profile list."""
        result = format_wlan_rate_profiles([])
        assert result == "No WLAN rate profiles configured."

    def test_format_wlan_rate_profiles_with_data(self) -> None:
        """Test formatting WLAN rate profile list."""
        profiles = [{"_id": "profile1", "name": "IoT Rates"}]
        result = format_wlan_rate_profiles(profiles)
        assert "IoT Rates" in result


class TestWlanRateProfileTools:
    """Tests for WLAN_RATE_PROFILE_TOOLS."""

    def test_tool_names(self) -> None:
        """Test that all expected tools are registered."""
        names = {tool.name for tool in WLAN_RATE_PROFILE_TOOLS}
        assert names == {
            "get_wlan_rate_profiles",
            "create_wlan_rate_profile",
            "update_wlan_rate_profile",
            "delete_wlan_rate_profile",
        }
