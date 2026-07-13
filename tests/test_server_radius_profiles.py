"""Tests for RADIUS profile CRUD tools."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.server._radius_profiles import (
    RADIUS_PROFILE_TOOLS,
    _handle_create_radius_profile,
    _handle_delete_radius_profile,
    _handle_get_radius_profiles,
    _handle_update_radius_profile,
    format_radius_profiles,
)


class TestHandleRadiusProfiles:
    """Tests for RADIUS profile tool handlers."""

    @pytest.mark.asyncio
    async def test_handle_get_radius_profiles(self) -> None:
        """Test _handle_get_radius_profiles."""
        mock_client = AsyncMock()
        mock_client.get_radius_profiles = AsyncMock(
            return_value=[{"_id": "rad1", "name": "RADIUS"}]
        )

        result = await _handle_get_radius_profiles(mock_client, {})

        assert "RADIUS" in result
        mock_client.get_radius_profiles.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_handle_create_radius_profile(self) -> None:
        """Test _handle_create_radius_profile."""
        mock_client = AsyncMock()
        mock_client.create_radius_profile = AsyncMock(
            return_value={"_id": "rad1", "name": "RADIUS"}
        )

        result = await _handle_create_radius_profile(
            mock_client,
            {"profile": {"name": "RADIUS", "x_secret": "supersecret123"}},
        )

        assert "RADIUS" in result
        assert "supersecret123" not in result
        mock_client.create_radius_profile.assert_called_once_with(
            {"name": "RADIUS", "x_secret": "supersecret123"}
        )

    @pytest.mark.asyncio
    async def test_handle_update_radius_profile(self) -> None:
        """Test _handle_update_radius_profile."""
        mock_client = AsyncMock()
        mock_client.update_radius_profile = AsyncMock()

        result = await _handle_update_radius_profile(
            mock_client,
            {
                "profile_id": "rad1",
                "profile": {"name": "RADIUS", "x_secret": "newsecret"},
            },
        )

        assert "rad1" in result
        assert "updated" in result
        assert "newsecret" not in result
        mock_client.update_radius_profile.assert_called_once_with(
            "rad1", {"name": "RADIUS", "x_secret": "newsecret"}
        )

    @pytest.mark.asyncio
    async def test_handle_delete_radius_profile(self) -> None:
        """Test _handle_delete_radius_profile."""
        mock_client = AsyncMock()
        mock_client.delete_radius_profile = AsyncMock()

        result = await _handle_delete_radius_profile(
            mock_client, {"profile_id": "rad1"}
        )

        assert "rad1" in result
        assert "deleted" in result
        mock_client.delete_radius_profile.assert_called_once_with("rad1")


class TestFormatRadiusProfiles:
    """Tests for format_radius_profiles."""

    def test_format_radius_profiles_empty(self) -> None:
        """Test formatting an empty RADIUS profile list."""
        result = format_radius_profiles([])
        assert result == "No RADIUS profiles configured."

    def test_format_radius_profiles_with_data(self) -> None:
        """Test formatting a RADIUS profile list."""
        profiles = [{"name": "Corporate RADIUS"}]
        result = format_radius_profiles(profiles)
        assert "Corporate RADIUS" in result

    def test_format_radius_profiles_excludes_secret(self) -> None:
        """Test that secret fields are never included in formatted output."""
        profiles = [
            {
                "name": "Corporate RADIUS",
                "x_secret": "supersecret123",
            }
        ]
        result = format_radius_profiles(profiles)
        assert "supersecret123" not in result


class TestRadiusProfileTools:
    """Tests for RADIUS_PROFILE_TOOLS registration."""

    def test_radius_profile_tools_names(self) -> None:
        """Test that all expected RADIUS profile tools are registered."""
        names = {tool.name for tool in RADIUS_PROFILE_TOOLS}
        assert names == {
            "get_radius_profiles",
            "create_radius_profile",
            "update_radius_profile",
            "delete_radius_profile",
        }
