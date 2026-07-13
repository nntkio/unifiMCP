"""Tests for UniFi client NAT rule CRUD."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.unifi_client._nat_rules import _NatRuleMixin


class TestUniFiClientNatRules:
    """Tests for NAT rule methods."""

    @pytest.fixture
    def mock_client(self) -> _NatRuleMixin:
        """Create a mock client for testing."""
        client = _NatRuleMixin()
        client._request_v2 = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_get_nat_rules(self, mock_client: _NatRuleMixin) -> None:
        """Test get_nat_rules method."""
        mock_client._request_v2.return_value = [{"_id": "nat1", "name": "Guest NAT"}]

        result = await mock_client.get_nat_rules()

        assert result == [{"_id": "nat1", "name": "Guest NAT"}]
        mock_client._request_v2.assert_called_once_with("GET", "/nat")

    @pytest.mark.asyncio
    async def test_create_nat_rule(self, mock_client: _NatRuleMixin) -> None:
        """Test create_nat_rule method."""
        mock_client._request_v2.return_value = [{"_id": "nat1", "name": "Guest NAT"}]

        result = await mock_client.create_nat_rule(
            {"name": "Guest NAT", "enabled": True}
        )

        assert result == {"_id": "nat1", "name": "Guest NAT"}
        mock_client._request_v2.assert_called_once_with(
            "POST",
            "/nat",
            json={"name": "Guest NAT", "enabled": True},
        )

    @pytest.mark.asyncio
    async def test_update_nat_rule(self, mock_client: _NatRuleMixin) -> None:
        """Test update_nat_rule method."""
        mock_client._request_v2.return_value = []

        result = await mock_client.update_nat_rule(
            "nat1", {"_id": "nat1", "name": "Guest NAT", "enabled": False}
        )

        assert result is True
        mock_client._request_v2.assert_called_once_with(
            "PUT",
            "/nat/nat1",
            json={"_id": "nat1", "name": "Guest NAT", "enabled": False},
        )

    @pytest.mark.asyncio
    async def test_delete_nat_rule(self, mock_client: _NatRuleMixin) -> None:
        """Test delete_nat_rule method."""
        mock_client._request_v2.return_value = []

        result = await mock_client.delete_nat_rule("nat1")

        assert result is True
        mock_client._request_v2.assert_called_once_with("DELETE", "/nat/nat1")
