"""Tests for UniFi client WAN SLA profile CRUD."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.unifi_client._wan_sla_profiles import _WanSlaProfileMixin


class TestUniFiClientWanSlaProfiles:
    """Tests for WAN SLA profile methods."""

    @pytest.fixture
    def mock_client(self) -> _WanSlaProfileMixin:
        """Create a mock client for testing."""
        client = _WanSlaProfileMixin()
        client._request_v2 = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_get_wan_sla_profiles(self, mock_client: _WanSlaProfileMixin) -> None:
        """Test get_wan_sla_profiles method."""
        mock_client._request_v2.return_value = [{"_id": "wansla1", "name": "Primary"}]

        result = await mock_client.get_wan_sla_profiles()

        assert result == [{"_id": "wansla1", "name": "Primary"}]
        mock_client._request_v2.assert_called_once_with("GET", "/profiles/wansla")

    @pytest.mark.asyncio
    async def test_create_wan_sla_profile(
        self, mock_client: _WanSlaProfileMixin
    ) -> None:
        """Test create_wan_sla_profile method."""
        mock_client._request_v2.return_value = [{"_id": "wansla1", "name": "Primary"}]

        result = await mock_client.create_wan_sla_profile({"name": "Primary"})

        assert result == {"_id": "wansla1", "name": "Primary"}
        mock_client._request_v2.assert_called_once_with(
            "POST", "/profiles/wansla", json={"name": "Primary"}
        )

    @pytest.mark.asyncio
    async def test_create_wan_sla_profile_empty_response(
        self, mock_client: _WanSlaProfileMixin
    ) -> None:
        """Test create_wan_sla_profile method with an empty response."""
        mock_client._request_v2.return_value = []

        result = await mock_client.create_wan_sla_profile({"name": "Primary"})

        assert result == {}

    @pytest.mark.asyncio
    async def test_update_wan_sla_profile(
        self, mock_client: _WanSlaProfileMixin
    ) -> None:
        """Test update_wan_sla_profile method."""
        mock_client._request_v2.return_value = []

        result = await mock_client.update_wan_sla_profile(
            "wansla1", {"_id": "wansla1", "name": "Primary Updated"}
        )

        assert result is True
        mock_client._request_v2.assert_called_once_with(
            "PUT",
            "/profiles/wansla/wansla1",
            json={"_id": "wansla1", "name": "Primary Updated"},
        )

    @pytest.mark.asyncio
    async def test_delete_wan_sla_profile(
        self, mock_client: _WanSlaProfileMixin
    ) -> None:
        """Test delete_wan_sla_profile method."""
        mock_client._request_v2.return_value = []

        result = await mock_client.delete_wan_sla_profile("wansla1")

        assert result is True
        mock_client._request_v2.assert_called_once_with(
            "DELETE", "/profiles/wansla/wansla1"
        )
