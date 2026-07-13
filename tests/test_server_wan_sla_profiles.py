"""Tests for WAN SLA profile CRUD tools."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.server._wan_sla_profiles import (
    WAN_SLA_PROFILE_TOOLS,
    _handle_create_wan_sla_profile,
    _handle_delete_wan_sla_profile,
    _handle_get_wan_sla_profiles,
    _handle_update_wan_sla_profile,
    format_wan_sla_profiles,
)


class TestWanSlaProfileHandlers:
    """Tests for WAN SLA profile handler functions."""

    @pytest.mark.asyncio
    async def test_handle_get_wan_sla_profiles(self) -> None:
        """Test _handle_get_wan_sla_profiles."""
        mock_client = AsyncMock()
        mock_client.get_wan_sla_profiles = AsyncMock(
            return_value=[{"_id": "wansla1", "name": "Primary"}]
        )

        result = await _handle_get_wan_sla_profiles(mock_client, {})

        assert "Primary" in result
        mock_client.get_wan_sla_profiles.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_handle_create_wan_sla_profile(self) -> None:
        """Test _handle_create_wan_sla_profile."""
        mock_client = AsyncMock()
        mock_client.create_wan_sla_profile = AsyncMock(
            return_value={"_id": "wansla1", "name": "Primary"}
        )

        result = await _handle_create_wan_sla_profile(
            mock_client, {"profile": {"name": "Primary"}}
        )

        assert "Primary" in result
        mock_client.create_wan_sla_profile.assert_called_once_with({"name": "Primary"})

    @pytest.mark.asyncio
    async def test_handle_update_wan_sla_profile(self) -> None:
        """Test _handle_update_wan_sla_profile."""
        mock_client = AsyncMock()
        mock_client.update_wan_sla_profile = AsyncMock()

        result = await _handle_update_wan_sla_profile(
            mock_client,
            {"profile_id": "wansla1", "profile": {"name": "Primary Updated"}},
        )

        assert "updated" in result
        mock_client.update_wan_sla_profile.assert_called_once_with(
            "wansla1", {"name": "Primary Updated"}
        )

    @pytest.mark.asyncio
    async def test_handle_delete_wan_sla_profile(self) -> None:
        """Test _handle_delete_wan_sla_profile."""
        mock_client = AsyncMock()
        mock_client.delete_wan_sla_profile = AsyncMock()

        result = await _handle_delete_wan_sla_profile(
            mock_client, {"profile_id": "wansla1"}
        )

        assert "deleted" in result
        mock_client.delete_wan_sla_profile.assert_called_once_with("wansla1")


class TestFormatWanSlaProfiles:
    """Tests for format_wan_sla_profiles."""

    def test_format_wan_sla_profiles_empty(self) -> None:
        """Test formatting empty WAN SLA profile list."""
        result = format_wan_sla_profiles([])
        assert result == "No WAN SLA profiles configured."

    def test_format_wan_sla_profiles_with_data(self) -> None:
        """Test formatting WAN SLA profile list."""
        profiles = [{"_id": "wansla1", "name": "Primary"}]
        result = format_wan_sla_profiles(profiles)
        assert "Primary" in result
        assert "1 WAN SLA profile(s)" in result


class TestWanSlaProfileTools:
    """Tests for WAN_SLA_PROFILE_TOOLS."""

    def test_contains_all_expected_tools(self) -> None:
        """Test that WAN_SLA_PROFILE_TOOLS contains all 4 expected tools."""
        names = {tool.name for tool in WAN_SLA_PROFILE_TOOLS}
        assert names == {
            "get_wan_sla_profiles",
            "create_wan_sla_profile",
            "update_wan_sla_profile",
            "delete_wan_sla_profile",
        }
