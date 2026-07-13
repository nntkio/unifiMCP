"""Tests for UniFi client port profile CRUD."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.unifi_client._port_profiles import _PortProfileMixin


class TestUniFiClientPortProfiles:
    """Tests for port profile methods."""

    @pytest.fixture
    def mock_client(self) -> _PortProfileMixin:
        """Create a mock client for testing."""
        client = _PortProfileMixin()
        client._request = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_get_port_profiles(self, mock_client: _PortProfileMixin) -> None:
        """Test get_port_profiles method."""
        mock_client._request.return_value = [{"_id": "prof1", "name": "All"}]

        result = await mock_client.get_port_profiles()

        assert result == [{"_id": "prof1", "name": "All"}]
        mock_client._request.assert_called_once_with(
            "GET", "/api/s/{site}/rest/portconf"
        )

    @pytest.mark.asyncio
    async def test_create_port_profile(self, mock_client: _PortProfileMixin) -> None:
        """Test create_port_profile method."""
        mock_client._request.return_value = [{"_id": "prof1", "name": "PoE Profile"}]

        result = await mock_client.create_port_profile(
            {"name": "PoE Profile", "poe_mode": "auto"}
        )

        assert result == {"_id": "prof1", "name": "PoE Profile"}
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/rest/portconf",
            json={"name": "PoE Profile", "poe_mode": "auto"},
        )

    @pytest.mark.asyncio
    async def test_update_port_profile(self, mock_client: _PortProfileMixin) -> None:
        """Test update_port_profile method."""
        mock_client._request.return_value = []

        result = await mock_client.update_port_profile(
            "prof1", {"_id": "prof1", "name": "PoE Profile", "poe_mode": "off"}
        )

        assert result is True
        mock_client._request.assert_called_once_with(
            "PUT",
            "/api/s/{site}/rest/portconf/prof1",
            json={"_id": "prof1", "name": "PoE Profile", "poe_mode": "off"},
        )

    @pytest.mark.asyncio
    async def test_delete_port_profile(self, mock_client: _PortProfileMixin) -> None:
        """Test delete_port_profile method."""
        mock_client._request.return_value = []

        result = await mock_client.delete_port_profile("prof1")

        assert result is True
        mock_client._request.assert_called_once_with(
            "DELETE", "/api/s/{site}/rest/portconf/prof1"
        )
