"""Tests for UniFi client firewall group CRUD."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.unifi_client._firewall_groups import _FirewallGroupMixin


class TestUniFiClientFirewallGroups:
    """Tests for firewall group methods."""

    @pytest.fixture
    def mock_client(self) -> _FirewallGroupMixin:
        """Create a mock client for testing."""
        client = _FirewallGroupMixin()
        client._request = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_get_firewall_groups(self, mock_client: _FirewallGroupMixin) -> None:
        """Test get_firewall_groups method."""
        mock_client._request.return_value = [{"_id": "fg1", "name": "Blocklist"}]

        result = await mock_client.get_firewall_groups()

        assert result == [{"_id": "fg1", "name": "Blocklist"}]
        mock_client._request.assert_called_once_with(
            "GET", "/api/s/{site}/rest/firewallgroup"
        )

    @pytest.mark.asyncio
    async def test_create_firewall_group(
        self, mock_client: _FirewallGroupMixin
    ) -> None:
        """Test create_firewall_group method."""
        mock_client._request.return_value = [{"_id": "fg1", "name": "Blocklist"}]

        result = await mock_client.create_firewall_group(
            {"name": "Blocklist", "group_type": "address-group"}
        )

        assert result == {"_id": "fg1", "name": "Blocklist"}
        mock_client._request.assert_called_once_with(
            "POST",
            "/api/s/{site}/rest/firewallgroup",
            json={"name": "Blocklist", "group_type": "address-group"},
        )

    @pytest.mark.asyncio
    async def test_create_firewall_group_empty_response(
        self, mock_client: _FirewallGroupMixin
    ) -> None:
        """Test create_firewall_group returns empty dict when no data."""
        mock_client._request.return_value = []

        result = await mock_client.create_firewall_group({"name": "Blocklist"})

        assert result == {}

    @pytest.mark.asyncio
    async def test_update_firewall_group(
        self, mock_client: _FirewallGroupMixin
    ) -> None:
        """Test update_firewall_group method."""
        mock_client._request.return_value = []

        result = await mock_client.update_firewall_group(
            "fg1", {"_id": "fg1", "name": "Blocklist", "group_type": "port-group"}
        )

        assert result is True
        mock_client._request.assert_called_once_with(
            "PUT",
            "/api/s/{site}/rest/firewallgroup/fg1",
            json={"_id": "fg1", "name": "Blocklist", "group_type": "port-group"},
        )

    @pytest.mark.asyncio
    async def test_delete_firewall_group(
        self, mock_client: _FirewallGroupMixin
    ) -> None:
        """Test delete_firewall_group method."""
        mock_client._request.return_value = []

        result = await mock_client.delete_firewall_group("fg1")

        assert result is True
        mock_client._request.assert_called_once_with(
            "DELETE", "/api/s/{site}/rest/firewallgroup/fg1"
        )
