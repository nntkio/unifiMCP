"""Tests for UniFi client RADIUS profile CRUD."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.unifi_client._radius_profiles import _RadiusProfileMixin


class TestUniFiClientRadiusProfiles:
    """Tests for RADIUS profile methods."""

    @pytest.fixture
    def mock_client(self) -> _RadiusProfileMixin:
        """Create a mock client for testing."""
        client = _RadiusProfileMixin()
        client._request = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_get_radius_profiles(self, mock_client: _RadiusProfileMixin) -> None:
        """Test get_radius_profiles method."""
        mock_client._request.return_value = [{"_id": "rad1", "name": "RADIUS"}]

        result = await mock_client.get_radius_profiles()

        assert result == [{"_id": "rad1", "name": "RADIUS"}]
        mock_client._request.assert_called_once_with(
            "GET", "/api/s/{site}/rest/radiusprofile"
        )

    @pytest.mark.asyncio
    async def test_create_radius_profile(
        self, mock_client: _RadiusProfileMixin
    ) -> None:
        """Test create_radius_profile method."""
        mock_client._request.return_value = [
            {"_id": "rad1", "name": "RADIUS", "x_secret": "supersecret123"}
        ]

        result = await mock_client.create_radius_profile(
            {"name": "RADIUS", "x_secret": "supersecret123"}
        )

        assert result == {
            "_id": "rad1",
            "name": "RADIUS",
            "x_secret": "supersecret123",
        }
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/rest/radiusprofile",
            json={"name": "RADIUS", "x_secret": "supersecret123"},
        )

    @pytest.mark.asyncio
    async def test_update_radius_profile(
        self, mock_client: _RadiusProfileMixin
    ) -> None:
        """Test update_radius_profile method."""
        mock_client._request.return_value = []

        result = await mock_client.update_radius_profile(
            "rad1", {"_id": "rad1", "name": "RADIUS", "x_secret": "newsecret"}
        )

        assert result is True
        mock_client._request.assert_called_once_with(
            "PUT",
            "/api/s/{site}/rest/radiusprofile/rad1",
            json={"_id": "rad1", "name": "RADIUS", "x_secret": "newsecret"},
        )

    @pytest.mark.asyncio
    async def test_delete_radius_profile(
        self, mock_client: _RadiusProfileMixin
    ) -> None:
        """Test delete_radius_profile method."""
        mock_client._request.return_value = []

        result = await mock_client.delete_radius_profile("rad1")

        assert result is True
        mock_client._request.assert_called_once_with(
            "DELETE", "/api/s/{site}/rest/radiusprofile/rad1"
        )
