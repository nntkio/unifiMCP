"""Tests for UniFi client WLAN rate profile CRUD."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.unifi_client._wlan_rate_profiles import _WlanRateProfileMixin


class TestUniFiClientWlanRateProfiles:
    """Tests for WLAN rate profile methods."""

    @pytest.fixture
    def mock_client(self) -> _WlanRateProfileMixin:
        """Create a mock client for testing."""
        client = _WlanRateProfileMixin()
        client._request_v2 = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_get_wlan_rate_profiles(
        self, mock_client: _WlanRateProfileMixin
    ) -> None:
        """Test get_wlan_rate_profiles method."""
        mock_client._request_v2.return_value = [{"_id": "profile1", "name": "Default"}]

        result = await mock_client.get_wlan_rate_profiles()

        assert result == [{"_id": "profile1", "name": "Default"}]
        mock_client._request_v2.assert_called_once_with("GET", "/profiles/wlanrate")

    @pytest.mark.asyncio
    async def test_create_wlan_rate_profile(
        self, mock_client: _WlanRateProfileMixin
    ) -> None:
        """Test create_wlan_rate_profile method."""
        mock_client._request_v2.return_value = [
            {"_id": "profile1", "name": "IoT Rates"}
        ]

        result = await mock_client.create_wlan_rate_profile({"name": "IoT Rates"})

        assert result == {"_id": "profile1", "name": "IoT Rates"}
        mock_client._request_v2.assert_called_once_with(
            "POST",
            "/profiles/wlanrate",
            json={"name": "IoT Rates"},
        )

    @pytest.mark.asyncio
    async def test_update_wlan_rate_profile(
        self, mock_client: _WlanRateProfileMixin
    ) -> None:
        """Test update_wlan_rate_profile method."""
        mock_client._request_v2.return_value = []

        result = await mock_client.update_wlan_rate_profile(
            "profile1", {"_id": "profile1", "name": "IoT Rates Updated"}
        )

        assert result is True
        mock_client._request_v2.assert_called_once_with(
            "PUT",
            "/profiles/wlanrate/profile1",
            json={"_id": "profile1", "name": "IoT Rates Updated"},
        )

    @pytest.mark.asyncio
    async def test_delete_wlan_rate_profile(
        self, mock_client: _WlanRateProfileMixin
    ) -> None:
        """Test delete_wlan_rate_profile method."""
        mock_client._request_v2.return_value = []

        result = await mock_client.delete_wlan_rate_profile("profile1")

        assert result is True
        mock_client._request_v2.assert_called_once_with(
            "DELETE", "/profiles/wlanrate/profile1"
        )
