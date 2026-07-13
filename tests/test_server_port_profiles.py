"""Tests for port profile CRUD tools."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.server._port_profiles import (
    PORT_PROFILE_TOOLS,
    _handle_create_port_profile,
    _handle_delete_port_profile,
    _handle_get_port_profiles,
    _handle_update_port_profile,
    format_port_profiles,
)


class TestHandlePortProfiles:
    """Tests for port profile tool handlers."""

    @pytest.mark.asyncio
    async def test_handle_get_port_profiles(self) -> None:
        """Test _handle_get_port_profiles."""
        mock_client = AsyncMock()
        mock_client.get_port_profiles = AsyncMock(
            return_value=[{"name": "All", "poe_mode": "auto"}]
        )

        result = await _handle_get_port_profiles(mock_client, {})

        assert "All" in result
        mock_client.get_port_profiles.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_handle_create_port_profile(self) -> None:
        """Test _handle_create_port_profile."""
        mock_client = AsyncMock()
        mock_client.create_port_profile = AsyncMock(
            return_value={"_id": "prof1", "name": "PoE Profile"}
        )

        result = await _handle_create_port_profile(
            mock_client, {"profile": {"name": "PoE Profile", "poe_mode": "auto"}}
        )

        assert "PoE Profile" in result
        mock_client.create_port_profile.assert_called_once_with(
            {"name": "PoE Profile", "poe_mode": "auto"}
        )

    @pytest.mark.asyncio
    async def test_handle_update_port_profile(self) -> None:
        """Test _handle_update_port_profile."""
        mock_client = AsyncMock()
        mock_client.update_port_profile = AsyncMock()

        result = await _handle_update_port_profile(
            mock_client,
            {"profile_id": "prof1", "profile": {"name": "PoE Profile"}},
        )

        assert "updated" in result
        mock_client.update_port_profile.assert_called_once_with(
            "prof1", {"name": "PoE Profile"}
        )

    @pytest.mark.asyncio
    async def test_handle_delete_port_profile(self) -> None:
        """Test _handle_delete_port_profile."""
        mock_client = AsyncMock()
        mock_client.delete_port_profile = AsyncMock()

        result = await _handle_delete_port_profile(mock_client, {"profile_id": "prof1"})

        assert "deleted" in result
        mock_client.delete_port_profile.assert_called_once_with("prof1")


class TestFormatPortProfiles:
    """Tests for format_port_profiles."""

    def test_format_port_profiles_empty(self) -> None:
        """Test formatting empty port profile list."""
        result = format_port_profiles([])
        assert result == "No port profiles configured."

    def test_format_port_profiles_with_data(self) -> None:
        """Test formatting port profile list."""
        profiles = [
            {
                "name": "PoE Profile",
                "poe_mode": "auto",
                "native_networkconf_id": "net1",
            }
        ]
        result = format_port_profiles(profiles)
        assert "PoE Profile" in result
        assert "auto" in result
        assert "net1" in result


class TestPortProfileTools:
    """Tests for PORT_PROFILE_TOOLS."""

    def test_tool_names(self) -> None:
        """Test that PORT_PROFILE_TOOLS contains all expected tool names."""
        names = {tool.name for tool in PORT_PROFILE_TOOLS}
        assert names == {
            "get_port_profiles",
            "create_port_profile",
            "update_port_profile",
            "delete_port_profile",
        }
