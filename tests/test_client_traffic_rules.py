"""Tests for UniFi client traffic rules."""

from unittest.mock import AsyncMock

import pytest

from unifi_mcp.unifi_client._base import UniFiError
from unifi_mcp.unifi_client._traffic_rules import _TrafficRuleMixin


class TestUniFiClientTrafficRules:
    """Tests for traffic rule methods."""

    @pytest.fixture
    def mock_client(self) -> _TrafficRuleMixin:
        """Create a mock client for testing."""
        client = _TrafficRuleMixin()
        client._request_v2 = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_get_traffic_rules(self, mock_client: _TrafficRuleMixin) -> None:
        """Test get_traffic_rules method."""
        mock_client._request_v2.return_value = [
            {"_id": "rule1", "description": "Block Streaming"}
        ]

        result = await mock_client.get_traffic_rules()

        assert len(result) == 1
        mock_client._request_v2.assert_called_once_with("GET", "/trafficrules")

    @pytest.mark.asyncio
    async def test_set_traffic_rule_enabled(
        self, mock_client: _TrafficRuleMixin
    ) -> None:
        """Test set_traffic_rule_enabled enables a rule found by ID."""
        mock_client.get_traffic_rules = AsyncMock(
            return_value=[
                {"_id": "rule1", "description": "Block Streaming", "enabled": False},
                {"_id": "rule2", "description": "Allow Gaming", "enabled": True},
            ]
        )

        result = await mock_client.set_traffic_rule_enabled("rule1", True)

        assert result is True
        mock_client._request_v2.assert_called_once_with(
            "PUT",
            "/trafficrules/rule1",
            json={"_id": "rule1", "description": "Block Streaming", "enabled": True},
        )

    @pytest.mark.asyncio
    async def test_set_traffic_rule_enabled_not_found(
        self, mock_client: _TrafficRuleMixin
    ) -> None:
        """Test set_traffic_rule_enabled raises when the rule ID doesn't exist."""
        mock_client.get_traffic_rules = AsyncMock(return_value=[])

        with pytest.raises(UniFiError, match="Traffic rule not found"):
            await mock_client.set_traffic_rule_enabled("missing", True)

    @pytest.mark.asyncio
    async def test_create_traffic_rule(self, mock_client: _TrafficRuleMixin) -> None:
        """Test create_traffic_rule method."""
        mock_client._request_v2.return_value = [
            {"_id": "rule1", "description": "Block Streaming"}
        ]

        result = await mock_client.create_traffic_rule(
            {"description": "Block Streaming", "action": "BLOCK"}
        )

        assert result == {"_id": "rule1", "description": "Block Streaming"}
        mock_client._request_v2.assert_called_once_with(
            "POST",
            "/trafficrules",
            json={"description": "Block Streaming", "action": "BLOCK"},
        )

    @pytest.mark.asyncio
    async def test_create_traffic_rule_empty_response(
        self, mock_client: _TrafficRuleMixin
    ) -> None:
        """Test create_traffic_rule returns {} when the controller sends nothing back."""
        mock_client._request_v2.return_value = []

        result = await mock_client.create_traffic_rule({"description": "Test"})

        assert result == {}

    @pytest.mark.asyncio
    async def test_update_traffic_rule(self, mock_client: _TrafficRuleMixin) -> None:
        """Test update_traffic_rule writes the full given object without merging."""
        mock_client._request_v2.return_value = []
        rule = {"_id": "rule1", "description": "Block Streaming", "enabled": True}

        result = await mock_client.update_traffic_rule("rule1", rule)

        assert result is True
        mock_client._request_v2.assert_called_once_with(
            "PUT", "/trafficrules/rule1", json=rule
        )

    @pytest.mark.asyncio
    async def test_delete_traffic_rule(self, mock_client: _TrafficRuleMixin) -> None:
        """Test delete_traffic_rule method."""
        mock_client._request_v2.return_value = []

        result = await mock_client.delete_traffic_rule("rule1")

        assert result is True
        mock_client._request_v2.assert_called_once_with("DELETE", "/trafficrules/rule1")
